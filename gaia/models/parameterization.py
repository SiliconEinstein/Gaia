"""Parameterization models — PriorRecord, FactorParamRecord, ResolutionPolicy.

Implements the parameterization layer on GlobalCanonicalGraph as defined in
docs/foundations/graph-ir/parameterization.md.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, model_validator

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CROMWELL_EPS: float = 1e-3
"""Cromwell's rule epsilon — all probabilities clamped to [EPS, 1-EPS]."""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _clamp(value: float) -> float:
    """Clamp value to (CROMWELL_EPS, 1 - CROMWELL_EPS)."""
    return max(CROMWELL_EPS, min(1 - CROMWELL_EPS, value))


# ---------------------------------------------------------------------------
# Records
# ---------------------------------------------------------------------------


class PriorRecord(BaseModel):
    """A single prior assignment for a global claim node.

    Values are Cromwell-clamped to [CROMWELL_EPS, 1 - CROMWELL_EPS] on
    creation. Multiple records for the same gcn_id may exist from different
    sources; resolution policy selects which one BP uses.
    """

    gcn_id: str
    value: float
    source_id: str
    created_at: datetime = None  # type: ignore[assignment]

    def model_post_init(self, __context: Any) -> None:
        if self.created_at is None:
            object.__setattr__(self, "created_at", datetime.now(timezone.utc))
        object.__setattr__(self, "value", _clamp(self.value))


class FactorParamRecord(BaseModel):
    """A single probability assignment for a global factor node.

    Covers infer, toolcall, and proof factors. Values are Cromwell-clamped.
    """

    factor_id: str
    probability: float
    source_id: str
    created_at: datetime = None  # type: ignore[assignment]

    def model_post_init(self, __context: Any) -> None:
        if self.created_at is None:
            object.__setattr__(self, "created_at", datetime.now(timezone.utc))
        object.__setattr__(self, "probability", _clamp(self.probability))


# ---------------------------------------------------------------------------
# Source
# ---------------------------------------------------------------------------


class ParameterizationSource(BaseModel):
    """Metadata about the model/policy that produced a batch of records."""

    source_id: str
    model: str
    policy: str | None = None
    config: dict[str, Any] | None = None
    created_at: datetime


# ---------------------------------------------------------------------------
# Resolution Policy
# ---------------------------------------------------------------------------


class ResolutionPolicy(BaseModel):
    """Policy for resolving multiple parameterization records before BP runs.

    Strategies:
    - ``"latest"``: pick the most recent record per node/factor.
    - ``"source"``: use only records from a specific ParameterizationSource;
      requires ``source_id`` to be set.

    ``prior_cutoff`` filters records to those created before the given
    timestamp, enabling reproducible BP runs.
    """

    strategy: str  # "latest" | "source"
    source_id: str | None = None
    prior_cutoff: datetime | None = None

    @model_validator(mode="after")
    def _validate_source_requires_source_id(self) -> ResolutionPolicy:
        if self.strategy == "source" and self.source_id is None:
            raise ValueError("strategy='source' requires source_id to be set")
        return self
