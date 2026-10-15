"""AI may draft a trade proposal.

It must not import the execution gateway or authorize an intent.
"""

from app.domains.ai.proposals import draft_trade_proposal
from app.domains.types import DomainBoundary, ImplementationStatus

BOUNDARY = DomainBoundary(
    key="ai",
    responsibility="Draft a trade proposal that cites evidence references.",
    must_not=[
        "Submit, approve, or size an order",
        "Bypass quant validation, the risk engine, policy, or the gateway",
        "Invent evidence or cite itself as the evidence source",
    ],
    implementation_status=ImplementationStatus.FOUNDATION,
    phase_note="A proposal type exists. No model is connected.",
)

__all__ = ["BOUNDARY", "draft_trade_proposal"]
