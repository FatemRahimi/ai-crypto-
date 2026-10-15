from __future__ import annotations

import ssl
from datetime import UTC, datetime

import certifi
import httpx
import pytest
from app.domains.market_data.providers.binance_spot import BinanceSpotProvider, _certificate_bundle
from app.domains.market_data.providers.stream import DeferredPublicTradeStream


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


def _response(status: int, payload: object) -> httpx.Response:
    return httpx.Response(
        status,
        json=payload,
        request=httpx.Request("GET", "https://data-api.binance.vision/test"),
    )


def test_klines_retry_transient_status_then_stop() -> None:
    transport = ScriptedTransport(
        [
            _response(429, {}),
            _response(200, [[1, "2"]]),
        ]
    )
    provider = BinanceSpotProvider(transport=transport, pause_seconds=0, max_attempts=2)
    rows = provider.fetch_klines(
        provider_symbol="BTCUSDT",
        interval="1m",
        start=None,
        end=None,
        limit=1,
        max_candles=1,
    )
    assert rows == [[1, "2"]]
    assert len(transport.calls) == 2


def test_recent_request_does_not_page() -> None:
    transport = ScriptedTransport([_response(200, [[1], [2], [3]])])
    provider = BinanceSpotProvider(transport=transport, pause_seconds=0)
    rows = provider.fetch_klines(
        provider_symbol="BTCUSDT",
        interval="1h",
        start=None,
        end=None,
        limit=3,
        max_candles=10,
    )
    assert len(rows) == 3
    assert len(transport.calls) == 1


def test_range_pages_forward_from_the_last_open_time() -> None:
    start = datetime(2026, 10, 15, tzinfo=UTC)
    transport = ScriptedTransport(
        [
            _response(200, [[1_700_000_000_000, "1"], [1_700_000_060_000, "1"]]),
            _response(200, []),
        ]
    )
    provider = BinanceSpotProvider(transport=transport, pause_seconds=0)
    provider.fetch_klines(
        provider_symbol="BTCUSDT",
        interval="1m",
        start=start,
        end=datetime(2026, 10, 15, 1, tzinfo=UTC),
        limit=2,
        max_candles=4,
    )
    assert len(transport.calls) == 2
    assert transport.calls[1][1]["startTime"] == 1_700_000_060_001


def test_certificate_bundle_uses_ssl_cert_file_when_set(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SSL_CERT_FILE", raising=False)
    assert _certificate_bundle() is True
    monkeypatch.setenv("SSL_CERT_FILE", certifi.where())
    bundle = _certificate_bundle()
    assert bundle is not True
    assert isinstance(bundle, ssl.SSLContext)


def test_deferred_stream_does_not_connect() -> None:
    stream = DeferredPublicTradeStream("binance_spot")
    stream.note_deferred()
    assert stream.connection_state() == "disconnected"
