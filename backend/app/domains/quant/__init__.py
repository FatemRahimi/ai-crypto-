"""Validation and future research runs.

A number from this domain requires a completed run record.
"""

from app.domains.types import DomainBoundary, ImplementationStatus

BOUNDARY = DomainBoundary(
    key="quant",
    responsibility="Validate proposals and, later, record research and backtests.",
    must_not=[
        "Invent a backtest result",
        "Publish a probability without a model-run record",
        "Be skipped for a directional execution",
    ],
    implementation_status=ImplementationStatus.PLANNED,
    phase_note="No backtest, statistic, or probability model is implemented.",
)
