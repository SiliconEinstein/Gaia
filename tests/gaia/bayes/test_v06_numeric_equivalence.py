"""Numeric equivalence between the v0.5 and v0.6 Bayes surfaces.

For the canonical Mendel 3:1-vs-null Binomial comparison the v0.6 unified
surface (``predict`` / ``observe(Variable, ...)`` / ``compare``) must
produce the same posterior beliefs as the v0.5 surface (``bayes.model`` /
``bayes.data`` / ``bayes.likelihood``). This file pins that equality.

Also exercises the new :class:`PrecomputedLikelihoods` Claim subclass:
the ``compare(precomputed=Claim)`` path must agree numerically with the
internally-computed comparison when the supplied log-likelihoods are the
ones the lowering would have computed itself.
"""

from __future__ import annotations

import math

import scipy.stats as stats

import gaia.engine.bayes as bayes
from gaia.engine.bayes.runtime.precomputed import PrecomputedLikelihoods
from gaia.engine.bp.exact import exact_inference
from gaia.engine.bp.lowering import lower_local_graph
from gaia.engine.lang import (
    BetaBinomial as LangBetaBinomial,
)
from gaia.engine.lang import (
    Binomial as LangBinomial,
)
from gaia.engine.lang import (
    Constant,
    Nat,
    Probability,
    Variable,
    claim,
    compute,
    equals,
    observe,
    parameter,
)
from gaia.engine.lang.compiler.compile import compile_package_artifact
from gaia.engine.lang.runtime.knowledge import _current_package
from gaia.engine.lang.runtime.package import CollectedPackage


def _v05_observed_value(variable: Variable, value: int, *, label: str) -> "object":
    """v0.5 observation Claim shape: formula + bayes.data-style metadata."""
    data = claim(
        f"Observed {variable.symbol} = {value}.",
        formula=equals(variable, Constant(value, variable.domain)),
        metadata={},
    )
    observe(data, rationale=data.content, label=f"observe_{label}")
    data.label = label
    return data


def _build_v05_mendel(*, exclusivity: str):
    pkg = CollectedPackage(name="mendel_v05_equiv", namespace="t")
    token = _current_package.set(pkg)
    try:
        theta = Variable(symbol="theta", domain=Probability)
        k = Variable(symbol="k", domain=Nat, value=295)
        n = 395

        h_31 = parameter(theta, 0.75, content="theta = 0.75.", prior=0.5, label="h_3_1")
        h_null = parameter(theta, 0.5, content="theta = 0.5.", prior=0.5, label="h_null")
        data = _v05_observed_value(k, 295, label="data")
        model_31 = bayes.model(
            h_31,
            observable=k,
            distribution=bayes.Binomial(n=n, p=theta),
            label="model_3_1",
        )
        model_null = bayes.model(
            h_null,
            observable=k,
            distribution=bayes.Binomial(n=n, p=theta),
            label="model_null",
        )
        cmp_result = bayes.likelihood(
            data,
            model=model_31,
            against=[model_null],
            exclusivity=exclusivity,
            label="likelihood",
        )
    finally:
        _current_package.reset(token)
    return pkg, h_31, h_null, data, cmp_result


def _build_v06_mendel(*, exclusivity: str):
    pkg = CollectedPackage(name="mendel_v06_equiv", namespace="t")
    token = _current_package.set(pkg)
    try:
        theta = Variable(symbol="theta", domain=Probability)
        k = Variable(symbol="k", domain=Nat, value=295)
        n = 395

        h_31 = parameter(theta, 0.75, content="theta = 0.75.", prior=0.5, label="h_3_1")
        h_null = parameter(theta, 0.5, content="theta = 0.5.", prior=0.5, label="h_null")
        data = observe(k, value=295, label="data", rationale="Observed k = 295.")
        pred_31 = bayes.predict(
            h_31,
            target=k,
            distribution=LangBinomial("k under 3:1", n=n, p=theta),
            label="model_3_1",
        )
        pred_null = bayes.predict(
            h_null,
            target=k,
            distribution=LangBinomial("k under null", n=n, p=theta),
            label="model_null",
        )
        cmp_result = bayes.compare(
            data,
            models=[pred_31, pred_null],
            exclusivity=exclusivity,
            label="likelihood",
        )
    finally:
        _current_package.reset(token)
    return pkg, h_31, h_null, data, cmp_result


def _beliefs(pkg, h_31, h_null, cmp_result) -> dict[str, float]:
    compiled = compile_package_artifact(pkg)
    beliefs, _ = exact_inference(lower_local_graph(compiled.graph))
    return {
        "h_31": beliefs[compiled.knowledge_ids_by_object[id(h_31)]],
        "h_null": beliefs[compiled.knowledge_ids_by_object[id(h_null)]],
        "cmp": beliefs[compiled.knowledge_ids_by_object[id(cmp_result)]],
    }


def test_v05_v06_posteriors_match_under_exhaustive_exclusivity():
    """exclusivity='exhaustive_pairwise_complement' — the canonical case."""
    pkg_v05, h_31_v05, h_null_v05, _, cmp_v05 = _build_v05_mendel(
        exclusivity="exhaustive_pairwise_complement"
    )
    pkg_v06, h_31_v06, h_null_v06, _, cmp_v06 = _build_v06_mendel(
        exclusivity="exhaustive_pairwise_complement"
    )
    b_v05 = _beliefs(pkg_v05, h_31_v05, h_null_v05, cmp_v05)
    b_v06 = _beliefs(pkg_v06, h_31_v06, h_null_v06, cmp_v06)
    assert math.isclose(b_v05["h_31"], b_v06["h_31"], rel_tol=1e-9, abs_tol=1e-12)
    assert math.isclose(b_v05["h_null"], b_v06["h_null"], rel_tol=1e-9, abs_tol=1e-12)
    assert math.isclose(b_v05["cmp"], b_v06["cmp"], rel_tol=1e-9, abs_tol=1e-12)


def test_v05_v06_posteriors_match_under_pairwise_contradiction():
    """exclusivity='pairwise_contradiction' — at-most-one-true case."""
    pkg_v05, h_31_v05, h_null_v05, _, cmp_v05 = _build_v05_mendel(
        exclusivity="pairwise_contradiction"
    )
    pkg_v06, h_31_v06, h_null_v06, _, cmp_v06 = _build_v06_mendel(
        exclusivity="pairwise_contradiction"
    )
    b_v05 = _beliefs(pkg_v05, h_31_v05, h_null_v05, cmp_v05)
    b_v06 = _beliefs(pkg_v06, h_31_v06, h_null_v06, cmp_v06)
    assert math.isclose(b_v05["h_31"], b_v06["h_31"], rel_tol=1e-9, abs_tol=1e-12)
    assert math.isclose(b_v05["h_null"], b_v06["h_null"], rel_tol=1e-9, abs_tol=1e-12)
    assert math.isclose(b_v05["cmp"], b_v06["cmp"], rel_tol=1e-9, abs_tol=1e-12)


def test_v05_v06_posteriors_match_under_no_exclusivity():
    """exclusivity='none' — Mendel-style asymmetric comparison."""
    pkg_v05, h_31_v05, h_null_v05, _, cmp_v05 = _build_v05_mendel(exclusivity="none")
    pkg_v06, h_31_v06, h_null_v06, _, cmp_v06 = _build_v06_mendel(exclusivity="none")
    b_v05 = _beliefs(pkg_v05, h_31_v05, h_null_v05, cmp_v05)
    b_v06 = _beliefs(pkg_v06, h_31_v06, h_null_v06, cmp_v06)
    assert math.isclose(b_v05["h_31"], b_v06["h_31"], rel_tol=1e-9, abs_tol=1e-12)
    assert math.isclose(b_v05["h_null"], b_v06["h_null"], rel_tol=1e-9, abs_tol=1e-12)
    assert math.isclose(b_v05["cmp"], b_v06["cmp"], rel_tol=1e-9, abs_tol=1e-12)


def test_v06_betabinomial_diffuse_matches_v05_mendel_example():
    """Mendel 3:1 vs BetaBinomial(N, 1, 1) — the example package's exact shape."""
    n = 395
    k_observed = 295

    pkg_v06 = CollectedPackage(name="mendel_v06_betabinomial", namespace="t")
    token = _current_package.set(pkg_v06)
    try:
        theta = Variable(symbol="theta", domain=Probability)
        k_var = Variable(symbol="k", domain=Nat, value=k_observed)
        mendel = claim("mendelian segregation", prior=0.5, label="mendel")
        diffuse = claim("blending inheritance", prior=0.5, label="diffuse")
        data = observe(k_var, value=k_observed, label="data")
        mendel_pred = bayes.predict(
            mendel,
            target=k_var,
            distribution=LangBinomial("k under Mendel", n=n, p=3 / 4),
            label="mendel_pred",
        )
        diffuse_pred = bayes.predict(
            diffuse,
            target=k_var,
            distribution=LangBetaBinomial(
                "k under diffuse", n=n, alpha=1.0, beta=1.0
            ),
            label="diffuse_pred",
        )
        cmp_v06 = bayes.compare(
            data,
            models=[mendel_pred, diffuse_pred],
            exclusivity="none",
            label="comparison",
        )
    finally:
        _current_package.reset(token)

    compiled = compile_package_artifact(pkg_v06)
    cmp_id = compiled.knowledge_ids_by_object[id(cmp_v06)]
    mendel_id = compiled.knowledge_ids_by_object[id(mendel)]
    diffuse_id = compiled.knowledge_ids_by_object[id(diffuse)]
    metadata = next(
        k for k in compiled.graph.knowledges if k.id == cmp_id
    ).metadata
    likelihoods = metadata["comparison"]["likelihoods"]
    assert likelihoods[mendel_id] == pytest_approx(
        stats.binom.logpmf(k_observed, n=n, p=3 / 4)
    )
    assert likelihoods[diffuse_id] == pytest_approx(
        stats.betabinom.logpmf(k_observed, n=n, a=1, b=1)
    )


def test_v06_precomputed_dict_matches_internal_evaluation():
    """compare(precomputed={h: logL}) reproduces the internal-eval BP outcome."""
    pkg_internal, h_31_i, h_null_i, _, cmp_internal = _build_v06_mendel(
        exclusivity="exhaustive_pairwise_complement"
    )
    b_internal = _beliefs(pkg_internal, h_31_i, h_null_i, cmp_internal)

    n = 395
    k = 295
    logL_31 = float(stats.binom.logpmf(k, n=n, p=0.75))
    logL_null = float(stats.binom.logpmf(k, n=n, p=0.50))

    pkg_pre = CollectedPackage(name="mendel_v06_precomputed_dict", namespace="t")
    token = _current_package.set(pkg_pre)
    try:
        theta = Variable(symbol="theta", domain=Probability)
        k_var = Variable(symbol="k", domain=Nat, value=k)
        h_31 = parameter(theta, 0.75, content="theta = 0.75.", prior=0.5, label="h_3_1")
        h_null = parameter(theta, 0.5, content="theta = 0.5.", prior=0.5, label="h_null")
        data = observe(k_var, value=k, label="data")
        pred_31 = bayes.predict(
            h_31,
            target=k_var,
            distribution=LangBinomial("k under 3:1", n=n, p=theta),
            label="model_3_1",
        )
        pred_null = bayes.predict(
            h_null,
            target=k_var,
            distribution=LangBinomial("k under null", n=n, p=theta),
            label="model_null",
        )
        cmp_pre = bayes.compare(
            data,
            models=[pred_31, pred_null],
            exclusivity="exhaustive_pairwise_complement",
            precomputed={h_31: logL_31, h_null: logL_null},
            label="likelihood",
        )
    finally:
        _current_package.reset(token)
    b_pre = _beliefs(pkg_pre, h_31, h_null, cmp_pre)

    assert math.isclose(b_internal["h_31"], b_pre["h_31"], rel_tol=1e-9, abs_tol=1e-12)
    assert math.isclose(b_internal["h_null"], b_pre["h_null"], rel_tol=1e-9, abs_tol=1e-12)
    assert math.isclose(b_internal["cmp"], b_pre["cmp"], rel_tol=1e-9, abs_tol=1e-12)


def test_v06_precomputed_claim_matches_internal_evaluation():
    """compare(precomputed=PrecomputedLikelihoods) is equivalent to the dict form.

    Exercises the v0.6 compute-layer path: a :class:`PrecomputedLikelihoods`
    Claim subclass carries the same hypothesis -> log-likelihood mapping,
    plus solver diagnostics, and feeds compare() through the same factor
    pipeline as the bare-dict form.
    """
    pkg_internal, h_31_i, h_null_i, _, cmp_internal = _build_v06_mendel(
        exclusivity="exhaustive_pairwise_complement"
    )
    b_internal = _beliefs(pkg_internal, h_31_i, h_null_i, cmp_internal)

    n = 395
    k = 295
    logL_31 = float(stats.binom.logpmf(k, n=n, p=0.75))
    logL_null = float(stats.binom.logpmf(k, n=n, p=0.50))

    pkg_pre = CollectedPackage(name="mendel_v06_precomputed_claim", namespace="t")
    token = _current_package.set(pkg_pre)
    try:
        theta = Variable(symbol="theta", domain=Probability)
        k_var = Variable(symbol="k", domain=Nat, value=k)
        h_31 = parameter(theta, 0.75, content="theta = 0.75.", prior=0.5, label="h_3_1")
        h_null = parameter(theta, 0.5, content="theta = 0.5.", prior=0.5, label="h_null")
        data = observe(k_var, value=k, label="data")
        pred_31 = bayes.predict(
            h_31,
            target=k_var,
            distribution=LangBinomial("k under 3:1", n=n, p=theta),
            label="model_3_1",
        )
        pred_null = bayes.predict(
            h_null,
            target=k_var,
            distribution=LangBinomial("k under null", n=n, p=theta),
            label="model_null",
        )
        precomputed = PrecomputedLikelihoods(
            "Mendel 3:1 vs null mock-solver run.",
            log_likelihoods={h_31: logL_31, h_null: logL_null},
            diagnostics={"r_hat_max": 1.0, "seed": 12345, "draws": 1000},
            solver="mock-nuts-1000",
            label="mock_solver_run",
        )
        cmp_pre = bayes.compare(
            data,
            models=[pred_31, pred_null],
            exclusivity="exhaustive_pairwise_complement",
            precomputed=precomputed,
            label="likelihood",
        )
    finally:
        _current_package.reset(token)
    b_pre = _beliefs(pkg_pre, h_31, h_null, cmp_pre)

    assert math.isclose(b_internal["h_31"], b_pre["h_31"], rel_tol=1e-9, abs_tol=1e-12)
    assert math.isclose(b_internal["h_null"], b_pre["h_null"], rel_tol=1e-9, abs_tol=1e-12)
    assert math.isclose(b_internal["cmp"], b_pre["cmp"], rel_tol=1e-9, abs_tol=1e-12)

    # Sanity: the PrecomputedLikelihoods Claim retains its solver / diagnostics
    # so reviewers and audit rules can inspect them.
    assert precomputed.solver == "mock-nuts-1000"
    assert precomputed.diagnostics == {"r_hat_max": 1.0, "seed": 12345, "draws": 1000}
    assert precomputed.log_likelihoods == {h_31: logL_31, h_null: logL_null}


def test_v06_precomputed_via_compute_decorator():
    """End-to-end: a @compute-wrapped function returns PrecomputedLikelihoods.

    Mirrors the spec's external-solver pattern. The wrapper here is a
    deterministic stub (no PyMC dependency) but it goes through the
    standard :class:`Compute` Action machinery, so the resulting Claim
    flows into compare() with a full audit trail.
    """
    n = 395
    k = 295

    pkg = CollectedPackage(name="mendel_v06_compute_solver", namespace="t")
    token = _current_package.set(pkg)
    try:
        theta = Variable(symbol="theta", domain=Probability)
        k_var = Variable(symbol="k", domain=Nat, value=k)
        h_31 = parameter(theta, 0.75, content="theta = 0.75.", prior=0.5, label="h_3_1")
        h_null = parameter(theta, 0.5, content="theta = 0.5.", prior=0.5, label="h_null")
        data = observe(k_var, value=k, label="data")
        pred_31 = bayes.predict(
            h_31,
            target=k_var,
            distribution=LangBinomial("k under 3:1", n=n, p=theta),
            label="model_3_1",
        )
        pred_null = bayes.predict(
            h_null,
            target=k_var,
            distribution=LangBinomial("k under null", n=n, p=theta),
            label="model_null",
        )

        @compute
        def mock_solver_run(
            data: object, h_31: object, h_null: object
        ) -> PrecomputedLikelihoods:
            """Deterministic stub of an external solver."""
            return PrecomputedLikelihoods(
                "Mock solver result.",
                log_likelihoods={
                    h_31: float(stats.binom.logpmf(k, n=n, p=0.75)),
                    h_null: float(stats.binom.logpmf(k, n=n, p=0.50)),
                },
                diagnostics={"r_hat_max": 1.0, "seed": 42},
                solver="mock-stub",
            )

        result = mock_solver_run(data, h_31, h_null)
        assert isinstance(result, PrecomputedLikelihoods)
        cmp_result = bayes.compare(
            data,
            models=[pred_31, pred_null],
            exclusivity="exhaustive_pairwise_complement",
            precomputed=result,
            label="comparison",
        )
    finally:
        _current_package.reset(token)

    compiled = compile_package_artifact(pkg)
    beliefs, _ = exact_inference(lower_local_graph(compiled.graph))
    h_31_id = compiled.knowledge_ids_by_object[id(h_31)]
    h_null_id = compiled.knowledge_ids_by_object[id(h_null)]
    # The precomputed log-likelihoods come from binom.logpmf, so the posterior
    # is the same canonical Mendel-vs-null outcome.
    assert beliefs[h_31_id] > 0.95
    assert beliefs[h_null_id] < 0.05


# ---------------------------------------------------------------------------
# Local pytest.approx without importing pytest at top level (avoids a hard
# pytest dependency in case this file is imported as a smoke check).
# ---------------------------------------------------------------------------


def pytest_approx(expected: float, *, rel: float = 1e-9, abs_: float = 1e-12):
    """Mimic pytest.approx for the few places we need it."""
    import pytest

    return pytest.approx(expected, rel=rel, abs=abs_)
