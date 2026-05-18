"""Bayes ``predict`` verb — author predictive distributions.

``predict(hypothesis, target=variable_or_distribution, distribution=dist)``
declares: "under ``hypothesis``, ``target`` follows the predictive
distribution ``dist``". Returns the helper Claim that other verbs cite.

The helper Claim writes the canonical ``metadata["prediction"]`` schema:

``{"hypothesis": Claim, "target": Variable | Distribution,
"distribution": Distribution, "kind": "prediction"}``

Key design points:

* ``target`` accepts ``Variable | Distribution`` so one kwarg covers both
  observable Variables (Bayes-style discrete counts) and Distribution
  random variables (quantity-with-predicate observations).
* ``distribution`` must be a :class:`Distribution` Knowledge object (from
  the ``gaia.engine.lang`` factories), not a raw typed-value pydantic
  instance — the latter is the internal scipy backend.
"""

from __future__ import annotations

from typing import Any

from gaia.engine.bayes.runtime import Prediction
from gaia.engine.lang.runtime import Claim, Distribution, Knowledge, Variable
from gaia.engine.lang.runtime.action import attach_reasoning, validate_no_self_warrant


def _claim_ref(claim: Claim) -> str:
    if claim.label:
        return f"[@{claim.label}]"
    return claim.content


def _target_descriptor(target: Variable | Distribution) -> str:
    if isinstance(target, Variable):
        return target.symbol
    return target.label or target.content[:40]


def predict(
    hypothesis: Claim,
    *,
    target: Variable | Distribution,
    distribution: Distribution,
    background: list[Knowledge] | None = None,
    rationale: str = "",
    label: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> Claim:
    """Declare a predictive distribution for one hypothesis.

    Returns the helper :class:`Claim`. The helper is what other v0.6 verbs
    (notably :func:`gaia.engine.bayes.compare`) cite to attach the
    prediction to a model-comparison action.
    """
    if not isinstance(hypothesis, Claim):
        raise TypeError("predict() hypothesis must be a Claim")
    if not isinstance(target, (Variable, Distribution)):
        raise TypeError(
            f"predict() target must be a Variable or a Distribution; got {type(target).__name__}"
        )
    if not isinstance(distribution, Distribution):
        raise TypeError(
            "predict() distribution must be a Distribution Knowledge object "
            "(use the factories in gaia.engine.lang: Normal, Binomial, "
            "BetaBinomial, ...); got "
            f"{type(distribution).__name__}"
        )

    merged = dict(metadata or {})
    prediction_meta = {
        "kind": "prediction",
        "hypothesis": hypothesis,
        "target": target,
        "distribution": distribution,
    }
    merged["prediction"] = {**dict(merged.get("prediction", {})), **prediction_meta}
    merged.setdefault("generated", True)
    merged.setdefault("helper_kind", "predictive_model")
    merged.setdefault("review", True)
    if rationale:
        merged["reason"] = rationale

    content = (
        f"{_claim_ref(hypothesis)} predicts {_target_descriptor(target)} ~ {distribution.kind}."
    )
    helper = Claim(
        content,
        background=background or [],
        metadata=merged,
    )
    helper.label = label

    action = Prediction(
        label=label,
        rationale=rationale,
        background=list(background or []),
        metadata={"bayes": {"action": "prediction"}},
        hypothesis=hypothesis,
        target=target,
        distribution=distribution,
        helper=helper,
    )
    validate_no_self_warrant(action, helper)
    attach_reasoning(helper, action)
    return helper
