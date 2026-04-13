"""Exact inference by brute-force enumeration — for verifying BP."""

from __future__ import annotations

import numpy as np

from gaia.bp.factor_graph import CROMWELL_EPS, Factor, FactorGraph, FactorType

__all__ = ["exact_inference", "comparison_table"]

CHUNK_BITS = 20


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

    raise ValueError(f"Unknown FactorType: {ft}")


def exact_inference(graph: FactorGraph) -> tuple[dict[str, float], float]:
    var_ids = sorted(graph.variables.keys())
    n = len(var_ids)

    if n > 26:
        raise ValueError(
            f"Exact inference requires 2^n enumeration. "
            f"n={n} is too large (max 26). Use BP instead."
        )

    var_idx = {v: i for i, v in enumerate(var_ids)}
    N = 1 << n

    priors = np.array([graph.variables[v] for v in var_ids], dtype=np.float64)
    log_p1 = np.log(priors)
    log_p0 = np.log(1.0 - priors)

    chunk_size = min(N, 1 << CHUNK_BITS)
    all_log_joints = np.empty(N, dtype=np.float64)

    for chunk_start in range(0, N, chunk_size):
        chunk_end = min(chunk_start + chunk_size, N)
        cs = chunk_end - chunk_start

        arange = np.arange(chunk_start, chunk_end, dtype=np.int64)
        states = np.empty((cs, n), dtype=np.int8)
        for i in range(n):
            states[:, i] = (arange >> i) & 1

        log_j = (states * log_p1 + (1 - states) * log_p0).sum(axis=1)

        for factor in graph.factors:
            log_j += _factor_log_potentials(factor, states, var_idx)

        all_log_joints[chunk_start:chunk_end] = log_j

    log_max = all_log_joints.max()
    joint = np.exp(all_log_joints - log_max)
    Z_shifted = joint.sum()

    log_Z = log_max + np.log(Z_shifted)
    Z = float(np.exp(log_Z))

    full_arange = np.arange(N, dtype=np.int64)
    beliefs: dict[str, float] = {}
    for i, vid in enumerate(var_ids):
        mask = ((full_arange >> i) & 1) == 1
        beliefs[vid] = float(joint[mask].sum() / Z_shifted)

    return beliefs, Z


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
    header = f"  {'Variable':25s}  {'Prior':>7}  {'Exact':>8}  {'BP':>8}  {'Diff':>8}  Match?"
    lines.append(header)
    lines.append("  " + "-" * 72)

    n_match = 0
    n_total = 0
    max_diff = 0.0

    for vid in var_ids:
        prior = graph.variables[vid]
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
