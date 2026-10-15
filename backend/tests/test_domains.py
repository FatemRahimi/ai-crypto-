from __future__ import annotations

from pathlib import Path

from app.domains.catalog import DOMAIN_BOUNDARIES, boundary_map

AI_ROOT = Path(__file__).resolve().parents[1] / "app" / "domains" / "ai"
BANNED_AI_TERMS = (
    "app.domains.execution",
    "authorize_execution",
    "ExecutionIntent",
    "ExecutionGateway",
    "GatewayNotEnabled",
)


def test_domain_catalog_is_unique_and_complete() -> None:
    keys = [item.key for item in DOMAIN_BOUNDARIES]
    assert len(keys) == len(set(keys))
    assert set(boundary_map()) == set(keys)
    for item in DOMAIN_BOUNDARIES:
        assert item.must_not
        assert item.phase_note


def test_ai_package_cannot_reach_the_execution_gateway() -> None:
    sources = list(AI_ROOT.rglob("*.py"))
    assert sources
    for path in sources:
        text = path.read_text(encoding="utf-8")
        for term in BANNED_AI_TERMS:
            assert term not in text, f"{path.name} contains {term}"
