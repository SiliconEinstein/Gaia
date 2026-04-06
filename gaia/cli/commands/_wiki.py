"""Generate agent-optimized Wiki markdown pages from compiled IR."""

from __future__ import annotations

from gaia.cli.commands._classify import classify_ir, node_role


def generate_wiki_home(ir: dict, beliefs_data: dict | None = None) -> str:
    """Generate Wiki Home.md with package overview and claim index."""
    pkg = ir.get("package_name", "Package")
    lines = [f"# {pkg}", ""]

    # Module index
    modules: dict[str, list[dict]] = {}
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
    ir: dict,
    beliefs_data: dict,
    param_data: dict | None = None,
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
    ir: dict,
    beliefs_data: dict | None = None,
    param_data: dict | None = None,
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


def generate_wiki_module(
    ir: dict,
    module_name: str,
    *,
    beliefs_data: dict | None = None,
    param_data: dict | None = None,
) -> str:
    """Generate a structured Wiki page for a single module.

    Each non-helper knowledge node gets: QID, type, role, content, prior,
    belief, derivation info, reasoning, metadata, and cross-references.
    """
    classification = classify_ir(ir)

    # Build lookup maps
    beliefs: dict[str, float] = {}
    if beliefs_data:
        beliefs = {b["knowledge_id"]: b["belief"] for b in beliefs_data.get("beliefs", [])}

    priors: dict[str, float] = {}
    if param_data:
        priors = {p["knowledge_id"]: p["value"] for p in param_data.get("priors", [])}

    # Index strategies by conclusion and by premise for cross-references
    strategies_by_conclusion: dict[str, list[dict]] = {}
    strategies_by_premise: dict[str, list[dict]] = {}
    for s in ir.get("strategies", []):
        conc = s.get("conclusion")
        if conc:
            strategies_by_conclusion.setdefault(conc, []).append(s)
        for p in s.get("premises", []):
            strategies_by_premise.setdefault(p, []).append(s)

    # Index operators by premise/variable for cross-references
    operators_by_variable: dict[str, list[dict]] = {}
    for o in ir.get("operators", []):
        for v in o.get("variables", []):
            operators_by_variable.setdefault(v, []).append(o)

    # Filter knowledges for this module, skip helpers
    module_knowledges = [
        k
        for k in ir["knowledges"]
        if k.get("module", "Root") == module_name and not k.get("label", "").startswith("__")
    ]

    lines = [f"# Module: {module_name}", ""]

    for k in module_knowledges:
        kid = k["id"]
        label = k.get("label", kid)
        ktype = k["type"]
        content = k.get("content", "")
        role = node_role(kid, ktype, classification)

        lines.append(f"### {label}")
        lines.append("")
        lines.append(f"**QID:** `{kid}`")
        lines.append(f"**Type:** {ktype}")
        lines.append(f"**Role:** {role}")
        lines.append(f"**Content:** {content}")

        # Prior
        if kid in priors:
            lines.append(f"**Prior:** {priors[kid]:.2f}")

        # Belief
        if kid in beliefs:
            lines.append(f"**Belief:** {beliefs[kid]:.2f}")

        # Derivation info (strategies where this node is the conclusion)
        if kid in strategies_by_conclusion:
            for s in strategies_by_conclusion[kid]:
                stype = s.get("type", "unknown")
                lines.append(f"**Derived from:** {stype}")
                premises = s.get("premises", [])
                if premises:
                    lines.append(f"**Premises:** {', '.join(f'`{p}`' for p in premises)}")
                reason = s.get("reason", "")
                if reason:
                    lines.append(f"**Reasoning:** {reason}")

        # Metadata
        metadata = k.get("metadata", {})
        if metadata:
            for mk, mv in metadata.items():
                lines.append(f"**{mk}:** {mv}")

        # Referenced by: strategies/operators where this node appears as a premise/variable
        refs: list[str] = []
        if kid in strategies_by_premise:
            for s in strategies_by_premise[kid]:
                conc = s.get("conclusion", "?")
                stype = s.get("type", "unknown")
                refs.append(f"{stype} -> `{conc}`")
        if kid in operators_by_variable:
            for o in operators_by_variable[kid]:
                conc = o.get("conclusion", "?")
                otype = o.get("type", "unknown")
                refs.append(f"{otype} -> `{conc}`")
        if refs:
            lines.append(f"**Referenced by:** {'; '.join(refs)}")

        lines.append("")

    return "\n".join(lines)
