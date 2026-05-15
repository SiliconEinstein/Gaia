"""Compile-time continuous-quantity diagnostics tests.

Two warning categories surface real authoring mistakes / known limitations:

* :class:`DeadContinuousQuantityWarning` — declared but never referenced.
* :class:`ObservationNotUpdatingPredicateWarning` — predicate prior was
  computed from the prior CDF without incorporating recorded observations.
"""

from __future__ import annotations

import warnings
from collections.abc import Callable
from typing import Any

import pytest

from gaia.engine.lang import Normal, claim, observe, register_prior
from gaia.engine.lang.compiler.compile import compile_package_artifact
from gaia.engine.lang.compiler.distribution_diagnostics import (
    DeadContinuousQuantityWarning,
    ObservationNotUpdatingPredicateWarning,
    detect_dead_distributions,
    detect_observation_not_updating_predicate,
)
from gaia.engine.lang.runtime.knowledge import _current_package
from gaia.engine.lang.runtime.package import CollectedPackage


def _build(make: Callable[[], Any]) -> CollectedPackage:
    pkg = CollectedPackage(name="diag_test_pkg", namespace="t")
    token = _current_package.set(pkg)
    try:
        make()
    finally:
        _current_package.reset(token)
    return pkg


# --------------------------------------------------------------------------- #
# Detector unit tests                                                         #
# --------------------------------------------------------------------------- #


def test_detect_dead_distribution_finds_unreferenced():
    def make() -> None:
        T_used = Normal("T_used", mu=200, sigma=50)
        T_dead = Normal("T_dead", mu=100, sigma=20)
        c = claim("uses T_used", T_used > 150)
        c.label = "c"
        del T_dead  # explicit: T_dead is never referenced

    pkg = _build(make)
    dead = detect_dead_distributions(pkg)
    assert len(dead) == 1
    assert dead[0].content == "T_dead"


def test_detect_dead_distribution_clean_when_all_used():
    def make() -> None:
        T_c = Normal("T_c", mu=200, sigma=50)
        c = claim("c", T_c > 150)
        c.label = "c"

    pkg = _build(make)
    assert detect_dead_distributions(pkg) == []


def test_detect_dead_distribution_recognises_observation_reference():
    """A Distribution referenced only via an observation Claim is still alive."""

    def make() -> None:
        T_c = Normal("T_c", mu=200, sigma=50)
        observe(T_c, value=203, error=5)

    pkg = _build(make)
    assert detect_dead_distributions(pkg) == []


def test_detect_dead_distribution_recognises_equation_reference():
    """A Distribution used in an equation BoolExpr counts as alive."""

    def make() -> None:
        A = Normal("A", mu=10, sigma=1)
        B = Normal("B", mu=10, sigma=1)
        eq = claim("A equals B", A == B, prior=0.5)
        eq.label = "eq"

    pkg = _build(make)
    assert detect_dead_distributions(pkg) == []


def test_detect_dead_distribution_recurses_into_derived_distribution():
    """Distribution buried inside a DerivedDistribution chain is still alive."""

    def make() -> None:
        A = Normal("A", mu=10, sigma=1)
        B = Normal("B", mu=10, sigma=1)
        rhs = A * 2 + B / 3
        eq = claim("A * 2 + B / 3 equals 5", rhs == 5, prior=0.5)
        eq.label = "eq"

    pkg = _build(make)
    assert detect_dead_distributions(pkg) == []


def test_detect_observation_not_updating_predicate_pairs():
    def make() -> None:
        T_c = Normal("T_c", mu=200, sigma=50)
        obs = observe(T_c, value=203, error=5)
        obs.label = "obs"
        high = claim("high T_c", T_c > 77)
        high.label = "high"

    pkg = _build(make)
    pairs = detect_observation_not_updating_predicate(pkg)
    assert len(pairs) == 1
    target, observations, predicates = pairs[0]
    assert target.content == "T_c"
    assert len(observations) == 1
    assert len(predicates) == 1


def test_detect_observation_not_updating_predicate_no_overlap():
    """Predicate without observation, or observation without predicate, is fine."""

    def make() -> None:
        T_a = Normal("T_a", mu=200, sigma=50)
        T_b = Normal("T_b", mu=100, sigma=20)
        # T_a only has a predicate (no observation)
        c1 = claim("ca", T_a > 150)
        c1.label = "ca"
        # T_b only has an observation (no predicate)
        observe(T_b, value=110, error=5)

    pkg = _build(make)
    assert detect_observation_not_updating_predicate(pkg) == []


def test_detect_observation_not_updating_predicate_skips_explicit_prior_override():
    def make() -> None:
        T_c = Normal("T_c", mu=200, sigma=50)
        observe(T_c, value=203, error=5)
        high = claim("high T_c posterior belief", T_c > 77)
        high.label = "high"
        register_prior(high, 0.99, justification="posterior-aware author override")

    pkg = _build(make)
    compile_package_artifact(pkg)
    assert detect_observation_not_updating_predicate(pkg) == []


def test_detect_observation_not_updating_predicate_multiple_observations():
    """Multiple observations of the same target collapse to a single warning.

    The warning lists all observation claims sharing the target.
    """

    def make() -> None:
        T_c = Normal("T_c", mu=200, sigma=50)
        o1 = observe(T_c, value=203, error=5)
        o1.label = "o1"
        o2 = observe(T_c, value=205, error=4)
        o2.label = "o2"
        high = claim("high T_c", T_c > 77)
        high.label = "high"

    pkg = _build(make)
    pairs = detect_observation_not_updating_predicate(pkg)
    assert len(pairs) == 1
    _, observations, _ = pairs[0]
    assert len(observations) == 2


# --------------------------------------------------------------------------- #
# Compile-time warning emission                                               #
# --------------------------------------------------------------------------- #


def test_compile_emits_dead_distribution_warning():
    def make() -> None:
        T_used = Normal("T_used", mu=200, sigma=50)
        T_dead = Normal("T_dead", mu=100, sigma=20)
        c = claim("c", T_used > 150)
        c.label = "c"
        del T_dead

    pkg = _build(make)
    with pytest.warns(DeadContinuousQuantityWarning, match="T_dead"):
        compile_package_artifact(pkg)


def test_compile_emits_observation_not_updating_predicate_warning():
    def make() -> None:
        T_c = Normal("T_c", mu=200, sigma=50)
        observe(T_c, value=203, error=5)
        high = claim("high T_c", T_c > 77)
        high.label = "high"

    pkg = _build(make)
    with pytest.warns(ObservationNotUpdatingPredicateWarning, match="high"):
        compile_package_artifact(pkg)


def test_compile_does_not_warn_for_observed_predicate_with_explicit_prior_override():
    def make() -> None:
        T_c = Normal("T_c", mu=200, sigma=50)
        observe(T_c, value=203, error=5)
        high = claim("high T_c posterior belief", T_c > 77)
        high.label = "high"
        register_prior(high, 0.99, justification="posterior-aware author override")

    pkg = _build(make)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        compile_package_artifact(pkg)
    relevant = [w for w in caught if issubclass(w.category, ObservationNotUpdatingPredicateWarning)]
    assert relevant == []


def test_compile_still_warns_when_only_inline_prior_is_present():
    def make() -> None:
        T_c = Normal("T_c", mu=200, sigma=50)
        observe(T_c, value=203, error=5)
        high = claim("high T_c inline guess", T_c > 77, prior=0.99)
        high.label = "high"

    pkg = _build(make)
    with pytest.warns(ObservationNotUpdatingPredicateWarning, match="high"):
        compile_package_artifact(pkg)


def test_compile_clean_when_no_diagnostic_applies():
    def make() -> None:
        T_c = Normal("T_c", mu=200, sigma=50)
        c = claim("c", T_c > 77)
        c.label = "c"

    pkg = _build(make)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        compile_package_artifact(pkg)
    relevant = [
        w
        for w in caught
        if issubclass(
            w.category,
            (DeadContinuousQuantityWarning, ObservationNotUpdatingPredicateWarning),
        )
    ]
    assert relevant == []


def test_warning_can_be_filtered_off():
    """Authors can suppress the warning category when intentional.

    Useful for a work-in-progress placeholder Distribution declared but not
    yet wired into any claim.
    """

    def make() -> None:
        T_used = Normal("T_used", mu=200, sigma=50)
        Normal("T_dead", mu=100, sigma=20)
        c = claim("c", T_used > 150)
        c.label = "c"

    pkg = _build(make)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        warnings.filterwarnings("ignore", category=DeadContinuousQuantityWarning)
        compile_package_artifact(pkg)
    relevant = [w for w in caught if issubclass(w.category, DeadContinuousQuantityWarning)]
    assert relevant == []
