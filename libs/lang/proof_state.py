"""Proof state analysis for Gaia Language packages (v3 and v4).

Analyzes a loaded Typst graph to classify every declaration:
- established: has a reasoning factor concluding it, or is a relation node
- assumptions: settings (contextual choices, no proof needed, but challengeable)
- holes: used as premise but has no proof in this package (includes observations)
- imported: external cross-package references
- questions: open inquiries
- standalone: declared but not referenced and not proven
"""

from __future__ import annotations

RELATION_TYPES = {"contradiction", "equivalence", "corroboration"}


def analyze_proof_state(graph: dict) -> dict:
    """Analyze proof state of a loaded Typst package graph.

    Args:
        graph: Dict from load_typst_package() with nodes, factors,
               constraints.

    Returns:
        Dict with keys: established, assumptions, holes, imported,
        questions, standalone, report.
    """
    nodes = {n["name"]: n for n in graph.get("nodes", [])}

    # Names that are conclusions of reasoning factors (established)
    proven_names: set[str] = set()
    for factor in graph.get("factors", []):
        if factor.get("type") == "reasoning":
            proven_names.add(factor["conclusion"])

    # Names used as premises across all factors
    used_as_premise: set[str] = set()
    for factor in graph.get("factors", []):
        for p in factor.get("premises") or factor.get("premise", []):
            used_as_premise.add(p)

    # Also count constraint `between` members as structurally referenced
    constraint_names = set()
    for constraint in graph.get("constraints", []):
        constraint_names.add(constraint.get("name"))
        for member in constraint.get("between", []):
            used_as_premise.add(member)

    established: list[dict] = []
    assumptions: list[dict] = []
    imported: list[dict] = []
    holes: list[dict] = []
    questions: list[dict] = []
    standalone: list[dict] = []

    for name, node in nodes.items():
        node_type = node.get("type", "")

        if node.get("external"):
            imported.append(node)
        elif node_type == "question":
            questions.append(node)
        elif node_type == "setting":
            assumptions.append(node)
        elif node_type in RELATION_TYPES or node_type == "relation" or name in constraint_names:
            # Relation nodes are structurally established by their constraint declaration.
            established.append(node)
        elif name in proven_names:
            established.append(node)
        elif name in used_as_premise:
            holes.append(node)
        else:
            standalone.append(node)

    report = _format_report(established, assumptions, imported, holes, questions, standalone)

    return {
        "established": established,
        "assumptions": assumptions,
        "imported": imported,
        "holes": holes,
        "questions": questions,
        "standalone": standalone,
        "report": report,
    }


def _format_report(
    established: list[dict],
    assumptions: list[dict],
    imported: list[dict],
    holes: list[dict],
    questions: list[dict],
    standalone: list[dict] | None = None,
) -> str:
    lines: list[str] = []

    if established:
        lines.append("\u2713 established:")
        for d in established:
            lines.append(f"  {d['name']}")

    if assumptions:
        lines.append("")
        lines.append("\u25cb assumptions (challengeable):")
        for d in assumptions:
            lines.append(f"  {d['name']}  ({d.get('type', '')})")

    if imported:
        lines.append("")
        lines.append("imports:")
        for d in imported:
            pkg = d.get("ext_package", "")
            ver = d.get("ext_version", "")
            suffix = f"  ({pkg}@{ver})" if pkg and ver else ""
            lines.append(f"  {d['name']}{suffix}")

    if holes:
        lines.append("")
        lines.append("? holes:")
        for d in holes:
            node_type = d.get("type", "claim")
            lines.append(f"  {d['name']}  ({node_type}, used as premise, no proof)")

    if questions:
        lines.append("")
        lines.append("? questions:")
        for d in questions:
            lines.append(f"  {d['name']}  (open)")

    if standalone:
        lines.append("")
        lines.append("- standalone (not referenced):")
        for d in standalone:
            lines.append(f"  {d['name']}  ({d.get('type', '')})")

    return "\n".join(lines)
