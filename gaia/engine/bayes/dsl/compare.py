"""v0.6 Bayes ``compare`` verb — compare equal-positioned predictive models.

``compare(data, models=[m1, m2, ...])`` evaluates the log-likelihood of
the observation Claim(s) ``data`` under each model's predictive
distribution and emits one IR ``infer`` strategy per hypothesis. Each
model is a helper Claim returned by :func:`predict`.

This is the v0.6 replacement for ``bayes.likelihood(data, model=...,
against=[...])``. Differences from v0.5:

* ``model=`` + ``against=[...]`` collapses to a single ``models=[...]``
  list. The model the author "advocates" is no longer encoded in the
  API; it lives in Claim priors instead, where review can see it.
* ``precomputed=`` accepts either the legacy ``dict[Claim, float]``
  shortcut or a :class:`PrecomputedLikelihoods` Claim carrying solver
  diagnostics.

The legacy ``bayes.likelihood`` verb stays available; v0.6 lowering
dispatches on :class:`ModelComparison` (this verb's Action), not on
:class:`Likelihood`.
"""

from __future__ import annotations

import hashlib
import re
from itertools import combinations
from typing import Any, Mapping

from gaia.engine.bayes.runtime import ModelComparison, Prediction
from gaia.engine.bayes.runtime.precomputed import PrecomputedLikelihoods
from gaia.engine.bp.factor_graph import CROMWELL_EPS
from gaia.engine.lang.runtime.action import (
    Contradict,
    Exclusive,
    attach_reasoning,
    validate_no_self_warrant,
)
from gaia.engine.lang.runtime.knowledge import Claim, Knowledge, _current_package

_EXCLUSIVITY_VALUES = {
    "none",
    "pairwise_contradiction",
    "exhaustive_pairwise_complement",
}

_LABEL_RE = re.compile(r"[^a-z0-9_]")


def _as_claim_tuple(
    value: Claim | list[Claim] | tuple[Claim, ...], *, name: str
) -> tuple[Claim, ...]:
    items: tuple[Claim, ...]
    items = (value,) if isinstance(value, Claim) else tuple(value)
    if not items:
        raise ValueError(f"compare() requires at least one {name} claim")
    for item in items:
        if not isinstance(item, Claim):
            raise TypeError(f"compare() {name} entries must be Claim objects")
    return items


def _prediction_action(helper: Claim) -> Prediction:
    for action in helper.from_actions:
        if isinstance(action, Prediction) and action.helper is helper:
            return action
    raise TypeError(
        "compare() models entries must be Claims returned by predict() "
        f"(no Prediction action attached to {helper.label or helper.content[:40]!r})"
    )


def _claim_ref(claim: Claim) -> str:
    if claim.label:
        return f"[@{claim.label}]"
    return claim.content


def _label_part(claim: Claim) -> str:
    raw = claim.label or claim.content or "claim"
    normalized = _LABEL_RE.sub("_", raw.strip().lower())
    normalized = normalized.strip("_")
    if not normalized:
        digest = hashlib.sha256(raw.encode()).hexdigest()[:8]
        normalized = f"claim_{digest}"
    if not (normalized[0].isalpha() or normalized[0] == "_"):
        normalized = f"_{normalized}"
    return normalized


def _relation_exists(kind: type, a: Claim, b: Claim) -> bool:
    pkg = _current_package.get()
    if pkg is None:
        return False
    pair = {id(a), id(b)}
    for action in pkg.actions:
        if isinstance(action, kind) and {id(action.a), id(action.b)} == pair:
            return True
    return False


def _auto_structural_label(base: str | None, relation: str, a: Claim, b: Claim) -> str:
    prefix = base or "compare"
    return f"{prefix}_{relation}_{_label_part(a)}_{_label_part(b)}"


def _auto_generated_by(label: str | None) -> str:
    return f"compare:{label or 'anonymous'}"


def _auto_contradict(a: Claim, b: Claim, *, label: str | None) -> None:
    if _relation_exists(Contradict, a, b):
        return
    helper = Claim(
        f"{_claim_ref(a)} and {_claim_ref(b)} contradict.",
        metadata={
            "generated": True,
            "helper_kind": "contradiction_result",
            "review": True,
            "auto_generated_by": _auto_generated_by(label),
            "bayes": {"auto_generated_by": _auto_generated_by(label)},
        },
    )
    action = Contradict(
        label=_auto_structural_label(label, "contradict", a, b),
        rationale="Bayes compare alternatives are pairwise contradictory.",
        metadata={"bayes": {"auto_generated_by": _auto_generated_by(label)}},
        a=a,
        b=b,
        helper=helper,
    )
    validate_no_self_warrant(action, helper)
    attach_reasoning(helper, action)


def _auto_exclusive(a: Claim, b: Claim, *, label: str | None) -> None:
    if _relation_exists(Exclusive, a, b):
        return
    helper = Claim(
        f"exactly one of {_claim_ref(a)} and {_claim_ref(b)} is true.",
        metadata={
            "generated": True,
            "helper_kind": "complement_result",
            "review": True,
            "auto_generated_by": _auto_generated_by(label),
            "bayes": {"auto_generated_by": _auto_generated_by(label)},
        },
    )
    action = Exclusive(
        label=_auto_structural_label(label, "exclusive", a, b),
        rationale="Bayes compare alternatives form a closed binary partition.",
        metadata={"bayes": {"auto_generated_by": _auto_generated_by(label)}},
        a=a,
        b=b,
        helper=helper,
    )
    validate_no_self_warrant(action, helper)
    attach_reasoning(helper, action)


def _ensure_structural_actions(
    hypotheses: tuple[Claim, ...],
    *,
    exclusivity: str,
    label: str | None,
) -> None:
    if exclusivity == "none" or len(hypotheses) < 2:
        return
    if exclusivity == "exhaustive_pairwise_complement" and len(hypotheses) == 2:
        _auto_exclusive(hypotheses[0], hypotheses[1], label=label)
        return
    for a, b in combinations(hypotheses, 2):
        _auto_contradict(a, b, label=label)


def _comparison_hypotheses(prediction_actions: tuple[Prediction, ...]) -> tuple[Claim, ...]:
    hypotheses = tuple(action.hypothesis for action in prediction_actions)
    if any(h is None for h in hypotheses):
        raise ValueError("predict() action is missing its hypothesis")
    typed_tuple = tuple(h for h in hypotheses if h is not None)
    if len({id(h) for h in typed_tuple}) != len(typed_tuple):
        raise ValueError("compare() received duplicate hypotheses through model helpers")
    return typed_tuple


def _validate_shared_target(prediction_actions: tuple[Prediction, ...]) -> None:
    """All compared models must predict the same target.

    Targets compare by Python identity when they are runtime objects
    (Variable / Distribution Knowledge). This catches the v0.5 bug where
    two predictive models accidentally referenced different Variable
    objects with the same symbol.
    """
    if not prediction_actions:
        return
    first_target = prediction_actions[0].target
    for action in prediction_actions[1:]:
        if action.target is not first_target:
            raise ValueError(
                "compare() model helpers must share one target; got "
                f"{first_target!r} vs {action.target!r}"
            )


def _normalize_precomputed(
    precomputed: Any,
    hypothesis_tuple: tuple[Claim, ...],
) -> tuple[dict[Claim, float], PrecomputedLikelihoods | None]:
    if precomputed is None:
        return {}, None

    if isinstance(precomputed, PrecomputedLikelihoods):
        likelihoods = dict(precomputed.log_likelihoods)
        claim_obj: PrecomputedLikelihoods | None = precomputed
    elif isinstance(precomputed, Mapping):
        likelihoods = dict(precomputed)
        claim_obj = None
    else:
        raise TypeError(
            "compare(precomputed=...) must be a dict[Claim, float] or a "
            "PrecomputedLikelihoods Claim, got "
            f"{type(precomputed).__name__}"
        )

    allowed = set(hypothesis_tuple)
    for key in likelihoods:
        if not isinstance(key, Claim) or key not in allowed:
            raise ValueError("precomputed likelihood keys must be original hypothesis Claims")
    provided = set(likelihoods)
    if provided != allowed:
        missing = sorted(claim.label or claim.content for claim in allowed - provided)
        details = []
        if missing:
            details.append(f"missing {missing}")
        suffix = f": {', '.join(details)}" if details else ""
        raise ValueError("precomputed likelihoods must cover exactly the model hypotheses" + suffix)
    coerced = {key: float(value) for key, value in likelihoods.items()}
    return coerced, claim_obj


def _comparison_metadata(
    metadata: dict[str, Any] | None,
    *,
    exclusivity: str,
    rationale: str,
) -> dict[str, Any]:
    merged = dict(metadata or {})
    merged["comparison"] = {
        **dict(merged.get("comparison", {})),
        "kind": "comparison",
        "exclusivity": exclusivity,
    }
    merged.setdefault("generated", True)
    merged.setdefault("helper_kind", "model_preference")
    merged.setdefault("review", True)
    if rationale:
        merged["reason"] = rationale
    return merged


def compare(
    data: Claim | list[Claim] | tuple[Claim, ...],
    *,
    models: list[Claim] | tuple[Claim, ...],
    background: list[Knowledge] | None = None,
    rationale: str = "",
    label: str | None = None,
    exclusivity: str = "pairwise_contradiction",
    precomputed: dict[Claim, float] | PrecomputedLikelihoods | None = None,
    metadata: dict[str, Any] | None = None,
) -> Claim:
    """Compare observed data against an equal-positioned list of models.

    Returns the comparison helper Claim. The helper carries
    ``metadata["comparison"]`` describing the exclusivity contract and,
    after compilation, the per-hypothesis log-likelihood table.
    """
    data_tuple = _as_claim_tuple(data, name="data")
    if not models:
        raise ValueError("compare() requires at least one model")
    models_tuple = _as_claim_tuple(models, name="models")
    if exclusivity not in _EXCLUSIVITY_VALUES:
        raise ValueError(f"unknown exclusivity mode: {exclusivity!r}")

    prediction_actions = tuple(_prediction_action(m) for m in models_tuple)
    hypothesis_tuple = _comparison_hypotheses(prediction_actions)
    _validate_shared_target(prediction_actions)
    log_likelihoods, precomputed_claim = _normalize_precomputed(precomputed, hypothesis_tuple)

    _ensure_structural_actions(hypothesis_tuple, exclusivity=exclusivity, label=label)

    helper = Claim(
        "Bayes model comparison.",
        background=background or [],
        metadata=_comparison_metadata(metadata, exclusivity=exclusivity, rationale=rationale),
        prior=1.0 - CROMWELL_EPS,
    )
    helper.label = label

    action = ModelComparison(
        label=label,
        rationale=rationale,
        background=list(background or []),
        metadata={"bayes": {"action": "model_comparison"}},
        helper=helper,
        models=models_tuple,
        data=data_tuple,
        exclusivity=exclusivity,
        precomputed=precomputed_claim if precomputed_claim is not None else (dict(log_likelihoods) if log_likelihoods else None),
        log_likelihoods=log_likelihoods,
    )
    validate_no_self_warrant(action, helper)
    attach_reasoning(helper, action)
    return helper
