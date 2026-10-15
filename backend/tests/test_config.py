from __future__ import annotations

from pathlib import Path

import pytest
from app.core import config
from app.core.config import Settings
from pydantic import ValidationError


def test_env_file_is_the_repository_root_dotenv() -> None:
    source = Path(config.__file__).resolve()
    repository_root = source.parents[3]
    assert config.REPO_ROOT == repository_root
    assert config.ENV_FILE == repository_root / ".env"
    assert (repository_root / "backend" / "pyproject.toml").is_file()
    assert (repository_root / ".env.example").is_file()
    assert config.REPO_ROOT != source.parents[2]
    assert config.REPO_ROOT != source.parents[4]


def test_local_settings_accept_defaults() -> None:
    settings = Settings(app_env="local")
    assert settings.cors_origin_list == [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]


def test_database_url_must_use_psycopg() -> None:
    with pytest.raises(ValidationError):
        Settings(database_url="postgresql://aicrypto:pw@127.0.0.1:5432/aicrypto")


def test_production_rejects_known_placeholder_secret() -> None:
    with pytest.raises(ValidationError):
        Settings(
            app_env="production",
            app_secret_key="local-dev-only-change-me",
            database_url="postgresql+psycopg://aicrypto:pw@db.internal:5432/aicrypto",
            cors_origins="https://app.example.com",
            debug=False,
        )


def test_production_rejects_debug_and_wildcard_cors() -> None:
    with pytest.raises(ValidationError):
        Settings(
            app_env="production",
            app_secret_key="a" * 32,
            database_url="postgresql+psycopg://aicrypto:pw@db.internal:5432/aicrypto",
            cors_origins="https://app.example.com",
            debug=True,
        )
    with pytest.raises(ValidationError):
        Settings(
            app_env="production",
            app_secret_key="a" * 32,
            database_url="postgresql+psycopg://aicrypto:pw@db.internal:5432/aicrypto",
            cors_origins="*",
            debug=False,
        )


def test_production_rejects_short_secret_that_is_not_a_known_placeholder() -> None:
    with pytest.raises(ValidationError):
        Settings(
            app_env="production",
            app_secret_key="b" * 31,
            database_url="postgresql+psycopg://aicrypto:pw@db.internal:5432/aicrypto",
            cors_origins="https://app.example.com",
            debug=False,
        )


def test_api_port_must_be_a_tcp_port() -> None:
    with pytest.raises(ValidationError):
        Settings(api_port=0)
    with pytest.raises(ValidationError):
        Settings(api_port=70000)


def test_production_accepts_explicit_configuration() -> None:
    settings = Settings(
        app_env="production",
        app_secret_key="a" * 40,
        database_url="postgresql+psycopg://aicrypto:pw@db.internal:5432/aicrypto",
        cors_origins="https://app.example.com",
        debug=False,
    )
    assert settings.app_env == "production"
    assert settings.cors_origin_list == ["https://app.example.com"]
