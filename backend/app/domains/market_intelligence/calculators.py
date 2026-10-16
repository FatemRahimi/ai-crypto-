"""Deterministic measurements from verified candles.

A pivot is confirmed only after the required later candles exist.
These functions do not emit a trade direction, a probability, or a price forecast.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum

from app.domains.market_data.quality import detect_candle_gaps, ensure_utc

CALCULATOR_VERSION = "technical-evidence-v1"
EVIDENCE_TYPES = (
    "swing_structure",
    "support_resistance",
    "range_statistics",
    "candle_vwap",
)
PIVOT_TYPES = ("swing_structure", "support_resistance")


class EvidenceStatus(StrEnum):
    VALID = "VALID"
    GAP_DETECTED = "GAP_DETECTED"
    INSUFFICIENT = "INSUFFICIENT"
    INVALID = "INVALID"


@dataclass(frozen=True, slots=True)
class InputCandle:
    candle_id: int
    open_time: datetime
    close_time: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal


@dataclass(frozen=True, slots=True)
class Pivot:
    kind: str
    price: Decimal
    candle_id: int
    pivot_open_time: datetime
    confirmed_at: datetime


@dataclass(frozen=True, slots=True)
class EvidenceDraft:
    evidence_type: str
    calculator_name: str
    calculator_version: str
    parameters: dict[str, object]
    observation_time: datetime | None
    input_open_start: datetime | None
    input_open_end: datetime | None
    input_candle_ids: tuple[int, ...]
    input_fingerprint: str
    data_status: EvidenceStatus
    result: dict[str, object]


def evaluate(
    evidence_type: str,
    candles: list[InputCandle],
    interval: str,
    parameters: Mapping[str, object],
) -> EvidenceDraft:
    if evidence_type not in EVIDENCE_TYPES:
        raise ValueError("unsupported evidence type")
    stored = dict(parameters)
    problem = _series_problem(evidence_type, candles, interval, stored)
    if problem is not None:
        return problem
    ordered = _ordered(candles)
    if evidence_type == "swing_structure":
        return _swing(ordered, interval, stored)
    if evidence_type == "support_resistance":
        return _levels(ordered, interval, stored)
    if evidence_type == "range_statistics":
        return _range(ordered, stored)
    return _vwap(ordered, stored)


def input_fingerprint(candles: list[InputCandle]) -> str:
    """SHA-256 of canonical candle content. This is not Python hash()."""
    ordered = sorted(candles, key=_fingerprint_order)
    payload = [
        {
            "candle_id": candle.candle_id,
            "open_time": _iso(candle.open_time),
            "close_time": _iso(candle.close_time),
            "open": _fingerprint_decimal(candle.open),
            "high": _fingerprint_decimal(candle.high),
            "low": _fingerprint_decimal(candle.low),
            "close": _fingerprint_decimal(candle.close),
            "volume": _fingerprint_decimal(candle.volume),
        }
        for candle in ordered
    ]
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def parameter_set(
    evidence_type: str,
    *,
    candle_limit: int,
    left: int,
    right: int,
    start: datetime | None,
    end: datetime | None,
) -> dict[str, object]:
    parameters: dict[str, object] = {"candle_limit": candle_limit}
    if evidence_type in PIVOT_TYPES:
        parameters["left"] = left
        parameters["right"] = right
    if start is not None:
        parameters["start"] = _iso(start)
    if end is not None:
        parameters["end"] = _iso(end)
    return parameters


def _series_problem(
    evidence_type: str,
    candles: list[InputCandle],
    interval: str,
    parameters: dict[str, object],
) -> EvidenceDraft | None:
    if not candles:
        return _draft(
            evidence_type,
            parameters,
            candles,
            EvidenceStatus.INSUFFICIENT,
            {"reason": "no verified candles"},
            observation_time=None,
        )
    ordered = _ordered(candles)
    seen: set[datetime] = set()
    for candle in ordered:
        opened = ensure_utc(candle.open_time)
        closed = ensure_utc(candle.close_time)
        if not isinstance(opened, datetime) or not isinstance(closed, datetime):
            return _draft(
                evidence_type,
                parameters,
                [],
                EvidenceStatus.INVALID,
                {"reason": "naive timestamp"},
                observation_time=None,
            )
        if opened in seen:
            return _draft(
                evidence_type,
                parameters,
                [],
                EvidenceStatus.INVALID,
                {"reason": "duplicate open_time"},
                observation_time=None,
            )
        seen.add(opened)
    gaps = detect_candle_gaps(interval, [candle.open_time for candle in ordered])
    if gaps:
        return _draft(
            evidence_type,
            parameters,
            ordered,
            EvidenceStatus.GAP_DETECTED,
            {"reason": "missing candles", "gap_count": len(gaps)},
        )
    return None


def _swing(
    candles: list[InputCandle],
    interval: str,
    parameters: dict[str, object],
) -> EvidenceDraft:
    del interval
    left = _lookback(parameters, "left")
    right = _lookback(parameters, "right")
    needed = left + right + 1
    if len(candles) < needed:
        return _draft(
            "swing_structure",
            parameters,
            candles,
            EvidenceStatus.INSUFFICIENT,
            {"reason": f"need at least {needed} candles", "pivots": [], "structure": []},
        )
    pivots = _pivots(candles, left, right)
    return _draft(
        "swing_structure",
        parameters,
        candles,
        EvidenceStatus.VALID,
        {
            "rule": "strict_fractal_confirmed_after_right_candles",
            "pivots": [_pivot_payload(pivot) for pivot in pivots],
            "structure": _structure(pivots),
        },
    )


def _levels(
    candles: list[InputCandle],
    interval: str,
    parameters: dict[str, object],
) -> EvidenceDraft:
    del interval
    left = _lookback(parameters, "left")
    right = _lookback(parameters, "right")
    needed = left + right + 1
    if len(candles) < needed:
        return _draft(
            "support_resistance",
            parameters,
            candles,
            EvidenceStatus.INSUFFICIENT,
            {"reason": f"need at least {needed} candles", "levels": []},
        )
    grouped: dict[tuple[str, Decimal], list[Pivot]] = {}
    for pivot in _pivots(candles, left, right):
        role = "resistance" if pivot.kind == "high" else "support"
        grouped.setdefault((role, pivot.price), []).append(pivot)
    levels = []
    ordered_levels = sorted(grouped.items(), key=lambda item: (item[0][0], item[0][1]))
    for (role, price), members in ordered_levels:
        levels.append(
            {
                "role": role,
                "price": _decimal_text(price),
                "touch_count": len(members),
                "candle_ids": [member.candle_id for member in members],
            }
        )
    return _draft(
        "support_resistance",
        parameters,
        candles,
        EvidenceStatus.VALID,
        {
            "rule": "exact_confirmed_pivot_price",
            "touch_count_definition": (
                "Number of confirmed pivots at this exact price. Not a strength rating."
            ),
            "levels": levels,
        },
    )


def _range(candles: list[InputCandle], parameters: dict[str, object]) -> EvidenceDraft:
    if not candles:
        return _draft(
            "range_statistics",
            parameters,
            candles,
            EvidenceStatus.INSUFFICIENT,
            {"reason": "no verified candles"},
            observation_time=None,
        )
    high = max(candle.high for candle in candles)
    low = min(candle.low for candle in candles)
    span = high - low
    midpoint = (high + low) / Decimal(2)
    percentage = (span / low) * Decimal(100)
    return _draft(
        "range_statistics",
        parameters,
        candles,
        EvidenceStatus.VALID,
        {
            "high": _decimal_text(high),
            "low": _decimal_text(low),
            "range": _decimal_text(span),
            "midpoint": _decimal_text(midpoint),
            "percentage_range": _decimal_text(percentage),
            "candle_count": len(candles),
        },
    )


def _vwap(candles: list[InputCandle], parameters: dict[str, object]) -> EvidenceDraft:
    limitation = {
        "price_proxy": "hlc3",
        "price_proxy_definition": "(high + low + close) / 3",
        "volume_field": "volume",
        "volume_definition": "candle base-asset volume",
        "limitation": "candle_proxy_not_trade_vwap",
    }
    total_volume = sum((candle.volume for candle in candles), Decimal(0))
    if total_volume == 0:
        return _draft(
            "candle_vwap",
            parameters,
            candles,
            EvidenceStatus.INSUFFICIENT,
            {"reason": "total volume is zero", **limitation},
        )
    weighted = sum(
        (
            ((candle.high + candle.low + candle.close) / Decimal(3)) * candle.volume
            for candle in candles
        ),
        Decimal(0),
    )
    return _draft(
        "candle_vwap",
        parameters,
        candles,
        EvidenceStatus.VALID,
        {
            "vwap": _decimal_text(weighted / total_volume),
            "total_volume": _decimal_text(total_volume),
            **limitation,
        },
    )


def _pivots(candles: list[InputCandle], left: int, right: int) -> list[Pivot]:
    found: list[Pivot] = []
    for index in range(left, len(candles) - right):
        candle = candles[index]
        earlier = candles[index - left : index]
        later = candles[index + 1 : index + 1 + right]
        neighbors = earlier + later
        confirmed_at = candles[index + right].close_time
        if all(candle.high > neighbor.high for neighbor in neighbors):
            found.append(
                Pivot("high", candle.high, candle.candle_id, candle.open_time, confirmed_at)
            )
        if all(candle.low < neighbor.low for neighbor in neighbors):
            found.append(Pivot("low", candle.low, candle.candle_id, candle.open_time, confirmed_at))
    return found


def _structure(pivots: list[Pivot]) -> list[dict[str, object]]:
    facts: list[dict[str, object]] = []
    for kind, higher, lower, equal in (
        ("high", "higher_high", "lower_high", "equal_high"),
        ("low", "higher_low", "lower_low", "equal_low"),
    ):
        previous: Pivot | None = None
        for pivot in pivots:
            if pivot.kind != kind:
                continue
            if previous is not None:
                if pivot.price > previous.price:
                    label = higher
                elif pivot.price < previous.price:
                    label = lower
                else:
                    label = equal
                facts.append(
                    {
                        "label": label,
                        "price": _decimal_text(pivot.price),
                        "previous_price": _decimal_text(previous.price),
                        "candle_id": pivot.candle_id,
                        "confirmed_at": _iso(pivot.confirmed_at),
                    }
                )
            previous = pivot
    return facts


def _pivot_payload(pivot: Pivot) -> dict[str, object]:
    return {
        "kind": pivot.kind,
        "price": _decimal_text(pivot.price),
        "candle_id": pivot.candle_id,
        "pivot_open_time": _iso(pivot.pivot_open_time),
        "confirmed_at": _iso(pivot.confirmed_at),
    }


def _draft(
    evidence_type: str,
    parameters: dict[str, object],
    candles: list[InputCandle],
    status: EvidenceStatus,
    result: dict[str, object],
    *,
    observation_time: datetime | None = None,
) -> EvidenceDraft:
    ordered = _ordered(candles)
    if ordered and observation_time is None:
        observation_time = ordered[-1].close_time
    return EvidenceDraft(
        evidence_type=evidence_type,
        calculator_name=evidence_type,
        calculator_version=CALCULATOR_VERSION,
        parameters=parameters,
        observation_time=observation_time,
        input_open_start=ordered[0].open_time if ordered else None,
        input_open_end=ordered[-1].open_time if ordered else None,
        input_candle_ids=tuple(candle.candle_id for candle in ordered),
        input_fingerprint=input_fingerprint(ordered),
        data_status=status,
        result=result,
    )


def _ordered(candles: list[InputCandle]) -> list[InputCandle]:
    def key(candle: InputCandle) -> tuple[int, datetime]:
        opened = ensure_utc(candle.open_time)
        if isinstance(opened, datetime):
            return (0, opened)
        return (1, datetime.min.replace(tzinfo=UTC))

    return sorted(candles, key=key)


def _lookback(parameters: dict[str, object], name: str) -> int:
    value = parameters[name]
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError("lookback must be a positive integer")
    return value


def _decimal_text(value: Decimal) -> str:
    return format(value, "f")


def _fingerprint_decimal(value: Decimal) -> str:
    return format(value.quantize(Decimal("1e-18")), "f")


def _fingerprint_order(candle: InputCandle) -> tuple[datetime, int]:
    opened = ensure_utc(candle.open_time)
    if not isinstance(opened, datetime):
        raise ValueError("timestamp must be timezone-aware")
    return (opened, candle.candle_id)


def _iso(value: datetime) -> str:
    stamped = ensure_utc(value)
    if not isinstance(stamped, datetime):
        raise ValueError("timestamp must be timezone-aware")
    return stamped.isoformat().replace("+00:00", "Z")
