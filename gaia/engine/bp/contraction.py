"""Tensor-contraction-based CPT computation for Gaia IR strategies.

Replaces O(2^k × BP) brute-force folding in ``fold_composite_to_cpt`` and
``compute_coarse_cpts`` with exact variable elimination.

Design:
    - ``factor_to_tensor``: Factor → dense ndarray + axis labels
    - ``contract_to_cpt``: einsum-based variable elimination with explicit unary factors
    - ``strategy_cpt``: recursive layer-by-layer CPT for a Strategy, cached by
      strategy_id per call

Every explicit non-free unary factor is applied exactly once, at the layer
where it is marginalized. Variables without unary factors are summed with the
base counting measure, matching ``gaia.engine.bp.exact.exact_inference``.

Spec: github.com/SiliconEinstein/Gaia/issues/357
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import numpy as np
from numpy.typing import NDArray

from gaia.engine.bp.factor_graph import Factor, FactorType
from gaia.engine.ir.strategy import Strategy

_HIGH: float = 1.0
_LOW: float = 0.0
type FloatArray = NDArray[np.float64]
type StrategyCpt = tuple[FloatArray, list[str]]
type TensorBuilder = Callable[[Factor, list[str], tuple[int, ...]], StrategyCpt]

__all__ = [
    "contract_to_cpt",
    "cpt_tensor_to_list",
    "factor_to_tensor",
    "strategy_cpt",
]


# Sentinel used by ``strategy_cpt`` to detect cycles while the recursion is
# in progress.  When a composite is first visited, we write this sentinel to
# the cache before recursing into its sub-strategies; if the recursion hits
# the same strategy_id again before it completes, we raise instead of looping
# forever.
class _InProgress:
    """Sentinel type for cycle detection in strategy CPT recursion."""


_IN_PROGRESS = _InProgress()
type StrategyCptCacheValue = StrategyCpt | _InProgress


def _float_array(values: object) -> FloatArray:
    """Return a float64 ndarray while preserving runtime numpy semantics."""
    return np.asarray(values, dtype=np.float64)


def _implication_tensor(_f: Factor, axes: list[str], shape: tuple[int, ...]) -> StrategyCpt:
    """Build the tensor for a ternary implication helper."""
    t = np.empty(shape, dtype=np.float64)
    for a in range(2):
        for b in range(2):
            for h in range(2):
                if h == 1:
                    t[a, b, h] = _LOW if (a == 1 and b == 0) else _HIGH
                else:
                    t[a, b, h] = _HIGH if (a == 1 and b == 0) else _LOW
    return t, axes


def _conjunction_tensor(_f: Factor, axes: list[str], shape: tuple[int, ...]) -> StrategyCpt:
    """Build the tensor for a conjunction factor."""
    grids = np.indices(shape)
    inputs_all_one = grids[:-1].all(axis=0)
    conclusion = grids[-1].astype(bool)
    return np.where(conclusion == inputs_all_one, _HIGH, _LOW).astype(np.float64), axes


def _disjunction_tensor(_f: Factor, axes: list[str], shape: tuple[int, ...]) -> StrategyCpt:
    """Build the tensor for a disjunction factor."""
    grids = np.indices(shape)
    inputs_any_one = grids[:-1].any(axis=0)
    conclusion = grids[-1].astype(bool)
    return np.where(conclusion == inputs_any_one, _HIGH, _LOW).astype(np.float64), axes


def _equivalence_tensor(_f: Factor, axes: list[str], shape: tuple[int, ...]) -> StrategyCpt:
    """Build the tensor for an equivalence factor."""
    grids = np.indices(shape)
    target = grids[0] == grids[1]
    return np.where(grids[2].astype(bool) == target, _HIGH, _LOW).astype(np.float64), axes


def _contradiction_tensor(_f: Factor, axes: list[str], shape: tuple[int, ...]) -> StrategyCpt:
    """Build the tensor for a contradiction factor."""
    grids = np.indices(shape)
    target = ~((grids[0] == 1) & (grids[1] == 1))
    return np.where(grids[2].astype(bool) == target, _HIGH, _LOW).astype(np.float64), axes


def _negation_tensor(_f: Factor, axes: list[str], shape: tuple[int, ...]) -> StrategyCpt:
    """Build the tensor for a negation factor."""
    grids = np.indices(shape)
    target = grids[0] == 0
    return np.where(grids[1].astype(bool) == target, _HIGH, _LOW).astype(np.float64), axes


def _complement_tensor(_f: Factor, axes: list[str], shape: tuple[int, ...]) -> StrategyCpt:
    """Build the tensor for a complement factor."""
    grids = np.indices(shape)
    target = grids[0] != grids[1]
    return np.where(grids[2].astype(bool) == target, _HIGH, _LOW).astype(np.float64), axes


def _soft_entailment_tensor(f: Factor, axes: list[str], shape: tuple[int, ...]) -> StrategyCpt:
    """Build the tensor for a soft-entailment factor."""
    if f.p1 is None or f.p2 is None:
        raise ValueError(f"SOFT_ENTAILMENT {f.factor_id!r} missing p1/p2")
    t = np.empty(shape, dtype=np.float64)
    t[0, 0] = f.p2
    t[0, 1] = 1.0 - f.p2
    t[1, 0] = 1.0 - f.p1
    t[1, 1] = f.p1
    return t, axes


def _conditional_tensor(f: Factor, axes: list[str], shape: tuple[int, ...]) -> StrategyCpt:
    """Build the tensor for a full conditional CPT."""
    if f.cpt is None:
        raise ValueError(f"CONDITIONAL {f.factor_id!r} missing cpt")
    k = len(f.variables)
    expected = 1 << k
    if len(f.cpt) != expected:
        raise ValueError(f"CONDITIONAL {f.factor_id!r}: cpt length {len(f.cpt)} != 2^k={expected}")
    cpt_arr = np.asarray(f.cpt, dtype=np.float64)
    grids = np.indices(shape)
    prem_idx = np.zeros(shape, dtype=np.int64)
    for bit in range(k):
        prem_idx |= grids[bit].astype(np.int64) << bit
    p = cpt_arr[prem_idx]
    conclusion = grids[-1]
    return np.where(conclusion == 1, p, 1.0 - p), axes


def _deductive_implication_tensor(
    _f: Factor, axes: list[str], shape: tuple[int, ...]
) -> StrategyCpt:
    """Build normalized hard deduction tensor: P(B|A), MaxEnt for ¬A."""
    grids = np.indices(shape)
    antecedent = grids[0]
    conclusion = grids[1]
    return np.where(
        antecedent == 1,
        np.where(conclusion == 1, _HIGH, _LOW),
        0.5,
    ).astype(np.float64), axes


def _pairwise_tensor(f: Factor, axes: list[str], _shape: tuple[int, ...]) -> StrategyCpt:
    """Build the tensor for a pairwise potential."""
    if f.cpt is None:
        raise ValueError(f"PAIRWISE_POTENTIAL {f.factor_id!r} missing cpt")
    if len(f.cpt) != 4:
        raise ValueError(f"PAIRWISE_POTENTIAL {f.factor_id!r}: cpt length {len(f.cpt)} != 4")
    return np.asarray(f.cpt, dtype=np.float64).reshape((2, 2), order="F"), axes


_TENSOR_BUILDERS: dict[FactorType, TensorBuilder] = {
    FactorType.IMPLICATION: _implication_tensor,
    FactorType.CONJUNCTION: _conjunction_tensor,
    FactorType.DISJUNCTION: _disjunction_tensor,
    FactorType.EQUIVALENCE: _equivalence_tensor,
    FactorType.CONTRADICTION: _contradiction_tensor,
    FactorType.NEGATION: _negation_tensor,
    FactorType.COMPLEMENT: _complement_tensor,
    FactorType.SOFT_ENTAILMENT: _soft_entailment_tensor,
    FactorType.CONDITIONAL: _conditional_tensor,
    FactorType.PAIRWISE_POTENTIAL: _pairwise_tensor,
    FactorType.DEDUCTIVE_IMPLICATION: _deductive_implication_tensor,
}


def factor_to_tensor(f: Factor) -> StrategyCpt:
    """Build a dense tensor representation of a Factor.

    Shape: ``(2,) * (len(f.variables) + 1)``.
    Axis order: ``f.variables`` in order, then ``f.conclusion``.

    Deterministic factors use strict ``_HIGH``/``_LOW`` values (1.0 / 0.0) so
    they match the semantics of ``gaia.engine.bp.potentials`` exactly.
    Parametric factors (SOFT_ENTAILMENT, CONDITIONAL) use their stored
    parameters.
    """
    axes = [*f.variables, f.conclusion]
    shape = (2,) * len(axes)
    try:
        builder = _TENSOR_BUILDERS[f.factor_type]
    except KeyError as err:
        raise ValueError(f"Unknown FactorType: {f.factor_type!r}") from err
    return builder(f, axes, shape)


def _collect_tensor_variables(tensors: list[StrategyCpt]) -> list[str]:
    """Collect distinct tensor variable names in first-seen order."""
    all_vars: list[str] = []
    seen: set[str] = set()
    for _, axes in tensors:
        for variable in axes:
            if variable not in seen:
                seen.add(variable)
                all_vars.append(variable)
    return all_vars


def _build_contract_operands(
    tensors: list[StrategyCpt],
    free_vars: list[str],
    unary_priors: dict[str, float],
) -> tuple[list[np.ndarray], list[list[str]], list[str]]:
    """Build factor, unary, and degenerate operands for contraction."""
    all_vars = _collect_tensor_variables(tensors)
    seen = set(all_vars)
    free_set = set(free_vars)

    operands: list[np.ndarray] = []
    operand_axes: list[list[str]] = []
    for tensor, axes in tensors:
        operands.append(np.asarray(tensor, dtype=np.float64))
        operand_axes.append(list(axes))

    for variable in all_vars:
        if variable in free_set:
            continue
        if variable in unary_priors:
            pi = unary_priors[variable]
            operands.append(np.array([1.0 - pi, pi], dtype=np.float64))
            operand_axes.append([variable])

    for variable in free_vars:
        if variable not in seen:
            operands.append(np.array([0.5, 0.5], dtype=np.float64))
            operand_axes.append([variable])
            seen.add(variable)
            all_vars.append(variable)

    return operands, operand_axes, all_vars


def _build_contract_args(
    operands: list[np.ndarray],
    operand_axes: list[list[str]],
    all_vars: list[str],
    free_vars: list[str],
) -> list[object]:
    """Build opt_einsum's alternating operand/index argument list."""
    var_to_idx = {variable: index for index, variable in enumerate(all_vars)}
    args: list[object] = []
    for operand, axes in zip(operands, operand_axes, strict=True):
        args.append(operand)
        args.append([var_to_idx[variable] for variable in axes])
    args.append([var_to_idx[variable] for variable in free_vars])
    return args


def _ascii_einsum_subscripts(einsum_str: str) -> str:
    """Remap opt_einsum's non-ASCII symbols to numpy-compatible ASCII."""
    special = [char for char in dict.fromkeys(einsum_str) if char not in "->,"]
    if not any(ord(char) > 127 for char in special):
        return einsum_str
    ascii52 = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
    mapping = {char: ascii52[index] for index, char in enumerate(special)}
    return "".join(mapping.get(char, char) for char in einsum_str)


def _execute_contract_path(operands: list[np.ndarray], path_info: Any) -> np.ndarray:
    """Execute opt_einsum's pairwise contraction path with per-step rescaling."""
    working: list[np.ndarray] = list(operands)
    for step in path_info.contraction_list:
        inds = step[0]
        einsum_str = _ascii_einsum_subscripts(step[2])
        popped = [working[index] for index in inds]
        for index in sorted(inds, reverse=True):
            working.pop(index)

        result = np.einsum(einsum_str, *popped)
        max_value = float(result.max())
        if max_value > 0:
            result = result / max_value

        working.append(result)

    return working[0]


def _normalize_contracted_joint(joint: np.ndarray) -> FloatArray:
    """Normalize a contracted joint along the conclusion axis."""
    totals = joint.sum(axis=-1, keepdims=True)
    if np.any(totals <= 0):
        raise ValueError(
            "contract_to_cpt: zero partition function encountered; "
            "graph may have contradictory deterministic factors."
        )
    return _float_array(joint / totals)


def contract_to_cpt(
    tensors: list[StrategyCpt],
    free_vars: list[str],
    unary_priors: dict[str, float],
) -> FloatArray:
    """Contract a list of factor tensors down to a conditional CPT tensor.

    Uses ``opt_einsum.contract_path`` to plan an optimal contraction order,
    then executes each pairwise step manually with per-step rescaling.
    Rescaling divides each intermediate tensor by its max, keeping values in
    ``[0, 1]`` and preventing raw-float64 underflow on deep graphs.  The
    final CPT is a ratio (``joint / sum_along_conclusion``), so rescaling
    intermediates by any positive constant preserves the result exactly.

    Because each pairwise step involves at most two operands whose combined
    axes are small, ``numpy.einsum`` has no trouble with the 52-symbol
    alphabet at any individual step — even when the global variable count
    exceeds 52.

    Args:
    tensors:
        List of ``(ndarray, axis_var_ids)`` pairs.  The ndarray has one axis
        per name in ``axis_var_ids`` (in order); each axis has size 2.
    free_vars:
        Variables that remain as axes in the output, in output order.
        Typically ``[*premises, conclusion]``.  The last entry is the
        conclusion and is the axis along which the output is normalized.
        A free variable that does not appear in any input tensor is handled
        as a degenerate constant axis (uniform contribution).
    unary_priors:
        Explicit unary factors ``[1-π, π]`` to apply to marginalized variables.
        Non-free variables omitted from this mapping are summed with the base
        counting measure, not assigned an implicit ``π=0.5`` prior.

    Returns:
        ndarray of shape ``(2,) * len(free_vars)`` giving
        ``P(conclusion | premises)``. The last axis is normalized so that
        ``T[..., 0] + T[..., 1] == 1``.

    Raises:
        ValueError: If ``free_vars`` is empty, or if the normalized joint is
            zero for some premise assignment even after per-step rescaling
            (indicates contradictory deterministic factors).
    """
    import opt_einsum as oe

    if not free_vars:
        raise ValueError("free_vars must be non-empty (need at least a conclusion axis)")

    # Build the full operand list:
    #   1) Original factor tensors
    #   2) Explicit unary-factor tensors for non-free variables
    #   3) Degenerate uniform tensors for free variables not in any input
    #      (legitimate case: CompositeStrategy with unused interface premises)
    operands, operand_axes, all_vars = _build_contract_operands(tensors, free_vars, unary_priors)
    args = _build_contract_args(operands, operand_axes, all_vars, free_vars)

    # Let opt_einsum plan an optimal contraction order.  ``contract_path``
    # returns ``(path, PathInfo)`` where ``PathInfo.contraction_list`` has
    # the per-step subscript strings we need to execute ourselves.
    _, path_info = oe.contract_path(*args, optimize="greedy")

    # Execute the path step by step.  Each step contracts exactly two
    # operands via a small np.einsum call (well within the 52-symbol
    # alphabet) and the result is rescaled to prevent underflow.
    joint = _execute_contract_path(operands, path_info)
    return _normalize_contracted_joint(joint)


def cpt_tensor_to_list(
    tensor: FloatArray,
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
        idx = (*(((assignment >> bit) & 1) for bit in range(k)), 1)
        out.append(float(t[idx]))
    return out


def strategy_cpt(
    s: Strategy,
    strat_by_id: dict[str, Strategy],
    strat_params: dict[str, list[float]],
    var_priors: dict[str, float],
    namespace: str,
    package_name: str,
    cache: dict[str, StrategyCptCacheValue],
) -> StrategyCpt:
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
    explicit unary factors on claim variables (e.g., when called from
    ``compute_coarse_cpts`` with the global factor graph's unary factors).
    Pass ``{}`` for isolated composite folding.

    Note:
        The ``cache`` is keyed by ``s.strategy_id``, which encodes
        ``(scope, type, premises, conclusion)``.  It does NOT encode
        ``var_priors`` or ``strat_params``.  Callers MUST pass a fresh
        ``cache`` dict for each top-level invocation; reusing a cache
        across calls with different unary factors or strat_params will return
        stale results for ``FormalStrategy`` and auto-formalized leaves
        whose internal helper claims have non-default priors.
    """
    from gaia.engine.bp.factor_graph import FactorGraph
    from gaia.engine.bp.lowering import _lower_strategy
    from gaia.engine.ir.strategy import CompositeStrategy

    if s.strategy_id is None:
        raise ValueError("strategy_cpt requires a strategy_id")
    if s.conclusion is None:
        raise ValueError(f"strategy_cpt requires a conclusion for {s.strategy_id!r}")
    strategy_id = s.strategy_id
    conclusion = s.conclusion

    cached = cache.get(strategy_id)
    if isinstance(cached, _InProgress):
        raise ValueError(
            f"strategy_cpt: cycle detected — strategy_id {strategy_id!r} "
            "is its own ancestor in the composite recursion."
        )
    if cached is not None:
        return cached

    if isinstance(s, CompositeStrategy):
        # Mark this composite as in-progress so recursive calls detect cycles.
        cache[strategy_id] = _IN_PROGRESS
        child_tensors: list[StrategyCpt] = []
        for sid in s.sub_strategies:
            sub = strat_by_id.get(sid)
            if sub is None:
                raise KeyError(
                    f"CompositeStrategy {strategy_id!r} references missing strategy_id {sid!r}"
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

        free = [*s.premises, conclusion]
        free_set = set(free)

        # Bridge variables: any child axis that isn't a composite free var.
        # Only explicit unary factors are applied at this layer. Internal
        # helper claims marginalized inside a child's CPT do NOT appear in any
        # child's axes and are correctly skipped here.
        bridges: dict[str, float] = {}
        for _, axes in child_tensors:
            for v in axes:
                if v not in free_set and v in var_priors and v not in bridges:
                    bridges[v] = var_priors[v]

        cpt_tensor = contract_to_cpt(child_tensors, free_vars=free, unary_priors=bridges)
        result = (cpt_tensor, free)
        cache[strategy_id] = result
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
        {},
        expand_formal=True,
        infer_degraded=False,
        ctr=ctr,
        claim_ids=claim_ids,
        namespace=namespace,
        package_name=package_name,
    )

    tensors = [factor_to_tensor(f) for f in mini.factors]
    free = [*s.premises, conclusion]
    free_set = set(free)
    # Explicit unary factors for variables in the mini fg that are NOT free axes.
    non_free = {v: p for v, p in mini.unary_factors.items() if v not in free_set}

    cpt_tensor = contract_to_cpt(tensors, free_vars=free, unary_priors=non_free)
    result = (cpt_tensor, free)
    cache[strategy_id] = result
    return result
