"""likelihood() DSL helper."""

from __future__ import annotations

from typing import Any

from gaia.lang.bayes.runtime import ComparisonResult, PredictiveModel
from gaia.lang.runtime import Claim, Knowledge


def likelihood(
    data: Claim | list[Claim] | tuple[Claim, ...],
    *,
    via: PredictiveModel,
    background: list[Knowledge] | None = None,
    rationale: str = "",
    label: str | None = None,
    exclusivity: str = "pairwise_contradiction",
    precomputed: dict[Claim, float] | None = None,
    metadata: dict[str, Any] | None = None,
) -> ComparisonResult:
    return ComparisonResult(
        data,
        via,
        background=background,
        rationale=rationale,
        label=label,
        exclusivity=exclusivity,
        precomputed=precomputed,
        metadata=metadata,
    )
