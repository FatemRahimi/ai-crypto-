from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.domains.market_data.identity import BTC_USDT_SPOT
from app.domains.market_data.normalize import normalize_book, normalize_kline, normalize_trade
from app.domains.market_data.quality import (
    DataStatus,
    Rejection,
    candle_freshness,
    detect_candle_gaps,
    ensure_utc,
    find_duplicate_open_times,
    validate_candle_shape,
)

OPEN = datetime(2026, 10, 15, 12, 0, tzinfo=UTC)
NOW = OPEN + timedelta(minutes=2)


def _candle_row(
    open_ms: int,
    *,
    close: str = "100.5",
    high: str = "101",
    low: str = "99",
) -> list[object]:
    return [
        open_ms,
        "100",
        high,
        low,
        close,
        "2.5",
        open_ms + 59_999,
        "250",
        3,
        "1",
        "100",
        "0",
    ]


def test_valid_kline_becomes_a_utc_candle() -> None:
    open_ms = int(OPEN.timestamp() * 1000)
    candle = normalize_kline(_candle_row(open_ms), BTC_USDT_SPOT, "1m", NOW, now=NOW)
    assert not isinstance(candle, Rejection)
    assert candle.open_time == OPEN
    assert candle.open_time.tzinfo == UTC
    assert candle.close == Decimal("100.5")
    assert candle.data_status is DataStatus.VALID
    assert candle.provider == "binance_spot"
    assert candle.canonical_symbol == "BTC/USDT"
    assert candle.provider_symbol == "BTCUSDT"


def test_float_price_is_rejected() -> None:
    row = _candle_row(int(OPEN.timestamp() * 1000))
    row[1] = 100.0
    assert isinstance(normalize_kline(row, BTC_USDT_SPOT, "1m", NOW, now=NOW), Rejection)


def test_negative_price_and_volume_are_rejected() -> None:
    open_ms = int(OPEN.timestamp() * 1000)
    negative_price = _candle_row(open_ms, close="-1", high="101", low="-1")
    assert isinstance(normalize_kline(negative_price, BTC_USDT_SPOT, "1m", NOW, now=NOW), Rejection)
    negative_volume = _candle_row(open_ms)
    negative_volume[5] = "-0.1"
    result = normalize_kline(negative_volume, BTC_USDT_SPOT, "1m", NOW, now=NOW)
    assert isinstance(result, Rejection)
    assert result.reason == "negative volume"


def test_high_below_low_and_close_outside_range_are_rejected() -> None:
    open_ms = int(OPEN.timestamp() * 1000)
    crossed = _candle_row(open_ms, high="90", low="99")
    assert isinstance(normalize_kline(crossed, BTC_USDT_SPOT, "1m", NOW, now=NOW), Rejection)
    outside = _candle_row(open_ms, close="120")
    result = normalize_kline(outside, BTC_USDT_SPOT, "1m", NOW, now=NOW)
    assert isinstance(result, Rejection)
    assert result.reason == "close is outside the high-low range"


def test_open_candle_and_bad_time_order_are_rejected() -> None:
    open_ms = int(NOW.timestamp() * 1000)
    still_open = _candle_row(open_ms)
    assert isinstance(normalize_kline(still_open, BTC_USDT_SPOT, "1m", NOW, now=NOW), Rejection)
    row = _candle_row(int(OPEN.timestamp() * 1000))
    row[6] = int(OPEN.timestamp() * 1000)
    result = normalize_kline(row, BTC_USDT_SPOT, "1m", NOW, now=NOW)
    assert isinstance(result, Rejection)
    assert result.reason == "close_time must be after open_time"


def test_unsupported_interval_is_rejected() -> None:
    problem = validate_candle_shape(
        interval="2m",
        open_time=OPEN,
        close_time=OPEN + timedelta(minutes=2),
        open_=Decimal("1"),
        high=Decimal("1"),
        low=Decimal("1"),
        close=Decimal("1"),
        volume=Decimal("1"),
        quote_volume=None,
    )
    assert isinstance(problem, Rejection)
    assert problem.reason == "unsupported interval"


def test_naive_timestamp_is_rejected() -> None:
    assert isinstance(ensure_utc(datetime(2026, 10, 15, 12, 0)), Rejection)


def test_duplicate_open_times_and_gaps() -> None:
    second = OPEN + timedelta(minutes=1)
    third = OPEN + timedelta(minutes=3)
    assert find_duplicate_open_times([OPEN, second, OPEN]) == {OPEN}
    gaps = detect_candle_gaps("1m", [OPEN, second, third])
    assert len(gaps) == 1
    assert gaps[0].missing_intervals == 1
    assert gaps[0].missing_open_time == OPEN + timedelta(minutes=2)


def test_stale_candle_is_detected_without_changing_the_price() -> None:
    status = candle_freshness("1m", OPEN + timedelta(seconds=59), NOW + timedelta(minutes=10))
    assert status is DataStatus.STALE


def test_trade_keeps_buyer_is_maker_without_inventing_a_side() -> None:
    trade = normalize_trade(
        {
            "id": 10,
            "price": "100.25",
            "qty": "0.01",
            "quoteQty": "1.0025",
            "time": int(OPEN.timestamp() * 1000),
            "isBuyerMaker": True,
            "isBestMatch": True,
        },
        BTC_USDT_SPOT,
        NOW,
    )
    assert not isinstance(trade, Rejection)
    assert trade.buyer_is_maker is True
    assert trade.provider_trade_id == 10
    assert not hasattr(trade, "aggressor_side")


def test_book_ticker_does_not_invent_a_source_timestamp() -> None:
    book = normalize_book(
        {
            "symbol": "BTCUSDT",
            "bidPrice": "100",
            "bidQty": "1",
            "askPrice": "101",
            "askQty": "2",
        },
        BTC_USDT_SPOT,
        NOW,
    )
    assert not isinstance(book, Rejection)
    assert book.source_timestamp is None
    assert book.ingested_at == NOW
