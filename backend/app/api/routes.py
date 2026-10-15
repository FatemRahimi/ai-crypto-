from __future__ import annotations

from typing import Literal

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict

from app.core import constitution
from app.core.config import Settings
from app.core.database import DatabaseProbe
from app.domains.catalog import DOMAIN_BOUNDARIES
from app.domains.pipeline import PIPELINE_STAGES
from app.domains.types import DomainBoundary


class HealthLive(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["ok"]
    service: Literal["ai-crypto-api"]
    environment: str
    phase: Literal[1]


class HealthReady(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["ok", "degraded"]
    database: Literal["ok", "unavailable"]
    execution_enabled: Literal[False]


class PlatformStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")

    phase: Literal[1]
    evidence_rule: str
    execution_enabled: Literal[False]
    custody: Literal["none"]
    withdrawal_permission_allowed: Literal[False]
    sessions: Literal["not_implemented"]
    mfa: Literal["not_implemented"]
    passkeys: Literal["not_implemented"]
    rate_limiting: Literal["not_implemented"]
    audit_log: Literal["not_implemented"]
    encrypted_exchange_credentials: Literal["not_implemented"]
    pipeline: list[str]
    domains: list[DomainBoundary]


def register_routes(app: FastAPI, settings: Settings, database_probe: DatabaseProbe) -> None:
    @app.get("/health/live", response_model=HealthLive)
    def health_live() -> HealthLive:
        return HealthLive(
            status="ok",
            service="ai-crypto-api",
            environment=settings.app_env,
            phase=constitution.PHASE,
        )

    @app.get("/health/ready", response_model=HealthReady)
    def health_ready() -> JSONResponse:
        database: Literal["ok", "unavailable"] = "ok" if database_probe() == "ok" else "unavailable"
        payload = HealthReady(
            status="ok" if database == "ok" else "degraded",
            database=database,
            execution_enabled=False,
        )
        return JSONResponse(
            status_code=200 if database == "ok" else 503,
            content=payload.model_dump(),
        )

    @app.get("/api/v1/platform", response_model=PlatformStatus)
    def platform_status() -> PlatformStatus:
        return PlatformStatus(
            phase=constitution.PHASE,
            evidence_rule=constitution.EVIDENCE_RULE,
            execution_enabled=constitution.EXECUTION_ENABLED,
            custody="none",
            withdrawal_permission_allowed=constitution.WITHDRAWAL_PERMISSION_ALLOWED,
            sessions="not_implemented",
            mfa="not_implemented",
            passkeys="not_implemented",
            rate_limiting="not_implemented",
            audit_log="not_implemented",
            encrypted_exchange_credentials="not_implemented",
            pipeline=list(PIPELINE_STAGES),
            domains=list(DOMAIN_BOUNDARIES),
        )
