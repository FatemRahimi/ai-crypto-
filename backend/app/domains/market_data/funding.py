"""USD-M funding observations.

The provider does not prove that a returned window contains every funding
charge. This module records the rows it accepted. It does not invent a
cadence, fill a missing timestamp, or call a rate a trade signal.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Literal

from app.domains.market_data.identity import BTC_USDT_USD_M_PERPETUAL, MarketIdentity
from app.domains.market_data.quality import (
    MONEY_SCALE,
    Rejection,
    ensure_utc,
    parse_millis,
    parse_money,
)

FUNDING_NORMALIZATION_VERSION = "binance-usdm-funding-v1"
FUNDING_ENDPOINT = "GET /fapi/v1/fundingRate"
RATE_TYPES = ("Regular", "Special")
PAGE_LIMIT = 1000
FundingStop = Literal["empty", "short_page", "cap", "no_progress"]


class FundingCompleteness(StrEnum):
    EMPTY = "EMPTY"
    INVALID = "INVALID"
    COMPLETENESS_UNKNOWN = "COMPLETENESS_UNKNOWN"


@dataclass(frozen=True, slots=True)
class CanonicalFunding:
    identity: MarketIdentity
    symbol: str
    funding_time: datetime
    funding_rate: Decimal
    rate_type: str
    content_fingerprint: str
    endpoint: str
    normalization_version: str
    ingested_at: datetime


@dataclass(frozen=True, slots=True)
class FundingPageRun:
    pages: tuple[tuple[object, ...], ...]
    stop: FundingStop
    saw_full_page: bool


@dataclass(frozen=True, slots=True)
class PreparedFunding:
    rows: tuple[CanonicalFunding, ...]
    duplicates: int
    conflicts: int
    invalid_reason: str | None


def funding_fingerprint(
    identity: MarketIdentity,
    *,
    symbol: str,
    funding_time: datetime,
    funding_rate: Decimal,
    rate_type: str,
) -> str:
    """SHA-256 of one funding observation. This is not Python hash()."""
    encoded = json.dumps(
        _row_payload(
            identity,
            symbol=symbol,
            funding_time=funding_time,
            funding_rate=funding_rate,
            rate_type=rate_type,
        ),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def funding_window_fingerprint(
    rows: list[CanonicalFunding],
    *,
    start: datetime,
    end: datetime,
) -> str:
    """SHA-256 of the request bounds and the ordered canonical rows."""
    ordered = sorted(rows, key=_order)
    payload = {
        "requested_end": _iso(end),
        "requested_start": _iso(start),
        "rows": [
            _row_payload(
                row.identity,
                symbol=row.symbol,
                funding_time=row.funding_time,
                funding_rate=row.funding_rate,
                rate_type=row.rate_type,
            )
            for row in ordered
        ],
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def retrieve_funding_pages(
    fetch_page: Callable[[int, int, int], list[object]],
    *,
    start_ms: int,
    end_ms: int,
    page_limit: int,
    max_rows: int,
) -> FundingPageRun:
    """Page an inclusive window. A full page restarts at the last fundingTime.

    The restart is inclusive. Callers dedupe. This function does not add one
    millisecond, and it stops if the inclusive cursor does not advance.
    """
    if page_limit < 1 or page_limit > PAGE_LIMIT:
        raise ValueError("funding page limit must be from 1 to 1000")
    if max_rows < 1:
        raise ValueError("funding row cap must be positive")
    if end_ms < start_ms:
        raise ValueError("end is before start")
    pages: list[tuple[object, ...]] = []
    collected = 0
    cursor = start_ms
    saw_full_page = False
    stop: FundingStop = "short_page"
    while collected < max_rows:
        limit = min(page_limit, max_rows - collected)
        page = fetch_page(cursor, end_ms, limit)
        if not page:
            stop = "empty" if not pages else "short_page"
            break
        pages.append(tuple(page))
        collected += len(page)
        if len(page) < limit:
            stop = "short_page"
            break
        saw_full_page = True
        last_time = _funding_time_ms(page[-1])
        if last_time is None or last_time < cursor or last_time == cursor:
            stop = "no_progress"
            break
        if collected >= max_rows:
            stop = "cap"
            break
        cursor = last_time
    return FundingPageRun(pages=tuple(pages), stop=stop, saw_full_page=saw_full_page)


def normalize_funding_row(
    row: object,
    identity: MarketIdentity,
    ingested_at: datetime,
) -> CanonicalFunding | Rejection:
    if identity != BTC_USDT_USD_M_PERPETUAL:
        return Rejection("funding identity is not the USD-M perpetual")
    if not isinstance(row, dict):
        return Rejection("funding row was not an object")
    symbol = row.get("symbol")
    if symbol != identity.provider_symbol:
        return Rejection("unexpected funding symbol")
    funding_time = parse_millis(row.get("fundingTime"), field="fundingTime")
    if isinstance(funding_time, Rejection):
        return funding_time
    funding_rate = parse_money(row.get("fundingRate"), field="fundingRate")
    if isinstance(funding_rate, Rejection):
        return funding_rate
    rate_type = row.get("rateType")
    if rate_type not in RATE_TYPES:
        return Rejection("invalid rateType")
    stamped = ensure_utc(ingested_at)
    if isinstance(stamped, Rejection):
        return stamped
    fingerprint = funding_fingerprint(
        identity,
        symbol=symbol,
        funding_time=funding_time,
        funding_rate=funding_rate,
        rate_type=rate_type,
    )
    return CanonicalFunding(
        identity=identity,
        symbol=symbol,
        funding_time=funding_time,
        funding_rate=funding_rate,
        rate_type=rate_type,
        content_fingerprint=fingerprint,
        endpoint=FUNDING_ENDPOINT,
        normalization_version=FUNDING_NORMALIZATION_VERSION,
        ingested_at=stamped,
    )


def prepare_funding_rows(
    rows: list[CanonicalFunding],
    *,
    start: datetime,
    end: datetime,
) -> PreparedFunding:
    """Dedupe inclusive page overlap. A changed rate for the same identity conflicts."""
    kept: list[CanonicalFunding] = []
    seen: dict[tuple[datetime, str], CanonicalFunding] = {}
    duplicates = 0
    conflicts = 0
    conflict_keys: list[tuple[datetime, str]] = []
    for row in rows:
        if row.funding_time < start or row.funding_time > end:
            return PreparedFunding((), duplicates, conflicts, "funding_time_outside_window")
        key = (row.funding_time, row.rate_type)
        prior = seen.get(key)
        if prior is None:
            seen[key] = row
            kept.append(row)
            continue
        if prior.content_fingerprint == row.content_fingerprint:
            duplicates += 1
            continue
        conflicts += 1
        conflict_keys.append(key)
    if conflict_keys:
        blocked = set(conflict_keys)
        kept = [row for row in kept if (row.funding_time, row.rate_type) not in blocked]
    kept.sort(key=_order)
    return PreparedFunding(tuple(kept), duplicates, conflicts, None)


def assess_funding_completeness(
    *,
    stop: FundingStop,
    invalid_reason: str | None,
    conflicts: int,
    row_count: int,
) -> tuple[FundingCompleteness, str]:
    """A successful response stays unknown. Spacing is not a gap."""
    if invalid_reason is not None:
        return FundingCompleteness.INVALID, invalid_reason
    if stop == "no_progress":
        return FundingCompleteness.INVALID, "pagination_no_progress"
    if conflicts:
        return FundingCompleteness.INVALID, "conflicting_funding_content"
    if row_count == 0 and stop == "empty":
        return FundingCompleteness.EMPTY, "provider_returned_no_funding_rows"
    return FundingCompleteness.COMPLETENESS_UNKNOWN, "historical_funding_coverage_not_proven"


def _funding_time_ms(row: object) -> int | None:
    if not isinstance(row, dict):
        return None
    value = row.get("fundingTime")
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


def _order(row: CanonicalFunding) -> tuple[datetime, str]:
    return (row.funding_time, row.rate_type)


def _row_payload(
    identity: MarketIdentity,
    *,
    symbol: str,
    funding_time: datetime,
    funding_rate: Decimal,
    rate_type: str,
) -> dict[str, object]:
    return {
        "canonical_symbol": identity.canonical_symbol,
        "funding_rate": format(funding_rate.quantize(MONEY_SCALE), "f"),
        "funding_time": _iso(funding_time),
        "market_type": identity.market_type,
        "provider": identity.provider,
        "provider_symbol": identity.provider_symbol,
        "rate_type": rate_type,
        "symbol": symbol,
    }


def _iso(value: datetime) -> str:
    stamped = ensure_utc(value)
    if isinstance(stamped, Rejection):
        raise ValueError(stamped.reason)
    return stamped.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
