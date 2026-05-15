"""Generate agent-optimized Wiki markdown pages from compiled IR."""

from __future__ import annotations

from typing import Any

from gaia.engine.inquiry._classify import classify_ir, node_role


def generate_wiki_home(ir: dict[str, Any], beliefs_data: dict[str, Any] | None = None) -> str:
    """Generate Wiki Home.md with package overview and claim index."""
    pkg = ir.get("package_name", "Package")
    lines = [f"# {pkg}", ""]

    # Module index
    modules: dict[str, list[dict[str, Any]]] = {}
    for k in ir["knowledges"]:
        mod = k.get("module", "Root")
        modules.setdefault(mod, []).append(k)

    lines.append("## Modules")
    lines.append("")
    for mod in modules:
        count = sum(1 for k in modules[mod] if not k.get("label", "").startswith("__"))
        page = f"Module-{mod.replace('_', '-')}"
        lines.append(f"- [{mod}]({page}) ({count} nodes)")
    lines.append("")

    # Claim index
    beliefs = {}
    if beliefs_data:
        beliefs = {b["knowledge_id"]: b["belief"] for b in beliefs_data.get("beliefs", [])}

    lines.append("## Claim Index")
    lines.append("")
    lines.append("| Label | Type | Module | Belief |")
    lines.append("|-------|------|--------|--------|")
    for k in ir["knowledges"]:
        label = k.get("label", "")
        if label.startswith("__"):
            continue
        kid = k["id"]
        ktype = k["type"]
        mod = k.get("module", "Root")
        belief = f"{beliefs[kid]:.2f}" if kid in beliefs else "\u2014"
        lines.append(f"| {label} | {ktype} | {mod} | {belief} |")

    lines.append("")
    return "\n".join(lines)


def generate_wiki_inference(
    ir: dict[str, Any],
    beliefs_data: dict[str, Any],
    param_data: dict[str, Any] | None = None,
) -> str:
    """Generate an Inference Results wiki page with diagnostics and a belief table.

    Shows convergence diagnostics and a full table of non-helper nodes sorted by
    belief descending, with columns: Label, Type, Prior, Belief, Role.
    """
    classification = classify_ir(ir)

    # Build lookup maps
    beliefs: dict[str, float] = {}
    belief_labels: dict[str, str] = {}
    if beliefs_data:
        for b in beliefs_data.get("beliefs", []):
            beliefs[b["knowledge_id"]] = b["belief"]
            if "label" in b:
                belief_labels[b["knowledge_id"]] = b["label"]

    priors: dict[str, float] = {}
    if param_data:
        priors = {p["knowledge_id"]: p["value"] for p in param_data.get("priors", [])}

    lines = ["# Inference Results", ""]

    # Diagnostics section
    diag = beliefs_data.get("diagnostics", {}) if beliefs_data else {}
    converged = diag.get("converged")
    iterations = diag.get("iterations_run")

    lines.append("## Diagnostics")
    lines.append("")
    if converged is not None:
        lines.append(f"- **Converged:** {'Yes' if converged else 'No'}")
    if iterations is not None:
        lines.append(f"- **Iterations:** {iterations}")
    lines.append("")

    # Belief table — sorted by belief descending, skip helpers
    knowledges = [k for k in ir["knowledges"] if not k.get("label", "").startswith("__")]
    knowledges.sort(key=lambda k: beliefs.get(k["id"], 0.0), reverse=True)

    lines.append("## Beliefs")
    lines.append("")
    lines.append("| Label | Type | Prior | Belief | Role |")
    lines.append("|-------|------|-------|--------|------|")

    for k in knowledges:
        kid = k["id"]
        label = k.get("label", kid)
        ktype = k["type"]
        role = node_role(kid, ktype, classification)
        prior = f"{priors[kid]:.2f}" if kid in priors else "\u2014"
        belief = f"{beliefs[kid]:.2f}" if kid in beliefs else "\u2014"
        lines.append(f"| {label} | {ktype} | {prior} | {belief} | {role} |")

    lines.append("")
    return "\n".join(lines)


def generate_all_wiki(
    ir: dict[str, Any],
    beliefs_data: dict[str, Any] | None = None,
    param_data: dict[str, Any] | None = None,
) -> dict[str, str]:
    """Generate all wiki pages and return them as ``{filename: markdown_content}``.

    Produces:
    - ``Home.md`` — package overview and claim index
    - ``Module-{name}.md`` — one page per unique module
    - ``Inference-Results.md`` — if *beliefs_data* is provided
    """
    pages: dict[str, str] = {}

    pages["Home.md"] = generate_wiki_home(ir, beliefs_data=beliefs_data)

    # Collect unique modules
    modules: set[str] = set()
    for k in ir["knowledges"]:
        modules.add(k.get("module", "Root"))

    for mod in sorted(modules):
        page_name = f"Module-{mod.replace('_', '-')}.md"
        pages[page_name] = generate_wiki_module(
            ir, mod, beliefs_data=beliefs_data, param_data=param_data
        )

    if beliefs_data is not None:
        pages["Inference-Results.md"] = generate_wiki_inference(
            ir, beliefs_data, param_data=param_data
        )

    return pages


def _beliefs_from_payload(beliefs_data: dict[str, Any] | None) -> dict[str, float]:
    """Extract knowledge beliefs from an optional beliefs payload."""
    if not beliefs_data:
        return {}
    return {b["knowledge_id"]: b["belief"] for b in beliefs_data.get("beliefs", [])}


def _priors_from_payload(param_data: dict[str, Any] | None) -> dict[str, float]:
    """Extract knowledge priors from an optional parameterization payload."""
    if not param_data:
        return {}
    return {p["knowledge_id"]: p["value"] for p in param_data.get("priors", [])}


def _strategy_indexes(
    ir: dict[str, Any],
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, list[dict[str, Any]]]]:
    """Index strategies by conclusion and premise."""
    by_conclusion: dict[str, list[dict[str, Any]]] = {}
    by_premise: dict[str, list[dict[str, Any]]] = {}
    for s in ir.get("strategies", []):
        conc = s.get("conclusion")
        if conc:
            by_conclusion.setdefault(conc, []).append(s)
        for p in s.get("premises", []):
            by_premise.setdefault(p, []).append(s)
    return by_conclusion, by_premise


def _operators_by_variable(ir: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    """Index operators by variable id."""
    operators_by_variable: dict[str, list[dict[str, Any]]] = {}
    for o in ir.get("operators", []):
        for v in o.get("variables", []):
            operators_by_variable.setdefault(v, []).append(o)
    return operators_by_variable


def _render_wiki_knowledge(
    *,
    knowledge: dict[str, Any],
    role: str,
    beliefs: dict[str, float],
    priors: dict[str, float],
    strategies_by_conclusion: dict[str, list[dict[str, Any]]],
    strategies_by_premise: dict[str, list[dict[str, Any]]],
    operators_by_variable: dict[str, list[dict[str, Any]]],
) -> list[str]:
    """Render one knowledge block for a wiki module page."""
    kid = knowledge["id"]
    label = knowledge.get("label", kid)
    lines = [
        f"### {label}",
        "",
        f"**QID:** `{kid}`",
        f"**Type:** {knowledge['type']}",
        f"**Role:** {role}",
        f"**Content:** {knowledge.get('content', '')}",
    ]
    if kid in priors:
        lines.append(f"**Prior:** {priors[kid]:.2f}")
    if kid in beliefs:
        lines.append(f"**Belief:** {beliefs[kid]:.2f}")
    lines.extend(_wiki_derivation_lines(kid, strategies_by_conclusion))
    lines.extend(_wiki_metadata_lines(knowledge))
    lines.extend(_wiki_reference_lines(kid, strategies_by_premise, operators_by_variable))
    lines.append("")
    return lines


def _wiki_derivation_lines(
    kid: str,
    strategies_by_conclusion: dict[str, list[dict[str, Any]]],
) -> list[str]:
    """Render derivation lines for strategies concluding a knowledge node."""
    lines: list[str] = []
    for strategy in strategies_by_conclusion.get(kid, []):
        stype = strategy.get("type", "unknown")
        lines.append(f"**Derived from:** {stype}")
        premises = strategy.get("premises", [])
        if premises:
            lines.append(f"**Premises:** {', '.join(f'`{p}`' for p in premises)}")
        reason = strategy.get("reason", "")
        if reason:
            lines.append(f"**Reasoning:** {reason}")
    return lines


def _wiki_metadata_lines(knowledge: dict[str, Any]) -> list[str]:
    """Render metadata lines for a knowledge node."""
    return [f"**{mk}:** {mv}" for mk, mv in (knowledge.get("metadata", {}) or {}).items()]


def _wiki_reference_lines(
    kid: str,
    strategies_by_premise: dict[str, list[dict[str, Any]]],
    operators_by_variable: dict[str, list[dict[str, Any]]],
) -> list[str]:
    """Render reverse-reference lines for a knowledge node."""
    refs: list[str] = []
    for strategy in strategies_by_premise.get(kid, []):
        refs.append(f"{strategy.get('type', 'unknown')} -> `{strategy.get('conclusion', '?')}`")
    for operator in operators_by_variable.get(kid, []):
        refs.append(f"{operator.get('type', 'unknown')} -> `{operator.get('conclusion', '?')}`")
    return [f"**Referenced by:** {'; '.join(refs)}"] if refs else []


def generate_wiki_module(
    ir: dict[str, Any],
    module_name: str,
    *,
    beliefs_data: dict[str, Any] | None = None,
    param_data: dict[str, Any] | None = None,
) -> str:
    """Generate a structured Wiki page for a single module.

    Each non-helper knowledge node gets: QID, type, role, content, prior,
    belief, derivation info, reasoning, metadata, and cross-references.
    """
    classification = classify_ir(ir)

    beliefs = _beliefs_from_payload(beliefs_data)
    priors = _priors_from_payload(param_data)
    strategies_by_conclusion, strategies_by_premise = _strategy_indexes(ir)
    operators_by_variable = _operators_by_variable(ir)

    # Filter knowledges for this module, skip helpers
    module_knowledges = [
        k
        for k in ir["knowledges"]
        if k.get("module", "Root") == module_name and not k.get("label", "").startswith("__")
    ]

    lines = [f"# Module: {module_name}", ""]

    for k in module_knowledges:
        kid = k["id"]
        ktype = k["type"]
        role = node_role(kid, ktype, classification)
        lines.extend(
            _render_wiki_knowledge(
                knowledge=k,
                role=role,
                beliefs=beliefs,
                priors=priors,
                strategies_by_conclusion=strategies_by_conclusion,
                strategies_by_premise=strategies_by_premise,
                operators_by_variable=operators_by_variable,
            )
        )

    return "\n".join(lines)
