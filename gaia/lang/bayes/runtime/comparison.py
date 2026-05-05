"""ComparisonResult runtime Claim."""

from __future__ import annotations

from typing import Any

from gaia.bp.factor_graph import CROMWELL_EPS
from gaia.lang.bayes.runtime.prediction import PredictiveModel
from gaia.lang.runtime import Claim, Knowledge
from gaia.lang.runtime.knowledge import ClaimKind

_EXCLUSIVITY_VALUES = {
    "none",
    "pairwise_contradiction",
    "exhaustive_pairwise_complement",
}


class ComparisonResult(Claim):
    """A computed likelihood comparison claim."""

    data: tuple[Claim, ...]
    via: PredictiveModel
    exclusivity: str
    precomputed: dict[Claim, float] | None

    def __init__(
        self,
        data: Claim | list[Claim] | tuple[Claim, ...],
        via: PredictiveModel,
        *,
        content: str | None = None,
        background: list[Knowledge] | None = None,
        rationale: str = "",
        label: str | None = None,
        exclusivity: str = "pairwise_contradiction",
        precomputed: dict[Claim, float] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        if isinstance(data, Claim):
            data_tuple = (data,)
        else:
            data_tuple = tuple(data)
        if not data_tuple:
            raise ValueError("likelihood() requires at least one observation claim")
        if not isinstance(via, PredictiveModel):
            raise TypeError("likelihood() via= must be a PredictiveModel")
        if exclusivity not in _EXCLUSIVITY_VALUES:
            raise ValueError(f"unknown exclusivity mode: {exclusivity!r}")
        for item in data_tuple:
            if not isinstance(item, Claim):
                raise TypeError("likelihood() data must be Claim objects")
        if precomputed is not None:
            for key, value in precomputed.items():
                if not isinstance(key, Claim):
                    raise TypeError("precomputed likelihood keys must be runtime Claim objects")
                float(value)

        bayes_meta = {
            "role": "comparison",
            "exclusivity": exclusivity,
        }
        merged = dict(metadata or {})
        merged["bayes"] = {**dict(merged.get("bayes", {})), **bayes_meta}
        if rationale:
            merged["reason"] = rationale
        super().__init__(
            content=content or "Bayes likelihood comparison.",
            background=background or [],
            metadata=merged,
            prior=1.0 - CROMWELL_EPS,
            kind=ClaimKind.GENERAL,
        )
        self.data = data_tuple
        self.via = via
        self.exclusivity = exclusivity
        self.precomputed = dict(precomputed) if precomputed is not None else None
        self.label = label
