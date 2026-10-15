"""Live stream boundary.

The public Binance stream `wss://data-stream.binance.vision/ws/btcusdt@trade`
is documented and unauthenticated. A continuous client is deferred to Phase 2.1
so this phase does not grow a reconnect loop before the stored candle path is
proven. Calling `note_deferred` records that the stream is not running.
"""

from __future__ import annotations

import logging
from typing import Literal, Protocol

logger = logging.getLogger("app.market_data.stream")

ConnectionState = Literal["disconnected", "connecting", "connected"]


class MarketStream(Protocol):
    def connection_state(self) -> ConnectionState:
        """Current connection. Deferred streams stay disconnected."""

    def note_deferred(self) -> None:
        """Record that no socket was opened."""


class DeferredPublicTradeStream:
    """No socket, no retry loop, no credentials."""

    def __init__(self, provider: str) -> None:
        self.provider = provider
        self._state: ConnectionState = "disconnected"

    def connection_state(self) -> ConnectionState:
        return self._state

    def note_deferred(self) -> None:
        self._state = "disconnected"
        logger.info(
            "market_data_stream_disconnected provider=%s reason=deferred",
            self.provider,
        )
