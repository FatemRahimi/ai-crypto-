from __future__ import annotations

import pytest
from app.core.config import Settings
from app.main import create_app
from fastapi import FastAPI
from fastapi.testclient import TestClient


def make_settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "app_env": "test",
        "app_secret_key": "test-only-secret",
        "database_url": "postgresql+psycopg://aicrypto:test@127.0.0.1:5432/aicrypto",
        "cors_origins": "http://localhost:3000",
        "log_level": "WARNING",
        "debug": False,
    }
    values.update(overrides)
    return Settings.model_validate(values)


@pytest.fixture
def settings() -> Settings:
    return make_settings()


@pytest.fixture
def app(settings: Settings) -> FastAPI:
    return create_app(settings, database_probe=lambda: "ok")


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    return TestClient(app)
