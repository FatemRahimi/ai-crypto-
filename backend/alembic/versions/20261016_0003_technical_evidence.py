"""Store deterministic technical evidence separately from candles.

Revision ID: 20261016_0003
Revises: 20261015_0002
Create Date: 2026-10-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261016_0003"
down_revision: str | None = "20261015_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "technical_evidence",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "market_id",
            sa.Integer(),
            sa.ForeignKey("market_instruments.id"),
            nullable=False,
        ),
        sa.Column("evidence_type", sa.String(length=32), nullable=False),
        sa.Column("interval", sa.String(length=8), nullable=False),
        sa.Column("observation_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("calculated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("calculator_name", sa.String(length=64), nullable=False),
        sa.Column("calculator_version", sa.String(length=64), nullable=False),
        sa.Column("parameters_json", sa.Text(), nullable=False),
        sa.Column("parameters_hash", sa.String(length=64), nullable=False),
        sa.Column("input_open_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("input_open_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("input_candle_count", sa.Integer(), nullable=False),
        sa.Column("input_candle_ids_json", sa.Text(), nullable=False),
        sa.Column("result_json", sa.Text(), nullable=False),
        sa.Column("data_status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "evidence_type in ('swing_structure', 'support_resistance', "
            "'range_statistics', 'candle_vwap')",
            name="ck_technical_evidence_type",
        ),
        sa.CheckConstraint(
            "data_status in ('VALID', 'GAP_DETECTED', 'INSUFFICIENT', 'INVALID')",
            name="ck_technical_evidence_status",
        ),
        sa.UniqueConstraint(
            "market_id",
            "evidence_type",
            "interval",
            "observation_time",
            "calculator_name",
            "calculator_version",
            "parameters_hash",
            name="uq_technical_evidence_identity",
        ),
    )
    op.create_index(
        "ix_technical_evidence_lookup",
        "technical_evidence",
        ["market_id", "evidence_type", "interval", "observation_time"],
    )


def downgrade() -> None:
    op.drop_index("ix_technical_evidence_lookup", table_name="technical_evidence")
    op.drop_table("technical_evidence")
