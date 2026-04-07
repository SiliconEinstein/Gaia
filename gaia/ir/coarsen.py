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
    """Compute effective CPTs for coarse infer strategies by marginalization.

    For each coarse strategy, clamp its premises to all 2^k assignments
    and run BP on the **full** factor graph to get P(conclusion=1 | assignment).

    Optimization: the factor graph is built once per strategy; only premise
    priors are updated between assignments.

    Returns a dict mapping strategy index to CPT (list of 2^k floats).
    """
    from gaia.bp.bp import BeliefPropagation
    from gaia.bp.lowering import lower_local_graph
    from gaia.ir.graphs import LocalCanonicalGraph

    CLAMP_HI = 1.0 - 1e-6
    CLAMP_LO = 1e-6

    priors = dict(node_priors or {})
    strat_params = dict(strategy_params or {})
    indices = (
        strategy_indices if strategy_indices is not None else set(range(len(coarse["strategies"])))
    )

    # Build the canonical graph once (shared across all strategies)
    canon = LocalCanonicalGraph(
        **{
            key: ir[key]
            for key in ("knowledges", "strategies", "operators", "namespace", "package_name")
        }
    )

    result: dict[int, list[float]] = {}

    for i, s in enumerate(coarse["strategies"]):
        if i not in indices:
            continue
        premises = s["premises"]
        conclusion = s["conclusion"]
        k = len(premises)
        cpt: list[float] = []

        for assignment in range(1 << k):
            # Clamp premise priors for this assignment
            clamped = dict(priors)
            for bit, pid in enumerate(premises):
                clamped[pid] = CLAMP_HI if (assignment >> bit) & 1 else CLAMP_LO

            # Build factor graph with clamped priors and run BP
            fg = lower_local_graph(
                canon,
                node_priors=clamped,
                strategy_conditional_params=strat_params,
            )
            bp = BeliefPropagation(damping=0.5, max_iterations=200)
            bp_result = bp.run(fg)
            cpt.append(bp_result.beliefs.get(conclusion, 0.5))

        result[i] = cpt

    return result
