"""Exact Jaynes-strict inference by 2^n enumeration.

Given an InformationSet over binary propositional variables, compute
the posterior marginal P(var = 1) for every variable and the log
partition function log Z. No approximation, no message passing.

Algorithm (PTLoS §4, §11):

    1. Enumerate all 2^n assignments.
    2. For each assignment x, accumulate log w(x):
         * class I (hard evidence)  : forbidden states -> -inf
         * class II (likelihoods)   : folded into class-IV effective priors
                                      (audit recorded)
         * class III (CPTs)         : log P(child | parents)
         * class IV (unary priors)  : log pi or log(1-pi)
         * class V (no information) : no factor (symmetric -> marginal 0.5)
         * logical constraints      : disallowed states -> -inf
    3. log Z = log sum_x exp(log w(x)).
    4. P(x_i=1) = sum_{x: x_i=1} exp(log w(x) - log Z).
    5. Z = 0 (log_max = -inf) -> raise: information set is inconsistent (D5).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence

import numpy as np

from jaynes_ref.information import InformationSet

_MAX_N = 20


@dataclass(frozen=True)
class InferenceResult:
    """Output of :func:."""

    beliefs: dict[str, float]
    log_Z: float
    likelihood_audit: list[dict] = field(default_factory=list)


def _enumerate_states(n: int) -> np.ndarray:
    N = 1 << n
    arange = np.arange(N, dtype=np.int64)
    states = np.empty((N, n), dtype=np.int8)
    for i in range(n):
        states[:, i] = (arange >> i) & 1
    return states


def _fold_likelihoods(
    info: InformationSet,
) -> tuple[dict[str, float], list[dict]]:
    """Class II -> class IV: apply each likelihood via Bayes odds update.

    For each Likelihood(var, lr):
        pi_before := effective_unary.get(var, 0.5)   # class V default
        odds := pi_before / (1 - pi_before) * lr
        pi_after := odds / (1 + odds)
    Audit trail records (var, pi_before, lr, pi_after) in order.
    """
    eff = dict(info.unary_priors)
    audit: list[dict] = []
    for lk in info.likelihoods:
        pi = eff.get(lk.variable, 0.5)
        odds = pi / (1.0 - pi) * lk.ratio
        pi_post = odds / (1.0 + odds)
        audit.append(
            {
                "variable": lk.variable,
                "pi_before": pi,
                "likelihood_ratio": lk.ratio,
                "pi_after": pi_post,
            }
        )
        eff[lk.variable] = pi_post
    return eff, audit


def _log_joint(
    info: InformationSet,
    var_idx: dict[str, int],
    states: np.ndarray,
    effective_unary: dict[str, float],
) -> np.ndarray:
    N = states.shape[0]
    log_w = np.zeros(N, dtype=np.float64)

    # Class I: hard evidence as δ mask
    for v, val in info.hard_evidence.items():
        i = var_idx[v]
        log_w = np.where(states[:, i] == val, log_w, -np.inf)

    # Class IV (incl. folded class II)
    for v, pi in effective_unary.items():
        i = var_idx[v]
        log_w = log_w + np.where(
            states[:, i] == 1, np.log(pi), np.log(1.0 - pi)
        )

    # Class III: P(child | parents)
    with np.errstate(divide="ignore"):
        for cpt in info.cpts:
            parent_idxs = [var_idx[p] for p in cpt.parents]
            child_idx = var_idx[cpt.child]
            bits = np.zeros(N, dtype=np.int64)
            for pos, pi in enumerate(parent_idxs):
                bits |= states[:, pi].astype(np.int64) << pos
            table = np.asarray(cpt.table, dtype=np.float64)
            p_child1 = table[bits]
            child_val = states[:, child_idx]
            prob = np.where(child_val == 1, p_child1, 1.0 - p_child1)
            log_w = log_w + np.log(prob)

    # Logical constraints: disallowed states -> -inf
    for c in info.constraints:
        c_idxs = [var_idx[v] for v in c.variables]
        c_states = states[:, c_idxs]
        allowed_mask = np.zeros(N, dtype=bool)
        for assign in c.allowed:
            match = np.ones(N, dtype=bool)
            for j, bit in enumerate(assign):
                match &= c_states[:, j] == bit
            allowed_mask |= match
        log_w = np.where(allowed_mask, log_w, -np.inf)

    # Weighted factors (PAIRWISE_POTENTIAL etc.): non-negative weights,
    # zero-weight assignments forbidden, positive entries contribute log w.
    for wf in info.weighted_factors:
        w_idxs = [var_idx[v] for v in wf.variables]
        bits = np.zeros(N, dtype=np.int64)
        for pos, vi in enumerate(w_idxs):
            bits |= states[:, vi].astype(np.int64) << pos
        weights = np.asarray(wf.weights, dtype=np.float64)
        w_sel = weights[bits]
        with np.errstate(divide="ignore"):
            log_w = log_w + np.where(w_sel > 0.0, np.log(w_sel), -np.inf)

    return log_w


def infer(info: InformationSet) -> InferenceResult:
    info.validate()
    var_ids = sorted(info.variables)
    n = len(var_ids)
    if n > _MAX_N:
        raise ValueError(
            f"Exact inference enumerates 2^n states. n={n} exceeds _MAX_N={_MAX_N}. "
            f"Use gaia.bp for larger graphs."
        )
    if n == 0:
        return InferenceResult(beliefs={}, log_Z=0.0, likelihood_audit=[])

    var_idx = {v: i for i, v in enumerate(var_ids)}
    states = _enumerate_states(n)
    eff_unary, audit = _fold_likelihoods(info)
    log_w = _log_joint(info, var_idx, states, eff_unary)

    log_max = log_w.max()
    if not np.isfinite(log_max):
        raise RuntimeError(
            "Z = 0: asserted information set is logically inconsistent. "
            "All 2^n states are forbidden by hard evidence and/or constraints (D5)."
        )
    w_shifted = np.exp(log_w - log_max)
    Z_shifted = float(w_shifted.sum())
    log_Z = float(log_max + np.log(Z_shifted))

    beliefs: dict[str, float] = {}
    for v in var_ids:
        i = var_idx[v]
        mask = states[:, i] == 1
        beliefs[v] = float(w_shifted[mask].sum() / Z_shifted)

    return InferenceResult(beliefs=beliefs, log_Z=log_Z, likelihood_audit=audit)


def joint_over(info: InformationSet, variables: Sequence[str]) -> np.ndarray:
    """Normalized joint over variables (bit-packed index, LSB-first)."""
    info.validate()
    if not variables:
        return np.array([1.0], dtype=np.float64)
    var_ids = sorted(info.variables)
    n = len(var_ids)
    if n > _MAX_N:
        raise ValueError(f"n={n} exceeds _MAX_N={_MAX_N}")
    var_idx = {v: i for i, v in enumerate(var_ids)}
    missing = [v for v in variables if v not in var_idx]
    if missing:
        raise KeyError(f"joint_over: unknown variables {missing!r}")

    states = _enumerate_states(n)
    eff_unary, _ = _fold_likelihoods(info)
    log_w = _log_joint(info, var_idx, states, eff_unary)
    log_max = log_w.max()
    if not np.isfinite(log_max):
        raise RuntimeError("Z = 0 in joint_over")
    w = np.exp(log_w - log_max)
    Zs = w.sum()

    bit = np.zeros(states.shape[0], dtype=np.int64)
    for pos, v in enumerate(variables):
        bit |= states[:, var_idx[v]].astype(np.int64) << pos
    out = np.bincount(bit, weights=w, minlength=1 << len(variables))
    return out / Zs
