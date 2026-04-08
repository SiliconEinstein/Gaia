"""Tensor-contraction-based CPT computation for Gaia IR strategies.

Replaces O(2^k × BP) brute-force folding in ``fold_composite_to_cpt`` and
``compute_coarse_cpts`` with exact variable elimination.

Design:
    - ``factor_to_tensor``: Factor → dense ndarray + axis labels
    - ``contract_to_cpt``: einsum-based variable elimination with unary priors
    - ``strategy_cpt``: recursive layer-by-layer CPT for a Strategy, cached by
      strategy_id per call

Every non-free variable's unary prior is applied exactly once, at the layer
where it is marginalized.  This matches the semantics of BP on the current
factor graph and of ``gaia.bp.exact.exact_inference``.

Spec: github.com/SiliconEinstein/Gaia/issues/357
"""

from __future__ import annotations

import numpy as np

from gaia.bp.factor_graph import CROMWELL_EPS, Factor, FactorType

_HIGH: float = 1.0 - CROMWELL_EPS
_LOW: float = CROMWELL_EPS


def factor_to_tensor(f: Factor) -> tuple[np.ndarray, list[str]]:
    """Build a dense tensor representation of a Factor.

    Shape: ``(2,) * (len(f.variables) + 1)``.
    Axis order: ``f.variables`` in order, then ``f.conclusion``.

    Deterministic factors use ``_HIGH``/``_LOW`` (Cromwell clamp) so they
    match the semantics of ``gaia.bp.potentials`` exactly.  Parametric
    factors (SOFT_ENTAILMENT, CONDITIONAL) use their stored parameters.
    """
    axes = [*f.variables, f.conclusion]
    n = len(axes)
    shape = (2,) * n
    ft = f.factor_type

    if ft == FactorType.IMPLICATION:
        t = np.full(shape, _HIGH, dtype=np.float64)
        # Forbid (antecedent=1, consequent=0)
        t[1, 0] = _LOW
        return t, axes

    if ft == FactorType.CONJUNCTION:
        grids = np.indices(shape)  # shape: (n, 2, 2, ..., 2)
        inputs_all_one = grids[:-1].all(axis=0)
        concl = grids[-1].astype(bool)
        t = np.where(concl == inputs_all_one, _HIGH, _LOW).astype(np.float64)
        return t, axes

    if ft == FactorType.DISJUNCTION:
        grids = np.indices(shape)
        inputs_any_one = grids[:-1].any(axis=0)
        concl = grids[-1].astype(bool)
        t = np.where(concl == inputs_any_one, _HIGH, _LOW).astype(np.float64)
        return t, axes

    if ft == FactorType.EQUIVALENCE:
        grids = np.indices(shape)
        # Helper concl == (A == B)
        target = grids[0] == grids[1]
        t = np.where(grids[2].astype(bool) == target, _HIGH, _LOW).astype(np.float64)
        return t, axes

    if ft == FactorType.CONTRADICTION:
        grids = np.indices(shape)
        # Helper concl == NOT(A AND B)
        target = ~((grids[0] == 1) & (grids[1] == 1))
        t = np.where(grids[2].astype(bool) == target, _HIGH, _LOW).astype(np.float64)
        return t, axes

    if ft == FactorType.COMPLEMENT:
        grids = np.indices(shape)
        # Helper concl == (A XOR B)
        target = grids[0] != grids[1]
        t = np.where(grids[2].astype(bool) == target, _HIGH, _LOW).astype(np.float64)
        return t, axes

    if ft == FactorType.SOFT_ENTAILMENT:
        if f.p1 is None or f.p2 is None:
            raise ValueError(f"SOFT_ENTAILMENT {f.factor_id!r} missing p1/p2")
        p1, p2 = f.p1, f.p2
        # p1 = P(C=1 | premise=1); p2 = P(C=0 | premise=0)
        # Axes: [premise, conclusion]
        t = np.empty(shape, dtype=np.float64)
        t[0, 0] = p2
        t[0, 1] = 1.0 - p2
        t[1, 0] = 1.0 - p1
        t[1, 1] = p1
        return t, axes

    if ft == FactorType.CONDITIONAL:
        if f.cpt is None:
            raise ValueError(f"CONDITIONAL {f.factor_id!r} missing cpt")
        k = len(f.variables)
        expected = 1 << k
        if len(f.cpt) != expected:
            raise ValueError(
                f"CONDITIONAL {f.factor_id!r}: cpt length {len(f.cpt)} != 2^k={expected}"
            )
        cpt_arr = np.asarray(f.cpt, dtype=np.float64)
        grids = np.indices(shape)
        # Build the flat premise index: sum(v_i << i) over input axes
        prem_idx = np.zeros(shape, dtype=np.int64)
        for bit in range(k):
            prem_idx |= grids[bit].astype(np.int64) << bit
        p = cpt_arr[prem_idx]
        concl = grids[-1]
        t = np.where(concl == 1, p, 1.0 - p)
        return t, axes

    raise ValueError(f"Unknown FactorType: {ft!r}")


def contract_to_cpt(
    tensors: list[tuple[np.ndarray, list[str]]],
    free_vars: list[str],
    unary_priors: dict[str, float],
) -> np.ndarray:
    """Contract a list of factor tensors down to a conditional CPT tensor.

    Uses ``opt_einsum`` to perform variable elimination: all factor
    tensors and unary prior tensors are multiplied and summed over every
    non-free variable in a single call, with an automatically-optimized
    contraction order.

    Parameters
    ----------
    tensors:
        List of ``(ndarray, axis_var_ids)`` pairs.  The ndarray has one axis
        per name in ``axis_var_ids`` (in order); each axis has size 2.
    free_vars:
        Variables that remain as axes in the output, in output order.
        Typically ``[*premises, conclusion]``.  The last entry is the
        conclusion and is the axis along which the output is normalized.
    unary_priors:
        Variables that must be marginalized out and have a prior
        ``[1-π, π]`` applied as a unary tensor.  Every non-free variable
        that appears in some tensor must be present here.

    Returns
    -------
    ndarray of shape ``(2,) * len(free_vars)`` giving ``P(conclusion | premises)``.
    The last axis is normalized so that ``T[..., 0] + T[..., 1] == 1``.

    Raises
    ------
    ValueError
        If ``free_vars`` is empty, if a unary prior is missing for a
        variable that appears in some tensor but is neither free nor
        covered by ``unary_priors``, or if the contracted joint is zero
        for some premise assignment (would produce NaN after normalizing).
    """
    import opt_einsum as oe

    if not free_vars:
        raise ValueError("free_vars must be non-empty (need at least a conclusion axis)")

    # Collect all distinct variable names across all tensors, preserving
    # first-seen order for determinism.
    all_vars: list[str] = []
    seen: set[str] = set()
    for _, axes in tensors:
        for v in axes:
            if v not in seen:
                seen.add(v)
                all_vars.append(v)
    for v in free_vars:
        if v not in seen:
            # A free variable that doesn't appear in any tensor would produce
            # a degenerate axis in the output. Track it so opt_einsum emits
            # the expected shape (the unary path leaves it as a size-2 axis).
            seen.add(v)
            all_vars.append(v)

    # Every non-free variable that appears in some tensor needs a prior.
    # Free variables never get priors (we want P(C|P), not P(C,P)).
    free_set = set(free_vars)
    missing = [v for v in all_vars if v not in free_set and v not in unary_priors]
    if missing:
        raise ValueError(
            f"contract_to_cpt: unary prior missing for marginalized variable(s): {missing}. "
            "The caller must supply a prior for every non-free variable."
        )

    # Assign a unique integer index to each variable.  opt_einsum accepts
    # arbitrary hashable labels in the list-of-indices form and does not
    # suffer from numpy.einsum's 52-symbol alphabet limit.
    var_to_idx: dict[str, int] = {v: i for i, v in enumerate(all_vars)}

    # Build the opt_einsum argument list: alternating (tensor, [axis_indices]).
    args: list[object] = []
    for t, axes in tensors:
        args.append(t)
        args.append([var_to_idx[v] for v in axes])

    # Add unary prior tensors for each non-free variable.
    for v in all_vars:
        if v in free_set:
            continue
        pi = unary_priors[v]
        args.append(np.array([1.0 - pi, pi], dtype=np.float64))
        args.append([var_to_idx[v]])

    # Output indices = free_vars in requested order.
    out_indices = [var_to_idx[v] for v in free_vars]
    args.append(out_indices)

    joint = oe.contract(*args, optimize="greedy")

    # Normalize along the last axis (conclusion).
    totals = joint.sum(axis=-1, keepdims=True)
    if np.any(totals <= 0):
        raise ValueError(
            "contract_to_cpt: zero partition function encountered; "
            "graph may have contradictory deterministic factors."
        )
    return joint / totals
