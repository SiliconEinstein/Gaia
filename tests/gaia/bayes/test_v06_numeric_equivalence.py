"""Numeric pins for the unified Bayes surface.

After the v0.5 clean break the surface is single-pathed: there is no
"v0.5 alpha" path to compare against. These tests instead pin the
canonical Mendel 3:1-vs-null and Mendel-vs-BetaBinomial-diffuse
posteriors against the closed-form ``scipy.stats`` log-likelihoods, and
exercise the three precomputed-input paths:

* ``compare(precomputed=dict)`` — the bare-dict shortcut.
* ``compare(precomputed=PrecomputedLikelihoods(...))`` — Claim-bearing
  external-solver output with diagnostics.
* ``@compute``-decorated wrapper returning :class:`PrecomputedLikelihoods` —
  the full audit path.

The numbers come from the worked Mendel example in
``docs/foundations/gaia-lang/bayes.md`` (Cromwell-clamped to ~498 odds
under ``exhaustive_pairwise_complement``).
"""

from __future__ import annotations

import math
from collections.abc import Callable
from typing import cast

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
    Nat,
    Probability,
    Variable,
    claim,
    compute,
    observe,
    parameter,
)
from gaia.engine.lang.compiler.compile import compile_package_artifact
from gaia.engine.lang.runtime.knowledge import Claim, _current_package
from gaia.engine.lang.runtime.package import CollectedPackage


def _build_mendel(*, exclusivity: str):
    """Build the canonical Mendel 3:1 vs Null 1:1 Binomial comparison."""
    pkg = CollectedPackage(name="mendel_unified", namespace="t")
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


# ---------------------------------------------------------------------------
# Internal-eval (no precomputed) pins
# ---------------------------------------------------------------------------


def test_mendel_log_likelihoods_match_scipy_under_exhaustive_exclusivity():
    pkg, h_31, h_null, _, cmp_result = _build_mendel(exclusivity="exhaustive_pairwise_complement")
    compiled = compile_package_artifact(pkg)
    cmp_id = compiled.knowledge_ids_by_object[id(cmp_result)]
    h_31_id = compiled.knowledge_ids_by_object[id(h_31)]
    h_null_id = compiled.knowledge_ids_by_object[id(h_null)]
    metadata = next(k for k in compiled.graph.knowledges if k.id == cmp_id).metadata
    likelihoods = metadata["comparison"]["likelihoods"]
    assert math.isclose(likelihoods[h_31_id], stats.binom.logpmf(295, n=395, p=0.75), rel_tol=1e-9)
    assert math.isclose(likelihoods[h_null_id], stats.binom.logpmf(295, n=395, p=0.5), rel_tol=1e-9)


def test_mendel_posteriors_match_worked_example_under_exhaustive_exclusivity():
    """exhaustive_pairwise_complement + equal 0.5 priors → Cromwell-clamped odds ≈ 498."""
    pkg, h_31, h_null, _, cmp_result = _build_mendel(exclusivity="exhaustive_pairwise_complement")
    b = _beliefs(pkg, h_31, h_null, cmp_result)
    assert b["h_31"] > 0.95
    assert b["h_null"] < 0.05
    assert b["cmp"] > 0.99
    # Cromwell clamp caps the pairwise odds at ~498 (see bayes.md worked example).
    assert b["h_31"] / b["h_null"] > 100.0


def test_mendel_betabinomial_diffuse_matches_scipy_betabinom():
    """Mendel 3:1 vs BetaBinomial(N, 1, 1) diffuse — the example package's exact shape."""
    n = 395
    k_observed = 295

    pkg = CollectedPackage(name="mendel_unified_diffuse", namespace="t")
    token = _current_package.set(pkg)
    try:
        k_var = Variable(symbol="k", domain=Nat, value=k_observed)
        mendel = claim("mendelian segregation", prior=0.5, label="mendel")
        diffuse = claim("diffuse alternative", prior=0.5, label="diffuse")
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
            distribution=LangBetaBinomial("k under diffuse", n=n, alpha=1.0, beta=1.0),
            label="diffuse_pred",
        )
        # Default ``exhaustive_pairwise_complement`` is fine here: the
        # test only reads metadata["comparison"]["likelihoods"], so the
        # auto-emitted Exclusive(mendel, diffuse) does not affect the
        # quantities being asserted. The earlier ``exclusivity="none"``
        # is no longer accepted.
        cmp_v06 = bayes.compare(
            data,
            models=[mendel_pred, diffuse_pred],
            label="comparison",
        )
    finally:
        _current_package.reset(token)

    compiled = compile_package_artifact(pkg)
    cmp_id = compiled.knowledge_ids_by_object[id(cmp_v06)]
    mendel_id = compiled.knowledge_ids_by_object[id(mendel)]
    diffuse_id = compiled.knowledge_ids_by_object[id(diffuse)]
    likelihoods = next(k for k in compiled.graph.knowledges if k.id == cmp_id).metadata[
        "comparison"
    ]["likelihoods"]
    assert math.isclose(
        likelihoods[mendel_id], stats.binom.logpmf(k_observed, n=n, p=3 / 4), rel_tol=1e-9
    )
    assert math.isclose(
        likelihoods[diffuse_id],
        stats.betabinom.logpmf(k_observed, n=n, a=1, b=1),
        rel_tol=1e-9,
    )


# ---------------------------------------------------------------------------
# Precomputed-input pins
# ---------------------------------------------------------------------------


def test_precomputed_dict_matches_internal_evaluation():
    """compare(precomputed={h: logL}) reproduces the internal-eval BP outcome."""
    pkg_internal, h_31_i, h_null_i, _, cmp_internal = _build_mendel(
        exclusivity="exhaustive_pairwise_complement"
    )
    b_internal = _beliefs(pkg_internal, h_31_i, h_null_i, cmp_internal)

    n = 395
    k = 295
    log_l_31 = float(stats.binom.logpmf(k, n=n, p=0.75))
    log_l_null = float(stats.binom.logpmf(k, n=n, p=0.50))

    pkg_pre = CollectedPackage(name="mendel_unified_pre_dict", namespace="t")
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
            precomputed={h_31: log_l_31, h_null: log_l_null},
            label="likelihood",
        )
    finally:
        _current_package.reset(token)
    b_pre = _beliefs(pkg_pre, h_31, h_null, cmp_pre)

    assert math.isclose(b_internal["h_31"], b_pre["h_31"], rel_tol=1e-9, abs_tol=1e-12)
    assert math.isclose(b_internal["h_null"], b_pre["h_null"], rel_tol=1e-9, abs_tol=1e-12)
    assert math.isclose(b_internal["cmp"], b_pre["cmp"], rel_tol=1e-9, abs_tol=1e-12)


def test_precomputed_claim_matches_internal_evaluation():
    """compare(precomputed=PrecomputedLikelihoods) is equivalent to the bare-dict form."""
    pkg_internal, h_31_i, h_null_i, _, cmp_internal = _build_mendel(
        exclusivity="exhaustive_pairwise_complement"
    )
    b_internal = _beliefs(pkg_internal, h_31_i, h_null_i, cmp_internal)

    n = 395
    k = 295
    log_l_31 = float(stats.binom.logpmf(k, n=n, p=0.75))
    log_l_null = float(stats.binom.logpmf(k, n=n, p=0.50))

    pkg_pre = CollectedPackage(name="mendel_unified_pre_claim", namespace="t")
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
            log_likelihoods={h_31: log_l_31, h_null: log_l_null},
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

    assert precomputed.solver == "mock-nuts-1000"
    assert precomputed.diagnostics == {"r_hat_max": 1.0, "seed": 12345, "draws": 1000}
    assert precomputed.log_likelihoods == {h_31: log_l_31, h_null: log_l_null}


def test_precomputed_via_compute_decorator():
    """End-to-end: a @compute-wrapped function returns PrecomputedLikelihoods.

    Mirrors the spec's external-solver pattern. The wrapper here is a
    deterministic stub (no PyMC dependency) but it goes through the
    standard :class:`Compute` Action machinery, so the resulting Claim
    flows into compare() with a full audit trail.
    """
    n = 395
    k = 295

    pkg = CollectedPackage(name="mendel_unified_compute_solver", namespace="t")
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
            data: Claim,  # noqa: ARG001 — recorded as Compute action dependency
            h_31: Claim,
            h_null: Claim,
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

        solver = cast(
            Callable[[Claim, Claim, Claim], PrecomputedLikelihoods],
            mock_solver_run,
        )
        result = solver(data, h_31, h_null)
        assert isinstance(result, PrecomputedLikelihoods)
        bayes.compare(
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
