"""Deterministic checks for market observations.

Invalid rows are rejected. This module does not rewrite prices or fill gaps.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from enum import StrEnum

from app.domains.market_data.identity import SUPPORTED_INTERVALS


class DataStatus(StrEnum):
    VALID = "VALID"
    STALE = "STALE"
    GAP_DETECTED = "GAP_DETECTED"
    INVALID = "INVALID"


INTERVAL_DURATION = {
    "1m": timedelta(minutes=1),
    "5m": timedelta(minutes=5),
    "15m": timedelta(minutes=15),
    "1h": timedelta(hours=1),
    "4h": timedelta(hours=4),
    "1d": timedelta(days=1),
}

STALE_INTERVAL_MULTIPLE = 2


@dataclass(frozen=True, slots=True)
class Rejection:
    reason: str


@dataclass(frozen=True, slots=True)
class CandleGap:
    after_open_time: datetime
    missing_open_time: datetime
    missing_intervals: int


def ensure_utc(value: datetime) -> datetime | Rejection:
    if value.tzinfo is None or value.utcoffset() is None:
        return Rejection("timestamp must be timezone-aware")
    return value.astimezone(UTC)


MONEY_SCALE = Decimal("1e-18")
MONEY_ABS_LIMIT = Decimal("1e20")
INT64_MAX = 2**63 - 1


def parse_money(value: object, *, field: str) -> Decimal | Rejection:
    """Accept a decimal string that fits numeric(38, 18) without rounding."""
    number = parse_decimal(value, field=field)
    if isinstance(number, Rejection):
        return number
    if number != number.quantize(MONEY_SCALE):
        return Rejection(f"{field} has more than 18 decimal places")
    if abs(number) >= MONEY_ABS_LIMIT:
        return Rejection(f"{field} exceeds stored precision")
    return number


def parse_int64(value: object, *, field: str) -> int | Rejection:
    if isinstance(value, bool) or not isinstance(value, int):
        return Rejection(f"{field} must be an integer")
    if value < 0 or value > INT64_MAX:
        return Rejection(f"{field} is outside signed 64-bit range")
    return value


def parse_decimal(value: object, *, field: str) -> Decimal | Rejection:
    if not isinstance(value, str):
        return Rejection(f"{field} must be a decimal string")
    try:
        number = Decimal(value)
    except Exception:
        return Rejection(f"{field} is not a decimal")
    if not number.is_finite():
        return Rejection(f"{field} is not finite")
    return number


def parse_millis(value: object, *, field: str) -> datetime | Rejection:
    if isinstance(value, bool) or not isinstance(value, int):
        return Rejection(f"{field} must be integer milliseconds")
    if value < 0:
        return Rejection(f"{field} is negative")
    return datetime.fromtimestamp(value / 1000, tz=UTC)


def validate_candle_shape(
    *,
    interval: str,
    open_time: datetime,
    close_time: datetime,
    open_: Decimal,
    high: Decimal,
    low: Decimal,
    close: Decimal,
    volume: Decimal,
    quote_volume: Decimal | None,
) -> Rejection | None:
    if interval not in SUPPORTED_INTERVALS:
        return Rejection("unsupported interval")
    opened = ensure_utc(open_time)
    closed = ensure_utc(close_time)
    if isinstance(opened, Rejection):
        return opened
    if isinstance(closed, Rejection):
        return closed
    if closed <= opened:
        return Rejection("close_time must be after open_time")
    duration = INTERVAL_DURATION[interval]
    if closed - opened > duration:
        return Rejection("candle span is longer than the interval")
    for name, number in (
        ("open", open_),
        ("high", high),
        ("low", low),
        ("close", close),
    ):
        if number <= 0:
            return Rejection(f"negative or zero {name}")
    if volume < 0:
        return Rejection("negative volume")
    if quote_volume is not None and quote_volume < 0:
        return Rejection("negative quote volume")
    if high < low:
        return Rejection("high is below low")
    if open_ > high or open_ < low:
        return Rejection("open is outside the high-low range")
    if close > high or close < low:
        return Rejection("close is outside the high-low range")
    return None


def validate_trade(
    *,
    price: Decimal,
    quantity: Decimal,
    quote_quantity: Decimal | None,
    event_time: datetime,
) -> Rejection | None:
    event = ensure_utc(event_time)
    if isinstance(event, Rejection):
        return event
    if price <= 0:
        return Rejection("negative or zero price")
    if quantity <= 0:
        return Rejection("negative or zero quantity")
    if quote_quantity is not None and quote_quantity < 0:
        return Rejection("negative quote quantity")
    return None


def is_closed_candle(close_time: datetime, now: datetime) -> bool:
    closed = ensure_utc(close_time)
    current = ensure_utc(now)
    if isinstance(closed, Rejection) or isinstance(current, Rejection):
        return False
    return closed <= current


def find_duplicate_open_times(open_times: list[datetime]) -> set[datetime]:
    seen: set[datetime] = set()
    duplicates: set[datetime] = set()
    for item in open_times:
        if item in seen:
            duplicates.add(item)
        seen.add(item)
    return duplicates


def detect_candle_gaps(interval: str, open_times: list[datetime]) -> list[CandleGap]:
    if interval not in INTERVAL_DURATION:
        return []
    step = INTERVAL_DURATION[interval]
    ordered = sorted(open_times)
    gaps: list[CandleGap] = []
    for previous, current in zip(ordered, ordered[1:], strict=False):
        delta = current - previous
        if delta == step:
            continue
        if delta < step:
            continue
        missing = int(delta / step) - 1
        if missing < 1:
            continue
        gaps.append(
            CandleGap(
                after_open_time=previous,
                missing_open_time=previous + step,
                missing_intervals=missing,
            )
        )
    return gaps


def candle_freshness(interval: str, close_time: datetime, now: datetime) -> DataStatus:
    if interval not in INTERVAL_DURATION:
        return DataStatus.INVALID
    closed = ensure_utc(close_time)
    current = ensure_utc(now)
    if isinstance(closed, Rejection) or isinstance(current, Rejection):
        return DataStatus.INVALID
    limit = INTERVAL_DURATION[interval] * STALE_INTERVAL_MULTIPLE
    if current - closed > limit:
        return DataStatus.STALE
    return DataStatus.VALID


def trade_freshness(event_time: datetime, now: datetime, *, max_age: timedelta) -> DataStatus:
    event = ensure_utc(event_time)
    current = ensure_utc(now)
    if isinstance(event, Rejection) or isinstance(current, Rejection):
        return DataStatus.INVALID
    if current - event > max_age:
        return DataStatus.STALE
    return DataStatus.VALID
