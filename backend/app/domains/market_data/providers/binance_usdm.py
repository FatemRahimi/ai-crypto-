"""Binance USD-M public funding history.

Official contract, read 2026-10-17 from the USD-M REST market-data schema:

- host https://fapi.binance.com
- GET /fapi/v1/fundingRate
- GET /fapi/v1/exchangeInfo

The history route takes symbol, inclusive startTime, inclusive endTime, and
limit (maximum 1000), and returns rows in ascending order. It does not
document a page cursor or a complete archive. This adapter does not send a
credential and does not persist markPrice.
"""

from __future__ import annotations

import logging
import os
import ssl
import time
from dataclasses import dataclass
from datetime import UTC, datetime

import httpx

from app.domains.market_data.funding import (
    PAGE_LIMIT,
    FundingPageRun,
    FundingStop,
    retrieve_funding_pages,
)
from app.domains.market_data.providers.base import MarketDataProviderError

logger = logging.getLogger("app.market_data.usdm")

FUNDING_PATH = "/fapi/v1/fundingRate"
EXCHANGE_INFO_PATH = "/fapi/v1/exchangeInfo"
TRANSIENT_STATUS = {429, 500, 502, 503, 504}


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


@dataclass(frozen=True, slots=True)
class FundingRetrieval:
    pages: tuple[tuple[object, ...], ...]
    stop: FundingStop
    saw_full_page: bool
    contract_type: str | None


class BinanceUsdMProvider:
    name = "binance_usdm"

    def __init__(
        self,
        base_url: str = "https://fapi.binance.com",
        *,
        timeout_seconds: float = 20.0,
        pause_seconds: float = 0.25,
        max_attempts: int = 3,
        page_limit: int = PAGE_LIMIT,
        transport: HttpxGetter | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.pause_seconds = pause_seconds
        self.max_attempts = max_attempts
        if page_limit < 1 or page_limit > PAGE_LIMIT:
            raise MarketDataProviderError("funding page limit must be from 1 to 1000")
        self.page_limit = page_limit
        self._owned = transport is None
        self._transport = transport or HttpxGetter(self.base_url, timeout_seconds)

    def close(self) -> None:
        if self._owned and isinstance(self._transport, HttpxGetter):
            self._transport.close()

    def fetch_funding(
        self,
        *,
        provider_symbol: str,
        start: datetime,
        end: datetime,
        max_rows: int,
    ) -> FundingRetrieval:
        if start.tzinfo is None or end.tzinfo is None:
            raise MarketDataProviderError("provider bounds must be timezone-aware")
        contract_type = contract_type_for_symbol(
            self._get_json(EXCHANGE_INFO_PATH, {}),
            provider_symbol,
        )

        calls = 0

        def fetch_page(start_ms: int, end_ms: int, limit: int) -> list[object]:
            nonlocal calls
            if calls:
                time.sleep(self.pause_seconds)
            calls += 1
            payload = self._get_json(
                FUNDING_PATH,
                {
                    "symbol": provider_symbol,
                    "startTime": start_ms,
                    "endTime": end_ms,
                    "limit": limit,
                },
            )
            if not isinstance(payload, list):
                raise MarketDataProviderError("fundingRate response was not a list")
            return payload

        run: FundingPageRun = retrieve_funding_pages(
            fetch_page,
            start_ms=_millis(start),
            end_ms=_millis(end),
            page_limit=self.page_limit,
            max_rows=max_rows,
        )
        return FundingRetrieval(
            pages=run.pages,
            stop=run.stop,
            saw_full_page=run.saw_full_page,
            contract_type=contract_type,
        )

    def _get_json(self, path: str, params: dict[str, str | int]) -> object:
        logger.info("usdm_fetch_started provider=%s endpoint=%s", self.name, path)
        delay = self.pause_seconds
        last_error = "provider request failed"
        for attempt in range(1, self.max_attempts + 1):
            try:
                response = self._transport.get(path, params)
            except httpx.HTTPError as exc:
                last_error = type(exc).__name__
                if attempt == self.max_attempts:
                    break
                time.sleep(delay)
                delay *= 2
                continue
            if response.status_code in TRANSIENT_STATUS:
                last_error = f"http_{response.status_code}"
                if attempt == self.max_attempts:
                    break
                time.sleep(delay)
                delay *= 2
                continue
            if response.status_code >= 400:
                raise MarketDataProviderError(f"provider returned HTTP {response.status_code}")
            payload: object = response.json()
            return payload
        raise MarketDataProviderError(last_error)


def contract_type_for_symbol(payload: object, symbol: str) -> str | None:
    """Return the contractType for one symbol. Ambiguous matches return None."""
    if not isinstance(payload, dict):
        return None
    symbols = payload.get("symbols")
    if not isinstance(symbols, list):
        return None
    found: str | None = None
    for item in symbols:
        if not isinstance(item, dict) or item.get("symbol") != symbol:
            continue
        value = item.get("contractType")
        if not isinstance(value, str):
            return None
        if found is not None and found != value:
            return None
        found = value
    return found


def _millis(value: datetime) -> int:
    utc = value.astimezone(UTC)
    epoch = datetime(1970, 1, 1, tzinfo=UTC)
    delta = utc - epoch
    return (delta.days * 86400 + delta.seconds) * 1000 + delta.microseconds // 1000


def _certificate_bundle() -> ssl.SSLContext | bool:
    bundle = os.environ.get("SSL_CERT_FILE", "").strip()
    if not bundle:
        return True
    return ssl.create_default_context(cafile=bundle)
