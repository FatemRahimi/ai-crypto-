"""Verified market observations.

Prices and derived series enter here from a named feed, or they do not enter.
"""

from app.domains.types import DomainBoundary, ImplementationStatus

BOUNDARY = DomainBoundary(
    key="market_data",
    responsibility="Ingest and retain verifiable market observations.",
    must_not=[
        "Synthesize a price and present it as a last trade",
        "Serve an estimate without labeling its source",
    ],
    implementation_status=ImplementationStatus.FOUNDATION,
    phase_note=(
        "Public Binance spot BTC/USDT and a separate USD-M BTCUSDT perpetual "
        "funding history. No credentials. Funding coverage is not claimed."
    ),
)
