"""Store public aggregate trades apart from ordinary trades.

Revision ID: 20261016_0005
Revises: 20261016_0004
Create Date: 2026-10-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261016_0005"
down_revision: str | None = "20261016_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

MONEY = sa.Numeric(38, 18)


def upgrade() -> None:
    op.create_table(
        "market_aggregate_trades",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "market_id",
            sa.Integer(),
            sa.ForeignKey("market_instruments.id"),
            nullable=False,
        ),
        sa.Column("aggregate_trade_id", sa.BigInteger(), nullable=False),
        sa.Column("price", MONEY, nullable=False),
        sa.Column("quantity", MONEY, nullable=False),
        sa.Column("event_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("first_trade_id", sa.BigInteger(), nullable=False),
        sa.Column("last_trade_id", sa.BigInteger(), nullable=False),
        sa.Column("buyer_is_maker", sa.Boolean(), nullable=False),
        sa.Column("ingested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("content_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("endpoint", sa.String(length=80), nullable=False),
        sa.Column("normalization_version", sa.String(length=64), nullable=False),
        sa.UniqueConstraint(
            "market_id",
            "aggregate_trade_id",
            name="uq_market_aggregate_trades_identity",
        ),
        sa.CheckConstraint(
            "price > 0 AND quantity > 0",
            name="ck_market_aggregate_trades_positive",
        ),
        sa.CheckConstraint(
            "last_trade_id >= first_trade_id",
            name="ck_market_aggregate_trades_id_span",
        ),
    )
    op.create_index(
        "ix_market_aggregate_trades_time",
        "market_aggregate_trades",
        ["market_id", "event_time"],
    )
    op.create_index(
        "ix_market_aggregate_trades_id",
        "market_aggregate_trades",
        ["market_id", "aggregate_trade_id"],
    )
    op.create_table(
        "market_aggregate_trade_windows",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "market_id",
            sa.Integer(),
            sa.ForeignKey("market_instruments.id"),
            nullable=False,
        ),
        sa.Column("requested_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("requested_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("first_event_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_event_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("first_aggregate_id", sa.BigInteger(), nullable=True),
        sa.Column("last_aggregate_id", sa.BigInteger(), nullable=True),
        sa.Column("aggregate_trade_count", sa.Integer(), nullable=False),
        sa.Column("underlying_first_trade_id", sa.BigInteger(), nullable=True),
        sa.Column("underlying_last_trade_id", sa.BigInteger(), nullable=True),
        sa.Column("inserted", sa.Integer(), nullable=False),
        sa.Column("duplicates", sa.Integer(), nullable=False),
        sa.Column("conflicts", sa.Integer(), nullable=False),
        sa.Column("completeness", sa.String(length=32), nullable=False),
        sa.Column("gap_details_json", sa.Text(), nullable=True),
        sa.Column("checked_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("input_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("endpoint", sa.String(length=80), nullable=False),
        sa.Column("normalization_version", sa.String(length=64), nullable=False),
    )
    op.create_index(
        "ix_market_aggregate_windows_lookup",
        "market_aggregate_trade_windows",
        ["market_id", "requested_start", "requested_end", "checked_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_market_aggregate_windows_lookup", table_name="market_aggregate_trade_windows")
    op.drop_table("market_aggregate_trade_windows")
    op.drop_index("ix_market_aggregate_trades_id", table_name="market_aggregate_trades")
    op.drop_index("ix_market_aggregate_trades_time", table_name="market_aggregate_trades")
    op.drop_table("market_aggregate_trades")
