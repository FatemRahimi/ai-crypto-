"""Read stored technical evidence. These routes do not calculate or fetch candles."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Annotated, Literal, Protocol, cast

from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, JsonValue
from sqlalchemy.exc import SQLAlchemyError

from app.core.constitution import EXECUTION_ENABLED
from app.core.errors import error_body
from app.domains.market_data.identity import SUPPORTED_INTERVALS
from app.domains.market_intelligence.calculators import EVIDENCE_TYPES
from app.domains.market_intelligence.service import EvidenceView

IntervalName = Literal["1m", "5m", "15m", "1h", "4h", "1d"]
EvidenceTypeName = Literal[
    "swing_structure",
    "support_resistance",
    "range_statistics",
    "candle_vwap",
]
CANONICAL_SYMBOL = "BTC/USDT"


class EvidenceReader(Protocol):
    def latest(
        self,
        evidence_type: str,
        interval: str,
        *,
        now: datetime | None = None,
    ) -> EvidenceView | None:
        """Return the newest stored evidence row for one type and interval."""

    def recent(
        self,
        *,
        interval: str | None = None,
        evidence_type: str | None = None,
        limit: int = 20,
        now: datetime | None = None,
    ) -> list[EvidenceView]:
        """Return stored evidence, newest observation first."""


class EvidenceResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

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
    parameters: dict[str, JsonValue]
    input_open_start: datetime
    input_open_end: datetime
    input_candle_count: int
    input_candle_ids: list[int]
    input_fingerprint: str
    result: dict[str, JsonValue]
    data_status: Literal["VALID", "GAP_DETECTED", "INSUFFICIENT", "INVALID"]
    freshness: Literal["fresh", "stale", "gap", "insufficient", "invalid"]


class EvidencePageResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    canonical_symbol: str
    records: list[EvidenceResponse]
    empty: bool
    detail: str
    execution_enabled: Literal[False]


class EvidenceLatestResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    canonical_symbol: str
    record: EvidenceResponse | None
    empty: bool
    detail: str
    execution_enabled: Literal[False]


def register_evidence_routes(app: FastAPI, reader: EvidenceReader) -> None:
    @app.get("/api/v1/technical-evidence", response_model=EvidencePageResponse)
    def technical_evidence(
        symbol: Annotated[str, Query()] = CANONICAL_SYMBOL,
        interval: Annotated[IntervalName | None, Query()] = None,
        evidence_type: Annotated[EvidenceTypeName | None, Query()] = None,
        limit: Annotated[int, Query(ge=1, le=100)] = 20,
    ) -> EvidencePageResponse | JSONResponse:
        if symbol != CANONICAL_SYMBOL:
            return _unknown_symbol()
        try:
            rows = reader.recent(interval=interval, evidence_type=evidence_type, limit=limit)
        except SQLAlchemyError:
            return _store_unavailable()
        records = [_record(row) for row in rows]
        return EvidencePageResponse(
            canonical_symbol=CANONICAL_SYMBOL,
            records=records,
            empty=not records,
            detail=(
                "No verified technical evidence" if not records else "Verified technical evidence"
            ),
            execution_enabled=EXECUTION_ENABLED,
        )

    @app.get("/api/v1/technical-evidence/latest", response_model=EvidenceLatestResponse)
    def latest_technical_evidence(
        symbol: Annotated[str, Query()] = CANONICAL_SYMBOL,
        interval: Annotated[IntervalName, Query()] = "1m",
        evidence_type: Annotated[EvidenceTypeName, Query()] = "swing_structure",
    ) -> EvidenceLatestResponse | JSONResponse:
        if symbol != CANONICAL_SYMBOL:
            return _unknown_symbol()
        if interval not in SUPPORTED_INTERVALS or evidence_type not in EVIDENCE_TYPES:
            return JSONResponse(
                status_code=422,
                content=error_body("validation_error", "unsupported evidence query"),
            )
        try:
            row = reader.latest(evidence_type, interval)
        except SQLAlchemyError:
            return _store_unavailable()
        if row is None:
            return EvidenceLatestResponse(
                canonical_symbol=CANONICAL_SYMBOL,
                record=None,
                empty=True,
                detail="No verified technical evidence",
                execution_enabled=EXECUTION_ENABLED,
            )
        return EvidenceLatestResponse(
            canonical_symbol=CANONICAL_SYMBOL,
            record=_record(row),
            empty=False,
            detail="Verified technical evidence",
            execution_enabled=EXECUTION_ENABLED,
        )


def _record(row: EvidenceView) -> EvidenceResponse:
    return EvidenceResponse(
        evidence_id=row.evidence_id,
        evidence_type=row.evidence_type,
        canonical_symbol=row.canonical_symbol,
        provider=row.provider,
        provider_symbol=row.provider_symbol,
        market_type=row.market_type,
        interval=row.interval,
        observation_time=as_utc(row.observation_time),
        calculated_at=as_utc(row.calculated_at),
        calculator_name=row.calculator_name,
        calculator_version=row.calculator_version,
        parameters=_json_object(row.parameters),
        input_open_start=as_utc(row.input_open_start),
        input_open_end=as_utc(row.input_open_end),
        input_candle_count=row.input_candle_count,
        input_candle_ids=row.input_candle_ids,
        input_fingerprint=row.input_fingerprint,
        result=_json_object(row.result),
        data_status=_status(row.data_status),
        freshness=_freshness(row.freshness),
    )


def _status(
    value: str,
) -> Literal["VALID", "GAP_DETECTED", "INSUFFICIENT", "INVALID"]:
    if value == "VALID":
        return "VALID"
    if value == "GAP_DETECTED":
        return "GAP_DETECTED"
    if value == "INSUFFICIENT":
        return "INSUFFICIENT"
    if value == "INVALID":
        return "INVALID"
    raise ValueError("unknown evidence status")


def _freshness(
    value: str,
) -> Literal["fresh", "stale", "gap", "insufficient", "invalid"]:
    if value == "fresh":
        return "fresh"
    if value == "stale":
        return "stale"
    if value == "gap":
        return "gap"
    if value == "insufficient":
        return "insufficient"
    if value == "invalid":
        return "invalid"
    raise ValueError("unknown evidence freshness")


def _json_object(value: dict[str, object]) -> dict[str, JsonValue]:
    parsed = json.loads(json.dumps(value))
    if not isinstance(parsed, dict):
        raise ValueError("evidence payload is not an object")
    return cast(dict[str, JsonValue], parsed)


def as_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamp must be timezone-aware")
    return value.astimezone(UTC)


def _unknown_symbol() -> JSONResponse:
    return JSONResponse(
        status_code=404,
        content=error_body("unknown_market", "Only BTC/USDT spot is available in this phase."),
    )


def _store_unavailable() -> JSONResponse:
    return JSONResponse(
        status_code=503,
        content=error_body("database_unavailable", "Technical evidence store is unavailable."),
    )
