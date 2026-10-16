"""Idempotent persistence for canonical observations."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.domains.market_data.identity import MarketIdentity
from app.domains.market_data.persistence import (
    AggregateTradeRow,
    AggregateTradeWindowRow,
    BookSnapshotRow,
    CandleRow,
    MarketRow,
    TradeRow,
)
from app.domains.market_data.records import (
    CanonicalAggregateTrade,
    CanonicalBook,
    CanonicalCandle,
    CanonicalTrade,
)


@dataclass(frozen=True, slots=True)
class WriteCounts:
    inserted: int
    duplicates: int


@dataclass(frozen=True, slots=True)
class AggregateWriteCounts:
    inserted: int
    duplicates: int
    conflicts: int
    conflict_ids: tuple[int, ...]


class MarketRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def ensure_market(self, identity: MarketIdentity) -> int:
        existing = self._session.scalar(
            select(MarketRow).where(
                MarketRow.provider == identity.provider,
                MarketRow.provider_symbol == identity.provider_symbol,
                MarketRow.market_type == identity.market_type,
            )
        )
        if existing is not None:
            return existing.id
        row = MarketRow(
            provider=identity.provider,
            market_type=identity.market_type,
            base_asset=identity.base_asset,
            quote_asset=identity.quote_asset,
            provider_symbol=identity.provider_symbol,
            canonical_symbol=identity.canonical_symbol,
        )
        self._session.add(row)
        self._session.flush()
        return row.id

    def insert_candles(self, market_id: int, candles: list[CanonicalCandle]) -> WriteCounts:
        if not candles:
            return WriteCounts(inserted=0, duplicates=0)
        values = [
            {
                "market_id": market_id,
                "interval": candle.interval,
                "open_time": candle.open_time,
                "close_time": candle.close_time,
                "open": candle.open,
                "high": candle.high,
                "low": candle.low,
                "close": candle.close,
                "volume": candle.volume,
                "quote_volume": candle.quote_volume,
                "trade_count": candle.trade_count,
                "ingested_at": candle.ingested_at,
                "data_status": candle.data_status.value,
                "endpoint": candle.endpoint,
                "normalization_version": candle.normalization_version,
            }
            for candle in candles
        ]
        statement = pg_insert(CandleRow).values(values)
        statement = statement.on_conflict_do_nothing(constraint="uq_market_candles_identity")
        inserted = len(self._session.scalars(statement.returning(CandleRow.id)).all())
        return WriteCounts(inserted=inserted, duplicates=len(candles) - inserted)

    def insert_trades(self, market_id: int, trades: list[CanonicalTrade]) -> WriteCounts:
        if not trades:
            return WriteCounts(inserted=0, duplicates=0)
        values = [
            {
                "market_id": market_id,
                "provider_trade_id": trade.provider_trade_id,
                "price": trade.price,
                "quantity": trade.quantity,
                "quote_quantity": trade.quote_quantity,
                "event_time": trade.event_time,
                "buyer_is_maker": trade.buyer_is_maker,
                "ingested_at": trade.ingested_at,
                "endpoint": trade.endpoint,
                "normalization_version": trade.normalization_version,
            }
            for trade in trades
        ]
        statement = pg_insert(TradeRow).values(values)
        statement = statement.on_conflict_do_nothing(constraint="uq_market_trades_identity")
        inserted = len(self._session.scalars(statement.returning(TradeRow.id)).all())
        return WriteCounts(inserted=inserted, duplicates=len(trades) - inserted)

    def insert_book_if_changed(self, market_id: int, book: CanonicalBook) -> WriteCounts:
        latest = self._session.scalar(
            select(BookSnapshotRow)
            .where(BookSnapshotRow.market_id == market_id)
            .order_by(BookSnapshotRow.ingested_at.desc())
            .limit(1)
        )
        if (
            latest is not None
            and latest.bid == book.bid
            and latest.ask == book.ask
            and latest.bid_quantity == book.bid_quantity
            and latest.ask_quantity == book.ask_quantity
        ):
            return WriteCounts(inserted=0, duplicates=1)
        self._session.add(
            BookSnapshotRow(
                market_id=market_id,
                bid=book.bid,
                ask=book.ask,
                bid_quantity=book.bid_quantity,
                ask_quantity=book.ask_quantity,
                source_timestamp=book.source_timestamp,
                ingested_at=book.ingested_at,
                endpoint=book.endpoint,
                normalization_version=book.normalization_version,
            )
        )
        self._session.flush()
        return WriteCounts(inserted=1, duplicates=0)

    def candle_range(
        self,
        identity: MarketIdentity,
        interval: str,
        start: datetime | None,
        end: datetime | None,
        limit: int,
    ) -> list[CandleRow]:
        market_id = self._market_id(identity)
        if market_id is None:
            return []
        query = select(CandleRow).where(
            CandleRow.market_id == market_id,
            CandleRow.interval == interval,
            CandleRow.data_status == "VALID",
        )
        if start is not None:
            query = query.where(CandleRow.open_time >= start)
        if end is not None:
            query = query.where(CandleRow.open_time <= end)
        return list(
            self._session.scalars(query.order_by(CandleRow.open_time.asc()).limit(limit)).all()
        )

    def latest_candle(
        self,
        identity: MarketIdentity,
        interval: str,
        now: datetime,
    ) -> CandleRow | None:
        market_id = self._market_id(identity)
        if market_id is None:
            return None
        return self._session.scalar(
            select(CandleRow)
            .where(
                CandleRow.market_id == market_id,
                CandleRow.interval == interval,
                CandleRow.data_status == "VALID",
                CandleRow.close_time <= now,
            )
            .order_by(CandleRow.open_time.desc())
            .limit(1)
        )

    def latest_trade(self, identity: MarketIdentity) -> TradeRow | None:
        market_id = self._market_id(identity)
        if market_id is None:
            return None
        return self._session.scalar(
            select(TradeRow)
            .where(TradeRow.market_id == market_id)
            .order_by(TradeRow.event_time.desc())
            .limit(1)
        )

    def insert_aggregate_trades(
        self,
        market_id: int,
        trades: list[CanonicalAggregateTrade],
    ) -> AggregateWriteCounts:
        if not trades:
            return AggregateWriteCounts(inserted=0, duplicates=0, conflicts=0, conflict_ids=())
        existing = {
            row.aggregate_trade_id: row
            for row in self._session.scalars(
                select(AggregateTradeRow).where(
                    AggregateTradeRow.market_id == market_id,
                    AggregateTradeRow.aggregate_trade_id.in_(
                        [trade.aggregate_trade_id for trade in trades]
                    ),
                )
            ).all()
        }
        fresh: list[CanonicalAggregateTrade] = []
        duplicates = 0
        conflicts = 0
        conflict_ids: list[int] = []
        for trade in trades:
            current = existing.get(trade.aggregate_trade_id)
            if current is None:
                fresh.append(trade)
                continue
            if current.content_fingerprint == trade.content_fingerprint:
                duplicates += 1
            else:
                conflicts += 1
                conflict_ids.append(trade.aggregate_trade_id)
        if fresh:
            self._session.add_all(
                [
                    AggregateTradeRow(
                        market_id=market_id,
                        aggregate_trade_id=trade.aggregate_trade_id,
                        price=trade.price,
                        quantity=trade.quantity,
                        event_time=trade.event_time,
                        first_trade_id=trade.first_trade_id,
                        last_trade_id=trade.last_trade_id,
                        buyer_is_maker=trade.buyer_is_maker,
                        ingested_at=trade.ingested_at,
                        content_fingerprint=trade.content_fingerprint,
                        endpoint=trade.endpoint,
                        normalization_version=trade.normalization_version,
                    )
                    for trade in fresh
                ]
            )
            self._session.flush()
        return AggregateWriteCounts(
            inserted=len(fresh),
            duplicates=duplicates,
            conflicts=conflicts,
            conflict_ids=tuple(conflict_ids),
        )

    def insert_aggregate_window(
        self,
        market_id: int,
        *,
        requested_start: datetime,
        requested_end: datetime,
        first_event_time: datetime | None,
        last_event_time: datetime | None,
        first_aggregate_id: int | None,
        last_aggregate_id: int | None,
        aggregate_trade_count: int,
        underlying_first_trade_id: int | None,
        underlying_last_trade_id: int | None,
        inserted: int,
        duplicates: int,
        conflicts: int,
        completeness: str,
        gap_details: dict[str, object] | None,
        checked_at: datetime,
        input_fingerprint: str,
        endpoint: str,
        normalization_version: str,
    ) -> None:
        self._session.add(
            AggregateTradeWindowRow(
                market_id=market_id,
                requested_start=requested_start,
                requested_end=requested_end,
                first_event_time=first_event_time,
                last_event_time=last_event_time,
                first_aggregate_id=first_aggregate_id,
                last_aggregate_id=last_aggregate_id,
                aggregate_trade_count=aggregate_trade_count,
                underlying_first_trade_id=underlying_first_trade_id,
                underlying_last_trade_id=underlying_last_trade_id,
                inserted=inserted,
                duplicates=duplicates,
                conflicts=conflicts,
                completeness=completeness,
                gap_details_json=None if gap_details is None else json.dumps(gap_details),
                checked_at=checked_at,
                input_fingerprint=input_fingerprint,
                endpoint=endpoint,
                normalization_version=normalization_version,
            )
        )
        self._session.flush()

    def aggregate_trade_range(
        self,
        identity: MarketIdentity,
        start: datetime | None,
        end: datetime | None,
        limit: int,
    ) -> list[AggregateTradeRow]:
        market_id = self._market_id(identity)
        if market_id is None:
            return []
        query = select(AggregateTradeRow).where(AggregateTradeRow.market_id == market_id)
        if start is not None:
            query = query.where(AggregateTradeRow.event_time >= start)
        if end is not None:
            query = query.where(AggregateTradeRow.event_time <= end)
        return list(
            self._session.scalars(
                query.order_by(
                    AggregateTradeRow.event_time.asc(),
                    AggregateTradeRow.aggregate_trade_id.asc(),
                ).limit(limit)
            ).all()
        )

    def latest_aggregate_window(
        self,
        identity: MarketIdentity,
        start: datetime | None,
        end: datetime | None,
    ) -> AggregateTradeWindowRow | None:
        market_id = self._market_id(identity)
        if market_id is None:
            return None
        query = select(AggregateTradeWindowRow).where(
            AggregateTradeWindowRow.market_id == market_id
        )
        if start is not None:
            query = query.where(AggregateTradeWindowRow.requested_start == start)
        if end is not None:
            query = query.where(AggregateTradeWindowRow.requested_end == end)
        return self._session.scalar(
            query.order_by(
                AggregateTradeWindowRow.checked_at.desc(),
                AggregateTradeWindowRow.id.desc(),
            ).limit(1)
        )

    def aggregate_windows_for_exact_bounds(
        self,
        identity: MarketIdentity,
        start: datetime,
        end: datetime,
    ) -> list[AggregateTradeWindowRow]:
        """Every report for this exact request. Callers must not keep only the newest."""
        market_id = self._market_id(identity)
        if market_id is None:
            return []
        return list(
            self._session.scalars(
                select(AggregateTradeWindowRow)
                .where(
                    AggregateTradeWindowRow.market_id == market_id,
                    AggregateTradeWindowRow.requested_start == start,
                    AggregateTradeWindowRow.requested_end == end,
                )
                .order_by(AggregateTradeWindowRow.id.asc())
            ).all()
        )

    def count_aggregate_trades(self, identity: MarketIdentity) -> int:
        market_id = self._market_id(identity)
        if market_id is None:
            return 0
        counted = self._session.scalar(
            select(func.count())
            .select_from(AggregateTradeRow)
            .where(AggregateTradeRow.market_id == market_id)
        )
        return int(counted or 0)

    def count_candles(self, identity: MarketIdentity) -> int:
        market_id = self._market_id(identity)
        if market_id is None:
            return 0
        counted = self._session.scalar(
            select(func.count()).select_from(CandleRow).where(CandleRow.market_id == market_id)
        )
        return int(counted or 0)

    def _market_id(self, identity: MarketIdentity) -> int | None:
        return self._session.scalar(
            select(MarketRow.id).where(
                MarketRow.provider == identity.provider,
                MarketRow.provider_symbol == identity.provider_symbol,
                MarketRow.market_type == identity.market_type,
            )
        )

