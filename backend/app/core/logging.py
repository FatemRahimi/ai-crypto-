from __future__ import annotations

import json
import logging
from datetime import UTC, datetime

from app.core.middleware import REQUEST_ID
from app.core.redaction import redact_text


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = REQUEST_ID.get()
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "ts": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": redact_text(record.getMessage()),
            "request_id": getattr(record, "request_id", "-"),
        }
        exc_info = record.exc_info
        if isinstance(exc_info, BaseException):
            exc_info = (type(exc_info), exc_info, exc_info.__traceback__)
        if isinstance(exc_info, tuple):
            exc_type = exc_info[0]
            payload["exc_type"] = exc_type.__name__ if isinstance(exc_type, type) else "Exception"
            payload["traceback"] = redact_text(self.formatException(exc_info))
        return json.dumps(payload, default=_json_default)


def _json_default(value: object) -> str:
    return redact_text(str(value))


def configure_logging(level: str) -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    handler.addFilter(RequestIdFilter())

    app_logger = logging.getLogger("app")
    app_logger.handlers.clear()
    app_logger.addHandler(handler)
    app_logger.setLevel(level)
    app_logger.propagate = False
