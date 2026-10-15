"""Exchange connection metadata.

Secrets, when they eventually exist, stay on the server in encrypted storage.
They are never accepted by the frontend in this phase.
"""

from app.domains.types import DomainBoundary, ImplementationStatus

BOUNDARY = DomainBoundary(
    key="connections",
    responsibility="Describe a future read or trade connection to an exchange account.",
    must_not=[
        "Request withdrawal permission",
        "Store a raw API secret in the browser, logs, or git",
        "Enable order placement by default",
    ],
    implementation_status=ImplementationStatus.PLANNED,
    phase_note="No exchange connection form or credential store is implemented.",
)
