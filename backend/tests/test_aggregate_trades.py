from __future__ import annotations

from collections.abc import Iterator, Sequence
from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal

import httpx
import pytest
from app.core.config import get_settings
from app.core.database import create_db_engine
from app.domains.market_data.aggregates import (
    aggregate_trade_fingerprint,
    aggregate_window_fingerprint,
)
from app.domains.market_data.identity import MarketIdentity
from app.domains.market_data.normalize import normalize_aggregate_trade
from app.domains.market_data.persistence import TradeRow
from app.domains.market_data.providers.base import (
    AggregateRetrieval,
    AggregateStop,
    MarketDataProviderError,
)
from app.domains.market_data.providers.binance_spot import AGG_TRADES_PATH, BinanceSpotProvider
from app.domains.market_data.quality import Rejection
from app.domains.market_data.records import CanonicalAggregateTrade
from app.domains.market_data.repository import MarketRepository
from app.domains.market_data.service import MarketDataService
from app.main import create_app
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from tests.conftest import make_settings

IDENTITY = MarketIdentity(
    provider="test_provider",
    market_type="spot",
    base_asset="BTC",
    quote_asset="USDT",
    provider_symbol="TESTBTCUSDT",
    canonical_symbol="BTC/USDT",
)
START = datetime(2026, 10, 15, 12, 0, tzinfo=UTC)
END = START + timedelta(seconds=5)
NOW = END + timedelta(minutes=1)


class ScriptedAggregates:
    name = "scripted"

    def __init__(self, retrieval: AggregateRetrieval) -> None:
        self._retrieval = retrieval
        self.calls = 0

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
        del provider_symbol, interval, start, end, limit, max_candles
        raise AssertionError("klines were not requested")

    def fetch_recent_trades(self, *, provider_symbol: str, limit: int) -> list[object]:
        del provider_symbol, limit
        raise AssertionError("recent trades were not requested")

    def fetch_book_ticker(self, *, provider_symbol: str) -> object:
        del provider_symbol
        raise AssertionError("book ticker was not requested")

    def fetch_aggregate_trades(
        self,
        *,
        provider_symbol: str,
        start: datetime,
        end: datetime,
        max_trades: int,
    ) -> AggregateRetrieval:
        del provider_symbol, start, end, max_trades
        self.calls += 1
        return self._retrieval


class ExplodingProvider(ScriptedAggregates):
    def __init__(self) -> None:
        super().__init__(AggregateRetrieval(pages=(), stop="empty", saw_full_page=False))

    def fetch_aggregate_trades(
        self,
        *,
        provider_symbol: str,
        start: datetime,
        end: datetime,
        max_trades: int,
    ) -> AggregateRetrieval:
        self.calls += 1
        del provider_symbol, start, end, max_trades
        raise AssertionError("provider called")


class TimeoutProvider(ScriptedAggregates):
    def __init__(self) -> None:
        super().__init__(AggregateRetrieval(pages=(), stop="empty", saw_full_page=False))

    def fetch_aggregate_trades(
        self,
        *,
        provider_symbol: str,
        start: datetime,
        end: datetime,
        max_trades: int,
    ) -> AggregateRetrieval:
        del provider_symbol, start, end, max_trades
        raise MarketDataProviderError("timeout")


class ScriptedTransport:
    def __init__(self, responses: list[httpx.Response | Exception]) -> None:
        self._responses = responses
        self.calls: list[tuple[str, dict[str, str | int]]] = []

    def get(self, path: str, params: dict[str, str | int]) -> httpx.Response:
        self.calls.append((path, params))
        item = self._responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def _response(payload: object) -> httpx.Response:
    return httpx.Response(
        200,
        json=payload,
        request=httpx.Request("GET", "https://data-api.binance.vision/api/v3/aggTrades"),
    )


def _millis(moment: datetime) -> int:
    return int(moment.timestamp() * 1000)


def _raw(
    aggregate_id: int,
    trade_id: int,
    offset_ms: int,
    *,
    price: str = "10.50",
    quantity: str = "0.010",
    maker: bool = False,
    last_trade_id: int | None = None,
) -> dict[str, object]:
    return {
        "a": aggregate_id,
        "p": price,
        "q": quantity,
        "f": trade_id,
        "l": trade_id if last_trade_id is None else last_trade_id,
        "T": _millis(START + timedelta(milliseconds=offset_ms)),
        "m": maker,
        "M": True,
    }


def _page(
    rows: Sequence[object],
    *,
    stop: AggregateStop = "short_page",
    full: bool = False,
) -> AggregateRetrieval:
    pages = () if not rows else (tuple(rows),)
    return AggregateRetrieval(pages=pages, stop=stop, saw_full_page=full)


def _service(
    sessions: sessionmaker[Session],
    retrieval: AggregateRetrieval,
) -> MarketDataService:
    return MarketDataService(sessions, ScriptedAggregates(retrieval), IDENTITY)


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


def test_binance_agg_trade_maps_decimal_utc_and_ignores_best_match() -> None:
    row = _raw(26129, 27781, 0, price="0.01633102", quantity="4.70443515", maker=True)
    without_match = dict(row)
    without_match.pop("M")
    first = normalize_aggregate_trade(row, IDENTITY, NOW)
    second = normalize_aggregate_trade(without_match, IDENTITY, NOW)
    assert isinstance(first, CanonicalAggregateTrade)
    assert isinstance(second, CanonicalAggregateTrade)
    assert first.price == Decimal("0.01633102")
    assert first.quantity == Decimal("4.70443515")
    assert isinstance(first.price, Decimal)
    assert first.event_time == START
    assert first.event_time.tzinfo is UTC
    assert first.buyer_is_maker is True
    assert first.first_trade_id == 27781
    assert first.last_trade_id == 27781
    assert first.content_fingerprint == second.content_fingerprint
    assert first.ingested_at != first.event_time
    assert first.endpoint == "GET /api/v3/aggTrades"


def test_decimal_scale_and_float_price_are_rejected() -> None:
    wide = _raw(1, 1, 0, price="1.0000000000000000001")
    floated = _raw(1, 1, 0)
    floated["p"] = 10.5
    assert isinstance(normalize_aggregate_trade(wide, IDENTITY, NOW), Rejection)
    assert isinstance(normalize_aggregate_trade(floated, IDENTITY, NOW), Rejection)


def test_pagination_advances_by_from_id_without_repeating_the_time_bound() -> None:
    start = START
    end = END
    transport = ScriptedTransport(
        [
            _response([_raw(10, 100, 0), _raw(11, 101, 10)]),
            _response([_raw(12, 102, 20), _raw(13, 103, 6_000)]),
        ]
    )
    provider = BinanceSpotProvider(
        transport=transport,
        pause_seconds=0,
        max_attempts=1,
        page_limit=2,
    )
    retrieval = provider.fetch_aggregate_trades(
        provider_symbol="BTCUSDT",
        start=start.astimezone(timezone(timedelta(hours=1))),
        end=end,
        max_trades=10,
    )
    assert transport.calls[0][0] == AGG_TRADES_PATH
    assert set(transport.calls[0][1]) == {"symbol", "startTime", "endTime", "limit"}
    assert transport.calls[0][1]["startTime"] == _millis(START)
    assert set(transport.calls[1][1]) == {"symbol", "fromId", "limit"}
    assert transport.calls[1][1]["fromId"] == 12
    assert "signature" not in transport.calls[0][1]
    assert "signature" not in transport.calls[1][1]
    assert retrieval.stop == "crossed_end"
    assert retrieval.saw_full_page is True


def test_page_boundary_duplicate_is_stored_once(
    sessions: sessionmaker[Session],
) -> None:
    page = AggregateRetrieval(
        pages=(
            (_raw(1, 10, 0), _raw(2, 11, 10)),
            (_raw(2, 11, 10), _raw(3, 12, 20)),
        ),
        stop="short_page",
        saw_full_page=True,
    )
    report = _service(sessions, page).ingest_aggregate_trades(start=START, end=END, now=NOW)
    stored = _service(sessions, page).aggregate_trades(start=None, end=None, limit=10)
    assert report.inserted == 3
    assert report.duplicates == 1
    assert report.conflicts == 0
    assert [row.aggregate_trade_id for row in stored] == [1, 2, 3]
    assert report.completeness.value != "COMPLETE"


def test_reingest_is_idempotent_and_conflict_does_not_overwrite(
    sessions: sessionmaker[Session],
) -> None:
    rows = [_raw(1, 10, 0), _raw(2, 11, 10), _raw(3, 12, 20)]
    service = _service(sessions, _page(rows))
    first = service.ingest_aggregate_trades(start=START, end=END, now=NOW)
    second = service.ingest_aggregate_trades(start=START, end=END, now=NOW)
    conflict = _service(
        sessions,
        _page([_raw(1, 10, 0, price="11.00"), _raw(2, 11, 10), _raw(3, 12, 20)]),
    ).ingest_aggregate_trades(start=START, end=END, now=NOW)
    stored = service.aggregate_trades(start=None, end=None, limit=10)
    assert first.completeness.value == "COMPLETE"
    assert first.inserted == 3
    assert second.inserted == 0
    assert second.duplicates == 3
    assert conflict.conflicts == 1
    assert conflict.completeness.value == "INVALID"
    assert stored[0].price == Decimal("10.50")
    assert len(stored) == 3


def test_contiguous_short_page_is_complete_and_a_known_id_hole_is_a_gap(
    sessions: sessionmaker[Session],
) -> None:
    complete = _service(
        sessions,
        _page([_raw(1, 10, 0), _raw(2, 11, 10), _raw(3, 12, 20)]),
    ).ingest_aggregate_trades(start=START, end=END, now=NOW)
    gapped = _service(
        sessions,
        _page([_raw(1, 10, 0), _raw(2, 11, 10), _raw(4, 13, 20)]),
    ).ingest_aggregate_trades(start=START, end=END, now=NOW)
    assert complete.completeness.value == "COMPLETE"
    assert complete.first_event_time == START
    assert complete.checked_at == NOW
    assert complete.underlying_first_trade_id == 10
    assert complete.underlying_last_trade_id == 12
    assert gapped.completeness.value == "GAP_DETECTED"
    gaps = gapped.gap_details["gaps"]
    assert isinstance(gaps, list)
    assert gaps[0]["after_aggregate_id"] == 2
    assert gaps[0]["next_aggregate_id"] == 4
    stored = _service(sessions, _page([])).aggregate_trades(start=None, end=None, limit=10)
    assert [row.aggregate_trade_id for row in stored] == [1, 2, 3, 4]


def test_empty_invalid_and_unknown_are_distinct(sessions: sessionmaker[Session]) -> None:
    empty = _service(sessions, _page([], stop="empty")).ingest_aggregate_trades(
        start=START,
        end=END,
        now=NOW,
    )
    invalid = _service(
        sessions,
        _page([_raw(2, 11, 10), _raw(1, 10, 0)]),
    ).ingest_aggregate_trades(start=START, end=END, now=NOW)
    backwards = _service(
        sessions,
        _page([_raw(1, 10, 20), _raw(2, 11, 10)]),
    ).ingest_aggregate_trades(start=START, end=END, now=NOW)
    aggregated = _service(
        sessions,
        _page([_raw(100, 10, 0, last_trade_id=12)]),
    ).ingest_aggregate_trades(start=START, end=END, now=NOW)
    hole = _service(
        sessions,
        _page([_raw(200, 10, 0), _raw(201, 12, 10)]),
    ).ingest_aggregate_trades(start=START, end=END, now=NOW)
    capped = _service(
        sessions,
        _page([_raw(300, 10, 0), _raw(301, 11, 10)], stop="cap", full=True),
    ).ingest_aggregate_trades(start=START, end=END, now=NOW)
    assert empty.completeness.value == "EMPTY"
    assert empty.aggregate_trade_count == 0
    assert invalid.completeness.value == "INVALID"
    assert backwards.completeness.value == "INVALID"
    assert aggregated.completeness.value == "COMPLETENESS_UNKNOWN"
    assert aggregated.gap_details["reason"] == "underlying_trade_id_span_is_aggregated"
    assert hole.completeness.value == "COMPLETENESS_UNKNOWN"
    assert hole.gap_details["reason"] == "underlying_trade_ids_are_not_contiguous"
    assert capped.completeness.value == "COMPLETENESS_UNKNOWN"
    assert capped.completeness.value != "COMPLETE"
    stored = _service(sessions, _page([])).aggregate_trades(start=None, end=None, limit=20)
    assert [row.aggregate_trade_id for row in stored] == [100, 200, 300, 201, 301]
    assert all(row.event_time != row.ingested_at for row in stored)


def test_malformed_outside_window_and_timeout_store_nothing(
    sessions: sessionmaker[Session],
) -> None:
    malformed = _service(sessions, _page([{"a": 1}])).ingest_aggregate_trades(
        start=START,
        end=END,
        now=NOW,
    )
    outside = _service(
        sessions,
        _page([_raw(1, 10, -1)]),
    ).ingest_aggregate_trades(start=START, end=END, now=NOW)
    assert malformed.completeness.value == "INVALID"
    assert outside.completeness.value == "INVALID"
    with pytest.raises(MarketDataProviderError):
        MarketDataService(sessions, TimeoutProvider(), IDENTITY).ingest_aggregate_trades(
            start=START,
            end=END,
            now=NOW,
        )
    with pytest.raises(ValueError):
        _service(sessions, _page([])).ingest_aggregate_trades(
            start=START,
            end=END,
            max_trades=5001,
            now=NOW,
        )
    stored = _service(sessions, _page([])).aggregate_trades(start=None, end=None, limit=20)
    assert stored == []


def test_partial_window_boundary_excludes_the_trade_after_end(
    sessions: sessionmaker[Session],
) -> None:
    retrieval = AggregateRetrieval(
        pages=(
            (_raw(1, 10, 0), _raw(2, 11, 10)),
            (_raw(3, 12, 6_000),),
        ),
        stop="crossed_end",
        saw_full_page=True,
    )
    report = _service(sessions, retrieval).ingest_aggregate_trades(start=START, end=END, now=NOW)
    stored = _service(sessions, retrieval).aggregate_trades(start=None, end=None, limit=10)
    assert [row.aggregate_trade_id for row in stored] == [1, 2]
    assert report.completeness.value == "COMPLETENESS_UNKNOWN"
    assert report.last_event_time == START + timedelta(milliseconds=10)


def test_fingerprint_is_stable_and_changes_when_content_changes() -> None:
    left = normalize_aggregate_trade(_raw(1, 10, 0, maker=False), IDENTITY, NOW)
    right = normalize_aggregate_trade(_raw(2, 11, 10, maker=False), IDENTITY, NOW)
    assert isinstance(left, CanonicalAggregateTrade)
    assert isinstance(right, CanonicalAggregateTrade)
    assert aggregate_trade_fingerprint(
        aggregate_trade_id=left.aggregate_trade_id,
        price=left.price,
        quantity=left.quantity,
        event_time=left.event_time,
        first_trade_id=left.first_trade_id,
        last_trade_id=left.last_trade_id,
        buyer_is_maker=left.buyer_is_maker,
    ) == left.content_fingerprint
    forward = aggregate_window_fingerprint([left, right])
    backward = aggregate_window_fingerprint([right, left])
    assert forward == backward
    changed = {
        "price": _raw(1, 10, 0, price="10.51"),
        "quantity": _raw(1, 10, 0, quantity="0.011"),
        "time": _raw(1, 10, 1),
        "id": _raw(9, 10, 0),
        "range": _raw(1, 10, 0, last_trade_id=11),
        "maker": _raw(1, 10, 0, maker=True),
    }
    for row in changed.values():
        other = normalize_aggregate_trade(row, IDENTITY, NOW)
        assert isinstance(other, CanonicalAggregateTrade)
        assert other.content_fingerprint != left.content_fingerprint


def test_read_api_has_no_data_until_ingest_and_never_calls_the_provider(
    sessions: sessionmaker[Session],
) -> None:
    provider = ExplodingProvider()
    service = MarketDataService(sessions, provider, IDENTITY)
    client = TestClient(
        create_app(make_settings(), database_probe=lambda: "ok", market_data=service)
    )
    missing = client.get("/api/v1/market-data/aggregate-trades")
    windows = client.get("/api/v1/market-data/aggregate-trade-windows")
    unknown = client.get("/api/v1/market-data/aggregate-trades", params={"symbol": "ETH/USDT"})
    assert missing.status_code == 200
    assert missing.json()["empty"] is True
    assert missing.json()["trades"] == []
    assert windows.status_code == 200
    assert windows.json()["empty"] is True
    assert windows.json()["stored_count"] == 0
    assert unknown.status_code == 404
    assert provider.calls == 0
    _service(
        sessions,
        _page([_raw(1, 10, 0), _raw(2, 11, 10), _raw(3, 12, 20)]),
    ).ingest_aggregate_trades(start=START, end=END, now=NOW)
    stored = client.get("/api/v1/market-data/aggregate-trades")
    body = stored.json()
    assert body["empty"] is False
    assert Decimal(body["trades"][0]["price"]) == Decimal("10.50")
    assert Decimal(body["trades"][0]["quantity"]) == Decimal("0.010")
    assert "." in body["trades"][0]["price"]
    assert body["trades"][0]["event_time"].startswith("2026-10-15T12:00:00")
    assert len(body["trades"][0]["content_fingerprint"]) == 64
    assert "poc" not in stored.text.lower()
    assert "vah" not in stored.text.lower()
    window = client.get("/api/v1/market-data/aggregate-trade-windows")
    assert window.json()["window"]["completeness"] == "COMPLETE"
    assert window.json()["stored_count"] == 3
    assert provider.calls == 0


def test_rollback_discards_uncommitted_rows(session: Session) -> None:
    repository = MarketRepository(session)
    market_id = repository.ensure_market(IDENTITY)
    trade = normalize_aggregate_trade(_raw(1, 10, 0), IDENTITY, NOW)
    assert isinstance(trade, CanonicalAggregateTrade)
    repository.insert_aggregate_trades(market_id, [trade])
    session.rollback()
    assert repository.count_aggregate_trades(IDENTITY) == 0
    ordinary = session.scalar(
        select(func.count()).select_from(TradeRow).where(TradeRow.market_id == market_id)
    )
    assert ordinary == 0


def test_provider_timeout_on_the_second_page_does_not_store_the_first(
    sessions: sessionmaker[Session],
) -> None:
    transport = ScriptedTransport(
        [
            _response([_raw(1, 10, 0)]),
            httpx.TimeoutException("timed out"),
        ]
    )
    provider = BinanceSpotProvider(
        transport=transport,
        pause_seconds=0,
        max_attempts=1,
        page_limit=1,
    )
    service = MarketDataService(sessions, provider, IDENTITY)
    with pytest.raises(MarketDataProviderError):
        service.ingest_aggregate_trades(start=START, end=END, max_trades=2, now=NOW)
    assert service.aggregate_trades(start=None, end=None, limit=10) == []
    window, stored = service.aggregate_trade_window(start=None, end=None)
    assert window is None
    assert stored == 0
