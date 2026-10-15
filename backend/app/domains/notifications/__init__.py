"""Future alerts about verified state changes."""

from app.domains.types import DomainBoundary, ImplementationStatus

BOUNDARY = DomainBoundary(
    key="notifications",
    responsibility="Notify the operator when a verified state changes.",
    must_not=[
        "Fabricate urgency",
        "State a market or account fact that was not recorded",
    ],
    implementation_status=ImplementationStatus.PLANNED,
    phase_note="No notification channel is implemented.",
)
