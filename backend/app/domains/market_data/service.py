"""Ingestion and queries. Callers do not touch provider payloads."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings
from app.core.database import create_db_engine
from app.domains.market_data.aggregates import (
    CompletenessStatus,
    PreparedAggregates,
    aggregate_window_fingerprint,
    assess_aggregate_completeness,
    prepare_aggregate_sequence,
)
from app.domains.market_data.identity import (
    BTC_USDT_SPOT,
    NORMALIZATION_VERSION,
    SUPPORTED_INTERVALS,
    MarketIdentity,
)
from app.domains.market_data.normalize import (
    normalize_aggregate_trade,
    normalize_book,
    normalize_kline,
    normalize_trade,
)
from app.domains.market_data.persistence import (
    AggregateTradeRow,
    AggregateTradeWindowRow,
    CandleRow,
    TradeRow,
)
from app.domains.market_data.providers.base import MarketDataProvider
from app.domains.market_data.providers.binance_spot import AGG_TRADES_PATH, BinanceSpotProvider
from app.domains.market_data.quality import (
    DataStatus,
    Rejection,
    candle_freshness,
    detect_candle_gaps,
    ensure_utc,
    trade_freshness,
)
from app.domains.market_data.records import CanonicalAggregateTrade, CanonicalCandle
from app.domains.market_data.repository import MarketRepository, WriteCounts

logger = logging.getLogger("app.market_data.service")

MAX_CANDLES_PER_RUN = 5000
DEFAULT_MAX_CANDLES = 1000
MAX_AGGREGATE_TRADES_PER_RUN = 5000
DEFAULT_MAX_AGGREGATE_TRADES = 1000
TRADE_FRESH_FOR = timedelta(minutes=2)
AGGREGATE_ENDPOINT = f"GET {AGG_TRADES_PATH}"


@dataclass(frozen=True, slots=True)
class IngestReport:
    inserted: int
    duplicates: int
    rejected: int
    gaps: int


@dataclass(frozen=True, slots=True)
class AggregateWindowReport:
    canonical_symbol: str
    provider: str
    provider_symbol: str
    market_type: str
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
    completeness: CompletenessStatus
    gap_details: dict[str, object]
    checked_at: datetime
    input_fingerprint: str
    endpoint: str
    normalization_version: str


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

    def ingest_aggregate_trades(
        self,
        *,
        start: datetime,
        end: datetime,
        max_trades: int = DEFAULT_MAX_AGGREGATE_TRADES,
        now: datetime | None = None,
    ) -> AggregateWindowReport:
        opened = ensure_utc(start)
        closed = ensure_utc(end)
        if isinstance(opened, Rejection) or isinstance(closed, Rejection):
            raise ValueError("start and end must be timezone-aware")
        if closed < opened:
            raise ValueError("end is before start")
        if max_trades < 1 or max_trades > MAX_AGGREGATE_TRADES_PER_RUN:
            raise ValueError(f"aggregate trade cap is {MAX_AGGREGATE_TRADES_PER_RUN}")
        moment = now or datetime.now(UTC)
        retrieval = self._provider.fetch_aggregate_trades(
            provider_symbol=self.identity.provider_symbol,
            start=opened,
            end=closed,
            max_trades=max_trades,
        )
        collected, invalid_reason = _collect_aggregate_pages(
            retrieval.pages,
            self.identity,
            moment,
            start=opened,
            end=closed,
        )
        if invalid_reason is None:
            prepared = prepare_aggregate_sequence(collected)
        else:
            prepared = PreparedAggregates((), 0, 0, (), invalid_reason)
        assessment = assess_aggregate_completeness(
            prepared.trades,
            page_count=len(retrieval.pages),
            stop=retrieval.stop,
            saw_full_page=retrieval.saw_full_page,
            invalid_reason=prepared.invalid_reason,
        )
        details = assessment.details(
            page_count=len(retrieval.pages),
            stop=retrieval.stop,
            saw_full_page=retrieval.saw_full_page,
        )
        status = assessment.status
        if prepared.conflicts:
            status = CompletenessStatus.INVALID
            details = {
                **details,
                "reason": "conflicting_aggregate_content",
                "conflict_ids": list(prepared.conflict_ids),
                "limitation": "conflicting_aggregate_id_was_not_overwritten",
            }
        observed = () if prepared.invalid_reason else prepared.trades
        with self._sessions() as session:
            repository = MarketRepository(session)
            market_id = repository.ensure_market(self.identity)
            counts = repository.insert_aggregate_trades(market_id, list(observed))
            if counts.conflicts:
                status = CompletenessStatus.INVALID
                details = {
                    **details,
                    "reason": "conflicting_aggregate_content",
                    "conflict_ids": [
                        *prepared.conflict_ids,
                        *counts.conflict_ids,
                    ],
                    "limitation": "conflicting_aggregate_id_was_not_overwritten",
                }
            fingerprint = aggregate_window_fingerprint(list(observed))
            report = _aggregate_report(
                self.identity,
                start=opened,
                end=closed,
                trades=observed,
                inserted=counts.inserted,
                duplicates=prepared.duplicates + counts.duplicates,
                conflicts=prepared.conflicts + counts.conflicts,
                status=status,
                details=details,
                checked_at=moment,
                fingerprint=fingerprint,
            )
            repository.insert_aggregate_window(
                market_id,
                requested_start=report.requested_start,
                requested_end=report.requested_end,
                first_event_time=report.first_event_time,
                last_event_time=report.last_event_time,
                first_aggregate_id=report.first_aggregate_id,
                last_aggregate_id=report.last_aggregate_id,
                aggregate_trade_count=report.aggregate_trade_count,
                underlying_first_trade_id=report.underlying_first_trade_id,
                underlying_last_trade_id=report.underlying_last_trade_id,
                inserted=report.inserted,
                duplicates=report.duplicates,
                conflicts=report.conflicts,
                completeness=report.completeness.value,
                gap_details=report.gap_details,
                checked_at=report.checked_at,
                input_fingerprint=report.input_fingerprint,
                endpoint=report.endpoint,
                normalization_version=report.normalization_version,
            )
            session.commit()
        if details.get("observed_aggregate_id_discontinuity") is True:
            logger.info(
                "market_data_aggregate_id_discontinuity_observed provider=%s count=%s",
                self.identity.provider,
                len(assessment.gaps),
            )
        return report

    def aggregate_trades(
        self,
        *,
        start: datetime | None,
        end: datetime | None,
        limit: int,
    ) -> list[AggregateTradeRow]:
        with self._sessions() as session:
            return MarketRepository(session).aggregate_trade_range(
                self.identity,
                start,
                end,
                limit,
            )

    def aggregate_trade_window(
        self,
        *,
        start: datetime | None,
        end: datetime | None,
    ) -> tuple[AggregateTradeWindowRow | None, int]:
        with self._sessions() as session:
            repository = MarketRepository(session)
            window = repository.latest_aggregate_window(self.identity, start, end)
            stored = repository.count_aggregate_trades(self.identity)
        return window, stored

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


def _collect_aggregate_pages(
    pages: tuple[tuple[object, ...], ...],
    identity: MarketIdentity,
    ingested_at: datetime,
    *,
    start: datetime,
    end: datetime,
) -> tuple[list[CanonicalAggregateTrade], str | None]:
    flat = [(page_index, row) for page_index, page in enumerate(pages) for row in page]
    kept: list[CanonicalAggregateTrade] = []
    for index, (page_index, row) in enumerate(flat):
        normalized = _normalize_in_window(row, identity, ingested_at)
        if isinstance(normalized, str):
            return [], normalized
        if normalized.event_time < start or (page_index == 0 and normalized.event_time > end):
            return [], "event_time_outside_window"
        if normalized.event_time > end:
            for later_row in flat[index + 1 :]:
                later = _normalize_in_window(later_row[1], identity, ingested_at)
                if isinstance(later, str):
                    return [], later
                if later.event_time <= end:
                    return [], "non_monotonic_event_time"
            return kept, None
        kept.append(normalized)
    return kept, None


def _normalize_in_window(
    row: object,
    identity: MarketIdentity,
    ingested_at: datetime,
) -> CanonicalAggregateTrade | str:
    normalized = normalize_aggregate_trade(row, identity, ingested_at)
    if isinstance(normalized, Rejection):
        logger.info(
            "market_data_validation_failed provider=%s kind=aggregate_trade reason=%s",
            identity.provider,
            normalized.reason,
        )
        return normalized.reason
    return normalized


def _aggregate_report(
    identity: MarketIdentity,
    *,
    start: datetime,
    end: datetime,
    trades: tuple[CanonicalAggregateTrade, ...],
    inserted: int,
    duplicates: int,
    conflicts: int,
    status: CompletenessStatus,
    details: dict[str, object],
    checked_at: datetime,
    fingerprint: str,
) -> AggregateWindowReport:
    first = trades[0] if trades else None
    last = trades[-1] if trades else None
    return AggregateWindowReport(
        canonical_symbol=identity.canonical_symbol,
        provider=identity.provider,
        provider_symbol=identity.provider_symbol,
        market_type=identity.market_type,
        requested_start=start,
        requested_end=end,
        first_event_time=None if first is None else first.event_time,
        last_event_time=None if last is None else last.event_time,
        first_aggregate_id=None if first is None else first.aggregate_trade_id,
        last_aggregate_id=None if last is None else last.aggregate_trade_id,
        aggregate_trade_count=len(trades),
        underlying_first_trade_id=None if first is None else first.first_trade_id,
        underlying_last_trade_id=None if last is None else last.last_trade_id,
        inserted=inserted,
        duplicates=duplicates,
        conflicts=conflicts,
        completeness=status,
        gap_details=details,
        checked_at=checked_at,
        input_fingerprint=fingerprint,
        endpoint=AGGREGATE_ENDPOINT,
        normalization_version=NORMALIZATION_VERSION,
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
