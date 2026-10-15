"""Candidate market states.

The vocabulary is long, short, wait, and no trade.
None of those words is an order.
"""

from app.domains.types import DomainBoundary, ImplementationStatus

BOUNDARY = DomainBoundary(
    key="opportunities",
    responsibility="Present candidate states assembled from evidence.",
    must_not=[
        "Assign a probability",
        "Become an order without the execution pipeline",
        "Show an entry, stop, or target without a verified source",
    ],
    implementation_status=ImplementationStatus.PLANNED,
    phase_note="No opportunity is evaluated.",
)
