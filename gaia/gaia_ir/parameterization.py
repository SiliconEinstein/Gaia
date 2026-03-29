"""Parameterization — probability parameters on GlobalCanonicalGraph.

Implements docs/foundations/gaia-ir/parameterization.md.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, model_validator

CROMWELL_EPS: float = 1e-3
"""Cromwell's rule epsilon — all probabilities clamped to [EPS, 1-EPS]."""


def _clamp(value: float) -> float:
    return max(CROMWELL_EPS, min(1 - CROMWELL_EPS, value))


class PriorRecord(BaseModel):
    """Prior probability for a global claim Knowledge.

    Only type=claim Knowledge has PriorRecord. Values are Cromwell-clamped.
    Multiple records for the same gcn_id may exist from different sources.
    """

    gcn_id: str
    value: float
    source_id: str
    created_at: datetime = None  # type: ignore[assignment]

    def model_post_init(self, __context: Any) -> None:
        if self.created_at is None:
            object.__setattr__(self, "created_at", datetime.now(timezone.utc))
        object.__setattr__(self, "value", _clamp(self.value))


class StrategyParamRecord(BaseModel):
    """Conditional probability parameters for a global Strategy.

    Parameter count depends on Strategy type:
    - infer: 2^k values (full CPT, one per premise truth-value combination)
    - noisy_and: 1 value (P(conclusion=true | all premises=true))
    - named strategies: 1 value (folded conditional probability)
    - toolcall/proof: defined separately

    All values are Cromwell-clamped.
    """

    strategy_id: str  # gcs_ prefix
    conditional_probabilities: list[float]
    source_id: str
    created_at: datetime = None  # type: ignore[assignment]

    def model_post_init(self, __context: Any) -> None:
        if self.created_at is None:
            object.__setattr__(self, "created_at", datetime.now(timezone.utc))
        clamped = [_clamp(p) for p in self.conditional_probabilities]
        object.__setattr__(self, "conditional_probabilities", clamped)


class ParameterizationSource(BaseModel):
    """Metadata about the model/policy that produced a batch of records."""

    source_id: str
    model: str
    policy: str | None = None
    config: dict[str, Any] | None = None
    created_at: datetime


class ResolutionPolicy(BaseModel):
    """Policy for resolving multiple parameterization records before BP runs.

    Strategies:
    - "latest": pick the most recent record per Knowledge/Strategy.
    - "source": use only records from a specific ParameterizationSource.

    prior_cutoff filters records to those created before the given timestamp,
    enabling reproducible BP runs.
    """

    strategy: str  # "latest" | "source"
    source_id: str | None = None
    prior_cutoff: datetime | None = None

    @model_validator(mode="after")
    def _validate_source_requires_source_id(self) -> ResolutionPolicy:
        if self.strategy == "source" and self.source_id is None:
            raise ValueError("strategy='source' requires source_id to be set")
        return self
