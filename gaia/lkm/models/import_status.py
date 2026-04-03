"""Import status tracking model."""

from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ImportStatusRecord(BaseModel):
    """Tracks the import status of a single package (paper) into LKM."""

    package_id: str
    status: str  # "ingested" | "failed:<reason>"
    variable_count: int = 0
    factor_count: int = 0
    prior_count: int = 0
    factor_param_count: int = 0
    started_at: datetime = Field(default_factory=_utcnow)
    completed_at: datetime = Field(default_factory=_utcnow)
    error: str = ""
