"""Generate docs/detailed-reasoning.md — per-module reasoning doc — from compiled IR."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from gaia.cli.commands._render_priors import format_belief
from gaia.engine.inquiry._classify import classify_ir, is_note_type, node_role


def topo_layers(ir: dict[str, Any]) -> dict[str, int]:
    """Assign each knowledge ID a topological layer (0 = no incoming edges)."""
    all_ids = {k["id"] for k in ir["knowledges"]}
    incoming: dict[str, set[str]] = defaultdict(set)
    for s in ir.get("strategies", []):
        conclusion = s.get("conclusion")
        if conclusion and conclusion in all_ids:
            for p in s.get("premises", []):
                if p in all_ids:
                    incoming[conclusion].add(p)
    for o in ir.get("operators", []):
        conclusion = o.get("conclusion")
        if conclusion and conclusion in all_ids:
            for v in o.get("variables", []):
                if v in all_ids:
                    incoming[conclusion].add(v)

    layers: dict[str, int] = {}
    remaining = set(all_ids)
    layer = 0
    while remaining:
        ready = {nid for nid in remaining if not (incoming.get(nid, set()) - set(layers.keys()))}
        if not ready:
            ready = remaining
        for nid in ready:
            layers[nid] = layer
        remaining -= ready
        layer += 1
    return layers


def _is_helper(label: str | None) -> bool:
    if not label:
        return True
    return label.startswith("__") or label.startswith("_anon")


def _anchor_id(label: str) -> str:
    return label


def _module_key(k: dict[str, Any]) -> str:
    module = k.get("module")
    return module if module else "Root"


def _display_knowledge_type(ktype: str) -> str:
    return "note" if is_note_type(ktype) else ktype


def _module_segments(nodes: list[dict[str, Any]]) -> list[tuple[str, list[dict[str, Any]]]]:
    segments: list[tuple[str, list[dict[str, Any]]]] = []
    for node in nodes:
        module_key = _module_key(node)
        if segments and segments[-1][0] == module_key:
            segments[-1][1].append(node)
            continue
        segments.append((module_key, [node]))
    return segments


# ── Mermaid rendering ──

_MERMAID_STYLES = """\
    classDef note fill:#f0f0f0,stroke:#999,color:#333
    classDef premise fill:#ddeeff,stroke:#4488bb,color:#333
    classDef derived fill:#ddffdd,stroke:#44bb44,color:#333
    classDef question fill:#fff3dd,stroke:#cc9944,color:#333
    classDef background fill:#f5f5f5,stroke:#bbb,stroke-dasharray: 5 5,color:#333
    classDef orphan fill:#fff,stroke:#ccc,stroke-dasharray: 5 5,color:#333
    classDef external fill:#fff,stroke:#aaa,stroke-dasharray: 3 3,color:#333
    classDef weak fill:#fff9c4,stroke:#f9a825,stroke-dasharray: 5 5,color:#333
    classDef contra fill:#ffebee,stroke:#c62828,color:#333"""

# Map node_role() output to Mermaid CSS class names
_ROLE_TO_CSS = {
    "note": "note",
    "question": "question",
    "derived": "derived",
    "structural": "derived",  # operator conclusions display like derived
    "independent": "premise",
    "background": "background",
    "orphaned": "orphan",
}

# Strategy type classification for visual rendering
_DETERMINISTIC_STRATEGIES = frozenset(
    {
        "deduction",
        "reductio",
        "elimination",
        "mathematical_induction",
        "case_analysis",
    }
)

# Operator symbol mapping for Mermaid hexagon nodes
_OPERATOR_SYMBOLS = {
    "contradiction": "\u2297",
    "equivalence": "\u2261",
    "complement": "\u2295",
    "negation": "\u00ac",
    "disjunction": "\u2228",
    "conjunction": "\u2227",
    "implication": "\u2192",
}

# Operators rendered with undirected (---) edges between variables
_UNDIRECTED_OPERATORS = frozenset({"equivalence", "contradiction", "complement", "implication"})


def _visible_mermaid_ids(
    ir: dict[str, Any],
    knowledge_by_id: dict[str, dict[str, Any]],
    node_ids: set[str] | None,
) -> tuple[set[str], set[str]]:
    """Return all visible node ids plus external ids for a scoped diagram."""
    if node_ids is None:
        return set(knowledge_by_id.keys()), set()

    external_ids: set[str] = set()
    _add_strategy_external_ids(external_ids, ir, knowledge_by_id, node_ids)
    _add_operator_external_ids(external_ids, ir, knowledge_by_id, node_ids)
    return node_ids | external_ids, external_ids


def _add_strategy_external_ids(
    external_ids: set[str],
    ir: dict[str, Any],
    knowledge_by_id: dict[str, dict[str, Any]],
    node_ids: set[str],
) -> None:
    """Add scoped-diagram external ids from strategy premises/background."""
    for strategy in ir.get("strategies", []):
        conclusion = strategy.get("conclusion")
        if not (conclusion and conclusion in node_ids):
            continue
        for ref in [*strategy.get("premises", []), *(strategy.get("background") or [])]:
            label = knowledge_by_id.get(ref, {}).get("label", "")
            if ref not in node_ids and not _is_helper(label):
                external_ids.add(ref)


def _add_operator_external_ids(
    external_ids: set[str],
    ir: dict[str, Any],
    knowledge_by_id: dict[str, dict[str, Any]],
    node_ids: set[str],
) -> None:
    """Add scoped-diagram external ids from operator variables/conclusions."""
    for operator in ir.get("operators", []):
        variables = operator.get("variables", [])
        conclusion = operator.get("conclusion")
        if not ((conclusion and conclusion in node_ids) or any(v in node_ids for v in variables)):
            continue
        for variable in variables:
            label = knowledge_by_id.get(variable, {}).get("label", "")
            if variable not in node_ids and not _is_helper(label):
                external_ids.add(variable)
        conc_label = knowledge_by_id.get(conclusion, {}).get("label", "") if conclusion else ""
        if conclusion and conclusion not in node_ids and not _is_helper(conc_label):
            external_ids.add(conclusion)


def _visible_labeled_refs(
    refs: list[str],
    all_visible: set[str],
    knowledge_by_id: dict[str, dict[str, Any]],
) -> list[str]:
    """Return visible, non-helper labels for a list of knowledge ids."""
    labels: list[str] = []
    for ref in refs:
        if ref not in all_visible:
            continue
        label = knowledge_by_id.get(ref, {}).get("label", "")
        if label and not _is_helper(label):
            labels.append(label)
    return labels


def _mermaid_node_line(
    label: str,
    kid: str,
    ktype: str,
    classification: Any,
    beliefs: dict[str, float] | None,
    *,
    title: str | None = None,
    css_class_override: str | None = None,
) -> str:
    display_name = title or label
    display = (
        f"{display_name} ({format_belief(beliefs[kid])})"
        if beliefs and kid in beliefs
        else display_name
    )
    display = display.replace('"', "#quot;").replace("*", "#ast;")
    if css_class_override:
        css = css_class_override
    else:
        role = node_role(kid, ktype, classification)
        css = _ROLE_TO_CSS.get(role, "orphan")
    return f'    {label}["{display}"]:::{css}'


def _append_mermaid_knowledge_nodes(
    lines: list[str],
    ir: dict[str, Any],
    classification: Any,
    beliefs: dict[str, float] | None,
    all_visible: set[str],
    external_ids: set[str],
) -> None:
    """Append visible knowledge nodes."""
    for k in ir["knowledges"]:
        kid = k["id"]
        if kid not in all_visible:
            continue
        label = k.get("label", "")
        if _is_helper(label):
            continue
        css_override = "external" if kid in external_ids else None
        lines.append(
            _mermaid_node_line(
                label,
                kid,
                k["type"],
                classification,
                beliefs,
                title=k.get("title"),
                css_class_override=css_override,
            )
        )


def _append_mermaid_strategy_edges(
    lines: list[str],
    ir: dict[str, Any],
    knowledge_by_id: dict[str, dict[str, Any]],
    all_visible: set[str],
) -> None:
    """Append strategy intermediate nodes and edges."""
    for i, s in enumerate(ir.get("strategies", [])):
        conclusion = s.get("conclusion")
        if not conclusion or conclusion not in all_visible:
            continue
        conc_label = knowledge_by_id.get(conclusion, {}).get("label", "")
        if _is_helper(conc_label):
            continue

        premises = _visible_labeled_refs(s.get("premises", []), all_visible, knowledge_by_id)
        backgrounds = _visible_labeled_refs(s.get("background") or [], all_visible, knowledge_by_id)
        if not premises and not backgrounds:
            continue

        stype = s.get("type", "")
        sid = f"strat_{i}"
        css = "" if stype in _DETERMINISTIC_STRATEGIES else ":::weak"
        lines.append(f'    {sid}(["{stype}"]){css}')
        for p_label in premises:
            lines.append(f"    {p_label} --> {sid}")
        for b_label in backgrounds:
            lines.append(f"    {b_label} -.-> {sid}")
        lines.append(f"    {sid} --> {conc_label}")


def _append_mermaid_operator_edges(
    lines: list[str],
    ir: dict[str, Any],
    knowledge_by_id: dict[str, dict[str, Any]],
    all_visible: set[str],
) -> None:
    """Append operator intermediate nodes and edges."""
    for i, o in enumerate(ir.get("operators", [])):
        conclusion = o.get("conclusion")
        conc_label = knowledge_by_id.get(conclusion, {}).get("label", "") if conclusion else ""
        conc_visible = bool(conclusion and conclusion in all_visible and not _is_helper(conc_label))

        otype = o.get("operator", "")
        visible_vars = _visible_labeled_refs(o.get("variables", []), all_visible, knowledge_by_id)
        if not visible_vars and not conc_visible:
            continue

        oid = f"oper_{i}"
        symbol = _OPERATOR_SYMBOLS.get(otype, otype)
        css = ":::contra" if otype == "contradiction" else ""
        lines.append(f'    {oid}{{{{"{symbol}"}}}}{css}')

        edge = " --- " if otype in _UNDIRECTED_OPERATORS else " --> "
        for v_label in visible_vars:
            lines.append(f"    {v_label}{edge}{oid}")
        if conc_visible:
            lines.append(f"    {oid}{edge}{conc_label}")


_MERMAID_LEGEND = (
    "**Diagram legend:**\n"
    "nodes: rectangle = claim/note/question;"
    " oval = derivation strategy; hexagon = structural operator.\n"
    "edges: solid arrow (`-->`) = premise; dotted arrow (`-.->`) = background note.\n"
    "operators: ⊕ exclusive partition; ⊗ contradiction; ≡ equivalence.\n"
    "colours: blue = premise/independent; green = derived; amber = question;"
    " grey/dashed = background or note; red = contradiction;"
    " dashed-yellow = non-deterministic strategy."
)


def render_mermaid(
    ir: dict[str, Any],
    beliefs: dict[str, float] | None = None,
    *,
    node_ids: set[str] | None = None,
) -> str:
    """Render a Mermaid graph TD diagram with strategy and operator intermediate nodes.

    Strategies render as stadium-shaped nodes; operators as hexagons.
    If node_ids is given, only show those nodes + edges between them.
    External premises (not in node_ids but connected) shown as dashed.
    """
    lines = ["```mermaid", "graph TD"]
    knowledge_by_id = {k["id"]: k for k in ir["knowledges"]}
    classification = classify_ir(ir)
    all_visible, external_ids = _visible_mermaid_ids(ir, knowledge_by_id, node_ids)

    _append_mermaid_knowledge_nodes(lines, ir, classification, beliefs, all_visible, external_ids)
    _append_mermaid_strategy_edges(lines, ir, knowledge_by_id, all_visible)
    _append_mermaid_operator_edges(lines, ir, knowledge_by_id, all_visible)

    lines.append("")
    lines.append(_MERMAID_STYLES)
    lines.append("```")
    lines.append("")
    lines.append(_MERMAID_LEGEND)
    return "\n".join(lines)


# ── Narrative ordering ──


def _narrative_order(ir: dict[str, Any]) -> list[dict[str, Any]]:
    """Return knowledge nodes in narrative reading order."""
    nodes = [k for k in ir["knowledges"] if not _is_helper(k.get("label", ""))]
    module_order = ir.get("module_order")

    if module_order and any(k.get("module") for k in nodes):
        module_rank = {m: i for i, m in enumerate(module_order)}

        def module_sort_key(k: dict[str, Any]) -> tuple[int, Any]:
            mod = k.get("module")
            idx = k.get("declaration_index", 0)
            mod_rank = module_rank.get(mod, 999) if mod else -1
            return (mod_rank, idx)

        return sorted(nodes, key=module_sort_key)

    # Fallback: topo sort (single-file or legacy packages)
    layers = topo_layers(ir)

    def fallback_sort_key(k: dict[str, Any]) -> tuple[int, int, Any]:
        kid = k["id"]
        ktype = k["type"]
        if ktype == "question":
            return (999, 0, k.get("label", ""))
        if is_note_type(ktype):
            return (-1, 0, k.get("label", ""))
        return (layers.get(kid, 0), 1, k.get("label", ""))

    return sorted(nodes, key=fallback_sort_key)


# ── Knowledge node rendering ──


def _render_node(
    k: dict[str, Any],
    strategy_for: dict[str, dict[str, Any]],
    knowledge_by_id: dict[str, dict[str, Any]],
    beliefs: dict[str, float],
    priors: dict[str, float],
    *,
    emit_anchor: bool = True,
    operator_for: dict[str, dict[str, Any]] | None = None,
) -> list[str]:
    """Render a single knowledge node as markdown lines."""
    label = k.get("label", "")
    kid = k["id"]
    content = k.get("content", "")
    exported = k.get("exported", False)
    lines: list[str] = []

    title = k.get("title") or label
    marker = " \u2605" if exported else ""
    ktype = k.get("type", "claim")

    # Keep a stable label-based anchor even when the visible heading uses title.
    if emit_anchor and label:
        lines.append(f'<a id="{_anchor_id(label)}"></a>')
        lines.append("")

    lines.append(f"#### {title}{marker}")
    lines.append("")

    # Type + label badge line
    type_emoji = {
        "note": "\U0001f4cb",
        "setting": "\U0001f4cb",
        "context": "\U0001f4cb",
        "claim": "\U0001f4cc",
        "question": "\u2753",
    }.get(ktype, "")
    badge_parts = [f"{type_emoji} `{label}`"]
    if kid in priors:
        badge_parts.append(f"Prior: {format_belief(priors[kid])}")
    if kid in beliefs:
        badge_parts.append(f"Belief: **{format_belief(beliefs[kid])}**")
    lines.append(" \u00a0\u00a0|\u00a0\u00a0 ".join(badge_parts))
    lines.append("")

    # Content in blockquote
    if content:
        for content_line in content.split("\n"):
            lines.append(f"> {content_line}")
        lines.append("")

    # Derivation (strategy)
    if kid in strategy_for:
        s = strategy_for[kid]
        stype = s.get("type", "")
        premise_links = []
        for p in s.get("premises", []):
            pk = knowledge_by_id.get(p, {})
            p_label = pk.get("label", p.split("::")[-1])
            p_title = pk.get("title") or p_label
            if not _is_helper(p_label):
                premise_links.append(f"[{p_title}](#{_anchor_id(p_label)})")
        lines.append(f"\U0001f517 **{stype}**({', '.join(premise_links)})")
        lines.append("")
        reason = (s.get("metadata") or {}).get("reason", "")
        if reason:
            lines.append("<details><summary>Reasoning</summary>")
            lines.append("")
            lines.append(reason)
            lines.append("")
            lines.append("</details>")
            lines.append("")

    # Structural link (operator: derive/contradict/equal/exclusive)
    if operator_for and kid in operator_for:
        o = operator_for[kid]
        otype = o.get("operator", "")
        var_links = []
        for v in o.get("variables", []):
            vk = knowledge_by_id.get(v, {})
            v_label = vk.get("label", v.split("::")[-1])
            v_title = vk.get("title") or v_label
            if not _is_helper(v_label):
                var_links.append(f"[{v_title}](#{_anchor_id(v_label)})")
        lines.append(f"\U0001f517 **{otype}**({', '.join(var_links)})")
        lines.append("")
        reason = (o.get("metadata") or {}).get("reason", "")
        if reason:
            lines.append("<details><summary>Reasoning</summary>")
            lines.append("")
            lines.append(reason)
            lines.append("")
            lines.append("</details>")
            lines.append("")

    lines.append("")
    return lines


def _overview_dependencies(ir: dict[str, Any]) -> dict[str, set[str]]:
    """Build a conclusion-to-premise dependency map for overview rendering."""
    deps: dict[str, set[str]] = defaultdict(set)
    for s in ir.get("strategies", []):
        conc = s.get("conclusion")
        if conc:
            for p in s.get("premises", []):
                deps[conc].add(p)
    for o in ir.get("operators", []):
        conc = o.get("conclusion")
        if conc:
            for v in o.get("variables", []):
                deps[conc].add(v)
    return deps


def _nearest_exported_deps(
    start: str,
    *,
    deps: dict[str, set[str]],
    exported_ids: set[str],
) -> set[str]:
    """Find nearest exported dependencies reachable from one exported node."""
    visited: set[str] = set()
    stack = list(deps.get(start, set()))
    result: set[str] = set()
    while stack:
        node = stack.pop()
        if node in visited:
            continue
        visited.add(node)
        if node in exported_ids:
            result.add(node)
        else:
            stack.extend(deps.get(node, set()))
    return result


def _overview_edges(ir: dict[str, Any], exported_ids: set[str]) -> set[tuple[str, str]]:
    """Return non-transitive exported dependency edges for the overview graph."""
    deps = _overview_dependencies(ir)
    edges: set[tuple[str, str]] = set()
    for eid in exported_ids:
        for dep_id in _nearest_exported_deps(eid, deps=deps, exported_ids=exported_ids):
            edges.add((dep_id, eid))
    return edges


def _render_overview_graph(
    ir: dict[str, Any],
    beliefs: dict[str, float] | None = None,
) -> list[str]:
    """Render a summary Mermaid graph showing dependencies between exported conclusions."""
    knowledge_by_id = {k["id"]: k for k in ir["knowledges"]}
    exported = [
        k for k in ir["knowledges"] if k.get("exported") and not _is_helper(k.get("label", ""))
    ]
    exported_ids = {k["id"] for k in exported}

    if len(exported) < 2:
        return []

    edges = _overview_edges(ir, exported_ids)
    if not edges:
        return []

    c = classify_ir(ir)
    lines = ["## Overview", "", "```mermaid", "graph LR"]

    for k in exported:
        label = k.get("label", "")
        kid = k["id"]
        title = k.get("title") or label
        display = (
            f"{title} ({format_belief(beliefs[kid])})" if beliefs and kid in beliefs else title
        )
        display = display.replace('"', "#quot;").replace("*", "#ast;")
        role = node_role(kid, k["type"], c)
        css = _ROLE_TO_CSS.get(role, "orphan")
        lines.append(f'    {label}["{display}"]:::{css}')

    for dep_id, eid in sorted(edges):
        dep_label = knowledge_by_id[dep_id].get("label", "")
        eid_label = knowledge_by_id[eid].get("label", "")
        lines.append(f"    {dep_label} --> {eid_label}")

    lines.append("")
    lines.append(_MERMAID_STYLES)
    lines.append("```")
    lines.append("")

    return lines


def _render_introduction(
    ir: dict[str, Any],
    beliefs: dict[str, float],
    priors: dict[str, float],
) -> list[str]:
    """Render an Introduction section from exported knowledge.

    Only used when there is NO motivation module (since the motivation module
    itself serves as the introduction). When no motivation module exists,
    show exported knowledge as a summary.
    """
    # If a motivation module exists, it IS the introduction — skip this section
    module_order = ir.get("module_order") or []
    if "motivation" in module_order:
        return []

    knowledge_by_id = {k["id"]: k for k in ir["knowledges"]}
    strategy_for: dict[str, dict[str, Any]] = {}
    for s in ir.get("strategies", []):
        if s.get("conclusion"):
            strategy_for[s["conclusion"]] = s
    operator_for: dict[str, dict[str, Any]] = {}
    for o in ir.get("operators", []):
        if o.get("conclusion"):
            operator_for[o["conclusion"]] = o

    exported = [
        k for k in ir["knowledges"] if k.get("exported") and not _is_helper(k.get("label", ""))
    ]
    if not exported:
        return []

    lines = ["## Introduction", ""]
    for k in exported:
        lines.extend(
            _render_node(
                k,
                strategy_for,
                knowledge_by_id,
                beliefs,
                priors,
                emit_anchor=False,
                operator_for=operator_for,
            )
        )
    return lines


def render_knowledge_nodes(
    ir: dict[str, Any],
    beliefs: dict[str, float] | None = None,
    priors: dict[str, float] | None = None,
) -> str:
    """Render knowledge nodes grouped by module with per-module Mermaid diagrams."""
    knowledge_by_id = {k["id"]: k for k in ir["knowledges"]}
    beliefs = beliefs or {}
    priors = priors or {}

    strategy_for: dict[str, dict[str, Any]] = {}
    for s in ir.get("strategies", []):
        if s.get("conclusion"):
            strategy_for[s["conclusion"]] = s
    operator_for: dict[str, dict[str, Any]] = {}
    for o in ir.get("operators", []):
        if o.get("conclusion"):
            operator_for[o["conclusion"]] = o

    module_order = ir.get("module_order")
    has_modules = module_order and any(k.get("module") for k in knowledge_by_id.values())
    sections: list[str] = []

    if has_modules:
        ordered_nodes = [k for k in ir["knowledges"] if not _is_helper(k.get("label", ""))]
        segments = _module_segments(ordered_nodes)
        module_titles = ir.get("module_titles") or {}
        segment_counts: dict[str, int] = defaultdict(int)
        first_module = module_order[0] if module_order else None

        for mod, nodes in segments:
            count = segment_counts[mod]
            heading = "Root" if mod == "Root" else module_titles.get(mod, mod)
            if count:
                heading = f"{heading} (continued)"
            segment_counts[mod] += 1

            sections.append(f"## {heading}")
            sections.append("")

            # Skip per-module Mermaid for the first module (introduction/motivation)
            # — the overview graph covers the high-level view
            if mod != "Root" and mod != first_module:
                mod_ids = {k["id"] for k in nodes}
                mermaid = render_mermaid(ir, beliefs=beliefs, node_ids=mod_ids)
                sections.append(mermaid)
                sections.append("")

            for k in nodes:
                sections.extend(
                    _render_node(
                        k,
                        strategy_for,
                        knowledge_by_id,
                        beliefs,
                        priors,
                        operator_for=operator_for,
                    )
                )
    else:
        # Single-file/legacy: one global diagram + type-based grouping
        ordered = _narrative_order(ir)
        sections.append("## Knowledge Graph")
        sections.append("")
        sections.append(render_mermaid(ir, beliefs=beliefs))
        sections.append("")

        sections.append("## Knowledge Nodes")
        sections.append("")
        current_type = None
        for k in ordered:
            ktype = _display_knowledge_type(k["type"])
            if ktype != current_type:
                current_type = ktype
                sections.append(f"### {ktype.title()}s")
                sections.append("")
            sections.extend(
                _render_node(
                    k,
                    strategy_for,
                    knowledge_by_id,
                    beliefs,
                    priors,
                    operator_for=operator_for,
                )
            )

    return "\n".join(sections)


# ── Inference results ──


def render_inference_results(
    ir: dict[str, Any],
    beliefs_data: dict[str, Any],
    param_data: dict[str, Any] | None = None,
) -> str:
    """Render inference results summary table."""
    lines = ["## Inference Results", ""]
    diag = beliefs_data.get("diagnostics", {})
    converged = diag.get("converged", False)
    iterations = diag.get("iterations_run", "?")
    lines.append(f"**BP converged:** {converged} ({iterations} iterations)")
    lines.append("")

    priors: dict[str, float] = {}
    if param_data:
        priors = {p["knowledge_id"]: p["value"] for p in param_data.get("priors", [])}

    knowledge_by_id = {k["id"]: k for k in ir["knowledges"]}
    c = classify_ir(ir)

    lines.append("| Label | Type | Prior | Belief | Role |")
    lines.append("|-------|------|-------|--------|------|")

    for b in sorted(beliefs_data.get("beliefs", []), key=lambda x: x["belief"]):
        kid = b["knowledge_id"]
        label = b.get("label", kid.split("::")[-1])
        if _is_helper(label):
            continue
        # Belief column keeps 4-decimal precision for "normal" values;
        # tiny posteriors switch to scientific notation so they aren't
        # silently rounded to 0.0000 (theme 002).
        belief_value = b["belief"]
        if abs(belief_value) < 0.0005 and belief_value != 0.0:
            belief = f"{belief_value:.1e}"
        else:
            belief = f"{belief_value:.4f}"
        prior = format_belief(priors[kid]) if kid in priors else "\u2014"
        k = knowledge_by_id.get(kid, {})
        ktype = k.get("type", "")
        role = node_role(kid, ktype, c)
        lines.append(f"| [{label}](#{_anchor_id(label)}) | {ktype} | {prior} | {belief} | {role} |")

    lines.append("")
    return "\n".join(lines)


# ── Top-level assembler ──


def generate_detailed_reasoning(
    ir: dict[str, Any],
    pkg_metadata: dict[str, Any],
    beliefs_data: dict[str, Any] | None = None,
    param_data: dict[str, Any] | None = None,
) -> str:
    """Generate detailed-reasoning.md content from compiled IR and optional inference results."""
    beliefs: dict[str, float] | None = None
    priors: dict[str, float] | None = None

    if beliefs_data:
        beliefs = {b["knowledge_id"]: b["belief"] for b in beliefs_data.get("beliefs", [])}
    if param_data:
        priors = {p["knowledge_id"]: p["value"] for p in param_data.get("priors", [])}

    parts: list[str] = []

    name = pkg_metadata.get("name", ir.get("package_name", "Package"))
    desc = pkg_metadata.get("description", "")
    parts.append(f"# {name}")
    parts.append("")
    if desc:
        parts.append(desc)
        parts.append("")

    # Overview graph: exported conclusions and their transitive dependencies
    overview = _render_overview_graph(ir, beliefs)
    if overview:
        parts.extend(overview)

    # Introduction: motivation module or exported knowledge
    intro = _render_introduction(ir, beliefs or {}, priors or {})
    if intro:
        parts.extend(intro)
        parts.append("")

    # Module sections (each with focused Mermaid) or single-file fallback
    parts.append(render_knowledge_nodes(ir, beliefs=beliefs, priors=priors))

    # Inference results
    if beliefs_data:
        parts.append(render_inference_results(ir, beliefs_data, param_data))

    return "\n".join(parts)
