"""Future append-only record of security-sensitive and decision events."""

from app.domains.types import DomainBoundary, ImplementationStatus

BOUNDARY = DomainBoundary(
    key="audit",
    responsibility="Record security-sensitive actions and decision outcomes.",
    must_not=[
        "Be rewritten to hide a rejection",
        "Store a raw secret or credential",
        "Invent a market claim",
    ],
    implementation_status=ImplementationStatus.PLANNED,
    phase_note="No audit writer or audit table is implemented.",
)
