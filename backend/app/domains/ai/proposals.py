from __future__ import annotations

from uuid import UUID

from app.domains.pipeline import Direction, EvidenceRef, TradeProposal


def draft_trade_proposal(
    *,
    proposal_id: UUID,
    instrument: str,
    direction: Direction,
    thesis: str,
    evidence_refs: list[EvidenceRef] | None = None,
) -> TradeProposal:
    """Build the only AI output this phase recognizes.

    The returned value is not validated by quant, approved by risk, or sent.
    """

    return TradeProposal(
        proposal_id=proposal_id,
        instrument=instrument,
        direction=direction,
        thesis=thesis,
        evidence_refs=evidence_refs or [],
    )
