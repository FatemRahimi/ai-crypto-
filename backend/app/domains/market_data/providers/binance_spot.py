"""Binance public spot market data.

Official references, retrieved 2026-10-16:

- https://github.com/binance/binance-spot-api-docs/blob/master/rest-api.md
- https://github.com/binance/binance-spot-api-docs/blob/master/faqs/market_data_only.md

Host `https://data-api.binance.vision` serves public market data without an API key.
This adapter calls `/api/v3/klines`, `/api/v3/trades`, `/api/v3/aggTrades`,
and `/api/v3/ticker/bookTicker`. It does not call account or signed endpoints.

`GET /api/v3/aggTrades` is weight 4 and reads the database. Parameters are
symbol, fromId, startTime, endTime, and limit (maximum 1000). The docs do not
define combining fromId with the time bounds, result order, or a maximum
window length. This adapter never sends fromId together with startTime or
endTime, and it does not treat a full page as a complete clock window.
"""

from __future__ import annotations

import logging
import os
import ssl
import time
from datetime import UTC, datetime
from typing import Protocol

import httpx

from app.domains.market_data.providers.base import (
    AggregateRetrieval,
    AggregateStop,
    MarketDataProviderError,
)

logger = logging.getLogger("app.market_data.provider")

KLINES_PATH = "/api/v3/klines"
TRADES_PATH = "/api/v3/trades"
AGG_TRADES_PATH = "/api/v3/aggTrades"
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
        page_limit: int = PAGE_LIMIT,
        transport: HttpGetter | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.pause_seconds = pause_seconds
        self.max_attempts = max_attempts
        if page_limit < 1 or page_limit > PAGE_LIMIT:
            raise MarketDataProviderError("aggregate page limit must be from 1 to 1000")
        self.page_limit = page_limit
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

    def fetch_aggregate_trades(
        self,
        *,
        provider_symbol: str,
        start: datetime,
        end: datetime,
        max_trades: int,
    ) -> AggregateRetrieval:
        """Page a bounded window. fromId is never combined with startTime or endTime."""
        if start.tzinfo is None or start.utcoffset() is None:
            raise MarketDataProviderError("provider bounds must be timezone-aware")
        if end.tzinfo is None or end.utcoffset() is None:
            raise MarketDataProviderError("provider bounds must be timezone-aware")
        if end < start:
            raise MarketDataProviderError("end is before start")
        if max_trades < 1:
            raise MarketDataProviderError("aggregate trade limit must be positive")
        pages: list[tuple[object, ...]] = []
        collected = 0
        from_id: int | None = None
        saw_full_page = False
        stop: AggregateStop = "short_page"
        end_ms = _millis(end)
        while collected < max_trades:
            page_limit = min(self.page_limit, max_trades - collected)
            if from_id is None:
                params: dict[str, str | int] = {
                    "symbol": provider_symbol,
                    "startTime": _millis(start),
                    "endTime": end_ms,
                    "limit": page_limit,
                }
            else:
                params = {"symbol": provider_symbol, "fromId": from_id, "limit": page_limit}
            payload = self._get_json(AGG_TRADES_PATH, params)
            if not isinstance(payload, list):
                raise MarketDataProviderError("aggTrades response was not a list")
            if not payload:
                stop = "empty" if not pages else "short_page"
                break
            pages.append(tuple(payload))
            collected += len(payload)
            if from_id is not None and _page_crosses_end(payload, end_ms):
                stop = "crossed_end"
                break
            if len(payload) < page_limit:
                stop = "short_page"
                break
            saw_full_page = True
            if collected >= max_trades:
                stop = "cap"
                break
            last_id = _aggregate_id(payload[-1])
            if last_id is None:
                stop = "no_progress"
                break
            next_id = last_id + 1
            if from_id is not None and next_id <= from_id:
                stop = "no_progress"
                break
            from_id = next_id
            time.sleep(self.pause_seconds)
        return AggregateRetrieval(pages=tuple(pages), stop=stop, saw_full_page=saw_full_page)

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


def _aggregate_id(row: object) -> int | None:
    if not isinstance(row, dict):
        return None
    value = row.get("a")
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


def _page_crosses_end(page: list[object], end_ms: int) -> bool:
    for row in page:
        if not isinstance(row, dict):
            continue
        stamp = row.get("T")
        if isinstance(stamp, bool) or not isinstance(stamp, int):
            continue
        if stamp > end_ms:
            return True
    return False


def _millis(value: datetime) -> int:
    if value.tzinfo is None:
        raise MarketDataProviderError("provider bounds must be timezone-aware")
    return int(value.timestamp() * 1000)
