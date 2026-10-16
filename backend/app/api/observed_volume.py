"""Read stored observed volume-at-price evidence. This route does not calculate."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated, Literal, Protocol

from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, JsonValue
from sqlalchemy.exc import SQLAlchemyError

from app.core.constitution import EXECUTION_ENABLED
from app.core.errors import error_body
from app.domains.market_intelligence.observed_volume_service import ObservedVolumeView

CANONICAL_SYMBOL = "BTC/USDT"
EMPTY_DETAIL = "No observed volume-at-price evidence has been calculated or stored."
PRESENT_DETAIL = (
    "Stored observed volume-at-price evidence. "
    "This is not proof of complete clock-window market coverage."
)


class ObservedVolumeReader(Protocol):
    def read(
        self,
        *,
        start: datetime | None = None,
        end: datetime | None = None,
        limit: int = 20,
    ) -> list[ObservedVolumeView]:
        """Return stored evidence. Newest calculated_at first."""


class GapResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    after_aggregate_id: int
    next_aggregate_id: int


class SourceDetailsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    attachment: Literal["identified", "not_identified"]
    coverage_claim: Literal["not_proven"]
    prior_report_completeness: str | None = None
    saw_full_page: bool | None = None
    observed_aggregate_id_discontinuity: bool | None = None
    page_was_short: bool | None = None
    page_count: int | None = None
    retrieval_stop: str | None = None
    reason: str | None = None
    read_cap: int | None = None
    rows_read_before_refusal: int | None = None
    gaps: list[GapResponse] | None = None


class BucketResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    price: str
    observed_base_volume: str
    aggregate_count: int
    derived_share_of_observed_base_volume: str


class ObservedVolumeResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evidence_id: int
    canonical_symbol: str
    provider: str
    provider_symbol: str
    market_type: str
    requested_start: datetime
    requested_end: datetime
    first_event_time: datetime | None
    last_event_time: datetime | None
    input_aggregate_count: int
    input_fingerprint: str
    parameters_hash: str
    parameters: dict[str, JsonValue]
    calculator_name: str
    calculator_version: str
    bucket_method: Literal["exact_price"]
    volume_definition: Literal["base_quantity"]
    poc_tie_break: Literal["lower_price"]
    source_completeness: Literal["COMPLETENESS_UNKNOWN", "INVALID"]
    source_limitation: str
    source_details: SourceDetailsResponse
    sufficiency: Literal["OBSERVED", "INSUFFICIENT", "INVALID"]
    total_observed_base_volume: str | None
    observed_poc_price: str | None
    poc_tie_count: int | None
    poc_tie: bool | None
    largest_aggregate_base_quantity: str | None
    derived_largest_aggregate_share_of_observed_base_volume: str | None
    calculated_at: datetime
    buckets: list[BucketResponse]


class ObservedVolumePageResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    canonical_symbol: str
    records: list[ObservedVolumeResponse]
    empty: bool
    detail: str
    execution_enabled: Literal[False]


def register_observed_volume_routes(app: FastAPI, reader: ObservedVolumeReader) -> None:
    @app.get("/api/v1/observed-volume", response_model=ObservedVolumePageResponse)
    def observed_volume(
        symbol: Annotated[str, Query()] = CANONICAL_SYMBOL,
        start: Annotated[datetime | None, Query()] = None,
        end: Annotated[datetime | None, Query()] = None,
        limit: Annotated[int, Query(ge=1, le=100)] = 20,
    ) -> ObservedVolumePageResponse | JSONResponse:
        if symbol != CANONICAL_SYMBOL:
            return _unknown_symbol()
        if (start is None) != (end is None):
            return _invalid("start and end must be supplied together")
        if start is not None and end is not None and start > end:
            return _invalid("start must be at or before end")
        try:
            rows = reader.read(start=start, end=end, limit=limit)
        except ValueError as exc:
            return _invalid(str(exc))
        except SQLAlchemyError:
            return _store_unavailable()
        records = [_record(row) for row in rows]
        return ObservedVolumePageResponse(
            canonical_symbol=CANONICAL_SYMBOL,
            records=records,
            empty=not records,
            detail=EMPTY_DETAIL if not records else PRESENT_DETAIL,
            execution_enabled=EXECUTION_ENABLED,
        )


def _record(row: ObservedVolumeView) -> ObservedVolumeResponse:
    return ObservedVolumeResponse(
        evidence_id=row.evidence_id,
        canonical_symbol=row.canonical_symbol,
        provider=row.provider,
        provider_symbol=row.provider_symbol,
        market_type=row.market_type,
        requested_start=as_utc(row.requested_start),
        requested_end=as_utc(row.requested_end),
        first_event_time=_utc(row.first_event_time),
        last_event_time=_utc(row.last_event_time),
        input_aggregate_count=row.input_aggregate_count,
        input_fingerprint=row.input_fingerprint,
        parameters_hash=row.parameters_hash,
        parameters=_json_object(row.parameters),
        calculator_name=row.calculator_name,
        calculator_version=row.calculator_version,
        bucket_method="exact_price",
        volume_definition="base_quantity",
        poc_tie_break="lower_price",
        source_completeness=_completeness(row.source_completeness),
        source_limitation=row.source_limitation,
        source_details=SourceDetailsResponse.model_validate(row.source_details),
        sufficiency=_sufficiency(row.sufficiency),
        total_observed_base_volume=_money(row.total_observed_base_volume),
        observed_poc_price=_money(row.observed_poc_price),
        poc_tie_count=row.poc_tie_count,
        poc_tie=row.poc_tie,
        largest_aggregate_base_quantity=_money(row.largest_aggregate_base_quantity),
        derived_largest_aggregate_share_of_observed_base_volume=_money(row.derived_largest_share),
        calculated_at=as_utc(row.calculated_at),
        buckets=[
            BucketResponse(
                price=_required_money(bucket.price),
                observed_base_volume=_required_money(bucket.observed_base_volume),
                aggregate_count=bucket.aggregate_count,
                derived_share_of_observed_base_volume=_required_money(bucket.derived_share),
            )
            for bucket in row.buckets
        ],
    )


def as_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamp must be timezone-aware")
    return value.astimezone(UTC)


def _utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return as_utc(value)


def _money(value: Decimal | None) -> str | None:
    if value is None:
        return None
    return format(value, "f")


def _required_money(value: Decimal) -> str:
    return format(value, "f")


def _json_object(value: dict[str, object]) -> dict[str, JsonValue]:
    parsed: dict[str, JsonValue] = {}
    for key, item in value.items():
        if isinstance(item, str | int | bool) or item is None:
            parsed[key] = item
    return parsed


def _completeness(value: str) -> Literal["COMPLETENESS_UNKNOWN", "INVALID"]:
    if value == "INVALID":
        return "INVALID"
    if value == "COMPLETENESS_UNKNOWN":
        return "COMPLETENESS_UNKNOWN"
    raise ValueError("unsupported source completeness")


def _sufficiency(value: str) -> Literal["OBSERVED", "INSUFFICIENT", "INVALID"]:
    if value == "OBSERVED":
        return "OBSERVED"
    if value == "INSUFFICIENT":
        return "INSUFFICIENT"
    if value == "INVALID":
        return "INVALID"
    raise ValueError("unsupported sufficiency")


def _invalid(message: str) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content=error_body("validation_error", message),
    )


def _unknown_symbol() -> JSONResponse:
    return JSONResponse(
        status_code=404,
        content=error_body("unknown_market", "Only BTC/USDT spot is available in this phase."),
    )


def _store_unavailable() -> JSONResponse:
    return JSONResponse(
        status_code=503,
        content=error_body("database_unavailable", "Observed volume store is unavailable."),
    )
