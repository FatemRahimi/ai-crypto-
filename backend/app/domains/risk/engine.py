from __future__ import annotations

from typing import Protocol

from app.domains.pipeline import (
    QuantValidation,
    RiskDecision,
    RiskEngineDisabledError,
    TradeProposal,
)


class RiskEngine(Protocol):
    def evaluate(self, proposal: TradeProposal, quant: QuantValidation) -> RiskDecision:
        """Deterministic evaluation. Implementations must not call a language model."""


class RiskEngineNotEnabled:
    """Phase 1 risk engine. It fails closed."""

    def evaluate(self, proposal: TradeProposal, quant: QuantValidation) -> RiskDecision:
        del proposal, quant
        raise RiskEngineDisabledError(
            "The deterministic risk engine is not implemented. It will not approve a proposal."
        )
