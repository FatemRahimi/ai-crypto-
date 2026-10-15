"""Ingestion and queries. Callers do not touch provider payloads."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings
from app.core.database import create_db_engine
from app.domains.market_data.identity import BTC_USDT_SPOT, SUPPORTED_INTERVALS, MarketIdentity
from app.domains.market_data.normalize import normalize_book, normalize_kline, normalize_trade
from app.domains.market_data.persistence import CandleRow, TradeRow
from app.domains.market_data.providers.base import MarketDataProvider
from app.domains.market_data.providers.binance_spot import BinanceSpotProvider
from app.domains.market_data.quality import (
    DataStatus,
    Rejection,
    candle_freshness,
    detect_candle_gaps,
    trade_freshness,
)
from app.domains.market_data.records import CanonicalCandle
from app.domains.market_data.repository import MarketRepository, WriteCounts

logger = logging.getLogger("app.market_data.service")

MAX_CANDLES_PER_RUN = 5000
DEFAULT_MAX_CANDLES = 1000
TRADE_FRESH_FOR = timedelta(minutes=2)


@dataclass(frozen=True, slots=True)
class IngestReport:
    inserted: int
    duplicates: int
    rejected: int
    gaps: int


@dataclass(frozen=True, slots=True)
class LatestView:
    canonical_symbol: str
    provider_symbol: str
    provider: str
    market_type: str
    quote_asset: str
    price: Decimal | None
    observation_time: datetime | None
    freshness: DataStatus
    endpoint: str | None
    normalization_version: str | None
    detail: str


class MarketDataService:
    def __init__(
        self,
        sessions: sessionmaker[Session],
        provider: MarketDataProvider,
        identity: MarketIdentity = BTC_USDT_SPOT,
    ) -> None:
        self._sessions = sessions
        self._provider = provider
        self.identity = identity

    @classmethod
    def from_settings(cls, settings: Settings) -> MarketDataService:
        engine = create_db_engine(settings)
        sessions = sessionmaker(bind=engine, expire_on_commit=False)
        provider = BinanceSpotProvider(settings.market_data_base_url)
        return cls(sessions, provider)

    def ingest_candles(
        self,
        interval: str,
        *,
        start: datetime | None = None,
        end: datetime | None = None,
        limit: int = 5,
        max_candles: int = DEFAULT_MAX_CANDLES,
        now: datetime | None = None,
    ) -> IngestReport:
        self._require_interval(interval)
        bounded = min(max_candles, MAX_CANDLES_PER_RUN)
        self._refuse_unbounded_range(interval, start, end, bounded)
        moment = now or datetime.now(UTC)
        raw_rows = self._provider.fetch_klines(
            provider_symbol=self.identity.provider_symbol,
            interval=interval,
            start=start,
            end=end,
            limit=limit,
            max_candles=bounded,
        )
        accepted: list[CanonicalCandle] = []
        rejected = 0
        for row in raw_rows:
            normalized = normalize_kline(row, self.identity, interval, moment, now=moment)
            if isinstance(normalized, Rejection):
                rejected += 1
                logger.info(
                    "market_data_validation_failed provider=%s kind=candle reason=%s",
                    self.identity.provider,
                    normalized.reason,
                )
                continue
            accepted.append(normalized)
        retained, batch_duplicates, conflicts = _partition_valid_candles(accepted)
        rejected += conflicts
        gaps = detect_candle_gaps(interval, [item.open_time for item in retained])
        if gaps:
            logger.info(
                "market_data_gap_detected provider=%s interval=%s gaps=%s",
                self.identity.provider,
                interval,
                len(gaps),
            )
        with self._sessions() as session:
            repository = MarketRepository(session)
            market_id = repository.ensure_market(self.identity)
            counts = repository.insert_candles(market_id, retained)
            session.commit()
        return IngestReport(
            inserted=counts.inserted,
            duplicates=counts.duplicates + batch_duplicates,
            rejected=rejected,
            gaps=len(gaps),
        )

    def ingest_recent_trades(self, *, limit: int = 5, now: datetime | None = None) -> IngestReport:
        moment = now or datetime.now(UTC)
        raw_rows = self._provider.fetch_recent_trades(
            provider_symbol=self.identity.provider_symbol,
            limit=limit,
        )
        trades = []
        rejected = 0
        for row in raw_rows:
            normalized = normalize_trade(row, self.identity, moment)
            if isinstance(normalized, Rejection):
                rejected += 1
                logger.info(
                    "market_data_validation_failed provider=%s kind=trade reason=%s",
                    self.identity.provider,
                    normalized.reason,
                )
                continue
            trades.append(normalized)
        with self._sessions() as session:
            repository = MarketRepository(session)
            market_id = repository.ensure_market(self.identity)
            counts = repository.insert_trades(market_id, trades)
            session.commit()
        return IngestReport(
            inserted=counts.inserted,
            duplicates=counts.duplicates,
            rejected=rejected,
            gaps=0,
        )

    def ingest_book(self, *, now: datetime | None = None) -> IngestReport:
        moment = now or datetime.now(UTC)
        raw = self._provider.fetch_book_ticker(provider_symbol=self.identity.provider_symbol)
        normalized = normalize_book(raw, self.identity, moment)
        if isinstance(normalized, Rejection):
            logger.info(
                "market_data_validation_failed provider=%s kind=book reason=%s",
                self.identity.provider,
                normalized.reason,
            )
            return IngestReport(inserted=0, duplicates=0, rejected=1, gaps=0)
        with self._sessions() as session:
            repository = MarketRepository(session)
            market_id = repository.ensure_market(self.identity)
            counts = repository.insert_book_if_changed(market_id, normalized)
            session.commit()
        return _report(counts, rejected=0)

    def candles(
        self,
        interval: str,
        *,
        start: datetime | None,
        end: datetime | None,
        limit: int,
    ) -> tuple[list[CandleRow], int]:
        self._require_interval(interval)
        with self._sessions() as session:
            rows = MarketRepository(session).candle_range(
                self.identity,
                interval,
                start,
                end,
                limit,
            )
        gaps = detect_candle_gaps(interval, [row.open_time for row in rows])
        if gaps:
            logger.info(
                "market_data_gap_detected provider=%s interval=%s gaps=%s",
                self.identity.provider,
                interval,
                len(gaps),
            )
        return rows, len(gaps)

    def latest(self, *, interval: str = "1m", now: datetime | None = None) -> LatestView:
        moment = now or datetime.now(UTC)
        with self._sessions() as session:
            repository = MarketRepository(session)
            trade = repository.latest_trade(self.identity)
            candle = repository.latest_candle(self.identity, interval, moment)
        if trade is not None and (candle is None or trade.event_time >= candle.close_time):
            freshness = trade_freshness(trade.event_time, moment, max_age=TRADE_FRESH_FOR)
            self._log_stale(freshness, "trade")
            return _latest_from_trade(self.identity, trade, freshness)
        if candle is not None:
            freshness = candle_freshness(interval, candle.close_time, moment)
            self._log_stale(freshness, "candle")
            return _latest_from_candle(self.identity, candle, freshness)
        return LatestView(
            canonical_symbol=self.identity.canonical_symbol,
            provider_symbol=self.identity.provider_symbol,
            provider=self.identity.provider,
            market_type=self.identity.market_type,
            quote_asset=self.identity.quote_asset,
            price=None,
            observation_time=None,
            freshness=DataStatus.INVALID,
            endpoint=None,
            normalization_version=None,
            detail="No verified market data",
        )

    def stored_candle_count(self) -> int:
        with self._sessions() as session:
            return MarketRepository(session).count_candles(self.identity)

    def _require_interval(self, interval: str) -> None:
        if interval not in SUPPORTED_INTERVALS:
            raise ValueError("unsupported interval")

    def _refuse_unbounded_range(
        self,
        interval: str,
        start: datetime | None,
        end: datetime | None,
        max_candles: int,
    ) -> None:
        if start is None or end is None:
            return
        from app.domains.market_data.quality import INTERVAL_DURATION

        step = INTERVAL_DURATION[interval]
        estimate = int((end - start) / step) + 1
        if estimate > max_candles:
            raise ValueError(
                f"requested range is about {estimate} candles; the cap is {max_candles}"
            )

    def _log_stale(self, freshness: DataStatus, kind: str) -> None:
        if freshness is DataStatus.STALE:
            logger.info(
                "market_data_stale provider=%s kind=%s symbol=%s",
                self.identity.provider,
                kind,
                self.identity.provider_symbol,
            )


def _partition_valid_candles(
    candles: list[CanonicalCandle],
) -> tuple[list[CanonicalCandle], int, int]:
    """Keep one candle per open time.

    Identical copies count as duplicates. If the same open time has different
    OHLCV content, every copy is rejected and none is stored.
    """
    groups: dict[datetime, list[CanonicalCandle]] = {}
    order: list[datetime] = []
    for candle in candles:
        bucket = groups.get(candle.open_time)
        if bucket is None:
            order.append(candle.open_time)
            bucket = []
            groups[candle.open_time] = bucket
        bucket.append(candle)
    retained: list[CanonicalCandle] = []
    duplicates = 0
    conflicts = 0
    for open_time in order:
        bucket = groups[open_time]
        if _ohlcv_conflicts(bucket):
            conflicts += len(bucket)
            logger.info(
                "market_data_validation_failed provider=%s kind=candle reason=%s",
                bucket[0].provider,
                "conflicting_candle",
            )
            continue
        retained.append(bucket[0])
        duplicates += len(bucket) - 1
    return retained, duplicates, conflicts


def _ohlcv_conflicts(candles: list[CanonicalCandle]) -> bool:
    first = _ohlcv(candles[0])
    return any(_ohlcv(candle) != first for candle in candles[1:])


def _ohlcv(candle: CanonicalCandle) -> tuple[object, ...]:
    return (
        candle.close_time,
        candle.open,
        candle.high,
        candle.low,
        candle.close,
        candle.volume,
        candle.quote_volume,
        candle.trade_count,
    )


def _report(counts: WriteCounts, *, rejected: int) -> IngestReport:
    return IngestReport(
        inserted=counts.inserted,
        duplicates=counts.duplicates,
        rejected=rejected,
        gaps=0,
    )


def _latest_from_trade(
    identity: MarketIdentity,
    trade: TradeRow,
    freshness: DataStatus,
) -> LatestView:
    return LatestView(
        canonical_symbol=identity.canonical_symbol,
        provider_symbol=identity.provider_symbol,
        provider=identity.provider,
        market_type=identity.market_type,
        quote_asset=identity.quote_asset,
        price=trade.price,
        observation_time=trade.event_time,
        freshness=freshness,
        endpoint=trade.endpoint,
        normalization_version=trade.normalization_version,
        detail="Verified public trade",
    )


def _latest_from_candle(
    identity: MarketIdentity,
    candle: CandleRow,
    freshness: DataStatus,
) -> LatestView:
    return LatestView(
        canonical_symbol=identity.canonical_symbol,
        provider_symbol=identity.provider_symbol,
        provider=identity.provider,
        market_type=identity.market_type,
        quote_asset=identity.quote_asset,
        price=candle.close,
        observation_time=candle.close_time,
        freshness=freshness,
        endpoint=candle.endpoint,
        normalization_version=candle.normalization_version,
        detail="Verified closed candle",
    )
