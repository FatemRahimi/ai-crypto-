"""Operator identity.

Future home of authentication, sessions, MFA, and passkeys.
This package does not grant trading authority.
"""

from app.domains.types import DomainBoundary, ImplementationStatus

BOUNDARY = DomainBoundary(
    key="identity",
    responsibility="Authenticate the human operator and, later, their sessions.",
    must_not=[
        "Authorize an exchange order",
        "Store exchange credentials",
        "Treat a model prompt as authentication",
    ],
    implementation_status=ImplementationStatus.PLANNED,
    phase_note="No login, session, MFA, or passkey flow is implemented.",
)
