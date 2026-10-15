"""Establish the Phase 1 revision chain.

Phase 1 does not persist markets, accounts, strategies, or trades.
Domain tables are added by the phase that owns that data.

Revision ID: 20261014_0001
Revises:
Create Date: 2026-10-14
"""

from collections.abc import Sequence

revision: str = "20261014_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the Alembic version record only."""


def downgrade() -> None:
    """No schema objects were created by this revision."""
