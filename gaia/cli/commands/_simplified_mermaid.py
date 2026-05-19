"""Simplified Mermaid graph for GitHub wiki overview pages.

Selects a bounded set of the most informative nodes and renders a compact
``graph TD`` diagram with prior → belief annotations.
"""

from __future__ import annotations

from typing import Any

from gaia.engine.inquiry._classify import KnowledgeClassification, classify_ir, node_role

# ── Mermaid CSS class definitions (self-contained, not imported from _detailed_reasoning) ──

_MERMAID_STYLES = """\
    classDef note fill:#f0f0f0,stroke:#999,color:#333
    classDef premise fill:#ddeeff,stroke:#4488bb,color:#333
    classDef derived fill:#ddffdd,stroke:#44bb44,color:#333
    classDef question fill:#fff3dd,stroke:#cc9944,color:#333
    classDef background fill:#f5f5f5,stroke:#bbb,stroke-dasharray: 5 5,color:#333
    classDef orphan fill:#fff,stroke:#ccc,stroke-dasharray: 5 5,color:#333
    classDef exported fill:#d4edda,stroke:#28a745,stroke-width:2px,color:#333
    classDef weak fill:#fff9c4,stroke:#f9a825,stroke-dasharray: 5 5,color:#333
    classDef contra fill:#ffebee,stroke:#c62828,color:#333"""

_ROLE_TO_CSS = {
    "note": "note",
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
    "negation": "\u00ac",
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


def _knowledge_by_id(ir: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Return knowledge nodes keyed by id."""
    return {k["id"]: k for k in ir["knowledges"]}


def _render_selected_knowledge_nodes(
    *,
    ir: dict[str, Any],
    selected: set[str],
    exported_ids: set[str],
    beliefs: dict[str, float],
    priors: dict[str, float],
    classification: KnowledgeClassification,
) -> tuple[list[str], set[str]]:
    """Render selected non-helper knowledge nodes."""
    lines: list[str] = []
    rendered_labels: set[str] = set()
    for k in ir["knowledges"]:
        kid = k["id"]
        if kid not in selected:
            continue
        label = k.get("label", "")
        if _is_helper(label):
            continue
        title = k.get("title") or label
        is_exported = kid in exported_ids
        prior_val = priors.get(kid, 0.5)
        annotation = f"{prior_val:.2f} \u2192 {beliefs.get(kid, prior_val):.2f}"
        star = " \u2605" if is_exported else ""
        display = f"{title}{star} ({annotation})"
        display = display.replace('"', "#quot;").replace("*", "#ast;")
        css = (
            "exported"
            if is_exported
            else _ROLE_TO_CSS.get(node_role(kid, k["type"], classification), "orphan")
        )
        lines.append(f'    {label}["{display}"]:::{css}')
        rendered_labels.add(label)
    return lines, rendered_labels


def _visible_strategy_labels(
    ids: list[str],
    *,
    selected: set[str],
    knowledge_by_id: dict[str, dict[str, Any]],
) -> list[str]:
    """Return selected non-helper labels for strategy endpoint ids."""
    labels: list[str] = []
    for kid in ids:
        if kid not in selected:
            continue
        label = knowledge_by_id.get(kid, {}).get("label", "")
        if label and not _is_helper(label):
            labels.append(label)
    return labels


def _render_strategy_edges(
    *,
    ir: dict[str, Any],
    selected: set[str],
    knowledge_by_id: dict[str, dict[str, Any]],
) -> list[str]:
    """Render selected strategy edges for simplified Mermaid."""
    lines: list[str] = []
    for i, strategy in enumerate(ir.get("strategies", [])):
        conclusion = strategy.get("conclusion")
        if not conclusion or conclusion not in selected:
            continue
        conc_label = knowledge_by_id.get(conclusion, {}).get("label", "")
        if _is_helper(conc_label):
            continue
        visible_premises = _visible_strategy_labels(
            strategy.get("premises", []), selected=selected, knowledge_by_id=knowledge_by_id
        )
        visible_bg = _visible_strategy_labels(
            strategy.get("background") or [], selected=selected, knowledge_by_id=knowledge_by_id
        )
        if not visible_premises and not visible_bg:
            continue
        stype = strategy.get("type", "")
        sid = f"strat_{i}"
        css = "" if stype in _DETERMINISTIC_STRATEGIES else ":::weak"
        lines.append(f'    {sid}(["{stype}"]){css}')
        lines.extend(f"    {label} --> {sid}" for label in visible_premises)
        lines.extend(f"    {label} -.-> {sid}" for label in visible_bg)
        lines.append(f"    {sid} --> {conc_label}")
    return lines


def _render_pulled_node(
    *,
    kid: str,
    label: str,
    knowledge_by_id: dict[str, dict[str, Any]],
    beliefs: dict[str, float],
    priors: dict[str, float],
    classification: KnowledgeClassification,
) -> str:
    """Render an unselected operator variable pulled into the graph."""
    k = knowledge_by_id.get(kid, {})
    title = k.get("title") or label
    prior_val = priors.get(kid, 0.5)
    belief_val = beliefs.get(kid, prior_val)
    display = f"{title} ({prior_val:.2f} \u2192 {belief_val:.2f})"
    display = display.replace('"', "#quot;").replace("*", "#ast;")
    role = node_role(kid, k.get("type", "claim"), classification)
    return f'    {label}["{display}"]:::{_ROLE_TO_CSS.get(role, "orphan")}'


def _render_operator_edges(
    *,
    ir: dict[str, Any],
    selected: set[str],
    knowledge_by_id: dict[str, dict[str, Any]],
    rendered_labels: set[str],
    beliefs: dict[str, float],
    priors: dict[str, float],
    classification: KnowledgeClassification,
) -> list[str]:
    """Render selected operator constraints for simplified Mermaid."""
    lines: list[str] = []
    for i, operator in enumerate(ir.get("operators", [])):
        lines.extend(
            _render_one_operator(
                i=i,
                operator=operator,
                selected=selected,
                knowledge_by_id=knowledge_by_id,
                rendered_labels=rendered_labels,
                beliefs=beliefs,
                priors=priors,
                classification=classification,
            )
        )
    return lines


def _render_one_operator(
    *,
    i: int,
    operator: dict[str, Any],
    selected: set[str],
    knowledge_by_id: dict[str, dict[str, Any]],
    rendered_labels: set[str],
    beliefs: dict[str, float],
    priors: dict[str, float],
    classification: KnowledgeClassification,
) -> list[str]:
    """Render one operator node and its variable/conclusion edges."""
    conclusion = operator.get("conclusion")
    conc_label = knowledge_by_id.get(conclusion, {}).get("label", "") if conclusion else ""
    conc_visible = bool(conclusion and conclusion in selected and not _is_helper(conc_label))
    variables = _operator_visible_variables(operator, selected, knowledge_by_id)
    if not variables.any_selected and not conc_visible:
        return []

    otype = operator.get("operator", "")
    oid = f"oper_{i}"
    edge = " --- " if otype in _UNDIRECTED_OPERATORS else " --> "
    css = ":::contra" if otype == "contradiction" else ""
    lines = [f'    {oid}{{{{"{_OPERATOR_SYMBOLS.get(otype, otype)}"}}}}{css}']
    for kid, label in variables.all_vars:
        if kid not in selected and label not in rendered_labels:
            lines.append(
                _render_pulled_node(
                    kid=kid,
                    label=label,
                    knowledge_by_id=knowledge_by_id,
                    beliefs=beliefs,
                    priors=priors,
                    classification=classification,
                )
            )
            rendered_labels.add(label)
        lines.append(f"    {label}{edge}{oid}")
    if conc_visible:
        lines.append(f"    {oid}{edge}{conc_label}")
    return lines


class _OperatorVariables:
    """Visible operator variables plus whether any were selected."""

    def __init__(self, all_vars: list[tuple[str, str]], any_selected: bool) -> None:
        self.all_vars = all_vars
        self.any_selected = any_selected


def _operator_visible_variables(
    operator: dict[str, Any],
    selected: set[str],
    knowledge_by_id: dict[str, dict[str, Any]],
) -> _OperatorVariables:
    """Collect non-helper operator variable labels."""
    all_vars: list[tuple[str, str]] = []
    any_selected = False
    for variable in operator.get("variables", []):
        label = knowledge_by_id.get(variable, {}).get("label", "")
        if label and not _is_helper(label):
            all_vars.append((variable, label))
            any_selected = any_selected or variable in selected
    return _OperatorVariables(all_vars, any_selected)


def render_simplified_mermaid(
    ir: dict[str, Any],
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

    knowledge_by_id = _knowledge_by_id(ir)
    classification = classify_ir(ir)

    lines = ["```mermaid", "graph TD"]
    knowledge_lines, rendered_labels = _render_selected_knowledge_nodes(
        ir=ir,
        selected=selected,
        exported_ids=exported_ids,
        beliefs=beliefs,
        priors=priors,
        classification=classification,
    )
    lines.extend(knowledge_lines)
    lines.extend(
        _render_strategy_edges(
            ir=ir,
            selected=selected,
            knowledge_by_id=knowledge_by_id,
        )
    )
    lines.extend(
        _render_operator_edges(
            ir=ir,
            selected=selected,
            knowledge_by_id=knowledge_by_id,
            rendered_labels=rendered_labels,
            beliefs=beliefs,
            priors=priors,
            classification=classification,
        )
    )

    lines.append("")
    lines.append(_MERMAID_STYLES)
    lines.append("```")
    return "\n".join(lines)
