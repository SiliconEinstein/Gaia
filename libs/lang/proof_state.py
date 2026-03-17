"""Proof state analysis for Gaia Language v2 packages.

Analyzes a loaded Typst graph to determine which declarations are
established (have proofs), which are axioms (settings/observations),
which are holes (claims used as premises without proofs), and which
are open questions.
"""

from __future__ import annotations

NO_PROOF_TYPES = {"setting", "observation", "question"}


def analyze_proof_state(graph: dict) -> dict:
    """Analyze proof state of a loaded Typst package graph.

    Args:
        graph: Dict from load_typst_package() with nodes, factors,
               proof_traces, constraints.

    Returns:
        Dict with keys: established, axioms, holes, questions, report.
    """
    nodes = {n["name"]: n for n in graph.get("nodes", [])}

    # Names that have proof traces (established)
    proven_names: set[str] = set()
    for trace in graph.get("proof_traces", []):
        proven_names.add(trace["conclusion"])

    # Names used as premises across all proofs
    used_as_premise: set[str] = set()
    for trace in graph.get("proof_traces", []):
        for p in trace.get("premises", []):
            used_as_premise.add(p)

    established: list[dict] = []
    axioms: list[dict] = []
    holes: list[dict] = []
    questions: list[dict] = []

    for name, node in nodes.items():
        node_type = node.get("type", "")

        if node_type == "question":
            questions.append(node)
        elif node_type in ("setting", "observation"):
            axioms.append(node)
        elif name in proven_names:
            established.append(node)
        elif name in used_as_premise:
            holes.append(node)
        # else: standalone claim, not used — could warn

    report = _format_report(established, axioms, holes, questions)

    return {
        "established": established,
        "axioms": axioms,
        "holes": holes,
        "questions": questions,
        "report": report,
    }


def _format_report(
    established: list[dict],
    axioms: list[dict],
    holes: list[dict],
    questions: list[dict],
) -> str:
    lines: list[str] = []

    if established:
        lines.append("\u2713 established:")
        for d in established:
            lines.append(f"  {d['name']}")

    if axioms:
        lines.append("")
        lines.append("\u25cb axioms (no proof needed):")
        for d in axioms:
            lines.append(f"  {d['name']}  ({d.get('type', '')})")

    if holes:
        lines.append("")
        lines.append("? holes:")
        for d in holes:
            lines.append(f"  {d['name']}  (claim, used as premise, no proof)")

    if questions:
        lines.append("")
        lines.append("? questions:")
        for d in questions:
            lines.append(f"  {d['name']}  (open)")

    return "\n".join(lines)
