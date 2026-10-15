"""Read verified candles, measure them, and store the evidence."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings
from app.core.database import create_db_engine
from app.domains.market_data.identity import BTC_USDT_SPOT, SUPPORTED_INTERVALS, MarketIdentity
from app.domains.market_data.quality import DataStatus, candle_freshness
from app.domains.market_intelligence.calculators import (
    EVIDENCE_TYPES,
    EvidenceDraft,
    evaluate,
    parameter_set,
)
from app.domains.market_intelligence.persistence import TechnicalEvidenceRow
from app.domains.market_intelligence.repository import EvidenceRepository

logger = logging.getLogger("app.market_intelligence")

MAX_CANDLE_LIMIT = 500
DEFAULT_CANDLE_LIMIT = 100
MAX_LOOKBACK = 20


@dataclass(frozen=True, slots=True)
class CalculationReport:
    inserted: int
    duplicates: int
    conflicts: int
    data_status: str
    evidence_id: int | None
    result: dict[str, object]


@dataclass(frozen=True, slots=True)
class EvidenceView:
    evidence_id: int
    evidence_type: str
    canonical_symbol: str
    provider: str
    provider_symbol: str
    market_type: str
    interval: str
    observation_time: datetime
    calculated_at: datetime
    calculator_name: str
    calculator_version: str
    parameters: dict[str, object]
    input_open_start: datetime
    input_open_end: datetime
    input_candle_count: int
    input_candle_ids: list[int]
    result: dict[str, object]
    data_status: str
    freshness: str


class TechnicalEvidenceService:
    def __init__(
        self,
        sessions: sessionmaker[Session],
        identity: MarketIdentity = BTC_USDT_SPOT,
    ) -> None:
        self._sessions = sessions
        self.identity = identity

    @classmethod
    def from_settings(cls, settings: Settings) -> TechnicalEvidenceService:
        engine = create_db_engine(settings)
        sessions = sessionmaker(bind=engine, expire_on_commit=False)
        return cls(sessions)

    def calculate(
        self,
        evidence_type: str,
        interval: str,
        *,
        start: datetime | None = None,
        end: datetime | None = None,
        candle_limit: int = DEFAULT_CANDLE_LIMIT,
        left: int = 2,
        right: int = 2,
        now: datetime | None = None,
    ) -> CalculationReport:
        self._validate(evidence_type, interval, candle_limit, left, right, start, end)
        moment = now or datetime.now(UTC)
        parameters = parameter_set(
            evidence_type,
            candle_limit=candle_limit,
            left=left,
            right=right,
            start=start,
            end=end,
        )
        with self._sessions() as session:
            repository = EvidenceRepository(session)
            market_id, candles = repository.load_candles(
                self.identity,
                interval,
                start,
                end,
                candle_limit,
            )
            draft = evaluate(evidence_type, candles, interval, parameters)
            if draft.observation_time is None or market_id is None:
                self._log_draft(draft)
                return _report(draft, inserted=0, duplicates=0, conflicts=0, evidence_id=None)
            outcome = repository.save(market_id, interval, draft, moment, moment)
            session.commit()
        self._log_draft(draft, outcome=outcome.outcome)
        return _report(
            draft,
            inserted=1 if outcome.outcome == "inserted" else 0,
            duplicates=1 if outcome.outcome == "duplicate" else 0,
            conflicts=1 if outcome.outcome == "conflict" else 0,
            evidence_id=outcome.row_id,
        )

    def latest(
        self,
        evidence_type: str,
        interval: str,
        *,
        now: datetime | None = None,
    ) -> EvidenceView | None:
        moment = now or datetime.now(UTC)
        with self._sessions() as session:
            row = EvidenceRepository(session).latest(self.identity, interval, evidence_type)
            if row is None:
                return None
            return _view(row, self.identity, moment)

    def recent(
        self,
        *,
        interval: str | None = None,
        evidence_type: str | None = None,
        limit: int = 20,
        now: datetime | None = None,
    ) -> list[EvidenceView]:
        moment = now or datetime.now(UTC)
        with self._sessions() as session:
            rows = EvidenceRepository(session).recent(
                self.identity,
                interval,
                evidence_type,
                limit,
            )
            return [_view(row, self.identity, moment) for row in rows]

    def _validate(
        self,
        evidence_type: str,
        interval: str,
        candle_limit: int,
        left: int,
        right: int,
        start: datetime | None,
        end: datetime | None,
    ) -> None:
        if evidence_type not in EVIDENCE_TYPES:
            raise ValueError("unsupported evidence type")
        if interval not in SUPPORTED_INTERVALS:
            raise ValueError("unsupported interval")
        if candle_limit < 1 or candle_limit > MAX_CANDLE_LIMIT:
            raise ValueError("candle limit is outside 1..500")
        if left < 1 or right < 1 or left > MAX_LOOKBACK or right > MAX_LOOKBACK:
            raise ValueError("lookback is outside 1..20")
        if start is not None and start.utcoffset() is None:
            raise ValueError("start must be timezone-aware")
        if end is not None and end.utcoffset() is None:
            raise ValueError("end must be timezone-aware")
        if start is not None and end is not None and start > end:
            raise ValueError("start is after end")

    def _log_draft(self, draft: EvidenceDraft, *, outcome: str | None = None) -> None:
        if draft.data_status.value == "GAP_DETECTED":
            logger.info(
                "technical_evidence_gap provider=%s type=%s",
                self.identity.provider,
                draft.evidence_type,
            )
        elif draft.data_status.value == "INSUFFICIENT":
            logger.info(
                "technical_evidence_insufficient provider=%s type=%s",
                self.identity.provider,
                draft.evidence_type,
            )
        elif outcome == "conflict":
            logger.info(
                "technical_evidence_conflict provider=%s type=%s",
                self.identity.provider,
                draft.evidence_type,
            )
        else:
            logger.info(
                "technical_evidence_calculated provider=%s type=%s status=%s",
                self.identity.provider,
                draft.evidence_type,
                draft.data_status.value,
            )


def evidence_freshness(
    data_status: str,
    observation_time: datetime,
    interval: str,
    now: datetime,
) -> str:
    if data_status == "GAP_DETECTED":
        return "gap"
    if data_status == "INSUFFICIENT":
        return "insufficient"
    if data_status == "INVALID":
        return "invalid"
    fresh = candle_freshness(interval, observation_time, now)
    if fresh is DataStatus.STALE:
        return "stale"
    if fresh is DataStatus.VALID:
        return "fresh"
    return "invalid"


def _report(
    draft: EvidenceDraft,
    *,
    inserted: int,
    duplicates: int,
    conflicts: int,
    evidence_id: int | None,
) -> CalculationReport:
    return CalculationReport(
        inserted=inserted,
        duplicates=duplicates,
        conflicts=conflicts,
        data_status=draft.data_status.value,
        evidence_id=evidence_id,
        result=draft.result,
    )


def _view(row: TechnicalEvidenceRow, identity: MarketIdentity, now: datetime) -> EvidenceView:
    parameters = json.loads(row.parameters_json)
    result = json.loads(row.result_json)
    if not isinstance(parameters, dict) or not isinstance(result, dict):
        raise ValueError("stored evidence payload is not an object")
    candle_ids = json.loads(row.input_candle_ids_json)
    if not isinstance(candle_ids, list):
        raise ValueError("stored candle ids are not a list")
    return EvidenceView(
        evidence_id=row.id,
        evidence_type=row.evidence_type,
        canonical_symbol=identity.canonical_symbol,
        provider=identity.provider,
        provider_symbol=identity.provider_symbol,
        market_type=identity.market_type,
        interval=row.interval,
        observation_time=row.observation_time,
        calculated_at=row.calculated_at,
        calculator_name=row.calculator_name,
        calculator_version=row.calculator_version,
        parameters=parameters,
        input_open_start=row.input_open_start,
        input_open_end=row.input_open_end,
        input_candle_count=row.input_candle_count,
        input_candle_ids=[int(item) for item in candle_ids],
        result=result,
        data_status=row.data_status,
        freshness=evidence_freshness(row.data_status, row.observation_time, row.interval, now),
    )
