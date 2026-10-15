"""Store public BTC spot observations.

Revision ID: 20261015_0002
Revises: 20261014_0001
Create Date: 2026-10-15
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261015_0002"
down_revision: str | None = "20261014_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

MONEY = sa.Numeric(38, 18)


def upgrade() -> None:
    op.create_table(
        "market_instruments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("market_type", sa.String(length=16), nullable=False),
        sa.Column("base_asset", sa.String(length=16), nullable=False),
        sa.Column("quote_asset", sa.String(length=16), nullable=False),
        sa.Column("provider_symbol", sa.String(length=32), nullable=False),
        sa.Column("canonical_symbol", sa.String(length=32), nullable=False),
        sa.UniqueConstraint(
            "provider",
            "provider_symbol",
            "market_type",
            name="uq_market_instruments_identity",
        ),
    )
    op.create_table(
        "market_candles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "market_id",
            sa.Integer(),
            sa.ForeignKey("market_instruments.id"),
            nullable=False,
        ),
        sa.Column("interval", sa.String(length=8), nullable=False),
        sa.Column("open_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("close_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("open", MONEY, nullable=False),
        sa.Column("high", MONEY, nullable=False),
        sa.Column("low", MONEY, nullable=False),
        sa.Column("close", MONEY, nullable=False),
        sa.Column("volume", MONEY, nullable=False),
        sa.Column("quote_volume", MONEY, nullable=True),
        sa.Column("trade_count", sa.Integer(), nullable=True),
        sa.Column("ingested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("data_status", sa.String(length=16), nullable=False),
        sa.Column("endpoint", sa.String(length=80), nullable=False),
        sa.Column("normalization_version", sa.String(length=64), nullable=False),
        sa.CheckConstraint("close_time > open_time", name="ck_market_candles_time"),
        sa.CheckConstraint("high >= low", name="ck_market_candles_high_low"),
        sa.CheckConstraint(
            "open > 0 AND high > 0 AND low > 0 AND close > 0 AND volume >= 0",
            name="ck_market_candles_non_negative",
        ),
        sa.UniqueConstraint(
            "market_id",
            "interval",
            "open_time",
            name="uq_market_candles_identity",
        ),
    )
    op.create_index(
        "ix_market_candles_lookup",
        "market_candles",
        ["market_id", "interval", "open_time"],
    )
    op.create_table(
        "market_trades",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "market_id",
            sa.Integer(),
            sa.ForeignKey("market_instruments.id"),
            nullable=False,
        ),
        sa.Column("provider_trade_id", sa.BigInteger(), nullable=False),
        sa.Column("price", MONEY, nullable=False),
        sa.Column("quantity", MONEY, nullable=False),
        sa.Column("quote_quantity", MONEY, nullable=True),
        sa.Column("event_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("buyer_is_maker", sa.Boolean(), nullable=True),
        sa.Column("ingested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("endpoint", sa.String(length=80), nullable=False),
        sa.Column("normalization_version", sa.String(length=64), nullable=False),
        sa.CheckConstraint("price > 0 AND quantity > 0", name="ck_market_trades_positive"),
        sa.UniqueConstraint("market_id", "provider_trade_id", name="uq_market_trades_identity"),
    )
    op.create_index("ix_market_trades_time", "market_trades", ["market_id", "event_time"])
    op.create_table(
        "market_book_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "market_id",
            sa.Integer(),
            sa.ForeignKey("market_instruments.id"),
            nullable=False,
        ),
        sa.Column("bid", MONEY, nullable=False),
        sa.Column("ask", MONEY, nullable=False),
        sa.Column("bid_quantity", MONEY, nullable=True),
        sa.Column("ask_quantity", MONEY, nullable=True),
        sa.Column("source_timestamp", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ingested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("endpoint", sa.String(length=80), nullable=False),
        sa.Column("normalization_version", sa.String(length=64), nullable=False),
        sa.CheckConstraint("bid > 0 AND ask >= bid", name="ck_market_book_prices"),
    )
    op.create_index(
        "ix_market_book_ingested",
        "market_book_snapshots",
        ["market_id", "ingested_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_market_book_ingested", table_name="market_book_snapshots")
    op.drop_table("market_book_snapshots")
    op.drop_index("ix_market_trades_time", table_name="market_trades")
    op.drop_table("market_trades")
    op.drop_index("ix_market_candles_lookup", table_name="market_candles")
    op.drop_table("market_candles")
    op.drop_table("market_instruments")
