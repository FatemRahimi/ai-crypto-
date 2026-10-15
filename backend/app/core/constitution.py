"""Flags the running process can actually stand behind.

The written constitution is docs/PROJECT_CONSTITUTION.md.
Only the constants in this module are exposed by the API.
"""

from typing import Literal

PHASE: Literal[1] = 1
EVIDENCE_RULE = "No evidence → no claim."
EXECUTION_ENABLED: Literal[False] = False
CUSTODY: Literal["none"] = "none"
WITHDRAWAL_PERMISSION_ALLOWED: Literal[False] = False
SESSIONS: Literal["not_implemented"] = "not_implemented"
MFA: Literal["not_implemented"] = "not_implemented"
RATE_LIMITING: Literal["not_implemented"] = "not_implemented"
PASSKEYS: Literal["not_implemented"] = "not_implemented"
AUDIT_LOG: Literal["not_implemented"] = "not_implemented"
ENCRYPTED_EXCHANGE_CREDENTIALS: Literal["not_implemented"] = "not_implemented"
