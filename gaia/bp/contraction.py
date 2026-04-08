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
