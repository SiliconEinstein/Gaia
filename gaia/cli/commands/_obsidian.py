"""Generate Obsidian vault from compiled IR.

Architecture:
- claims/  — one page per non-helper claim, numbered by topological order
- modules/ — numbered chapter pages (narrative organized by claim numbers)
- meta/    — beliefs table, holes list
- _index.md, overview.md, .obsidian/

Naming: filenames use titles, wikilinks use labels, aliases bridge them.
"""

from __future__ import annotations

import json
from typing import Any

from gaia.cli.commands._detailed_reasoning import render_mermaid, topo_layers
from gaia.cli.commands._render_priors import format_belief
from gaia.cli.commands._simplified_mermaid import render_simplified_mermaid
from gaia.engine.inquiry._classify import (
    KnowledgeClassification,
    classify_ir,
    is_note_type,
    node_role,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _sanitize_filename(name: str) -> str:
    for ch in r'<>:"/\|?*':
        name = name.replace(ch, "")
    return name.strip()


def _is_helper(label: str | None) -> bool:
    if not label:
        return True
    return label.startswith("__") or label.startswith("_anon")


def _render_frontmatter(fields: dict[str, Any]) -> str:
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


def _assign_claim_numbers(ir: dict[str, Any]) -> dict[str, int]:
    """Assign sequential numbers by topological order (0=leaves, high=conclusions)."""
    layers = topo_layers(ir)
    module_order = ir.get("module_order") or []
    module_rank = {m: i for i, m in enumerate(module_order)}

    claims = [k for k in ir["knowledges"] if not _is_helper(k.get("label"))]

    def sort_key(k: dict[str, Any]) -> tuple[int, int, Any]:
        kid = k["id"]
        return (
            layers.get(kid, 0),
            module_rank.get(k.get("module", "Root"), 999),
            k.get("declaration_index") or 0,
        )

    claims.sort(key=sort_key)
    return {k["id"]: i + 1 for i, k in enumerate(claims)}


# ---------------------------------------------------------------------------
# Page generators
# ---------------------------------------------------------------------------


def _generate_claim_page(
    k: dict[str, Any],
    num: int,
    beliefs: dict[str, float],
    priors: dict[str, float],
    justifications: dict[str, str],
    strategies_by_conclusion: dict[str, list[dict[str, Any]]],
    strategies_by_premise: dict[str, list[dict[str, Any]]],
    label_for_id: dict[str, str],
    claim_numbers: dict[str, int],
) -> str:
    kid = k["id"]
    label = k.get("label", "")
    title = k.get("title") or label.replace("_", " ")
    content = k.get("content", "")
    module = k.get("module", "Root")
    exported = k.get("exported", False)
    star = " ★" if exported else ""

    strategy_for = strategies_by_conclusion.get(kid, [])
    strategy_type = strategy_for[0]["type"] if strategy_for else None
    premise_count = len(strategy_for[0]["premises"]) if strategy_for else 0

    def cref(target_id: str) -> str:
        lbl = label_for_id.get(target_id, target_id.split("::")[-1])
        n = claim_numbers.get(target_id)
        return f"[[{lbl}|#{n:02d} {lbl}]]" if n else f"[[{lbl}]]"

    fm = _render_frontmatter(
        {
            "type": k["type"],
            "label": label,
            "aliases": [label],
            "claim_number": num,
            "qid": kid,
            "module": module,
            "exported": exported,
            "prior": priors.get(kid),
            "belief": beliefs.get(kid),
            "strategy_type": strategy_type,
            "premise_count": premise_count,
            "tags": [k["type"], module.replace("_", "-")],
        }
    )

    lines = [fm, "", f"# #{num:02d} {title}{star}", "", f"> {content}", ""]

    if strategy_for:
        s = strategy_for[0]
        lines.append("## Derivation")
        lines.append(f"- **Strategy**: {s['type']}")
        premises = s.get("premises", [])
        if premises:
            lines.append("- **Premises**:")
            for p in premises:
                lines.append(f"  - {cref(p)}")
        reason = (s.get("metadata") or {}).get("reason", "") or s.get("reason", "")
        if reason:
            lines.append("")
            lines.append("> [!REASONING]")
            lines.append(f"> {reason}")
        lines.append("")

    # Review
    justification = justifications.get(kid, "")
    prior_val = priors.get(kid)
    belief_val = beliefs.get(kid)
    if prior_val is not None or justification:
        lines.append("## Review")
        if prior_val is not None:
            lines.append(f"**Prior**: {format_belief(prior_val)}")
        if justification:
            lines.append(f"**Justification**: {justification}")
        if belief_val is not None:
            lines.append(f"**Belief**: {format_belief(belief_val)}")
        lines.append("")

    if kid in strategies_by_premise:
        lines.append("## Supports")
        for s in strategies_by_premise[kid]:
            conc = s.get("conclusion", "")
            lines.append(f"- → {cref(conc)} via {s['type']}")
        lines.append("")

    lines.append("## Module")
    lines.append(f"[[{module}]]")
    lines.append("")
    return "\n".join(lines)


def _generate_module_section_page(
    module_name: str,
    section_num: int,
    title: str,
    claims: list[dict[str, Any]],
    ir: dict[str, Any],
    beliefs: dict[str, float],
    priors: dict[str, float],
    claim_numbers: dict[str, int],
    label_for_id: dict[str, str],
) -> str:
    """Generate a section page for a DSL module, claims ordered by topo sort."""
    del label_for_id
    exported_count = sum(1 for k in claims if k.get("exported"))

    fm = _render_frontmatter(
        {
            "type": "section",
            "label": module_name,
            "aliases": [module_name],
            "section_number": section_num,
            "title": title,
            "claim_count": len(claims),
            "exported_count": exported_count,
            "tags": ["section", module_name.replace("_", "-")],
        }
    )

    lines = [fm, "", f"# {section_num:02d} - {title}", ""]

    # Per-section reasoning graph
    sec_ids = {k["id"] for k in claims}
    if sec_ids:
        lines.append(render_mermaid(ir, beliefs=beliefs, node_ids=sec_ids))
        lines.append("")

    lines.append("## Claims")
    lines.append("")

    for k in claims:
        kid = k["id"]
        label = k.get("label", "")
        k_title = k.get("title") or label.replace("_", " ")
        content = k.get("content", "")
        num = claim_numbers.get(kid, 0)
        star = " ★" if k.get("exported") else ""
        prior_str = format_belief(priors[kid]) if kid in priors else "—"
        belief_str = format_belief(beliefs[kid]) if kid in beliefs else "—"

        lines.append(f"### [[{label}|#{num:02d} {k_title}]]{star}")
        lines.append(f"> {content}")
        lines.append("")
        lines.append(f"Prior: {prior_str} → Belief: {belief_str}")
        lines.append("")

    return "\n".join(lines)


def _generate_beliefs_page(
    ir: dict[str, Any],
    beliefs: dict[str, float],
    priors: dict[str, float],
    claim_numbers: dict[str, int],
) -> str:
    classification = classify_ir(ir)
    lines = [
        "---",
        "type: meta",
        "aliases: [beliefs]",
        "tags: [meta, beliefs]",
        "---",
        "",
        "# Beliefs",
        "",
    ]
    lines.append("| # | Label | Type | Prior | Belief | Role |")
    lines.append("|---|-------|------|-------|--------|------|")

    knowledges = [k for k in ir["knowledges"] if not _is_helper(k.get("label", ""))]
    knowledges.sort(key=lambda k: beliefs.get(k["id"], 0.0), reverse=True)

    for k in knowledges:
        kid = k["id"]
        label = k.get("label", "")
        ktype = k["type"]
        role = node_role(kid, ktype, classification)
        prior = format_belief(priors[kid]) if kid in priors else "—"
        belief = format_belief(beliefs[kid]) if kid in beliefs else "—"
        num = claim_numbers.get(kid, 0)
        lines.append(f"| {num:02d} | [[{label}]] | {ktype} | {prior} | {belief} | {role} |")

    lines.append("")
    return "\n".join(lines)


def _generate_holes_page(leaves: list[dict[str, Any]], claim_numbers: dict[str, int]) -> str:
    lines = [
        "---",
        "type: meta",
        "aliases: [holes]",
        "tags: [meta, holes]",
        "---",
        "",
        "# Leaf Premises (Holes)",
        "",
    ]
    lines.append("| # | Label | Module | Content |")
    lines.append("|---|-------|--------|---------|")
    sorted_leaves = sorted(leaves, key=lambda k: claim_numbers.get(k["id"], 0))
    for k in sorted_leaves:
        label = k.get("label", "")
        module = k.get("module", "Root")
        num = claim_numbers.get(k["id"], 0)
        content = k.get("content", "")
        if len(content) > 60:
            content = content[:60] + "..."
        lines.append(f"| {num:02d} | [[{label}]] | [[{module}]] | {content} |")
    lines.append("")
    return "\n".join(lines)


def _generate_index(
    ir: dict[str, Any],
    all_claims: list[dict[str, Any]],
    claim_numbers: dict[str, int],
    beliefs: dict[str, float],
    section_list: list[tuple[str, str, int]],
) -> str:
    """Generate _index.md. section_list = [(module_name, title, claim_count)]."""
    pkg = ir.get("package_name", "Package")
    ir_hash = ir.get("ir_hash", "unknown")
    all_k = ir["knowledges"]

    lines = [f"# {pkg}", ""]
    if ir_hash and ir_hash != "unknown":
        lines.append(f"IR hash: `{ir_hash[:16]}...`")
        lines.append("")

    lines.append("## Statistics")
    lines.append("")
    lines.append("| Metric | Count |")
    lines.append("|--------|-------|")
    n_claims = sum(1 for k in all_k if k["type"] == "claim")
    n_notes = sum(1 for k in all_k if is_note_type(k["type"]))
    n_questions = sum(1 for k in all_k if k["type"] == "question")
    lines.append(
        f"| Knowledge nodes | {len(all_k)} "
        f"({n_claims} claims, {n_notes} notes, {n_questions} questions) |"
    )
    lines.append(f"| Strategies | {len(ir.get('strategies', []))} |")
    lines.append(f"| Operators | {len(ir.get('operators', []))} |")
    lines.append(f"| Sections | {len(section_list)} |")
    lines.append(f"| Exported | {sum(1 for k in all_k if k.get('exported'))} |")
    lines.append("")

    # Sections
    lines.append("## Sections")
    lines.append("")
    lines.append("| # | Section | Claims |")
    lines.append("|---|---------|--------|")
    for i, (mod, _title, count) in enumerate(section_list, 1):
        lines.append(f"| {i:02d} | [[{mod}]] | {count} |")
    lines.append("")

    # Claim index
    lines.append("## Claim Index")
    lines.append("")
    lines.append("| # | Claim | Type | Section | Belief |")
    lines.append("|---|-------|------|---------|--------|")
    sorted_claims = sorted(all_claims, key=lambda k: claim_numbers.get(k["id"], 0))
    for k in sorted_claims:
        kid = k["id"]
        label = k.get("label", "")
        mod = k.get("module", "Root")
        num = claim_numbers.get(kid, 0)
        star = " ★" if k.get("exported") else ""
        belief = format_belief(beliefs[kid]) if kid in beliefs else "—"
        lines.append(f"| {num:02d} | [[{label}]]{star} | {k['type']} | [[{mod}]] | {belief} |")
    lines.append("")

    # Reading path
    if len(section_list) > 1:
        lines.append("## Reading Path")
        lines.append("")
        lines.append(" → ".join(f"[[{mod}]]" for mod, _, _ in section_list))
        lines.append("")

    lines.append("## Quick Links")
    lines.append("")
    lines.append("- [[overview]] — Reasoning graph")
    if beliefs:
        lines.append("- [[beliefs]] — Full belief table")
    lines.append("- [[holes]] — Leaf premises")
    lines.append("")
    return "\n".join(lines)


def _generate_overview(
    ir: dict[str, Any], beliefs: dict[str, float], priors: dict[str, float]
) -> str:
    pkg = ir.get("package_name", "Package")
    lines = ["---", "type: overview", "tags: [overview]", "---", ""]
    lines.append(f"# {pkg} — Overview")
    lines.append("")
    if beliefs:
        exported_ids = {k["id"] for k in ir.get("knowledges", []) if k.get("exported")}
        lines.append(render_simplified_mermaid(ir, beliefs, priors, exported_ids))
    else:
        lines.append(render_mermaid(ir))
    lines.append("")
    return "\n".join(lines)


def _generate_obsidian_config() -> str:
    config = {
        "collapse-filter": False,
        "search": "",
        "showTags": False,
        "showAttachments": False,
        "hideUnresolved": False,
        "colorGroups": [
            {"query": "tag:#claim", "color": {"a": 1, "rgb": 5025616}},
            {"query": "tag:#note", "color": {"a": 1, "rgb": 8421504}},
            {"query": "tag:#question", "color": {"a": 1, "rgb": 16750848}},
            {"query": "tag:#module", "color": {"a": 1, "rgb": 65280}},
            {"query": "tag:#evidence", "color": {"a": 1, "rgb": 255}},
            {"query": "tag:#meta", "color": {"a": 1, "rgb": 11184810}},
        ],
    }
    return json.dumps(config, indent=2)


def _obsidian_belief_inputs(
    beliefs_data: dict[str, Any] | None,
    param_data: dict[str, Any] | None,
) -> tuple[dict[str, float], dict[str, float], dict[str, str]]:
    """Extract beliefs, priors, and justifications for Obsidian pages."""
    beliefs = (
        {b["knowledge_id"]: b["belief"] for b in beliefs_data.get("beliefs", [])}
        if beliefs_data
        else {}
    )
    priors: dict[str, float] = {}
    justifications: dict[str, str] = {}
    if param_data:
        for p in param_data.get("priors", []):
            priors[p["knowledge_id"]] = p["value"]
            if p.get("justification"):
                justifications[p["knowledge_id"]] = p["justification"]
    return beliefs, priors, justifications


def _obsidian_strategy_indexes(
    ir: dict[str, Any],
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, list[dict[str, Any]]]]:
    """Index strategies by conclusion and premise for Obsidian pages."""
    by_conclusion: dict[str, list[dict[str, Any]]] = {}
    by_premise: dict[str, list[dict[str, Any]]] = {}
    for strategy in ir.get("strategies", []):
        conc = strategy.get("conclusion")
        if conc:
            by_conclusion.setdefault(conc, []).append(strategy)
        for premise in strategy.get("premises", []):
            by_premise.setdefault(premise, []).append(strategy)
    return by_conclusion, by_premise


def _obsidian_label_for_id(ir: dict[str, Any]) -> dict[str, str]:
    """Return display labels keyed by knowledge id."""
    return {k["id"]: k.get("label", k["id"].split("::")[-1]) for k in ir["knowledges"]}


def _obsidian_claim_role(
    k: dict[str, Any],
    *,
    exported_ids: set[str],
    classification: KnowledgeClassification,
) -> str:
    """Return the Obsidian claim subdirectory for one knowledge node."""
    if k["id"] in exported_ids:
        return "conclusions"
    role = node_role(k["id"], k["type"], classification)
    return {
        "independent": "holes",
        "derived": "intermediate",
        "note": "context",
        "background": "context",
        "structural": "context",
        "orphaned": "context",
        "question": "conclusions",
    }.get(role, "context")


def _obsidian_modules(ir: dict[str, Any]) -> list[str]:
    """Return module order followed by any modules discovered in knowledges."""
    modules: list[str] = []
    seen: set[str] = set()
    for module in ir.get("module_order") or []:
        if module not in seen:
            modules.append(module)
            seen.add(module)
    for k in ir["knowledges"]:
        mod = k.get("module", "Root")
        if mod not in seen and not _is_helper(k.get("label", "")):
            modules.append(mod)
            seen.add(mod)
    return modules


def _write_obsidian_claim_pages(
    pages: dict[str, str],
    *,
    all_claims: list[dict[str, Any]],
    exported_ids: set[str],
    classification: KnowledgeClassification,
    claim_numbers: dict[str, int],
    beliefs: dict[str, float],
    priors: dict[str, float],
    justifications: dict[str, str],
    strategies_by_conclusion: dict[str, list[dict[str, Any]]],
    strategies_by_premise: dict[str, list[dict[str, Any]]],
    label_for_id: dict[str, str],
) -> None:
    """Populate one Obsidian claim page per non-helper knowledge node."""
    for k in all_claims:
        kid = k["id"]
        label = k.get("label", "")
        title = k.get("title") or label.replace("_", " ")
        cn = claim_numbers.get(kid, 0)
        role = _obsidian_claim_role(k, exported_ids=exported_ids, classification=classification)
        fname = _sanitize_filename(f"{cn:02d} - {title}")
        pages[f"claims/{role}/{fname}.md"] = _generate_claim_page(
            k,
            cn,
            beliefs,
            priors,
            justifications,
            strategies_by_conclusion,
            strategies_by_premise,
            label_for_id,
            claim_numbers,
        )


def _write_obsidian_module_pages(
    pages: dict[str, str],
    *,
    modules: list[str],
    module_titles: dict[str, str],
    all_claims: list[dict[str, Any]],
    ir: dict[str, Any],
    beliefs: dict[str, float],
    priors: dict[str, float],
    claim_numbers: dict[str, int],
    label_for_id: dict[str, str],
) -> int:
    """Populate module section pages and return the next section number."""
    sec_num = 0
    for mod in modules:
        mod_claims = [k for k in all_claims if k.get("module", "Root") == mod]
        if not mod_claims:
            continue
        sec_num += 1
        mod_claims.sort(key=lambda k: claim_numbers.get(k["id"], 0))
        title = module_titles.get(mod) or mod.replace("_", " ").title()
        fname = _sanitize_filename(f"{sec_num:02d} - {title}")
        pages[f"sections/{fname}.md"] = _generate_module_section_page(
            mod,
            sec_num,
            title,
            mod_claims,
            ir,
            beliefs,
            priors,
            claim_numbers,
            label_for_id,
        )
    return sec_num


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def generate_obsidian_vault(
    ir: dict[str, Any],
    *,
    beliefs_data: dict[str, Any] | None = None,
    param_data: dict[str, Any] | None = None,
) -> dict[str, str]:
    """Generate Obsidian vault with numbered claims and module chapters."""
    pages: dict[str, str] = {}

    beliefs, priors, justifications = _obsidian_belief_inputs(beliefs_data, param_data)
    strategies_by_conclusion, strategies_by_premise = _obsidian_strategy_indexes(ir)
    label_for_id = _obsidian_label_for_id(ir)

    claim_numbers = _assign_claim_numbers(ir)
    all_claims = [k for k in ir["knowledges"] if not _is_helper(k.get("label"))]

    exported_ids = {k["id"] for k in ir["knowledges"] if k.get("exported")}
    classification = classify_ir(ir)

    # Claim pages (sorted into role subdirectories)
    _write_obsidian_claim_pages(
        pages,
        all_claims=all_claims,
        exported_ids=exported_ids,
        classification=classification,
        claim_numbers=claim_numbers,
        beliefs=beliefs,
        priors=priors,
        justifications=justifications,
        strategies_by_conclusion=strategies_by_conclusion,
        strategies_by_premise=strategies_by_premise,
        label_for_id=label_for_id,
    )

    # Section pages from DSL modules (module_order defines narrative arc)
    module_titles: dict[str, str] = ir.get("module_titles") or {}
    modules = _obsidian_modules(ir)
    sec_num = _write_obsidian_module_pages(
        pages,
        modules=modules,
        module_titles=module_titles,
        all_claims=all_claims,
        ir=ir,
        beliefs=beliefs,
        priors=priors,
        claim_numbers=claim_numbers,
        label_for_id=label_for_id,
    )

    # Weak Points section — claims with lowest belief
    if beliefs:
        sec_num += 1
        weak = sorted(
            [k for k in all_claims if k["id"] in beliefs],
            key=lambda k: beliefs[k["id"]],
        )[:10]  # bottom 10
        weak_lines = [
            "---",
            "type: section",
            "aliases: [weak-points]",
            "section_number: " + str(sec_num),
            "title: Weak Points",
            "tags: [section, weak-points]",
            "---",
            "",
            f"# {sec_num:02d} - Weak Points",
            "",
            "Claims with the lowest posterior belief — potential weak links in the reasoning.",
            "",
            "| # | Claim | Prior | Belief | Justification |",
            "|---|-------|-------|--------|---------------|",
        ]
        for k in weak:
            kid = k["id"]
            label = k.get("label", "")
            num = claim_numbers.get(kid, 0)
            prior = format_belief(priors[kid]) if kid in priors else "—"
            belief = format_belief(beliefs[kid])
            just = justifications.get(kid, "")
            weak_lines.append(f"| {num:02d} | [[{label}]] | {prior} | {belief} | {just} |")
        weak_lines.append("")
        pages[f"sections/{sec_num:02d} - Weak Points.md"] = "\n".join(weak_lines)

    # Open Questions section — leaf premises (holes) + questions
    sec_num += 1
    conclusion_ids = {s.get("conclusion") for s in ir.get("strategies", []) if s.get("conclusion")}
    leaves = [
        k for k in all_claims if k["id"] not in conclusion_ids and not is_note_type(k["type"])
    ]
    questions = [k for k in all_claims if k["type"] == "question"]
    oq_lines = [
        "---",
        "type: section",
        "aliases: [open-questions]",
        "section_number: " + str(sec_num),
        "title: Open Questions",
        "tags: [section, open-questions]",
        "---",
        "",
        f"# {sec_num:02d} - Open Questions",
        "",
        "Leaf premises that could be strengthened and open questions for future work.",
        "",
    ]
    if questions:
        oq_lines.append("## Questions")
        oq_lines.append("")
        for k in questions:
            label = k.get("label", "")
            num = claim_numbers.get(k["id"], 0)
            content = k.get("content", "")
            oq_lines.append(f"- [[{label}|#{num:02d} {label}]]: {content}")
        oq_lines.append("")
    oq_lines.append("## Leaf Premises (Holes)")
    oq_lines.append("")
    oq_lines.append("| # | Claim | Module | Content |")
    oq_lines.append("|---|-------|--------|---------|")
    sorted_leaves = sorted(leaves, key=lambda k: claim_numbers.get(k["id"], 0))
    for k in sorted_leaves:
        label = k.get("label", "")
        mod = k.get("module", "Root")
        num = claim_numbers.get(k["id"], 0)
        content = k.get("content", "")
        if len(content) > 60:
            content = content[:60] + "..."
        oq_lines.append(f"| {num:02d} | [[{label}]] | [[{mod}]] | {content} |")
    oq_lines.append("")
    pages[f"sections/{sec_num:02d} - Open Questions.md"] = "\n".join(oq_lines)

    # Meta
    if beliefs:
        pages["meta/beliefs.md"] = _generate_beliefs_page(ir, beliefs, priors, claim_numbers)
    pages["meta/holes.md"] = _generate_holes_page(leaves, claim_numbers)

    # Build section list for index
    section_list: list[tuple[str, str, int]] = []
    for mod in modules:
        mod_count = sum(1 for k in all_claims if k.get("module", "Root") == mod)
        if mod_count > 0:
            t = module_titles.get(mod) or mod.replace("_", " ").title()
            section_list.append((mod, t, mod_count))
    if beliefs:
        section_list.append(("weak-points", "Weak Points", len(weak)))
    section_list.append(("open-questions", "Open Questions", len(leaves) + len(questions)))

    # Index + overview + config
    pages["_index.md"] = _generate_index(ir, all_claims, claim_numbers, beliefs, section_list)
    pages["overview.md"] = _generate_overview(ir, beliefs, priors)
    pages[".obsidian/graph.json"] = _generate_obsidian_config()

    return pages
