from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class ImplementationStatus(StrEnum):
    PLANNED = "planned"
    FOUNDATION = "foundation"
    DISABLED = "disabled"


class DomainBoundary(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    key: str = Field(pattern=r"^[a-z][a-z0-9_]{1,40}$")
    responsibility: str = Field(min_length=1, max_length=300)
    must_not: list[str] = Field(min_length=1)
    implementation_status: ImplementationStatus
    phase_note: str = Field(min_length=1, max_length=300)
