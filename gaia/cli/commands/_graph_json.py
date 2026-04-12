"""Generate graph.json for interactive visualization (v2).

Strategy and operator entries are promoted to intermediate nodes.
Edges carry a ``role`` field (premise/background/conclusion/variable).
Top-level ``modules`` and ``cross_module_edges`` arrays are computed.
"""

from __future__ import annotations

import json
from collections import Counter


def generate_graph_json(
    ir: dict,
    beliefs_data: dict | None = None,
    param_data: dict | None = None,
    exported_ids: set[str] | None = None,
) -> str:
    """Return JSON string with nodes, edges, modules, and cross_module_edges."""
    beliefs: dict[str, float] = {}
    if beliefs_data:
        beliefs = {b["knowledge_id"]: b["belief"] for b in beliefs_data.get("beliefs", [])}
    priors: dict[str, float] = {}
    if param_data:
        priors = {p["knowledge_id"]: p["value"] for p in param_data.get("priors", [])}
    exported = exported_ids or set()

    kid_module: dict[str, str] = {}
    for k in ir.get("knowledges", []):
        if k.get("module"):
            kid_module[k["id"]] = k["module"]

    module_order: list[str] = ir.get("module_order", [])

    nodes: list[dict] = []
    for k in ir["knowledges"]:
        label = k.get("label", "")
        if label.startswith("__"):
            continue
        kid = k["id"]
        nodes.append({
            "id": kid,
            "label": label,
            "title": k.get("title"),
            "type": k["type"],
            "module": k.get("module"),
            "content": k.get("content", ""),
            "prior": priors.get(kid),
            "belief": beliefs.get(kid),
            "exported": kid in exported,
            "metadata": k.get("metadata", {}),
        })

    edges: list[dict] = []
    strategy_counts: Counter[str] = Counter()
    cross_module: Counter[tuple[str, str]] = Counter()

    for i, s in enumerate(ir.get("strategies", [])):
        conc = s.get("conclusion")
        if not conc:
            continue
        conc_mod = kid_module.get(conc, "")
        strat_id = f"strat_{i}"

        nodes.append({
            "id": strat_id,
            "type": "strategy",
            "strategy_type": s.get("type", ""),
            "module": conc_mod,
            "reason": s.get("reason", ""),
        })
        strategy_counts[conc_mod] += 1

        for p in s.get("premises", []):
            edges.append({"source": p, "target": strat_id, "role": "premise"})
            p_mod = kid_module.get(p, "")
            if p_mod and conc_mod and p_mod != conc_mod:
                cross_module[(p_mod, conc_mod)] += 1
        for bg in s.get("background", []):
            edges.append({"source": bg, "target": strat_id, "role": "background"})
        edges.append({"source": strat_id, "target": conc, "role": "conclusion"})

    for i, o in enumerate(ir.get("operators", [])):
        conc = o.get("conclusion")
        oper_id = f"oper_{i}"
        conc_mod = kid_module.get(conc, "") if conc else ""

        nodes.append({
            "id": oper_id,
            "type": "operator",
            "operator_type": o.get("operator", ""),
            "module": conc_mod,
        })

        for v in o.get("variables", []):
            edges.append({"source": v, "target": oper_id, "role": "variable"})
        if conc:
            edges.append({"source": oper_id, "target": conc, "role": "conclusion"})

    module_node_counts: Counter[str] = Counter()
    for n in nodes:
        mod = n.get("module")
        if mod and n["type"] not in ("strategy", "operator"):
            module_node_counts[mod] += 1

    seen = set(module_order)
    all_mods = list(module_order)
    for mod in sorted(module_node_counts.keys()):
        if mod not in seen:
            all_mods.append(mod)

    modules = [
        {
            "id": mod,
            "order": idx,
            "node_count": module_node_counts.get(mod, 0),
            "strategy_count": strategy_counts.get(mod, 0),
        }
        for idx, mod in enumerate(all_mods)
        if module_node_counts.get(mod, 0) > 0 or strategy_counts.get(mod, 0) > 0
    ]

    cross_module_edges = [
        {"from_module": fm, "to_module": tm, "count": cnt}
        for (fm, tm), cnt in sorted(cross_module.items())
    ]

    return json.dumps(
        {
            "modules": modules,
            "cross_module_edges": cross_module_edges,
            "nodes": nodes,
            "edges": edges,
        },
        indent=2,
        ensure_ascii=False,
    )
