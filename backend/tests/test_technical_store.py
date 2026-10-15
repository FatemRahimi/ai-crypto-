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
from app.domains.market_intelligence.calculators import EvidenceDraft, EvidenceStatus
from app.domains.market_intelligence.repository import EvidenceRepository
from app.domains.market_intelligence.service import TechnicalEvidenceService
from sqlalchemy.orm import Session, sessionmaker

IDENTITY = MarketIdentity(
    provider="test_provider",
    market_type="spot",
    base_asset="BTC",
    quote_asset="USDT",
    provider_symbol="TESTEVIDENCEUSDT",
    canonical_symbol="BTC/USDT",
)
OPEN = datetime(2026, 10, 15, 18, 0, tzinfo=UTC)


def _candle(index: int, *, step: timedelta = timedelta(minutes=1)) -> CanonicalCandle:
    opened = OPEN + (step * index)
    return CanonicalCandle(
        provider=IDENTITY.provider,
        canonical_symbol=IDENTITY.canonical_symbol,
        provider_symbol=IDENTITY.provider_symbol,
        market_type=IDENTITY.market_type,
        quote_asset=IDENTITY.quote_asset,
        interval="1m",
        open_time=opened,
        close_time=opened + timedelta(seconds=59, milliseconds=999),
        open=Decimal("100"),
        high=Decimal("110") if index % 2 == 0 else Decimal("105"),
        low=Decimal("90") if index % 2 == 0 else Decimal("95"),
        close=Decimal("100"),
        volume=Decimal("2"),
        quote_volume=Decimal("200"),
        trade_count=4,
        ingested_at=opened + timedelta(hours=3),
        data_status=DataStatus.VALID,
        endpoint="fixture",
        normalization_version="test",
    )


def _draft(price: str) -> EvidenceDraft:
    return EvidenceDraft(
        evidence_type="range_statistics",
        calculator_name="range_statistics",
        calculator_version="technical-evidence-v1",
        parameters={"candle_limit": 10},
        observation_time=OPEN + timedelta(minutes=9),
        input_open_start=OPEN,
        input_open_end=OPEN + timedelta(minutes=9),
        input_candle_ids=(1,),
        data_status=EvidenceStatus.VALID,
        result={"high": price, "low": "1", "range": "0", "midpoint": "1", "percentage_range": "0"},
    )


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


def test_recalculation_is_idempotent_and_keeps_provenance(
    sessions: sessionmaker[Session],
) -> None:
    with sessions() as session:
        repository = MarketRepository(session)
        market_id = repository.ensure_market(IDENTITY)
        repository.insert_candles(market_id, [_candle(index) for index in range(5)])
        session.commit()
    service = TechnicalEvidenceService(sessions, IDENTITY)
    first = service.calculate("range_statistics", "1m", candle_limit=10, now=OPEN)
    second = service.calculate("range_statistics", "1m", candle_limit=10, now=OPEN)
    view = service.latest("range_statistics", "1m", now=OPEN + timedelta(minutes=30))
    assert first.inserted == 1
    assert first.conflicts == 0
    assert second.duplicates == 1
    assert second.evidence_id == first.evidence_id
    assert first.result == second.result
    assert view is not None
    assert view.data_status == "VALID"
    assert view.freshness == "stale"
    assert view.calculator_version == "technical-evidence-v1"
    assert view.input_candle_count == 5
    assert view.observation_time == _candle(4).close_time
    assert view.observation_time != _candle(4).ingested_at
    assert view.parameters["candle_limit"] == 10
    with sessions() as session:
        assert EvidenceRepository(session).count_evidence(IDENTITY) == 1


def test_gap_is_stored_without_a_filled_measurement(sessions: sessionmaker[Session]) -> None:
    with sessions() as session:
        repository = MarketRepository(session)
        market_id = repository.ensure_market(IDENTITY)
        repository.insert_candles(market_id, [_candle(0), _candle(1), _candle(3)])
        session.commit()
    service = TechnicalEvidenceService(sessions, IDENTITY)
    report = service.calculate("range_statistics", "1m", candle_limit=10, now=OPEN)
    assert report.data_status == "GAP_DETECTED"
    assert "high" not in report.result
    view = service.latest("range_statistics", "1m", now=OPEN)
    assert view is not None
    assert view.freshness == "gap"
    assert view.input_candle_ids


def test_conflicting_result_is_not_replaced(sessions: sessionmaker[Session]) -> None:
    with sessions() as session:
        repository = EvidenceRepository(session)
        market_id = MarketRepository(session).ensure_market(IDENTITY)
        moment = OPEN + timedelta(minutes=20)
        first = repository.save(market_id, "1m", _draft("1"), moment, moment)
        second = repository.save(market_id, "1m", _draft("2"), moment, moment)
        session.commit()
        assert first.outcome == "inserted"
        assert second.outcome == "conflict"
        assert repository.count_evidence(IDENTITY) == 1
        stored = repository.latest(IDENTITY, "1m", "range_statistics")
        assert stored is not None
        assert '"high":"1"' in stored.result_json
