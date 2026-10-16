"""Store observed volume-at-price evidence apart from candle technical evidence.

Revision ID: 20261016_0006
Revises: 20261016_0005
Create Date: 2026-10-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261016_0006"
down_revision: str | None = "20261016_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

MONEY = sa.Numeric(38, 18)


def upgrade() -> None:
    op.create_table(
        "observed_volume_evidence",
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
        sa.Column("input_aggregate_count", sa.Integer(), nullable=False),
        sa.Column("input_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("parameters_hash", sa.String(length=64), nullable=False),
        sa.Column("parameters_json", sa.Text(), nullable=False),
        sa.Column("calculator_name", sa.String(length=64), nullable=False),
        sa.Column("calculator_version", sa.String(length=64), nullable=False),
        sa.Column("bucket_method", sa.String(length=32), nullable=False),
        sa.Column("volume_definition", sa.String(length=32), nullable=False),
        sa.Column("poc_tie_break", sa.String(length=32), nullable=False),
        sa.Column("source_completeness", sa.String(length=32), nullable=False),
        sa.Column("source_limitation", sa.Text(), nullable=False),
        sa.Column("source_details_json", sa.Text(), nullable=False),
        sa.Column("sufficiency", sa.String(length=16), nullable=False),
        sa.Column("total_observed_base_volume", MONEY, nullable=True),
        sa.Column("observed_poc_price", MONEY, nullable=True),
        sa.Column("poc_tie_count", sa.Integer(), nullable=True),
        sa.Column("poc_tie", sa.Boolean(), nullable=True),
        sa.Column("largest_aggregate_base_quantity", MONEY, nullable=True),
        sa.Column("derived_largest_share", MONEY, nullable=True),
        sa.Column("calculated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "market_id",
            "calculator_name",
            "calculator_version",
            "parameters_hash",
            "input_fingerprint",
            name="uq_observed_volume_evidence_identity",
        ),
        sa.CheckConstraint(
            "sufficiency in ('OBSERVED', 'INSUFFICIENT', 'INVALID')",
            name="ck_observed_volume_sufficiency",
        ),
        sa.CheckConstraint(
            "source_completeness in ('COMPLETENESS_UNKNOWN', 'INVALID')",
            name="ck_observed_volume_source_completeness",
        ),
        sa.CheckConstraint(
            "(sufficiency = 'INVALID' AND source_completeness = 'INVALID') OR "
            "(sufficiency <> 'INVALID' AND source_completeness = 'COMPLETENESS_UNKNOWN')",
            name="ck_observed_volume_not_complete",
        ),
        sa.CheckConstraint(
            "bucket_method = 'exact_price' AND volume_definition = 'base_quantity' "
            "AND poc_tie_break = 'lower_price'",
            name="ck_observed_volume_method",
        ),
        sa.CheckConstraint(
            "("
            "sufficiency = 'OBSERVED' "
            "AND observed_poc_price IS NOT NULL "
            "AND poc_tie_count IS NOT NULL "
            "AND poc_tie IS NOT NULL "
            "AND total_observed_base_volume IS NOT NULL "
            "AND largest_aggregate_base_quantity IS NOT NULL "
            "AND derived_largest_share IS NOT NULL "
            "AND input_aggregate_count > 0"
            ") OR ("
            "sufficiency <> 'OBSERVED' "
            "AND observed_poc_price IS NULL "
            "AND poc_tie_count IS NULL "
            "AND poc_tie IS NULL "
            "AND total_observed_base_volume IS NULL "
            "AND largest_aggregate_base_quantity IS NULL "
            "AND derived_largest_share IS NULL"
            ")",
            name="ck_observed_volume_measurement",
        ),
    )
    op.create_index(
        "ix_observed_volume_evidence_lookup",
        "observed_volume_evidence",
        ["market_id", "requested_start", "requested_end", "calculated_at"],
    )
    op.create_table(
        "observed_volume_buckets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "evidence_id",
            sa.Integer(),
            sa.ForeignKey("observed_volume_evidence.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("price", MONEY, nullable=False),
        sa.Column("observed_base_volume", MONEY, nullable=False),
        sa.Column("aggregate_count", sa.Integer(), nullable=False),
        sa.Column("derived_share", MONEY, nullable=False),
        sa.UniqueConstraint("evidence_id", "price", name="uq_observed_volume_bucket_price"),
        sa.CheckConstraint(
            "price > 0 AND observed_base_volume > 0 AND aggregate_count > 0 "
            "AND derived_share >= 0 AND derived_share <= 1",
            name="ck_observed_volume_bucket_positive",
        ),
    )
    op.create_index(
        "ix_observed_volume_buckets_evidence",
        "observed_volume_buckets",
        ["evidence_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_observed_volume_buckets_evidence", table_name="observed_volume_buckets")
    op.drop_table("observed_volume_buckets")
    op.drop_index("ix_observed_volume_evidence_lookup", table_name="observed_volume_evidence")
    op.drop_table("observed_volume_evidence")
