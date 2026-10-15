"""Persistence for technical evidence. Candle rows are read and never rewritten."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.domains.market_data.identity import MarketIdentity
from app.domains.market_data.persistence import CandleRow, MarketRow
from app.domains.market_intelligence.calculators import EvidenceDraft, InputCandle
from app.domains.market_intelligence.persistence import TechnicalEvidenceRow


@dataclass(frozen=True, slots=True)
class SaveOutcome:
    outcome: Literal["inserted", "duplicate", "conflict"]
    row_id: int


class EvidenceRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def load_candles(
        self,
        identity: MarketIdentity,
        interval: str,
        start: datetime | None,
        end: datetime | None,
        limit: int,
    ) -> tuple[int | None, list[InputCandle]]:
        market_id = self._market_id(identity)
        if market_id is None:
            return None, []
        query = select(CandleRow).where(
            CandleRow.market_id == market_id,
            CandleRow.interval == interval,
            CandleRow.data_status == "VALID",
        )
        if start is not None:
            query = query.where(CandleRow.open_time >= start)
        if end is not None:
            query = query.where(CandleRow.open_time <= end)
        newest = list(
            self._session.scalars(query.order_by(CandleRow.open_time.desc()).limit(limit))
        )
        candles = [
            InputCandle(
                candle_id=row.id,
                open_time=row.open_time,
                close_time=row.close_time,
                open=row.open,
                high=row.high,
                low=row.low,
                close=row.close,
                volume=row.volume,
            )
            for row in reversed(newest)
        ]
        return market_id, candles

    def save(
        self,
        market_id: int,
        interval: str,
        draft: EvidenceDraft,
        calculated_at: datetime,
        created_at: datetime,
    ) -> SaveOutcome:
        if (
            draft.observation_time is None
            or draft.input_open_start is None
            or draft.input_open_end is None
        ):
            raise ValueError("evidence without an observation is not stored")
        parameters = canonical_json(draft.parameters)
        result = canonical_json(draft.result)
        digest = hashlib.sha256(parameters.encode("utf-8")).hexdigest()
        existing = self._existing(
            market_id,
            draft.evidence_type,
            interval,
            draft.observation_time,
            draft.calculator_name,
            draft.calculator_version,
            digest,
        )
        if existing is not None:
            return self._same_or_conflict(existing, result, draft.data_status.value)
        row = TechnicalEvidenceRow(
            market_id=market_id,
            evidence_type=draft.evidence_type,
            interval=interval,
            observation_time=draft.observation_time,
            calculated_at=calculated_at,
            calculator_name=draft.calculator_name,
            calculator_version=draft.calculator_version,
            parameters_json=parameters,
            parameters_hash=digest,
            input_open_start=draft.input_open_start,
            input_open_end=draft.input_open_end,
            input_candle_count=len(draft.input_candle_ids),
            input_candle_ids_json=json.dumps(list(draft.input_candle_ids)),
            result_json=result,
            data_status=draft.data_status.value,
            created_at=created_at,
        )
        try:
            with self._session.begin_nested():
                self._session.add(row)
                self._session.flush()
        except IntegrityError:
            raced = self._existing(
                market_id,
                draft.evidence_type,
                interval,
                draft.observation_time,
                draft.calculator_name,
                draft.calculator_version,
                digest,
            )
            if raced is None:
                raise
            return self._same_or_conflict(raced, result, draft.data_status.value)
        return SaveOutcome("inserted", row.id)

    def latest(
        self,
        identity: MarketIdentity,
        interval: str,
        evidence_type: str,
    ) -> TechnicalEvidenceRow | None:
        market_id = self._market_id(identity)
        if market_id is None:
            return None
        return self._session.scalar(
            select(TechnicalEvidenceRow)
            .where(
                TechnicalEvidenceRow.market_id == market_id,
                TechnicalEvidenceRow.interval == interval,
                TechnicalEvidenceRow.evidence_type == evidence_type,
            )
            .order_by(TechnicalEvidenceRow.observation_time.desc(), TechnicalEvidenceRow.id.desc())
            .limit(1)
        )

    def recent(
        self,
        identity: MarketIdentity,
        interval: str | None,
        evidence_type: str | None,
        limit: int,
    ) -> list[TechnicalEvidenceRow]:
        market_id = self._market_id(identity)
        if market_id is None:
            return []
        query = select(TechnicalEvidenceRow).where(TechnicalEvidenceRow.market_id == market_id)
        if interval is not None:
            query = query.where(TechnicalEvidenceRow.interval == interval)
        if evidence_type is not None:
            query = query.where(TechnicalEvidenceRow.evidence_type == evidence_type)
        query = query.order_by(
            TechnicalEvidenceRow.observation_time.desc(),
            TechnicalEvidenceRow.id.desc(),
        ).limit(limit)
        return list(self._session.scalars(query))

    def count_evidence(self, identity: MarketIdentity) -> int:
        market_id = self._market_id(identity)
        if market_id is None:
            return 0
        rows = self._session.scalars(
            select(TechnicalEvidenceRow.id).where(TechnicalEvidenceRow.market_id == market_id)
        )
        return len(list(rows))

    def _existing(
        self,
        market_id: int,
        evidence_type: str,
        interval: str,
        observation_time: datetime,
        calculator_name: str,
        calculator_version: str,
        parameters_hash: str,
    ) -> TechnicalEvidenceRow | None:
        return self._session.scalar(
            select(TechnicalEvidenceRow).where(
                TechnicalEvidenceRow.market_id == market_id,
                TechnicalEvidenceRow.evidence_type == evidence_type,
                TechnicalEvidenceRow.interval == interval,
                TechnicalEvidenceRow.observation_time == observation_time,
                TechnicalEvidenceRow.calculator_name == calculator_name,
                TechnicalEvidenceRow.calculator_version == calculator_version,
                TechnicalEvidenceRow.parameters_hash == parameters_hash,
            )
        )

    def _same_or_conflict(
        self,
        existing: TechnicalEvidenceRow,
        result: str,
        status: str,
    ) -> SaveOutcome:
        if existing.result_json == result and existing.data_status == status:
            return SaveOutcome("duplicate", existing.id)
        return SaveOutcome("conflict", existing.id)

    def _market_id(self, identity: MarketIdentity) -> int | None:
        return self._session.scalar(
            select(MarketRow.id).where(
                MarketRow.provider == identity.provider,
                MarketRow.provider_symbol == identity.provider_symbol,
                MarketRow.market_type == identity.market_type,
            )
        )


def canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
