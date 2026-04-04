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


def render_mermaid(ir: dict, beliefs: dict[str, float] | None = None) -> str:
    """Render a Mermaid graph TD diagram from the IR."""
    lines = ["```mermaid", "graph TD"]
    knowledge_by_id = {k["id"]: k for k in ir["knowledges"]}

    strategy_conclusions: set[str] = set()
    strategy_premises: set[str] = set()
    for s in ir.get("strategies", []):
        if s.get("conclusion"):
            strategy_conclusions.add(s["conclusion"])
        for p in s.get("premises", []):
            strategy_premises.add(p)

    for k in ir["knowledges"]:
        label = k.get("label", "")
        if _is_helper(label):
            continue
        kid = k["id"]
        ktype = k["type"]
        display = f"{label} ({beliefs[kid]:.2f})" if beliefs and kid in beliefs else label
        # Escape quotes in display for Mermaid
        display = display.replace('"', "#quot;")
        if ktype == "setting":
            lines.append(f'    {label}["{display}"]:::setting')
        elif ktype == "question":
            lines.append(f'    {label}["{display}"]:::question')
        elif kid in strategy_conclusions:
            lines.append(f'    {label}["{display}"]:::derived')
        elif kid in strategy_premises:
            lines.append(f'    {label}["{display}"]:::premise')
        else:
            lines.append(f'    {label}["{display}"]:::orphan')

    for s in ir.get("strategies", []):
        conclusion = s.get("conclusion")
        if not conclusion:
            continue
        conc_label = knowledge_by_id.get(conclusion, {}).get("label", "")
        if _is_helper(conc_label):
            continue
        stype = s.get("type", "")
        for p in s.get("premises", []):
            p_label = knowledge_by_id.get(p, {}).get("label", "")
            if _is_helper(p_label):
                continue
            lines.append(f"    {p_label} -->|{stype}| {conc_label}")

    for o in ir.get("operators", []):
        conclusion = o.get("conclusion")
        if not conclusion:
            continue
        conc_label = knowledge_by_id.get(conclusion, {}).get("label", "")
        if _is_helper(conc_label):
            continue
        otype = o.get("operator", "")
        for v in o.get("variables", []):
            v_label = knowledge_by_id.get(v, {}).get("label", "")
            if _is_helper(v_label):
                continue
            lines.append(f"    {v_label} -.-|{otype}| {conc_label}")

    lines.append("")
    lines.append("    classDef setting fill:#f0f0f0,stroke:#999")
    lines.append("    classDef premise fill:#ddeeff,stroke:#4488bb")
    lines.append("    classDef derived fill:#ddffdd,stroke:#44bb44")
    lines.append("    classDef question fill:#fff3dd,stroke:#cc9944")
    lines.append("    classDef orphan fill:#fff,stroke:#ccc,stroke-dasharray: 5 5")
    lines.append("```")
    return "\n".join(lines)


def _narrative_order(ir: dict) -> list[dict]:
    """Return knowledge nodes in narrative reading order."""
    layers = topo_layers(ir)
    nodes = [k for k in ir["knowledges"] if not _is_helper(k.get("label", ""))]

    def sort_key(k):
        kid = k["id"]
        ktype = k["type"]
        if ktype == "question":
            return (999, 0, k.get("label", ""))
        if ktype == "setting":
            return (-1, 0, k.get("label", ""))
        return (layers.get(kid, 0), 1, k.get("label", ""))

    return sorted(nodes, key=sort_key)


def render_knowledge_nodes(
    ir: dict,
    beliefs: dict[str, float] | None = None,
    priors: dict[str, float] | None = None,
) -> str:
    """Render the Knowledge Nodes section in narrative order with hyperlinks."""
    knowledge_by_id = {k["id"]: k for k in ir["knowledges"]}
    beliefs = beliefs or {}
    priors = priors or {}

    strategy_for: dict[str, dict] = {}
    for s in ir.get("strategies", []):
        if s.get("conclusion"):
            strategy_for[s["conclusion"]] = s

    ordered = _narrative_order(ir)
    sections: list[str] = ["## Knowledge Nodes", ""]
    current_type = None

    for k in ordered:
        ktype = k["type"]
        label = k.get("label", "")
        kid = k["id"]
        content = k.get("content", "")

        if ktype != current_type:
            current_type = ktype
            sections.append(f"### {ktype.title()}s")
            sections.append("")

        sections.append(f"#### {label}")
        sections.append("")
        sections.append(content)
        sections.append("")

        if kid in strategy_for:
            s = strategy_for[kid]
            stype = s.get("type", "")
            premise_labels = []
            for p in s.get("premises", []):
                p_label = knowledge_by_id.get(p, {}).get("label", p.split("::")[-1])
                if not _is_helper(p_label):
                    premise_labels.append(f"[{p_label}](#{p_label})")
            sections.append(f"**Derived via:** {stype}({', '.join(premise_labels)})")

        meta_parts = []
        if kid in priors:
            meta_parts.append(f"**Prior:** {priors[kid]:.2f}")
        if kid in beliefs:
            meta_parts.append(f"**Belief:** {beliefs[kid]:.2f}")
        if meta_parts:
            sections.append(" · ".join(meta_parts))

        if kid in strategy_for:
            reason = (strategy_for[kid].get("metadata") or {}).get("reason", "")
            if reason:
                sections.append(f"**Reason:** {reason}")

        sections.append("")

    return "\n".join(sections)


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
    strategy_conclusions = {
        s["conclusion"] for s in ir.get("strategies", []) if s.get("conclusion")
    }
    strategy_premises: set[str] = set()
    for s in ir.get("strategies", []):
        for p in s.get("premises", []):
            strategy_premises.add(p)

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
        lines.append(f"| [{label}](#{label}) | {ktype} | {prior} | {belief} | {role} |")

    lines.append("")
    return "\n".join(lines)


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

    parts.append("## Knowledge Graph")
    parts.append("")
    parts.append(render_mermaid(ir, beliefs=beliefs))
    parts.append("")

    parts.append(render_knowledge_nodes(ir, beliefs=beliefs, priors=priors))

    if beliefs_data:
        parts.append(render_inference_results(ir, beliefs_data, param_data))

    return "\n".join(parts)
