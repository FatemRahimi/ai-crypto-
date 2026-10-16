"""Read-only market observations. These routes do not call the provider."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated, Literal, Protocol, cast

from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, JsonValue
from sqlalchemy.exc import SQLAlchemyError

from app.core.errors import error_body
from app.domains.market_data.identity import SUPPORTED_INTERVALS
from app.domains.market_data.persistence import (
    AggregateTradeRow,
    AggregateTradeWindowRow,
    CandleRow,
)
from app.domains.market_data.quality import DataStatus
from app.domains.market_data.service import LatestView

IntervalName = Literal["1m", "5m", "15m", "1h", "4h", "1d"]
CompletenessName = Literal[
    "COMPLETE",
    "GAP_DETECTED",
    "EMPTY",
    "INVALID",
    "COMPLETENESS_UNKNOWN",
]
CANONICAL_SYMBOL = "BTC/USDT"


class MarketReader(Protocol):
    def stored_candle_count(self) -> int:
        """Count stored valid candles for the phase market."""

    def candles(
        self,
        interval: str,
        *,
        start: datetime | None,
        end: datetime | None,
        limit: int,
    ) -> tuple[list[CandleRow], int]:
        """Return ascending candles and a gap count."""

    def latest(self, *, interval: str = "1m", now: datetime | None = None) -> LatestView:
        """Return the newest verified trade or closed candle."""

    def aggregate_trades(
        self,
        *,
        start: datetime | None,
        end: datetime | None,
        limit: int,
    ) -> list[AggregateTradeRow]:
        """Return stored aggregate trades. This does not call the provider."""

    def aggregate_trade_window(
        self,
        *,
        start: datetime | None,
        end: datetime | None,
    ) -> tuple[AggregateTradeWindowRow | None, int]:
        """Return the latest stored window report and the stored trade count."""


class MarketStatusResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: str
    canonical_symbol: str
    provider_symbol: str
    market_type: str
    quote_asset: str
    stored_candles: int
    freshness: Literal["fresh", "stale", "unavailable"]
    stream: Literal["disconnected"]
    execution_enabled: Literal[False]


class CandleResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: str
    canonical_symbol: str
    provider_symbol: str
    market_type: str
    interval: str
    open_time: datetime
    close_time: datetime
    open: str
    high: str
    low: str
    close: str
    volume: str
    quote_volume: str | None
    trade_count: int | None
    ingested_at: datetime
    data_status: Literal["VALID"]
    endpoint: str
    normalization_version: str


class CandlePageResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    canonical_symbol: str
    interval: str
    candles: list[CandleResponse]
    gap_count: int
    empty: bool


class AggregateTradeResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: str
    canonical_symbol: str
    provider_symbol: str
    market_type: str
    aggregate_trade_id: int
    price: str
    quantity: str
    event_time: datetime
    first_trade_id: int
    last_trade_id: int
    buyer_is_maker: bool
    ingested_at: datetime
    content_fingerprint: str
    endpoint: str
    normalization_version: str


class AggregateTradePageResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    canonical_symbol: str
    trades: list[AggregateTradeResponse]
    empty: bool


class AggregateWindowResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    canonical_symbol: str
    provider: str
    provider_symbol: str
    requested_start: datetime
    requested_end: datetime
    first_event_time: datetime | None
    last_event_time: datetime | None
    first_aggregate_id: int | None
    last_aggregate_id: int | None
    aggregate_trade_count: int
    underlying_first_trade_id: int | None
    underlying_last_trade_id: int | None
    inserted: int
    duplicates: int
    conflicts: int
    completeness: CompletenessName
    gap_details: dict[str, JsonValue]
    checked_at: datetime
    input_fingerprint: str
    endpoint: str
    normalization_version: str


class AggregateWindowPageResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    canonical_symbol: str
    empty: bool
    stored_count: int
    window: AggregateWindowResponse | None


class LatestResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    canonical_symbol: str
    provider_symbol: str
    provider: str
    market_type: str
    quote_asset: str
    price: str | None
    observation_time: datetime | None
    freshness: Literal["fresh", "stale", "unavailable"]
    endpoint: str | None
    normalization_version: str | None
    detail: str


def register_market_routes(app: FastAPI, reader: MarketReader) -> None:
    @app.get("/api/v1/market-data/status", response_model=MarketStatusResponse)
    def market_status() -> MarketStatusResponse | JSONResponse:
        try:
            latest = reader.latest()
            stored = reader.stored_candle_count()
        except SQLAlchemyError:
            return _store_unavailable()
        return MarketStatusResponse(
            provider=latest.provider,
            canonical_symbol=latest.canonical_symbol,
            provider_symbol=latest.provider_symbol,
            market_type=latest.market_type,
            quote_asset=latest.quote_asset,
            stored_candles=stored,
            freshness=_freshness(latest),
            stream="disconnected",
            execution_enabled=False,
        )

    @app.get("/api/v1/market-data/candles", response_model=CandlePageResponse)
    def market_candles(
        symbol: Annotated[str, Query()] = CANONICAL_SYMBOL,
        interval: Annotated[IntervalName, Query()] = "1m",
        start: Annotated[datetime | None, Query()] = None,
        end: Annotated[datetime | None, Query()] = None,
        limit: Annotated[int, Query(ge=1, le=500)] = 100,
    ) -> CandlePageResponse | JSONResponse:
        if symbol != CANONICAL_SYMBOL:
            return _unknown_symbol()
        if start is not None and end is not None and start > end:
            return JSONResponse(
                status_code=422,
                content=error_body("validation_error", "start must be at or before end"),
            )
        try:
            rows, gap_count = reader.candles(interval, start=start, end=end, limit=limit)
        except SQLAlchemyError:
            return _store_unavailable()
        except ValueError as exc:
            return JSONResponse(
                status_code=422,
                content=error_body("validation_error", str(exc)),
            )
        candles = [_candle_response(row) for row in rows]
        return CandlePageResponse(
            canonical_symbol=CANONICAL_SYMBOL,
            interval=interval,
            candles=candles,
            gap_count=gap_count,
            empty=not candles,
        )

    @app.get("/api/v1/market-data/latest", response_model=LatestResponse)
    def market_latest(
        symbol: Annotated[str, Query()] = CANONICAL_SYMBOL,
        interval: Annotated[IntervalName, Query()] = "1m",
    ) -> LatestResponse | JSONResponse:
        if symbol != CANONICAL_SYMBOL:
            return _unknown_symbol()
        if interval not in SUPPORTED_INTERVALS:
            return JSONResponse(
                status_code=422,
                content=error_body("validation_error", "unsupported interval"),
            )
        try:
            latest = reader.latest(interval=interval)
        except SQLAlchemyError:
            return _store_unavailable()
        return _latest_response(latest)

    @app.get(
        "/api/v1/market-data/aggregate-trades",
        response_model=AggregateTradePageResponse,
    )
    def aggregate_trades(
        symbol: Annotated[str, Query()] = CANONICAL_SYMBOL,
        start: Annotated[datetime | None, Query()] = None,
        end: Annotated[datetime | None, Query()] = None,
        limit: Annotated[int, Query(ge=1, le=500)] = 100,
    ) -> AggregateTradePageResponse | JSONResponse:
        if symbol != CANONICAL_SYMBOL:
            return _unknown_symbol()
        if start is not None and end is not None and start > end:
            return JSONResponse(
                status_code=422,
                content=error_body("validation_error", "start must be at or before end"),
            )
        try:
            rows = reader.aggregate_trades(start=start, end=end, limit=limit)
        except SQLAlchemyError:
            return _store_unavailable()
        return AggregateTradePageResponse(
            canonical_symbol=CANONICAL_SYMBOL,
            trades=[_aggregate_trade_response(row) for row in rows],
            empty=not rows,
        )

    @app.get(
        "/api/v1/market-data/aggregate-trade-windows",
        response_model=AggregateWindowPageResponse,
    )
    def aggregate_trade_windows(
        symbol: Annotated[str, Query()] = CANONICAL_SYMBOL,
        start: Annotated[datetime | None, Query()] = None,
        end: Annotated[datetime | None, Query()] = None,
    ) -> AggregateWindowPageResponse | JSONResponse:
        if symbol != CANONICAL_SYMBOL:
            return _unknown_symbol()
        try:
            window, stored_count = reader.aggregate_trade_window(start=start, end=end)
        except SQLAlchemyError:
            return _store_unavailable()
        return AggregateWindowPageResponse(
            canonical_symbol=CANONICAL_SYMBOL,
            empty=window is None and stored_count == 0,
            stored_count=stored_count,
            window=None if window is None else _aggregate_window_response(window),
        )


def _freshness(latest: LatestView) -> Literal["fresh", "stale", "unavailable"]:
    if latest.price is None:
        return "unavailable"
    if latest.freshness is DataStatus.STALE:
        return "stale"
    return "fresh"


def _latest_response(latest: LatestView) -> LatestResponse:
    return LatestResponse(
        canonical_symbol=latest.canonical_symbol,
        provider_symbol=latest.provider_symbol,
        provider=latest.provider,
        market_type=latest.market_type,
        quote_asset=latest.quote_asset,
        price=None if latest.price is None else _decimal_text(latest.price),
        observation_time=(
            None if latest.observation_time is None else as_utc(latest.observation_time)
        ),
        freshness=_freshness(latest),
        endpoint=latest.endpoint,
        normalization_version=latest.normalization_version,
        detail=latest.detail,
    )


def _candle_response(row: CandleRow) -> CandleResponse:
    return CandleResponse(
        provider=BTC_PROVIDER,
        canonical_symbol=CANONICAL_SYMBOL,
        provider_symbol="BTCUSDT",
        market_type="spot",
        interval=row.interval,
        open_time=as_utc(row.open_time),
        close_time=as_utc(row.close_time),
        open=_decimal_text(row.open),
        high=_decimal_text(row.high),
        low=_decimal_text(row.low),
        close=_decimal_text(row.close),
        volume=_decimal_text(row.volume),
        quote_volume=None if row.quote_volume is None else _decimal_text(row.quote_volume),
        trade_count=row.trade_count,
        ingested_at=as_utc(row.ingested_at),
        data_status="VALID",
        endpoint=row.endpoint,
        normalization_version=row.normalization_version,
    )


BTC_PROVIDER = "binance_spot"


def as_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamp must be timezone-aware")
    return value.astimezone(UTC)


def _decimal_text(value: Decimal) -> str:
    return format(value, "f")


def _aggregate_trade_response(row: AggregateTradeRow) -> AggregateTradeResponse:
    return AggregateTradeResponse(
        provider=BTC_PROVIDER,
        canonical_symbol=CANONICAL_SYMBOL,
        provider_symbol="BTCUSDT",
        market_type="spot",
        aggregate_trade_id=row.aggregate_trade_id,
        price=_decimal_text(row.price),
        quantity=_decimal_text(row.quantity),
        event_time=as_utc(row.event_time),
        first_trade_id=row.first_trade_id,
        last_trade_id=row.last_trade_id,
        buyer_is_maker=row.buyer_is_maker,
        ingested_at=as_utc(row.ingested_at),
        content_fingerprint=row.content_fingerprint,
        endpoint=row.endpoint,
        normalization_version=row.normalization_version,
    )


def _aggregate_window_response(row: AggregateTradeWindowRow) -> AggregateWindowResponse:
    return AggregateWindowResponse(
        canonical_symbol=CANONICAL_SYMBOL,
        provider=BTC_PROVIDER,
        provider_symbol="BTCUSDT",
        requested_start=as_utc(row.requested_start),
        requested_end=as_utc(row.requested_end),
        first_event_time=None if row.first_event_time is None else as_utc(row.first_event_time),
        last_event_time=None if row.last_event_time is None else as_utc(row.last_event_time),
        first_aggregate_id=row.first_aggregate_id,
        last_aggregate_id=row.last_aggregate_id,
        aggregate_trade_count=row.aggregate_trade_count,
        underlying_first_trade_id=row.underlying_first_trade_id,
        underlying_last_trade_id=row.underlying_last_trade_id,
        inserted=row.inserted,
        duplicates=row.duplicates,
        conflicts=row.conflicts,
        completeness=_completeness_name(row.completeness),
        gap_details=_json_object(_gap_details(row.gap_details_json)),
        checked_at=as_utc(row.checked_at),
        input_fingerprint=row.input_fingerprint,
        endpoint=row.endpoint,
        normalization_version=row.normalization_version,
    )


def _completeness_name(value: str) -> CompletenessName:
    if value == "COMPLETE":
        return "COMPLETE"
    if value == "GAP_DETECTED":
        return "GAP_DETECTED"
    if value == "EMPTY":
        return "EMPTY"
    if value == "INVALID":
        return "INVALID"
    if value == "COMPLETENESS_UNKNOWN":
        return "COMPLETENESS_UNKNOWN"
    raise ValueError("unknown completeness status")


def _gap_details(raw: str | None) -> dict[str, object]:
    if raw is None:
        return {}
    parsed = json.loads(raw)
    if not isinstance(parsed, dict):
        return {"reason": "unreadable_gap_details"}
    return {str(key): value for key, value in parsed.items()}


def _json_object(value: dict[str, object]) -> dict[str, JsonValue]:
    parsed = json.loads(json.dumps(value))
    if not isinstance(parsed, dict):
        return {}
    return cast(dict[str, JsonValue], parsed)


def _unknown_symbol() -> JSONResponse:
    return JSONResponse(
        status_code=404,
        content=error_body("unknown_market", "Only BTC/USDT spot is available in this phase."),
    )


def _store_unavailable() -> JSONResponse:
    return JSONResponse(
        status_code=503,
        content=error_body("database_unavailable", "Market data store is unavailable."),
    )
