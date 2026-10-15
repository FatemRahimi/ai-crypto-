from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
from app.core.config import get_settings
from app.core.database import create_db_engine
from app.domains.market_data.identity import MarketIdentity
from app.domains.market_data.service import MarketDataService
from sqlalchemy.orm import Session, sessionmaker

IDENTITY = MarketIdentity(
    provider="test_provider",
    market_type="spot",
    base_asset="BTC",
    quote_asset="USDT",
    provider_symbol="TESTBTCUSDT",
    canonical_symbol="BTC/USDT",
)
OPEN = datetime(2026, 10, 15, 18, 0, tzinfo=UTC)
NOW = OPEN + timedelta(minutes=5)


class ScriptedKlines:
    name = "scripted"

    def __init__(self, rows: list[list[object]]) -> None:
        self._rows = rows

    def fetch_klines(
        self,
        *,
        provider_symbol: str,
        interval: str,
        start: datetime | None,
        end: datetime | None,
        limit: int,
        max_candles: int,
    ) -> list[list[object]]:
        return self._rows

    def fetch_recent_trades(self, *, provider_symbol: str, limit: int) -> list[object]:
        return []

    def fetch_book_ticker(self, *, provider_symbol: str) -> object:
        return {}


def _kline(open_time: datetime, *, close: str = "100.5") -> list[object]:
    open_ms = int(open_time.timestamp() * 1000)
    return [
        open_ms,
        "100",
        "101",
        "99",
        close,
        "2.5",
        open_ms + 59_999,
        "250",
        3,
        "1",
        "100",
        "0",
    ]


@pytest.fixture
def sessions() -> Iterator[sessionmaker[Session]]:
    engine = create_db_engine(get_settings())
    connection = engine.connect()
    outer = connection.begin()
    factory = sessionmaker(
        bind=connection,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )
    try:
        yield factory
    finally:
        outer.rollback()
        connection.close()
        engine.dispose()


def test_identical_open_times_keep_one_candle_and_count_duplicates(
    sessions: sessionmaker[Session],
) -> None:
    row = _kline(OPEN)
    service = MarketDataService(sessions, ScriptedKlines([row, row]), IDENTITY)
    report = service.ingest_candles("1m", now=NOW)
    repeat = MarketDataService(sessions, ScriptedKlines([row]), IDENTITY)
    again = repeat.ingest_candles("1m", now=NOW)
    assert report.inserted == 1
    assert report.duplicates == 1
    assert report.rejected == 0
    assert again.inserted == 0
    assert again.duplicates == 1
    assert again.rejected == 0
    assert service.stored_candle_count() == 1


def test_conflicting_open_times_are_rejected(sessions: sessionmaker[Session]) -> None:
    service = MarketDataService(
        sessions,
        ScriptedKlines([_kline(OPEN, close="100.5"), _kline(OPEN, close="100.6")]),
        IDENTITY,
    )
    report = service.ingest_candles("1m", now=NOW)
    assert report.inserted == 0
    assert report.duplicates == 0
    assert report.rejected == 2
    assert service.stored_candle_count() == 0
