from __future__ import annotations

from uuid import uuid4

import pytest
from app.domains.ai import draft_trade_proposal
from app.domains.execution import GatewayNotEnabled
from app.domains.pipeline import (
    Direction,
    EvidenceRef,
    EvidenceRequiredError,
    ExecutionBoundaryError,
    ExecutionDisabledError,
    ExecutionPolicyDecision,
    QuantValidation,
    QuantValidationStatus,
    RiskDecision,
    TradeProposal,
    authorize_execution,
)
from app.domains.risk import RiskEngineNotEnabled
from pydantic import ValidationError


def _evidence() -> EvidenceRef:
    return EvidenceRef(source="candle_store", ref="btc-2026-01-01")


def test_wait_proposal_does_not_require_evidence() -> None:
    proposal = draft_trade_proposal(
        proposal_id=uuid4(),
        instrument="BTCUSDT",
        direction=Direction.WAIT,
        thesis="No directional claim.",
    )
    assert proposal.evidence_refs == []


def test_directional_proposal_requires_evidence() -> None:
    with pytest.raises(ValidationError):
        draft_trade_proposal(
            proposal_id=uuid4(),
            instrument="BTCUSDT",
            direction=Direction.LONG,
            thesis="A long claim without a record.",
        )


def test_evidence_cannot_cite_the_model_itself() -> None:
    with pytest.raises(ValidationError):
        EvidenceRef(source="llm", ref="chat-1")


def test_proposal_rejects_order_and_probability_fields() -> None:
    proposal_id = uuid4()
    with pytest.raises(ValidationError):
        TradeProposal.model_validate(
            {
                "proposal_id": str(proposal_id),
                "instrument": "BTCUSDT",
                "direction": "long",
                "thesis": "Has evidence.",
                "evidence_refs": [{"source": "candle_store", "ref": "1"}],
                "probability": 0.72,
            }
        )
    with pytest.raises(ValidationError):
        TradeProposal.model_validate(
            {
                "proposal_id": str(proposal_id),
                "instrument": "BTCUSDT",
                "direction": "long",
                "thesis": "Has evidence.",
                "evidence_refs": [{"source": "candle_store", "ref": "1"}],
                "quantity": 1,
                "leverage": 5,
            }
        )


def test_risk_decision_cannot_come_from_a_language_model() -> None:
    with pytest.raises(ValidationError):
        RiskDecision(
            proposal_id=uuid4(),
            approved=True,
            reasons=["model said so"],
            decided_by="llm",
        )


def test_kill_switch_cannot_be_combined_with_permission() -> None:
    with pytest.raises(ValidationError):
        ExecutionPolicyDecision(
            proposal_id=uuid4(),
            allowed=True,
            reasons=["switch is on"],
            kill_switch_engaged=True,
        )


def test_authorize_execution_requires_the_full_chain() -> None:
    proposal_id = uuid4()
    proposal = TradeProposal(
        proposal_id=proposal_id,
        instrument="BTCUSDT",
        direction=Direction.LONG,
        thesis="Boundary fixture.",
        evidence_refs=[_evidence()],
    )
    quant = QuantValidation(
        proposal_id=proposal_id,
        status=QuantValidationStatus.PASSED,
        evidence_refs=[_evidence()],
    )
    risk = RiskDecision(proposal_id=proposal_id, approved=True, reasons=["fixture"])
    blocked = ExecutionPolicyDecision(
        proposal_id=proposal_id,
        allowed=False,
        reasons=["kill switch"],
        kill_switch_engaged=True,
    )
    with pytest.raises(ExecutionBoundaryError):
        authorize_execution(proposal, quant, risk, blocked)

    allowed = ExecutionPolicyDecision(
        proposal_id=proposal_id,
        allowed=True,
        reasons=["policy fixture"],
    )
    intent = authorize_execution(proposal, quant, risk, allowed)
    assert intent.direction is Direction.LONG
    with pytest.raises(ExecutionDisabledError):
        GatewayNotEnabled().submit(intent)


def test_missing_evidence_stops_authorization() -> None:
    proposal_id = uuid4()
    proposal = TradeProposal(
        proposal_id=proposal_id,
        instrument="BTCUSDT",
        direction=Direction.NO_TRADE,
        thesis="No trade.",
    )
    quant = QuantValidation(proposal_id=proposal_id, status=QuantValidationStatus.NOT_RUN)
    risk = RiskDecision(proposal_id=proposal_id, approved=False, reasons=["not run"])
    policy = ExecutionPolicyDecision(
        proposal_id=proposal_id,
        allowed=False,
        reasons=["not run"],
    )
    with pytest.raises(ExecutionBoundaryError):
        authorize_execution(proposal, quant, risk, policy)


def test_passed_quant_without_evidence_is_rejected() -> None:
    with pytest.raises(ValidationError):
        QuantValidation(proposal_id=uuid4(), status=QuantValidationStatus.PASSED)


def test_mismatched_ids_are_rejected() -> None:
    proposal = TradeProposal(
        proposal_id=uuid4(),
        instrument="BTCUSDT",
        direction=Direction.SHORT,
        thesis="Boundary fixture.",
        evidence_refs=[_evidence()],
    )
    quant = QuantValidation(
        proposal_id=uuid4(),
        status=QuantValidationStatus.PASSED,
        evidence_refs=[_evidence()],
    )
    risk = RiskDecision(proposal_id=proposal.proposal_id, approved=True, reasons=["fixture"])
    policy = ExecutionPolicyDecision(
        proposal_id=proposal.proposal_id,
        allowed=True,
        reasons=["fixture"],
    )
    with pytest.raises(ExecutionBoundaryError):
        authorize_execution(proposal, quant, risk, policy)


def test_directional_authorization_fails_closed_without_quant_evidence() -> None:
    proposal_id = uuid4()
    proposal = TradeProposal(
        proposal_id=proposal_id,
        instrument="BTCUSDT",
        direction=Direction.LONG,
        thesis="Boundary fixture.",
        evidence_refs=[_evidence()],
    )
    quant = QuantValidation(proposal_id=proposal_id, status=QuantValidationStatus.FAILED)
    risk = RiskDecision(proposal_id=proposal_id, approved=True, reasons=["fixture"])
    policy = ExecutionPolicyDecision(
        proposal_id=proposal_id,
        allowed=True,
        reasons=["fixture"],
    )
    with pytest.raises(EvidenceRequiredError):
        authorize_execution(proposal, quant, risk, policy)


def test_failed_quant_cannot_be_authorized() -> None:
    proposal_id = uuid4()
    proposal = TradeProposal(
        proposal_id=proposal_id,
        instrument="BTCUSDT",
        direction=Direction.SHORT,
        thesis="Boundary fixture.",
        evidence_refs=[_evidence()],
    )
    quant = QuantValidation(
        proposal_id=proposal_id,
        status=QuantValidationStatus.FAILED,
        evidence_refs=[_evidence()],
    )
    risk = RiskDecision(proposal_id=proposal_id, approved=True, reasons=["fixture"])
    policy = ExecutionPolicyDecision(
        proposal_id=proposal_id,
        allowed=True,
        reasons=["fixture"],
    )
    with pytest.raises(ExecutionBoundaryError):
        authorize_execution(proposal, quant, risk, policy)


def test_risk_engine_and_empty_quant_fail_closed() -> None:
    proposal = TradeProposal(
        proposal_id=uuid4(),
        instrument="BTCUSDT",
        direction=Direction.WAIT,
        thesis="No evaluation.",
    )
    quant = QuantValidation(proposal_id=proposal.proposal_id, status=QuantValidationStatus.NOT_RUN)
    with pytest.raises(Exception, match="not implemented"):
        RiskEngineNotEnabled().evaluate(proposal, quant)
    assert EvidenceRequiredError.code == "evidence_required"
