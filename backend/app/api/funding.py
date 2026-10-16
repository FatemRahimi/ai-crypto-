"""Read stored USD-M funding observations. This route does not call Binance."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Literal, Protocol

from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict
from sqlalchemy.exc import SQLAlchemyError

from app.core.constitution import EXECUTION_ENABLED
from app.core.errors import error_body
from app.domains.market_data.funding_service import UNKNOWN_LIMITATION
from app.domains.market_data.identity import BTC_USDT_USD_M_PERPETUAL
from app.domains.market_data.persistence import FundingObservationRow, FundingWindowRow

CANONICAL_SYMBOL = BTC_USDT_USD_M_PERPETUAL.canonical_symbol
EMPTY_DETAIL = "No stored funding evidence is available."
INSTRUMENT_LABEL = "Binance USD-M BTCUSDT perpetual"
CompletenessName = Literal["COMPLETENESS_UNKNOWN", "EMPTY", "INVALID"]
RateTypeName = Literal["Regular", "Special"]


class FundingReader(Protocol):
    def read(
        self,
        *,
        start: datetime | None,
        end: datetime | None,
        limit: int,
    ) -> tuple[list[FundingObservationRow], FundingWindowRow | None]:
        """Return stored observations and the latest matching window, if any."""


class FundingRowResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    funding_time: datetime
    funding_rate: str
    rate_type: RateTypeName
    content_fingerprint: str
    endpoint: str
    normalization_version: str
    ingested_at: datetime


class FundingPageResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    canonical_symbol: str
    provider: str
    provider_symbol: str
    market_type: str
    instrument_label: str
    empty: bool
    detail: str
    completeness: CompletenessName | None
    limitation: str | None
    requested_start: datetime | None
    requested_end: datetime | None
    input_fingerprint: str | None
    normalization_version: str | None
    endpoint: str | None
    execution_enabled: Literal[False]
    records: list[FundingRowResponse]


def register_funding_routes(app: FastAPI, reader: FundingReader) -> None:
    @app.get("/api/v1/funding", response_model=FundingPageResponse)
    def funding_observations(
        symbol: Annotated[str, Query()] = CANONICAL_SYMBOL,
        start: Annotated[datetime | None, Query()] = None,
        end: Annotated[datetime | None, Query()] = None,
        limit: Annotated[int, Query(ge=1, le=500)] = 20,
    ) -> FundingPageResponse | JSONResponse:
        if symbol != CANONICAL_SYMBOL:
            return JSONResponse(
                status_code=404,
                content=error_body("unknown_symbol", "funding is only stored for BTCUSDT-PERP"),
            )
        if start is not None and end is not None and start > end:
            return JSONResponse(
                status_code=422,
                content=error_body("validation_error", "start must be at or before end"),
            )
        try:
            rows, window = reader.read(start=start, end=end, limit=limit)
        except SQLAlchemyError:
            return JSONResponse(
                status_code=503,
                content=error_body("store_unavailable", "funding evidence could not be read"),
            )
        records = [_row(row) for row in rows]
        completeness = _completeness(window)
        limitation = UNKNOWN_LIMITATION if records else None
        detail = EMPTY_DETAIL if not records else UNKNOWN_LIMITATION
        return FundingPageResponse(
            canonical_symbol=CANONICAL_SYMBOL,
            provider=BTC_USDT_USD_M_PERPETUAL.provider,
            provider_symbol=BTC_USDT_USD_M_PERPETUAL.provider_symbol,
            market_type=BTC_USDT_USD_M_PERPETUAL.market_type,
            instrument_label=INSTRUMENT_LABEL,
            empty=not records,
            detail=detail,
            completeness=completeness,
            limitation=limitation,
            requested_start=_utc(None if window is None else window.requested_start),
            requested_end=_utc(None if window is None else window.requested_end),
            input_fingerprint=None if window is None else window.input_fingerprint,
            normalization_version=None if window is None else window.normalization_version,
            endpoint=None if window is None else window.endpoint,
            execution_enabled=EXECUTION_ENABLED,
            records=records,
        )


def _row(row: FundingObservationRow) -> FundingRowResponse:
    rate_type: RateTypeName = "Regular" if row.rate_type == "Regular" else "Special"
    return FundingRowResponse(
        funding_time=as_utc(row.funding_time),
        funding_rate=format(row.funding_rate, "f"),
        rate_type=rate_type,
        content_fingerprint=row.content_fingerprint,
        endpoint=row.endpoint,
        normalization_version=row.normalization_version,
        ingested_at=as_utc(row.ingested_at),
    )


def _completeness(window: FundingWindowRow | None) -> CompletenessName | None:
    if window is None:
        return None
    allowed: dict[str, CompletenessName] = {
        "COMPLETENESS_UNKNOWN": "COMPLETENESS_UNKNOWN",
        "EMPTY": "EMPTY",
        "INVALID": "INVALID",
    }
    return allowed.get(window.completeness)


def as_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamp must be timezone-aware")
    return value.astimezone(UTC)


def _utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return as_utc(value)
