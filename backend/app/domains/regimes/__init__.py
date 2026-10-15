"""Future classifications of BTC behaviour from quantitative features."""

from app.domains.types import DomainBoundary, ImplementationStatus

BOUNDARY = DomainBoundary(
    key="regimes",
    responsibility="Classify market behaviour from measured features once those features exist.",
    must_not=[
        "Present a language-model label as a measurement",
        "Drive an order on its own",
    ],
    implementation_status=ImplementationStatus.PLANNED,
    phase_note="No regime model is implemented.",
)
