"""Deterministic risk approval.

A language model cannot approve, reject, or override this domain.
"""

from app.domains.risk.engine import RiskEngine, RiskEngineNotEnabled
from app.domains.types import DomainBoundary, ImplementationStatus

BOUNDARY = DomainBoundary(
    key="risk",
    responsibility="Approve or reject a proposal with deterministic rules.",
    must_not=[
        "Call a language model to decide approval",
        "Accept an override written in AI prose",
        "Approve when required inputs are missing",
    ],
    implementation_status=ImplementationStatus.DISABLED,
    phase_note="The engine refuses every evaluation. No risk rules are implemented.",
)

__all__ = ["BOUNDARY", "RiskEngine", "RiskEngineNotEnabled"]
