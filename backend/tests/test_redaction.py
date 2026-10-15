from __future__ import annotations

import logging
import sys

from app.core.logging import JsonFormatter
from app.core.redaction import redact_mapping, redact_text


def test_redact_text_removes_urls_and_bearers() -> None:
    message = (
        "connect postgresql+psycopg://aicrypto:super-secret@127.0.0.1/aicrypto "
        "Authorization Bearer abc.def-123"
    )
    redacted = redact_text(message)
    assert "super-secret" not in redacted
    assert "abc.def-123" not in redacted
    assert "[redacted-url]" in redacted
    assert "Bearer [redacted]" in redacted


def test_redact_mapping_hides_sensitive_keys() -> None:
    redacted = redact_mapping(
        {
            "database_url": "postgresql+psycopg://aicrypto:super-secret@db/aicrypto",
            "api_key": "raw-key",
            "note": "Bearer abcdef stays out",
            "nested": {"password": "hide-me", "label": "visible"},
        }
    )
    assert redacted["database_url"] == "[redacted]"
    assert redacted["api_key"] == "[redacted]"
    assert "abcdef" not in str(redacted["note"])
    nested = redacted["nested"]
    assert isinstance(nested, dict)
    assert nested["password"] == "[redacted]"
    assert nested["label"] == "visible"


def test_json_logs_redact_exception_text() -> None:
    formatter = JsonFormatter()
    try:
        raise RuntimeError("postgresql://user:super-secret@db/app")
    except RuntimeError:
        record = logging.LogRecord(
            name="app.errors",
            level=logging.ERROR,
            pathname=__file__,
            lineno=1,
            msg="boom",
            args=(),
            exc_info=sys.exc_info(),
        )
    rendered = formatter.format(record)
    assert "super-secret" not in rendered
    assert "RuntimeError" in rendered
