"""Future view of positions that came from verified fills."""

from app.domains.types import DomainBoundary, ImplementationStatus

BOUNDARY = DomainBoundary(
    key="positions",
    responsibility="Represent positions once fills are verified.",
    must_not=[
        "Display entry, liquidation, or PnL without a verified source",
        "Close or reduce a position by itself",
    ],
    implementation_status=ImplementationStatus.PLANNED,
    phase_note="No position book is implemented.",
)
