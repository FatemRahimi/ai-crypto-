from __future__ import annotations

from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class Direction(StrEnum):
    LONG = "long"
    SHORT = "short"
    WAIT = "wait"
    NO_TRADE = "no_trade"


class QuantValidationStatus(StrEnum):
    NOT_RUN = "not_run"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    PASSED = "passed"
    FAILED = "failed"


class DomainError(Exception):
    code = "domain_error"


class EvidenceRequiredError(DomainError):
    code = "evidence_required"


class ExecutionBoundaryError(DomainError):
    code = "execution_boundary"


class ExecutionDisabledError(DomainError):
    code = "execution_disabled"


class RiskEngineDisabledError(DomainError):
    code = "risk_engine_disabled"


PIPELINE_STAGES: tuple[str, ...] = (
    "ai_or_strategy",
    "trade_proposal",
    "quant_validation",
    "deterministic_risk_engine",
    "execution_policy",
    "restricted_execution_gateway",
    "exchange_adapter",
)

_SELF_CITATION = frozenset({"ai", "guess", "llm", "model", "opinion"})


class EvidenceRef(BaseModel):
    """Pointer to a verifiable record. The pointer is not the evidence itself."""

    model_config = ConfigDict(extra="forbid")

    source: str = Field(pattern=r"^[a-z0-9_:-]{1,64}$")
    ref: str = Field(min_length=1, max_length=128)

    @field_validator("source")
    @classmethod
    def reject_self_citation(cls, value: str) -> str:
        if value.lower() in _SELF_CITATION:
            raise ValueError("Evidence must cite a verifiable record, not a model opinion")
        return value


class TradeProposal(BaseModel):
    """The only structured output AI may hand to the rest of the system.

    This is not an order. It has no size, price, leverage, or credentials.
    """

    model_config = ConfigDict(extra="forbid")

    proposal_id: UUID
    instrument: str = Field(pattern=r"^[A-Z0-9._:-]{1,32}$")
    direction: Direction
    evidence_refs: list[EvidenceRef] = Field(default_factory=list)
    thesis: str = Field(min_length=1, max_length=2000)

    @model_validator(mode="after")
    def directional_claims_need_evidence(self) -> TradeProposal:
        if self.direction in {Direction.LONG, Direction.SHORT} and not self.evidence_refs:
            raise ValueError("Directional proposals require at least one evidence reference")
        return self


class QuantValidation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    proposal_id: UUID
    status: QuantValidationStatus
    evidence_refs: list[EvidenceRef] = Field(default_factory=list)

    @property
    def passed(self) -> bool:
        return self.status is QuantValidationStatus.PASSED

    @model_validator(mode="after")
    def passed_requires_evidence(self) -> QuantValidation:
        if self.status is QuantValidationStatus.PASSED and not self.evidence_refs:
            raise ValueError("A passing quant validation requires evidence references")
        return self


class RiskDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    proposal_id: UUID
    approved: bool
    reasons: list[str] = Field(min_length=1)
    decided_by: str = "deterministic_risk_engine"

    @field_validator("decided_by")
    @classmethod
    def only_the_risk_engine(cls, value: str) -> str:
        if value != "deterministic_risk_engine":
            raise ValueError("Risk decisions must come from the deterministic risk engine")
        return value

    @field_validator("reasons")
    @classmethod
    def reasons_are_present(cls, value: list[str]) -> list[str]:
        if any(not item.strip() for item in value):
            raise ValueError("Risk reasons cannot be empty")
        return value


class ExecutionPolicyDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    proposal_id: UUID
    allowed: bool
    reasons: list[str] = Field(min_length=1)
    kill_switch_engaged: bool = False

    @field_validator("reasons")
    @classmethod
    def reasons_are_present(cls, value: list[str]) -> list[str]:
        if any(not item.strip() for item in value):
            raise ValueError("Policy reasons cannot be empty")
        return value

    @model_validator(mode="after")
    def kill_switch_fails_closed(self) -> ExecutionPolicyDecision:
        if self.kill_switch_engaged and self.allowed:
            raise ValueError("An engaged kill switch cannot allow execution")
        return self


class ExecutionIntent(BaseModel):
    """Permission token. It is not an order and carries no size, price, or secret."""

    model_config = ConfigDict(extra="forbid")

    proposal_id: UUID
    instrument: str = Field(pattern=r"^[A-Z0-9._:-]{1,32}$")
    direction: Direction
    quant_status: QuantValidationStatus
    risk_decided_by: str

    @model_validator(mode="after")
    def token_is_complete(self) -> ExecutionIntent:
        if self.direction not in {Direction.LONG, Direction.SHORT}:
            raise ValueError("An execution intent must be long or short")
        if self.quant_status is not QuantValidationStatus.PASSED:
            raise ValueError("An execution intent requires a passing quant validation")
        if self.risk_decided_by != "deterministic_risk_engine":
            raise ValueError("An execution intent requires the deterministic risk engine")
        return self


def authorize_execution(
    proposal: TradeProposal,
    quant: QuantValidation,
    risk: RiskDecision,
    policy: ExecutionPolicyDecision,
) -> ExecutionIntent:
    """Choke point between a proposal and a permission token.

    Calling this does not contact an exchange. The gateway still has to accept
    the token, and the Phase 1 gateway refuses every token.
    """

    ids = {proposal.proposal_id, quant.proposal_id, risk.proposal_id, policy.proposal_id}
    if len(ids) != 1:
        raise ExecutionBoundaryError("Proposal, quant, risk, and policy ids must match")
    if proposal.direction not in {Direction.LONG, Direction.SHORT}:
        raise ExecutionBoundaryError("Only long or short proposals can be authorized")
    if not proposal.evidence_refs or not quant.evidence_refs:
        raise EvidenceRequiredError("No evidence → no claim")
    if not quant.passed:
        raise ExecutionBoundaryError("Quant validation has not passed")
    if not risk.approved:
        raise ExecutionBoundaryError("Deterministic risk approval is required")
    if not policy.allowed or policy.kill_switch_engaged:
        raise ExecutionBoundaryError("Execution policy does not allow this proposal")
    return ExecutionIntent(
        proposal_id=proposal.proposal_id,
        instrument=proposal.instrument,
        direction=proposal.direction,
        quant_status=QuantValidationStatus.PASSED,
        risk_decided_by=risk.decided_by,
    )
