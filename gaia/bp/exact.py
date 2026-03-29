"""Exact inference by brute-force enumeration — for verifying BP.

Computes exact marginal beliefs by enumerating all 2^n joint states,
evaluating the full joint distribution P(x) ∝ ∏_v prior(v) × ∏_f ψ_f(x),
then marginalizing each variable.

This is O(2^n × (n + m)) where n = #variables, m = #factors.
Practical for n ≤ ~25 (33M states). Uses numpy vectorization with chunked
processing to keep memory bounded.

Usage:
    from gaia.bp.exact import exact_inference
    beliefs, Z = exact_inference(graph)
"""

from __future__ import annotations

import numpy as np

from gaia.bp.factor_graph import CROMWELL_EPS, Factor, FactorGraph, FactorType

__all__ = ["exact_inference"]

CHUNK_BITS = 20  # Process 2^20 = 1M states per chunk (≈24MB per chunk)


def _factor_log_potentials(
    factor: Factor,
    states: np.ndarray,  # (chunk_size, n) int8
    var_idx: dict[str, int],
) -> np.ndarray:
    """Compute log-potential for a factor across all states in a chunk.

    Returns shape (chunk_size,) float64 array of log-potentials.
    Fully vectorized — no Python loops over states.
    """
    cs = states.shape[0]
    eps = CROMWELL_EPS
    ft = factor.factor_type

    if ft == FactorType.ENTAILMENT:
        # bp.md §2.6: entailment is SILENT when premises are false.
        # log(1.0) = 0 → no contribution when any premise is false.
        p = factor.p
        premise_idxs = [var_idx[v] for v in factor.premises]
        conclusion_idxs = [var_idx[v] for v in factor.conclusions]

        all_prem_true = np.ones(cs, dtype=bool)
        for pi in premise_idxs:
            all_prem_true &= states[:, pi] == 1

        log_pot = np.zeros(cs, dtype=np.float64)
        for ci in conclusion_idxs:
            c_val = states[:, ci]
            # When premises are false: potential = 1.0, log = 0 (silent)
            # When premises are true:  potential = p or 1-p
            pot_val = np.where(
                all_prem_true,
                np.where(c_val == 1, p, 1.0 - p),
                1.0,
            )
            log_pot += np.log(pot_val)
        return log_pot

    elif ft in (FactorType.INDUCTION, FactorType.ABDUCTION):
        # bp.md §2.1: noisy-AND + leak. C4 satisfied via eps.
        p = factor.p
        premise_idxs = [var_idx[v] for v in factor.premises]
        conclusion_idxs = [var_idx[v] for v in factor.conclusions]

        all_prem_true = np.ones(cs, dtype=bool)
        for pi in premise_idxs:
            all_prem_true &= states[:, pi] == 1

        log_pot = np.zeros(cs, dtype=np.float64)
        for ci in conclusion_idxs:
            c_val = states[:, ci]
            pot_val = np.where(
                all_prem_true,
                np.where(c_val == 1, p, 1.0 - p),
                np.where(c_val == 1, eps, 1.0 - eps),
            )
            log_pot += np.log(pot_val)
        return log_pot

    elif ft == FactorType.CONTRADICTION:
        r_idx = var_idx[factor.relation_var]
        claim_idxs = [var_idx[v] for v in factor.premises]

        r_val = states[:, r_idx]
        all_claims_true = np.ones(cs, dtype=bool)
        for ci in claim_idxs:
            all_claims_true &= states[:, ci] == 1

        pot_val = np.where((r_val == 1) & all_claims_true, eps, 1.0)
        return np.log(pot_val)

    elif ft == FactorType.EQUIVALENCE:
        r_idx = var_idx[factor.relation_var]
        a_idx = var_idx[factor.premises[0]]
        b_idx = var_idx[factor.premises[1]]

        r_val = states[:, r_idx]
        a_val = states[:, a_idx]
        b_val = states[:, b_idx]

        pot_val = np.where(
            r_val == 0,
            1.0,
            np.where(a_val == b_val, 1.0 - eps, eps),
        )
        return np.log(pot_val)

    else:
        raise ValueError(f"Unknown FactorType: {ft}")


def exact_inference(
    graph: FactorGraph,
) -> tuple[dict[str, float], float]:
    """Compute exact marginal beliefs by brute-force enumeration.

    Parameters
    ----------
    graph:
        A validated FactorGraph. Max ~25 variables (2^25 ≈ 33M states).

    Returns
    -------
    tuple[dict[str, float], float]
        (beliefs, Z) where:
        - beliefs: {var_id: P(v=1)} exact marginal for each variable
        - Z: partition function (sum of all unnormalized joint probabilities)

    Raises
    ------
    ValueError
        If the graph has more than 26 variables (would require >2B states).
    """
    var_ids = sorted(graph.variables.keys())
    n = len(var_ids)

    if n > 26:
        raise ValueError(
            f"Exact inference requires 2^n enumeration. "
            f"n={n} is too large (max 26). Use BP instead."
        )

    var_idx = {v: i for i, v in enumerate(var_ids)}
    N = 1 << n  # total number of joint states

    # Precompute log-priors
    priors = np.array([graph.variables[v] for v in var_ids], dtype=np.float64)
    log_p1 = np.log(priors)  # log P(v=1)
    log_p0 = np.log(1.0 - priors)  # log P(v=0)

    # Process in chunks to bound memory
    chunk_size = min(N, 1 << CHUNK_BITS)

    # Store all log-joint values (N float64 ≈ 8N bytes)
    all_log_joints = np.empty(N, dtype=np.float64)

    for chunk_start in range(0, N, chunk_size):
        chunk_end = min(chunk_start + chunk_size, N)
        cs = chunk_end - chunk_start

        # Generate binary assignments for this chunk
        arange = np.arange(chunk_start, chunk_end, dtype=np.int64)
        states = np.empty((cs, n), dtype=np.int8)
        for i in range(n):
            states[:, i] = (arange >> i) & 1

        # Log-prior contribution: Σ_i [s_i * log(π_i) + (1-s_i) * log(1-π_i)]
        log_j = (states * log_p1 + (1 - states) * log_p0).sum(axis=1)

        # Factor potential contributions
        for factor in graph.factors:
            log_j += _factor_log_potentials(factor, states, var_idx)

        all_log_joints[chunk_start:chunk_end] = log_j

    # Log-sum-exp for numerical stability
    log_max = all_log_joints.max()
    joint = np.exp(all_log_joints - log_max)
    Z_shifted = joint.sum()

    # True partition function
    log_Z = log_max + np.log(Z_shifted)
    Z = np.exp(log_Z)

    # Marginals: P(v_i=1) = Σ_{states where v_i=1} joint[s] / Z_total
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
    """Format a comparison table between exact and BP beliefs.

    Parameters
    ----------
    graph: FactorGraph for variable names and priors
    exact_beliefs: from exact_inference
    bp_beliefs: from BeliefPropagation.run()
    Z: partition function from exact_inference
    title: table title
    tolerance: max allowed |exact - bp| for a "match" (✓)

    Returns
    -------
    str: formatted table ready for printing
    """
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
