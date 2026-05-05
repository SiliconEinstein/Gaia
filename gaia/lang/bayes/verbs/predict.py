"""predict() DSL helper."""

from __future__ import annotations

from typing import Any

from gaia.lang.bayes.distributions.protocol import Distribution
from gaia.lang.bayes.runtime import PredictiveModel
from gaia.lang.runtime import Claim, Knowledge, Variable


def predict(
    hypothesis: Claim | set[Claim] | list[Claim] | tuple[Claim, ...],
    observable: Variable,
    *,
    distribution: Distribution,
    background: list[Knowledge] | None = None,
    rationale: str = "",
    label: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> PredictiveModel:
    return PredictiveModel(
        hypothesis,
        observable,
        distribution,
        background=background,
        rationale=rationale,
        label=label,
        metadata=metadata,
    )
