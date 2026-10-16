from __future__ import annotations

from app.domains.pipeline import PIPELINE_STAGES
from app.main import create_app
from fastapi import FastAPI
from fastapi.testclient import TestClient

from tests.conftest import make_settings


def test_platform_reports_phase1_posture(client: TestClient) -> None:
    response = client.get("/api/v1/platform")
    assert response.status_code == 200
    body = response.json()
    assert body["phase"] == 1
    assert body["evidence_rule"] == "No evidence → no claim."
    assert body["execution_enabled"] is False
    assert body["custody"] == "none"
    assert body["withdrawal_permission_allowed"] is False
    assert body["sessions"] == "not_implemented"
    assert body["mfa"] == "not_implemented"
    assert body["passkeys"] == "not_implemented"
    assert body["rate_limiting"] == "not_implemented"
    assert body["audit_log"] == "not_implemented"
    assert body["encrypted_exchange_credentials"] == "not_implemented"
    assert body["pipeline"] == list(PIPELINE_STAGES)
    keys = [item["key"] for item in body["domains"]]
    assert keys == [
        "identity",
        "accounts",
        "connections",
        "market_data",
        "market_intelligence",
        "strategies",
        "quant",
        "regimes",
        "opportunities",
        "risk",
        "capital",
        "positions",
        "execution",
        "notifications",
        "performance",
        "ai",
        "audit",
    ]
    by_key = {item["key"]: item for item in body["domains"]}
    assert by_key["execution"]["implementation_status"] == "disabled"
    assert by_key["risk"]["implementation_status"] == "disabled"
    assert by_key["ai"]["implementation_status"] == "foundation"
    assert by_key["market_data"]["implementation_status"] == "foundation"
    assert by_key["market_intelligence"]["implementation_status"] == "foundation"


def test_openapi_exposes_only_foundation_routes(app: FastAPI) -> None:
    schema = app.openapi()
    assert set(schema["paths"]) == {
        "/health/live",
        "/health/ready",
        "/api/v1/platform",
        "/api/v1/market-data/status",
        "/api/v1/market-data/candles",
        "/api/v1/market-data/latest",
        "/api/v1/market-data/aggregate-trades",
        "/api/v1/market-data/aggregate-trade-windows",
        "/api/v1/technical-evidence",
        "/api/v1/technical-evidence/latest",
    }
    for operations in schema["paths"].values():
        assert set(operations) == {"get"}


def test_production_hides_api_docs() -> None:
    app = create_app(
        make_settings(
            app_env="production",
            app_secret_key="p" * 40,
            cors_origins="https://app.example.com",
            database_url="postgresql+psycopg://aicrypto:pw@db.internal:5432/aicrypto",
        ),
        database_probe=lambda: "unavailable",
    )
    assert app.docs_url is None
    assert app.openapi_url is None
