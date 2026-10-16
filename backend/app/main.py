from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.market_data import MarketReader, register_market_routes
from app.api.observed_volume import ObservedVolumeReader, register_observed_volume_routes
from app.api.routes import register_routes
from app.api.technical_evidence import EvidenceReader, register_evidence_routes
from app.core.config import Settings, get_settings
from app.core.database import DatabaseProbe, build_database_probe
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging
from app.core.middleware import RequestContextMiddleware
from app.domains.market_data.service import MarketDataService
from app.domains.market_intelligence.observed_volume_service import ObservedVolumeService
from app.domains.market_intelligence.service import TechnicalEvidenceService


def create_app(
    settings: Settings | None = None,
    database_probe: DatabaseProbe | None = None,
    market_data: MarketReader | None = None,
    evidence: EvidenceReader | None = None,
    observed_volume: ObservedVolumeReader | None = None,
) -> FastAPI:
    resolved = settings or get_settings()
    configure_logging(resolved.log_level)
    probe = database_probe or build_database_probe(resolved)

    app = FastAPI(
        title="AI-Crypto API",
        version="0.1.0",
        summary="Public BTC market data and a refusing execution boundary. No custody.",
        docs_url=None if resolved.app_env == "production" else "/docs",
        redoc_url=None,
        openapi_url=None if resolved.app_env == "production" else "/openapi.json",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=resolved.cors_origin_list,
        allow_credentials=False,
        allow_methods=["GET", "OPTIONS"],
        allow_headers=["Content-Type", "X-Request-ID"],
    )
    app.add_middleware(RequestContextMiddleware)
    register_exception_handlers(app)
    register_routes(app, resolved, probe)
    register_market_routes(app, market_data or MarketDataService.from_settings(resolved))
    register_evidence_routes(app, evidence or TechnicalEvidenceService.from_settings(resolved))
    register_observed_volume_routes(
        app,
        observed_volume or ObservedVolumeService.from_settings(resolved),
    )
    return app


app = create_app()
