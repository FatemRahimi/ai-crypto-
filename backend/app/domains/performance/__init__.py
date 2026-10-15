"""Future statistics computed from verified executions."""

from app.domains.types import DomainBoundary, ImplementationStatus

BOUNDARY = DomainBoundary(
    key="performance",
    responsibility="Compute performance from verified fills and decisions.",
    must_not=[
        "Fabricate profit, drawdown, or a trading record",
        "Present a sample chart as account history",
    ],
    implementation_status=ImplementationStatus.PLANNED,
    phase_note="No performance calculation is implemented.",
)
