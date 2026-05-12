"""Exact inference by brute-force enumeration — for verifying BP."""

from __future__ import annotations

from collections.abc import Callable

import numpy as np
from numpy.typing import NDArray

from gaia.bp.factor_graph import CROMWELL_EPS, Factor, FactorGraph, FactorType

__all__ = ["comparison_table", "exact_inference", "exact_joint_over"]

CHUNK_BITS = 20
FloatArray = NDArray[np.float64]
type LogPotentialEvaluator = Callable[[Factor, np.ndarray, dict[str, int]], FloatArray]
_HIGH = 1.0 - CROMWELL_EPS
_LOW = CROMWELL_EPS


def _float_array(values: object) -> FloatArray:
    """Return a float64 ndarray while preserving runtime numpy semantics."""
    return np.asarray(values, dtype=np.float64)


def _enumerate_log_joint(
    graph: FactorGraph,
) -> tuple[list[str], dict[str, int], np.ndarray]:
    var_ids = sorted(graph.variables.keys())
    n = len(var_ids)

    if n > 26:
        raise ValueError(
            f"Exact inference requires 2^n enumeration. "
            f"n={n} is too large (max 26). Use BP instead."
        )

    var_idx = {v: i for i, v in enumerate(var_ids)}
    N = 1 << n

    chunk_size = min(N, 1 << CHUNK_BITS)
    all_log_joints = np.empty(N, dtype=np.float64)
    unary_idxs: list[tuple[int, float]] = [
        (var_idx[v], p) for v, p in graph.unary_factors.items() if v in var_idx
    ]

    for chunk_start in range(0, N, chunk_size):
        chunk_end = min(chunk_start + chunk_size, N)
        cs = chunk_end - chunk_start

        arange = np.arange(chunk_start, chunk_end, dtype=np.int64)
        states = np.empty((cs, n), dtype=np.int8)
        for i in range(n):
            states[:, i] = (arange >> i) & 1

        log_j = np.zeros(cs, dtype=np.float64)
        for i, p in unary_idxs:
            log_j += np.where(states[:, i] == 1, np.log(p), np.log(1.0 - p))

        for factor in graph.factors:
            log_j += _factor_log_potentials(factor, states, var_idx)

        all_log_joints[chunk_start:chunk_end] = log_j

    return var_ids, var_idx, all_log_joints


def _shifted_joint(log_joints: np.ndarray) -> tuple[np.ndarray, float]:
    log_max = log_joints.max()
    joint = np.exp(log_joints - log_max)
    z_shifted = joint.sum()
    return joint, float(z_shifted)


def _factor_log_potentials(
    factor: Factor,
    states: np.ndarray,
    var_idx: dict[str, int],
) -> FloatArray:
    try:
        evaluator = _LOG_POTENTIAL_EVALUATORS[factor.factor_type]
    except KeyError as err:
        raise ValueError(f"Unknown FactorType: {factor.factor_type}") from err
    return evaluator(factor, states, var_idx)


def _log_implication(factor: Factor, states: np.ndarray, var_idx: dict[str, int]) -> FloatArray:
    """Vectorized log potentials for implication factors."""
    vids = factor.variables
    a = states[:, var_idx[vids[0]]]
    b = states[:, var_idx[vids[1]]]
    helper = states[:, var_idx[factor.conclusion]]
    std_impl = np.where((a == 1) & (b == 0), _LOW, _HIGH)
    comp = np.where((a == 1) & (b == 0), _HIGH, _LOW)
    return _float_array(np.log(np.where(helper == 1, std_impl, comp)))


def _log_conjunction(factor: Factor, states: np.ndarray, var_idx: dict[str, int]) -> FloatArray:
    """Vectorized log potentials for conjunction factors."""
    all_one = np.ones(states.shape[0], dtype=bool)
    for index in [var_idx[x] for x in factor.variables]:
        all_one &= states[:, index] == 1
    conclusion = states[:, var_idx[factor.conclusion]]
    ok = (all_one & (conclusion == 1)) | ((~all_one) & (conclusion == 0))
    return _float_array(np.log(np.where(ok, _HIGH, _LOW)))


def _log_disjunction(factor: Factor, states: np.ndarray, var_idx: dict[str, int]) -> FloatArray:
    """Vectorized log potentials for disjunction factors."""
    any_one = np.zeros(states.shape[0], dtype=bool)
    for index in [var_idx[x] for x in factor.variables]:
        any_one |= states[:, index] == 1
    conclusion = states[:, var_idx[factor.conclusion]]
    ok = (any_one & (conclusion == 1)) | ((~any_one) & (conclusion == 0))
    return _float_array(np.log(np.where(ok, _HIGH, _LOW)))


def _log_equivalence(factor: Factor, states: np.ndarray, var_idx: dict[str, int]) -> FloatArray:
    """Vectorized log potentials for equivalence factors."""
    vids = factor.variables
    target = (states[:, var_idx[vids[0]]] == states[:, var_idx[vids[1]]]).astype(np.int8)
    ok = states[:, var_idx[factor.conclusion]] == target
    return _float_array(np.log(np.where(ok, _HIGH, _LOW)))


def _log_contradiction(factor: Factor, states: np.ndarray, var_idx: dict[str, int]) -> FloatArray:
    """Vectorized log potentials for contradiction factors."""
    vids = factor.variables
    both = (states[:, var_idx[vids[0]]] == 1) & (states[:, var_idx[vids[1]]] == 1)
    target = np.where(both, 0, 1).astype(np.int8)
    ok = states[:, var_idx[factor.conclusion]] == target
    return _float_array(np.log(np.where(ok, _HIGH, _LOW)))


def _log_negation(factor: Factor, states: np.ndarray, var_idx: dict[str, int]) -> FloatArray:
    """Vectorized log potentials for negation factors."""
    target = 1 - states[:, var_idx[factor.variables[0]]]
    ok = states[:, var_idx[factor.conclusion]] == target
    return _float_array(np.log(np.where(ok, _HIGH, _LOW)))


def _log_complement(factor: Factor, states: np.ndarray, var_idx: dict[str, int]) -> FloatArray:
    """Vectorized log potentials for complement factors."""
    vids = factor.variables
    target = (states[:, var_idx[vids[0]]] != states[:, var_idx[vids[1]]]).astype(np.int8)
    ok = states[:, var_idx[factor.conclusion]] == target
    return _float_array(np.log(np.where(ok, _HIGH, _LOW)))


def _log_soft_entailment(factor: Factor, states: np.ndarray, var_idx: dict[str, int]) -> FloatArray:
    """Vectorized log potentials for soft-entailment factors."""
    assert factor.p1 is not None and factor.p2 is not None
    premise = states[:, var_idx[factor.variables[0]]]
    conclusion = states[:, var_idx[factor.conclusion]]
    pot = np.where(
        premise == 1,
        np.where(conclusion == 1, factor.p1, 1.0 - factor.p1),
        np.where(conclusion == 0, factor.p2, 1.0 - factor.p2),
    )
    return _float_array(np.log(pot))


def _log_conditional(factor: Factor, states: np.ndarray, var_idx: dict[str, int]) -> FloatArray:
    """Vectorized log potentials for conditional factors."""
    assert factor.cpt is not None
    cpt = np.array(factor.cpt, dtype=np.float64)
    index = np.zeros(states.shape[0], dtype=np.int64)
    for bit, variable_index in enumerate([var_idx[x] for x in factor.variables]):
        index |= states[:, variable_index].astype(np.int64) << bit
    p_sel = cpt[index]
    conclusion = states[:, var_idx[factor.conclusion]]
    return _float_array(np.log(np.where(conclusion == 1, p_sel, 1.0 - p_sel)))


def _log_pairwise(factor: Factor, states: np.ndarray, var_idx: dict[str, int]) -> FloatArray:
    """Vectorized log potentials for pairwise-potential factors."""
    assert factor.cpt is not None
    a_idx = var_idx[factor.variables[0]]
    b_idx = var_idx[factor.conclusion]
    weights = np.array(factor.cpt, dtype=np.float64)
    index = states[:, a_idx].astype(np.int64) | (states[:, b_idx].astype(np.int64) << 1)
    return _float_array(np.log(weights[index]))


_LOG_POTENTIAL_EVALUATORS: dict[FactorType, LogPotentialEvaluator] = {
    FactorType.IMPLICATION: _log_implication,
    FactorType.CONJUNCTION: _log_conjunction,
    FactorType.DISJUNCTION: _log_disjunction,
    FactorType.EQUIVALENCE: _log_equivalence,
    FactorType.CONTRADICTION: _log_contradiction,
    FactorType.NEGATION: _log_negation,
    FactorType.COMPLEMENT: _log_complement,
    FactorType.SOFT_ENTAILMENT: _log_soft_entailment,
    FactorType.CONDITIONAL: _log_conditional,
    FactorType.PAIRWISE_POTENTIAL: _log_pairwise,
}


def exact_inference(graph: FactorGraph) -> tuple[dict[str, float], float]:
    """Compute exact marginals and the partition function by enumeration.

    Args:
        graph: Factor graph to enumerate. Graphs with more than 26 variables
            are rejected by the shared enumeration helper.

    Returns:
        A pair ``(beliefs, Z)`` where ``beliefs`` maps variable IDs to exact
        posterior ``P(x=1)`` and ``Z`` is the unnormalized partition function.
    """
    var_ids, _, all_log_joints = _enumerate_log_joint(graph)
    joint, z_shifted = _shifted_joint(all_log_joints)
    log_Z = all_log_joints.max() + np.log(z_shifted)
    Z = float(np.exp(log_Z))

    full_arange = np.arange(len(all_log_joints), dtype=np.int64)
    beliefs: dict[str, float] = {}
    for i, vid in enumerate(var_ids):
        mask = ((full_arange >> i) & 1) == 1
        beliefs[vid] = float(joint[mask].sum() / z_shifted)

    return beliefs, Z


def exact_joint_over(graph: FactorGraph, free_vars: list[str]) -> np.ndarray:
    """Return the normalized joint over ``free_vars`` by exact enumeration.

    The result is indexed by the bit pattern over ``free_vars`` in order:
    index ``sum(v_i << i for i, v_i in enumerate(free_vars))``.
    """
    if not free_vars:
        return np.array([1.0], dtype=np.float64)

    _var_ids, var_idx, all_log_joints = _enumerate_log_joint(graph)
    missing = [v for v in free_vars if v not in var_idx]
    if missing:
        raise KeyError(f"exact_joint_over: unknown free vars {missing!r}")

    joint, z_shifted = _shifted_joint(all_log_joints)
    full_arange = np.arange(len(all_log_joints), dtype=np.int64)
    assignment_idx = np.zeros(len(all_log_joints), dtype=np.int64)
    for bit, vid in enumerate(free_vars):
        assignment_idx |= ((full_arange >> var_idx[vid]) & 1).astype(np.int64) << bit

    probs = np.bincount(assignment_idx, weights=joint, minlength=1 << len(free_vars))
    return probs / z_shifted


def comparison_table(
    graph: FactorGraph,
    exact_beliefs: dict[str, float],
    bp_beliefs: dict[str, float],
    Z: float,
    title: str = "Exact vs BP Comparison",
    tolerance: float = 0.02,
) -> str:
    """Render a side-by-side exact-vs-BP belief comparison table.

    Args:
        graph: Factor graph whose variables are displayed.
        exact_beliefs: Exact posterior beliefs keyed by variable ID.
        bp_beliefs: Approximate BP posterior beliefs keyed by variable ID.
        Z: Exact partition function to show in the table header.
        title: Header title for the rendered table.
        tolerance: Absolute difference below which a row is counted as matching.

    Returns:
        A formatted multiline table for diagnostics and tests.
    """
    var_ids = sorted(graph.variables.keys())

    lines = []
    lines.append(f"\n{'=' * 78}")
    lines.append(f"  {title}")
    lines.append(f"  Total states: {2 ** len(var_ids):,}  |  Partition function Z = {Z:.6e}")
    lines.append(f"{'=' * 78}")
    header = f"  {'Variable':25s}  {'Unary':>7}  {'Exact':>8}  {'BP':>8}  {'Diff':>8}  Match?"
    lines.append(header)
    lines.append("  " + "-" * 72)

    n_match = 0
    n_total = 0
    max_diff = 0.0

    for vid in var_ids:
        prior = graph.unary_factors.get(vid, 0.5)
        ex = exact_beliefs.get(vid, 0.0)
        bp = bp_beliefs.get(vid, 0.0)
        diff = abs(ex - bp)
        max_diff = max(max_diff, diff)
        match = diff < tolerance
        if match:
            n_match += 1
        n_total += 1
        mark = "  ✓" if match else "  ✗"
        lines.append(f"  {vid:25s}  {prior:7.4f}  {ex:8.6f}  {bp:8.6f}  {diff:8.6f}{mark}")

    lines.append("  " + "-" * 72)
    lines.append(
        f"  Matched: {n_match}/{n_total}  |  Max diff: {max_diff:.6f}  |  Tolerance: {tolerance}"
    )

    if n_match == n_total:
        lines.append("  ✓ All beliefs match within tolerance — BP is correct on this graph.")
    else:
        mismatches = n_total - n_match
        lines.append(
            f"  ✗ {mismatches} belief(s) differ beyond tolerance — "
            "expected for loopy BP on graphs with cycles."
        )

    lines.append(f"{'=' * 78}")
    return "\n".join(lines)
