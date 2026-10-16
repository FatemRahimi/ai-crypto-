"""Provider boundary. Domain services depend on this, not on one exchange SDK."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Protocol


class MarketDataProviderError(Exception):
    """The public provider did not return a usable response."""


AggregateStop = Literal["empty", "short_page", "crossed_end", "cap", "no_progress"]


@dataclass(frozen=True, slots=True)
class AggregateRetrieval:
    pages: tuple[tuple[object, ...], ...]
    stop: AggregateStop
    saw_full_page: bool


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

    def fetch_aggregate_trades(
        self,
        *,
        provider_symbol: str,
        start: datetime,
        end: datetime,
        max_trades: int,
    ) -> AggregateRetrieval:
        """Return raw aggregate-trade pages for an explicit window."""
