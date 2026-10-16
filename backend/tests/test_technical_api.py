from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from app.domains.market_intelligence.service import EvidenceView
from app.main import create_app
from fastapi.testclient import TestClient

from tests.conftest import make_settings

OPEN = datetime(2026, 10, 15, 12, 0, tzinfo=UTC)
ROOT = Path(__file__).resolve().parents[1]


class MemoryEvidence:
    def __init__(self, rows: list[EvidenceView]) -> None:
        self.rows = rows

    def latest(
        self,
        evidence_type: str,
        interval: str,
        *,
        now: datetime | None = None,
    ) -> EvidenceView | None:
        del now
        for row in self.rows:
            if row.evidence_type == evidence_type and row.interval == interval:
                return row
        return None

    def recent(
        self,
        *,
        interval: str | None = None,
        evidence_type: str | None = None,
        limit: int = 20,
        now: datetime | None = None,
    ) -> list[EvidenceView]:
        del now
        chosen = self.rows
        if interval is not None:
            chosen = [row for row in chosen if row.interval == interval]
        if evidence_type is not None:
            chosen = [row for row in chosen if row.evidence_type == evidence_type]
        return chosen[:limit]


def _view() -> EvidenceView:
    return EvidenceView(
        evidence_id=7,
        evidence_type="swing_structure",
        canonical_symbol="BTC/USDT",
        provider="binance_spot",
        provider_symbol="BTCUSDT",
        market_type="spot",
        interval="1m",
        observation_time=OPEN,
        calculated_at=OPEN,
        calculator_name="swing_structure",
        calculator_version="technical-evidence-v1",
        parameters={"left": 2, "right": 2, "candle_limit": 10},
        input_open_start=OPEN,
        input_open_end=OPEN,
        input_candle_count=5,
        input_candle_ids=[1, 2, 3, 4, 5],
        input_fingerprint="ab" * 32,
        result={
            "pivots": [],
            "structure": [],
            "rule": "strict_fractal_confirmed_after_right_candles",
        },
        data_status="VALID",
        freshness="stale",
    )


def test_empty_evidence_is_explicit_and_unknown_markets_are_rejected() -> None:
    client = TestClient(
        create_app(make_settings(), database_probe=lambda: "ok", evidence=MemoryEvidence([]))
    )
    empty = client.get("/api/v1/technical-evidence?symbol=BTC/USDT&interval=1m")
    latest = client.get("/api/v1/technical-evidence/latest?symbol=BTC/USDT&interval=1m")
    unknown = client.get("/api/v1/technical-evidence?symbol=ETH/USDT")
    assert empty.status_code == 200
    assert empty.json()["empty"] is True
    assert empty.json()["detail"] == "No verified technical evidence"
    assert empty.json()["records"] == []
    assert empty.json()["execution_enabled"] is False
    assert latest.json()["record"] is None
    assert "price" not in latest.json()
    assert unknown.status_code == 404
    assert "price" not in unknown.json()


def test_stored_evidence_exposes_provenance() -> None:
    client = TestClient(
        create_app(make_settings(), database_probe=lambda: "ok", evidence=MemoryEvidence([_view()]))
    )
    response = client.get(
        "/api/v1/technical-evidence/latest?symbol=BTC/USDT&interval=1m&evidence_type=swing_structure"
    )
    body = response.json()["record"]
    assert response.status_code == 200
    assert body["calculator_version"] == "technical-evidence-v1"
    assert body["input_candle_ids"] == [1, 2, 3, 4, 5]
    assert body["input_fingerprint"] == "ab" * 32
    assert body["freshness"] == "stale"
    assert body["provider"] == "binance_spot"
    assert "probability" not in body["result"]


def test_evidence_routes_do_not_call_a_market_provider() -> None:
    api = (ROOT / "app" / "api" / "technical_evidence.py").read_text(encoding="utf-8")
    service = (ROOT / "app" / "domains" / "market_intelligence" / "service.py").read_text(
        encoding="utf-8"
    )
    assert "binance" not in api.lower()
    assert "httpx" not in api
    assert "fetch_klines" not in api
    assert "fetch_klines" not in service
    assert "BinanceSpotProvider" not in service
