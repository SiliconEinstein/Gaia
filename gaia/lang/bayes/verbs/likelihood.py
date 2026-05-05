"""Bayes likelihood helper."""

from __future__ import annotations

import hashlib
import re
from itertools import combinations
from typing import Any

from gaia.bp.factor_graph import CROMWELL_EPS
from gaia.lang.bayes.runtime import Likelihood, PredictiveModel
from gaia.lang.runtime.action import Contradict, Exclusive
from gaia.lang.runtime.knowledge import Claim, Knowledge, _current_package

_EXCLUSIVITY_VALUES = {
    "none",
    "pairwise_contradiction",
    "exhaustive_pairwise_complement",
}

_LABEL_RE = re.compile(r"[^a-z0-9_]")


def _as_claim_tuple(
    value: Claim | list[Claim] | tuple[Claim, ...], *, name: str
) -> tuple[Claim, ...]:
    if isinstance(value, Claim):
        items = (value,)
    else:
        items = tuple(value)
    if not items:
        raise ValueError(f"likelihood() requires at least one {name} claim")
    for item in items:
        if not isinstance(item, Claim):
            raise TypeError(f"likelihood() {name} entries must be Claim objects")
    return items


def _model_action(helper: Claim) -> PredictiveModel:
    for action in helper.supports:
        if isinstance(action, PredictiveModel) and action.helper is helper:
            return action
    raise TypeError("likelihood() model entries must be Claims returned by bayes.model()")


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


def _relation_exists(kind: type[Contradict] | type[Exclusive], a: Claim, b: Claim) -> bool:
    pkg = _current_package.get()
    if pkg is None:
        return False
    pair = {id(a), id(b)}
    for action in pkg.actions:
        if isinstance(action, kind) and {id(action.a), id(action.b)} == pair:
            return True
    return False


def _auto_structural_label(base: str | None, relation: str, a: Claim, b: Claim) -> str:
    prefix = base or "likelihood"
    return f"{prefix}_{relation}_{_label_part(a)}_{_label_part(b)}"


def _auto_generated_by(label: str | None) -> str:
    return f"likelihood:{label or 'anonymous'}"


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
        rationale="Bayes likelihood alternatives are pairwise contradictory.",
        metadata={"bayes": {"auto_generated_by": _auto_generated_by(label)}},
        a=a,
        b=b,
        helper=helper,
    )
    action.warrants.append(helper)


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
        rationale="Bayes likelihood alternatives form a closed binary partition.",
        metadata={"bayes": {"auto_generated_by": _auto_generated_by(label)}},
        a=a,
        b=b,
        helper=helper,
    )
    action.warrants.append(helper)


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


def likelihood(
    data: Claim | list[Claim] | tuple[Claim, ...],
    *,
    model: Claim,
    against: Claim | list[Claim] | tuple[Claim, ...] = (),
    background: list[Knowledge] | None = None,
    rationale: str = "",
    label: str | None = None,
    exclusivity: str = "pairwise_contradiction",
    precomputed: dict[Claim, float] | None = None,
    metadata: dict[str, Any] | None = None,
) -> Claim:
    """Compare observed data against one or more Bayes model helpers."""
    data_tuple = _as_claim_tuple(data, name="data")
    if not isinstance(model, Claim):
        raise TypeError("likelihood() model= must be a Claim returned by bayes.model()")
    against_tuple = () if against == () else _as_claim_tuple(against, name="against")
    if exclusivity not in _EXCLUSIVITY_VALUES:
        raise ValueError(f"unknown exclusivity mode: {exclusivity!r}")

    model_actions = (_model_action(model), *(_model_action(item) for item in against_tuple))
    hypotheses = tuple(action.hypothesis for action in model_actions)
    if any(h is None for h in hypotheses):
        raise ValueError("bayes.model() action is missing its hypothesis")
    hypothesis_tuple = tuple(h for h in hypotheses if h is not None)
    if len({id(h) for h in hypothesis_tuple}) != len(hypothesis_tuple):
        raise ValueError("likelihood() received duplicate hypotheses through model helpers")

    observable_symbols = {action.observable.symbol for action in model_actions if action.observable}
    if len(observable_symbols) != 1:
        raise ValueError("likelihood() model helpers must share one observable")

    log_likelihoods: dict[Claim, float] = {}
    if precomputed is not None:
        allowed = set(hypothesis_tuple)
        for key in precomputed:
            if not isinstance(key, Claim) or key not in allowed:
                raise ValueError("precomputed likelihood keys must be original hypothesis Claims")
        provided = set(precomputed)
        if provided != allowed:
            missing = sorted((claim.label or claim.content for claim in allowed - provided))
            details = []
            if missing:
                details.append(f"missing {missing}")
            suffix = f": {', '.join(details)}" if details else ""
            raise ValueError(
                "precomputed likelihoods must cover exactly the model hypotheses" + suffix
            )
        for key, value in precomputed.items():
            log_likelihoods[key] = float(value)

    _ensure_structural_actions(hypothesis_tuple, exclusivity=exclusivity, label=label)

    merged = dict(metadata or {})
    merged["bayes"] = {
        **dict(merged.get("bayes", {})),
        "role": "comparison",
        "exclusivity": exclusivity,
    }
    merged.setdefault("generated", True)
    merged.setdefault("helper_kind", "model_preference")
    merged.setdefault("review", True)
    if rationale:
        merged["reason"] = rationale

    helper = Claim(
        "Bayes likelihood comparison.",
        background=background or [],
        metadata=merged,
        prior=1.0 - CROMWELL_EPS,
    )
    helper.label = label
    action = Likelihood(
        label=label,
        rationale=rationale,
        background=list(background or []),
        warrants=[helper],
        metadata={"bayes": {"action": "likelihood"}},
        helper=helper,
        model=model,
        against=against_tuple,
        data=data_tuple,
        exclusivity=exclusivity,
        precomputed=dict(precomputed) if precomputed is not None else None,
        log_likelihoods=log_likelihoods,
    )
    helper.supports.append(action)
    return helper
