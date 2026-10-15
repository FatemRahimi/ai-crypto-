"""Idempotent persistence for canonical observations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.domains.market_data.identity import MarketIdentity
from app.domains.market_data.persistence import BookSnapshotRow, CandleRow, MarketRow, TradeRow
from app.domains.market_data.records import CanonicalBook, CanonicalCandle, CanonicalTrade


@dataclass(frozen=True, slots=True)
class WriteCounts:
    inserted: int
    duplicates: int


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

