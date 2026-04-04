"""gaia compile --readme: generate README.md from compiled IR."""

from __future__ import annotations

from collections import defaultdict


def topo_layers(ir: dict) -> dict[str, int]:
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


def _is_helper(label: str) -> bool:
    return label.startswith("__")


def _anchor_id(label: str) -> str:
    return label


def _module_key(k: dict) -> str:
    module = k.get("module")
    return module if module else "Root"


def _module_segments(nodes: list[dict]) -> list[tuple[str, list[dict]]]:
    segments: list[tuple[str, list[dict]]] = []
    for node in nodes:
        module_key = _module_key(node)
        if segments and segments[-1][0] == module_key:
            segments[-1][1].append(node)
            continue
        segments.append((module_key, [node]))
    return segments


# ── Mermaid rendering ──


_MERMAID_STYLES = """\
    classDef setting fill:#f0f0f0,stroke:#999
    classDef premise fill:#ddeeff,stroke:#4488bb
    classDef derived fill:#ddffdd,stroke:#44bb44
    classDef question fill:#fff3dd,stroke:#cc9944
    classDef orphan fill:#fff,stroke:#ccc,stroke-dasharray: 5 5
    classDef external fill:#fff,stroke:#aaa,stroke-dasharray: 3 3"""


def _classify_nodes(ir: dict) -> tuple[set[str], set[str]]:
    """Return (strategy_conclusions, strategy_premises) ID sets."""
    conclusions: set[str] = set()
    premises: set[str] = set()
    for s in ir.get("strategies", []):
        if s.get("conclusion"):
            conclusions.add(s["conclusion"])
        for p in s.get("premises", []):
            premises.add(p)
    return conclusions, premises


def _mermaid_node_line(
    label: str,
    kid: str,
    ktype: str,
    strategy_conclusions: set[str],
    strategy_premises: set[str],
    beliefs: dict[str, float] | None,
    *,
    title: str | None = None,
    css_class_override: str | None = None,
) -> str:
    display_name = title or label
    display = f"{display_name} ({beliefs[kid]:.2f})" if beliefs and kid in beliefs else display_name
    display = display.replace('"', "#quot;")
    if css_class_override:
        css = css_class_override
    elif ktype == "setting":
        css = "setting"
    elif ktype == "question":
        css = "question"
    elif kid in strategy_conclusions:
        css = "derived"
    elif kid in strategy_premises:
        css = "premise"
    else:
        css = "orphan"
    return f'    {label}["{display}"]:::{css}'


def render_mermaid(
    ir: dict,
    beliefs: dict[str, float] | None = None,
    *,
    node_ids: set[str] | None = None,
) -> str:
    """Render a Mermaid graph TD diagram.

    If node_ids is given, only show those nodes + edges between them.
    External premises (not in node_ids but connected) shown as dashed.
    """
    lines = ["```mermaid", "graph TD"]
    knowledge_by_id = {k["id"]: k for k in ir["knowledges"]}
    strategy_conclusions, strategy_premises = _classify_nodes(ir)

    # Determine which nodes to render
    if node_ids is not None:
        # Collect external premises that feed into this module's conclusions
        external_ids: set[str] = set()
        for s in ir.get("strategies", []):
            conc = s.get("conclusion")
            if conc and conc in node_ids:
                for p in s.get("premises", []):
                    if p not in node_ids:
                        p_label = knowledge_by_id.get(p, {}).get("label", "")
                        if not _is_helper(p_label):
                            external_ids.add(p)
        for o in ir.get("operators", []):
            conc = o.get("conclusion")
            if conc and conc in node_ids:
                for v in o.get("variables", []):
                    if v not in node_ids:
                        v_label = knowledge_by_id.get(v, {}).get("label", "")
                        if not _is_helper(v_label):
                            external_ids.add(v)
        all_visible = node_ids | external_ids
    else:
        external_ids = set()
        all_visible = set(knowledge_by_id.keys())

    # Render nodes
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
                strategy_conclusions,
                strategy_premises,
                beliefs,
                title=k.get("title"),
                css_class_override=css_override,
            )
        )

    # Render strategy edges (only if both ends visible)
    for s in ir.get("strategies", []):
        conclusion = s.get("conclusion")
        if not conclusion or conclusion not in all_visible:
            continue
        conc_label = knowledge_by_id.get(conclusion, {}).get("label", "")
        if _is_helper(conc_label):
            continue
        stype = s.get("type", "")
        for p in s.get("premises", []):
            if p not in all_visible:
                continue
            p_label = knowledge_by_id.get(p, {}).get("label", "")
            if _is_helper(p_label):
                continue
            lines.append(f"    {p_label} -->|{stype}| {conc_label}")

    # Render operator edges
    for o in ir.get("operators", []):
        conclusion = o.get("conclusion")
        if not conclusion or conclusion not in all_visible:
            continue
        conc_label = knowledge_by_id.get(conclusion, {}).get("label", "")
        if _is_helper(conc_label):
            continue
        otype = o.get("operator", "")
        for v in o.get("variables", []):
            if v not in all_visible:
                continue
            v_label = knowledge_by_id.get(v, {}).get("label", "")
            if _is_helper(v_label):
                continue
            lines.append(f"    {v_label} -.-|{otype}| {conc_label}")

    lines.append("")
    lines.append(_MERMAID_STYLES)
    lines.append("```")
    return "\n".join(lines)


# ── Narrative ordering ──


def _narrative_order(ir: dict) -> list[dict]:
    """Return knowledge nodes in narrative reading order."""
    nodes = [k for k in ir["knowledges"] if not _is_helper(k.get("label", ""))]
    module_order = ir.get("module_order")

    if module_order and any(k.get("module") for k in nodes):
        module_rank = {m: i for i, m in enumerate(module_order)}

        def sort_key(k):
            mod = k.get("module")
            idx = k.get("declaration_index", 0)
            mod_rank = module_rank.get(mod, 999) if mod else -1
            return (mod_rank, idx)

        return sorted(nodes, key=sort_key)

    # Fallback: topo sort (single-file or legacy packages)
    layers = topo_layers(ir)

    def sort_key(k):
        kid = k["id"]
        ktype = k["type"]
        if ktype == "question":
            return (999, 0, k.get("label", ""))
        if ktype == "setting":
            return (-1, 0, k.get("label", ""))
        return (layers.get(kid, 0), 1, k.get("label", ""))

    return sorted(nodes, key=sort_key)


# ── Knowledge node rendering ──


def _render_node(
    k: dict,
    strategy_for: dict[str, dict],
    knowledge_by_id: dict[str, dict],
    beliefs: dict[str, float],
    priors: dict[str, float],
    *,
    emit_anchor: bool = True,
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
    type_emoji = {"setting": "\U0001f4cb", "claim": "\U0001f4cc", "question": "\u2753"}.get(
        ktype, ""
    )
    badge_parts = [f"{type_emoji} `{label}`"]
    if kid in priors:
        badge_parts.append(f"Prior: {priors[kid]:.2f}")
    if kid in beliefs:
        badge_parts.append(f"Belief: **{beliefs[kid]:.2f}**")
    lines.append(" \u00a0\u00a0|\u00a0\u00a0 ".join(badge_parts))
    lines.append("")

    # Content in blockquote
    if content:
        for content_line in content.split("\n"):
            lines.append(f"> {content_line}")
        lines.append("")

    # Derivation
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

    lines.append("")
    return lines


def _render_introduction(
    ir: dict,
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
    strategy_for: dict[str, dict] = {}
    for s in ir.get("strategies", []):
        if s.get("conclusion"):
            strategy_for[s["conclusion"]] = s

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
            )
        )
    return lines


def render_knowledge_nodes(
    ir: dict,
    beliefs: dict[str, float] | None = None,
    priors: dict[str, float] | None = None,
) -> str:
    """Render knowledge nodes grouped by module with per-module Mermaid diagrams."""
    knowledge_by_id = {k["id"]: k for k in ir["knowledges"]}
    beliefs = beliefs or {}
    priors = priors or {}

    strategy_for: dict[str, dict] = {}
    for s in ir.get("strategies", []):
        if s.get("conclusion"):
            strategy_for[s["conclusion"]] = s

    module_order = ir.get("module_order")
    has_modules = module_order and any(k.get("module") for k in knowledge_by_id.values())
    sections: list[str] = []

    if has_modules:
        ordered_nodes = [k for k in ir["knowledges"] if not _is_helper(k.get("label", ""))]
        segments = _module_segments(ordered_nodes)
        module_titles = ir.get("module_titles") or {}
        segment_counts: dict[str, int] = defaultdict(int)

        for mod, nodes in segments:
            count = segment_counts[mod]
            if mod == "Root":
                heading = "Root"
            else:
                heading = module_titles.get(mod, mod)
            if count:
                heading = f"{heading} (continued)"
            segment_counts[mod] += 1

            sections.append(f"## {heading}")
            sections.append("")

            if mod != "Root":
                mod_ids = {k["id"] for k in nodes}
                mermaid = render_mermaid(ir, beliefs=beliefs, node_ids=mod_ids)
                sections.append(mermaid)
                sections.append("")

            for k in nodes:
                sections.extend(_render_node(k, strategy_for, knowledge_by_id, beliefs, priors))
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
            ktype = k["type"]
            if ktype != current_type:
                current_type = ktype
                sections.append(f"### {ktype.title()}s")
                sections.append("")
            sections.extend(_render_node(k, strategy_for, knowledge_by_id, beliefs, priors))

    return "\n".join(sections)


# ── Inference results ──


def render_inference_results(
    ir: dict,
    beliefs_data: dict,
    param_data: dict | None = None,
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
    strategy_conclusions, strategy_premises = _classify_nodes(ir)

    lines.append("| Label | Type | Prior | Belief | Role |")
    lines.append("|-------|------|-------|--------|------|")

    for b in sorted(beliefs_data.get("beliefs", []), key=lambda x: x["belief"]):
        kid = b["knowledge_id"]
        label = b.get("label", kid.split("::")[-1])
        if _is_helper(label):
            continue
        belief = f"{b['belief']:.4f}"
        prior = f"{priors[kid]:.2f}" if kid in priors else "\u2014"
        k = knowledge_by_id.get(kid, {})
        ktype = k.get("type", "")
        if kid in strategy_conclusions:
            role = "derived"
        elif kid in strategy_premises:
            role = "independent"
        else:
            role = "orphaned"
        lines.append(f"| [{label}](#{_anchor_id(label)}) | {ktype} | {prior} | {belief} | {role} |")

    lines.append("")
    return "\n".join(lines)


# ── Top-level assembler ──


def generate_readme(
    ir: dict,
    pkg_metadata: dict,
    beliefs_data: dict | None = None,
    param_data: dict | None = None,
) -> str:
    """Generate full README.md content from compiled IR and optional inference results."""
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
