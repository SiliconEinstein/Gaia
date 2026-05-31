# ruff: noqa: RUF002
# Greek letters appear in scientific docstrings; keep them as-is.

"""Bayes ``compare`` verb - compare equal-positioned predictive models.

``compare(data, models=[m1, m2, ...])`` evaluates the log-likelihood of
the observation Claim(s) ``data`` under each model's predictive
distribution and emits one IR ``infer`` strategy per hypothesis. Each
model is a helper Claim returned by :func:`model`.

Key design points (vs the earlier in-flight Bayes alpha that this
clean break replaces):

* ``model=`` + ``against=[...]`` is collapsed to a single ``models=[...]``
  list. The model the author "advocates" is no longer encoded in the
  API; it lives in Claim priors instead, where review can see it.
* The default ``exclusivity`` is ``"exhaustive_pairwise_complement"``
  (was ``"pairwise_contradiction"`` in the earlier alpha). The previous
  default silently diluted Bayesian model-selection posteriors by the
  mass that ``α=0.5`` assigned to the "all-false" joint state. The new
  default matches the standard Bayesian model-selection contract for
  2-model comparisons, and ``compare()`` rejects ``len(models) > 2``
  under it until the N-ary Exclusive operator lands. See the
  ``compare()`` docstring's "Exclusivity contracts" section for the
  full trade-off across the two modes.
* ``compare()`` deduplicates against same-type external
  ``exclusive(...)`` / ``contradict(...)`` declarations over the same
  hypothesis pair — authors who used to write ``exclusivity="none"``
  to defer to an external structural action should now drop that
  argument and let the default dedup path take over. The ``"none"``
  option is no longer accepted (raises ``ValueError`` with a
  remediation hint). Cross-type coexistence
  (e.g. external ``contradict()`` + auto-emitted ``exclusive()``) is
  allowed: the two are logically consistent and the IR's own
  consistency checks govern whether the combined graph is legal.
* ``precomputed=`` accepts either the bare ``dict[Claim, float]``
  shortcut or a :class:`PrecomputedLikelihoods` Claim carrying solver
  diagnostics. NaN / +inf log-likelihoods are rejected at the entry
  point to prevent silent Cromwell-clamping.
"""

from __future__ import annotations

import hashlib
import math
import re
from collections.abc import Mapping
from itertools import combinations
from typing import Any

from gaia.engine.bayes.runtime import Model, ModelCompare
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


def _model_action(helper: Claim) -> Model:
    for action in helper.from_actions:
        if isinstance(action, Model) and action.helper is helper:
            return action
    raise TypeError(
        "compare() models entries must be Claims returned by model() "
        f"(no Model action attached to {helper.label or helper.content[:40]!r})"
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


def _existing_pair_relations(a: Claim, b: Claim) -> tuple[Exclusive | Contradict, ...]:
    """Return existing ``Exclusive`` / ``Contradict`` actions over (a, b).

    Looks at the active package the same way action registration does:
    first the ContextVar-bound ``_current_package``, then — if unset —
    fall back to ``infer_package_from_callstack()``. Without the
    fallback the dedup silently misses the ``gaia build compile``
    path, where ``load_gaia_package()`` registers actions through the
    inferred package without ever binding ``_current_package``.
    """
    from gaia.engine.lang.runtime.package import infer_package_from_callstack

    pkg = _current_package.get()
    if pkg is None:
        pkg = infer_package_from_callstack()
    if pkg is None:
        return ()
    pair = {id(a), id(b)}
    return tuple(
        action
        for action in pkg.actions
        if isinstance(action, (Exclusive, Contradict)) and {id(action.a), id(action.b)} == pair
    )


def _auto_structural_label(base: str | None, relation: str, a: Claim, b: Claim) -> str:
    prefix = base or "compare"
    return f"{prefix}_{relation}_{_label_part(a)}_{_label_part(b)}"


def _auto_generated_by(label: str | None) -> str:
    return f"compare:{label or 'anonymous'}"


def _emit_contradict(a: Claim, b: Claim, *, label: str | None) -> None:
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


def _emit_exclusive(a: Claim, b: Claim, *, label: str | None) -> None:
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


def _auto_exclusive(a: Claim, b: Claim, *, label: str | None) -> None:
    """Emit ``Exclusive(a, b)`` unless an existing same-type relation covers it.

    Cross-type coexistence (e.g. external ``contradict()`` + this
    ``exclusive()``) is logically consistent — ``Exclusive`` implies
    ``Contradict``, so the joint constraint is just ``Exclusive``. We
    therefore do **not** raise when only a ``Contradict`` already exists
    over the pair; the IR's structural-relation consistency checks
    (e.g. the D2 "same operator + same args + distinct conclusions"
    rule) are the authority on whether the combined factor graph is
    legal.
    """
    if any(isinstance(action, Exclusive) for action in _existing_pair_relations(a, b)):
        return
    _emit_exclusive(a, b, label=label)


def _auto_contradict(a: Claim, b: Claim, *, label: str | None) -> None:
    """Emit ``Contradict(a, b)`` unless an existing same-type relation covers it.

    Symmetric to :func:`_auto_exclusive` — only same-type dedup,
    cross-type coexistence is left to the IR's own consistency
    machinery.
    """
    if any(isinstance(action, Contradict) for action in _existing_pair_relations(a, b)):
        return
    _emit_contradict(a, b, label=label)


def _ensure_structural_actions(
    hypotheses: tuple[Claim, ...],
    *,
    exclusivity: str,
    label: str | None,
) -> None:
    if len(hypotheses) < 2:
        return
    if exclusivity == "exhaustive_pairwise_complement":
        if len(hypotheses) > 2:
            # N-ary exclusive ("exactly one of M_1..M_N is true") needs a
            # dedicated IR primitive that we do not yet have; falling back
            # to pairwise Contradict would silently degrade to
            # at-most-one semantics and dilute posterior odds by the
            # (F,F,...,F) state's probability mass. Reject loudly until
            # the N-ary operator lands (see follow-up issue tracking
            # this limitation).
            raise NotImplementedError(
                "compare(exclusivity='exhaustive_pairwise_complement') "
                f"with {len(hypotheses)} models requires an N-ary Exclusive "
                "operator that is not yet implemented. Either: (a) use "
                "exclusivity='pairwise_contradiction' explicitly and "
                "accept at-most-one semantics (posterior will be diluted "
                "by the 'all-false' state), or (b) restrict the "
                "comparison to two models. Authors who previously relied "
                "on exclusivity='none' to defer to an external "
                "exclusive()/contradict() declaration can simply drop "
                "the argument: compare() now deduplicates against any "
                "external same-type structural action over the same "
                "hypothesis pair."
            )
        _auto_exclusive(hypotheses[0], hypotheses[1], label=label)
        return
    for a, b in combinations(hypotheses, 2):
        _auto_contradict(a, b, label=label)


def _comparison_hypotheses(model_actions: tuple[Model, ...]) -> tuple[Claim, ...]:
    hypotheses = tuple(action.hypothesis for action in model_actions)
    if any(h is None for h in hypotheses):
        raise ValueError("model() action is missing its hypothesis")
    typed_tuple = tuple(h for h in hypotheses if h is not None)
    if len({id(h) for h in typed_tuple}) != len(typed_tuple):
        raise ValueError("compare() received duplicate hypotheses through model helpers")
    return typed_tuple


def _validate_shared_observable(model_actions: tuple[Model, ...]) -> None:
    """All compared models must predict the same observable."""
    if not model_actions:
        return
    first_observable = model_actions[0].observable
    for action in model_actions[1:]:
        if action.observable is not first_observable:
            raise ValueError(
                "compare() model helpers must share one observable; got "
                f"{first_observable!r} vs {action.observable!r}"
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
    coerced: dict[Claim, float] = {}
    for key, raw in likelihoods.items():
        value = float(raw)
        # NaN means the wrapper failed to record a meaningful number; +inf
        # would silently get clamped to Cromwell-max and dominate every
        # other hypothesis. -inf is fine ("zero likelihood under this
        # hypothesis"); the lowering already drops -inf-only comparisons
        # via the "zero support under every hypothesis" check.
        if math.isnan(value):
            raise ValueError(
                "compare(precomputed=...) log-likelihood for "
                f"{key.label or key.content[:40]!r} is NaN. Fix the upstream "
                "wrapper to record a real log-likelihood (or -inf for "
                "zero-likelihood hypotheses), not a missing-value sentinel."
            )
        if math.isinf(value) and value > 0:
            raise ValueError(
                "compare(precomputed=...) log-likelihood for "
                f"{key.label or key.content[:40]!r} is +inf. A finite "
                "log-likelihood is required; +inf would silently dominate "
                "the comparison via Cromwell clamping."
            )
        coerced[key] = value
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
    exclusivity: str = "exhaustive_pairwise_complement",
    precomputed: dict[Claim, float] | PrecomputedLikelihoods | None = None,
    metadata: dict[str, Any] | None = None,
) -> Claim:
    """Compare observed data against an equal-positioned list of models.

    Returns the comparison helper Claim. The helper carries
    ``metadata["comparison"]`` describing the exclusivity contract and,
    after compilation, the per-hypothesis log-likelihood table.

    Point vs composite hypotheses
    -----------------------------
    Use a point distribution such as ``Binomial(n, p=v)`` only when the
    hypothesis really fixes the parameter value. If the hypothesis
    commits to a direction or region instead, use a compound
    distribution such as ``BetaBinomial(n, alpha, beta)``.

    Comparing a point hypothesis with a diffuse alternative such as
    ``BetaBinomial(n, alpha=1, beta=1)`` can produce extreme Bayes
    factors from one Gaia observation claim when the data are only
    slightly off the point. Run ``gaia sdk`` for the local SDK reference
    and cheat sheet; see the Bayes Hypothesis Types guide in the Gaia
    docs (``docs/for-users/bayes-hypothesis-types.md``) for the full
    treatment.

    Exclusivity contracts
    ---------------------
    ``exclusivity`` controls what structural-action relationship Gaia
    asserts between the compared hypotheses. **The choice of contract
    materially changes the posterior** because it changes the set of
    joint hypothesis states the factor graph is allowed to occupy:

    * ``"exhaustive_pairwise_complement"`` (**default**, 2 models only):
      ensure ``exclusive(m1, m2)`` is in the package — exactly one of
      the two hypotheses is true. Posterior odds equal the
      (Cromwell-clamped) likelihood ratio. This is the standard
      Bayesian model-selection contract and the right default when the
      author intends "which of these two competing models best explains
      the data". Currently rejected for ``len(models) > 2`` until an
      N-ary Exclusive operator is implemented; use
      ``"pairwise_contradiction"`` (at-most-one semantics) meanwhile.

    * ``"pairwise_contradiction"`` (≥2 models): ensure
      ``contradict(m_i, m_j)`` is in the package for every pair.
      At-most-one is true; an "all false" joint state is allowed. The
      hardcoded ``α=0.5`` anchor in each ``infer`` factor's CPT then
      assigns substantial mass to that joint state, **diluting
      model-comparison posterior odds**. Use this only when you
      genuinely believe the listed models may all be wrong and want the
      posterior to reflect that.

    Deduplication
    -------------
    ``compare()`` does not blindly create new structural actions —
    before emitting it scans the active package for an existing
    same-type relation covering the same hypothesis pair:

    * **No same-type external declaration**: ``compare()`` emits the
      auto-generated structural action matching ``exclusivity``.
    * **Same-type external declaration already in place** (e.g.
      external ``exclusive(m1, m2)`` and ``exclusivity=
      "exhaustive_pairwise_complement"``): ``compare()`` skips
      emission. The external author's helper Claim and rationale are
      preserved.
    * **Different-type external declaration** (e.g. external
      ``contradict(m1, m2)`` while ``compare()`` wants to emit
      ``exclusive(m1, m2)``): both actions coexist. They are logically
      consistent — ``Exclusive`` implies ``Contradict``, so the joint
      factor-graph constraint is just ``Exclusive``. The IR's own
      structural-relation consistency checks (the D2 "same operator +
      same args + distinct conclusions" rule and friends) are the
      authority on whether the combined graph is legal, not the DSL.

    The previous ``exclusivity="none"`` escape hatch (which suppressed
    auto-generation entirely) is no longer accepted: same-type dedup
    serves the same purpose without letting authors silently bypass
    any contract.
    """
    data_tuple = _as_claim_tuple(data, name="data")
    models_tuple = _as_claim_tuple(models, name="models")
    if len(models_tuple) < 2:
        raise ValueError("compare() requires at least two models")
    if exclusivity == "none":
        # 'none' used to mean "skip auto-generation; I declared exclusivity
        # externally myself". It is no longer accepted because compare()
        # now deduplicates against external exclusive()/contradict()
        # actions over the same hypothesis pair, so the dedicated escape
        # hatch is redundant. Keeping it would also let authors silently
        # bypass any exclusivity contract, which the new default exists
        # precisely to prevent.
        raise ValueError(
            "compare(exclusivity='none') is no longer accepted. compare() "
            "now deduplicates against any external exclusive() / "
            "contradict() declaration over the same hypothesis pair, so "
            "you can drop the argument: the default "
            "('exhaustive_pairwise_complement') will skip auto-emission "
            "when an external structural action is already in place. If "
            "you want at-most-one semantics, pass "
            "exclusivity='pairwise_contradiction' explicitly."
        )
    if exclusivity not in _EXCLUSIVITY_VALUES:
        raise ValueError(f"unknown exclusivity mode: {exclusivity!r}")

    model_actions = tuple(_model_action(m) for m in models_tuple)
    hypothesis_tuple = _comparison_hypotheses(model_actions)
    _validate_shared_observable(model_actions)
    log_likelihoods, precomputed_claim = _normalize_precomputed(precomputed, hypothesis_tuple)

    _ensure_structural_actions(hypothesis_tuple, exclusivity=exclusivity, label=label)

    helper = Claim(
        "Bayes model comparison.",
        background=background or [],
        metadata=_comparison_metadata(metadata, exclusivity=exclusivity, rationale=rationale),
        prior=1.0 - CROMWELL_EPS,
    )
    helper.label = label

    if precomputed_claim is not None:
        recorded_precomputed: Any = precomputed_claim
    elif log_likelihoods:
        recorded_precomputed = dict(log_likelihoods)
    else:
        recorded_precomputed = None
    action = ModelCompare(
        label=label,
        rationale=rationale,
        background=list(background or []),
        metadata={"bayes": {"action": "model_compare"}},
        helper=helper,
        models=models_tuple,
        data=data_tuple,
        exclusivity=exclusivity,
        precomputed=recorded_precomputed,
        log_likelihoods=log_likelihoods,
    )
    validate_no_self_warrant(action, helper)
    attach_reasoning(helper, action)
    return helper
