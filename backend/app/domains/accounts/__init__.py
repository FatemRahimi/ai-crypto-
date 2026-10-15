"""Operator-declared capital context.

This is not a wallet and it does not hold balances.
"""

from app.domains.types import DomainBoundary, ImplementationStatus

BOUNDARY = DomainBoundary(
    key="accounts",
    responsibility="Record capital context the operator declares for later planning.",
    must_not=[
        "Custody assets",
        "Invent a balance",
        "Move or withdraw funds",
    ],
    implementation_status=ImplementationStatus.PLANNED,
    phase_note="No account ledger is implemented.",
)
