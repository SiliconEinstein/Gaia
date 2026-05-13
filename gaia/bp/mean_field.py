"""Mean Field Variational Inference for binary factor graphs.

Coordinate Ascent Variational Inference (CAVI) for binary variables.

Theory
------
Approximate the true posterior p(x) with a fully factored distribution:
    q(x) = prod_i q_i(x_i),  q_i(x_i=1) = mu_i in [eps, 1-eps]

Minimise KL(q || p) equivalently maximise the ELBO:
    L(q) = E_q[log p(x)] - E_q[log q(x)]
         = E_q[log psi(x)] + H(q)

CAVI update for variable i (holding all others fixed):
    log q_i(x_i) ∝ E_{q_{-i}}[log p(x)]
                 = sum_f E_{q_{-i}}[log psi_f(x)]

For binary variables with {0,1} potentials (delta-like), the expectation
reduces to a sum over factor assignments weighted by the current q values.

Hard evidence (Class I) — Gaia adjusted Jaynes:
    Variables in graph.hard_evidence are clamped to {ε, 1-ε} (Cromwell)
    rather than strict {0, 1}. They are excluded from the CAVI update
    loop (treated as fixed strong prior).

Convergence:
    ELBO is non-decreasing under CAVI (guaranteed).
    We stop when max|delta_mu| < threshold.

Complexity: O(n * F * 2^k) per sweep, where k = max factor arity.
For Gaia's factors (k <= 6), this is O(n * F * 64) -- linear in n.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from numpy.typing import NDArray

from gaia.bp.factor_graph import CROMWELL_EPS, FactorGraph
from gaia.bp.potentials import evaluate_potential

__all__ = ["MeanFieldVI", "MFResult", "MFDiagnostics"]

from itertools import product as cartesian_product

# Cromwell clamp for mean-field parameters
_MF_EPS = 1e-6

# 软化零势能，避免 log(0) = -∞ 导致 CAVI 退化
# 对硬约束图（IMPLICATION 等）MF 仍是近似，但不会崩溃
_MF_POT_EPS = 1e-10


def _clamp(mu: float) -> float:
    return float(np.clip(mu, _MF_EPS, 1.0 - _MF_EPS))


# ---------------------------------------------------------------------------
# ELBO computation
# ---------------------------------------------------------------------------


def _compute_elbo(
    graph: FactorGraph,
    mu: dict[str, float],
    var_to_factors: dict[str, list[int]],
) -> float:
    """Compute the Evidence Lower BOund (ELBO).

    L = E_q[log psi(x)] + H(q)
      = sum_f E_q[log psi_f(x)] - sum_i [mu_i log mu_i + (1-mu_i) log(1-mu_i)]

    For binary {0,1} potentials, E_q[log psi_f] is computed by summing
    over all 2^k assignments weighted by q.
    """
    # Expected log-potential term
    elbo = 0.0
    for fi, factor in enumerate(graph.factors):
        all_vars = factor.all_vars
        for vals in cartesian_product((0, 1), repeat=len(all_vars)):
            assignment = {v: val for v, val in zip(all_vars, vals, strict=True)}
            pot = evaluate_potential(factor, assignment)
            if pot <= 0.0:
                continue
            log_pot = np.log(max(pot, _MF_POT_EPS))
            # q-weight for this assignment
            weight = 1.0
            for v, val in zip(all_vars, vals, strict=True):
                if v not in mu:
                    continue
                weight *= mu[v] if val == 1 else (1.0 - mu[v])
            elbo += weight * log_pot

    # Unary factor contribution: E_q[log psi_i(x_i)] = mu_i*log(p_i) + (1-mu_i)*log(1-p_i)
    for vid, p in graph.unary_factors.items():
        if vid not in mu:
            continue
        p_c = _clamp(float(p))
        m = mu[vid]
        elbo += m * np.log(p_c) + (1.0 - m) * np.log(1.0 - p_c)

    # Entropy term: H(q) = -sum_i [mu_i log mu_i + (1-mu_i) log(1-mu_i)]
    for vid, m in mu.items():
        m_c = _clamp(m)
        elbo -= m_c * np.log(m_c) + (1.0 - m_c) * np.log(1.0 - m_c)

    return float(elbo)


# ---------------------------------------------------------------------------
# CAVI update
# ---------------------------------------------------------------------------


def _cavi_update(
    var: str,
    graph: FactorGraph,
    mu: dict[str, float],
    var_to_factors: dict[str, list[int]],
) -> float:
    """Compute the CAVI update for variable var.

    log q(x_i=1) - log q(x_i=0) = sum_f [E_{q_{-i}}[log psi_f | x_i=1]
                                          - E_{q_{-i}}[log psi_f | x_i=0]]

    Returns the new mu_i = sigma(natural_param).
    """
    log_ratio = 0.0  # log q(x_i=1) / q(x_i=0)

    # Unary factor (prior): log psi_unary(x_i=1) - log psi_unary(x_i=0) = logit(p_i)
    if var in graph.unary_factors:
        p = _clamp(graph.unary_factors[var])
        log_ratio += np.log(p) - np.log(1.0 - p)

    for fi in var_to_factors.get(var, []):
        factor = graph.factors[fi]
        all_vars = factor.all_vars
        other_vars = [v for v in all_vars if v != var]

        # For each value of x_i, compute E_{q_{-i}}[log psi_f]
        for x_i, sign in ((1, +1.0), (0, -1.0)):
            for other_vals in cartesian_product((0, 1), repeat=len(other_vars)):
                assignment = {v: val for v, val in zip(other_vars, other_vals, strict=True)}
                assignment[var] = x_i

                pot = evaluate_potential(factor, assignment)
                # 软化零势能：log(0)=-∞ 会使 CAVI 退化到极端值
                log_pot = np.log(max(pot, _MF_POT_EPS))

                # q-weight for other variables
                weight = 1.0
                for v, val in zip(other_vars, other_vals, strict=True):
                    if v not in mu:
                        continue
                    weight *= mu[v] if val == 1 else (1.0 - mu[v])

                log_ratio += sign * weight * log_pot

    # sigmoid(log_ratio) = P(x_i=1) under q
    # Numerically stable sigmoid
    if log_ratio >= 0:
        new_mu = 1.0 / (1.0 + np.exp(-log_ratio))
    else:
        e = np.exp(log_ratio)
        new_mu = e / (1.0 + e)

    return _clamp(float(new_mu))


# ---------------------------------------------------------------------------
# Diagnostics
# ---------------------------------------------------------------------------


@dataclass
class MFDiagnostics:
    """Diagnostics from a Mean Field VI run."""

    converged: bool = False
    iterations_run: int = 0
    max_change_at_stop: float = 0.0
    elbo_history: list[float] = field(default_factory=list)
    belief_history: dict[str, list[float]] = field(default_factory=dict)


@dataclass
class MFResult:
    """Return value of MeanFieldVI.run()."""

    beliefs: dict[str, float]
    diagnostics: MFDiagnostics


# ---------------------------------------------------------------------------
# MeanFieldVI
# ---------------------------------------------------------------------------


class MeanFieldVI:
    """Coordinate Ascent Variational Inference (CAVI) for binary factor graphs.

    Scales to large graphs (n > 2000) where Junction Tree and TRW-BP are
    too expensive. Complexity O(n * F * 2^k) per sweep.

    Parameters
    ----------
    max_iterations:
        Maximum number of full CAVI sweeps.
    convergence_threshold:
        Stop when max|delta_mu| < threshold.
    track_elbo:
        If True, compute and record ELBO after each sweep (adds O(F*2^k) cost).
    """

    def __init__(
        self,
        max_iterations: int = 500,
        convergence_threshold: float = 1e-6,
        track_elbo: bool = False,
    ) -> None:
        self._max_iter = max_iterations
        self._threshold = convergence_threshold
        self._track_elbo = track_elbo

    def run(self, graph: FactorGraph) -> MFResult:
        """Run CAVI on graph and return beliefs + diagnostics."""
        diag = MFDiagnostics()

        if not graph.variables:
            return MFResult(beliefs={}, diagnostics=diag)

        var_to_factors = graph.get_var_to_factors()

        # Initialise mu: hard_evidence -> Cromwell-clamped {ε, 1-ε},
        # others -> prior or 0.5
        mu: dict[str, float] = {}
        for vid in graph.variables:
            if vid in graph.hard_evidence:
                mu[vid] = (1.0 - CROMWELL_EPS) if graph.hard_evidence[vid] == 1 else CROMWELL_EPS
            elif vid in graph.unary_factors:
                mu[vid] = _clamp(graph.unary_factors[vid])
            else:
                mu[vid] = 0.5

        # Soft variables (updated by CAVI)
        soft_vars = [v for v in graph.variables if v not in graph.hard_evidence]

        # Seed belief history
        for vid in graph.variables:
            diag.belief_history[vid] = [mu[vid]]

        if self._track_elbo:
            diag.elbo_history.append(_compute_elbo(graph, mu, var_to_factors))

        max_change = 0.0

        for iteration in range(self._max_iter):
            max_change = 0.0

            for vid in soft_vars:
                old_mu = mu[vid]
                mu[vid] = _cavi_update(vid, graph, mu, var_to_factors)
                max_change = max(max_change, abs(mu[vid] - old_mu))

            for vid in graph.variables:
                diag.belief_history[vid].append(mu[vid])

            if self._track_elbo:
                diag.elbo_history.append(_compute_elbo(graph, mu, var_to_factors))

            if max_change < self._threshold:
                diag.converged = True
                diag.iterations_run = iteration + 1
                diag.max_change_at_stop = max_change
                return MFResult(beliefs=dict(mu), diagnostics=diag)

        diag.converged = False
        diag.iterations_run = self._max_iter
        diag.max_change_at_stop = max_change
        return MFResult(beliefs=dict(mu), diagnostics=diag)
