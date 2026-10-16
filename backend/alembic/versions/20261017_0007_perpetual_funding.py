"""Store USD-M perpetual funding observations.

Revision ID: 20261017_0007
Revises: 20261016_0006
Create Date: 2026-10-17
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261017_0007"
down_revision: str | None = "20261016_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

MONEY = sa.Numeric(38, 18)


def upgrade() -> None:
    op.create_table(
        "market_funding_observations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "market_id",
            sa.Integer(),
            sa.ForeignKey("market_instruments.id"),
            nullable=False,
        ),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("funding_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("funding_rate", MONEY, nullable=False),
        sa.Column("rate_type", sa.String(length=16), nullable=False),
        sa.Column("content_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("endpoint", sa.String(length=80), nullable=False),
        sa.Column("normalization_version", sa.String(length=64), nullable=False),
        sa.Column("ingested_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "rate_type IN ('Regular', 'Special')",
            name="ck_market_funding_rate_type",
        ),
        sa.UniqueConstraint(
            "market_id",
            "funding_time",
            "rate_type",
            name="uq_market_funding_identity",
        ),
    )
    op.create_index(
        "ix_market_funding_time",
        "market_funding_observations",
        ["market_id", "funding_time"],
    )
    op.create_table(
        "market_funding_windows",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "market_id",
            sa.Integer(),
            sa.ForeignKey("market_instruments.id"),
            nullable=False,
        ),
        sa.Column("requested_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("requested_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("first_funding_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_funding_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("row_count", sa.Integer(), nullable=False),
        sa.Column("inserted", sa.Integer(), nullable=False),
        sa.Column("duplicates", sa.Integer(), nullable=False),
        sa.Column("conflicts", sa.Integer(), nullable=False),
        sa.Column("completeness", sa.String(length=32), nullable=False),
        sa.Column("details_json", sa.Text(), nullable=True),
        sa.Column("checked_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("input_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("endpoint", sa.String(length=80), nullable=False),
        sa.Column("normalization_version", sa.String(length=64), nullable=False),
        sa.CheckConstraint(
            "completeness IN ('COMPLETENESS_UNKNOWN', 'EMPTY', 'INVALID')",
            name="ck_market_funding_window_not_complete",
        ),
        sa.CheckConstraint(
            "requested_end >= requested_start",
            name="ck_market_funding_window_bounds",
        ),
    )
    op.create_index(
        "ix_market_funding_windows_lookup",
        "market_funding_windows",
        ["market_id", "requested_start", "requested_end", "checked_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_market_funding_windows_lookup", table_name="market_funding_windows")
    op.drop_table("market_funding_windows")
    op.drop_index("ix_market_funding_time", table_name="market_funding_observations")
    op.drop_table("market_funding_observations")
