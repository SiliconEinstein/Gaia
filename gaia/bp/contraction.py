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

__all__ = [
    "factor_to_tensor",
    "contract_to_cpt",
    "strategy_cpt",
    "cpt_tensor_to_list",
]

# Sentinel used by ``strategy_cpt`` to detect cycles while the recursion is
# in progress.  When a composite is first visited, we write this sentinel to
# the cache before recursing into its sub-strategies; if the recursion hits
# the same strategy_id again before it completes, we raise instead of looping
# forever.
_IN_PROGRESS = object()


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


def cpt_tensor_to_list(
    tensor: np.ndarray,
    axes: list[str],
    premises: list[str],
    conclusion: str,
) -> list[float]:
    """Flatten a normalized CPT tensor to the bit-indexed list format.

    ``tensor`` must have shape ``(2,) * len(axes)`` and be normalized
    along the conclusion axis.  The output has length ``2 ** len(premises)``
    and is indexed by ``sum(v_i << i for i, v_i in enumerate(premises))``.
    Bit 0 corresponds to the first premise (matching the existing
    ``fold_composite_to_cpt`` convention and ``FactorType.CONDITIONAL``).
    """
    k = len(premises)
    target_order = [*premises, conclusion]
    perm = [axes.index(name) for name in target_order]
    t = np.transpose(tensor, perm)
    out: list[float] = []
    for assignment in range(1 << k):
        idx = tuple(((assignment >> bit) & 1) for bit in range(k)) + (1,)
        out.append(float(t[idx]))
    return out


def strategy_cpt(
    s,
    strat_by_id: dict,
    strat_params: dict[str, list[float]],
    var_priors: dict[str, float],
    namespace: str,
    package_name: str,
    cache: dict,
) -> tuple[np.ndarray, list[str]]:
    """Compute the effective CPT tensor of a single Gaia IR strategy.

    Layer-by-layer variable elimination:
    - Leaf strategies (INFER, NOISY_AND, FormalStrategy, auto-formalized named
      strategies): build a mini FactorGraph via the existing ``_lower_strategy``
      dispatch, convert its factors to tensors, and contract them with unary
      priors from the mini fg's ``variables`` dict.
    - CompositeStrategy: recursion (implemented in Task 5).

    The returned tuple is ``(cpt_tensor, axes)`` where axes =
    ``[*s.premises, s.conclusion]``.

    ``cache`` is mutated: keyed by ``strategy_id``, values are
    ``(cpt_tensor, axes)`` pairs.  Callers pass a fresh dict per top-level
    invocation to scope the cache to that call.

    ``var_priors`` is forwarded to ``_lower_strategy`` so that it can honor
    non-default priors on claim variables (e.g., when called from
    ``compute_coarse_cpts`` with the global factor graph's variables).
    Pass ``{}`` for isolated composite folding.

    Note
    ----
    The ``cache`` is keyed by ``s.strategy_id``, which encodes
    ``(scope, type, premises, conclusion)``.  It does NOT encode
    ``var_priors`` or ``strat_params``.  Callers MUST pass a fresh
    ``cache`` dict for each top-level invocation; reusing a cache
    across calls with different priors or strat_params will return
    stale results for ``FormalStrategy`` and auto-formalized leaves
    whose internal helper claims have non-default priors.
    """
    from gaia.bp.factor_graph import FactorGraph
    from gaia.bp.lowering import _lower_strategy
    from gaia.ir.strategy import CompositeStrategy

    cached = cache.get(s.strategy_id)
    if cached is _IN_PROGRESS:
        raise ValueError(
            f"strategy_cpt: cycle detected — strategy_id {s.strategy_id!r} "
            "is its own ancestor in the composite recursion."
        )
    if cached is not None:
        return cached

    if isinstance(s, CompositeStrategy):
        # Mark this composite as in-progress so recursive calls detect cycles.
        cache[s.strategy_id] = _IN_PROGRESS
        child_tensors: list[tuple[np.ndarray, list[str]]] = []
        for sid in s.sub_strategies:
            sub = strat_by_id.get(sid)
            if sub is None:
                raise KeyError(
                    f"CompositeStrategy {s.strategy_id!r} references missing strategy_id {sid!r}"
                )
            sub_tensor, sub_axes = strategy_cpt(
                sub,
                strat_by_id,
                strat_params,
                var_priors,
                namespace,
                package_name,
                cache,
            )
            child_tensors.append((sub_tensor, sub_axes))

        free = [*s.premises, s.conclusion]
        free_set = set(free)

        # Bridge variables: any child axis that isn't a composite free var.
        # Each bridge gets a unary prior at this layer (default 0.5 if not
        # in var_priors).  Internal helper claims marginalized inside a
        # child's CPT do NOT appear in any child's axes and are correctly
        # skipped here.
        bridges: dict[str, float] = {}
        for _, axes in child_tensors:
            for v in axes:
                if v not in free_set and v not in bridges:
                    bridges[v] = var_priors.get(v, 0.5)

        cpt_tensor = contract_to_cpt(child_tensors, free_vars=free, unary_priors=bridges)
        result = (cpt_tensor, free)
        cache[s.strategy_id] = result
        return result

    # Leaf: build a mini FactorGraph via the existing _lower_strategy dispatch.
    mini = FactorGraph()
    ctr = [0]
    claim_ids: set[str] = set()
    _lower_strategy(
        mini,
        s,
        strat_by_id,
        var_priors,
        strat_params,
        expand_formal=True,
        infer_degraded=False,
        ctr=ctr,
        claim_ids=claim_ids,
        namespace=namespace,
        package_name=package_name,
    )

    tensors = [factor_to_tensor(f) for f in mini.factors]
    free = [*s.premises, s.conclusion]
    free_set = set(free)
    # Unary priors for every variable in the mini fg that is NOT a free axis.
    non_free = {v: p for v, p in mini.variables.items() if v not in free_set}

    cpt_tensor = contract_to_cpt(tensors, free_vars=free, unary_priors=non_free)
    result = (cpt_tensor, free)
    cache[s.strategy_id] = result
    return result
