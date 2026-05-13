"""Layer-0 information-theoretic queries on top of exact inference.

Every function shares the same enumeration backend as exact.infer, so
Z and log w(x) are computed once and reused. All quantities are
in **nats** (natural log) to stay consistent with PTLoS.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np

from jaynes_ref.exact import _MAX_N, _enumerate_states, _fold_likelihoods, _log_joint
from jaynes_ref.information import InformationSet


def _log_w_and_idx(info: InformationSet) -> tuple[np.ndarray, list[str], dict[str, int]]:
    info.validate()
    var_ids = sorted(info.variables)
    n = len(var_ids)
    if n > _MAX_N:
        raise ValueError(f"n={n} exceeds _MAX_N={_MAX_N}")
    if n == 0:
        return np.zeros(1), [], {}
    var_idx = {v: i for i, v in enumerate(var_ids)}
    states = _enumerate_states(n)
    eff, _ = _fold_likelihoods(info)
    log_w = _log_joint(info, var_idx, states, eff)
    return log_w, var_ids, var_idx


def _normalize_log_w(log_w: np.ndarray) -> np.ndarray:
    log_max = log_w.max()
    if not np.isfinite(log_max):
        raise RuntimeError("Z = 0: information set is inconsistent (D5).")
    w = np.exp(log_w - log_max)
    return w / w.sum()


def map_assignment(info: InformationSet) -> tuple[dict[str, int], float]:
    """Return the MAP (mode) assignment and its log-probability."""
    log_w, var_ids, _ = _log_w_and_idx(info)
    if not var_ids:
        return {}, 0.0
    p = _normalize_log_w(log_w)
    j = int(np.argmax(p))
    assignment = {v: int((j >> i) & 1) for i, v in enumerate(var_ids)}
    log_p = float(np.log(p[j]))
    return assignment, log_p


def entropy(info: InformationSet) -> float:
    """Shannon entropy H[p] = -Sum p log p of the full joint, in nats."""
    log_w, var_ids, _ = _log_w_and_idx(info)
    if not var_ids:
        return 0.0
    p = _normalize_log_w(log_w)
    nonzero = p > 0.0
    return float(-(p[nonzero] * np.log(p[nonzero])).sum())


def marginal_entropy(info: InformationSet, variables: Sequence[str]) -> float:
    """Entropy H[p_S] where S = variables (nuisance variables marginalized)."""
    p_s = marginal(info, variables)
    nonzero = p_s > 0.0
    return float(-(p_s[nonzero] * np.log(p_s[nonzero])).sum())


def marginal(info: InformationSet, variables: Sequence[str]) -> np.ndarray:
    """Normalized marginal over variables with nuisance variables.

    summed out. Index: bit_i = variables[i] (LSB first).
    """
    log_w, var_ids, var_idx = _log_w_and_idx(info)
    if not variables:
        return np.array([1.0], dtype=np.float64)
    missing = [v for v in variables if v not in var_idx]
    if missing:
        raise KeyError(f"marginal: unknown variables {missing!r}")
    p = _normalize_log_w(log_w)
    states = _enumerate_states(len(var_ids))
    bit = np.zeros(states.shape[0], dtype=np.int64)
    for pos, v in enumerate(variables):
        bit |= states[:, var_idx[v]].astype(np.int64) << pos
    return np.bincount(bit, weights=p, minlength=1 << len(variables))


def mutual_information(
    info: InformationSet,
    A: Sequence[str],
    B: Sequence[str],
) -> float:
    """I(A;B) = H(A) + H(B) - H(A,B), nats. Requires A and B disjoint."""
    a, b = set(A), set(B)
    if a & b:
        raise ValueError(f"A and B must be disjoint; overlap = {a & b}")
    HA = marginal_entropy(info, list(A))
    HB = marginal_entropy(info, list(B))
    HAB = marginal_entropy(info, list(A) + list(B))
    return HA + HB - HAB


def kl_divergence(p: np.ndarray, q: np.ndarray) -> float:
    """KL(p || q) in nats. p and q must have the same length and.

    sum to 1. q=0 where p>0 returns +inf.
    """
    if p.shape != q.shape:
        raise ValueError(f"shape mismatch: {p.shape} vs {q.shape}")
    out = 0.0
    for pi, qi in zip(p, q, strict=False):
        if pi <= 0:
            continue
        if qi <= 0:
            return float("inf")
        out += pi * (float(np.log(pi)) - float(np.log(qi)))
    return out
