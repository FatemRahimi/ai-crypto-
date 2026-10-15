"""The only future path from an authorized intent to an exchange adapter.

AI, strategy, and research code must not import the gateway to submit an order.
"""

from app.domains.execution.gateway import ExecutionGateway, GatewayNotEnabled
from app.domains.types import DomainBoundary, ImplementationStatus

BOUNDARY = DomainBoundary(
    key="execution",
    responsibility="Accept an authorized intent and, in a later phase, pass it to an adapter.",
    must_not=[
        "Accept a call from the AI domain",
        "Submit an order while this phase is running",
        "Request withdrawal permission",
    ],
    implementation_status=ImplementationStatus.DISABLED,
    phase_note="The gateway refuses every intent. No exchange adapter exists.",
)

__all__ = ["BOUNDARY", "ExecutionGateway", "GatewayNotEnabled"]
