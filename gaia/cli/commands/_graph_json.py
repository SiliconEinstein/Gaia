"""Generate graph.json for interactive visualization (v2).

Strategy and operator entries are promoted to intermediate nodes.
Edges carry a ``role`` field (premise/background/conclusion/variable).
Top-level ``modules`` and ``cross_module_edges`` arrays are computed.
"""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Iterable, Iterator
from pathlib import Path
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


def _iter_knowledge_nodes(
    ir: dict[str, Any],
    *,
    beliefs: dict[str, float],
    priors: dict[str, float],
    exported: set[str],
) -> Iterator[dict[str, Any]]:
    """Yield visible knowledge nodes for graph.json."""
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
        yield {
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


def _strategy_counts_and_cross_module(
    ir: dict[str, Any],
    kid_module: dict[str, str],
) -> tuple[Counter[str], Counter[tuple[str, str]]]:
    """Return strategy and cross-module counters without materializing graph edges."""
    strategy_counts: Counter[str] = Counter()
    cross_module: Counter[tuple[str, str]] = Counter()
    for strategy in ir.get("strategies", []):
        conc = strategy.get("conclusion")
        if not conc:
            continue
        conc_mod = kid_module.get(conc, "")
        strategy_counts[conc_mod] += 1
        for premise in strategy.get("premises", []):
            premise_mod = kid_module.get(premise, "")
            if premise_mod and conc_mod and premise_mod != conc_mod:
                cross_module[(premise_mod, conc_mod)] += 1
    return strategy_counts, cross_module


def _module_entries_from_ir(
    ir: dict[str, Any],
    *,
    module_order: list[str],
    strategy_counts: Counter[str],
) -> list[dict[str, Any]]:
    """Build module entries directly from visible knowledge nodes."""
    module_node_counts: Counter[str] = Counter()
    for knowledge in ir.get("knowledges", []):
        label = knowledge.get("label", "")
        mod = knowledge.get("module")
        if mod and not label.startswith(HELPER_LABEL_PREFIXES):
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


def _graph_context(
    ir: dict[str, Any],
    beliefs_data: dict[str, Any] | None = None,
    param_data: dict[str, Any] | None = None,
    exported_ids: set[str] | None = None,
) -> tuple[
    dict[str, float],
    dict[str, float],
    set[str],
    dict[str, str],
    list[dict[str, Any]],
    list[dict[str, Any]],
]:
    """Build the small graph.json context shared by streaming and string output."""
    beliefs = _beliefs_from_payload(beliefs_data)
    priors = _priors_from_payload(param_data)
    exported = exported_ids or set()
    kid_module = _knowledge_modules(ir)
    module_order: list[str] = list(ir.get("module_order") or [])
    strategy_counts, cross_module = _strategy_counts_and_cross_module(ir, kid_module)
    modules = _module_entries_from_ir(
        ir,
        module_order=module_order,
        strategy_counts=strategy_counts,
    )
    cross_module_edges = [
        {"from_module": fm, "to_module": tm, "count": cnt}
        for (fm, tm), cnt in sorted(cross_module.items())
    ]
    return beliefs, priors, exported, kid_module, modules, cross_module_edges


def _iter_strategy_nodes(
    ir: dict[str, Any], kid_module: dict[str, str]
) -> Iterator[dict[str, Any]]:
    """Yield strategy intermediate nodes for graph.json."""
    for i, strategy in enumerate(ir.get("strategies", [])):
        conc = strategy.get("conclusion")
        if not conc:
            continue
        yield {
            "id": f"strat_{i}",
            "type": "strategy",
            "strategy_type": strategy.get("type", ""),
            "module": kid_module.get(conc, ""),
            "reason": strategy.get("reason", ""),
        }


def _iter_operator_nodes(
    ir: dict[str, Any], kid_module: dict[str, str]
) -> Iterator[dict[str, Any]]:
    """Yield operator intermediate nodes for graph.json."""
    for i, operator in enumerate(ir.get("operators", [])):
        conc = operator.get("conclusion")
        yield {
            "id": f"oper_{i}",
            "type": "operator",
            "operator_type": operator.get("operator", ""),
            "module": kid_module.get(conc, "") if conc else "",
        }


def _iter_nodes(
    ir: dict[str, Any],
    *,
    beliefs: dict[str, float],
    priors: dict[str, float],
    exported: set[str],
    kid_module: dict[str, str],
) -> Iterator[dict[str, Any]]:
    yield from _iter_knowledge_nodes(ir, beliefs=beliefs, priors=priors, exported=exported)
    yield from _iter_strategy_nodes(ir, kid_module)
    yield from _iter_operator_nodes(ir, kid_module)


def _iter_edges(ir: dict[str, Any]) -> Iterator[dict[str, Any]]:
    """Yield graph edges without materializing the complete edge list."""
    for i, strategy in enumerate(ir.get("strategies", [])):
        conc = strategy.get("conclusion")
        if not conc:
            continue
        strat_id = f"strat_{i}"
        for premise in strategy.get("premises", []):
            yield {"source": premise, "target": strat_id, "role": "premise"}
        for background in strategy.get("background", []):
            yield {"source": background, "target": strat_id, "role": "background"}
        yield {"source": strat_id, "target": conc, "role": "conclusion"}

    for i, operator in enumerate(ir.get("operators", [])):
        conc = operator.get("conclusion")
        oper_id = f"oper_{i}"
        for variable in operator.get("variables", []):
            yield {"source": variable, "target": oper_id, "role": "variable"}
        if conc:
            yield {"source": oper_id, "target": conc, "role": "conclusion"}


def _iter_json_array(items: Iterable[dict[str, Any]]) -> Iterator[str]:
    yield "["
    first = True
    for item in items:
        if first:
            first = False
        else:
            yield ","
        yield json.dumps(item, ensure_ascii=False, separators=(",", ":"))
    yield "]"


def iter_graph_json_chunks(
    ir: dict[str, Any],
    beliefs_data: dict[str, Any] | None = None,
    param_data: dict[str, Any] | None = None,
    exported_ids: set[str] | None = None,
) -> Iterator[str]:
    """Yield graph.json chunks without materializing node/edge arrays."""
    beliefs, priors, exported, kid_module, modules, cross_module_edges = _graph_context(
        ir,
        beliefs_data=beliefs_data,
        param_data=param_data,
        exported_ids=exported_ids,
    )

    yield '{"modules":'
    yield from _iter_json_array(modules)
    yield ',"cross_module_edges":'
    yield from _iter_json_array(cross_module_edges)
    yield ',"nodes":'
    yield from _iter_json_array(
        _iter_nodes(
            ir,
            beliefs=beliefs,
            priors=priors,
            exported=exported,
            kid_module=kid_module,
        )
    )
    yield ',"edges":'
    yield from _iter_json_array(_iter_edges(ir))
    yield "}"


def write_graph_json(
    path: Path,
    ir: dict[str, Any],
    beliefs_data: dict[str, Any] | None = None,
    param_data: dict[str, Any] | None = None,
    exported_ids: set[str] | None = None,
) -> None:
    """Write graph.json directly to *path* using a bounded-memory stream."""
    with path.open("w", encoding="utf-8") as f:
        for chunk in iter_graph_json_chunks(
            ir,
            beliefs_data=beliefs_data,
            param_data=param_data,
            exported_ids=exported_ids,
        ):
            f.write(chunk)


def generate_graph_json(
    ir: dict[str, Any],
    beliefs_data: dict[str, Any] | None = None,
    param_data: dict[str, Any] | None = None,
    exported_ids: set[str] | None = None,
) -> str:
    """Return JSON string with nodes, edges, modules, and cross_module_edges."""
    return "".join(
        iter_graph_json_chunks(
            ir,
            beliefs_data=beliefs_data,
            param_data=param_data,
            exported_ids=exported_ids,
        )
    )
