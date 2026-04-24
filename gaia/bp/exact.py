"""Exact inference by brute-force enumeration — for verifying BP."""

from __future__ import annotations

import numpy as np

from gaia.bp.factor_graph import CROMWELL_EPS, Factor, FactorGraph, FactorType

__all__ = ["exact_inference", "exact_joint_over", "comparison_table"]

CHUNK_BITS = 20


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
) -> np.ndarray:
    cs = states.shape[0]
    h = 1.0 - CROMWELL_EPS
    lo = CROMWELL_EPS
    ft = factor.factor_type
    vids = factor.variables
    concl = factor.conclusion

    if ft == FactorType.IMPLICATION:
        a_idx = var_idx[vids[0]]
        b_idx = var_idx[vids[1]]
        h_idx = var_idx[concl]
        a = states[:, a_idx]
        b = states[:, b_idx]
        hv = states[:, h_idx]
        # H=1: standard implication (A=1,B=0 forbidden)
        # H=0: complement (A=1,B=0 is the only HIGH row)
        std_impl = np.where((a == 1) & (b == 0), lo, h)
        comp = np.where((a == 1) & (b == 0), h, lo)
        pot = np.where(hv == 1, std_impl, comp)
        return np.log(pot)

    if ft == FactorType.CONJUNCTION:
        idxs = [var_idx[x] for x in vids]
        m_idx = var_idx[concl]
        all_one = np.ones(cs, dtype=bool)
        for ii in idxs:
            all_one &= states[:, ii] == 1
        m = states[:, m_idx]
        ok = (all_one & (m == 1)) | ((~all_one) & (m == 0))
        pot = np.where(ok, h, lo)
        return np.log(pot)

    if ft == FactorType.DISJUNCTION:
        idxs = [var_idx[x] for x in vids]
        d_idx = var_idx[concl]
        any_one = np.zeros(cs, dtype=bool)
        for ii in idxs:
            any_one |= states[:, ii] == 1
        d = states[:, d_idx]
        ok = (any_one & (d == 1)) | ((~any_one) & (d == 0))
        pot = np.where(ok, h, lo)
        return np.log(pot)

    if ft == FactorType.EQUIVALENCE:
        a_idx = var_idx[vids[0]]
        b_idx = var_idx[vids[1]]
        h_idx = var_idx[concl]
        target = (states[:, a_idx] == states[:, b_idx]).astype(np.int8)
        ok = states[:, h_idx] == target
        pot = np.where(ok, h, lo)
        return np.log(pot)

    if ft == FactorType.CONTRADICTION:
        a_idx = var_idx[vids[0]]
        b_idx = var_idx[vids[1]]
        h_idx = var_idx[concl]
        both = (states[:, a_idx] == 1) & (states[:, b_idx] == 1)
        target = np.where(both, 0, 1).astype(np.int8)
        ok = states[:, h_idx] == target
        pot = np.where(ok, h, lo)
        return np.log(pot)

    if ft == FactorType.NEGATION:
        a_idx = var_idx[vids[0]]
        h_idx = var_idx[concl]
        target = 1 - states[:, a_idx]
        ok = states[:, h_idx] == target
        pot = np.where(ok, h, lo)
        return np.log(pot)

    if ft == FactorType.COMPLEMENT:
        a_idx = var_idx[vids[0]]
        b_idx = var_idx[vids[1]]
        h_idx = var_idx[concl]
        xor = states[:, a_idx] != states[:, b_idx]
        target = xor.astype(np.int8)
        ok = states[:, h_idx] == target
        pot = np.where(ok, h, lo)
        return np.log(pot)

    if ft == FactorType.SOFT_ENTAILMENT:
        assert factor.p1 is not None and factor.p2 is not None
        p1, p2 = factor.p1, factor.p2
        m_idx = var_idx[vids[0]]
        c_idx = var_idx[concl]
        m = states[:, m_idx]
        cv = states[:, c_idx]
        pot = np.where(
            m == 1,
            np.where(cv == 1, p1, 1.0 - p1),
            np.where(cv == 0, p2, 1.0 - p2),
        )
        return np.log(pot)

    if ft == FactorType.CONDITIONAL:
        assert factor.cpt is not None
        idxs = [var_idx[x] for x in vids]
        c_idx = var_idx[concl]
        cpt = np.array(factor.cpt, dtype=np.float64)
        idx = np.zeros(cs, dtype=np.int64)
        for i, ii in enumerate(idxs):
            idx |= states[:, ii].astype(np.int64) << i
        p_sel = cpt[idx]
        cv = states[:, c_idx]
        pot = np.where(cv == 1, p_sel, 1.0 - p_sel)
        return np.log(pot)

    if ft == FactorType.PAIRWISE_POTENTIAL:
        assert factor.cpt is not None
        a_idx = var_idx[vids[0]]
        b_idx = var_idx[concl]
        weights = np.array(factor.cpt, dtype=np.float64)
        idx = states[:, a_idx].astype(np.int64) | (states[:, b_idx].astype(np.int64) << 1)
        return np.log(weights[idx])

    raise ValueError(f"Unknown FactorType: {ft}")


def exact_inference(graph: FactorGraph) -> tuple[dict[str, float], float]:
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

    var_ids, var_idx, all_log_joints = _enumerate_log_joint(graph)
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
