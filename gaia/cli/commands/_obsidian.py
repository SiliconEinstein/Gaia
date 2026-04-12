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

from gaia.cli.commands._classify import classify_ir, node_role
from gaia.cli.commands._detailed_reasoning import render_mermaid, topo_layers
from gaia.cli.commands._simplified_mermaid import render_simplified_mermaid
from gaia.ir.coarsen import coarsen_ir
from gaia.ir.linearize import NarrativeSection, linearize_narrative


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


def _render_frontmatter(fields: dict) -> str:
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


def _assign_claim_numbers(ir: dict) -> dict[str, int]:
    """Assign sequential numbers by topological order (0=leaves, high=conclusions)."""
    layers = topo_layers(ir)
    module_order = ir.get("module_order") or []
    module_rank = {m: i for i, m in enumerate(module_order)}

    claims = [k for k in ir["knowledges"] if not _is_helper(k.get("label"))]

    def sort_key(k):
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
    k: dict,
    num: int,
    beliefs: dict[str, float],
    priors: dict[str, float],
    strategies_by_conclusion: dict[str, list[dict]],
    strategies_by_premise: dict[str, list[dict]],
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


def _generate_section_page(
    section: NarrativeSection,
    section_num: int,
    ir: dict,
    beliefs: dict[str, float],
    priors: dict[str, float],
    claim_numbers: dict[str, int],
    kid_to_k: dict[str, dict],
) -> str:
    """Generate a section page from a NarrativeSection (connectivity-based grouping)."""
    title = section.title

    # Collect knowledge nodes for this section
    section_kids = [e.kid for e in section.entries if e.kid in kid_to_k]
    section_nodes = [kid_to_k[kid] for kid in section_kids]
    section_nodes.sort(key=lambda k: claim_numbers.get(k["id"], 0))

    exported_count = sum(1 for e in section.entries if e.exported)

    fm = _render_frontmatter(
        {
            "type": "section",
            "section_number": section_num,
            "title": title,
            "layer": section.layer,
            "claim_count": len(section.entries),
            "exported_count": exported_count,
            "tags": ["section", f"layer-{section.layer}"],
        }
    )

    lines = [fm, "", f"# {section_num:02d} - {title}", ""]

    # Per-section reasoning graph
    sec_ids = {k["id"] for k in section_nodes}
    if sec_ids:
        lines.append(render_mermaid(ir, beliefs=beliefs, node_ids=sec_ids))
        lines.append("")

    lines.append("## Claims")
    lines.append("")

    for k in section_nodes:
        kid = k["id"]
        label = k.get("label", "")
        k_title = k.get("title") or label.replace("_", " ")
        content = k.get("content", "")
        num = claim_numbers.get(kid, 0)
        star = " ★" if k.get("exported") else ""
        prior_str = f"{priors[kid]:.2f}" if kid in priors else "—"
        belief_str = f"{beliefs[kid]:.2f}" if kid in beliefs else "—"

        lines.append(f"### [[{label}|#{num:02d} {k_title}]]{star}")
        lines.append(f"> {content}")
        lines.append("")
        lines.append(f"Prior: {prior_str} → Belief: {belief_str}")
        lines.append("")

    return "\n".join(lines)


def _generate_beliefs_page(
    ir: dict,
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
        prior = f"{priors[kid]:.2f}" if kid in priors else "—"
        belief = f"{beliefs[kid]:.2f}" if kid in beliefs else "—"
        num = claim_numbers.get(kid, 0)
        lines.append(f"| {num:02d} | [[{label}]] | {ktype} | {prior} | {belief} | {role} |")

    lines.append("")
    return "\n".join(lines)


def _generate_holes_page(leaves: list[dict], claim_numbers: dict[str, int]) -> str:
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
    ir: dict,
    all_claims: list[dict],
    claim_numbers: dict[str, int],
    beliefs: dict[str, float],
    sections: list[NarrativeSection],
) -> str:
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
    n_settings = sum(1 for k in all_k if k["type"] == "setting")
    n_questions = sum(1 for k in all_k if k["type"] == "question")
    lines.append(
        f"| Knowledge nodes | {len(all_k)} ({n_claims} claims, {n_settings} settings, {n_questions} questions) |"
    )
    lines.append(f"| Strategies | {len(ir.get('strategies', []))} |")
    lines.append(f"| Operators | {len(ir.get('operators', []))} |")
    lines.append(f"| Sections | {len(sections)} |")
    lines.append(f"| Exported | {sum(1 for k in all_k if k.get('exported'))} |")
    lines.append("")

    # Sections (narrative grouping)
    lines.append("## Sections")
    lines.append("")
    lines.append("| # | Section | Layer | Claims |")
    lines.append("|---|---------|-------|--------|")
    for i, sec in enumerate(sections, 1):
        sec_title = _sanitize_filename(sec.title)
        lines.append(f"| {i:02d} | [[{sec_title}]] | {sec.layer} | {len(sec.entries)} |")
    lines.append("")

    # Claim index
    lines.append("## Claim Index")
    lines.append("")
    lines.append("| # | Claim | Type | Belief |")
    lines.append("|---|-------|------|--------|")
    sorted_claims = sorted(all_claims, key=lambda k: claim_numbers.get(k["id"], 0))
    for k in sorted_claims:
        kid = k["id"]
        label = k.get("label", "")
        num = claim_numbers.get(kid, 0)
        star = " ★" if k.get("exported") else ""
        belief = f"{beliefs[kid]:.2f}" if kid in beliefs else "—"
        lines.append(f"| {num:02d} | [[{label}]]{star} | {k['type']} | {belief} |")
    lines.append("")

    # Reading path (sections in order)
    if len(sections) > 1:
        lines.append("## Reading Path")
        lines.append("")
        sec_names = [_sanitize_filename(s.title) for s in sections]
        lines.append(" → ".join(f"[[{n}]]" for n in sec_names))
        lines.append("")

    lines.append("## Quick Links")
    lines.append("")
    lines.append("- [[overview]] — Reasoning graph")
    if beliefs:
        lines.append("- [[beliefs]] — Full belief table")
    lines.append("- [[holes]] — Leaf premises")
    lines.append("")
    return "\n".join(lines)


def _generate_overview(ir: dict, beliefs: dict[str, float], priors: dict[str, float]) -> str:
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
            {"query": "tag:#setting", "color": {"a": 1, "rgb": 8421504}},
            {"query": "tag:#question", "color": {"a": 1, "rgb": 16750848}},
            {"query": "tag:#module", "color": {"a": 1, "rgb": 65280}},
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
    """Generate Obsidian vault with numbered claims and module chapters."""
    pages: dict[str, str] = {}

    beliefs: dict[str, float] = {}
    if beliefs_data:
        beliefs = {b["knowledge_id"]: b["belief"] for b in beliefs_data.get("beliefs", [])}
    priors: dict[str, float] = {}
    if param_data:
        priors = {p["knowledge_id"]: p["value"] for p in param_data.get("priors", [])}

    strategies_by_conclusion: dict[str, list[dict]] = {}
    strategies_by_premise: dict[str, list[dict]] = {}
    for s in ir.get("strategies", []):
        conc = s.get("conclusion")
        if conc:
            strategies_by_conclusion.setdefault(conc, []).append(s)
        for p in s.get("premises", []):
            strategies_by_premise.setdefault(p, []).append(s)

    label_for_id: dict[str, str] = {}
    for k in ir["knowledges"]:
        label_for_id[k["id"]] = k.get("label", k["id"].split("::")[-1])

    claim_numbers = _assign_claim_numbers(ir)
    all_claims = [k for k in ir["knowledges"] if not _is_helper(k.get("label"))]

    kid_to_k = {k["id"]: k for k in ir["knowledges"]}

    # Classify claims into roles
    conclusion_ids = {s.get("conclusion") for s in ir.get("strategies", []) if s.get("conclusion")}
    exported_ids = {k["id"] for k in ir["knowledges"] if k.get("exported")}

    def _claim_role(k: dict) -> str:
        kid = k["id"]
        if kid in exported_ids:
            return "conclusions"
        if kid in conclusion_ids:
            return "intermediate"
        return "premises"

    # Claim pages (sorted into role subdirectories)
    for k in all_claims:
        kid = k["id"]
        label = k.get("label", "")
        title = k.get("title") or label.replace("_", " ")
        cn = claim_numbers.get(kid, 0)
        role = _claim_role(k)
        fname = _sanitize_filename(f"{cn:02d} - {title}")
        pages[f"claims/{role}/{fname}.md"] = _generate_claim_page(
            k,
            cn,
            beliefs,
            priors,
            strategies_by_conclusion,
            strategies_by_premise,
            label_for_id,
            claim_numbers,
        )
    try:
        coarse = coarsen_ir(ir, exported_ids)
        sections = linearize_narrative(coarse, beliefs=beliefs, priors=priors)
    except Exception:
        # Fallback: one section per module
        sections = []

    # Section pages (replace old module pages)
    for i, sec in enumerate(sections, 1):
        fname = _sanitize_filename(f"{i:02d} - {sec.title}")
        pages[f"sections/{fname}.md"] = _generate_section_page(
            sec,
            i,
            ir,
            beliefs,
            priors,
            claim_numbers,
            kid_to_k,
        )

    # Leaves for holes page
    conclusion_ids = {s.get("conclusion") for s in ir.get("strategies", []) if s.get("conclusion")}
    leaves = [k for k in all_claims if k["id"] not in conclusion_ids and k["type"] != "setting"]

    # Meta
    if beliefs:
        pages["meta/beliefs.md"] = _generate_beliefs_page(ir, beliefs, priors, claim_numbers)
    pages["meta/holes.md"] = _generate_holes_page(leaves, claim_numbers)

    # Index + overview + config
    pages["_index.md"] = _generate_index(ir, all_claims, claim_numbers, beliefs, sections)
    pages["overview.md"] = _generate_overview(ir, beliefs, priors)
    pages[".obsidian/graph.json"] = _generate_obsidian_config()

    return pages
