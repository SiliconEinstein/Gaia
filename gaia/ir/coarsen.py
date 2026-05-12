"""Coarsen a Gaia IR to show only leaf premises → exported conclusions.

All intermediate nodes are folded away. Each multi-hop reasoning chain
becomes a single ``infer`` edge connecting a leaf premise to an exported
conclusion it supports (directly or transitively).
"""

from __future__ import annotations

from typing import Any

_HELPER_LABEL_PREFIXES = ("__", "_anon")


def coarsen_ir(ir: dict[str, Any], exported_ids: set[str]) -> dict[str, Any]:
    """Produce a coarse-grained IR with leaf premises and exported conclusions.

    Args:
        ir: Full compiled IR dict with knowledges, strategies, operators.
        exported_ids: Set of knowledge IDs that are exported conclusions.

    Returns:
        A new IR dict (same schema) containing only leaf premises + exported
        conclusions, connected by ``infer`` strategies representing transitive
        reasoning chains.
    """
    knowledge_labels = _knowledge_labels(ir)
    leaf_ids = _leaf_ids(ir, knowledge_labels)
    forward = _build_forward_adjacency(ir)

    edges = _coarse_edges(leaf_ids, exported_ids, forward)
    leaf_ids |= _add_orphan_surrogate_edges(ir, exported_ids, forward, edges)
    unique_edges = sorted(set(edges))

    connected_leaves = {src for src, _ in unique_edges}
    connected_exports = {dst for _, dst in unique_edges}
    keep_ids = connected_leaves | connected_exports
    coarse_knowledges = _coarse_knowledges(ir, keep_ids)
    coarse_strategies = _coarse_strategies(unique_edges)
    coarse_operators = _coarse_operators(ir, keep_ids, coarse_knowledges)

    return {
        "package_name": ir.get("package_name", ""),
        "namespace": ir.get("namespace", ""),
        "knowledges": coarse_knowledges,
        "strategies": coarse_strategies,
        "operators": coarse_operators,
    }


def _is_helper_label(label: str) -> bool:
    return label.startswith(_HELPER_LABEL_PREFIXES)


def _knowledge_labels(ir: dict[str, Any]) -> dict[str, str]:
    return {k["id"]: k.get("label") or "" for k in ir["knowledges"]}


def _knowledge_types(ir: dict[str, Any]) -> dict[str, str]:
    return {k["id"]: k.get("type", "") for k in ir["knowledges"]}


def _concluded_ids(ir: dict[str, Any]) -> set[str]:
    strat_conclusions = {s["conclusion"] for s in ir["strategies"] if s.get("conclusion")}
    op_conclusions = {o["conclusion"] for o in ir["operators"] if o.get("conclusion")}
    return strat_conclusions | op_conclusions


def _leaf_ids(ir: dict[str, Any], knowledge_labels: dict[str, str]) -> set[str]:
    all_concluded = _concluded_ids(ir)
    leaf_ids = {
        k["id"]
        for k in ir["knowledges"]
        if not _is_helper_label(k.get("label") or "")
        and k["id"] not in all_concluded
        and k["type"] == "claim"
    }
    leaf_ids.update(_induction_interface_premises(ir, knowledge_labels))
    return leaf_ids


def _induction_interface_premises(
    ir: dict[str, Any],
    knowledge_labels: dict[str, str],
) -> set[str]:
    premises: set[str] = set()
    for strategy in ir["strategies"]:
        if strategy.get("type") != "induction":
            continue
        conclusion = strategy.get("conclusion")
        if not conclusion:
            continue
        for premise in strategy.get("premises", []):
            if premise != conclusion and not _is_helper_label(knowledge_labels.get(premise, "")):
                premises.add(premise)
    return premises


def _build_forward_adjacency(ir: dict[str, Any]) -> dict[str, set[str]]:
    forward: dict[str, set[str]] = {}
    for strategy in ir["strategies"]:
        _add_adjacency_edges(forward, strategy.get("premises", []), strategy.get("conclusion"))
    for operator in ir["operators"]:
        _add_adjacency_edges(forward, operator.get("variables", []), operator.get("conclusion"))
    return forward


def _build_reverse_adjacency(ir: dict[str, Any]) -> dict[str, set[str]]:
    reverse: dict[str, set[str]] = {}
    for strategy in ir["strategies"]:
        _add_reverse_edges(reverse, strategy.get("conclusion"), strategy.get("premises", []))
    for operator in ir["operators"]:
        _add_reverse_edges(reverse, operator.get("conclusion"), operator.get("variables", []))
    return reverse


def _add_adjacency_edges(
    adjacency: dict[str, set[str]],
    sources: list[str],
    conclusion: str | None,
) -> None:
    if not conclusion:
        return
    for source in sources:
        adjacency.setdefault(source, set()).add(conclusion)


def _add_reverse_edges(
    reverse: dict[str, set[str]],
    conclusion: str | None,
    sources: list[str],
) -> None:
    if not conclusion:
        return
    for source in sources:
        reverse.setdefault(conclusion, set()).add(source)


def _coarse_edges(
    leaf_ids: set[str],
    exported_ids: set[str],
    forward: dict[str, set[str]],
) -> list[tuple[str, str]]:
    edges = _reachable_export_edges(leaf_ids, exported_ids, forward)
    for exported_id in exported_ids:
        starts = forward.get(exported_id, set())
        edges.extend(
            _reachable_export_edges(
                {exported_id},
                exported_ids,
                forward,
                starts=starts,
                include_self_export=True,
            )
        )
    return edges


def _reachable_export_edges(
    source_ids: set[str],
    exported_ids: set[str],
    forward: dict[str, set[str]],
    *,
    starts: set[str] | None = None,
    include_self_export: bool = False,
) -> list[tuple[str, str]]:
    edges: list[tuple[str, str]] = []
    for source_id in source_ids:
        queue = list(starts) if starts is not None else [source_id]
        visited: set[str] = set()
        while queue:
            node = queue.pop(0)
            if node in visited:
                continue
            visited.add(node)
            if (include_self_export or node != source_id) and node in exported_ids:
                edges.append((source_id, node))
                continue
            queue.extend(neighbor for neighbor in forward.get(node, []) if neighbor not in visited)
    return edges


def _add_orphan_surrogate_edges(
    ir: dict[str, Any],
    exported_ids: set[str],
    forward: dict[str, set[str]],
    edges: list[tuple[str, str]],
) -> set[str]:
    orphaned_exports = exported_ids - {dst for _, dst in edges}
    if not orphaned_exports:
        return set()

    reverse = _build_reverse_adjacency(ir)
    surrogate_leaves = _surrogate_leaves_for_orphans(
        orphaned_exports,
        reverse,
        _knowledge_labels(ir),
        _knowledge_types(ir),
    )
    edges.extend(_reachable_export_edges(surrogate_leaves, exported_ids, forward))
    return surrogate_leaves


def _surrogate_leaves_for_orphans(
    orphaned_exports: set[str],
    reverse: dict[str, set[str]],
    knowledge_labels: dict[str, str],
    knowledge_types: dict[str, str],
) -> set[str]:
    surrogate_leaves: set[str] = set()
    for orphan in orphaned_exports:
        surrogate_leaves.update(
            _cycle_breaking_leaves(orphan, reverse, knowledge_labels, knowledge_types)
        )
    return surrogate_leaves


def _cycle_breaking_leaves(
    orphan: str,
    reverse: dict[str, set[str]],
    knowledge_labels: dict[str, str],
    knowledge_types: dict[str, str],
) -> set[str]:
    leaves: set[str] = set()
    visited: set[str] = set()
    queue = list(reverse.get(orphan, []))
    while queue:
        node = queue.pop(0)
        if node in visited:
            continue
        visited.add(node)
        queue.extend(
            _next_reverse_nodes(node, reverse, knowledge_labels, knowledge_types, visited, leaves)
        )
    return leaves


def _next_reverse_nodes(
    node: str,
    reverse: dict[str, set[str]],
    knowledge_labels: dict[str, str],
    knowledge_types: dict[str, str],
    visited: set[str],
    leaves: set[str],
) -> list[str]:
    if _is_helper_label(knowledge_labels.get(node, "")):
        return [pred for pred in reverse.get(node, []) if pred not in visited]
    if knowledge_types.get(node) != "claim":
        return []

    preds = reverse.get(node, set())
    non_helper_preds = _non_helper_claim_predecessors(preds, knowledge_labels, knowledge_types)
    if not non_helper_preds or non_helper_preds <= visited:
        leaves.add(node)
        return []
    return [pred for pred in preds if pred not in visited]


def _non_helper_claim_predecessors(
    predecessors: set[str],
    knowledge_labels: dict[str, str],
    knowledge_types: dict[str, str],
) -> set[str]:
    return {
        pred
        for pred in predecessors
        if not _is_helper_label(knowledge_labels.get(pred, ""))
        and knowledge_types.get(pred) == "claim"
    }


def _coarse_knowledges(ir: dict[str, Any], keep_ids: set[str]) -> list[dict[str, Any]]:
    return [knowledge for knowledge in ir["knowledges"] if knowledge["id"] in keep_ids]


def _coarse_strategies(unique_edges: list[tuple[str, str]]) -> list[dict[str, Any]]:
    by_conclusion: dict[str, list[str]] = {}
    for source_id, conclusion_id in unique_edges:
        if source_id != conclusion_id:
            by_conclusion.setdefault(conclusion_id, []).append(source_id)
    return [
        {"type": "infer", "premises": sorted(premises), "conclusion": conclusion, "reason": ""}
        for conclusion, premises in by_conclusion.items()
    ]


def _coarse_operators(
    ir: dict[str, Any],
    keep_ids: set[str],
    coarse_knowledges: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    knowledge_by_id = {knowledge["id"]: knowledge for knowledge in ir["knowledges"]}
    coarse_operators = []
    for operator in ir.get("operators", []):
        all_nodes = _operator_nodes(operator)
        if all_nodes & keep_ids:
            coarse_operators.append(operator)
            _pull_operator_knowledges(all_nodes, keep_ids, coarse_knowledges, knowledge_by_id)
    return coarse_operators


def _operator_nodes(operator: dict[str, Any]) -> set[str]:
    all_nodes = set(operator.get("variables", []))
    if conclusion := operator.get("conclusion"):
        all_nodes.add(conclusion)
    return all_nodes


def _pull_operator_knowledges(
    all_nodes: set[str],
    keep_ids: set[str],
    coarse_knowledges: list[dict[str, Any]],
    knowledge_by_id: dict[str, dict[str, Any]],
) -> None:
    for node_id in all_nodes:
        if node_id in keep_ids:
            continue
        keep_ids.add(node_id)
        knowledge = knowledge_by_id.get(node_id)
        if knowledge and not (knowledge.get("label", "") or "").startswith("__"):
            coarse_knowledges.append(knowledge)


def _binary_entropy(p: float) -> float:
    """H(Bernoulli(p)) in bits."""
    import math

    if p <= 0 or p >= 1:
        return 0.0
    return -(p * math.log2(p) + (1 - p) * math.log2(1 - p))


def mutual_information(
    cpt: list[float],
    premise_priors: list[float],
) -> float:
    """Compute I(premises; conclusion) in bits from a coarse CPT.

    Args:
        cpt: CPT of length 2^k, indexed by binary encoding of premise assignment.
        premise_priors: Prior probability of each premise being true (length k).

    Returns:
        Mutual information in bits.
    """
    k = len(premise_priors)
    assert len(cpt) == (1 << k)

    # P(C=1) marginal and conditional entropy H(C|P)
    p_c1 = 0.0
    h_c_given_p = 0.0

    for assignment in range(1 << k):
        # P(assignment) = product of premise marginals
        p_assignment = 1.0
        for bit in range(k):
            pi = premise_priors[bit]
            if (assignment >> bit) & 1:
                p_assignment *= pi
            else:
                p_assignment *= 1 - pi

        p_c1_given_a = cpt[assignment]
        p_c1 += p_assignment * p_c1_given_a
        h_c_given_p += p_assignment * _binary_entropy(p_c1_given_a)

    h_c = _binary_entropy(p_c1)
    return max(0.0, h_c - h_c_given_p)


def compute_coarse_cpts(
    ir: dict[str, Any],
    coarse: dict[str, Any],
    node_priors: dict[str, float] | None = None,
    strategy_params: dict[str, list[float]] | None = None,
    strategy_indices: set[int] | None = None,
) -> dict[int, list[float]]:
    """Compute effective CPTs for coarse infer strategies via tensor contraction.

    Lowers the canonical graph once, precomputes each IR strategy's effective
    CPT via ``strategy_cpt`` (sharing a cache across coarse strategies), and
    contracts strategy CPTs + operator tensors + unary priors for each coarse
    strategy.  Exact — no BP iterations.

    Returns a dict mapping strategy index to CPT (list of 2^k floats).
    """
    from gaia.bp.contraction import (
        StrategyCptCacheValue,
        contract_to_cpt,
        cpt_tensor_to_list,
        factor_to_tensor,
        strategy_cpt,
    )
    from gaia.bp.factor_graph import Factor
    from gaia.bp.lowering import _OPERATOR_MAP, lower_local_graph
    from gaia.ir.graphs import LocalCanonicalGraph

    priors = dict(node_priors or {})
    strat_params = dict(strategy_params or {})
    indices = (
        strategy_indices if strategy_indices is not None else set(range(len(coarse["strategies"])))
    )

    # Build the canonical graph and lower it once.  The lowered fg carries
    # every variable's prior (including ones set by _lower_strategy for
    # relation-operator conclusions or auto-formalized helper claims).
    canon = LocalCanonicalGraph(
        **{
            key: ir[key]
            for key in ("knowledges", "strategies", "operators", "namespace", "package_name")
        }
    )
    fg = lower_local_graph(
        canon,
        node_priors=priors,
        strategy_conditional_params=strat_params,
    )

    # Build operator tensors directly from canon.operators.  Each operator
    # becomes one factor tensor using the same FactorType mapping as
    # lower_local_graph's operator pass.
    operator_tensors: list[tuple[Any, list[str]]] = []
    for op in canon.operators:
        op_factor = Factor(
            factor_id=f"op_{op.conclusion}",
            factor_type=_OPERATOR_MAP[op.operator],
            variables=list(op.variables),
            conclusion=op.conclusion,
        )
        operator_tensors.append(factor_to_tensor(op_factor))

    # Precompute every IR strategy's effective CPT once, shared cache.
    from gaia.ir.strategy import CompositeStrategy

    strat_by_id = {s.strategy_id: s for s in canon.strategies if s.strategy_id}
    cache: dict[str, StrategyCptCacheValue] = {}
    strategy_tensors: list[tuple[Any, list[str]]] = []
    for s in canon.strategies:
        # CompositeStrategy organizes sub-strategies; its CPT is already a
        # contraction of its children's CPTs.  Including it as a separate
        # tensor would double-count every path through the composite.
        # The children themselves are iterated normally below / above.
        if isinstance(s, CompositeStrategy):
            continue
        sub_tensor, sub_axes = strategy_cpt(
            s,
            strat_by_id=strat_by_id,
            strat_params=strat_params,
            var_priors=fg.unary_factors,
            namespace=canon.namespace,
            package_name=canon.package_name,
            cache=cache,
        )
        strategy_tensors.append((sub_tensor, sub_axes))

    all_tensors = strategy_tensors + operator_tensors

    # Union of all axis labels touched by any tensor.
    all_axes: set[str] = set()
    for _, axes in all_tensors:
        all_axes.update(axes)

    result: dict[int, list[float]] = {}

    for i, s in enumerate(coarse["strategies"]):
        if i not in indices:
            continue
        coarse_premises = list(s["premises"])
        coarse_conclusion = s["conclusion"]
        free = [*coarse_premises, coarse_conclusion]
        if len(free) != len(set(free)):
            raise ValueError(
                f"coarse strategy {i}: conclusion {coarse_conclusion!r} must not also "
                "appear in premises"
            )
        free_set = set(free)

        # Unary priors for every variable that:
        #   - appears in at least one collected tensor's axes
        #   - is not a coarse free variable
        #   - exists in fg.unary_factors (has an explicit unary factor)
        # Helper claims absorbed inside a strategy CPT do NOT appear in
        # all_axes and so are correctly skipped here (their priors were
        # already applied inside the strategy CPT).
        unary_priors = {
            v: fg.unary_factors[v] for v in all_axes if v not in free_set and v in fg.unary_factors
        }

        cpt_tensor = contract_to_cpt(
            all_tensors,
            free_vars=free,
            unary_priors=unary_priors,
        )
        result[i] = cpt_tensor_to_list(cpt_tensor, free, coarse_premises, coarse_conclusion)

    return result
