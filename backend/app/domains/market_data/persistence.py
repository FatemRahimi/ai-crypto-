"""PostgreSQL tables for canonical market observations."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

MONEY = Numeric(38, 18)


class MarketRow(Base):
    __tablename__ = "market_instruments"
    __table_args__ = (
        UniqueConstraint(
            "provider",
            "provider_symbol",
            "market_type",
            name="uq_market_instruments_identity",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    market_type: Mapped[str] = mapped_column(String(16), nullable=False)
    base_asset: Mapped[str] = mapped_column(String(16), nullable=False)
    quote_asset: Mapped[str] = mapped_column(String(16), nullable=False)
    provider_symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    canonical_symbol: Mapped[str] = mapped_column(String(32), nullable=False)


class CandleRow(Base):
    __tablename__ = "market_candles"
    __table_args__ = (
        UniqueConstraint(
            "market_id",
            "interval",
            "open_time",
            name="uq_market_candles_identity",
        ),
        CheckConstraint("close_time > open_time", name="ck_market_candles_time"),
        CheckConstraint("high >= low", name="ck_market_candles_high_low"),
        CheckConstraint(
            "open > 0 AND high > 0 AND low > 0 AND close > 0 AND volume >= 0",
            name="ck_market_candles_non_negative",
        ),
        Index("ix_market_candles_lookup", "market_id", "interval", "open_time"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    market_id: Mapped[int] = mapped_column(ForeignKey("market_instruments.id"), nullable=False)
    interval: Mapped[str] = mapped_column(String(8), nullable=False)
    open_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    close_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    open: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    high: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    low: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    close: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    volume: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    quote_volume: Mapped[Decimal | None] = mapped_column(MONEY, nullable=True)
    trade_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    data_status: Mapped[str] = mapped_column(String(16), nullable=False)
    endpoint: Mapped[str] = mapped_column(String(80), nullable=False)
    normalization_version: Mapped[str] = mapped_column(String(64), nullable=False)


class TradeRow(Base):
    __tablename__ = "market_trades"
    __table_args__ = (
        UniqueConstraint("market_id", "provider_trade_id", name="uq_market_trades_identity"),
        CheckConstraint("price > 0 AND quantity > 0", name="ck_market_trades_positive"),
        Index("ix_market_trades_time", "market_id", "event_time"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    market_id: Mapped[int] = mapped_column(ForeignKey("market_instruments.id"), nullable=False)
    provider_trade_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    price: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    quantity: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    quote_quantity: Mapped[Decimal | None] = mapped_column(MONEY, nullable=True)
    event_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    buyer_is_maker: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    endpoint: Mapped[str] = mapped_column(String(80), nullable=False)
    normalization_version: Mapped[str] = mapped_column(String(64), nullable=False)


class AggregateTradeRow(Base):
    """Public aggregate trades. Ordinary `market_trades` rows stay a different feed."""

    __tablename__ = "market_aggregate_trades"
    __table_args__ = (
        UniqueConstraint(
            "market_id",
            "aggregate_trade_id",
            name="uq_market_aggregate_trades_identity",
        ),
        CheckConstraint("price > 0 AND quantity > 0", name="ck_market_aggregate_trades_positive"),
        CheckConstraint(
            "last_trade_id >= first_trade_id",
            name="ck_market_aggregate_trades_id_span",
        ),
        Index("ix_market_aggregate_trades_time", "market_id", "event_time"),
        Index("ix_market_aggregate_trades_id", "market_id", "aggregate_trade_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    market_id: Mapped[int] = mapped_column(ForeignKey("market_instruments.id"), nullable=False)
    aggregate_trade_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    price: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    quantity: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    event_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    first_trade_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    last_trade_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    buyer_is_maker: Mapped[bool] = mapped_column(Boolean, nullable=False)
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    content_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    endpoint: Mapped[str] = mapped_column(String(80), nullable=False)
    normalization_version: Mapped[str] = mapped_column(String(64), nullable=False)


class AggregateTradeWindowRow(Base):
    """One completeness check for an explicit aggregate-trade request window."""

    __tablename__ = "market_aggregate_trade_windows"
    __table_args__ = (
        Index(
            "ix_market_aggregate_windows_lookup",
            "market_id",
            "requested_start",
            "requested_end",
            "checked_at",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    market_id: Mapped[int] = mapped_column(ForeignKey("market_instruments.id"), nullable=False)
    requested_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    requested_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    first_event_time: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    last_event_time: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    first_aggregate_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    last_aggregate_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    aggregate_trade_count: Mapped[int] = mapped_column(Integer, nullable=False)
    underlying_first_trade_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    underlying_last_trade_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    inserted: Mapped[int] = mapped_column(Integer, nullable=False)
    duplicates: Mapped[int] = mapped_column(Integer, nullable=False)
    conflicts: Mapped[int] = mapped_column(Integer, nullable=False)
    completeness: Mapped[str] = mapped_column(String(32), nullable=False)
    gap_details_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    input_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    endpoint: Mapped[str] = mapped_column(String(80), nullable=False)
    normalization_version: Mapped[str] = mapped_column(String(64), nullable=False)


class BookSnapshotRow(Base):
    __tablename__ = "market_book_snapshots"
    __table_args__ = (
        CheckConstraint("bid > 0 AND ask >= bid", name="ck_market_book_prices"),
        Index("ix_market_book_ingested", "market_id", "ingested_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    market_id: Mapped[int] = mapped_column(ForeignKey("market_instruments.id"), nullable=False)
    bid: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    ask: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    bid_quantity: Mapped[Decimal | None] = mapped_column(MONEY, nullable=True)
    ask_quantity: Mapped[Decimal | None] = mapped_column(MONEY, nullable=True)
    source_timestamp: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    endpoint: Mapped[str] = mapped_column(String(80), nullable=False)
    normalization_version: Mapped[str] = mapped_column(String(64), nullable=False)
