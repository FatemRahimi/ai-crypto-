from __future__ import annotations

from collections.abc import Iterator
from dataclasses import replace
from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import cast

import pytest
from app.core.config import get_settings
from app.core.database import create_db_engine
from app.domains.market_data.aggregates import (
    aggregate_trade_fingerprint,
    aggregate_window_fingerprint,
)
from app.domains.market_data.identity import MarketIdentity
from app.domains.market_data.providers.binance_spot import BinanceSpotProvider
from app.domains.market_data.records import CanonicalAggregateTrade
from app.domains.market_data.repository import MarketRepository
from app.domains.market_intelligence.observed_volume import (
    CALCULATOR_NAME,
    CALCULATOR_VERSION,
    COVERAGE_LIMITATION,
    ObservedBucket,
    VolumeAggregate,
    calculate_observed_volume,
    derived_share,
    parameter_hash,
    profile_input_fingerprint,
)
from app.domains.market_intelligence.observed_volume_repository import ObservedVolumeRepository
from app.domains.market_intelligence.observed_volume_service import (
    ObservedVolumeReport,
    ObservedVolumeService,
)
from app.domains.market_intelligence.persistence import (
    ObservedVolumeBucketRow,
    ObservedVolumeEvidenceRow,
)
from app.main import create_app
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from tests.conftest import make_settings

IDENTITY = MarketIdentity(
    provider="test_provider",
    market_type="spot",
    base_asset="BTC",
    quote_asset="USDT",
    provider_symbol="TESTOBSERVEDUSDT",
    canonical_symbol="BTC/USDT",
)
START = datetime(2026, 10, 15, 12, 0, tzinfo=UTC)
END = START + timedelta(minutes=5)
NOW = END + timedelta(minutes=1)
FINGERPRINT = "a" * 64
ENDPOINT = "GET /api/v3/aggTrades"
NORMALIZATION = "binance-public-v1"


def _row(
    aggregate_id: int,
    price: str,
    quantity: str,
    when: datetime,
    *,
    fingerprint: str = FINGERPRINT,
    maker: bool = False,
    first: int | None = None,
    last: int | None = None,
) -> VolumeAggregate:
    return VolumeAggregate(
        aggregate_trade_id=aggregate_id,
        price=Decimal(price),
        quantity=Decimal(quantity),
        event_time=when,
        content_fingerprint=fingerprint,
        first_trade_id=aggregate_id if first is None else first,
        last_trade_id=aggregate_id if last is None else last,
        buyer_is_maker=maker,
    )


def _trade(
    aggregate_id: int,
    price: str,
    quantity: str,
    when: datetime,
    *,
    maker: bool = False,
    first: int | None = None,
    last: int | None = None,
    ingested: datetime | None = None,
) -> CanonicalAggregateTrade:
    first_id = aggregate_id if first is None else first
    last_id = first_id if last is None else last
    amount = Decimal(price)
    size = Decimal(quantity)
    fingerprint = aggregate_trade_fingerprint(
        aggregate_trade_id=aggregate_id,
        price=amount,
        quantity=size,
        event_time=when,
        first_trade_id=first_id,
        last_trade_id=last_id,
        buyer_is_maker=maker,
    )
    return CanonicalAggregateTrade(
        provider=IDENTITY.provider,
        canonical_symbol=IDENTITY.canonical_symbol,
        provider_symbol=IDENTITY.provider_symbol,
        market_type=IDENTITY.market_type,
        aggregate_trade_id=aggregate_id,
        price=amount,
        quantity=size,
        event_time=when,
        first_trade_id=first_id,
        last_trade_id=last_id,
        buyer_is_maker=maker,
        ingested_at=ingested or when,
        content_fingerprint=fingerprint,
        endpoint=ENDPOINT,
        normalization_version=NORMALIZATION,
    )


def _store(session: Session, trades: list[CanonicalAggregateTrade]) -> int:
    repository = MarketRepository(session)
    market_id = repository.ensure_market(IDENTITY)
    repository.insert_aggregate_trades(market_id, trades)
    session.commit()
    return market_id


def _window(
    session: Session,
    market_id: int,
    trades: list[CanonicalAggregateTrade],
    *,
    start: datetime = START,
    end: datetime = END,
    completeness: str = "COMPLETENESS_UNKNOWN",
    gap_details: dict[str, object] | None = None,
    checked_at: datetime = NOW,
) -> None:
    MarketRepository(session).insert_aggregate_window(
        market_id,
        requested_start=start,
        requested_end=end,
        first_event_time=trades[0].event_time if trades else None,
        last_event_time=trades[-1].event_time if trades else None,
        first_aggregate_id=trades[0].aggregate_trade_id if trades else None,
        last_aggregate_id=trades[-1].aggregate_trade_id if trades else None,
        aggregate_trade_count=len(trades),
        underlying_first_trade_id=min((trade.first_trade_id for trade in trades), default=None),
        underlying_last_trade_id=max((trade.last_trade_id for trade in trades), default=None),
        inserted=len(trades),
        duplicates=0,
        conflicts=0,
        completeness=completeness,
        gap_details=gap_details,
        checked_at=checked_at,
        input_fingerprint=aggregate_window_fingerprint(trades),
        endpoint=ENDPOINT,
        normalization_version=NORMALIZATION,
    )
    session.commit()


@pytest.fixture
def sessions() -> Iterator[sessionmaker[Session]]:
    engine = create_db_engine(get_settings())
    connection = engine.connect()
    outer = connection.begin()
    factory = sessionmaker(
        bind=connection,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )
    try:
        yield factory
    finally:
        outer.rollback()
        connection.close()
        engine.dispose()


def test_one_aggregate_is_one_exact_price_bucket() -> None:
    draft = calculate_observed_volume([_row(1, "10.50", "0.125", START)], start=START, end=END)
    assert draft.sufficiency == "OBSERVED"
    assert draft.buckets == (
        ObservedBucket(
            price=Decimal("10.50"),
            observed_base_volume=Decimal("0.125"),
            aggregate_count=1,
            derived_share=Decimal("1.000000000000000000"),
        ),
    )
    assert draft.observed_poc_price == Decimal("10.50")


def test_same_price_quantities_sum() -> None:
    draft = calculate_observed_volume(
        [_row(1, "10", "0.1", START), _row(2, "10", "0.2", START)],
        start=START,
        end=END,
    )
    assert draft.buckets[0].observed_base_volume == Decimal("0.3")
    assert draft.buckets[0].aggregate_count == 2
    assert type(draft.total_observed_base_volume) is Decimal
    assert draft.total_observed_base_volume == Decimal("0.3")


def test_distinct_prices_stay_separate_and_ordered() -> None:
    draft = calculate_observed_volume(
        [
            _row(3, "30", "1", START),
            _row(1, "10", "1", START),
            _row(2, "20", "1", START),
        ],
        start=START,
        end=END,
    )
    assert [bucket.price for bucket in draft.buckets] == [
        Decimal("10"),
        Decimal("20"),
        Decimal("30"),
    ]


def test_largest_bucket_is_the_observed_poc() -> None:
    draft = calculate_observed_volume(
        [_row(1, "10", "1", START), _row(2, "20", "5", START)],
        start=START,
        end=END,
    )
    assert draft.observed_poc_price == Decimal("20")
    assert draft.poc_tie is False
    assert draft.poc_tie_count == 1


def test_exact_tie_selects_the_lower_price_and_keeps_the_count() -> None:
    draft = calculate_observed_volume(
        [_row(2, "20", "5", START), _row(1, "10", "5", START)],
        start=START,
        end=END,
    )
    assert draft.observed_poc_price == Decimal("10")
    assert draft.poc_tie is True
    assert draft.poc_tie_count == 2


def test_decimal_scale_is_preserved_and_share_is_derived() -> None:
    assert derived_share(Decimal("1"), Decimal("3")) == Decimal("0.333333333333333333")
    assert derived_share(Decimal("2"), Decimal("3")) == Decimal("0.666666666666666667")
    draft = calculate_observed_volume(
        [
            _row(1, "10", "0.000000000000000001", START),
            _row(2, "10", "0.000000000000000002", START),
        ],
        start=START,
        end=END,
    )
    assert draft.total_observed_base_volume == Decimal("0.000000000000000003")
    assert draft.buckets[0].observed_base_volume == Decimal("0.000000000000000003")


def test_missing_prices_are_not_invented() -> None:
    draft = calculate_observed_volume(
        [_row(1, "10", "1", START), _row(2, "12", "1", START)],
        start=START,
        end=END,
    )
    assert [bucket.price for bucket in draft.buckets] == [Decimal("10"), Decimal("12")]


def test_aggregated_trade_span_stays_at_its_stored_price() -> None:
    draft = calculate_observed_volume(
        [_row(1, "50", "1.25", START, first=10, last=14)],
        start=START,
        end=END,
    )
    assert len(draft.buckets) == 1
    assert draft.buckets[0].price == Decimal("50")
    assert draft.buckets[0].observed_base_volume == Decimal("1.25")
    assert draft.buckets[0].aggregate_count == 1


def test_buyer_is_maker_changes_provenance_identity_and_not_the_sum() -> None:
    """content_fingerprint includes buyer_is_maker.

    That inclusion is intentional and stronger than the base-quantity sum.
    """
    maker_off = aggregate_trade_fingerprint(
        aggregate_trade_id=7,
        price=Decimal("10"),
        quantity=Decimal("1.5"),
        event_time=START,
        first_trade_id=7,
        last_trade_id=7,
        buyer_is_maker=False,
    )
    maker_on = aggregate_trade_fingerprint(
        aggregate_trade_id=7,
        price=Decimal("10"),
        quantity=Decimal("1.5"),
        event_time=START,
        first_trade_id=7,
        last_trade_id=7,
        buyer_is_maker=True,
    )
    off = _row(7, "10", "1.5", START, fingerprint=maker_off, maker=False)
    on = _row(7, "10", "1.5", START, fingerprint=maker_on, maker=True)
    assert profile_input_fingerprint([off]) != profile_input_fingerprint([on])
    left = calculate_observed_volume([off], start=START, end=END)
    right = calculate_observed_volume([on], start=START, end=END)
    assert left.total_observed_base_volume == right.total_observed_base_volume == Decimal("1.5")
    assert "delta" not in ObservedBucket.__dataclass_fields__
    assert "buyer_is_maker" not in ObservedBucket.__dataclass_fields__
    conflict = calculate_observed_volume([off, on], start=START, end=END)
    assert conflict.sufficiency == "INVALID"
    assert conflict.observed_poc_price is None


def test_only_event_time_inside_the_window_is_used() -> None:
    draft = calculate_observed_volume(
        [
            _row(1, "10", "100", START - timedelta(microseconds=1)),
            _row(2, "10", "1", START),
            _row(3, "10", "2", END),
            _row(4, "10", "100", END + timedelta(microseconds=1)),
        ],
        start=START,
        end=END,
    )
    assert draft.input_aggregate_count == 2
    assert draft.total_observed_base_volume == Decimal("3")
    assert draft.first_event_time == START
    assert draft.last_event_time == END


def test_volume_aggregate_has_no_ingested_at_membership_field() -> None:
    assert "ingested_at" not in VolumeAggregate.__dataclass_fields__


def test_empty_window_is_insufficient_without_a_poc() -> None:
    draft = calculate_observed_volume([], start=START, end=END)
    assert draft.sufficiency == "INSUFFICIENT"
    assert draft.observed_poc_price is None
    assert draft.buckets == ()
    assert draft.limitation == (
        "No stored aggregate trades in the requested window. "
        "This is not proof the market was idle."
    )


def test_conflicting_aggregate_is_invalid_without_a_poc() -> None:
    draft = calculate_observed_volume(
        [_row(1, "10", "1", START), _row(1, "11", "1", START, fingerprint="b" * 64)],
        start=START,
        end=END,
    )
    assert draft.sufficiency == "INVALID"
    assert draft.reason == "conflicting_aggregate_content"
    assert draft.observed_poc_price is None
    assert draft.buckets == ()


def test_malformed_values_fail_closed() -> None:
    too_fine = calculate_observed_volume(
        [_row(1, "1.0000000000000000001", "1", START)],
        start=START,
        end=END,
    )
    assert too_fine.sufficiency == "INVALID"
    assert too_fine.observed_poc_price is None
    floated = _row(1, "10", "1", START)
    floated = replace(floated, quantity=cast(Decimal, 0.1))
    rejected = calculate_observed_volume([floated], start=START, end=END)
    assert rejected.sufficiency == "INVALID"
    assert rejected.observed_poc_price is None
    overflow = calculate_observed_volume(
        [
            _row(1, "10", "60000000000000000000", START),
            _row(2, "11", "60000000000000000000", START),
        ],
        start=START,
        end=END,
    )
    assert overflow.sufficiency == "INVALID"
    assert overflow.buckets == ()


def test_calculator_source_does_not_call_float() -> None:
    source = (
        Path(__file__).parents[1] / "app" / "domains" / "market_intelligence" / "observed_volume.py"
    ).read_text(encoding="utf-8")
    assert "float(" not in source


def test_identical_inputs_and_reversed_order_share_one_fingerprint() -> None:
    rows = [_row(2, "20", "1", START), _row(1, "10", "2", END)]
    assert profile_input_fingerprint(rows) == profile_input_fingerprint(list(reversed(rows)))
    assert parameter_hash(START, END) == parameter_hash(START, END)
    first = calculate_observed_volume(rows, start=START, end=END)
    second = calculate_observed_volume(list(reversed(rows)), start=START, end=END)
    assert first.input_fingerprint == second.input_fingerprint
    assert first.parameters_hash == second.parameters_hash
    assert first.calculator_name == CALCULATOR_NAME
    assert first.calculator_version == CALCULATOR_VERSION


def test_material_changes_and_parameters_change_identity() -> None:
    base = _row(1, "10", "1", START)
    changed_price = profile_input_fingerprint([_row(1, "11", "1", START)])
    changed_quantity = profile_input_fingerprint([_row(1, "10", "2", START)])
    assert profile_input_fingerprint([base]) != changed_price
    assert profile_input_fingerprint([base]) != changed_quantity
    moved = _row(1, "10", "1", START + timedelta(seconds=1))
    assert profile_input_fingerprint([base]) != profile_input_fingerprint([moved])
    inside = calculate_observed_volume([base], start=START, end=END)
    outside = calculate_observed_volume(
        [_row(1, "10", "1", END + timedelta(microseconds=1))],
        start=START,
        end=END,
    )
    assert inside.input_fingerprint != outside.input_fingerprint
    assert inside.parameters_hash != parameter_hash(START, END + timedelta(seconds=1))[0]


def test_duplicate_rows_count_once() -> None:
    draft = calculate_observed_volume(
        [_row(1, "10", "1", START), _row(1, "10", "1", START)],
        start=START,
        end=END,
    )
    assert draft.input_aggregate_count == 1
    assert draft.buckets[0].aggregate_count == 1


def test_largest_aggregate_share_is_descriptive() -> None:
    draft = calculate_observed_volume(
        [_row(1, "10", "9", START), _row(2, "11", "1", START)],
        start=START,
        end=END,
    )
    assert draft.largest_aggregate_base_quantity == Decimal("9")
    assert draft.derived_largest_share == derived_share(Decimal("9"), Decimal("10"))
    assert draft.observed_poc_price == Decimal("10")


def test_stored_calculation_is_idempotent_and_keeps_unknown_completeness(
    sessions: sessionmaker[Session],
) -> None:
    with sessions() as session:
        _store(session, [_trade(1, "10.50", "0.1", START)])
    service = ObservedVolumeService(sessions, IDENTITY)
    first = service.calculate(START, END, now=NOW)
    second = service.calculate(START, END, now=NOW + timedelta(minutes=5))
    view = service.read(start=START, end=END, limit=10)
    assert first.inserted == 1
    assert first.sufficiency == "OBSERVED"
    assert first.source_completeness == "COMPLETENESS_UNKNOWN"
    assert first.limitation == COVERAGE_LIMITATION
    assert second.duplicates == 1
    assert second.conflicts == 0
    assert second.evidence_id == first.evidence_id
    assert len(view) == 1
    assert view[0].calculated_at == NOW
    assert view[0].calculator_version == CALCULATOR_VERSION
    assert view[0].source_completeness == "COMPLETENESS_UNKNOWN"
    assert view[0].source_details["attachment"] == "not_identified"
    assert view[0].source_details["coverage_claim"] == "not_proven"


def test_unknown_completeness_can_still_be_measured(
    sessions: sessionmaker[Session],
) -> None:
    trade = _trade(1, "10", "1", START)
    with sessions() as session:
        market_id = _store(session, [trade])
        _window(
            session,
            market_id,
            [trade],
            completeness="COMPLETE",
            gap_details={
                "reason": "clock_window_coverage_not_proven",
                "saw_full_page": True,
                "page_was_short": False,
                "page_count": 2,
                "retrieval_stop": "cap",
                "observed_aggregate_id_discontinuity": True,
                "gaps": [{"after_aggregate_id": 1, "next_aggregate_id": 3}],
            },
        )
    view = ObservedVolumeService(sessions, IDENTITY).calculate(START, END, now=NOW)
    stored = ObservedVolumeService(sessions, IDENTITY).read(start=START, end=END, limit=1)[0]
    assert view.sufficiency == "OBSERVED"
    assert view.source_completeness == "COMPLETENESS_UNKNOWN"
    assert stored.source_completeness == "COMPLETENESS_UNKNOWN"
    assert stored.source_details["attachment"] == "identified"
    assert stored.source_details["prior_report_completeness"] == "COMPLETE"
    assert stored.source_details["saw_full_page"] is True
    assert stored.source_details["retrieval_stop"] == "cap"
    assert stored.source_details["page_count"] == 2
    assert stored.source_details["observed_aggregate_id_discontinuity"] is True
    assert stored.source_details["coverage_claim"] == "not_proven"
    assert stored.sufficiency == "OBSERVED"


def test_disagreeing_or_non_matching_reports_are_not_selected(
    sessions: sessionmaker[Session],
) -> None:
    trade = _trade(1, "10", "1", START)
    with sessions() as session:
        market_id = _store(session, [trade])
        _window(
            session,
            market_id,
            [trade],
            completeness="COMPLETENESS_UNKNOWN",
            gap_details={"saw_full_page": False, "retrieval_stop": "short_page"},
            checked_at=NOW,
        )
        _window(
            session,
            market_id,
            [trade],
            completeness="COMPLETE",
            gap_details={"saw_full_page": True, "retrieval_stop": "cap"},
            checked_at=NOW + timedelta(seconds=1),
        )
        _window(
            session,
            market_id,
            [trade],
            start=START,
            end=END + timedelta(hours=1),
            completeness="COMPLETE",
            gap_details={"saw_full_page": True, "retrieval_stop": "cap"},
        )
    ObservedVolumeService(sessions, IDENTITY).calculate(START, END, now=NOW)
    stored = ObservedVolumeService(sessions, IDENTITY).read(start=START, end=END, limit=1)[0]
    assert stored.source_completeness == "COMPLETENESS_UNKNOWN"
    assert stored.source_details["attachment"] == "not_identified"
    assert stored.source_details["saw_full_page"] is None
    assert stored.source_details["prior_report_completeness"] is None


def test_empty_store_is_insufficient_and_a_read_cap_is_invalid(
    sessions: sessionmaker[Session],
) -> None:
    empty = ObservedVolumeService(sessions, IDENTITY).calculate(START, END, now=NOW)
    assert empty.sufficiency == "INSUFFICIENT"
    assert empty.observed_poc_price is None
    assert empty.source_completeness == "COMPLETENESS_UNKNOWN"
    with sessions() as session:
        _store(
            session,
            [_trade(1, "10", "1", START), _trade(2, "11", "1", START + timedelta(seconds=1))],
        )
    capped = ObservedVolumeService(sessions, IDENTITY, max_rows=1).calculate(START, END, now=NOW)
    assert capped.sufficiency == "INVALID"
    assert capped.observed_poc_price is None
    assert capped.source_completeness == "INVALID"
    stored = ObservedVolumeService(sessions, IDENTITY, max_rows=1).read(limit=10)
    invalid = [row for row in stored if row.sufficiency == "INVALID"]
    assert invalid[0].buckets == ()
    assert invalid[0].source_details["reason"] == "stored_row_read_cap_reached"
    assert invalid[0].source_details["read_cap"] == 1


def test_membership_uses_event_time_not_ingested_at(sessions: sessionmaker[Session]) -> None:
    with sessions() as session:
        _store(
            session,
            [
                _trade(1, "10", "1", START, ingested=END + timedelta(days=1)),
                _trade(2, "10", "2", END, ingested=START - timedelta(days=2)),
                _trade(
                    3,
                    "10",
                    "100",
                    END + timedelta(microseconds=1),
                    ingested=START,
                ),
                _trade(4, "10", "100", START - timedelta(microseconds=1), ingested=START),
            ],
        )
    report = ObservedVolumeService(sessions, IDENTITY).calculate(START, END, now=NOW)
    assert report.sufficiency == "OBSERVED"
    view = ObservedVolumeService(sessions, IDENTITY).read(start=START, end=END, limit=1)[0]
    assert view.input_aggregate_count == 2
    assert view.total_observed_base_volume == Decimal("3")


def test_backfill_creates_a_new_version_and_preserves_the_old_one(
    sessions: sessionmaker[Session],
) -> None:
    with sessions() as session:
        _store(session, [_trade(1, "10", "1", START)])
    service = ObservedVolumeService(sessions, IDENTITY)
    first = service.calculate(START, END, now=NOW)
    with sessions() as session:
        _store(
            session,
            [
                _trade(
                    2,
                    "9",
                    "5",
                    START + timedelta(seconds=1),
                    ingested=NOW + timedelta(minutes=1),
                )
            ],
        )
    second = service.calculate(START, END, now=NOW + timedelta(minutes=2))
    history = service.read(start=START, end=END, limit=10)
    assert first.input_fingerprint != second.input_fingerprint
    assert second.inserted == 1
    assert second.observed_poc_price == Decimal("9")
    assert {row.evidence_id for row in history} == {first.evidence_id, second.evidence_id}
    old = next(row for row in history if row.evidence_id == first.evidence_id)
    assert old.observed_poc_price == Decimal("10")
    assert old.calculated_at == NOW
    assert old.input_fingerprint == first.input_fingerprint


def test_changed_window_is_a_new_parameter_identity(sessions: sessionmaker[Session]) -> None:
    with sessions() as session:
        _store(session, [_trade(1, "10", "1", START)])
    service = ObservedVolumeService(sessions, IDENTITY)
    first = service.calculate(START, END, now=NOW)
    second = service.calculate(START, END + timedelta(seconds=1), now=NOW)
    assert first.parameters_hash != second.parameters_hash
    assert len(service.read(limit=10)) == 2


def test_conflict_result_does_not_replace_stored_evidence(
    sessions: sessionmaker[Session],
) -> None:
    draft = calculate_observed_volume([_row(1, "10", "1", START)], start=START, end=END)
    details: dict[str, object] = {
        "attachment": "not_identified",
        "coverage_claim": "not_proven",
        "reason": "no_single_retrieval_report_identifies_this_row_set",
    }
    with sessions() as session:
        market_id = MarketRepository(session).ensure_market(IDENTITY)
        repository = ObservedVolumeRepository(session)
        first = repository.save(
            market_id,
            draft,
            requested_start=START,
            requested_end=END,
            source_completeness="COMPLETENESS_UNKNOWN",
            source_details=details,
            calculated_at=NOW,
        )
        second = repository.save(
            market_id,
            replace(draft, observed_poc_price=Decimal("99")),
            requested_start=START,
            requested_end=END,
            source_completeness="COMPLETENESS_UNKNOWN",
            source_details=details,
            calculated_at=NOW + timedelta(minutes=1),
        )
        session.commit()
        stored = session.get(ObservedVolumeEvidenceRow, first.row_id)
        assert stored is not None
        assert second.outcome == "conflict"
        assert second.row_id == first.row_id
        assert stored.observed_poc_price == Decimal("10")
        assert stored.calculated_at == NOW


def test_get_without_evidence_is_an_honest_empty_state(sessions: sessionmaker[Session]) -> None:
    service = ObservedVolumeService(sessions, IDENTITY)
    client = TestClient(
        create_app(make_settings(), database_probe=lambda: "ok", observed_volume=service)
    )
    before = _counts(sessions)
    response = client.get("/api/v1/observed-volume?symbol=BTC/USDT")
    assert response.status_code == 200
    body = response.json()
    assert body["empty"] is True
    assert body["records"] == []
    assert body["detail"] == "No observed volume-at-price evidence has been calculated or stored."
    assert body["execution_enabled"] is False
    assert _counts(sessions) == before


def test_get_returns_the_stored_measurement_without_mutation_or_calculation(
    sessions: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = {"provider": 0}

    def fetched(*args: object, **kwargs: object) -> None:
        del args, kwargs
        calls["provider"] += 1
        raise AssertionError("provider fetch")

    monkeypatch.setattr(BinanceSpotProvider, "fetch_aggregate_trades", fetched)
    monkeypatch.setattr(BinanceSpotProvider, "fetch_klines", fetched)
    monkeypatch.setattr(BinanceSpotProvider, "fetch_recent_trades", fetched)
    monkeypatch.setattr(BinanceSpotProvider, "fetch_book_ticker", fetched)

    class Spy(ObservedVolumeService):
        def calculate(
            self,
            start: datetime,
            end: datetime,
            *,
            now: datetime | None = None,
        ) -> ObservedVolumeReport:
            del start, end, now
            raise AssertionError("GET calculated")

    with sessions() as session:
        _store(session, [_trade(1, "10.50", "0.1", START), _trade(2, "11.00", "0.1", END)])
    service = Spy(sessions, IDENTITY)
    ObservedVolumeService.calculate(service, START, END, now=NOW)
    client = TestClient(
        create_app(make_settings(), database_probe=lambda: "ok", observed_volume=service)
    )
    before = _counts(sessions)
    response = client.get("/api/v1/observed-volume?symbol=BTC/USDT")
    assert response.status_code == 200
    assert calls["provider"] == 0
    assert _counts(sessions) == before
    body = response.json()
    record = body["records"][0]
    assert body["empty"] is False
    assert record["sufficiency"] == "OBSERVED"
    assert record["source_completeness"] == "COMPLETENESS_UNKNOWN"
    assert record["source_limitation"] == COVERAGE_LIMITATION
    assert Decimal(record["observed_poc_price"]) == Decimal("10.50")
    assert Decimal(record["buckets"][0]["observed_base_volume"]) == Decimal("0.1")
    assert "e" not in record["observed_poc_price"].lower()
    assert record["poc_tie"] is True
    assert record["poc_tie_count"] == 2
    assert _banned_keys(body) == set()
    assert record["calculator_name"] == CALCULATOR_NAME
    assert record["bucket_method"] == "exact_price"
    assert record["volume_definition"] == "base_quantity"


def test_read_api_normalizes_timestamps_to_utc() -> None:
    from app.api.observed_volume import as_utc

    local = datetime(2026, 10, 16, 2, 40, tzinfo=timezone(timedelta(hours=1)))
    stamped = as_utc(local)
    assert stamped == datetime(2026, 10, 16, 1, 40, tzinfo=UTC)
    assert stamped.utcoffset() == timedelta(0)


def test_calculation_modules_do_not_call_a_provider() -> None:
    root = Path(__file__).parents[1]
    names = [
        "app/domains/market_intelligence/observed_volume.py",
        "app/domains/market_intelligence/observed_volume_service.py",
        "app/domains/market_intelligence/observed_volume_repository.py",
        "app/api/observed_volume.py",
    ]
    for name in names:
        text = (root / name).read_text(encoding="utf-8")
        assert "BinanceSpotProvider" not in text
        assert "httpx" not in text
        assert "fetch_aggregate_trades" not in text


def test_later_report_does_not_rewrite_the_first_evidence(
    sessions: sessionmaker[Session],
) -> None:
    trade = _trade(1, "10", "1", START)
    with sessions() as session:
        market_id = _store(session, [trade])
    service = ObservedVolumeService(sessions, IDENTITY)
    service.calculate(START, END, now=NOW)
    with sessions() as session:
        _window(
            session,
            market_id,
            [trade],
            gap_details={"saw_full_page": True, "retrieval_stop": "cap"},
        )
    again = service.calculate(START, END, now=NOW + timedelta(minutes=1))
    stored = service.read(start=START, end=END, limit=5)
    assert again.duplicates == 1
    assert again.conflicts == 0
    assert len(stored) == 1
    assert stored[0].source_details["attachment"] == "not_identified"


def _counts(sessions: sessionmaker[Session]) -> tuple[int, int]:
    with sessions() as session:
        evidence = session.scalar(select(func.count()).select_from(ObservedVolumeEvidenceRow))
        buckets = session.scalar(select(func.count()).select_from(ObservedVolumeBucketRow))
    return int(evidence or 0), int(buckets or 0)


def _banned_keys(value: object) -> set[str]:
    banned = {"vah", "val", "hvn", "lvn", "tpo", "delta", "cvd", "signal", "probability"}
    found: set[str] = set()

    def walk(item: object) -> None:
        if isinstance(item, dict):
            for key, child in item.items():
                if key.lower() in banned:
                    found.add(key.lower())
                walk(child)
        elif isinstance(item, list):
            for child in item:
                walk(child)

    walk(value)
    return found
