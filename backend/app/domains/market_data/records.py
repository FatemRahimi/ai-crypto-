"""Canonical observations. Downstream code uses these, not provider JSON."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from app.domains.market_data.quality import DataStatus


@dataclass(frozen=True, slots=True)
class CanonicalCandle:
    provider: str
    canonical_symbol: str
    provider_symbol: str
    market_type: str
    quote_asset: str
    interval: str
    open_time: datetime
    close_time: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
    quote_volume: Decimal | None
    trade_count: int | None
    ingested_at: datetime
    data_status: DataStatus
    endpoint: str
    normalization_version: str


@dataclass(frozen=True, slots=True)
class CanonicalTrade:
    provider: str
    canonical_symbol: str
    provider_symbol: str
    market_type: str
    provider_trade_id: int
    price: Decimal
    quantity: Decimal
    quote_quantity: Decimal | None
    event_time: datetime
    buyer_is_maker: bool | None
    ingested_at: datetime
    endpoint: str
    normalization_version: str


@dataclass(frozen=True, slots=True)
class CanonicalBook:
    provider: str
    canonical_symbol: str
    provider_symbol: str
    market_type: str
    bid: Decimal
    ask: Decimal
    bid_quantity: Decimal | None
    ask_quantity: Decimal | None
    source_timestamp: datetime | None
    ingested_at: datetime
    endpoint: str
    normalization_version: str
