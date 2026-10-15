from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient


def test_security_headers_and_request_id(client: TestClient) -> None:
    response = client.get("/health/live", headers={"X-Request-ID": "req_123"})
    assert response.status_code == 200
    assert response.headers["x-request-id"] == "req_123"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "no-referrer"
    assert response.headers["cache-control"] == "no-store"
    assert "camera=()" in response.headers["permissions-policy"]


def test_invalid_request_id_is_replaced(client: TestClient) -> None:
    response = client.get("/health/live", headers={"X-Request-ID": "not a safe id"})
    assert response.headers["x-request-id"] != "not a safe id"
    assert response.headers["x-request-id"]


def test_cors_allows_only_configured_origin(client: TestClient) -> None:
    allowed = client.get("/health/live", headers={"Origin": "http://localhost:3000"})
    assert allowed.headers["access-control-allow-origin"] == "http://localhost:3000"
    rejected = client.get("/health/live", headers={"Origin": "http://evil.example"})
    assert "access-control-allow-origin" not in rejected.headers


def test_validation_errors_are_structured(app: FastAPI) -> None:
    @app.get("/_test/echo")
    def echo(count: int) -> dict[str, int]:
        return {"count": count}

    response = TestClient(app).get("/_test/echo?count=nope")
    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "validation_error"
    assert body["error"]["request_id"]


def test_unhandled_errors_do_not_leak_secrets(app: FastAPI) -> None:
    @app.get("/_test/boom")
    def boom() -> dict[str, str]:
        raise RuntimeError(
            "postgresql+psycopg://aicrypto:super-secret@127.0.0.1/aicrypto Bearer abcdef"
        )

    response = TestClient(app, raise_server_exceptions=False).get("/_test/boom")
    assert response.status_code == 500
    assert response.json()["error"]["code"] == "internal_error"
    assert response.json()["error"]["message"] == "Something went wrong."
    assert "super-secret" not in response.text
    assert "abcdef" not in response.text
