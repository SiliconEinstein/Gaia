"""Generate Obsidian vault from compiled IR.

Produces a dict mapping vault-relative paths to markdown content,
organized as: conclusions/, evidence/, modules/, reasoning/, meta/,
plus _index.md, overview.md, and .obsidian/ config.
"""

from __future__ import annotations

import json

from gaia.cli.commands._classify import classify_ir, node_role
from gaia.cli.commands._detailed_reasoning import render_mermaid


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _is_helper(label: str | None) -> bool:
    if not label:
        return True
    return label.startswith("__") or label.startswith("_anon")


def _build_page_set(
    conclusions: list[dict],
    evidence: list[dict],
    module_inlined: list[dict],
) -> tuple[set[str], dict[str, str]]:
    """Build (ids_with_pages, id_to_module) for wikilink resolution.

    Returns:
    - ids_with_pages: set of knowledge IDs that have their own page
    - inlined_id_to_module: kid → module name for nodes inlined in module pages
    """
    ids_with_pages: set[str] = set()
    for k in conclusions:
        ids_with_pages.add(k["id"])
    for k in evidence:
        ids_with_pages.add(k["id"])

    inlined_id_to_module: dict[str, str] = {}
    for k in module_inlined:
        inlined_id_to_module[k["id"]] = k.get("module", "Root")

    return ids_with_pages, inlined_id_to_module


def _wikilink(
    kid: str,
    label_for_id: dict[str, str],
    ids_with_pages: set[str],
    inlined_id_to_module: dict[str, str],
) -> str:
    """Generate a wikilink for a knowledge ID.

    If the target has its own page: ``[[label]]``
    If the target is inlined in a module page: ``[[module#label|label]]``
    Otherwise: plain ``label`` (no link).
    """
    label = label_for_id.get(kid, kid.split("::")[-1])
    if kid in ids_with_pages:
        return f"[[{label}]]"
    if kid in inlined_id_to_module:
        mod = inlined_id_to_module[kid]
        return f"[[{mod}#{label}|{label}]]"
    return label


def _is_complex_strategy(s: dict) -> bool:
    """A strategy gets its own page if complex (induction/elimination/case_analysis or ≥3 premises)."""
    complex_types = {"induction", "elimination", "case_analysis"}
    return s.get("type") in complex_types or len(s.get("premises", [])) >= 3


def _render_frontmatter(fields: dict) -> str:
    """Render YAML frontmatter block."""
    lines = ["---"]
    for key, value in fields.items():
        if value is None:
            lines.append(f"{key}: null")
        elif isinstance(value, bool):
            lines.append(f"{key}: {'true' if value else 'false'}")
        elif isinstance(value, list):
            if not value:
                lines.append(f"{key}: []")
            else:
                lines.append(f"{key}: [{', '.join(str(v) for v in value)}]")
        elif isinstance(value, (int, float)):
            lines.append(f"{key}: {value}")
        else:
            s = str(value)
            if any(c in s for c in ":#{}[]|>&*!%@`"):
                lines.append(f'{key}: "{s}"')
            else:
                lines.append(f"{key}: {s}")
    lines.append("---")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------


def _classify_pages(
    ir: dict,
) -> tuple[list[dict], list[dict], list[dict]]:
    """Classify knowledge nodes into page categories.

    Returns (conclusions, evidence, module_inlined) where:
    - conclusions: exported claims + questions → own pages in conclusions/
    - evidence: leaf premises (premise but not conclusion, not setting) → evidence/
    - module_inlined: non-exported derived claims + settings → inlined in modules/
    """
    classification = classify_ir(ir)
    conclusions: list[dict] = []
    evidence: list[dict] = []
    module_inlined: list[dict] = []

    for k in ir["knowledges"]:
        label = k.get("label", "")
        if _is_helper(label):
            continue

        kid = k["id"]
        ktype = k["type"]

        if ktype == "question" or (ktype == "claim" and k.get("exported")):
            conclusions.append(k)
        elif ktype == "setting":
            module_inlined.append(k)
        elif kid in classification.strategy_conclusions:
            module_inlined.append(k)
        else:
            evidence.append(k)

    return conclusions, evidence, module_inlined


# ---------------------------------------------------------------------------
# Page generators
# ---------------------------------------------------------------------------


def _generate_claim_page(
    k: dict,
    beliefs: dict[str, float],
    priors: dict[str, float],
    strategies_by_conclusion: dict[str, list[dict]],
    strategies_by_premise: dict[str, list[dict]],
    label_for_id: dict[str, str],
    ids_with_pages: set[str],
    inlined_id_to_module: dict[str, str],
) -> str:
    """Generate a conclusion page (exported claim or question)."""
    kid = k["id"]
    label = k.get("label", "")
    title = k.get("title") or label.replace("_", " ")
    content = k.get("content", "")
    module = k.get("module", "Root")

    def wl(target_id: str) -> str:
        return _wikilink(target_id, label_for_id, ids_with_pages, inlined_id_to_module)

    strategy_for = strategies_by_conclusion.get(kid, [])
    strategy_type = strategy_for[0]["type"] if strategy_for else None
    premise_count = len(strategy_for[0]["premises"]) if strategy_for else 0

    fm = _render_frontmatter(
        {
            "type": k["type"],
            "label": label,
            "qid": kid,
            "module": module,
            "exported": k.get("exported", False),
            "prior": priors.get(kid),
            "belief": beliefs.get(kid),
            "strategy_type": strategy_type,
            "premise_count": premise_count,
            "tags": [k["type"], module.replace("_", "-")],
        }
    )

    lines = [fm, "", f"# {title}", "", f"> {content}", ""]

    # Derivation
    if strategy_for:
        s = strategy_for[0]
        stype = s["type"]
        sid = s.get("strategy_id", "")
        s_label = label_for_id.get(sid, sid)
        lines.append("## Derivation")
        if _is_complex_strategy(s):
            lines.append(f"- **Strategy**: [[{s_label}]] ({stype})")
        else:
            lines.append(f"- **Strategy**: {stype}")
        premises = s.get("premises", [])
        if premises:
            lines.append("- **Premises**:")
            for p in premises:
                lines.append(f"  - {wl(p)}")
        reason = (s.get("metadata") or {}).get("reason", "") or s.get("reason", "")
        if reason:
            lines.append("")
            lines.append("> [!REASONING]")
            lines.append(f"> {reason}")
        lines.append("")

    # Supports
    if kid in strategies_by_premise:
        lines.append("## Supports")
        for s in strategies_by_premise[kid]:
            conc = s.get("conclusion", "")
            lines.append(f"- → {wl(conc)} via {s['type']}")
        lines.append("")

    # Module link
    lines.append("## Module")
    lines.append(f"[[{module}]]")
    lines.append("")

    return "\n".join(lines)


def _generate_evidence_page(
    k: dict,
    beliefs: dict[str, float],
    priors: dict[str, float],
    strategies_by_premise: dict[str, list[dict]],
    label_for_id: dict[str, str],
    ids_with_pages: set[str],
    inlined_id_to_module: dict[str, str],
) -> str:
    """Generate an evidence page (leaf premise)."""
    kid = k["id"]
    label = k.get("label", "")
    title = k.get("title") or label.replace("_", " ")
    content = k.get("content", "")
    module = k.get("module", "Root")

    def wl(target_id: str) -> str:
        return _wikilink(target_id, label_for_id, ids_with_pages, inlined_id_to_module)

    fm = _render_frontmatter(
        {
            "type": "evidence",
            "label": label,
            "qid": kid,
            "module": module,
            "prior": priors.get(kid),
            "belief": beliefs.get(kid),
            "tags": ["evidence", module.replace("_", "-")],
        }
    )

    lines = [fm, "", f"# {title}", "", f"> {content}", ""]

    if kid in strategies_by_premise:
        lines.append("## Supports")
        for s in strategies_by_premise[kid]:
            conc = s.get("conclusion", "")
            lines.append(f"- → {wl(conc)} via {s['type']}")
        lines.append("")

    lines.append("## Module")
    lines.append(f"[[{module}]]")
    lines.append("")

    return "\n".join(lines)


def _generate_module_page(
    module_name: str,
    ir: dict,
    beliefs: dict[str, float],
    priors: dict[str, float],
    strategies_by_conclusion: dict[str, list[dict]],
    label_for_id: dict[str, str],
    ids_with_pages: set[str],
    inlined_id_to_module: dict[str, str],
    module_title: str | None = None,
) -> str:
    """Generate a module page with inlined non-exported claims and settings."""
    title = module_title or module_name.replace("_", " ").title()

    def wl(target_id: str) -> str:
        return _wikilink(target_id, label_for_id, ids_with_pages, inlined_id_to_module)

    module_nodes = [
        k
        for k in ir["knowledges"]
        if k.get("module", "Root") == module_name and not _is_helper(k.get("label", ""))
    ]

    exported_count = sum(1 for k in module_nodes if k.get("exported"))

    fm = _render_frontmatter(
        {
            "type": "module",
            "label": module_name,
            "title": title,
            "claim_count": len(module_nodes),
            "exported_count": exported_count,
            "tags": ["module", module_name.replace("_", "-")],
        }
    )

    lines = [fm, "", f"# {title}", "", "## Claims", ""]

    for k in module_nodes:
        kid = k["id"]
        label = k.get("label", "")
        content = k.get("content", "")
        is_exported = k.get("exported", False)

        if is_exported or k["type"] == "question":
            star = " ★" if is_exported else ""
            prior_str = f"{priors[kid]:.2f}" if kid in priors else "—"
            belief_str = f"{beliefs[kid]:.2f}" if kid in beliefs else "—"
            lines.append(f"### [[{label}]]{star}")
            lines.append(f"> {content}")
            lines.append("")
            lines.append(f"Prior: {prior_str} → Belief: {belief_str}")
            lines.append("")
        else:
            lines.append(f"### {label}")
            lines.append(f"> {content}")
            lines.append("")
            if kid in strategies_by_conclusion:
                s = strategies_by_conclusion[kid][0]
                premises = s.get("premises", [])
                lines.append(f"Derived via {s['type']} from: " + ", ".join(wl(p) for p in premises))
                lines.append("")

    return "\n".join(lines)


def _generate_strategy_page(
    s: dict,
    label_for_id: dict[str, str],
    ids_with_pages: set[str],
    inlined_id_to_module: dict[str, str],
) -> str:
    """Generate a reasoning page for a complex strategy."""
    sid = s.get("strategy_id", "")
    stype = s.get("type", "unknown")
    s_label = sid.removeprefix("lcs_") if sid else stype
    conc = s.get("conclusion", "")
    conc_label = label_for_id.get(conc, conc.split("::")[-1])
    premises = s.get("premises", [])

    def wl(target_id: str) -> str:
        return _wikilink(target_id, label_for_id, ids_with_pages, inlined_id_to_module)

    fm = _render_frontmatter(
        {
            "type": "strategy",
            "strategy_type": stype,
            "label": s_label,
            "premise_count": len(premises),
            "conclusion": conc_label,
            "tags": ["strategy", stype],
        }
    )

    lines = [fm, "", f"# {stype}: {s_label}", ""]
    lines.append(f"**Conclusion:** {wl(conc)}")
    lines.append("")

    if premises:
        lines.append("## Premises")
        for p in premises:
            lines.append(f"- {wl(p)}")
        lines.append("")

    reason = (s.get("metadata") or {}).get("reason", "") or s.get("reason", "")
    if reason:
        lines.append("## Reasoning")
        lines.append(reason)
        lines.append("")

    return "\n".join(lines)


def _generate_beliefs_page(
    ir: dict,
    beliefs: dict[str, float],
    priors: dict[str, float],
    label_for_id: dict[str, str],
    ids_with_pages: set[str],
    inlined_id_to_module: dict[str, str],
) -> str:
    """Generate meta/beliefs.md with a sortable belief table."""
    classification = classify_ir(ir)
    lines = ["---", "type: meta", "tags: [meta, beliefs]", "---", "", "# Beliefs", ""]
    lines.append("| Label | Type | Prior | Belief | Role |")
    lines.append("|-------|------|-------|--------|------|")

    knowledges = [k for k in ir["knowledges"] if not _is_helper(k.get("label", ""))]
    knowledges.sort(key=lambda k: beliefs.get(k["id"], 0.0), reverse=True)

    for k in knowledges:
        kid = k["id"]
        ktype = k["type"]
        role = node_role(kid, ktype, classification)
        prior = f"{priors[kid]:.2f}" if kid in priors else "—"
        belief = f"{beliefs[kid]:.2f}" if kid in beliefs else "—"
        link = _wikilink(kid, label_for_id, ids_with_pages, inlined_id_to_module)
        lines.append(f"| {link} | {ktype} | {prior} | {belief} | {role} |")

    lines.append("")
    return "\n".join(lines)


def _generate_holes_page(evidence_nodes: list[dict]) -> str:
    """Generate meta/holes.md listing all leaf premises."""
    lines = ["---", "type: meta", "tags: [meta, holes]", "---", "", "# Leaf Premises (Holes)", ""]
    lines.append("| Label | Module | Content |")
    lines.append("|-------|--------|---------|")
    for k in evidence_nodes:
        label = k.get("label", "")
        module = k.get("module", "Root")
        content = k.get("content", "")
        if len(content) > 60:
            content = content[:60] + "..."
        lines.append(f"| [[{label}]] | [[{module}]] | {content} |")
    lines.append("")
    return "\n".join(lines)


def _generate_index(
    ir: dict,
    conclusions: list[dict],
    evidence: list[dict],
    beliefs: dict[str, float],
    modules: dict[str, str | None],
) -> str:
    """Generate _index.md — master navigation page."""
    pkg = ir.get("package_name", "Package")
    ir_hash = ir.get("ir_hash", "unknown")

    all_k = ir["knowledges"]
    n_claims = sum(1 for k in all_k if k["type"] == "claim")
    n_settings = sum(1 for k in all_k if k["type"] == "setting")
    n_questions = sum(1 for k in all_k if k["type"] == "question")
    n_strategies = len(ir.get("strategies", []))
    n_operators = len(ir.get("operators", []))
    n_exported = sum(1 for k in all_k if k.get("exported"))

    lines = [f"# {pkg}", ""]
    if ir_hash and ir_hash != "unknown":
        lines.append(f"IR hash: `{ir_hash[:16]}...`")
        lines.append("")

    lines.append("## Statistics")
    lines.append("")
    lines.append("| Metric | Count |")
    lines.append("|--------|-------|")
    lines.append(
        f"| Knowledge nodes | {len(all_k)}"
        f" ({n_claims} claims, {n_settings} settings, {n_questions} questions) |"
    )
    lines.append(f"| Strategies | {n_strategies} |")
    lines.append(f"| Operators | {n_operators} |")
    lines.append(f"| Modules | {len(modules)} |")
    lines.append(f"| Exported conclusions | {n_exported} |")
    lines.append(f"| Leaf premises | {len(evidence)} |")
    lines.append("")

    # Module navigation
    lines.append("## Modules")
    lines.append("")
    lines.append("| Module | Claims |")
    lines.append("|--------|--------|")
    for mod in modules:
        count = sum(
            1
            for k in all_k
            if k.get("module", "Root") == mod and not _is_helper(k.get("label", ""))
        )
        lines.append(f"| [[{mod}]] | {count} |")
    lines.append("")

    # Exported conclusions
    exported = [k for k in conclusions if k.get("exported")]
    if exported:
        lines.append("## Exported Conclusions")
        lines.append("")
        lines.append("| Conclusion | Belief | Module |")
        lines.append("|------------|--------|--------|")
        for k in exported:
            label = k.get("label", "")
            mod = k.get("module", "Root")
            belief = f"{beliefs[k['id']]:.2f}" if k["id"] in beliefs else "—"
            lines.append(f"| [[{label}]] | {belief} | [[{mod}]] |")
        lines.append("")

    # Quick links
    lines.append("## Quick Links")
    lines.append("")
    lines.append("- [[overview]] — Reasoning graph")
    if beliefs:
        lines.append("- [[meta/beliefs]] — Full belief table")
    lines.append("- [[meta/holes]] — Leaf premises")
    lines.append("")

    return "\n".join(lines)


def _generate_overview(ir: dict) -> str:
    """Generate overview.md with Mermaid reasoning graph."""
    pkg = ir.get("package_name", "Package")
    lines = ["---", "type: overview", "tags: [overview]", "---", ""]
    lines.append(f"# {pkg} — Overview")
    lines.append("")
    lines.append(render_mermaid(ir))
    lines.append("")
    return "\n".join(lines)


def _generate_obsidian_config() -> str:
    """Generate .obsidian/graph.json with color groups by node type."""
    config = {
        "collapse-filter": False,
        "search": "",
        "showTags": False,
        "showAttachments": False,
        "hideUnresolved": False,
        "colorGroups": [
            {"query": "tag:#claim", "color": {"a": 1, "rgb": 5025616}},
            {"query": "tag:#setting", "color": {"a": 1, "rgb": 8421504}},
            {"query": "tag:#question", "color": {"a": 1, "rgb": 16750848}},
            {"query": "tag:#module", "color": {"a": 1, "rgb": 65280}},
            {"query": "tag:#strategy", "color": {"a": 1, "rgb": 16711680}},
            {"query": "tag:#evidence", "color": {"a": 1, "rgb": 255}},
            {"query": "tag:#meta", "color": {"a": 1, "rgb": 11184810}},
        ],
    }
    return json.dumps(config, indent=2)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def generate_obsidian_vault(
    ir: dict,
    *,
    beliefs_data: dict | None = None,
    param_data: dict | None = None,
) -> dict[str, str]:
    """Generate Obsidian vault pages as {vault_path: markdown_content}.

    Returns a dict mapping vault-relative file paths to markdown content.
    The caller writes these to ``.gaia-wiki/`` on disk.
    """
    pages: dict[str, str] = {}

    # Build lookup maps
    beliefs: dict[str, float] = {}
    if beliefs_data:
        beliefs = {b["knowledge_id"]: b["belief"] for b in beliefs_data.get("beliefs", [])}
    priors: dict[str, float] = {}
    if param_data:
        priors = {p["knowledge_id"]: p["value"] for p in param_data.get("priors", [])}

    # Strategy indexes
    strategies_by_conclusion: dict[str, list[dict]] = {}
    strategies_by_premise: dict[str, list[dict]] = {}
    for s in ir.get("strategies", []):
        conc = s.get("conclusion")
        if conc:
            strategies_by_conclusion.setdefault(conc, []).append(s)
        for p in s.get("premises", []):
            strategies_by_premise.setdefault(p, []).append(s)

    # Label lookup: kid/strategy_id → label
    label_for_id: dict[str, str] = {}
    for k in ir["knowledges"]:
        label_for_id[k["id"]] = k.get("label", k["id"].split("::")[-1])
    for s in ir.get("strategies", []):
        sid = s.get("strategy_id", "")
        if sid:
            label_for_id[sid] = sid.removeprefix("lcs_")

    # Classify nodes
    conclusions, evidence, module_inlined = _classify_pages(ir)

    # Build page-ownership map for wikilink resolution
    ids_with_pages, inlined_id_to_module = _build_page_set(conclusions, evidence, module_inlined)

    # Conclusion pages
    for k in conclusions:
        label = k.get("label", "")
        pages[f"conclusions/{label}.md"] = _generate_claim_page(
            k,
            beliefs,
            priors,
            strategies_by_conclusion,
            strategies_by_premise,
            label_for_id,
            ids_with_pages,
            inlined_id_to_module,
        )

    # Evidence pages
    for k in evidence:
        label = k.get("label", "")
        pages[f"evidence/{label}.md"] = _generate_evidence_page(
            k,
            beliefs,
            priors,
            strategies_by_premise,
            label_for_id,
            ids_with_pages,
            inlined_id_to_module,
        )

    # Module pages
    modules: dict[str, str | None] = {}
    module_titles = ir.get("module_titles") or {}
    for k in ir["knowledges"]:
        mod = k.get("module", "Root")
        if mod not in modules:
            modules[mod] = module_titles.get(mod)

    for mod, mod_title in modules.items():
        pages[f"modules/{mod}.md"] = _generate_module_page(
            mod,
            ir,
            beliefs,
            priors,
            strategies_by_conclusion,
            label_for_id,
            ids_with_pages,
            inlined_id_to_module,
            mod_title,
        )

    # Strategy pages (complex only)
    for s in ir.get("strategies", []):
        if _is_complex_strategy(s):
            sid = s.get("strategy_id", "")
            s_label = sid.removeprefix("lcs_") if sid else s.get("type", "strategy")
            pages[f"reasoning/{s_label}.md"] = _generate_strategy_page(
                s,
                label_for_id,
                ids_with_pages,
                inlined_id_to_module,
            )

    # Meta pages
    if beliefs:
        pages["meta/beliefs.md"] = _generate_beliefs_page(
            ir,
            beliefs,
            priors,
            label_for_id,
            ids_with_pages,
            inlined_id_to_module,
        )
    pages["meta/holes.md"] = _generate_holes_page(evidence)

    # Index and overview
    pages["_index.md"] = _generate_index(ir, conclusions, evidence, beliefs, modules)
    pages["overview.md"] = _generate_overview(ir)
    pages[".obsidian/graph.json"] = _generate_obsidian_config()

    return pages
