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
        coarse_strategies.append({
            "type": "infer",
            "premises": sorted(premises),
            "conclusion": conc,
            "reason": "",
        })

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
