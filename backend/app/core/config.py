from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[3]
ENV_FILE = REPO_ROOT / ".env"

INSECURE_SECRET_VALUES = frozenset(
    {
        "",
        "change-me",
        "changeme",
        "local-dev-only-change-me",
        "password",
        "secret",
    }
)


class Settings(BaseSettings):
    """Process configuration.

    APP_SECRET_KEY is loaded and checked so a production process fails closed
    when it is missing. Phase 1 does not sign sessions with it.
    """

    model_config = SettingsConfigDict(
        env_file=ENV_FILE if ENV_FILE.is_file() else None,
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_env: Literal["local", "test", "production"] = "local"
    app_secret_key: str = Field(default="local-dev-only-change-me")
    api_host: str = "127.0.0.1"
    api_port: int = Field(default=8000, ge=1, le=65535)
    database_url: str = (
        "postgresql+psycopg://aicrypto:local_dev_change_me@127.0.0.1:5432/aicrypto"
    )
    market_data_base_url: str = "https://data-api.binance.vision"
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    log_level: str = "INFO"
    debug: bool = False

    @field_validator("log_level")
    @classmethod
    def normalize_log_level(cls, value: str) -> str:
        normalized = value.upper()
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if normalized not in allowed:
            raise ValueError("LOG_LEVEL must be DEBUG, INFO, WARNING, ERROR, or CRITICAL")
        return normalized

    @field_validator("api_host")
    @classmethod
    def require_api_host(cls, value: str) -> str:
        host = value.strip()
        if not host:
            raise ValueError("API_HOST must not be empty")
        return host

    @field_validator("market_data_base_url")
    @classmethod
    def require_public_market_data_url(cls, value: str) -> str:
        url = value.strip().rstrip("/")
        if not url.startswith("https://"):
            raise ValueError("MARKET_DATA_BASE_URL must use https")
        return url

    @field_validator("database_url")
    @classmethod
    def require_psycopg_url(cls, value: str) -> str:
        if not value.startswith("postgresql+psycopg://"):
            raise ValueError("DATABASE_URL must start with postgresql+psycopg://")
        return value

    @property
    def cors_origin_list(self) -> list[str]:
        origins = [item.strip() for item in self.cors_origins.split(",") if item.strip()]
        return origins

    @model_validator(mode="after")
    def enforce_production_guards(self) -> Settings:
        if self.app_env != "production":
            return self
        if self.debug:
            raise ValueError("DEBUG must be false when APP_ENV is production")
        secret = self.app_secret_key.strip()
        if secret.lower() in INSECURE_SECRET_VALUES or len(secret) < 32:
            raise ValueError(
                "APP_SECRET_KEY must be a unique value of at least 32 characters in production"
            )
        origins = self.cors_origin_list
        if not origins or any(origin == "*" for origin in origins):
            raise ValueError("CORS_ORIGINS must be an explicit allowlist in production")
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
