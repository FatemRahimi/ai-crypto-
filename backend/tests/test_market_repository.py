from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from app.core.config import get_settings
from app.core.database import create_db_engine
from app.domains.market_data.identity import MarketIdentity
from app.domains.market_data.quality import DataStatus
from app.domains.market_data.records import CanonicalCandle
from app.domains.market_data.repository import MarketRepository
from sqlalchemy.orm import Session

IDENTITY = MarketIdentity(
    provider="test_provider",
    market_type="spot",
    base_asset="BTC",
    quote_asset="USDT",
    provider_symbol="TESTBTCUSDT",
    canonical_symbol="BTC/USDT",
)
OPEN = datetime(2026, 10, 15, 12, 0, tzinfo=UTC)


def _candle(open_time: datetime) -> CanonicalCandle:
    return CanonicalCandle(
        provider=IDENTITY.provider,
        canonical_symbol=IDENTITY.canonical_symbol,
        provider_symbol=IDENTITY.provider_symbol,
        market_type=IDENTITY.market_type,
        quote_asset=IDENTITY.quote_asset,
        interval="1m",
        open_time=open_time,
        close_time=open_time + timedelta(seconds=59, milliseconds=999),
        open=Decimal("100"),
        high=Decimal("101"),
        low=Decimal("99"),
        close=Decimal("100.5"),
        volume=Decimal("2"),
        quote_volume=Decimal("201"),
        trade_count=4,
        ingested_at=open_time + timedelta(minutes=2),
        data_status=DataStatus.VALID,
        endpoint="GET /api/v3/klines",
        normalization_version="test",
    )


@pytest.fixture
def session() -> Iterator[Session]:
    engine = create_db_engine(get_settings())
    connection = engine.connect()
    outer = connection.begin()
    bound = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        yield bound
    finally:
        bound.close()
        outer.rollback()
        connection.close()
        engine.dispose()


def test_candle_insert_is_idempotent_and_range_is_ordered(session: Session) -> None:
    repository = MarketRepository(session)
    market_id = repository.ensure_market(IDENTITY)
    first = _candle(OPEN)
    second = _candle(OPEN + timedelta(minutes=1))
    inserted = repository.insert_candles(market_id, [second, first])
    again = repository.insert_candles(market_id, [first])
    session.flush()
    rows = repository.candle_range(IDENTITY, "1m", None, None, limit=10)
    assert inserted.inserted == 2
    assert again.duplicates == 1
    assert [row.open_time for row in rows] == [first.open_time, second.open_time]
    latest = repository.latest_candle(IDENTITY, "1m", OPEN + timedelta(minutes=5))
    assert latest is not None
    assert latest.open_time == second.open_time
    assert repository.count_candles(IDENTITY) == 2
