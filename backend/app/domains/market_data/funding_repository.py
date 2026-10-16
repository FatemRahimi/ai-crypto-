"""Persistence for USD-M funding observations. Conflicts are not overwritten."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domains.market_data.funding import CanonicalFunding
from app.domains.market_data.identity import MarketIdentity
from app.domains.market_data.persistence import FundingObservationRow, FundingWindowRow, MarketRow
from app.domains.market_data.repository import MarketRepository


@dataclass(frozen=True, slots=True)
class FundingWriteCounts:
    inserted: int
    duplicates: int
    conflicts: int


class FundingRepository:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._markets = MarketRepository(session)

    def ensure_market(self, identity: MarketIdentity) -> int:
        return self._markets.ensure_market(identity)

    def insert_observations(
        self,
        market_id: int,
        rows: list[CanonicalFunding],
    ) -> FundingWriteCounts:
        if not rows:
            return FundingWriteCounts(inserted=0, duplicates=0, conflicts=0)
        existing = {
            (row.funding_time, row.rate_type): row
            for row in self._session.scalars(
                select(FundingObservationRow).where(
                    FundingObservationRow.market_id == market_id,
                    FundingObservationRow.funding_time.in_([row.funding_time for row in rows]),
                )
            ).all()
        }
        fresh: list[CanonicalFunding] = []
        duplicates = 0
        conflicts = 0
        for row in rows:
            current = existing.get((row.funding_time, row.rate_type))
            if current is None:
                fresh.append(row)
                continue
            if current.content_fingerprint == row.content_fingerprint:
                duplicates += 1
            else:
                conflicts += 1
        if fresh:
            self._session.add_all(
                [
                    FundingObservationRow(
                        market_id=market_id,
                        symbol=row.symbol,
                        funding_time=row.funding_time,
                        funding_rate=row.funding_rate,
                        rate_type=row.rate_type,
                        content_fingerprint=row.content_fingerprint,
                        endpoint=row.endpoint,
                        normalization_version=row.normalization_version,
                        ingested_at=row.ingested_at,
                    )
                    for row in fresh
                ]
            )
            self._session.flush()
        return FundingWriteCounts(
            inserted=len(fresh),
            duplicates=duplicates,
            conflicts=conflicts,
        )

    def insert_window(
        self,
        market_id: int,
        *,
        requested_start: datetime,
        requested_end: datetime,
        first_funding_time: datetime | None,
        last_funding_time: datetime | None,
        row_count: int,
        inserted: int,
        duplicates: int,
        conflicts: int,
        completeness: str,
        details: dict[str, object],
        checked_at: datetime,
        input_fingerprint: str,
        endpoint: str,
        normalization_version: str,
    ) -> None:
        self._session.add(
            FundingWindowRow(
                market_id=market_id,
                requested_start=requested_start,
                requested_end=requested_end,
                first_funding_time=first_funding_time,
                last_funding_time=last_funding_time,
                row_count=row_count,
                inserted=inserted,
                duplicates=duplicates,
                conflicts=conflicts,
                completeness=completeness,
                details_json=json.dumps(details, sort_keys=True),
                checked_at=checked_at,
                input_fingerprint=input_fingerprint,
                endpoint=endpoint,
                normalization_version=normalization_version,
            )
        )
        self._session.flush()

    def observations(
        self,
        identity: MarketIdentity,
        *,
        start: datetime | None,
        end: datetime | None,
        limit: int,
    ) -> list[FundingObservationRow]:
        market_id = self._market_id(identity)
        if market_id is None:
            return []
        query = select(FundingObservationRow).where(FundingObservationRow.market_id == market_id)
        if start is not None:
            query = query.where(FundingObservationRow.funding_time >= start)
        if end is not None:
            query = query.where(FundingObservationRow.funding_time <= end)
        return list(
            self._session.scalars(
                query.order_by(
                    FundingObservationRow.funding_time.asc(),
                    FundingObservationRow.rate_type.asc(),
                ).limit(limit)
            ).all()
        )

    def latest_window(
        self,
        identity: MarketIdentity,
        *,
        start: datetime | None,
        end: datetime | None,
    ) -> FundingWindowRow | None:
        market_id = self._market_id(identity)
        if market_id is None:
            return None
        query = select(FundingWindowRow).where(FundingWindowRow.market_id == market_id)
        if start is not None and end is not None:
            query = query.where(
                FundingWindowRow.requested_start == start,
                FundingWindowRow.requested_end == end,
            )
        return self._session.scalar(
            query.order_by(FundingWindowRow.checked_at.desc(), FundingWindowRow.id.desc()).limit(1)
        )

    def _market_id(self, identity: MarketIdentity) -> int | None:
        return self._session.scalar(
            select(MarketRow.id).where(
                MarketRow.provider == identity.provider,
                MarketRow.provider_symbol == identity.provider_symbol,
                MarketRow.market_type == identity.market_type,
            )
        )
