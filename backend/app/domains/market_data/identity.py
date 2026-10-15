"""Explicit market identity. BTC/USD and BTC/USDT are not the same market."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class MarketIdentity:
    provider: str
    market_type: str
    base_asset: str
    quote_asset: str
    provider_symbol: str
    canonical_symbol: str


BTC_USDT_SPOT = MarketIdentity(
    provider="binance_spot",
    market_type="spot",
    base_asset="BTC",
    quote_asset="USDT",
    provider_symbol="BTCUSDT",
    canonical_symbol="BTC/USDT",
)

NORMALIZATION_VERSION = "binance-public-v1"
SUPPORTED_INTERVALS = ("1m", "5m", "15m", "1h", "4h", "1d")
