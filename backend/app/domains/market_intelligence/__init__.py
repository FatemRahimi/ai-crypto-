"""Evidence-backed descriptions of market state.

Interpretation stays downstream of market data and upstream of orders.
"""

from app.domains.types import DomainBoundary, ImplementationStatus

BOUNDARY = DomainBoundary(
    key="market_intelligence",
    responsibility="Assemble descriptions of market state that cite stored observations.",
    must_not=[
        "Emit an exchange order",
        "Claim structure without a market-data reference",
        "Store a language-model measurement",
        "Emit a trade recommendation or a probability",
    ],
    implementation_status=ImplementationStatus.FOUNDATION,
    phase_note=(
        "Phase 3A stores deterministic technical evidence from verified candles. "
        "No profile, order flow, derivatives, or LLM measurement."
    ),
)
