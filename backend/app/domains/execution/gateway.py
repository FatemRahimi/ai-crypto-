from __future__ import annotations

from typing import Protocol

from app.domains.pipeline import ExecutionDisabledError, ExecutionIntent


class ExecutionGateway(Protocol):
    def submit(self, intent: ExecutionIntent) -> None:
        """Hand an authorized intent to an exchange adapter."""


class GatewayNotEnabled:
    """Phase 1 gateway. Submission is impossible here."""

    def submit(self, intent: ExecutionIntent) -> None:
        del intent
        raise ExecutionDisabledError(
            "Execution is disabled. Phase 1 has no exchange adapter and will not submit orders."
        )
