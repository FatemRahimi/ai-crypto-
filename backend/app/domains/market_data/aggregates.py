"""Aggregate-trade identity, fingerprint, and completeness.

Binance documents `a`, `f`, and `l` as aggregate, first, and last trade ids.
It does not document that those integers are a gap-free ledger of every
trade in a clock window. This module does not fill holes and does not treat
HTTP success as coverage.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from app.domains.market_data.quality import Rejection, ensure_utc
from app.domains.market_data.records import CanonicalAggregateTrade

_MONEY = Decimal("1e-18")


class CompletenessStatus(StrEnum):
    COMPLETE = "COMPLETE"
    GAP_DETECTED = "GAP_DETECTED"
    EMPTY = "EMPTY"
    INVALID = "INVALID"
    COMPLETENESS_UNKNOWN = "COMPLETENESS_UNKNOWN"


@dataclass(frozen=True, slots=True)
class AggregateGap:
    after_aggregate_id: int
    next_aggregate_id: int


@dataclass(frozen=True, slots=True)
class PreparedAggregates:
    trades: tuple[CanonicalAggregateTrade, ...]
    duplicates: int
    conflicts: int
    conflict_ids: tuple[int, ...]
    invalid_reason: str | None


@dataclass(frozen=True, slots=True)
class CompletenessAssessment:
    status: CompletenessStatus
    reason: str
    gaps: tuple[AggregateGap, ...]

    def details(self, *, page_count: int, stop: str, saw_full_page: bool) -> dict[str, object]:
        body: dict[str, object] = {
            "reason": self.reason,
            "page_count": page_count,
            "retrieval_stop": stop,
            "saw_full_page": saw_full_page,
            "limitation": _LIMITATIONS[self.status],
        }
        if self.gaps:
            body["gaps"] = [
                {
                    "after_aggregate_id": gap.after_aggregate_id,
                    "next_aggregate_id": gap.next_aggregate_id,
                }
                for gap in self.gaps
            ]
        return body


_LIMITATIONS = {
    CompletenessStatus.COMPLETE: (
        "complete_means_one_short_page_of_chained_single_trade_ids"
    ),
    CompletenessStatus.GAP_DETECTED: "returned_aggregate_id_hole_was_not_filled",
    CompletenessStatus.EMPTY: "empty_response_is_not_proof_the_market_was_idle",
    CompletenessStatus.INVALID: "rejected_response_stored_no_aggregate_trades",
    CompletenessStatus.COMPLETENESS_UNKNOWN: (
        "binance_ids_are_not_documented_as_a_complete_clock_window_ledger"
    ),
}


def aggregate_trade_fingerprint(
    *,
    aggregate_trade_id: int,
    price: Decimal,
    quantity: Decimal,
    event_time: datetime,
    first_trade_id: int,
    last_trade_id: int,
    buyer_is_maker: bool,
) -> str:
    """SHA-256 of one canonical aggregate trade. This is not Python hash()."""
    encoded = json.dumps(
        _payload(
            aggregate_trade_id=aggregate_trade_id,
            price=price,
            quantity=quantity,
            event_time=event_time,
            first_trade_id=first_trade_id,
            last_trade_id=last_trade_id,
            buyer_is_maker=buyer_is_maker,
        ),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def aggregate_window_fingerprint(trades: list[CanonicalAggregateTrade]) -> str:
    """SHA-256 of the trade set. Input order does not change the digest."""
    ordered = sorted(trades, key=_fingerprint_order)
    payload = [
        _payload(
            aggregate_trade_id=trade.aggregate_trade_id,
            price=trade.price,
            quantity=trade.quantity,
            event_time=trade.event_time,
            first_trade_id=trade.first_trade_id,
            last_trade_id=trade.last_trade_id,
            buyer_is_maker=trade.buyer_is_maker,
        )
        for trade in ordered
    ]
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def prepare_aggregate_sequence(
    trades: list[CanonicalAggregateTrade],
) -> PreparedAggregates:
    """Keep response order. Identical repeated ids are duplicates."""
    kept: list[CanonicalAggregateTrade] = []
    seen: dict[int, CanonicalAggregateTrade] = {}
    duplicates = 0
    conflicts = 0
    conflict_ids: list[int] = []
    last_id: int | None = None
    for trade in trades:
        prior = seen.get(trade.aggregate_trade_id)
        if prior is not None:
            if _same_content(prior, trade):
                duplicates += 1
                continue
            conflicts += 1
            conflict_ids.append(trade.aggregate_trade_id)
            continue
        if last_id is not None and trade.aggregate_trade_id <= last_id:
            return _invalid_sequence(
                duplicates,
                conflicts,
                conflict_ids,
                "non_monotonic_aggregate_id",
            )
        if last_id is not None and trade.event_time < kept[-1].event_time:
            return _invalid_sequence(
                duplicates,
                conflicts,
                conflict_ids,
                "non_monotonic_event_time",
            )
        seen[trade.aggregate_trade_id] = trade
        kept.append(trade)
        last_id = trade.aggregate_trade_id
    if conflict_ids:
        blocked = set(conflict_ids)
        kept = [trade for trade in kept if trade.aggregate_trade_id not in blocked]
    return PreparedAggregates(tuple(kept), duplicates, conflicts, tuple(conflict_ids), None)


def assess_aggregate_completeness(
    trades: tuple[CanonicalAggregateTrade, ...],
    *,
    page_count: int,
    stop: str,
    saw_full_page: bool,
    invalid_reason: str | None = None,
) -> CompletenessAssessment:
    """Classify the retrieved sequence. A 200 response is not COMPLETE."""
    if invalid_reason is not None:
        return CompletenessAssessment(CompletenessStatus.INVALID, invalid_reason, ())
    if not trades:
        if stop == "empty" or (stop == "short_page" and page_count == 0 and not saw_full_page):
            return CompletenessAssessment(
                CompletenessStatus.EMPTY,
                "provider_returned_no_rows",
                (),
            )
        return CompletenessAssessment(
            CompletenessStatus.COMPLETENESS_UNKNOWN,
            "no_rows_after_retrieval",
            (),
        )
    overlap = _overlap(trades)
    if overlap is not None:
        return CompletenessAssessment(CompletenessStatus.INVALID, overlap, ())
    gaps = _id_gaps(trades)
    exhaustive = stop == "short_page" and page_count == 1 and not saw_full_page
    if gaps:
        return CompletenessAssessment(
            CompletenessStatus.GAP_DETECTED,
            "aggregate_id_not_contiguous",
            gaps,
        )
    if any(trade.first_trade_id != trade.last_trade_id for trade in trades):
        return CompletenessAssessment(
            CompletenessStatus.COMPLETENESS_UNKNOWN,
            "underlying_trade_id_span_is_aggregated",
            (),
        )
    if _underlying_hole(trades):
        return CompletenessAssessment(
            CompletenessStatus.COMPLETENESS_UNKNOWN,
            "underlying_trade_ids_are_not_contiguous",
            (),
        )
    if not exhaustive:
        return CompletenessAssessment(
            CompletenessStatus.COMPLETENESS_UNKNOWN,
            "response_does_not_prove_the_window",
            (),
        )
    return CompletenessAssessment(
        CompletenessStatus.COMPLETE,
        "single_short_page_contiguous_single_trade_ids",
        (),
    )


def _payload(
    *,
    aggregate_trade_id: int,
    price: Decimal,
    quantity: Decimal,
    event_time: datetime,
    first_trade_id: int,
    last_trade_id: int,
    buyer_is_maker: bool,
) -> dict[str, object]:
    stamped = ensure_utc(event_time)
    if isinstance(stamped, Rejection):
        raise ValueError("timestamp must be timezone-aware")
    return {
        "aggregate_trade_id": aggregate_trade_id,
        "buyer_is_maker": buyer_is_maker,
        "event_time": stamped.isoformat().replace("+00:00", "Z"),
        "first_trade_id": first_trade_id,
        "last_trade_id": last_trade_id,
        "price": format(price.quantize(_MONEY), "f"),
        "quantity": format(quantity.quantize(_MONEY), "f"),
    }


def _fingerprint_order(trade: CanonicalAggregateTrade) -> tuple[int, str]:
    return (trade.aggregate_trade_id, trade.content_fingerprint)


def _invalid_sequence(
    duplicates: int,
    conflicts: int,
    conflict_ids: list[int],
    reason: str,
) -> PreparedAggregates:
    return PreparedAggregates((), duplicates, conflicts, tuple(conflict_ids), reason)


def _same_content(left: CanonicalAggregateTrade, right: CanonicalAggregateTrade) -> bool:
    return left.content_fingerprint == right.content_fingerprint


def _id_gaps(trades: tuple[CanonicalAggregateTrade, ...]) -> tuple[AggregateGap, ...]:
    gaps: list[AggregateGap] = []
    for previous, current in zip(trades, trades[1:], strict=False):
        if current.aggregate_trade_id != previous.aggregate_trade_id + 1:
            gaps.append(
                AggregateGap(
                    after_aggregate_id=previous.aggregate_trade_id,
                    next_aggregate_id=current.aggregate_trade_id,
                )
            )
    return tuple(gaps)


def _overlap(trades: tuple[CanonicalAggregateTrade, ...]) -> str | None:
    for previous, current in zip(trades, trades[1:], strict=False):
        if current.first_trade_id <= previous.last_trade_id:
            return "underlying_trade_ranges_overlap"
    return None


def _underlying_hole(trades: tuple[CanonicalAggregateTrade, ...]) -> bool:
    for previous, current in zip(trades, trades[1:], strict=False):
        if current.first_trade_id != previous.last_trade_id + 1:
            return True
    return False
