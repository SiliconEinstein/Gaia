"""Linearize a coarse reasoning graph into a narrative outline.

Topological sort → layering → module grouping → narrative sections.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class NarrativeEntry:
    """One claim in the narrative outline."""

    kid: str
    label: str
    title: str
    module: str
    type: str  # "claim" / "setting"
    exported: bool
    prior: float | None
    belief: float | None
    derived_from: list[str]  # labels of premises
    supports: list[str]  # labels of conclusions
    strategy_type: str  # "infer" / "deduction" / etc.
    mi_bits: float  # mutual information of the edge leading here


@dataclass
class NarrativeSection:
    """A group of entries forming a narrative section (chapter)."""

    title: str
    layer: int
    entries: list[NarrativeEntry] = field(default_factory=list)


def linearize_narrative(
    coarse: dict,
    beliefs: dict[str, float] | None = None,
    priors: dict[str, float] | None = None,
    mi_per_strategy: dict[int, float] | None = None,
) -> list[NarrativeSection]:
    """Convert a coarse reasoning DAG into a linear narrative outline.

    Algorithm:
    1. Build adjacency from coarse strategies
    2. Topological sort → assign layer to each node
    3. Auto-detect narrative sections by grouping adjacent layers
       with the same dominant module
    4. Within each section, order entries by layer then by module
    """
    beliefs = beliefs or {}
    priors = priors or {}
    mi_map = mi_per_strategy or {}

    kid_to_k = {k["id"]: k for k in coarse["knowledges"]}
    exported_ids = {k["id"] for k in coarse["knowledges"] if k.get("exported")}

    # Build forward/backward adjacency from strategies
    forward: dict[str, list[str]] = {}  # kid → [conclusion kids]
    backward: dict[str, list[str]] = {}  # kid → [premise kids]
    strategy_for_conclusion: dict[str, dict] = {}  # conclusion kid → strategy dict
    strategy_idx_for_conclusion: dict[str, int] = {}

    for i, s in enumerate(coarse["strategies"]):
        conc = s["conclusion"]
        strategy_for_conclusion[conc] = s
        strategy_idx_for_conclusion[conc] = i
        for p in s["premises"]:
            forward.setdefault(p, []).append(conc)
            backward.setdefault(conc, []).append(p)

    # Also track operator relationships
    for o in coarse.get("operators", []):
        conc = o.get("conclusion")
        for v in o.get("variables", []):
            if conc:
                forward.setdefault(v, []).append(conc)
                backward.setdefault(conc, []).append(v)

    # Topological sort → layer assignment
    all_kids = {k["id"] for k in coarse["knowledges"]}
    in_degree: dict[str, int] = {kid: 0 for kid in all_kids}
    for conc, plist in backward.items():
        in_degree[conc] = len(plist)

    layers: dict[str, int] = {}
    queue = [kid for kid in all_kids if in_degree.get(kid, 0) == 0]
    layer = 0
    while queue:
        next_queue: list[str] = []
        for kid in queue:
            layers[kid] = layer
        for kid in queue:
            for neighbor in forward.get(kid, []):
                if neighbor in all_kids:
                    in_degree[neighbor] -= 1
                    if in_degree[neighbor] <= 0 and neighbor not in layers:
                        next_queue.append(neighbor)
        queue = next_queue
        layer += 1

    # Handle any remaining (cycles or disconnected)
    for kid in all_kids:
        if kid not in layers:
            layers[kid] = layer

    max_layer = max(layers.values()) if layers else 0

    # Build narrative entries
    entries_by_kid: dict[str, NarrativeEntry] = {}
    for k in coarse["knowledges"]:
        kid = k["id"]
        label = k.get("label", "")
        if label.startswith("__"):
            continue

        # What supports this?
        derived_labels = []
        stype = ""
        mi = 0.0
        if kid in strategy_for_conclusion:
            s = strategy_for_conclusion[kid]
            stype = s.get("type", "")
            derived_labels = [
                kid_to_k[p].get("label", "?")
                for p in s["premises"]
                if p in kid_to_k
            ]
            idx = strategy_idx_for_conclusion.get(kid)
            if idx is not None:
                mi = mi_map.get(idx, 0.0)

        # What does this support?
        supports_labels = [
            kid_to_k[c].get("label", "?")
            for c in forward.get(kid, [])
            if c in kid_to_k
        ]

        entries_by_kid[kid] = NarrativeEntry(
            kid=kid,
            label=label,
            title=k.get("title") or label,
            module=k.get("module", ""),
            type=k.get("type", "claim"),
            exported=kid in exported_ids,
            prior=priors.get(kid),
            belief=beliefs.get(kid),
            derived_from=derived_labels,
            supports=supports_labels,
            strategy_type=stype,
            mi_bits=mi,
        )

    # Group into narrative sections:
    # For each (layer, module) pair, create a section.
    # Then merge consecutive sections with the same module.
    raw_sections: list[tuple[int, str, list[NarrativeEntry]]] = []
    for lyr in range(max_layer + 1):
        # Collect entries at this layer, grouped by module
        by_module: dict[str, list[NarrativeEntry]] = {}
        for kid, entry in entries_by_kid.items():
            if layers.get(kid) == lyr:
                m = entry.module or "General"
                by_module.setdefault(m, []).append(entry)
        # Sort modules by number of entries (largest first for this layer)
        for mod in sorted(by_module, key=lambda m: -len(by_module[m])):
            raw_sections.append((lyr, mod, by_module[mod]))

    # Merge consecutive sections with the same module
    sections: list[NarrativeSection] = []
    for lyr, mod, entries in raw_sections:
        if sections and sections[-1].title == mod:
            sections[-1].entries.extend(entries)
        else:
            sections.append(NarrativeSection(title=mod, layer=lyr, entries=list(entries)))

    # Sort entries within each section: non-exported first, then by belief
    for section in sections:
        section.entries.sort(key=lambda e: (e.exported, e.belief or 0))

    return sections


def render_narrative_outline(sections: list[NarrativeSection]) -> str:
    """Render narrative sections as markdown for agent consumption."""
    lines: list[str] = []
    lines.append("# Narrative Outline")
    lines.append("")
    lines.append(
        "This outline follows the topological order of the reasoning graph. "
        "Each section groups claims by module. Use this as the backbone for "
        "writing narrative summaries."
    )
    lines.append("")

    entry_num = 0
    for section in sections:
        lines.append(f"## {section.title}")
        lines.append("")
        for entry in section.entries:
            entry_num += 1
            star = " ★" if entry.exported else ""
            prior_str = f"{entry.prior:.2f}" if entry.prior is not None else "0.50"
            belief_str = f"{entry.belief:.2f}" if entry.belief is not None else "—"

            lines.append(
                f"{entry_num}. **{entry.title}{star}** "
                f"(prior: {prior_str} → belief: {belief_str})"
            )

            if entry.derived_from:
                mi_str = f" [{entry.mi_bits:.2f} bits]" if entry.mi_bits > 0 else ""
                lines.append(
                    f"   - ← {entry.strategy_type}({', '.join(entry.derived_from)})"
                    f"{mi_str}"
                )

            if entry.supports:
                lines.append(
                    f"   - → supports: {', '.join(entry.supports)}"
                )

            lines.append("")

    return "\n".join(lines)
