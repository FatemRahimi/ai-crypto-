"""Future sizing and exposure limits.

This domain does not hold funds.
"""

from app.domains.types import DomainBoundary, ImplementationStatus

BOUNDARY = DomainBoundary(
    key="capital",
    responsibility="Apply capital and exposure limits after risk approval.",
    must_not=[
        "Custody or transfer funds",
        "Size a position before risk approval",
        "Invent free collateral",
    ],
    implementation_status=ImplementationStatus.PLANNED,
    phase_note="No sizing or leverage rule is implemented.",
)
