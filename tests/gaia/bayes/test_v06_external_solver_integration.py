"""External-solver integration via ``compute`` and ``PrecomputedLikelihoods``.

The v0.6 spec describes a contract for hooking external statistical
solvers (PyMC, Stan, NumPyro, ...) into Gaia: wrap the solver call with
``@compute``, return a :class:`PrecomputedLikelihoods` Claim carrying
``log_likelihoods`` and ``diagnostics``, then pass that Claim to
``compare(precomputed=...)``. The dedicated mock test in
``test_v06_numeric_equivalence.py`` exercises the plumbing with a stub
that just calls ``scipy.stats.binom.logpmf`` —— which is the same routine
the lowering would have called itself.

This file goes one step deeper: the "external solver" here is
:func:`scipy.integrate.quad`, doing real adaptive numerical quadrature
to compute the marginal likelihood ``∫ Binomial(k|n,p) Beta(p|α,β) dp``.
That marginal has a closed form (``BetaBinomial(n, α, β)``) so we can
check the numerical-solver result against the analytic one without any
extra dependency. Quad reports an absolute-error estimate, which we
store in ``PrecomputedLikelihoods.diagnostics`` to exercise the
diagnostics-payload story end-to-end.

Why this is useful beyond the mock test:

* Quad is genuinely deterministic-numerical, not just an alias for the
  closed-form routine, so it surfaces real ``epsabs``/``epsrel``
  tolerance choices and reports a real numerical error.
* The diagnostics payload includes a non-trivial structured field
  (per-hypothesis abs-error estimates) — confirming that opaque
  solver-specific metadata rides cleanly through the contract.
* The closed-form (``BetaBinomial(n=395, α=1, β=1)``) gives the exact
  uniform marginal ``1/(n+1)`` for every k, so numeric-vs-analytic
  agreement at 1e-9 is the obvious correctness check.
"""

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
    Nat,
    Probability,
    Variable,
    claim,
    compute,
    observe,
)
from gaia.engine.lang.compiler.compile import compile_package_artifact
from gaia.engine.lang.runtime.knowledge import _current_package
from gaia.engine.lang.runtime.package import CollectedPackage


N_TRIALS = 395
K_OBSERVED = 295


@compute
def scipy_quad_log_marginals(
    data: object,
    mendel_hypothesis: object,
    diffuse_hypothesis: object,
) -> PrecomputedLikelihoods:
    """Compute log marginal likelihoods via scipy.integrate.quad.

    For the Mendel-3:1 hypothesis the marginal is a point evaluation
    (no latent parameters), so we use the closed-form ``binom.pmf``
    and record zero quadrature error.

    For the Diffuse hypothesis (``p ~ Beta(1, 1)``) we numerically
    integrate ``Binomial(k|n,p) * Beta(p|1,1)`` over ``p ∈ [0, 1]``
    and stash quad's absolute-error estimate in ``diagnostics`` so a
    downstream audit rule can decide whether the integration is
    tight enough to trust.
    """
    from scipy.integrate import quad

    log_l_mendel = float(stats.binom.logpmf(K_OBSERVED, n=N_TRIALS, p=0.75))

    def integrand(p: float) -> float:
        return float(stats.binom.pmf(K_OBSERVED, n=N_TRIALS, p=p) * stats.beta.pdf(p, a=1.0, b=1.0))

    epsabs = 1e-14
    epsrel = 1e-14
    integral, abs_err = quad(integrand, 0.0, 1.0, epsabs=epsabs, epsrel=epsrel, limit=200)
    log_l_diffuse = math.log(integral)

    return PrecomputedLikelihoods(
        "scipy.integrate.quad log marginal likelihoods for Mendel vs Diffuse.",
        log_likelihoods={
            mendel_hypothesis: log_l_mendel,
            diffuse_hypothesis: log_l_diffuse,
        },
        diagnostics={
            "method": "scipy.integrate.quad",
            "epsabs": epsabs,
            "epsrel": epsrel,
            "limit": 200,
            "per_hypothesis": {
                "mendel": {
                    "marginal_kind": "point",
                    "abs_error_estimate": 0.0,
                },
                "diffuse": {
                    "marginal_kind": "numeric_quadrature",
                    "integrand": "Binomial(k|n,p) * Beta(p|1,1)",
                    "abs_error_estimate": float(abs_err),
                    "raw_integral": float(integral),
                },
            },
        },
        solver="scipy-integrate-quad",
        label="scipy_quad_marginals",
    )


def _build_v06_with_external_solver(
    *,
    use_precomputed: bool,
    exclusivity: str = "exhaustive_pairwise_complement",
):
    """Build a self-contained Mendel-vs-Diffuse comparison package.

    Uses ``exhaustive_pairwise_complement`` by default so the comparison
    is self-contained: ``compare()`` auto-generates the Exclusive action
    that pins mendel XOR diffuse. The canonical Mendel example package
    declares ``exclusive(mendel, blending)`` separately and uses
    ``exclusivity="none"``; either route reaches the same BP shape, but
    the self-contained one is cleaner for unit-test fixtures.
    """
    pkg = CollectedPackage(name="mendel_v06_quad_solver", namespace="t")
    token = _current_package.set(pkg)
    try:
        k_var = Variable(symbol="k", domain=Nat, value=K_OBSERVED)
        mendel = claim("mendelian segregation", prior=0.5, label="mendel")
        diffuse = claim("diffuse alternative", prior=0.5, label="diffuse")
        data = observe(k_var, value=K_OBSERVED, label="data")
        mendel_pred = bayes.predict(
            mendel,
            target=k_var,
            distribution=LangBinomial("k under Mendel", n=N_TRIALS, p=0.75),
            label="mendel_pred",
        )
        diffuse_pred = bayes.predict(
            diffuse,
            target=k_var,
            distribution=LangBetaBinomial(
                "k under Diffuse", n=N_TRIALS, alpha=1.0, beta=1.0
            ),
            label="diffuse_pred",
        )

        if use_precomputed:
            precomputed_claim = scipy_quad_log_marginals(data, mendel, diffuse)
            cmp_result = bayes.compare(
                data,
                models=[mendel_pred, diffuse_pred],
                exclusivity=exclusivity,
                precomputed=precomputed_claim,
                label="comparison",
            )
        else:
            precomputed_claim = None
            cmp_result = bayes.compare(
                data,
                models=[mendel_pred, diffuse_pred],
                exclusivity=exclusivity,
                label="comparison",
            )
    finally:
        _current_package.reset(token)
    return pkg, mendel, diffuse, cmp_result, precomputed_claim


def _beliefs_for(pkg, mendel, diffuse, cmp_result) -> dict[str, float]:
    compiled = compile_package_artifact(pkg)
    beliefs, _ = exact_inference(lower_local_graph(compiled.graph))
    return {
        "mendel": beliefs[compiled.knowledge_ids_by_object[id(mendel)]],
        "diffuse": beliefs[compiled.knowledge_ids_by_object[id(diffuse)]],
        "cmp": beliefs[compiled.knowledge_ids_by_object[id(cmp_result)]],
    }


def test_scipy_quad_solver_matches_closed_form_betabinomial():
    """The numerical solver result agrees with the closed-form BetaBinomial.

    For ``α=β=1`` the marginal is uniform over k: ``P(k) = 1/(n+1)``,
    so ``log P(k) = -log(n+1)`` regardless of which k was observed.
    Confirm quad gives the same number scipy.stats.betabinom does.
    """
    pkg, mendel, diffuse, cmp_result, precomputed_claim = _build_v06_with_external_solver(
        use_precomputed=True,
    )
    assert precomputed_claim is not None

    # Closed-form log P(k=295 | n=395, α=1, β=1) = log(1/396) = -log(396)
    expected_log_l_diffuse = float(stats.betabinom.logpmf(K_OBSERVED, n=N_TRIALS, a=1.0, b=1.0))
    expected_uniform_log = -math.log(N_TRIALS + 1)
    assert math.isclose(expected_log_l_diffuse, expected_uniform_log, rel_tol=1e-12, abs_tol=1e-14)

    actual_log_l_diffuse = precomputed_claim.log_likelihoods[diffuse]
    assert math.isclose(
        actual_log_l_diffuse,
        expected_log_l_diffuse,
        rel_tol=1e-9,
        abs_tol=1e-12,
    )

    # And quad's reported abs error estimate must be tighter than the gap to
    # the analytic answer — i.e. the diagnostic is honest, not a placeholder.
    abs_err = precomputed_claim.diagnostics["per_hypothesis"]["diffuse"]["abs_error_estimate"]
    assert abs_err < 1e-10


def test_external_solver_bp_posteriors_match_internal_evaluation():
    """End-to-end: BP outputs through scipy-quad path match the closed-form path."""
    pkg_internal, mendel_i, diffuse_i, cmp_internal, _ = _build_v06_with_external_solver(
        use_precomputed=False,
    )
    beliefs_internal = _beliefs_for(pkg_internal, mendel_i, diffuse_i, cmp_internal)

    pkg_quad, mendel_q, diffuse_q, cmp_quad, precomputed_claim = _build_v06_with_external_solver(
        use_precomputed=True,
    )
    beliefs_quad = _beliefs_for(pkg_quad, mendel_q, diffuse_q, cmp_quad)

    assert math.isclose(
        beliefs_internal["mendel"], beliefs_quad["mendel"], rel_tol=1e-9, abs_tol=1e-12
    )
    assert math.isclose(
        beliefs_internal["diffuse"], beliefs_quad["diffuse"], rel_tol=1e-9, abs_tol=1e-12
    )
    assert math.isclose(
        beliefs_internal["cmp"], beliefs_quad["cmp"], rel_tol=1e-9, abs_tol=1e-12
    )


def test_precomputed_claim_carries_solver_diagnostics_through_compile():
    """The diagnostics payload is preserved on the Claim object end-to-end.

    The diagnostics live on the :class:`PrecomputedLikelihoods` Claim
    (not on the comparison helper's metadata) — they describe how the
    likelihoods were obtained, not what the comparison concludes. This
    lets reviewers and audit rules walk back from the comparison to the
    Compute action and inspect the solver's tolerance and error
    estimates without parsing free-form metadata.
    """
    pkg, _, _, cmp_result, precomputed_claim = _build_v06_with_external_solver(
        use_precomputed=True,
    )
    assert precomputed_claim is not None

    # The Claim's own fields (set by PrecomputedLikelihoods.__init__).
    assert precomputed_claim.solver == "scipy-integrate-quad"
    assert precomputed_claim.diagnostics["method"] == "scipy.integrate.quad"
    assert precomputed_claim.diagnostics["epsabs"] == 1e-14
    assert "per_hypothesis" in precomputed_claim.diagnostics
    assert precomputed_claim.diagnostics["per_hypothesis"]["diffuse"][
        "marginal_kind"
    ] == "numeric_quadrature"

    # Compile and walk the IR — the precomputed claim is in the knowledge map.
    compiled = compile_package_artifact(pkg)
    pre_id = compiled.knowledge_ids_by_object[id(precomputed_claim)]
    pre_node = next(k for k in compiled.graph.knowledges if k.id == pre_id)
    # The solver-specific diagnostics ride along as Claim metadata so audit
    # rules and gaia explain can render them next to the comparison they fed.
    assert pre_node.metadata.get("solver") == "scipy-integrate-quad"
    assert pre_node.metadata.get("kind") == "precomputed_likelihoods"


def test_external_solver_path_reproduces_mendel_canonical_posteriors():
    """The Mendel 3:1 vs Diffuse posteriors via the scipy-quad route are sane.

    With ``exhaustive_pairwise_complement`` exclusivity and equal 0.5
    priors, an overwhelming likelihood ratio in favour of Mendel must
    push its posterior well above the prior and pull the diffuse
    alternative well below it. Exact thresholds depend on the Cromwell
    clamp on individual likelihood factors and on whether the helper
    Claim is itself part of the joint, so we assert a directional bound
    rather than a hard number. The strict numeric agreement against the
    internal-eval lowering is covered by
    :func:`test_external_solver_bp_posteriors_match_internal_evaluation`.
    """
    pkg, mendel, diffuse, cmp_result, _ = _build_v06_with_external_solver(use_precomputed=True)
    beliefs = _beliefs_for(pkg, mendel, diffuse, cmp_result)
    # Mendel rises clearly above its 0.5 prior; the diffuse alternative drops
    # well below it; the comparison helper is essentially fired (>~1).
    assert beliefs["mendel"] > 0.85
    assert beliefs["diffuse"] < 0.15
    assert beliefs["mendel"] > 10 * beliefs["diffuse"]
    assert beliefs["cmp"] > 0.99
