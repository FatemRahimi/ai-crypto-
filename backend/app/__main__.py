"""Start the API using API_HOST and API_PORT from the environment or .env.

Uvicorn's own command does not read those settings. Use this module when the
port must follow configuration, for example when port 8000 is already taken.
"""

from __future__ import annotations

import uvicorn

from app.core.config import get_settings


def main() -> None:
    settings = get_settings()
    uvicorn.run(
        "app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.app_env == "local",
    )


if __name__ == "__main__":
    main()
