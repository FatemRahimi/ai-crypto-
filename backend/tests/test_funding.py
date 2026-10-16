from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from app.core.config import get_settings
from app.core.database import create_db_engine
from app.domains.market_data.funding import (
    FundingStop,
    assess_funding_completeness,
    normalize_funding_row,
    retrieve_funding_pages,
)
from app.domains.market_data.funding_service import FundingDataService
from app.domains.market_data.identity import BTC_USDT_SPOT, BTC_USDT_USD_M_PERPETUAL
from app.domains.market_data.persistence import FundingObservationRow, MarketRow
from app.domains.market_data.providers.binance_usdm import (
    FundingRetrieval,
    contract_type_for_symbol,
)
from app.domains.market_data.quality import Rejection
from app.main import create_app
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from tests.conftest import make_settings

START = datetime(2026, 10, 16, 8, 0, tzinfo=UTC)
END = datetime(2026, 10, 16, 16, 0, tzinfo=UTC)
NOW = datetime(2026, 10, 16, 17, 0, tzinfo=UTC)
FIRST_MS = 1792137600000
SECOND_MS = 1792166400000


class ScriptedFunding:
    def __init__(self, retrieval: FundingRetrieval) -> None:
        self.retrieval = retrieval
        self.calls = 0

    def fetch_funding(
        self,
        *,
        provider_symbol: str,
        start: datetime,
        end: datetime,
        max_rows: int,
    ) -> FundingRetrieval:
        del provider_symbol, start, end, max_rows
        self.calls += 1
        return self.retrieval


def _row(
    funding_ms: int,
    rate: str,
    rate_type: str = "Regular",
    symbol: str = "BTCUSDT",
) -> dict[str, object]:
    return {
        "symbol": symbol,
        "fundingTime": funding_ms,
        "fundingRate": rate,
        "rateType": rate_type,
        "markPrice": "82260.20000000",
    }


def _retrieval(
    rows: list[object],
    *,
    stop: FundingStop = "short_page",
    full: bool = False,
    contract_type: str | None = "PERPETUAL",
) -> FundingRetrieval:
    pages = () if not rows else (tuple(rows),)
    return FundingRetrieval(
        pages=pages,
        stop=stop,
        saw_full_page=full,
        contract_type=contract_type,
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


def test_negative_and_positive_rates_keep_decimal_text() -> None:
    negative = normalize_funding_row(_row(FIRST_MS, "-0.03750000"), BTC_USDT_USD_M_PERPETUAL, NOW)
    positive = normalize_funding_row(_row(SECOND_MS, "0.00006803"), BTC_USDT_USD_M_PERPETUAL, NOW)
    fine = normalize_funding_row(
        _row(FIRST_MS, "0.000000000000000001"),
        BTC_USDT_USD_M_PERPETUAL,
        NOW,
    )
    assert isinstance(negative, Rejection) is False
    assert isinstance(positive, Rejection) is False
    assert isinstance(fine, Rejection) is False
    assert isinstance(negative, Rejection) or negative.funding_rate == Decimal("-0.03750000")
    assert isinstance(positive, Rejection) or positive.funding_rate == Decimal("0.00006803")
    assert isinstance(fine, Rejection) or fine.funding_rate == Decimal("0.000000000000000001")
    assert isinstance(negative, Rejection) or negative.funding_time == datetime(
        2026, 10, 16, 8, 0, tzinfo=UTC
    )
    assert isinstance(negative, Rejection) or negative.rate_type == "Regular"


def test_malformed_funding_rows_are_rejected() -> None:
    unexpected = _row(FIRST_MS, "-0.1", symbol="ETHUSDT")
    assert isinstance(normalize_funding_row(unexpected, BTC_USDT_USD_M_PERPETUAL, NOW), Rejection)
    assert isinstance(
        normalize_funding_row(_row(FIRST_MS, "not-a-rate"), BTC_USDT_USD_M_PERPETUAL, NOW),
        Rejection,
    )
    bad_time = _row(FIRST_MS, "0.1")
    bad_time["fundingTime"] = "2026-10-16"
    assert isinstance(normalize_funding_row(bad_time, BTC_USDT_USD_M_PERPETUAL, NOW), Rejection)
    crowded = _row(FIRST_MS, "0.1", rate_type="Crowded")
    assert isinstance(normalize_funding_row(crowded, BTC_USDT_USD_M_PERPETUAL, NOW), Rejection)
    too_fine = normalize_funding_row(
        _row(FIRST_MS, "0.0000000000000000001"),
        BTC_USDT_USD_M_PERPETUAL,
        NOW,
    )
    assert isinstance(too_fine, Rejection)


def test_spot_identity_is_not_the_perpetual() -> None:
    assert BTC_USDT_SPOT.provider_symbol == BTC_USDT_USD_M_PERPETUAL.provider_symbol
    assert BTC_USDT_SPOT != BTC_USDT_USD_M_PERPETUAL
    assert BTC_USDT_SPOT.provider != BTC_USDT_USD_M_PERPETUAL.provider
    assert BTC_USDT_SPOT.market_type != BTC_USDT_USD_M_PERPETUAL.market_type
    assert BTC_USDT_SPOT.canonical_symbol != BTC_USDT_USD_M_PERPETUAL.canonical_symbol
    rejected = normalize_funding_row(_row(FIRST_MS, "0.1"), BTC_USDT_SPOT, NOW)
    assert isinstance(rejected, Rejection)


def test_same_timestamp_rate_types_page_without_skipping_or_looping() -> None:
    regular = _row(FIRST_MS, "0.1", "Regular")
    later = _row(SECOND_MS, "0.3", "Regular")
    special = _row(SECOND_MS, "0.2", "Special")
    calls: list[tuple[int, int, int]] = []

    def fetch_page(start_ms: int, end_ms: int, limit: int) -> list[object]:
        calls.append((start_ms, end_ms, limit))
        if start_ms == FIRST_MS:
            return [regular, later]
        return [special]

    run = retrieve_funding_pages(
        fetch_page,
        start_ms=FIRST_MS,
        end_ms=SECOND_MS,
        page_limit=2,
        max_rows=10,
    )
    assert run.saw_full_page is True
    assert run.stop == "short_page"
    assert calls[1][0] == SECOND_MS
    flat = [row for page in run.pages for row in page]
    assert flat == [regular, later, special]
    assert calls[1][0] == SECOND_MS
    assert calls[1][0] != SECOND_MS + 1

    stuck = retrieve_funding_pages(
        lambda start_ms, end_ms, limit: [regular],
        start_ms=FIRST_MS,
        end_ms=SECOND_MS,
        page_limit=1,
        max_rows=5,
    )
    assert stuck.stop == "no_progress"


def test_short_page_is_not_complete_and_spacing_is_not_a_gap() -> None:
    status, reason = assess_funding_completeness(
        stop="short_page",
        invalid_reason=None,
        conflicts=0,
        row_count=2,
    )
    assert status.value == "COMPLETENESS_UNKNOWN"
    assert reason != "GAP_DETECTED"
    empty, empty_reason = assess_funding_completeness(
        stop="empty",
        invalid_reason=None,
        conflicts=0,
        row_count=0,
    )
    assert empty.value == "EMPTY"
    assert empty_reason == "provider_returned_no_funding_rows"
    source = Path("app/domains/market_data/funding.py").read_text(encoding="utf-8")
    assert "timedelta(hours=8)" not in source
    assert "GAP_DETECTED" not in source


def test_contract_type_is_read_from_exchange_info() -> None:
    payload = {"symbols": [{"symbol": "BTCUSDT", "contractType": "PERPETUAL"}]}
    assert contract_type_for_symbol(payload, "BTCUSDT") == "PERPETUAL"
    assert contract_type_for_symbol(payload, "ETHUSDT") is None


def test_ingest_is_idempotent_and_keeps_distinct_rate_types(
    sessions: sessionmaker[Session],
) -> None:
    provider = ScriptedFunding(
        _retrieval([_row(FIRST_MS, "-0.03750000"), _row(FIRST_MS, "0.01000000", "Special")])
    )
    service = FundingDataService(sessions, provider)
    first = service.ingest(start=START, end=END, now=NOW)
    second = service.ingest(start=START, end=END, now=NOW)
    assert first.completeness.value == "COMPLETENESS_UNKNOWN"
    assert first.inserted == 2
    assert second.inserted == 0
    assert second.duplicates == 2
    assert second.input_fingerprint == first.input_fingerprint
    with sessions() as session:
        rows = list(
            session.scalars(
                select(FundingObservationRow).where(FundingObservationRow.funding_time == START)
            ).all()
        )
        assert len(rows) == 2
        assert {row.rate_type for row in rows} == {"Regular", "Special"}
        assert {row.funding_rate for row in rows} == {Decimal("-0.03750000"), Decimal("0.01000000")}
        perpetual = session.scalar(
            select(MarketRow).where(
                MarketRow.provider == "binance_usdm",
                MarketRow.provider_symbol == "BTCUSDT",
            )
        )
        assert perpetual is not None
        assert perpetual.market_type == "perpetual"
        assert perpetual.canonical_symbol == "BTCUSDT-PERP"
        spot = session.scalar(
            select(MarketRow).where(
                MarketRow.provider == BTC_USDT_SPOT.provider,
                MarketRow.provider_symbol == "BTCUSDT",
            )
        )
        if spot is not None:
            assert spot.id != perpetual.id
            assert spot.canonical_symbol == "BTC/USDT"


def test_conflict_does_not_replace_the_stored_rate(sessions: sessionmaker[Session]) -> None:
    original = ScriptedFunding(_retrieval([_row(FIRST_MS, "0.10000000")]))
    service = FundingDataService(sessions, original)
    service.ingest(start=START, end=END, now=NOW)
    changed = FundingDataService(
        sessions,
        ScriptedFunding(_retrieval([_row(FIRST_MS, "0.20000000")])),
    )
    report = changed.ingest(start=START, end=END, now=NOW)
    assert report.completeness.value == "INVALID"
    assert report.conflicts == 1
    with sessions() as session:
        stored = session.scalars(
            select(FundingObservationRow).where(FundingObservationRow.funding_time == START)
        ).all()
        assert len(stored) == 1
        assert stored[0].funding_rate == Decimal("0.10000000")


def test_empty_window_stores_no_zero_rate(sessions: sessionmaker[Session]) -> None:
    service = FundingDataService(sessions, ScriptedFunding(_retrieval([], stop="empty")))
    report = service.ingest(start=START, end=END, now=NOW)
    assert report.completeness.value == "EMPTY"
    assert report.row_count == 0
    with sessions() as session:
        stored = session.scalar(
            select(func.count())
            .select_from(FundingObservationRow)
            .where(FundingObservationRow.ingested_at == NOW)
        )
        assert stored == 0


def test_failed_pages_store_nothing(sessions: sessionmaker[Session]) -> None:
    outside = _row(FIRST_MS - 1, "0.10000000")
    out_of_window = FundingDataService(sessions, ScriptedFunding(_retrieval([outside])))
    refused = out_of_window.ingest(start=START, end=END, now=NOW)
    assert refused.completeness.value == "INVALID"
    assert refused.row_count == 0
    stalled = FundingDataService(
        sessions,
        ScriptedFunding(_retrieval([_row(FIRST_MS, "0.10000000")], stop="no_progress", full=True)),
    )
    stalled_report = stalled.ingest(start=START, end=END, now=NOW)
    assert stalled_report.completeness.value == "INVALID"
    assert stalled_report.details["reason"] == "pagination_no_progress"
    with sessions() as session:
        stored = session.scalar(
            select(func.count())
            .select_from(FundingObservationRow)
            .where(FundingObservationRow.funding_time == START)
        )
        assert stored == 0


def test_unconfirmed_contract_does_not_write(sessions: sessionmaker[Session]) -> None:
    service = FundingDataService(
        sessions,
        ScriptedFunding(_retrieval([_row(FIRST_MS, "0.1")], contract_type="CURRENT_QUARTER")),
    )
    with pytest.raises(ValueError, match="perpetual"):
        service.ingest(start=START, end=END, now=NOW)
    with sessions() as session:
        stored = session.scalar(
            select(func.count())
            .select_from(FundingObservationRow)
            .where(FundingObservationRow.funding_time == START)
        )
        assert stored == 0


def test_read_does_not_call_the_provider(sessions: sessionmaker[Session]) -> None:
    provider = ScriptedFunding(_retrieval([_row(FIRST_MS, "-0.03750000")]))
    service = FundingDataService(sessions, provider)
    service.ingest(start=START, end=END, now=NOW)
    calls = provider.calls
    rows, window = service.read(start=START, end=END, limit=20)
    assert provider.calls == calls
    assert len(rows) == 1
    assert window is not None
    assert window.completeness == "COMPLETENESS_UNKNOWN"
    app = create_app(
        make_settings(),
        database_probe=lambda: "ok",
        funding=service,
    )
    response = TestClient(app).get("/api/v1/funding?symbol=BTCUSDT-PERP")
    assert provider.calls == calls
    assert response.status_code == 200
    body = response.json()
    assert body["execution_enabled"] is False
    assert body["provider"] == "binance_usdm"
    assert body["market_type"] == "perpetual"
    assert body["canonical_symbol"] == "BTCUSDT-PERP"
    assert body["records"][0]["funding_rate"] == "-0.037500000000000000"
    assert isinstance(body["records"][0]["funding_rate"], str)
    assert body["records"][0]["funding_time"].startswith("2026-10-16T08:00:00")
    assert "+01:00" not in body["records"][0]["funding_time"]
    assert body["completeness"] == "COMPLETENESS_UNKNOWN"
    assert "not proven" in body["limitation"]
    assert body["input_fingerprint"] == window.input_fingerprint
    assert "markPrice" not in body["records"][0]
    spot = TestClient(app).get("/api/v1/funding?symbol=BTC/USDT")
    assert spot.status_code == 404


def test_duplicate_boundary_is_one_stored_row(sessions: sessionmaker[Session]) -> None:
    duplicated = _row(FIRST_MS, "0.10000000")
    retrieval = FundingRetrieval(
        pages=(tuple([duplicated, _row(SECOND_MS, "0.20000000")]), tuple([duplicated])),
        stop="short_page",
        saw_full_page=True,
        contract_type="PERPETUAL",
    )
    report = FundingDataService(sessions, ScriptedFunding(retrieval)).ingest(
        start=START,
        end=END,
        now=NOW,
    )
    assert report.duplicates == 1
    assert report.inserted == 2
    assert report.completeness.value == "COMPLETENESS_UNKNOWN"
