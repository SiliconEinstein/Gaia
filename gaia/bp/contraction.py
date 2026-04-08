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
        t = np.full(shape, _LOW, dtype=np.float64)
        for idx in np.ndindex(*shape):
            inputs = idx[:-1]
            concl = idx[-1]
            target = 1 if all(v == 1 for v in inputs) else 0
            if concl == target:
                t[idx] = _HIGH
        return t, axes

    if ft == FactorType.DISJUNCTION:
        t = np.full(shape, _LOW, dtype=np.float64)
        for idx in np.ndindex(*shape):
            inputs = idx[:-1]
            concl = idx[-1]
            target = 1 if any(v == 1 for v in inputs) else 0
            if concl == target:
                t[idx] = _HIGH
        return t, axes

    if ft == FactorType.EQUIVALENCE:
        t = np.full(shape, _LOW, dtype=np.float64)
        for a in (0, 1):
            for b in (0, 1):
                target = 1 if a == b else 0
                t[a, b, target] = _HIGH
        return t, axes

    if ft == FactorType.CONTRADICTION:
        t = np.full(shape, _LOW, dtype=np.float64)
        for a in (0, 1):
            for b in (0, 1):
                target = 0 if (a == 1 and b == 1) else 1
                t[a, b, target] = _HIGH
        return t, axes

    if ft == FactorType.COMPLEMENT:
        t = np.full(shape, _LOW, dtype=np.float64)
        for a in (0, 1):
            for b in (0, 1):
                target = 1 if a != b else 0
                t[a, b, target] = _HIGH
        return t, axes

    if ft == FactorType.SOFT_ENTAILMENT:
        if f.p1 is None or f.p2 is None:
            raise ValueError(f"SOFT_ENTAILMENT {f.factor_id!r} missing p1/p2")
        p1, p2 = f.p1, f.p2
        t = np.empty(shape, dtype=np.float64)
        # Axes: [premise, conclusion]
        t[0, 0] = p2
        t[0, 1] = 1.0 - p2
        t[1, 0] = 1.0 - p1
        t[1, 1] = p1
        return t, axes

    if ft == FactorType.CONDITIONAL:
        if f.cpt is None:
            raise ValueError(f"CONDITIONAL {f.factor_id!r} missing cpt")
        cpt = np.asarray(f.cpt, dtype=np.float64)
        k = len(f.variables)
        expected = 1 << k
        if cpt.shape != (expected,):
            raise ValueError(
                f"CONDITIONAL {f.factor_id!r}: cpt length {cpt.shape[0]} != 2^k={expected}"
            )
        t = np.empty(shape, dtype=np.float64)
        for idx in np.ndindex(*shape):
            prem_idx = 0
            for bit, v in enumerate(idx[:-1]):
                if v == 1:
                    prem_idx |= 1 << bit
            p = cpt[prem_idx]
            t[idx] = p if idx[-1] == 1 else (1.0 - p)
        return t, axes

    raise ValueError(f"Unknown FactorType: {ft!r}")
