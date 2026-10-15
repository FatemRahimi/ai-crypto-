from __future__ import annotations

import re
from collections.abc import Mapping

_URL = re.compile(r"\b[a-z][a-z0-9+.-]*://[^\s\"']+", re.IGNORECASE)
_BEARER = re.compile(r"(?i)\bbearer\s+[a-z0-9._~+/=-]+")
_SENSITIVE_KEY = re.compile(
    r"(password|passwd|secret|token|api[-_]?key|authorization|credential|dsn|database_url)",
    re.IGNORECASE,
)


def redact_text(value: str) -> str:
    without_urls = _URL.sub("[redacted-url]", value)
    return _BEARER.sub("Bearer [redacted]", without_urls)


def redact_mapping(value: Mapping[str, object]) -> dict[str, object]:
    redacted: dict[str, object] = {}
    for key, item in value.items():
        if _SENSITIVE_KEY.search(key):
            redacted[key] = "[redacted]"
            continue
        if isinstance(item, str):
            redacted[key] = redact_text(item)
            continue
        if isinstance(item, dict):
            redacted[key] = redact_mapping(item)
            continue
        redacted[key] = item
    return redacted
