"""Store observed volume-at-price evidence without rewriting an earlier measurement."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Literal

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.domains.market_data.identity import MarketIdentity
from app.domains.market_data.persistence import MarketRow
from app.domains.market_intelligence.observed_volume import (
    BUCKET_METHOD,
    POC_TIE_BREAK,
    VOLUME_DEFINITION,
    ObservedVolumeDraft,
)
from app.domains.market_intelligence.persistence import (
    ObservedVolumeBucketRow,
    ObservedVolumeEvidenceRow,
)


@dataclass(frozen=True, slots=True)
class SaveOutcome:
    outcome: Literal["inserted", "duplicate", "conflict"]
    row_id: int


def canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


class ObservedVolumeRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def save(
        self,
        market_id: int,
        draft: ObservedVolumeDraft,
        *,
        requested_start: datetime,
        requested_end: datetime,
        source_completeness: str,
        source_details: dict[str, object],
        calculated_at: datetime,
    ) -> SaveOutcome:
        details = canonical_json(source_details)
        existing = self._existing(market_id, draft)
        if existing is not None:
            return self._same_or_conflict(existing, draft)
        row = ObservedVolumeEvidenceRow(
            market_id=market_id,
            requested_start=requested_start,
            requested_end=requested_end,
            first_event_time=draft.first_event_time,
            last_event_time=draft.last_event_time,
            input_aggregate_count=draft.input_aggregate_count,
            input_fingerprint=draft.input_fingerprint,
            parameters_hash=draft.parameters_hash,
            parameters_json=canonical_json(draft.parameters),
            calculator_name=draft.calculator_name,
            calculator_version=draft.calculator_version,
            bucket_method=BUCKET_METHOD,
            volume_definition=VOLUME_DEFINITION,
            poc_tie_break=POC_TIE_BREAK,
            source_completeness=source_completeness,
            source_limitation=draft.limitation,
            source_details_json=details,
            sufficiency=draft.sufficiency,
            total_observed_base_volume=draft.total_observed_base_volume,
            observed_poc_price=draft.observed_poc_price,
            poc_tie_count=draft.poc_tie_count,
            poc_tie=draft.poc_tie,
            largest_aggregate_base_quantity=draft.largest_aggregate_base_quantity,
            derived_largest_share=draft.derived_largest_share,
            calculated_at=calculated_at,
        )
        try:
            with self._session.begin_nested():
                self._session.add(row)
                self._session.flush()
                self._session.add_all(self._bucket_rows(row.id, draft))
                self._session.flush()
        except IntegrityError:
            raced = self._existing(market_id, draft)
            if raced is None:
                raise
            return self._same_or_conflict(raced, draft)
        return SaveOutcome("inserted", row.id)

    def list_evidence(
        self,
        identity: MarketIdentity,
        start: datetime | None,
        end: datetime | None,
        limit: int,
    ) -> list[ObservedVolumeEvidenceRow]:
        market_id = self._market_id(identity)
        if market_id is None:
            return []
        query = select(ObservedVolumeEvidenceRow).where(
            ObservedVolumeEvidenceRow.market_id == market_id
        )
        if start is not None and end is not None:
            query = query.where(
                ObservedVolumeEvidenceRow.requested_start == start,
                ObservedVolumeEvidenceRow.requested_end == end,
            )
        return list(
            self._session.scalars(
                query.order_by(
                    ObservedVolumeEvidenceRow.calculated_at.desc(),
                    ObservedVolumeEvidenceRow.id.desc(),
                ).limit(limit)
            ).all()
        )

    def buckets_for(self, evidence_ids: list[int]) -> dict[int, list[ObservedVolumeBucketRow]]:
        if not evidence_ids:
            return {}
        rows = list(
            self._session.scalars(
                select(ObservedVolumeBucketRow)
                .where(ObservedVolumeBucketRow.evidence_id.in_(evidence_ids))
                .order_by(ObservedVolumeBucketRow.price.asc(), ObservedVolumeBucketRow.id.asc())
            ).all()
        )
        grouped: dict[int, list[ObservedVolumeBucketRow]] = {}
        for row in rows:
            grouped.setdefault(row.evidence_id, []).append(row)
        return grouped

    def _existing(
        self,
        market_id: int,
        draft: ObservedVolumeDraft,
    ) -> ObservedVolumeEvidenceRow | None:
        return self._session.scalar(
            select(ObservedVolumeEvidenceRow).where(
                ObservedVolumeEvidenceRow.market_id == market_id,
                ObservedVolumeEvidenceRow.calculator_name == draft.calculator_name,
                ObservedVolumeEvidenceRow.calculator_version == draft.calculator_version,
                ObservedVolumeEvidenceRow.parameters_hash == draft.parameters_hash,
                ObservedVolumeEvidenceRow.input_fingerprint == draft.input_fingerprint,
            )
        )

    def _same_or_conflict(
        self,
        existing: ObservedVolumeEvidenceRow,
        draft: ObservedVolumeDraft,
    ) -> SaveOutcome:
        if self._matches(existing, draft):
            return SaveOutcome("duplicate", existing.id)
        return SaveOutcome("conflict", existing.id)

    def _matches(
        self,
        existing: ObservedVolumeEvidenceRow,
        draft: ObservedVolumeDraft,
    ) -> bool:
        stored_buckets = self.buckets_for([existing.id]).get(existing.id, [])
        return (
            existing.sufficiency == draft.sufficiency
            and existing.source_limitation == draft.limitation
            and existing.input_aggregate_count == draft.input_aggregate_count
            and _same_decimal(existing.total_observed_base_volume, draft.total_observed_base_volume)
            and _same_decimal(existing.observed_poc_price, draft.observed_poc_price)
            and existing.poc_tie_count == draft.poc_tie_count
            and existing.poc_tie == draft.poc_tie
            and _same_decimal(
                existing.largest_aggregate_base_quantity,
                draft.largest_aggregate_base_quantity,
            )
            and _same_decimal(existing.derived_largest_share, draft.derived_largest_share)
            and _same_time(existing.first_event_time, draft.first_event_time)
            and _same_time(existing.last_event_time, draft.last_event_time)
            and _same_buckets(stored_buckets, draft)
        )

    def _bucket_rows(
        self,
        evidence_id: int,
        draft: ObservedVolumeDraft,
    ) -> list[ObservedVolumeBucketRow]:
        return [
            ObservedVolumeBucketRow(
                evidence_id=evidence_id,
                price=bucket.price,
                observed_base_volume=bucket.observed_base_volume,
                aggregate_count=bucket.aggregate_count,
                derived_share=bucket.derived_share,
            )
            for bucket in draft.buckets
        ]

    def _market_id(self, identity: MarketIdentity) -> int | None:
        return self._session.scalar(
            select(MarketRow.id).where(
                MarketRow.provider == identity.provider,
                MarketRow.provider_symbol == identity.provider_symbol,
                MarketRow.market_type == identity.market_type,
            )
        )


def _same_decimal(left: Decimal | None, right: Decimal | None) -> bool:
    if left is None or right is None:
        return left is None and right is None
    return left == right


def _same_time(left: datetime | None, right: datetime | None) -> bool:
    if left is None or right is None:
        return left is None and right is None
    return left == right


def _same_buckets(
    stored: list[ObservedVolumeBucketRow],
    draft: ObservedVolumeDraft,
) -> bool:
    if len(stored) != len(draft.buckets):
        return False
    ordered = sorted(draft.buckets, key=lambda bucket: bucket.price)
    for row, bucket in zip(stored, ordered, strict=True):
        if (
            row.price != bucket.price
            or row.observed_base_volume != bucket.observed_base_volume
            or row.aggregate_count != bucket.aggregate_count
            or row.derived_share != bucket.derived_share
        ):
            return False
    return True
