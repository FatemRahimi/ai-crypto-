"""Observed volume at an exact stored price, and the observed point of control.

The input is stored aggregate trades. A successful sum is not proof that the
clock window contains every market trade. `buyer_is_maker` is not bid or ask
size and is not summed. The profile fingerprint includes each row's Phase 3B
`content_fingerprint`, so a maker-flag or trade-id change changes evidence
identity even when the base-quantity sum would not. That is stronger source
identity than the arithmetic requires.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from decimal import ROUND_HALF_EVEN, Context, Decimal, InvalidOperation, localcontext
from typing import Literal

from app.domains.market_data.quality import (
    INT64_MAX,
    MONEY_ABS_LIMIT,
    MONEY_SCALE,
    Rejection,
    ensure_utc,
)

CALCULATOR_NAME = "observed-volume-at-price"
CALCULATOR_VERSION = "observed-volume-at-price-v1"
BUCKET_METHOD = "exact_price"
VOLUME_DEFINITION = "base_quantity"
POC_TIE_BREAK = "lower_price"
DERIVED_SHARE_SCALE = Decimal("1e-18")
COVERAGE_LIMITATION = (
    "Based on stored aggregate-trade observations. "
    "Complete clock-window coverage is not proven."
)
EMPTY_LIMITATION = (
    "No stored aggregate trades in the requested window. "
    "This is not proof the market was idle."
)
CONFLICT_LIMITATION = (
    "Same aggregate id has conflicting canonical content. "
    "No observed point of control was calculated."
)
MALFORMED_LIMITATION = (
    "Aggregate-trade values were rejected. No observed point of control was calculated."
)
CAP_LIMITATION = (
    "Stored aggregate-trade read reached the calculation cap. "
    "No observed volume at price was calculated."
)
WINDOW_LIMITATION = "Requested window is not a valid UTC interval."

Sufficiency = Literal["OBSERVED", "INSUFFICIENT", "INVALID"]


@dataclass(frozen=True, slots=True)
class VolumeAggregate:
    aggregate_trade_id: int
    price: Decimal
    quantity: Decimal
    event_time: datetime
    content_fingerprint: str
    first_trade_id: int
    last_trade_id: int
    buyer_is_maker: bool


@dataclass(frozen=True, slots=True)
class ObservedBucket:
    price: Decimal
    observed_base_volume: Decimal
    aggregate_count: int
    derived_share: Decimal


@dataclass(frozen=True, slots=True)
class ObservedVolumeDraft:
    sufficiency: Sufficiency
    reason: str
    limitation: str
    buckets: tuple[ObservedBucket, ...]
    total_observed_base_volume: Decimal | None
    observed_poc_price: Decimal | None
    poc_tie_count: int | None
    poc_tie: bool | None
    largest_aggregate_base_quantity: Decimal | None
    derived_largest_share: Decimal | None
    first_event_time: datetime | None
    last_event_time: datetime | None
    input_aggregate_count: int
    input_fingerprint: str
    parameters_hash: str
    parameters: dict[str, str]
    calculator_name: str
    calculator_version: str
    used: tuple[VolumeAggregate, ...]


def derived_share(part: Decimal, total: Decimal) -> Decimal:
    """Quantized ratio of exact base quantities. The quantities themselves stay exact."""
    with localcontext(Context(prec=60, rounding=ROUND_HALF_EVEN)):
        return (part / total).quantize(DERIVED_SHARE_SCALE, rounding=ROUND_HALF_EVEN)


def parameter_hash(start: datetime, end: datetime) -> tuple[str, dict[str, str]]:
    start_text = _iso(start)
    end_text = _iso(end)
    if start_text is None or end_text is None or start > end:
        payload = {"reason": "invalid_window"}
        return _sha256(payload), {key: str(value) for key, value in payload.items()}
    parameters = {
        "bucket_method": BUCKET_METHOD,
        "poc_tie_break": POC_TIE_BREAK,
        "volume_definition": VOLUME_DEFINITION,
        "window_end": end_text,
        "window_start": start_text,
    }
    return _sha256(parameters), parameters


def profile_input_fingerprint(rows: tuple[VolumeAggregate, ...] | list[VolumeAggregate]) -> str:
    """SHA-256 of calculator inputs plus each row's canonical content fingerprint."""
    payload = [_row_payload(row) for row in sorted(rows, key=_row_order)]
    return _sha256(payload)


def calculate_observed_volume(
    rows: list[VolumeAggregate] | tuple[VolumeAggregate, ...],
    *,
    start: datetime,
    end: datetime,
) -> ObservedVolumeDraft:
    digest, parameters = parameter_hash(start, end)
    if parameters.get("reason") == "invalid_window":
        return _empty_draft(
            sufficiency="INVALID",
            reason="invalid_window",
            limitation=WINDOW_LIMITATION,
            parameters_hash=digest,
            parameters=parameters,
            input_fingerprint=_sha256({"reason": "invalid_window"}),
        )
    members: list[VolumeAggregate] = []
    for row in rows:
        checked = _checked(row)
        if checked is None:
            return _empty_draft(
                sufficiency="INVALID",
                reason="malformed_aggregate_value",
                limitation=MALFORMED_LIMITATION,
                parameters_hash=digest,
                parameters=parameters,
                input_fingerprint=_sha256({"reason": "malformed_aggregate_value"}),
            )
        event = _instant(checked.event_time)
        if event is None:
            return _empty_draft(
                sufficiency="INVALID",
                reason="malformed_aggregate_value",
                limitation=MALFORMED_LIMITATION,
                parameters_hash=digest,
                parameters=parameters,
                input_fingerprint=_sha256({"reason": "malformed_aggregate_value"}),
            )
        if event < start or event > end:
            continue
        members.append(checked)
    prepared = _dedupe(members)
    if isinstance(prepared, str):
        versions = tuple(sorted(members, key=_row_order))
        return _empty_draft(
            sufficiency="INVALID",
            reason=prepared,
            limitation=CONFLICT_LIMITATION,
            parameters_hash=digest,
            parameters=parameters,
            input_fingerprint=profile_input_fingerprint(versions),
            input_aggregate_count=len(versions),
            used=versions,
        )
    if not prepared:
        return _empty_draft(
            sufficiency="INSUFFICIENT",
            reason="no_stored_aggregates",
            limitation=EMPTY_LIMITATION,
            parameters_hash=digest,
            parameters=parameters,
            input_fingerprint=profile_input_fingerprint(()),
        )
    return _measure(prepared, parameters_hash=digest, parameters=parameters)


def capped_read_draft(start: datetime, end: datetime, *, rows_seen: int) -> ObservedVolumeDraft:
    digest, parameters = parameter_hash(start, end)
    fingerprint = _sha256(
        {
            "reason": "stored_row_read_cap_reached",
            "rows_seen": rows_seen,
            "window_end": parameters.get("window_end", ""),
            "window_start": parameters.get("window_start", ""),
        }
    )
    return _empty_draft(
        sufficiency="INVALID",
        reason="stored_row_read_cap_reached",
        limitation=CAP_LIMITATION,
        parameters_hash=digest,
        parameters=parameters,
        input_fingerprint=fingerprint,
    )


def main(argv: list[str] | None = None) -> int:
    import argparse

    from sqlalchemy.exc import SQLAlchemyError

    from app.core.config import get_settings
    from app.domains.market_intelligence.observed_volume_service import ObservedVolumeService

    parser = argparse.ArgumentParser(
        description="Calculate observed volume at price from stored aggregate trades."
    )
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    args = parser.parse_args(argv)
    try:
        start = _parse_cli_time(args.start)
        end = _parse_cli_time(args.end)
        report = ObservedVolumeService.from_settings(get_settings()).calculate(start, end)
    except ValueError as exc:
        print(exc)
        return 2
    except SQLAlchemyError:
        print("observed volume store is unavailable")
        return 1
    print(
        f"sufficiency={report.sufficiency} "
        f"source_completeness={report.source_completeness} "
        f"observed_poc_price={_cli_decimal(report.observed_poc_price)} "
        f"poc_tie_count={report.poc_tie_count} "
        f"inserted={report.inserted} duplicates={report.duplicates} "
        f"conflicts={report.conflicts}"
    )
    return 1 if report.conflicts else 0


def _measure(
    rows: tuple[VolumeAggregate, ...],
    *,
    parameters_hash: str,
    parameters: dict[str, str],
) -> ObservedVolumeDraft:
    totals: dict[Decimal, tuple[Decimal, int]] = {}
    with localcontext(Context(prec=60)):
        for row in rows:
            volume, count = totals.get(row.price, (Decimal(0), 0))
            totals[row.price] = (volume + row.quantity, count + 1)
    total = _exact_sum([item[0] for item in totals.values()])
    if total is None or total <= 0 or total >= MONEY_ABS_LIMIT:
        return _empty_draft(
            sufficiency="INVALID",
            reason="malformed_aggregate_value",
            limitation=MALFORMED_LIMITATION,
            parameters_hash=parameters_hash,
            parameters=parameters,
            input_fingerprint=profile_input_fingerprint(rows),
            input_aggregate_count=len(rows),
            used=rows,
        )
    largest = max(row.quantity for row in rows)
    if largest >= MONEY_ABS_LIMIT:
        return _empty_draft(
            sufficiency="INVALID",
            reason="malformed_aggregate_value",
            limitation=MALFORMED_LIMITATION,
            parameters_hash=parameters_hash,
            parameters=parameters,
            input_fingerprint=profile_input_fingerprint(rows),
            input_aggregate_count=len(rows),
            used=rows,
        )
    buckets = tuple(
        ObservedBucket(
            price=price,
            observed_base_volume=volume,
            aggregate_count=count,
            derived_share=derived_share(volume, total),
        )
        for price, (volume, count) in sorted(totals.items(), key=lambda item: item[0])
    )
    max_volume = max(bucket.observed_base_volume for bucket in buckets)
    tied = [bucket.price for bucket in buckets if bucket.observed_base_volume == max_volume]
    times = [row.event_time for row in rows]
    return ObservedVolumeDraft(
        sufficiency="OBSERVED",
        reason="observed_from_stored_aggregates",
        limitation=COVERAGE_LIMITATION,
        buckets=buckets,
        total_observed_base_volume=total,
        observed_poc_price=min(tied),
        poc_tie_count=len(tied),
        poc_tie=len(tied) > 1,
        largest_aggregate_base_quantity=largest,
        derived_largest_share=derived_share(largest, total),
        first_event_time=min(times),
        last_event_time=max(times),
        input_aggregate_count=len(rows),
        input_fingerprint=profile_input_fingerprint(rows),
        parameters_hash=parameters_hash,
        parameters=parameters,
        calculator_name=CALCULATOR_NAME,
        calculator_version=CALCULATOR_VERSION,
        used=rows,
    )


def _dedupe(rows: list[VolumeAggregate]) -> tuple[VolumeAggregate, ...] | str:
    grouped: dict[int, VolumeAggregate] = {}
    for row in rows:
        prior = grouped.get(row.aggregate_trade_id)
        if prior is None:
            grouped[row.aggregate_trade_id] = row
            continue
        if _same_aggregate(prior, row):
            continue
        return "conflicting_aggregate_content"
    return tuple(grouped.values())


def _same_aggregate(left: VolumeAggregate, right: VolumeAggregate) -> bool:
    return (
        left.price == right.price
        and left.quantity == right.quantity
        and _instant(left.event_time) == _instant(right.event_time)
        and left.content_fingerprint == right.content_fingerprint
        and left.first_trade_id == right.first_trade_id
        and left.last_trade_id == right.last_trade_id
        and left.buyer_is_maker == right.buyer_is_maker
    )


def _checked(row: VolumeAggregate) -> VolumeAggregate | None:
    price = _money(row.price)
    quantity = _money(row.quantity)
    event = _instant(row.event_time)
    aggregate_id = _identifier(row.aggregate_trade_id)
    first_trade_id = _identifier(row.first_trade_id)
    last_trade_id = _identifier(row.last_trade_id)
    if (
        price is None
        or quantity is None
        or event is None
        or aggregate_id is None
        or first_trade_id is None
        or last_trade_id is None
        or last_trade_id < first_trade_id
        or not isinstance(row.buyer_is_maker, bool)
        or not _fingerprint(row.content_fingerprint)
    ):
        return None
    return VolumeAggregate(
        aggregate_trade_id=aggregate_id,
        price=price,
        quantity=quantity,
        event_time=event,
        content_fingerprint=row.content_fingerprint,
        first_trade_id=first_trade_id,
        last_trade_id=last_trade_id,
        buyer_is_maker=row.buyer_is_maker,
    )


def _empty_draft(
    *,
    sufficiency: Sufficiency,
    reason: str,
    limitation: str,
    parameters_hash: str,
    parameters: dict[str, str],
    input_fingerprint: str,
    input_aggregate_count: int = 0,
    used: tuple[VolumeAggregate, ...] = (),
) -> ObservedVolumeDraft:
    return ObservedVolumeDraft(
        sufficiency=sufficiency,
        reason=reason,
        limitation=limitation,
        buckets=(),
        total_observed_base_volume=None,
        observed_poc_price=None,
        poc_tie_count=None,
        poc_tie=None,
        largest_aggregate_base_quantity=None,
        derived_largest_share=None,
        first_event_time=None,
        last_event_time=None,
        input_aggregate_count=input_aggregate_count,
        input_fingerprint=input_fingerprint,
        parameters_hash=parameters_hash,
        parameters=parameters,
        calculator_name=CALCULATOR_NAME,
        calculator_version=CALCULATOR_VERSION,
        used=used,
    )


def _money(value: object) -> Decimal | None:
    if not isinstance(value, Decimal) or not value.is_finite():
        return None
    try:
        quantized = value.quantize(MONEY_SCALE, context=Context(prec=38))
    except InvalidOperation:
        return None
    if value != quantized:
        return None
    if value <= 0 or value >= MONEY_ABS_LIMIT:
        return None
    return value


def _exact_sum(values: list[Decimal]) -> Decimal | None:
    try:
        with localcontext(Context(prec=60)):
            total = sum(values, Decimal(0))
            if total != total.quantize(MONEY_SCALE):
                return None
            return total
    except InvalidOperation:
        return None


def _identifier(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    if value < 0 or value > INT64_MAX:
        return None
    return value


def _fingerprint(value: object) -> bool:
    if not isinstance(value, str) or len(value) != 64:
        return False
    return all(char in "0123456789abcdef" for char in value)


def _instant(value: datetime) -> datetime | None:
    stamped = ensure_utc(value)
    if isinstance(stamped, Rejection):
        return None
    return stamped


def _iso(value: datetime) -> str | None:
    stamped = _instant(value)
    if stamped is None:
        return None
    return stamped.isoformat().replace("+00:00", "Z")


def _row_payload(row: VolumeAggregate) -> dict[str, object]:
    return {
        "aggregate_trade_id": row.aggregate_trade_id,
        "content_fingerprint": row.content_fingerprint,
        "event_time": _iso(row.event_time),
        "price": format(row.price, "f"),
        "quantity": format(row.quantity, "f"),
    }


def _row_order(row: VolumeAggregate) -> tuple[int, str, str, str, str]:
    return (
        row.aggregate_trade_id,
        row.content_fingerprint,
        format(row.price, "f"),
        format(row.quantity, "f"),
        _iso(row.event_time) or "",
    )


def _sha256(payload: object) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _parse_cli_time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("timestamp must be timezone-aware")
    return parsed


def _cli_decimal(value: Decimal | None) -> str:
    if value is None:
        return "none"
    return format(value, "f")


if __name__ == "__main__":
    raise SystemExit(main())
