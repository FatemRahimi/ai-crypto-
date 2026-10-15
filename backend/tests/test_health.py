from __future__ import annotations

from app.main import create_app
from fastapi.testclient import TestClient

from tests.conftest import make_settings


def test_live_health(client: TestClient) -> None:
    response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "ai-crypto-api",
        "environment": "test",
        "phase": 1,
    }


def test_ready_is_ok_when_database_probe_passes(client: TestClient) -> None:
    response = client.get("/health/ready")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["database"] == "ok"
    assert response.json()["execution_enabled"] is False


def test_ready_is_degraded_when_database_is_unavailable() -> None:
    app = create_app(make_settings(), database_probe=lambda: "unavailable")
    response = TestClient(app).get("/health/ready")
    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "degraded"
    assert body["database"] == "unavailable"
    assert body["execution_enabled"] is False


def test_unknown_probe_result_fails_closed() -> None:
    app = create_app(make_settings(), database_probe=lambda: "mystery")
    response = TestClient(app).get("/health/ready")
    assert response.status_code == 503
    assert response.json()["database"] == "unavailable"
