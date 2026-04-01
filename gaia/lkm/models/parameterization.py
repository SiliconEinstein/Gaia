"""Parameterization models — probability parameters and their sources."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel

CROMWELL_EPS: float = 1e-3
"""Cromwell's rule epsilon — all probabilities clamped to [EPS, 1-EPS]."""


def cromwell_clamp(value: float) -> float:
    """Clamp probability to (ε, 1-ε) per Cromwell's rule."""
    return max(CROMWELL_EPS, min(1 - CROMWELL_EPS, value))


class PriorRecord(BaseModel):
    """Prior probability for a global claim variable.

    Only visibility=public, type=claim variables should have PriorRecords.
    This constraint is enforced at the storage/integration layer, not here,
    because PriorRecord doesn't know the variable's visibility.

    Values are Cromwell-clamped on construction.
    """

    variable_id: str  # gcn_id
    value: float  # ∈ (ε, 1-ε)
    source_id: str  # → ParameterizationSource.source_id
    created_at: datetime

    def model_post_init(self, __context: Any) -> None:
        object.__setattr__(self, "value", cromwell_clamp(self.value))


class FactorParamRecord(BaseModel):
    """Conditional probability parameters for a global strategy factor.

    Only factor_type=strategy, subtype ∈ {infer, noisy_and} factors need this.
    Enforced at storage/integration layer.

    All values are Cromwell-clamped on construction.
    """

    factor_id: str  # gfac_id
    conditional_probabilities: list[float]  # Cromwell clamped
    source_id: str
    created_at: datetime

    def model_post_init(self, __context: Any) -> None:
        clamped = [cromwell_clamp(p) for p in self.conditional_probabilities]
        object.__setattr__(self, "conditional_probabilities", clamped)


class ParameterizationSource(BaseModel):
    """Metadata about the origin of parameterization records.

    source_class is LKM-specific (not in upstream Gaia IR contract).
    Priority: official > heuristic > provisional (irreversible).
    """

    source_id: str
    source_class: str  # "official" | "heuristic" | "provisional"
    model: str  # reviewer ID or LLM model name
    policy: str | None = None
    config: dict | None = None
    created_at: datetime
