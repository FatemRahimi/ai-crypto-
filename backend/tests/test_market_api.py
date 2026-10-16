from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal

from app.domains.market_data.persistence import (
    AggregateTradeRow,
    AggregateTradeWindowRow,
    CandleRow,
)
from app.domains.market_data.quality import DataStatus
from app.domains.market_data.service import LatestView
from app.main import create_app
from fastapi.testclient import TestClient

from tests.conftest import make_settings

OPEN = datetime(2026, 10, 15, 12, 0, tzinfo=UTC)


class MemoryMarket:
    def __init__(self, latest: LatestView) -> None:
        self._latest = latest
        self.calls: list[str] = []

    def stored_candle_count(self) -> int:
        return 0 if self._latest.price is None else 1

    def candles(
        self,
        interval: str,
        *,
        start: datetime | None,
        end: datetime | None,
        limit: int,
    ) -> tuple[list[CandleRow], int]:
        del interval, start, end, limit
        self.calls.append("candles")
        return [], 0

    def latest(self, *, interval: str = "1m", now: datetime | None = None) -> LatestView:
        del interval, now
        self.calls.append("latest")
        return self._latest

    def aggregate_trades(
        self,
        *,
        start: datetime | None,
        end: datetime | None,
        limit: int,
    ) -> list[AggregateTradeRow]:
        del start, end, limit
        self.calls.append("aggregate_trades")
        return []

    def aggregate_trade_window(
        self,
        *,
        start: datetime | None,
        end: datetime | None,
    ) -> tuple[AggregateTradeWindowRow | None, int]:
        del start, end
        self.calls.append("aggregate_trade_window")
        return None, 0


def _client(latest: LatestView) -> TestClient:
    app = create_app(make_settings(), database_probe=lambda: "ok", market_data=MemoryMarket(latest))
    return TestClient(app)


def test_empty_market_data_is_explicit_and_has_no_price() -> None:
    client = _client(
        LatestView(
            canonical_symbol="BTC/USDT",
            provider_symbol="BTCUSDT",
            provider="binance_spot",
            market_type="spot",
            quote_asset="USDT",
            price=None,
            observation_time=None,
            freshness=DataStatus.VALID,
            endpoint=None,
            normalization_version=None,
            detail="No verified market data",
        )
    )
    latest = client.get("/api/v1/market-data/latest")
    assert latest.status_code == 200
    body = latest.json()
    assert body["price"] is None
    assert body["detail"] == "No verified market data"
    assert body["freshness"] == "unavailable"
    assert "100" not in latest.text
    candles = client.get("/api/v1/market-data/candles")
    assert candles.status_code == 200
    assert candles.json()["empty"] is True
    assert candles.json()["candles"] == []


def test_latest_verified_price_keeps_source_and_time() -> None:
    client = _client(
        LatestView(
            canonical_symbol="BTC/USDT",
            provider_symbol="BTCUSDT",
            provider="binance_spot",
            market_type="spot",
            quote_asset="USDT",
            price=Decimal("64000.10"),
            observation_time=datetime(2026, 10, 15, 13, 0, 59, tzinfo=timezone(timedelta(hours=1))),
            freshness=DataStatus.STALE,
            endpoint="GET /api/v3/trades",
            normalization_version="binance-public-v1",
            detail="Verified public trade",
        )
    )
    response = client.get("/api/v1/market-data/latest")
    assert response.status_code == 200
    body = response.json()
    assert body["price"] == "64000.10"
    assert body["provider"] == "binance_spot"
    assert body["freshness"] == "stale"
    assert body["observation_time"].startswith("2026-10-15T12:00:59")
    assert body["observation_time"].endswith(("Z", "+00:00"))
    status = client.get("/api/v1/market-data/status")
    assert status.json()["execution_enabled"] is False
    assert status.json()["stream"] == "disconnected"


def test_unknown_symbol_is_not_filled_with_btc() -> None:
    client = _client(
        LatestView(
            canonical_symbol="BTC/USDT",
            provider_symbol="BTCUSDT",
            provider="binance_spot",
            market_type="spot",
            quote_asset="USDT",
            price=Decimal("1"),
            observation_time=OPEN,
            freshness=DataStatus.VALID,
            endpoint="GET /api/v3/trades",
            normalization_version="binance-public-v1",
            detail="Verified public trade",
        )
    )
    response = client.get("/api/v1/market-data/latest", params={"symbol": "ETH/USDT"})
    assert response.status_code == 404
    assert "price" not in response.json()
