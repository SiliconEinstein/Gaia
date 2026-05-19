"""Generate graph.json for interactive visualization (v2).

Strategy and operator entries are promoted to intermediate nodes.
Edges carry a ``role`` field (premise/background/conclusion/variable).
Top-level ``modules`` and ``cross_module_edges`` arrays are computed.
"""

from __future__ import annotations

import json
from collections import Counter
from typing import Any

from gaia.engine.ir.coarsen import HELPER_LABEL_PREFIXES


def _beliefs_from_payload(beliefs_data: dict[str, Any] | None) -> dict[str, float]:
    """Extract graph belief values from an optional beliefs payload."""
    if not beliefs_data:
        return {}
    return {b["knowledge_id"]: b["belief"] for b in beliefs_data.get("beliefs", [])}


def _priors_from_payload(param_data: dict[str, Any] | None) -> dict[str, float]:
    """Extract graph prior values from an optional parameterization payload."""
    if not param_data:
        return {}
    return {p["knowledge_id"]: p["value"] for p in param_data.get("priors", [])}


def _knowledge_modules(ir: dict[str, Any]) -> dict[str, str]:
    """Return knowledge-id to module mappings for nodes with a module."""
    return {
        k["id"]: k["module"] for k in ir.get("knowledges", []) if k.get("id") and k.get("module")
    }


def _knowledge_nodes(
    ir: dict[str, Any],
    *,
    beliefs: dict[str, float],
    priors: dict[str, float],
    exported: set[str],
) -> list[dict[str, Any]]:
    """Build visible knowledge nodes for graph.json."""
    nodes: list[dict[str, Any]] = []
    for k in ir["knowledges"]:
        label = k.get("label", "")
        if label.startswith(HELPER_LABEL_PREFIXES):
            # `__` dunder helpers (operator conclusions like
            # `__implication_result`) and `_anon_<NNN>` compiler-minted
            # labels are not authored by the user; drop them from the
            # visualization layer (graph.json → starmap, etc.).
            # Prefix set sourced from gaia.engine.ir.coarsen so the
            # helper-label naming convention has a single source of truth.
            continue
        kid = k["id"]
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
    return nodes


def _append_strategy_graph(
    ir: dict[str, Any],
    *,
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    kid_module: dict[str, str],
) -> tuple[Counter[str], Counter[tuple[str, str]]]:
    """Append strategy nodes/edges and return module counters."""
    strategy_counts: Counter[str] = Counter()
    cross_module: Counter[tuple[str, str]] = Counter()
    for i, s in enumerate(ir.get("strategies", [])):
        conc = s.get("conclusion")
        if not conc:
            continue
        conc_mod = kid_module.get(conc, "")
        strat_id = f"strat_{i}"
        nodes.append(
            {
                "id": strat_id,
                "type": "strategy",
                "strategy_type": s.get("type", ""),
                "module": conc_mod,
                "reason": s.get("reason", ""),
            }
        )
        strategy_counts[conc_mod] += 1
        _append_strategy_edges(s, strat_id, conc, conc_mod, edges, kid_module, cross_module)
    return strategy_counts, cross_module


def _append_strategy_edges(
    strategy: dict[str, Any],
    strat_id: str,
    conc: str,
    conc_mod: str,
    edges: list[dict[str, Any]],
    kid_module: dict[str, str],
    cross_module: Counter[tuple[str, str]],
) -> None:
    """Append premise/background/conclusion edges for one strategy."""
    for p in strategy.get("premises", []):
        edges.append({"source": p, "target": strat_id, "role": "premise"})
        p_mod = kid_module.get(p, "")
        if p_mod and conc_mod and p_mod != conc_mod:
            cross_module[(p_mod, conc_mod)] += 1
    for bg in strategy.get("background", []):
        edges.append({"source": bg, "target": strat_id, "role": "background"})
    edges.append({"source": strat_id, "target": conc, "role": "conclusion"})


def _append_operator_graph(
    ir: dict[str, Any],
    *,
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    kid_module: dict[str, str],
) -> None:
    """Append operator nodes and edges for graph.json."""
    for i, o in enumerate(ir.get("operators", [])):
        conc = o.get("conclusion")
        oper_id = f"oper_{i}"
        nodes.append(
            {
                "id": oper_id,
                "type": "operator",
                "operator_type": o.get("operator", ""),
                "module": kid_module.get(conc, "") if conc else "",
            }
        )
        for v in o.get("variables", []):
            edges.append({"source": v, "target": oper_id, "role": "variable"})
        if conc:
            edges.append({"source": oper_id, "target": conc, "role": "conclusion"})


def _module_entries(
    *,
    nodes: list[dict[str, Any]],
    module_order: list[str],
    strategy_counts: Counter[str],
) -> list[dict[str, Any]]:
    """Build graph.json module entries preserving explicit module order first."""
    module_node_counts: Counter[str] = Counter()
    for node in nodes:
        mod = node.get("module")
        if mod and node["type"] not in ("strategy", "operator"):
            module_node_counts[mod] += 1

    seen = set(module_order)
    all_mods = list(module_order)
    all_mods.extend(mod for mod in sorted(module_node_counts.keys()) if mod not in seen)
    return [
        {
            "id": mod,
            "order": idx,
            "node_count": module_node_counts.get(mod, 0),
            "strategy_count": strategy_counts.get(mod, 0),
        }
        for idx, mod in enumerate(all_mods)
        if module_node_counts.get(mod, 0) > 0 or strategy_counts.get(mod, 0) > 0
    ]


def generate_graph_json(
    ir: dict[str, Any],
    beliefs_data: dict[str, Any] | None = None,
    param_data: dict[str, Any] | None = None,
    exported_ids: set[str] | None = None,
) -> str:
    """Return JSON string with nodes, edges, modules, and cross_module_edges."""
    beliefs = _beliefs_from_payload(beliefs_data)
    priors = _priors_from_payload(param_data)
    exported = exported_ids or set()

    kid_module = _knowledge_modules(ir)
    module_order: list[str] = ir.get("module_order", [])

    nodes = _knowledge_nodes(ir, beliefs=beliefs, priors=priors, exported=exported)
    edges: list[dict[str, Any]] = []
    strategy_counts, cross_module = _append_strategy_graph(
        ir,
        nodes=nodes,
        edges=edges,
        kid_module=kid_module,
    )
    _append_operator_graph(ir, nodes=nodes, edges=edges, kid_module=kid_module)

    modules = _module_entries(
        nodes=nodes,
        module_order=module_order,
        strategy_counts=strategy_counts,
    )

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
