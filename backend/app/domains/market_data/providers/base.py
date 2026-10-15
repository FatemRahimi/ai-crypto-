"""Provider boundary. Domain services depend on this, not on one exchange SDK."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol


class MarketDataProviderError(Exception):
    """The public provider did not return a usable response."""


class MarketDataProvider(Protocol):
    name: str

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
        """Return provider kline rows. The caller normalizes them."""

    def fetch_recent_trades(self, *, provider_symbol: str, limit: int) -> list[object]:
        """Return recent public trades. Not an account trade history."""

    def fetch_book_ticker(self, *, provider_symbol: str) -> object:
        """Return the current public best bid and ask."""
