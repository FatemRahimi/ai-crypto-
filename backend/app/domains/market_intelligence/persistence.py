"""Derived technical evidence. Canonical candles stay in the market tables."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
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


class TechnicalEvidenceRow(Base):
    __tablename__ = "technical_evidence"
    __table_args__ = (
        UniqueConstraint(
            "market_id",
            "evidence_type",
            "interval",
            "observation_time",
            "calculator_name",
            "calculator_version",
            "parameters_hash",
            "input_fingerprint",
            name="uq_technical_evidence_identity",
        ),
        CheckConstraint(
            "evidence_type in ('swing_structure', 'support_resistance', "
            "'range_statistics', 'candle_vwap')",
            name="ck_technical_evidence_type",
        ),
        CheckConstraint(
            "data_status in ('VALID', 'GAP_DETECTED', 'INSUFFICIENT', 'INVALID')",
            name="ck_technical_evidence_status",
        ),
        Index(
            "ix_technical_evidence_lookup",
            "market_id",
            "evidence_type",
            "interval",
            "observation_time",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    market_id: Mapped[int] = mapped_column(ForeignKey("market_instruments.id"), nullable=False)
    evidence_type: Mapped[str] = mapped_column(String(32), nullable=False)
    interval: Mapped[str] = mapped_column(String(8), nullable=False)
    observation_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    calculated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    calculator_name: Mapped[str] = mapped_column(String(64), nullable=False)
    calculator_version: Mapped[str] = mapped_column(String(64), nullable=False)
    parameters_json: Mapped[str] = mapped_column(Text, nullable=False)
    parameters_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    input_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    input_open_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    input_open_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    input_candle_count: Mapped[int] = mapped_column(Integer, nullable=False)
    input_candle_ids_json: Mapped[str] = mapped_column(Text, nullable=False)
    result_json: Mapped[str] = mapped_column(Text, nullable=False)
    data_status: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ObservedVolumeEvidenceRow(Base):
    """One observed volume-at-price measurement. Candle technical evidence stays separate."""

    __tablename__ = "observed_volume_evidence"
    __table_args__ = (
        UniqueConstraint(
            "market_id",
            "calculator_name",
            "calculator_version",
            "parameters_hash",
            "input_fingerprint",
            name="uq_observed_volume_evidence_identity",
        ),
        CheckConstraint(
            "sufficiency in ('OBSERVED', 'INSUFFICIENT', 'INVALID')",
            name="ck_observed_volume_sufficiency",
        ),
        CheckConstraint(
            "source_completeness in ('COMPLETENESS_UNKNOWN', 'INVALID')",
            name="ck_observed_volume_source_completeness",
        ),
        CheckConstraint(
            "(sufficiency = 'INVALID' AND source_completeness = 'INVALID') OR "
            "(sufficiency <> 'INVALID' AND source_completeness = 'COMPLETENESS_UNKNOWN')",
            name="ck_observed_volume_not_complete",
        ),
        CheckConstraint(
            "bucket_method = 'exact_price' AND volume_definition = 'base_quantity' "
            "AND poc_tie_break = 'lower_price'",
            name="ck_observed_volume_method",
        ),
        CheckConstraint(
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
        Index(
            "ix_observed_volume_evidence_lookup",
            "market_id",
            "requested_start",
            "requested_end",
            "calculated_at",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    market_id: Mapped[int] = mapped_column(ForeignKey("market_instruments.id"), nullable=False)
    requested_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    requested_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    first_event_time: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_event_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    input_aggregate_count: Mapped[int] = mapped_column(Integer, nullable=False)
    input_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    parameters_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    parameters_json: Mapped[str] = mapped_column(Text, nullable=False)
    calculator_name: Mapped[str] = mapped_column(String(64), nullable=False)
    calculator_version: Mapped[str] = mapped_column(String(64), nullable=False)
    bucket_method: Mapped[str] = mapped_column(String(32), nullable=False)
    volume_definition: Mapped[str] = mapped_column(String(32), nullable=False)
    poc_tie_break: Mapped[str] = mapped_column(String(32), nullable=False)
    source_completeness: Mapped[str] = mapped_column(String(32), nullable=False)
    source_limitation: Mapped[str] = mapped_column(Text, nullable=False)
    source_details_json: Mapped[str] = mapped_column(Text, nullable=False)
    sufficiency: Mapped[str] = mapped_column(String(16), nullable=False)
    total_observed_base_volume: Mapped[Decimal | None] = mapped_column(MONEY, nullable=True)
    observed_poc_price: Mapped[Decimal | None] = mapped_column(MONEY, nullable=True)
    poc_tie_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    poc_tie: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    largest_aggregate_base_quantity: Mapped[Decimal | None] = mapped_column(MONEY, nullable=True)
    derived_largest_share: Mapped[Decimal | None] = mapped_column(MONEY, nullable=True)
    calculated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ObservedVolumeBucketRow(Base):
    """One exact stored price. Rows are ordered by price when read."""

    __tablename__ = "observed_volume_buckets"
    __table_args__ = (
        UniqueConstraint("evidence_id", "price", name="uq_observed_volume_bucket_price"),
        CheckConstraint(
            "price > 0 AND observed_base_volume > 0 AND aggregate_count > 0 "
            "AND derived_share >= 0 AND derived_share <= 1",
            name="ck_observed_volume_bucket_positive",
        ),
        Index("ix_observed_volume_buckets_evidence", "evidence_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    evidence_id: Mapped[int] = mapped_column(
        ForeignKey("observed_volume_evidence.id", ondelete="CASCADE"),
        nullable=False,
    )
    price: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    observed_base_volume: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    aggregate_count: Mapped[int] = mapped_column(Integer, nullable=False)
    derived_share: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
