"""Derived technical evidence. Canonical candles stay in the market tables."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


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
    input_open_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    input_open_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    input_candle_count: Mapped[int] = mapped_column(Integer, nullable=False)
    input_candle_ids_json: Mapped[str] = mapped_column(Text, nullable=False)
    result_json: Mapped[str] = mapped_column(Text, nullable=False)
    data_status: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
