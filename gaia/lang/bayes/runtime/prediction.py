"""PredictiveModel runtime Claim."""

from __future__ import annotations

from typing import Any

from gaia.lang.bayes.distributions.protocol import Distribution
from gaia.lang.runtime import Claim, Knowledge, Variable
from gaia.lang.runtime.knowledge import ClaimKind


def _ordered_hypotheses(
    hypothesis: Claim | set[Claim] | list[Claim] | tuple[Claim, ...],
) -> tuple[Claim, ...]:
    if isinstance(hypothesis, Claim):
        items = (hypothesis,)
    else:
        items = tuple(hypothesis)
    if not items:
        raise ValueError("predict() requires at least one hypothesis")
    for item in items:
        if not isinstance(item, Claim):
            raise TypeError("predict() hypotheses must be Claim objects")
    return tuple(sorted(items, key=lambda h: h.label or h.content))


class PredictiveModel(Claim):
    """A Bayes predictive model claim."""

    hypotheses: tuple[Claim, ...]
    observable: Variable
    distribution: Distribution

    def __init__(
        self,
        hypothesis: Claim | set[Claim] | list[Claim] | tuple[Claim, ...],
        observable: Variable,
        distribution: Distribution,
        *,
        content: str | None = None,
        background: list[Knowledge] | None = None,
        rationale: str = "",
        label: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        if not isinstance(observable, Variable):
            raise TypeError("predict() observable must be a Variable")
        if not hasattr(distribution, "model_dump"):
            raise TypeError("predict() distribution must implement the Distribution protocol")

        hypotheses = _ordered_hypotheses(hypothesis)
        bayes_meta = {
            "role": "prediction",
            "distribution": distribution.model_dump(),
            "observable": {"symbol": observable.symbol},
            "hypotheses": [h.label or h.content for h in hypotheses],
        }
        merged = dict(metadata or {})
        merged["bayes"] = {**dict(merged.get("bayes", {})), **bayes_meta}
        if rationale:
            merged["reason"] = rationale
        super().__init__(
            content=content or f"Predictive model for {observable.symbol}.",
            background=background or [],
            metadata=merged,
            kind=ClaimKind.GENERAL,
        )
        self.hypotheses = hypotheses
        self.observable = observable
        self.distribution = distribution
        self.label = label
