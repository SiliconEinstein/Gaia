"""Treewidth-bounded exact inference via log-space Variable Elimination.

Ground-truth peer to ``jaynes_ref.exact.infer``. Identical semantics but
scales beyond the n<=20 brute-force cap to graphs with treewidth ~20.

Approach: build one ``(scope, log_tensor)`` factor per item in the
InformationSet, then eliminate variables one at a time. For per-target
marginals we re-run VE once per target (simple and trivially correct;
speed is not the priority at the ground-truth layer).

Elimination order uses a min-neighbors (min-degree) heuristic, which is
good enough for the sparse chains and trees produced by Gaia lowering.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

import numpy as np

from gaia.jaynes_ref.exact import InferenceResult, _fold_likelihoods
from gaia.jaynes_ref.information import InformationSet

__all__ = ["jt_infer"]


Scope = tuple[str, ...]


@dataclass
class _Factor:
    scope: Scope
    log_tensor: np.ndarray

    def __post_init__(self) -> None:
        expected = (2,) * len(self.scope)
        if self.log_tensor.shape != expected:
            raise ValueError(
                f"_Factor shape mismatch: scope={self.scope} expects {expected}, "
                f"got {self.log_tensor.shape}"
            )


# ---------------------------------------------------------------------------
# Factor construction
# ---------------------------------------------------------------------------


def _build_factors(
    info: InformationSet,
    effective_unary: dict[str, float],
) -> list[_Factor]:
    factors: list[_Factor] = []

    for v, val in info.hard_evidence.items():
        arr = np.array([-np.inf, -np.inf], dtype=np.float64)
        arr[val] = 0.0
        factors.append(_Factor((v,), arr))

    for v, pi in effective_unary.items():
        arr = np.array(
            [np.log(1.0 - pi) if (1.0 - pi) > 0 else -np.inf, np.log(pi) if pi > 0 else -np.inf],
            dtype=np.float64,
        )
        factors.append(_Factor((v,), arr))

    for cpt in info.cpts:
        scope = (*tuple(cpt.parents), cpt.child)
        k = len(cpt.parents)
        table = np.asarray(cpt.table, dtype=np.float64)
        tensor = np.empty((2,) * len(scope), dtype=np.float64)
        for pa_idx in range(1 << k):
            pa_bits = tuple(((pa_idx >> b) & 1) for b in range(k))
            p1 = float(table[pa_idx])
            tensor[(*pa_bits, 0)] = np.log(1.0 - p1) if (1.0 - p1) > 0 else -np.inf
            tensor[(*pa_bits, 1)] = np.log(p1) if p1 > 0 else -np.inf
        factors.append(_Factor(scope, tensor))

    for c in info.constraints:
        scope = tuple(c.variables)
        tensor = np.full((2,) * len(scope), -np.inf, dtype=np.float64)
        for assign in c.allowed:
            tensor[tuple(assign)] = 0.0
        factors.append(_Factor(scope, tensor))

    for wf in info.weighted_factors:
        scope = tuple(wf.variables)
        k = len(scope)
        weights = np.asarray(wf.weights, dtype=np.float64)
        tensor = np.empty((2,) * k, dtype=np.float64)
        for idx in range(1 << k):
            bits = tuple(((idx >> b) & 1) for b in range(k))
            w = float(weights[idx])
            tensor[bits] = np.log(w) if w > 0.0 else -np.inf
        factors.append(_Factor(scope, tensor))

    return factors


# ---------------------------------------------------------------------------
# Core VE operations
# ---------------------------------------------------------------------------


def _broadcast_to_union(factor: _Factor, union_scope: Scope) -> np.ndarray:
    """Reshape ``factor.log_tensor`` so it broadcasts cleanly against any.

    other factor over a superset of its scope.
    """
    positions = [union_scope.index(v) for v in factor.scope]
    rank = len(union_scope)
    if positions != sorted(positions):
        order = sorted(range(len(positions)), key=lambda i: positions[i])
        t = np.transpose(factor.log_tensor, order)
        sorted_positions = sorted(positions)
    else:
        t = factor.log_tensor
        sorted_positions = positions
    shape = [1] * rank
    for pos in sorted_positions:
        shape[pos] = 2
    return t.reshape(shape)


def _product(factors: list[_Factor]) -> _Factor:
    if not factors:
        raise ValueError("_product requires at least one factor")
    union: list[str] = []
    seen: set[str] = set()
    for f in factors:
        for v in f.scope:
            if v not in seen:
                union.append(v)
                seen.add(v)
    union_scope = tuple(union)
    rank = len(union_scope)
    acc = np.zeros((2,) * rank, dtype=np.float64)
    for f in factors:
        acc = acc + _broadcast_to_union(f, union_scope)
    return _Factor(union_scope, acc)


def _sum_out(factor: _Factor, var: str) -> _Factor:
    axis = factor.scope.index(var)
    new_scope = factor.scope[:axis] + factor.scope[axis + 1 :]
    t = factor.log_tensor
    m = np.max(t, axis=axis)
    m_finite = np.isfinite(m)
    m_safe = np.where(m_finite, m, 0.0)
    m_safe_b = np.expand_dims(m_safe, axis=axis)
    shifted = np.exp(t - m_safe_b)
    summed = np.sum(shifted, axis=axis)
    with np.errstate(divide="ignore"):
        log_sum = np.log(summed)
    out = np.where(m_finite, m_safe + log_sum, -np.inf)
    return _Factor(new_scope, out)


# ---------------------------------------------------------------------------
# Min-neighbors elimination order
# ---------------------------------------------------------------------------


def _min_neighbors_order(variables: Iterable[str], factors: list[_Factor]) -> list[str]:
    var_set = set(variables)
    neighbors: dict[str, set[str]] = {v: set() for v in var_set}
    for f in factors:
        s = set(f.scope) & var_set
        for v in s:
            neighbors[v].update(u for u in s if u != v)
    remaining = set(var_set)
    order: list[str] = []
    while remaining:
        v = min(remaining, key=lambda x: (len(neighbors[x] & remaining), x))
        order.append(v)
        remaining.remove(v)
        nbrs = neighbors[v] & remaining
        for u in nbrs:
            neighbors[u].discard(v)
            neighbors[u].update(w for w in nbrs if w != u)
    return order


# ---------------------------------------------------------------------------
# End-to-end VE
# ---------------------------------------------------------------------------


def _ve_run(factors: list[_Factor], order: list[str]) -> list[_Factor]:
    pool = list(factors)
    for v in order:
        hit = [f for f in pool if v in f.scope]
        if not hit:
            continue
        pool = [f for f in pool if v not in f.scope]
        prod = _product(hit)
        summed = _sum_out(prod, v)
        pool.append(summed)
    return pool


def _final_log_Z(remaining: list[_Factor]) -> float:
    total = 0.0
    for f in remaining:
        if f.scope:
            raise RuntimeError(f"_final_log_Z: unexpected residual factor with scope {f.scope}")
        total += float(f.log_tensor)
    return total


def jt_infer(info: InformationSet) -> InferenceResult:
    """Build junction tree and perform exact inference."""
    info.validate()
    variables = sorted(info.variables)
    if not variables:
        return InferenceResult(beliefs={}, log_Z=0.0, likelihood_audit=[])

    effective_unary, audit = _fold_likelihoods(info)
    base_factors = _build_factors(info, effective_unary)

    # Find variables that appear in at least one factor
    vars_in_factors: set[str] = set()
    for f in base_factors:
        vars_in_factors.update(f.scope)

    # Isolated variables: in variables but not in any factor
    isolated_vars = set(variables) - vars_in_factors

    order_full = _min_neighbors_order(variables, base_factors)
    remaining = _ve_run(base_factors, order_full)
    log_Z = _final_log_Z(remaining)

    # Each isolated variable contributes log(2) to Z (two possible states)
    log_Z += len(isolated_vars) * np.log(2.0)

    if not np.isfinite(log_Z):
        raise RuntimeError(
            "Z = 0: asserted information set is logically inconsistent. "
            "All joint assignments are forbidden by hard evidence and/or "
            "constraints (D5)."
        )

    beliefs: dict[str, float] = {}
    for target in variables:
        if target in isolated_vars:
            # Isolated variable: uniform prior
            beliefs[target] = 0.5
            continue

        others = [v for v in variables if v != target]
        rem = _ve_run(base_factors, _min_neighbors_order(others, base_factors))
        targeted = [f for f in rem if f.scope]
        if not targeted:
            # Target is independent of the information set: uniform 0.5.
            beliefs[target] = 0.5
            continue
        prod = _product(targeted)
        if prod.scope != (target,):
            raise RuntimeError(
                f"jt_infer: residual product scope {prod.scope!r} is not just ({target!r},)"
            )
        t = prod.log_tensor
        m = t.max()
        if not np.isfinite(m):
            raise RuntimeError(f"jt_infer: Z=0 slice found while computing marginal for {target!r}")
        w = np.exp(t - m)
        beliefs[target] = float(w[1] / w.sum())

    return InferenceResult(beliefs=beliefs, log_Z=log_Z, likelihood_audit=audit)
