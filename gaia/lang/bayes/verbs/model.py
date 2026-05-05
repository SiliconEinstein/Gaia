"""Bayes predictive-model helper."""

from __future__ import annotations

from typing import Any

from gaia.lang.bayes.distributions.protocol import Distribution
from gaia.lang.bayes.runtime import PredictiveModel
from gaia.lang.runtime import Claim, Knowledge, Variable


def _claim_ref(claim: Claim) -> str:
    if claim.label:
        return f"[@{claim.label}]"
    return claim.content


def model(
    hypothesis: Claim,
    *,
    observable: Variable,
    distribution: Distribution,
    background: list[Knowledge] | None = None,
    rationale: str = "",
    label: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> Claim:
    """Declare a predictive model for one hypothesis. Returns the helper Claim."""
    if not isinstance(hypothesis, Claim):
        raise TypeError("bayes.model() hypothesis must be a Claim")
    if not isinstance(observable, Variable):
        raise TypeError("bayes.model() observable must be a Variable")
    if not hasattr(distribution, "model_dump"):
        raise TypeError("bayes.model() distribution must implement the Distribution protocol")

    merged = dict(metadata or {})
    bayes_meta = {
        "role": "prediction",
        "observable": {"symbol": observable.symbol},
    }
    merged["bayes"] = {**dict(merged.get("bayes", {})), **bayes_meta}
    merged.setdefault("generated", True)
    merged.setdefault("helper_kind", "predictive_model")
    merged.setdefault("review", True)
    if rationale:
        merged["reason"] = rationale

    helper = Claim(
        f"{_claim_ref(hypothesis)} predicts {observable.symbol} under {distribution.kind}.",
        background=background or [],
        metadata=merged,
    )
    helper.label = label
    action = PredictiveModel(
        label=label,
        rationale=rationale,
        background=list(background or []),
        warrants=[helper],
        metadata={"bayes": {"action": "predictive_model"}},
        hypothesis=hypothesis,
        observable=observable,
        distribution=distribution,
        helper=helper,
    )
    helper.supports.append(action)
    return helper
