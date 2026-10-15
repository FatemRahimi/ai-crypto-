from __future__ import annotations

import logging
from collections.abc import Callable

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import DeclarativeBase

from app.core.config import Settings

logger = logging.getLogger("app.database")

DatabaseProbe = Callable[[], str]


class Base(DeclarativeBase):
    """Declarative base for future domain models.

    Phase 1 has no mapped tables. Alembic still imports this metadata.
    """


def create_db_engine(settings: Settings) -> Engine:
    return create_engine(
        settings.database_url,
        pool_pre_ping=True,
        connect_args={"connect_timeout": 3},
    )


def probe_database(engine: Engine) -> str:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception as exc:
        logger.warning("database_unavailable error_type=%s", type(exc).__name__)
        return "unavailable"
    return "ok"


def build_database_probe(settings: Settings) -> DatabaseProbe:
    engine = create_db_engine(settings)

    def probe() -> str:
        return probe_database(engine)

    return probe
