"""Compile-time diagnostics for the continuous-quantity surface.

Two detectors emit Python warnings during ``compile_package_artifact``:

1. :class:`DeadContinuousQuantityWarning` — author declared a
   :class:`Distribution` (e.g. ``T_c = Normal(...)``) but never referenced it
   in any claim's predicate / equation / observation metadata. Catches typos
   and forgotten quantities.

2. :class:`ObservationNotUpdatingPredicateWarning` — author both observed a
   distribution and wrote a predicate over the same distribution; the
   predicate prior is currently computed from the distribution's *prior* CDF
   without incorporating observations. This is a real correctness gap that
   the v0.7 posterior-CDF work will close (tracked separately); this warning
   surfaces the limitation so authors are not silently misled by a
   prior-CDF-only result.

Both detectors are non-fatal — they emit warnings, never errors. Authors
who intentionally want a unreferenced distribution or a predicate-without-
posterior-update can suppress them with the standard ``warnings.filterwarnings``
machinery, scoping by category for precision.
"""

from __future__ import annotations

import warnings
from typing import TYPE_CHECKING, Any

from gaia.lang.compiler.predicate_lowering import (
    PREDICATE_LOWERING_SOURCE_ID,
    PREDICATE_PRIOR_GENERATED_ATTR,
)
from gaia.lang.dsl.bool_expr import BoolExpr, DerivedDistribution
from gaia.lang.runtime.distribution import Distribution
from gaia.lang.runtime.knowledge import Claim

if TYPE_CHECKING:
    from gaia.lang.runtime.package import CollectedPackage


class DeadContinuousQuantityWarning(UserWarning):
    """A Distribution was declared but never referenced anywhere in the package."""


class ObservationNotUpdatingPredicateWarning(UserWarning):
    """Predicate prior was computed from prior CDF without observations.

    A predicate over a Distribution that has recorded observations does not
    yet incorporate the observation into its prior — the prior CDF is used
    directly. Posterior CDF support is deferred to a future release.
    """


def _walk_distributions(value: Any, sink: set[int]) -> None:
    """Recursively collect every Distribution id referenced inside ``value``.

    Walks BoolExpr / DerivedDistribution nesting plus dict / list / tuple
    containers so the detector sees every distribution mentioned anywhere
    in a claim's metadata.
    """
    if isinstance(value, Distribution):
        sink.add(id(value))
        return
    if isinstance(value, (BoolExpr, DerivedDistribution)):
        _walk_distributions(value.left, sink)
        _walk_distributions(value.right, sink)
        return
    if isinstance(value, dict):
        for v in value.values():
            _walk_distributions(v, sink)
        return
    if isinstance(value, (list, tuple, set)):
        for v in value:
            _walk_distributions(v, sink)
        return


def _referenced_distribution_ids(pkg: CollectedPackage) -> set[int]:
    """Set of Distribution object-ids referenced by any claim in the package."""
    referenced: set[int] = set()
    for knowledge in pkg.knowledge:
        if isinstance(knowledge, Claim):
            _walk_distributions(knowledge.metadata, referenced)
    return referenced


def _observed_distribution_to_obs_claims(
    pkg: CollectedPackage,
) -> dict[int, list[Claim]]:
    """Map distribution id to the list of observation claims targeting it."""
    out: dict[int, list[Claim]] = {}
    for knowledge in pkg.knowledge:
        if not isinstance(knowledge, Claim):
            continue
        observation = (knowledge.metadata or {}).get("observation")
        if not isinstance(observation, dict):
            continue
        target = observation.get("target_distribution")
        if isinstance(target, Distribution):
            out.setdefault(id(target), []).append(knowledge)
    return out


def _predicated_distribution_to_pred_claims(
    pkg: CollectedPackage,
) -> dict[int, list[Claim]]:
    """Map distribution id to the list of predicate claims with it as the LHS."""
    out: dict[int, list[Claim]] = {}
    for knowledge in pkg.knowledge:
        if not isinstance(knowledge, Claim):
            continue
        predicate = (knowledge.metadata or {}).get("predicate")
        if isinstance(predicate, BoolExpr) and isinstance(predicate.left, Distribution):
            prior_was_generated = bool(getattr(knowledge, PREDICATE_PRIOR_GENERATED_ATTR, False))
            if knowledge.prior is not None and not prior_was_generated:
                continue
            if knowledge.metadata.get("prior_source_id") not in {
                None,
                PREDICATE_LOWERING_SOURCE_ID,
            }:
                continue
            out.setdefault(id(predicate.left), []).append(knowledge)
    return out


def detect_dead_distributions(pkg: CollectedPackage) -> list[Distribution]:
    """Return Distributions declared on the package but never referenced."""
    referenced = _referenced_distribution_ids(pkg)
    return [d for d in pkg.distributions if id(d) not in referenced]


def detect_observation_not_updating_predicate(
    pkg: CollectedPackage,
) -> list[tuple[Distribution, list[Claim], list[Claim]]]:
    """Find (distribution, observations, predicates) triples that share a target.

    For each triple, the predicate prior was computed from the distribution's
    prior CDF without incorporating the observation(s) — a known v0.6
    limitation that the posterior-CDF work will close.
    """
    observed = _observed_distribution_to_obs_claims(pkg)
    predicated = _predicated_distribution_to_pred_claims(pkg)
    out: list[tuple[Distribution, list[Claim], list[Claim]]] = []
    for dist_id in observed.keys() & predicated.keys():
        # Recover the Distribution object from any of the observation claims
        # (they all share the same target).
        sample_obs = observed[dist_id][0]
        target = sample_obs.metadata["observation"]["target_distribution"]
        out.append((target, observed[dist_id], predicated[dist_id]))
    return out


def _label_or_content(d: Distribution) -> str:
    return d.label or (d.content[:50] + ("..." if len(d.content) > 50 else ""))


def _claim_label_or_content(c: Claim) -> str:
    return c.label or (c.content[:60] + ("..." if len(c.content) > 60 else ""))


def emit_distribution_warnings(pkg: CollectedPackage) -> None:
    """Run both detectors and surface their findings via :mod:`warnings`.

    Called from :func:`compile_package_artifact` immediately after predicate
    lowering. Warnings surface in pytest output, in the CLI, and through any
    standard ``warnings.catch_warnings`` capture.
    """
    for dead in detect_dead_distributions(pkg):
        warnings.warn(
            f"Continuous quantity {_label_or_content(dead)!r} "
            f"({dead.kind} distribution) was declared but never referenced "
            "in any claim, predicate, equation, or observation. Either "
            "reference it from a claim or remove the declaration. "
            "If this is intentional, suppress with "
            "warnings.filterwarnings('ignore', "
            "category=DeadContinuousQuantityWarning).",
            DeadContinuousQuantityWarning,
            stacklevel=2,
        )

    for target, obs_claims, pred_claims in detect_observation_not_updating_predicate(pkg):
        obs_labels = ", ".join(_claim_label_or_content(c) for c in obs_claims)
        pred_labels = ", ".join(_claim_label_or_content(c) for c in pred_claims)
        warnings.warn(
            f"Predicate(s) {{{pred_labels}}} over distribution "
            f"{_label_or_content(target)!r} compute their prior from the "
            f"prior CDF directly, without incorporating the observation(s) "
            f"{{{obs_labels}}}. Posterior-aware CDF is tracked separately for "
            "a future release. Until then, either set `prior=` explicitly on "
            "the predicate claim to reflect the post-observation belief, or "
            "express the inference via gaia.lang.bayes.likelihood().",
            ObservationNotUpdatingPredicateWarning,
            stacklevel=2,
        )
