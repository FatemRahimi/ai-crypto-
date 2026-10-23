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

# USD-M perpetual. The provider symbol text matches spot BTCUSDT; the market does not.
BTC_USDT_USD_M_PERPETUAL = MarketIdentity(
    provider="binance_usdm",
    market_type="perpetual",
    base_asset="BTC",
    quote_asset="USDT",
    provider_symbol="BTCUSDT",
    canonical_symbol="BTCUSDT-PERP",
)

NORMALIZATION_VERSION = "binance-public-v1"
SUPPORTED_INTERVALS = ("1m", "5m", "15m", "1h", "4h", "1d")
