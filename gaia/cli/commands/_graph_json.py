"""Generate graph.json for interactive visualization."""

from __future__ import annotations

import json


def generate_graph_json(
    ir: dict,
    beliefs_data: dict | None = None,
    param_data: dict | None = None,
    exported_ids: set[str] | None = None,
) -> str:
    """Generate JSON with nodes and edges for Cytoscape.js visualization."""
    beliefs: dict[str, float] = {}
    if beliefs_data:
        beliefs = {b["knowledge_id"]: b["belief"] for b in beliefs_data.get("beliefs", [])}
    priors: dict[str, float] = {}
    if param_data:
        priors = {p["knowledge_id"]: p["value"] for p in param_data.get("priors", [])}
    exported = exported_ids or set()

    nodes = []
    for k in ir["knowledges"]:
        kid = k["id"]
        label = k.get("label", "")
        if label.startswith("__"):
            continue
        nodes.append(
            {
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
            }
        )

    edges = []
    for s in ir.get("strategies", []):
        conc = s.get("conclusion")
        if not conc:
            continue
        for p in s.get("premises", []):
            edges.append(
                {
                    "source": p,
                    "target": conc,
                    "type": "strategy",
                    "strategy_type": s.get("type", ""),
                    "reason": s.get("reason", ""),
                }
            )
    for o in ir.get("operators", []):
        conc = o.get("conclusion")
        for v in o.get("variables", []):
            edges.append(
                {
                    "source": v,
                    "target": conc or v,
                    "type": "operator",
                    "operator_type": o.get("operator", ""),
                    "reason": o.get("reason", ""),
                }
            )

    return json.dumps({"nodes": nodes, "edges": edges}, indent=2, ensure_ascii=False)
