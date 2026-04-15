"""Coarsen a Gaia IR to show only leaf premises → exported conclusions.

All intermediate nodes are folded away. Each multi-hop reasoning chain
becomes a single ``infer`` edge connecting a leaf premise to an exported
conclusion it supports (directly or transitively).
"""

from __future__ import annotations


def coarsen_ir(ir: dict, exported_ids: set[str]) -> dict:
    """Produce a coarse-grained IR with leaf premises and exported conclusions.

    Parameters
    ----------
    ir:
        Full compiled IR dict with knowledges, strategies, operators.
    exported_ids:
        Set of knowledge IDs that are exported conclusions.

    Returns
    -------
    A new IR dict (same schema) containing only leaf premises + exported
    conclusions, connected by ``infer`` strategies representing transitive
    reasoning chains.
    """
    # 1. Identify all nodes concluded by a strategy or operator
    strat_conclusions = {s["conclusion"] for s in ir["strategies"] if s.get("conclusion")}
    op_conclusions = {o["conclusion"] for o in ir["operators"] if o.get("conclusion")}
    all_concluded = strat_conclusions | op_conclusions

    # 2. Identify leaf premises: claims not concluded by any strategy/operator,
    #    excluding helpers and settings
    leaf_ids: set[str] = set()
    for k in ir["knowledges"]:
        kid = k["id"]
        label = k.get("label", "")
        if label.startswith("__") or label.startswith("_anon"):
            continue
        if kid not in all_concluded and k["type"] == "claim":
            leaf_ids.add(kid)

    # 3. Build forward adjacency: for each node, which conclusions does it
    #    support (as a premise of a strategy or variable of an operator)?
    forward: dict[str, set[str]] = {}
    for s in ir["strategies"]:
        conc = s.get("conclusion")
        if not conc:
            continue
        for p in s.get("premises", []):
            forward.setdefault(p, set()).add(conc)
    for o in ir["operators"]:
        conc = o.get("conclusion")
        if not conc:
            continue
        for v in o.get("variables", []):
            forward.setdefault(v, set()).add(conc)

    # 4. For each leaf premise, BFS forward to find which exported conclusions
    #    it transitively supports. Stop at exported conclusions.
    edges: list[tuple[str, str]] = []
    for leaf in leaf_ids:
        visited: set[str] = set()
        queue = [leaf]
        while queue:
            node = queue.pop(0)
            if node in visited:
                continue
            visited.add(node)
            if node != leaf and node in exported_ids:
                edges.append((leaf, node))
                continue
            for neighbor in forward.get(node, []):
                if neighbor not in visited:
                    queue.append(neighbor)

    # 4b. Also find exported → exported edges (one exported supports another)
    for exp in exported_ids:
        visited: set[str] = set()
        queue = list(forward.get(exp, []))
        while queue:
            node = queue.pop(0)
            if node in visited:
                continue
            visited.add(node)
            if node in exported_ids:
                edges.append((exp, node))
                continue
            for neighbor in forward.get(node, []):
                if neighbor not in visited:
                    queue.append(neighbor)

    # 4c. Handle unreachable exported conclusions.
    # Some exported conclusions have no path from leaf premises — e.g. when
    # induction patterns create cycles (law → obs and obs₁+obs₂ → law) making
    # every node "concluded".  For unreachable exports, reverse-BFS to find the
    # deepest non-helper claims and promote them to surrogate leaf premises.
    connected_exports_so_far = {e[1] for e in edges}
    orphaned_exports = exported_ids - connected_exports_so_far
    if orphaned_exports:
        # Build reverse adjacency: conclusion → premises
        reverse_adj: dict[str, set[str]] = {}
        for s in ir["strategies"]:
            conc = s.get("conclusion")
            if not conc:
                continue
            for p in s.get("premises", []):
                reverse_adj.setdefault(conc, set()).add(p)
        for o in ir["operators"]:
            conc = o.get("conclusion")
            if not conc:
                continue
            for v in o.get("variables", []):
                reverse_adj.setdefault(conc, set()).add(v)

        # For each orphaned export, reverse-BFS to find claims with no further
        # non-helper predecessors — these are "cycle-breaking" leaves.
        kid_labels = {k["id"]: k.get("label", "") for k in ir["knowledges"]}
        kid_types = {k["id"]: k.get("type", "") for k in ir["knowledges"]}
        surrogate_leaves: set[str] = set()

        for orphan in orphaned_exports:
            visited: set[str] = set()
            queue = list(reverse_adj.get(orphan, []))
            while queue:
                node = queue.pop(0)
                if node in visited:
                    continue
                visited.add(node)
                lbl = kid_labels.get(node, "")
                if lbl.startswith("__") or lbl.startswith("_anon"):
                    # Skip helpers, keep searching
                    for pred in reverse_adj.get(node, []):
                        if pred not in visited:
                            queue.append(pred)
                    continue
                if kid_types.get(node) != "claim":
                    continue
                # If this node has no non-helper predecessors, it's a surrogate leaf
                preds = reverse_adj.get(node, set())
                non_helper_preds = {
                    p
                    for p in preds
                    if not kid_labels.get(p, "").startswith("__")
                    and not kid_labels.get(p, "").startswith("_anon")
                    and kid_types.get(p) == "claim"
                }
                if not non_helper_preds:
                    surrogate_leaves.add(node)
                else:
                    # Check if all predecessors are already visited (cycle)
                    if non_helper_preds <= visited:
                        surrogate_leaves.add(node)
                    else:
                        for pred in preds:
                            if pred not in visited:
                                queue.append(pred)

        # Run forward BFS from surrogate leaves
        leaf_ids |= surrogate_leaves
        for leaf in surrogate_leaves:
            visited_fwd: set[str] = set()
            queue_fwd = [leaf]
            while queue_fwd:
                node = queue_fwd.pop(0)
                if node in visited_fwd:
                    continue
                visited_fwd.add(node)
                if node != leaf and node in exported_ids:
                    edges.append((leaf, node))
                    continue
                for neighbor in forward.get(node, []):
                    if neighbor not in visited_fwd:
                        queue_fwd.append(neighbor)

    # 5. Deduplicate edges
    unique_edges = sorted(set(edges))

    # 6. Determine which leaf premises are actually connected to exports
    connected_leaves = {e[0] for e in unique_edges}
    connected_exports = {e[1] for e in unique_edges}

    # 7. Build coarse knowledges (only connected nodes)
    keep_ids = connected_leaves | connected_exports
    coarse_knowledges = []
    for k in ir["knowledges"]:
        if k["id"] in keep_ids:
            coarse_knowledges.append(k)

    # 8. Build coarse strategies (one infer per edge)
    coarse_strategies = []
    by_conclusion: dict[str, list[str]] = {}
    for src, dst in unique_edges:
        by_conclusion.setdefault(dst, []).append(src)

    for conc, premises in by_conclusion.items():
        coarse_strategies.append(
            {
                "type": "infer",
                "premises": sorted(premises),
                "conclusion": conc,
                "reason": "",
            }
        )

    # 9. Preserve operators whose variables/conclusion touch keep_ids.
    #    Also pull in any operator variables not yet in keep_ids so the
    #    constraint renders completely.
    coarse_operators = []
    for o in ir.get("operators", []):
        conc = o.get("conclusion")
        variables = o.get("variables", [])
        all_nodes = set(variables)
        if conc:
            all_nodes.add(conc)
        # Keep operator if at least one endpoint is in keep_ids
        if all_nodes & keep_ids:
            coarse_operators.append(o)
            # Pull in any missing variables/conclusion
            for nid in all_nodes:
                if nid not in keep_ids:
                    keep_ids.add(nid)
                    k = next((k for k in ir["knowledges"] if k["id"] == nid), None)
                    if k and not k.get("label", "").startswith("__"):
                        coarse_knowledges.append(k)

    return {
        "package_name": ir.get("package_name", ""),
        "namespace": ir.get("namespace", ""),
        "knowledges": coarse_knowledges,
        "strategies": coarse_strategies,
        "operators": coarse_operators,
    }


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

    Parameters
    ----------
    cpt:
        CPT of length 2^k, indexed by binary encoding of premise assignment.
    premise_priors:
        Prior probability of each premise being true (length k).

    Returns
    -------
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
    ir: dict,
    coarse: dict,
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
    operator_tensors: list[tuple] = []
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
    cache: dict = {}
    strategy_tensors: list[tuple] = []
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
            var_priors=fg.variables,
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
        free_set = set(free)

        # Unary priors for every variable that:
        #   - appears in at least one collected tensor's axes
        #   - is not a coarse free variable
        #   - exists in fg.variables (has a registered prior)
        # Helper claims absorbed inside a strategy CPT do NOT appear in
        # all_axes and so are correctly skipped here (their priors were
        # already applied inside the strategy CPT).
        unary_priors = {
            v: fg.variables[v] for v in all_axes if v not in free_set and v in fg.variables
        }

        cpt_tensor = contract_to_cpt(
            all_tensors,
            free_vars=free,
            unary_priors=unary_priors,
        )
        result[i] = cpt_tensor_to_list(cpt_tensor, free, coarse_premises, coarse_conclusion)

    return result
