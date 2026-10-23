"""Ingest and read stored USD-M funding observations.

Read methods do not call the provider.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol

from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings
from app.core.database import create_db_engine
from app.domains.market_data.funding import (
    FUNDING_ENDPOINT,
    FUNDING_NORMALIZATION_VERSION,
    CanonicalFunding,
    FundingCompleteness,
    PreparedFunding,
    assess_funding_completeness,
    funding_window_fingerprint,
    normalize_funding_row,
    prepare_funding_rows,
)
from app.domains.market_data.funding_repository import FundingRepository
from app.domains.market_data.identity import BTC_USDT_USD_M_PERPETUAL, MarketIdentity
from app.domains.market_data.persistence import FundingObservationRow, FundingWindowRow
from app.domains.market_data.providers.binance_usdm import BinanceUsdMProvider, FundingRetrieval
from app.domains.market_data.quality import Rejection, ensure_utc

logger = logging.getLogger("app.market_data.funding")

MAX_FUNDING_ROWS_PER_RUN = 5000
DEFAULT_MAX_FUNDING_ROWS = 1000
EMPTY_LIMITATION = (
    "The provider returned no funding rows for this request. "
    "That is not a zero funding rate and not proof the market had no funding."
)
UNKNOWN_LIMITATION = (
    "Stored funding observations are available. "
    "Complete historical funding coverage is not proven."
)


@dataclass(frozen=True, slots=True)
class FundingWindowReport:
    canonical_symbol: str
    provider: str
    provider_symbol: str
    market_type: str
    requested_start: datetime
    requested_end: datetime
    first_funding_time: datetime | None
    last_funding_time: datetime | None
    row_count: int
    inserted: int
    duplicates: int
    conflicts: int
    completeness: FundingCompleteness
    details: dict[str, object]
    checked_at: datetime
    input_fingerprint: str
    endpoint: str
    normalization_version: str


class FundingSource(Protocol):
    def fetch_funding(
        self,
        *,
        provider_symbol: str,
        start: datetime,
        end: datetime,
        max_rows: int,
    ) -> FundingRetrieval:
        """Return raw funding pages and the exchange-info contract type."""


class FundingDataService:
    def __init__(
        self,
        sessions: sessionmaker[Session],
        provider: FundingSource,
        identity: MarketIdentity = BTC_USDT_USD_M_PERPETUAL,
    ) -> None:
        if identity != BTC_USDT_USD_M_PERPETUAL:
            raise ValueError("funding service is only the USD-M BTCUSDT perpetual")
        self._sessions = sessions
        self._provider = provider
        self.identity = identity

    @classmethod
    def from_settings(cls, settings: Settings) -> FundingDataService:
        engine = create_db_engine(settings)
        sessions = sessionmaker(bind=engine, expire_on_commit=False)
        return cls(sessions, BinanceUsdMProvider())

    def ingest(
        self,
        *,
        start: datetime,
        end: datetime,
        max_rows: int = DEFAULT_MAX_FUNDING_ROWS,
        now: datetime | None = None,
    ) -> FundingWindowReport:
        opened = ensure_utc(start)
        closed = ensure_utc(end)
        if isinstance(opened, Rejection) or isinstance(closed, Rejection):
            raise ValueError("start and end must be timezone-aware")
        if closed < opened:
            raise ValueError("end is before start")
        if max_rows < 1 or max_rows > MAX_FUNDING_ROWS_PER_RUN:
            raise ValueError(f"funding row cap is {MAX_FUNDING_ROWS_PER_RUN}")
        moment = now or datetime.now(UTC)
        retrieval = self._provider.fetch_funding(
            provider_symbol=self.identity.provider_symbol,
            start=opened,
            end=closed,
            max_rows=max_rows,
        )
        if retrieval.contract_type != "PERPETUAL":
            raise ValueError("exchange info did not confirm a USD-M perpetual")
        collected, invalid_reason = _collect(retrieval, self.identity, moment)
        if retrieval.stop == "no_progress":
            invalid_reason = invalid_reason or "pagination_no_progress"
        if invalid_reason is None:
            prepared = prepare_funding_rows(collected, start=opened, end=closed)
        else:
            prepared = PreparedFunding((), 0, 0, invalid_reason)
        blocked = prepared.invalid_reason is not None or retrieval.stop == "no_progress"
        status, reason = assess_funding_completeness(
            stop=retrieval.stop,
            invalid_reason=prepared.invalid_reason,
            conflicts=prepared.conflicts,
            row_count=0 if blocked else len(prepared.rows),
        )
        store = () if blocked else prepared.rows
        with self._sessions() as session:
            repository = FundingRepository(session)
            market_id = repository.ensure_market(self.identity)
            counts = repository.insert_observations(market_id, list(store))
            conflicts = prepared.conflicts + counts.conflicts
            if counts.conflicts:
                status = FundingCompleteness.INVALID
                reason = "conflicting_funding_content"
            fingerprint = funding_window_fingerprint(
                list(store),
                start=opened,
                end=closed,
            )
            details = _details(
                reason=reason,
                stop=retrieval.stop,
                saw_full_page=retrieval.saw_full_page,
                page_count=len(retrieval.pages),
                contract_type=retrieval.contract_type,
            )
            report = FundingWindowReport(
                canonical_symbol=self.identity.canonical_symbol,
                provider=self.identity.provider,
                provider_symbol=self.identity.provider_symbol,
                market_type=self.identity.market_type,
                requested_start=opened,
                requested_end=closed,
                first_funding_time=None if not store else store[0].funding_time,
                last_funding_time=None if not store else store[-1].funding_time,
                row_count=len(store),
                inserted=counts.inserted,
                duplicates=prepared.duplicates + counts.duplicates,
                conflicts=conflicts,
                completeness=status,
                details=details,
                checked_at=moment,
                input_fingerprint=fingerprint,
                endpoint=FUNDING_ENDPOINT,
                normalization_version=FUNDING_NORMALIZATION_VERSION,
            )
            repository.insert_window(
                market_id,
                requested_start=report.requested_start,
                requested_end=report.requested_end,
                first_funding_time=report.first_funding_time,
                last_funding_time=report.last_funding_time,
                row_count=report.row_count,
                inserted=report.inserted,
                duplicates=report.duplicates,
                conflicts=report.conflicts,
                completeness=report.completeness.value,
                details=report.details,
                checked_at=report.checked_at,
                input_fingerprint=report.input_fingerprint,
                endpoint=report.endpoint,
                normalization_version=report.normalization_version,
            )
            session.commit()
        return report

    def read(
        self,
        *,
        start: datetime | None,
        end: datetime | None,
        limit: int,
    ) -> tuple[list[FundingObservationRow], FundingWindowRow | None]:
        with self._sessions() as session:
            repository = FundingRepository(session)
            rows = repository.observations(self.identity, start=start, end=end, limit=limit)
            window = repository.latest_window(self.identity, start=start, end=end)
        return rows, window


def _collect(
    retrieval: FundingRetrieval,
    identity: MarketIdentity,
    ingested_at: datetime,
) -> tuple[list[CanonicalFunding], str | None]:
    collected: list[CanonicalFunding] = []
    for page in retrieval.pages:
        for row in page:
            normalized = normalize_funding_row(row, identity, ingested_at)
            if isinstance(normalized, Rejection):
                logger.info(
                    "funding_validation_failed provider=%s reason=%s",
                    identity.provider,
                    normalized.reason,
                )
                return [], normalized.reason
            collected.append(normalized)
    return collected, None


def _details(
    *,
    reason: str,
    stop: str,
    saw_full_page: bool,
    page_count: int,
    contract_type: str | None,
) -> dict[str, object]:
    if reason == "provider_returned_no_funding_rows":
        limitation = EMPTY_LIMITATION
    elif reason == "historical_funding_coverage_not_proven":
        limitation = UNKNOWN_LIMITATION
    else:
        limitation = "Rejected funding response stored no observations."
    return {
        "reason": reason,
        "retrieval_stop": stop,
        "saw_full_page": saw_full_page,
        "page_count": page_count,
        "contract_type": contract_type,
        "limitation": limitation,
        "cadence_assumed": False,
    }
