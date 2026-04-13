"""Simplified Mermaid graph for GitHub wiki overview pages.

Selects a bounded set of the most informative nodes and renders a compact
``graph TD`` diagram with prior → belief annotations.
"""

from __future__ import annotations

from gaia.cli.commands._classify import classify_ir, node_role

# ── Mermaid CSS class definitions (self-contained, not imported from _detailed_reasoning) ──

_MERMAID_STYLES = """\
    classDef setting fill:#f0f0f0,stroke:#999,color:#333
    classDef premise fill:#ddeeff,stroke:#4488bb,color:#333
    classDef derived fill:#ddffdd,stroke:#44bb44,color:#333
    classDef question fill:#fff3dd,stroke:#cc9944,color:#333
    classDef background fill:#f5f5f5,stroke:#bbb,stroke-dasharray: 5 5,color:#333
    classDef orphan fill:#fff,stroke:#ccc,stroke-dasharray: 5 5,color:#333
    classDef exported fill:#d4edda,stroke:#28a745,stroke-width:2px,color:#333
    classDef weak fill:#fff9c4,stroke:#f9a825,stroke-dasharray: 5 5,color:#333
    classDef contra fill:#ffebee,stroke:#c62828,color:#333"""

_ROLE_TO_CSS = {
    "setting": "setting",
    "question": "question",
    "derived": "derived",
    "structural": "derived",
    "independent": "premise",
    "background": "background",
    "orphaned": "orphan",
}

# Operators rendered with undirected (---) edges between variables
_UNDIRECTED_OPERATORS = frozenset({"equivalence", "contradiction", "complement", "implication"})

_OPERATOR_SYMBOLS = {
    "contradiction": "\u2297",
    "equivalence": "\u2261",
    "complement": "\u2295",
    "disjunction": "\u2228",
    "conjunction": "\u2227",
    "implication": "\u2192",
}

_DETERMINISTIC_STRATEGIES = frozenset(
    {
        "deduction",
        "reductio",
        "elimination",
        "mathematical_induction",
        "case_analysis",
    }
)


# ── Node selection (Task 6) ──


def select_simplified_nodes(
    beliefs: dict[str, float],
    priors: dict[str, float],
    exported_ids: set[str],
    max_nodes: int = 15,
) -> set[str]:
    """Select nodes for the simplified overview graph.

    1. Always include all exported conclusions
    2. Fill remaining slots with highest |belief - prior| nodes
    3. Cap at max_nodes
    """
    selected = set(exported_ids)
    candidates: list[tuple[float, str]] = []
    for kid, belief in beliefs.items():
        if kid in selected:
            continue
        prior = priors.get(kid, 0.5)
        delta = abs(belief - prior)
        candidates.append((delta, kid))
    candidates.sort(reverse=True)
    remaining = max_nodes - len(selected)
    for _, kid in candidates[: max(0, remaining)]:
        selected.add(kid)
    return selected


# ── Mermaid rendering (Task 7) ──


def _is_helper(label: str | None) -> bool:
    if not label:
        return True
    return label.startswith("__") or label.startswith("_anon")


def render_simplified_mermaid(
    ir: dict,
    beliefs: dict[str, float],
    priors: dict[str, float],
    exported_ids: set[str],
    max_nodes: int = 15,
) -> str:
    """Render a simplified Mermaid ``graph TD`` diagram.

    Each node shows ``Label ★ (prior → belief)`` for exported conclusions
    and ``Label (prior → belief)`` for others.  Only edges whose both
    endpoints are in the selected set are included.
    """
    selected = select_simplified_nodes(beliefs, priors, exported_ids, max_nodes)

    knowledge_by_id = {k["id"]: k for k in ir["knowledges"]}
    c = classify_ir(ir)

    lines = ["```mermaid", "graph TD"]
    _rendered_labels: set[str] = set()

    # Render knowledge nodes
    for k in ir["knowledges"]:
        kid = k["id"]
        if kid not in selected:
            continue
        label = k.get("label", "")
        if _is_helper(label):
            continue

        title = k.get("title") or label
        is_exported = kid in exported_ids
        star = " \u2605" if is_exported else ""

        prior_val = priors.get(kid, 0.5)
        belief_val = beliefs.get(kid, prior_val)
        annotation = f"{prior_val:.2f} \u2192 {belief_val:.2f}"

        display = f"{title}{star} ({annotation})"
        display = display.replace('"', "#quot;").replace("*", "#ast;")

        if is_exported:
            css = "exported"
        else:
            role = node_role(kid, k["type"], c)
            css = _ROLE_TO_CSS.get(role, "orphan")

        lines.append(f'    {label}["{display}"]:::{css}')
        _rendered_labels.add(label)

    # Render strategy edges between selected nodes
    for i, s in enumerate(ir.get("strategies", [])):
        conclusion = s.get("conclusion")
        if not conclusion or conclusion not in selected:
            continue
        conc_label = knowledge_by_id.get(conclusion, {}).get("label", "")
        if _is_helper(conc_label):
            continue

        stype = s.get("type", "")
        sid = f"strat_{i}"

        visible_premises: list[str] = []
        for p in s.get("premises", []):
            if p not in selected:
                continue
            p_label = knowledge_by_id.get(p, {}).get("label", "")
            if p_label and not _is_helper(p_label):
                visible_premises.append(p_label)

        visible_bg: list[str] = []
        for b in s.get("background") or []:
            if b not in selected:
                continue
            b_label = knowledge_by_id.get(b, {}).get("label", "")
            if b_label and not _is_helper(b_label):
                visible_bg.append(b_label)

        if not visible_premises and not visible_bg:
            continue

        css = "" if stype in _DETERMINISTIC_STRATEGIES else ":::weak"
        lines.append(f'    {sid}(["{stype}"]){css}')

        for p_label in visible_premises:
            lines.append(f"    {p_label} --> {sid}")
        for b_label in visible_bg:
            lines.append(f"    {b_label} -.-> {sid}")
        lines.append(f"    {sid} --> {conc_label}")

    # Render operator edges between selected nodes.
    # When an operator has at least one selected variable, pull in the
    # missing variables so the constraint renders completely.
    for i, o in enumerate(ir.get("operators", [])):
        conclusion = o.get("conclusion")
        conc_label = knowledge_by_id.get(conclusion, {}).get("label", "") if conclusion else ""
        conc_visible = conclusion and conclusion in selected and not _is_helper(conc_label)

        otype = o.get("operator", "")
        symbol = _OPERATOR_SYMBOLS.get(otype, otype)
        oid = f"oper_{i}"
        is_undirected = otype in _UNDIRECTED_OPERATORS

        # Collect all non-helper variable labels for this operator
        all_vars: list[tuple[str, str]] = []  # (kid, label)
        any_selected = False
        for v in o.get("variables", []):
            v_label = knowledge_by_id.get(v, {}).get("label", "")
            if v_label and not _is_helper(v_label):
                all_vars.append((v, v_label))
                if v in selected:
                    any_selected = True

        if not any_selected and not conc_visible:
            continue

        css = ":::contra" if otype == "contradiction" else ""
        lines.append(f'    {oid}{{{{"{symbol}"}}}}{css}')

        # Render all variables (pull in unselected ones so the constraint
        # is complete — e.g. both sides of a contradiction are shown)
        edge = " --- " if is_undirected else " --> "
        for v_kid, v_label in all_vars:
            # Ensure pulled-in nodes have a node definition
            if v_kid not in selected and v_label not in _rendered_labels:
                k = knowledge_by_id.get(v_kid, {})
                title = k.get("title") or v_label
                prior_val = priors.get(v_kid, 0.5)
                belief_val = beliefs.get(v_kid, prior_val)
                annotation = f"{prior_val:.2f} \u2192 {belief_val:.2f}"
                display = f"{title} ({annotation})"
                display = display.replace('"', "#quot;").replace("*", "#ast;")
                role = node_role(v_kid, k.get("type", "claim"), c)
                node_css = _ROLE_TO_CSS.get(role, "orphan")
                lines.append(f'    {v_label}["{display}"]:::{node_css}')
                _rendered_labels.add(v_label)
            lines.append(f"    {v_label}{edge}{oid}")
        if conc_visible:
            lines.append(f"    {oid}{edge}{conc_label}")

    lines.append("")
    lines.append(_MERMAID_STYLES)
    lines.append("```")
    return "\n".join(lines)
