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
    ],
    implementation_status=ImplementationStatus.PLANNED,
    phase_note="No market interpretation is implemented.",
)
