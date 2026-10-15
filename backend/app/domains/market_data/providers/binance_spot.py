"""Binance public spot market data.

Official references, retrieved 2026-10-15:

- https://github.com/binance/binance-spot-api-docs/blob/master/rest-api.md
- https://github.com/binance/binance-spot-api-docs/blob/master/faqs/market_data_only.md

Host `https://data-api.binance.vision` serves public market data without an API key.
This adapter calls only endpoints listed there: `/api/v3/klines`, `/api/v3/trades`,
and `/api/v3/ticker/bookTicker`. It does not call account or signed endpoints.
"""

from __future__ import annotations

import logging
import os
import ssl
import time
from datetime import UTC, datetime
from typing import Protocol

import httpx

from app.domains.market_data.providers.base import MarketDataProviderError

logger = logging.getLogger("app.market_data.provider")

KLINES_PATH = "/api/v3/klines"
TRADES_PATH = "/api/v3/trades"
BOOK_PATH = "/api/v3/ticker/bookTicker"
PAGE_LIMIT = 1000
TRANSIENT_STATUS = {429, 500, 502, 503, 504}


class HttpGetter(Protocol):
    def get(self, path: str, params: dict[str, str | int]) -> httpx.Response:
        """Perform one GET."""


class HttpxGetter:
    def __init__(self, base_url: str, timeout_seconds: float) -> None:
        self._client = httpx.Client(
            base_url=base_url,
            timeout=timeout_seconds,
            verify=_certificate_bundle(),
        )

    def get(self, path: str, params: dict[str, str | int]) -> httpx.Response:
        return self._client.get(path, params=params)

    def close(self) -> None:
        self._client.close()


class BinanceSpotProvider:
    name = "binance_spot"

    def __init__(
        self,
        base_url: str = "https://data-api.binance.vision",
        *,
        timeout_seconds: float = 10.0,
        pause_seconds: float = 0.25,
        max_attempts: int = 3,
        transport: HttpGetter | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.pause_seconds = pause_seconds
        self.max_attempts = max_attempts
        self._owned = transport is None
        self._transport = transport or HttpxGetter(self.base_url, timeout_seconds)

    def close(self) -> None:
        if self._owned and isinstance(self._transport, HttpxGetter):
            self._transport.close()

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
        if limit < 1 or max_candles < 1:
            raise MarketDataProviderError("candle limit must be positive")
        collected: list[list[object]] = []
        cursor = start
        while len(collected) < max_candles:
            page_limit = min(PAGE_LIMIT, limit, max_candles - len(collected))
            params: dict[str, str | int] = {
                "symbol": provider_symbol,
                "interval": interval,
                "limit": page_limit,
            }
            if cursor is not None:
                params["startTime"] = _millis(cursor)
            if end is not None:
                params["endTime"] = _millis(end)
            page = self._get_json(KLINES_PATH, params)
            if not isinstance(page, list):
                raise MarketDataProviderError("klines response was not a list")
            rows = [row for row in page if isinstance(row, list)]
            if len(rows) != len(page):
                raise MarketDataProviderError("klines response contained a non-list row")
            if not rows:
                break
            collected.extend(rows)
            if start is None or len(rows) < page_limit or len(collected) >= max_candles:
                break
            last_open = rows[-1][0]
            if not isinstance(last_open, int):
                break
            next_open = datetime.fromtimestamp((last_open + 1) / 1000, tz=UTC)
            if end is not None and next_open > end:
                break
            cursor = next_open
            time.sleep(self.pause_seconds)
        return collected[:max_candles]

    def fetch_recent_trades(self, *, provider_symbol: str, limit: int) -> list[object]:
        if limit < 1 or limit > PAGE_LIMIT:
            raise MarketDataProviderError("trade limit must be from 1 to 1000")
        payload = self._get_json(TRADES_PATH, {"symbol": provider_symbol, "limit": limit})
        if not isinstance(payload, list):
            raise MarketDataProviderError("trades response was not a list")
        return payload

    def fetch_book_ticker(self, *, provider_symbol: str) -> object:
        return self._get_json(BOOK_PATH, {"symbol": provider_symbol})

    def _get_json(self, path: str, params: dict[str, str | int]) -> object:
        logger.info(
            "market_data_fetch_started provider=%s endpoint=%s symbol=%s",
            self.name,
            path,
            params.get("symbol", ""),
        )
        delay = self.pause_seconds
        last_error = "provider request failed"
        for attempt in range(1, self.max_attempts + 1):
            try:
                response = self._transport.get(path, params)
            except httpx.HTTPError as exc:
                last_error = type(exc).__name__
                logger.info(
                    "market_data_fetch_failed provider=%s endpoint=%s error_type=%s attempt=%s",
                    self.name,
                    path,
                    last_error,
                    attempt,
                )
                if attempt == self.max_attempts:
                    break
                time.sleep(delay)
                delay *= 2
                continue
            if response.status_code in TRANSIENT_STATUS:
                last_error = f"http_{response.status_code}"
                logger.info(
                    "market_data_fetch_failed provider=%s endpoint=%s error_type=%s attempt=%s",
                    self.name,
                    path,
                    last_error,
                    attempt,
                )
                if attempt == self.max_attempts:
                    break
                time.sleep(delay)
                delay *= 2
                continue
            if response.status_code >= 400:
                logger.info(
                    "market_data_fetch_failed provider=%s endpoint=%s "
                    "error_type=http_%s attempt=%s",
                    self.name,
                    path,
                    response.status_code,
                    attempt,
                )
                raise MarketDataProviderError(f"provider returned HTTP {response.status_code}")
            logger.info(
                "market_data_fetch_completed provider=%s endpoint=%s status=%s",
                self.name,
                path,
                response.status_code,
            )
            payload: object = response.json()
            return payload
        raise MarketDataProviderError(last_error)


def _certificate_bundle() -> ssl.SSLContext | bool:
    """Use SSL_CERT_FILE when the process must trust the OS certificate store."""
    bundle = os.environ.get("SSL_CERT_FILE", "").strip()
    if not bundle:
        return True
    return ssl.create_default_context(cafile=bundle)


def _millis(value: datetime) -> int:
    if value.tzinfo is None:
        raise MarketDataProviderError("provider bounds must be timezone-aware")
    return int(value.timestamp() * 1000)
