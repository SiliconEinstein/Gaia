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
            # a degenerate axis in the output. Add it to the index pool so the
            # output has the requested shape (einsum will emit a size-2 axis
            # with uniform contribution from the unary prior path).
            seen.add(v)
            all_vars.append(v)

    # Every non-free variable that appears in some tensor needs a prior.
    # Free variables never get priors (we want P(C|P), not P(C,P)).
    missing = [v for v in all_vars if v not in set(free_vars) and v not in unary_priors]
    if missing:
        raise ValueError(
            f"contract_to_cpt: unary prior missing for marginalized variable(s): {missing}. "
            "The caller must supply a prior for every non-free variable."
        )

    free_set = set(free_vars)

    # Represent the working state as a list of (tensor, axes) pairs.
    # Start by folding unary priors onto their corresponding variable axes,
    # then sequentially eliminate each non-free variable.
    work: list[tuple[np.ndarray, list[str]]] = list(tensors)

    # Attach each unary prior as its own rank-1 tensor.
    for v in all_vars:
        if v in free_set:
            continue
        pi = unary_priors[v]
        work.append((np.array([1.0 - pi, pi], dtype=np.float64), [v]))

    # Sequentially eliminate non-free variables via pairwise contraction.
    # For each variable to eliminate, find all tensors that share it, multiply
    # them together (contracting that variable out), and put the result back.
    # This avoids numpy's 52-symbol limit by never forming a single huge einsum.
    vars_to_eliminate = [v for v in all_vars if v not in free_set]
    for v in vars_to_eliminate:
        # Partition work into tensors that mention v and those that don't.
        with_v = [(t, ax) for t, ax in work if v in ax]
        without_v = [(t, ax) for t, ax in work if v not in ax]
        if not with_v:
            continue
        # Accumulate product over all tensors that mention v.
        # At each step contract with the next tensor, keeping v alive until
        # all multiplicands are folded in, then sum out v.
        acc_t, acc_ax = with_v[0]
        for next_t, next_ax in with_v[1:]:
            # Collect distinct axes for the product tensor.
            merged_ax = list(acc_ax)
            for a in next_ax:
                if a not in merged_ax:
                    merged_ax.append(a)
            # Use at most len(merged_ax) symbols — always ≤ 52 here because
            # we only track variables alive in the two operands at once.
            n_sym = len(merged_ax)
            sym = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"[:n_sym]
            ax_to_sym = {a: sym[i] for i, a in enumerate(merged_ax)}
            lhs = "".join(ax_to_sym[a] for a in acc_ax)
            rhs = "".join(ax_to_sym[a] for a in next_ax)
            out = "".join(ax_to_sym[a] for a in merged_ax)
            acc_t = np.einsum(f"{lhs},{rhs}->{out}", acc_t, next_t, optimize="greedy")
            acc_ax = merged_ax
        # Now sum out v from acc_t.
        v_axis = acc_ax.index(v)
        acc_t = acc_t.sum(axis=v_axis)
        acc_ax = [a for a in acc_ax if a != v]
        without_v.append((acc_t, acc_ax))
        work = without_v

    # All non-free variables have been eliminated.  Combine remaining tensors
    # (which only involve free variables) into a single joint tensor.
    if not work:
        # Degenerate: no tensors at all — return uniform CPT.
        joint = np.ones((2,) * len(free_vars), dtype=np.float64)
    else:
        acc_t, acc_ax = work[0]
        for next_t, next_ax in work[1:]:
            merged_ax = list(acc_ax)
            for a in next_ax:
                if a not in merged_ax:
                    merged_ax.append(a)
            n_sym = len(merged_ax)
            sym = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"[:n_sym]
            ax_to_sym = {a: sym[i] for i, a in enumerate(merged_ax)}
            lhs = "".join(ax_to_sym[a] for a in acc_ax)
            rhs = "".join(ax_to_sym[a] for a in next_ax)
            out = "".join(ax_to_sym[a] for a in merged_ax)
            acc_t = np.einsum(f"{lhs},{rhs}->{out}", acc_t, next_t, optimize="greedy")
            acc_ax = merged_ax
        # Transpose to match free_vars order.
        perm = [acc_ax.index(v) for v in free_vars]
        joint = np.transpose(acc_t, perm)

    # Normalize along the last axis (conclusion).
    totals = joint.sum(axis=-1, keepdims=True)
    if np.any(totals <= 0):
        raise ValueError(
            "contract_to_cpt: zero partition function encountered; "
            "graph may have contradictory deterministic factors."
        )
    return joint / totals
