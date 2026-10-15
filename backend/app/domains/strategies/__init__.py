"""Human trading intent and future compiled rules.

A desired return is a preference, not a forecast.
"""

from app.domains.types import DomainBoundary, ImplementationStatus

BOUNDARY = DomainBoundary(
    key="strategies",
    responsibility="Capture operator intent and, later, compile it into testable rules.",
    must_not=[
        "Submit an order",
        "Treat a desired return as an expected return",
        "Activate a strategy without quant validation",
    ],
    implementation_status=ImplementationStatus.PLANNED,
    phase_note="No strategy is stored or compiled.",
)
