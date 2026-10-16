"""Calculate observed volume at price from aggregate trades that are already stored."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings
from app.core.database import create_db_engine
from app.domains.market_data.aggregates import aggregate_window_fingerprint
from app.domains.market_data.identity import BTC_USDT_SPOT, MarketIdentity
from app.domains.market_data.persistence import AggregateTradeRow, AggregateTradeWindowRow
from app.domains.market_data.records import CanonicalAggregateTrade
from app.domains.market_data.repository import MarketRepository
from app.domains.market_intelligence.observed_volume import (
    ObservedVolumeDraft,
    VolumeAggregate,
    calculate_observed_volume,
    capped_read_draft,
)
from app.domains.market_intelligence.observed_volume_repository import (
    ObservedVolumeRepository,
    canonical_json,
)
from app.domains.market_intelligence.persistence import (
    ObservedVolumeBucketRow,
    ObservedVolumeEvidenceRow,
)

MAX_OBSERVED_AGGREGATES = 5000


@dataclass(frozen=True, slots=True)
class ObservedVolumeReport:
    inserted: int
    duplicates: int
    conflicts: int
    sufficiency: str
    source_completeness: str
    evidence_id: int | None
    observed_poc_price: Decimal | None
    poc_tie_count: int | None
    poc_tie: bool | None
    input_fingerprint: str
    parameters_hash: str
    limitation: str


@dataclass(frozen=True, slots=True)
class ObservedBucketView:
    price: Decimal
    observed_base_volume: Decimal
    aggregate_count: int
    derived_share: Decimal


@dataclass(frozen=True, slots=True)
class ObservedVolumeView:
    evidence_id: int
    canonical_symbol: str
    provider: str
    provider_symbol: str
    market_type: str
    requested_start: datetime
    requested_end: datetime
    first_event_time: datetime | None
    last_event_time: datetime | None
    input_aggregate_count: int
    input_fingerprint: str
    parameters_hash: str
    parameters: dict[str, object]
    calculator_name: str
    calculator_version: str
    bucket_method: str
    volume_definition: str
    poc_tie_break: str
    source_completeness: str
    source_limitation: str
    source_details: dict[str, object]
    sufficiency: str
    total_observed_base_volume: Decimal | None
    observed_poc_price: Decimal | None
    poc_tie_count: int | None
    poc_tie: bool | None
    largest_aggregate_base_quantity: Decimal | None
    derived_largest_share: Decimal | None
    calculated_at: datetime
    buckets: tuple[ObservedBucketView, ...]


class ObservedVolumeService:
    def __init__(
        self,
        sessions: sessionmaker[Session],
        identity: MarketIdentity = BTC_USDT_SPOT,
        *,
        max_rows: int = MAX_OBSERVED_AGGREGATES,
    ) -> None:
        if max_rows < 1:
            raise ValueError("max_rows must be positive")
        self._sessions = sessions
        self.identity = identity
        self._max_rows = max_rows

    @classmethod
    def from_settings(cls, settings: Settings) -> ObservedVolumeService:
        engine = create_db_engine(settings)
        sessions = sessionmaker(bind=engine, expire_on_commit=False)
        return cls(sessions)

    def calculate(
        self,
        start: datetime,
        end: datetime,
        *,
        now: datetime | None = None,
    ) -> ObservedVolumeReport:
        self._require_window(start, end)
        moment = now or datetime.now(UTC)
        with self._sessions() as session:
            market = MarketRepository(session)
            market_id = market.ensure_market(self.identity)
            loaded = market.aggregate_trade_range(self.identity, start, end, self._max_rows + 1)
            windows = market.aggregate_windows_for_exact_bounds(self.identity, start, end)
            if len(loaded) > self._max_rows:
                draft = capped_read_draft(start, end, rows_seen=len(loaded))
                completeness, details = _cap_provenance(self._max_rows, len(loaded))
            else:
                draft = calculate_observed_volume(
                    [_volume(row) for row in loaded],
                    start=start,
                    end=end,
                )
                completeness, details = _provenance(
                    draft,
                    [_canonical(self.identity, row) for row in loaded],
                    windows,
                )
            outcome = ObservedVolumeRepository(session).save(
                market_id,
                draft,
                requested_start=start,
                requested_end=end,
                source_completeness=completeness,
                source_details=details,
                calculated_at=moment,
            )
            session.commit()
        return ObservedVolumeReport(
            inserted=1 if outcome.outcome == "inserted" else 0,
            duplicates=1 if outcome.outcome == "duplicate" else 0,
            conflicts=1 if outcome.outcome == "conflict" else 0,
            sufficiency=draft.sufficiency,
            source_completeness=completeness,
            evidence_id=outcome.row_id,
            observed_poc_price=draft.observed_poc_price,
            poc_tie_count=draft.poc_tie_count,
            poc_tie=draft.poc_tie,
            input_fingerprint=draft.input_fingerprint,
            parameters_hash=draft.parameters_hash,
            limitation=draft.limitation,
        )

    def read(
        self,
        *,
        start: datetime | None = None,
        end: datetime | None = None,
        limit: int = 20,
    ) -> list[ObservedVolumeView]:
        if (start is None) != (end is None):
            raise ValueError("start and end must be supplied together")
        if start is not None and end is not None:
            self._require_window(start, end)
        with self._sessions() as session:
            repository = ObservedVolumeRepository(session)
            rows = repository.list_evidence(self.identity, start, end, limit)
            grouped = repository.buckets_for([row.id for row in rows])
            return [_view(self.identity, row, grouped.get(row.id, [])) for row in rows]

    def _require_window(self, start: datetime, end: datetime) -> None:
        if start.tzinfo is None or start.utcoffset() is None:
            raise ValueError("start must be timezone-aware")
        if end.tzinfo is None or end.utcoffset() is None:
            raise ValueError("end must be timezone-aware")
        if start > end:
            raise ValueError("start must be at or before end")


def _volume(row: AggregateTradeRow) -> VolumeAggregate:
    return VolumeAggregate(
        aggregate_trade_id=row.aggregate_trade_id,
        price=row.price,
        quantity=row.quantity,
        event_time=row.event_time,
        content_fingerprint=row.content_fingerprint,
        first_trade_id=row.first_trade_id,
        last_trade_id=row.last_trade_id,
        buyer_is_maker=row.buyer_is_maker,
    )


def _canonical(identity: MarketIdentity, row: AggregateTradeRow) -> CanonicalAggregateTrade:
    return CanonicalAggregateTrade(
        provider=identity.provider,
        canonical_symbol=identity.canonical_symbol,
        provider_symbol=identity.provider_symbol,
        market_type=identity.market_type,
        aggregate_trade_id=row.aggregate_trade_id,
        price=row.price,
        quantity=row.quantity,
        event_time=row.event_time,
        first_trade_id=row.first_trade_id,
        last_trade_id=row.last_trade_id,
        buyer_is_maker=row.buyer_is_maker,
        ingested_at=row.ingested_at,
        content_fingerprint=row.content_fingerprint,
        endpoint=row.endpoint,
        normalization_version=row.normalization_version,
    )


def _provenance(
    draft: ObservedVolumeDraft,
    trades: list[CanonicalAggregateTrade],
    windows: list[AggregateTradeWindowRow],
) -> tuple[str, dict[str, object]]:
    if draft.sufficiency == "INVALID":
        return "INVALID", _details(attachment="not_identified", reason=draft.reason)
    used_ids = {row.aggregate_trade_id for row in draft.used}
    selected = [trade for trade in trades if trade.aggregate_trade_id in used_ids]
    expected = aggregate_window_fingerprint(selected)
    matches = [
        window
        for window in windows
        if window.input_fingerprint == expected and window.aggregate_trade_count == len(selected)
    ]
    agreed = _agreed_report(matches)
    if agreed is None:
        return "COMPLETENESS_UNKNOWN", _details(
            attachment="not_identified",
            reason="no_single_retrieval_report_identifies_this_row_set",
        )
    window, parsed = agreed
    copied = _copy_flags(parsed)
    if copied is None:
        return "COMPLETENESS_UNKNOWN", _details(
            attachment="not_identified",
            reason="no_single_retrieval_report_identifies_this_row_set",
        )
    return "COMPLETENESS_UNKNOWN", _details(
        attachment="identified",
        reason=_text(parsed.get("reason")),
        prior_report_completeness=window.completeness,
        **copied,
    )


def _cap_provenance(read_cap: int, rows_seen: int) -> tuple[str, dict[str, object]]:
    return "INVALID", _details(
        attachment="not_identified",
        reason="stored_row_read_cap_reached",
        read_cap=read_cap,
        rows_read_before_refusal=rows_seen,
    )


def _agreed_report(
    windows: list[AggregateTradeWindowRow],
) -> tuple[AggregateTradeWindowRow, dict[str, object]] | None:
    if not windows:
        return None
    signatures: list[tuple[str, dict[str, object]]] = []
    for window in windows:
        parsed = _parse_details(window.gap_details_json)
        if parsed is None:
            return None
        signatures.append((window.completeness + canonical_json(parsed), parsed))
    first = signatures[0][0]
    if any(signature != first for signature, _parsed in signatures):
        return None
    return windows[0], signatures[0][1]


def _parse_details(raw: str | None) -> dict[str, object] | None:
    if raw is None:
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, dict):
        return None
    return {str(key): value for key, value in parsed.items()}


def _copy_flags(parsed: dict[str, object]) -> dict[str, object] | None:
    saw_full_page = _bool_flag(parsed, "saw_full_page")
    discontinuity = _bool_flag(parsed, "observed_aggregate_id_discontinuity")
    page_was_short = _bool_flag(parsed, "page_was_short")
    page_count = _int_flag(parsed, "page_count")
    retrieval_stop = _text_flag(parsed, "retrieval_stop")
    gaps = _gaps(parsed)
    if (
        saw_full_page is _BAD
        or discontinuity is _BAD
        or page_was_short is _BAD
        or page_count is _BAD
        or retrieval_stop is _BAD
        or gaps is _BAD
    ):
        return None
    return {
        "saw_full_page": saw_full_page,
        "observed_aggregate_id_discontinuity": discontinuity,
        "page_was_short": page_was_short,
        "page_count": page_count,
        "retrieval_stop": retrieval_stop,
        "gaps": gaps,
    }


def _details(**flags: object) -> dict[str, object]:
    body: dict[str, object] = {
        "attachment": flags.get("attachment"),
        "coverage_claim": "not_proven",
        "prior_report_completeness": flags.get("prior_report_completeness"),
        "saw_full_page": flags.get("saw_full_page"),
        "observed_aggregate_id_discontinuity": flags.get("observed_aggregate_id_discontinuity"),
        "page_was_short": flags.get("page_was_short"),
        "page_count": flags.get("page_count"),
        "retrieval_stop": flags.get("retrieval_stop"),
        "reason": flags.get("reason"),
        "read_cap": flags.get("read_cap"),
        "rows_read_before_refusal": flags.get("rows_read_before_refusal"),
        "gaps": flags.get("gaps"),
    }
    return body


_BAD = object()


def _bool_flag(parsed: dict[str, object], key: str) -> bool | None | object:
    if key not in parsed or parsed[key] is None:
        return None
    value = parsed[key]
    if isinstance(value, bool):
        return value
    return _BAD


def _int_flag(parsed: dict[str, object], key: str) -> int | None | object:
    if key not in parsed or parsed[key] is None:
        return None
    value = parsed[key]
    if isinstance(value, bool) or not isinstance(value, int):
        return _BAD
    return value


def _text_flag(parsed: dict[str, object], key: str) -> str | None | object:
    if key not in parsed or parsed[key] is None:
        return None
    value = parsed[key]
    if isinstance(value, str):
        return value
    return _BAD


def _text(value: object) -> str | None:
    if isinstance(value, str):
        return value
    return None


def _gaps(parsed: dict[str, object]) -> list[dict[str, int]] | None | object:
    if "gaps" not in parsed or parsed["gaps"] is None:
        return None
    raw = parsed["gaps"]
    if not isinstance(raw, list):
        return _BAD
    gaps: list[dict[str, int]] = []
    for item in raw:
        if not isinstance(item, dict):
            return _BAD
        after = item.get("after_aggregate_id")
        nxt = item.get("next_aggregate_id")
        if isinstance(after, bool) or isinstance(nxt, bool):
            return _BAD
        if not isinstance(after, int) or not isinstance(nxt, int):
            return _BAD
        gaps.append({"after_aggregate_id": after, "next_aggregate_id": nxt})
    return gaps


def _view(
    identity: MarketIdentity,
    row: ObservedVolumeEvidenceRow,
    buckets: list[ObservedVolumeBucketRow],
) -> ObservedVolumeView:
    parameters = json.loads(row.parameters_json)
    details = json.loads(row.source_details_json)
    if not isinstance(parameters, dict) or not isinstance(details, dict):
        raise ValueError("stored observed volume evidence is unreadable")
    return ObservedVolumeView(
        evidence_id=row.id,
        canonical_symbol=identity.canonical_symbol,
        provider=identity.provider,
        provider_symbol=identity.provider_symbol,
        market_type=identity.market_type,
        requested_start=row.requested_start,
        requested_end=row.requested_end,
        first_event_time=row.first_event_time,
        last_event_time=row.last_event_time,
        input_aggregate_count=row.input_aggregate_count,
        input_fingerprint=row.input_fingerprint,
        parameters_hash=row.parameters_hash,
        parameters={str(key): value for key, value in parameters.items()},
        calculator_name=row.calculator_name,
        calculator_version=row.calculator_version,
        bucket_method=row.bucket_method,
        volume_definition=row.volume_definition,
        poc_tie_break=row.poc_tie_break,
        source_completeness=row.source_completeness,
        source_limitation=row.source_limitation,
        source_details={str(key): value for key, value in details.items()},
        sufficiency=row.sufficiency,
        total_observed_base_volume=row.total_observed_base_volume,
        observed_poc_price=row.observed_poc_price,
        poc_tie_count=row.poc_tie_count,
        poc_tie=row.poc_tie,
        largest_aggregate_base_quantity=row.largest_aggregate_base_quantity,
        derived_largest_share=row.derived_largest_share,
        calculated_at=row.calculated_at,
        buckets=tuple(
            ObservedBucketView(
                price=bucket.price,
                observed_base_volume=bucket.observed_base_volume,
                aggregate_count=bucket.aggregate_count,
                derived_share=bucket.derived_share,
            )
            for bucket in buckets
        ),
    )
