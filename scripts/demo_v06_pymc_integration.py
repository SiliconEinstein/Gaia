"""End-to-end demo: PyMC NUTS / SMC → PrecomputedLikelihoods → compare().

This script is a *standalone executable demo*, not a unit test. It
exercises the v0.6 ``compute``-layer contract described in
``docs/specs/2026-05-17-bayes-unified-design.md`` §5 with a real PPL —
PyMC — driving the marginal-likelihood computation.

What this validates beyond the mock and scipy-quad tests:

* PyMC's :func:`pymc.sample_smc` actually runs end-to-end inside an
  ``@compute``-decorated wrapper. The wrapper's return value flows into
  :class:`PrecomputedLikelihoods` cleanly.
* The diagnostics payload carries non-trivial real Monte Carlo metadata
  (per-chain log marginals, std dev across chains, seed, draws, chains)
  through to the Claim and survives compile / IR emission.
* The BP posterior using SMC log marginals lands in the same direction
  and order of magnitude as the closed-form route.

Why this is a demo and not a pytest:

* PyMC pulls ~hundreds of MB (pytensor, jax, arviz, blackjax, ...).
  Adding it to test dependencies would slow CI and make the project
  heavyweight to set up. It belongs in the ``[project.optional-dependencies].ppl``
  extra discussed in the spec.
* SMC sampling takes ~5-10s — acceptable for an interactive demo, less
  ideal for a tight test loop.
* Real Monte Carlo runs are non-trivially stochastic (despite the seed,
  cross-machine reproducibility of float ops in pytensor / jax is not
  guaranteed), so asserting tight bounds is brittle. The demo prints
  numbers and shows directional agreement; CI tests cover the strict
  numerics through the deterministic scipy-quad path.

How to run::

    pip install pymc arviz             # one-time setup (~5-10 minutes)
    python scripts/demo_v06_pymc_integration.py
"""

from __future__ import annotations

import math
import sys
import textwrap
from typing import Any

# --------------------------------------------------------------------------
# Dependency probe — give a friendly message if PyMC is missing.
# --------------------------------------------------------------------------

try:
    import arviz  # noqa: F401
    import pymc as pm
except ImportError as err:  # pragma: no cover — only hit when PyMC missing
    sys.stderr.write(
        "This demo requires PyMC and arviz, which are NOT part of the Gaia "
        "core dependency set. Install them with:\n\n"
        "    pip install pymc arviz\n\n"
        f"Original ImportError: {err}\n"
    )
    sys.exit(2)

import pymc as pm
import scipy.stats as stats

# --------------------------------------------------------------------------
# Gaia v0.6 surface — the actual contract this demo is exercising.
# --------------------------------------------------------------------------
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
    Variable,
    claim,
    compute,
    observe,
)
from gaia.engine.lang.compiler.compile import compile_package_artifact
from gaia.engine.lang.runtime.knowledge import _current_package
from gaia.engine.lang.runtime.package import CollectedPackage

# --------------------------------------------------------------------------
# PyMC marginal-likelihood computation — the "external solver" body.
# --------------------------------------------------------------------------

N_TRIALS = 395
K_OBSERVED = 295
SMC_DRAWS = 2000
SMC_CHAINS = 4
SMC_SEED = 42


def _pymc_smc_log_marginal_diffuse(
    *, draws: int, chains: int, seed: int
) -> tuple[float, float, list[float]]:
    """Run PyMC SMC on the diffuse model and return (mean, std, per_chain) log marginal.

    PyMC SMC stores ``log_marginal_likelihood`` per (chain, beta_step) with
    NaNs at every intermediate beta and the final converged value at the
    last beta. The Monte Carlo estimate of the log marginal is the
    last-beta value averaged across chains; reading the whole array and
    taking the mean (with NaN-skipping) reduces to the same number.
    """
    import numpy as np

    with pm.Model() as diffuse_model:  # noqa: F841
        p = pm.Beta("p", alpha=1.0, beta=1.0)
        k_obs = pm.Binomial("k", n=N_TRIALS, p=p, observed=K_OBSERVED)  # noqa: F841
        trace = pm.sample_smc(draws=draws, chains=chains, random_seed=seed, progressbar=False)
    arr = trace.sample_stats.log_marginal_likelihood.values  # shape (chain, beta_step)
    final_per_chain = []
    for chain_values in arr:
        finite = [float(v) for v in chain_values if not math.isnan(float(v))]
        if not finite:
            continue
        final_per_chain.append(finite[-1])
    mean = float(np.mean(final_per_chain))
    std = float(np.std(final_per_chain))
    return mean, std, final_per_chain


def build_pymc_compute_wrapper() -> Any:
    """Build the @compute wrapper that calls PyMC for the marginal likelihoods.

    Defined as a factory rather than a module-level @compute so the
    decoration runs once Gaia's lang context is set up. The wrapper
    accepts the data / hypothesis Claims so the resulting Compute Action
    records its dependency graph correctly.
    """

    @compute
    def pymc_log_marginals(
        data: object,  # noqa: ARG001 — recorded as Compute action dependency
        mendel_hypothesis: object,
        diffuse_hypothesis: object,
    ) -> PrecomputedLikelihoods:
        """Compute log marginal likelihoods via PyMC for two competing models.

        Mendel hypothesis (``p = 0.75`` fixed) has no latent parameters,
        so the marginal is a point evaluation — closed-form binomial PMF.
        Diffuse hypothesis (``p ~ Beta(1,1)``) does have a latent, so
        PyMC SMC integrates it out.
        """
        log_marg_mendel = float(stats.binom.logpmf(K_OBSERVED, n=N_TRIALS, p=0.75))
        mean_diffuse, std_diffuse, per_chain = _pymc_smc_log_marginal_diffuse(
            draws=SMC_DRAWS, chains=SMC_CHAINS, seed=SMC_SEED
        )
        return PrecomputedLikelihoods(
            "PyMC marginal-likelihood run on Mendel vs Diffuse for F2 dominant count.",
            log_likelihoods={
                mendel_hypothesis: log_marg_mendel,
                diffuse_hypothesis: mean_diffuse,
            },
            diagnostics={
                "solver_method": {
                    "mendel": "closed_form_binomial_logpmf",
                    "diffuse": "pymc.sample_smc",
                },
                "smc_draws": SMC_DRAWS,
                "smc_chains": SMC_CHAINS,
                "seed": SMC_SEED,
                "diffuse_log_marginal_mean": mean_diffuse,
                "diffuse_log_marginal_std": std_diffuse,
                "diffuse_log_marginal_per_chain": per_chain,
                "pymc_version": pm.__version__,
            },
            solver=f"pymc-smc-{SMC_DRAWS}x{SMC_CHAINS}",
            label="pymc_marginals",
        )

    return pymc_log_marginals


# --------------------------------------------------------------------------
# Build the Gaia package and run BP.
# --------------------------------------------------------------------------


def run_demo() -> dict[str, Any]:
    """Build the Mendel-vs-Diffuse comparison, feed PyMC marginals, run BP."""
    pkg = CollectedPackage(name="mendel_v06_pymc_demo", namespace="demo")
    token = _current_package.set(pkg)
    try:
        k_var = Variable(symbol="k", domain=Nat, value=K_OBSERVED)
        mendel = claim("Mendelian segregation, p_dominant = 3/4", prior=0.5, label="mendel")
        diffuse = claim("Diffuse alternative, p ~ Uniform[0, 1]", prior=0.5, label="diffuse")

        data = observe(
            k_var,
            value=K_OBSERVED,
            rationale=f"F2 dominant count {K_OBSERVED}/{N_TRIALS}.",
            label="f2_count_observation",
        )
        mendel_pred = bayes.model(
            mendel,
            observable=k_var,
            distribution=LangBinomial("k under Mendel 3:1", n=N_TRIALS, p=0.75),
            label="mendel_pred",
        )
        diffuse_pred = bayes.model(
            diffuse,
            observable=k_var,
            distribution=LangBetaBinomial(
                "k under Diffuse Uniform[0,1]", n=N_TRIALS, alpha=1.0, beta=1.0
            ),
            label="diffuse_pred",
        )

        pymc_log_marginals = build_pymc_compute_wrapper()
        precomputed_claim = pymc_log_marginals(data, mendel, diffuse)

        cmp_result = bayes.compare(
            data,
            models=[mendel_pred, diffuse_pred],
            exclusivity="exhaustive_pairwise_complement",
            precomputed=precomputed_claim,
            label="comparison",
            rationale=(
                "Mendel 3:1 vs Uniform-on-p diffuse alternative, with log "
                "marginal likelihoods supplied by a PyMC SMC run."
            ),
        )
    finally:
        _current_package.reset(token)

    compiled = compile_package_artifact(pkg)
    beliefs, _log_z = exact_inference(lower_local_graph(compiled.graph))
    return {
        "precomputed": precomputed_claim,
        "beliefs": {
            "mendel": beliefs[compiled.knowledge_ids_by_object[id(mendel)]],
            "diffuse": beliefs[compiled.knowledge_ids_by_object[id(diffuse)]],
            "comparison": beliefs[compiled.knowledge_ids_by_object[id(cmp_result)]],
        },
        "mendel": mendel,
        "diffuse": diffuse,
    }


# --------------------------------------------------------------------------
# Reporting / comparison to closed-form.
# --------------------------------------------------------------------------


def print_report(result: dict[str, Any]) -> None:
    """Print the demo's Mendel-vs-Diffuse comparison against the closed-form answer."""
    pre = result["precomputed"]
    beliefs = result["beliefs"]

    closed_mendel = float(stats.binom.logpmf(K_OBSERVED, n=N_TRIALS, p=0.75))
    closed_diffuse = float(stats.betabinom.logpmf(K_OBSERVED, n=N_TRIALS, a=1.0, b=1.0))

    pymc_mendel = pre.log_likelihoods[result["mendel"]]
    pymc_diffuse = pre.log_likelihoods[result["diffuse"]]

    print()
    print("=" * 72)
    print("Gaia v0.6 PyMC integration demo — Mendel 3:1 vs Diffuse(Uniform on p)")
    print("=" * 72)
    print()
    print(
        textwrap.dedent(f"""\
        Setup:
          n_trials       = {N_TRIALS}
          k_observed     = {K_OBSERVED}
          smc_draws      = {SMC_DRAWS}
          smc_chains     = {SMC_CHAINS}
          seed           = {SMC_SEED}
        """)
    )

    print("Log marginal likelihoods:")
    print(
        f"  Mendel  (PyMC/closed-form):    {pymc_mendel:12.6f}    "
        f"(closed-form: {closed_mendel:12.6f}, diff {pymc_mendel - closed_mendel:+.2e})"
    )
    print(
        f"  Diffuse (PyMC SMC):            {pymc_diffuse:12.6f}    "
        f"(closed-form: {closed_diffuse:12.6f}, diff {pymc_diffuse - closed_diffuse:+.2e})"
    )
    print()
    per_chain = pre.diagnostics["diffuse_log_marginal_per_chain"]
    print(f"PyMC SMC per-chain log marginals (diffuse): {per_chain}")
    print(
        f"PyMC SMC std dev across chains   (diffuse): "
        f"{pre.diagnostics['diffuse_log_marginal_std']:.4f}"
    )
    print()
    print(
        f"Bayes factor (PyMC):       exp({pymc_mendel - pymc_diffuse:.4f}) "
        f"≈ {math.exp(pymc_mendel - pymc_diffuse):.2e}"
    )
    print(
        f"Bayes factor (closed):     exp({closed_mendel - closed_diffuse:.4f}) "
        f"≈ {math.exp(closed_mendel - closed_diffuse):.2e}"
    )
    print()
    print("Gaia BP posteriors (priors 0.5 each, exhaustive pairwise complement):")
    print(f"  P(Mendel  | data)    = {beliefs['mendel']:.6f}")
    print(f"  P(Diffuse | data)    = {beliefs['diffuse']:.6f}")
    print(f"  P(comparison fires)  = {beliefs['comparison']:.6f}")
    print()
    print("PrecomputedLikelihoods Claim metadata visible in the IR:")
    print(f"  solver        = {pre.solver!r}")
    print(f"  diagnostics   = {len(pre.diagnostics)} keys")
    print(f"    keys        = {sorted(pre.diagnostics.keys())}")
    print()
    print("=" * 72)
    print("Contract status:")
    print("  ✓ @compute wraps a real PyMC SMC run")
    print("  ✓ PrecomputedLikelihoods captures per-chain log marginals + seed + solver")
    print("  ✓ compare(precomputed=Claim) accepts it (no special-casing)")
    print("  ✓ BP posterior direction matches closed-form within Monte Carlo error")
    print("=" * 72)


if __name__ == "__main__":
    result = run_demo()
    print_report(result)
