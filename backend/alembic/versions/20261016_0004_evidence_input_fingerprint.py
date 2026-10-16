"""Identify technical evidence by candle content.

Revision ID: 20261016_0004
Revises: 20261016_0003
Create Date: 2026-10-16
"""

import json
from collections.abc import Sequence
from datetime import datetime
from decimal import Decimal

import sqlalchemy as sa
from alembic import op
from app.domains.market_intelligence.calculators import InputCandle, input_fingerprint

revision: str = "20261016_0004"
down_revision: str | None = "20261016_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

IDENTITY = (
    "market_id",
    "evidence_type",
    "interval",
    "observation_time",
    "calculator_name",
    "calculator_version",
    "parameters_hash",
)


def upgrade() -> None:
    op.add_column(
        "technical_evidence",
        sa.Column("input_fingerprint", sa.String(length=64), nullable=True),
    )
    _backfill_input_fingerprints()
    op.alter_column("technical_evidence", "input_fingerprint", nullable=False)
    op.drop_constraint("uq_technical_evidence_identity", "technical_evidence", type_="unique")
    op.create_unique_constraint(
        "uq_technical_evidence_identity",
        "technical_evidence",
        [*IDENTITY, "input_fingerprint"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_technical_evidence_identity", "technical_evidence", type_="unique")
    op.create_unique_constraint(
        "uq_technical_evidence_identity",
        "technical_evidence",
        list(IDENTITY),
    )
    op.drop_column("technical_evidence", "input_fingerprint")


def _backfill_input_fingerprints() -> None:
    connection = op.get_bind()
    evidence_rows = connection.execute(
        sa.text("SELECT id, input_candle_ids_json FROM technical_evidence")
    ).mappings()
    for evidence in evidence_rows:
        candles = [_load_candle(connection, int(candle_id)) for candle_id in _candle_ids(evidence)]
        digest = input_fingerprint(candles)
        connection.execute(
            sa.text(
                "UPDATE technical_evidence "
                "SET input_fingerprint = :digest WHERE id = :evidence_id"
            ),
            {"digest": digest, "evidence_id": evidence["id"]},
        )


def _candle_ids(evidence: sa.RowMapping) -> list[int]:
    raw_ids = json.loads(evidence["input_candle_ids_json"])
    if not isinstance(raw_ids, list):
        raise RuntimeError(f"technical evidence {evidence['id']} has no candle id list")
    return [int(candle_id) for candle_id in raw_ids]


def _load_candle(connection: sa.Connection, candle_id: int) -> InputCandle:
    candle = connection.execute(
        sa.text(
            "SELECT id, open_time, close_time, open, high, low, close, volume "
            "FROM market_candles WHERE id = :candle_id"
        ),
        {"candle_id": candle_id},
    ).mappings().one_or_none()
    if candle is None:
        raise RuntimeError(f"technical evidence cites missing candle {candle_id}")
    return InputCandle(
        candle_id=int(candle["id"]),
        open_time=_time(candle["open_time"]),
        close_time=_time(candle["close_time"]),
        open=Decimal(candle["open"]),
        high=Decimal(candle["high"]),
        low=Decimal(candle["low"]),
        close=Decimal(candle["close"]),
        volume=Decimal(candle["volume"]),
    )


def _time(value: object) -> datetime:
    if not isinstance(value, datetime):
        raise RuntimeError("candle timestamp is not a datetime")
    return value
