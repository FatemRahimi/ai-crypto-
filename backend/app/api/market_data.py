"""Read-only market observations. These routes do not call the provider."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated, Literal, Protocol

from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict
from sqlalchemy.exc import SQLAlchemyError

from app.core.errors import error_body
from app.domains.market_data.identity import SUPPORTED_INTERVALS
from app.domains.market_data.persistence import CandleRow
from app.domains.market_data.quality import DataStatus
from app.domains.market_data.service import LatestView

IntervalName = Literal["1m", "5m", "15m", "1h", "4h", "1d"]
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
