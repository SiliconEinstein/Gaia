"""Linearize a coarse reasoning graph into a narrative outline.

Topological sort → layering → connectivity-based grouping → narrative sections.
Grouping uses high-cohesion/low-coupling: nodes sharing premises or conclusions
are grouped together, independent of the Python module structure.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class NarrativeEntry:
    """One claim in the narrative outline."""

    kid: str
    label: str
    title: str
    type: str
    exported: bool
    prior: float | None
    belief: float | None
    derived_from: list[str]
    supports: list[str]
    strategy_type: str
    mi_bits: float


@dataclass
class NarrativeSection:
    """A group of entries forming a narrative section."""

    title: str
    layer: int
    entries: list[NarrativeEntry] = field(default_factory=list)


def _union_find_group(
    nodes: list[str],
    edges: list[tuple[str, str]],
) -> list[set[str]]:
    """Cluster nodes by connectivity using union-find."""
    parent: dict[str, str] = {n: n for n in nodes}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: str, b: str) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    for a, b in edges:
        if a in parent and b in parent:
            union(a, b)

    groups: dict[str, set[str]] = {}
    for n in nodes:
        root = find(n)
        groups.setdefault(root, set()).add(n)
    return list(groups.values())


def linearize_narrative(
    coarse: dict,
    beliefs: dict[str, float] | None = None,
    priors: dict[str, float] | None = None,
    mi_per_strategy: dict[int, float] | None = None,
) -> list[NarrativeSection]:
    """Convert a coarse reasoning DAG into a linear narrative outline.

    Algorithm:
    1. Build adjacency from coarse strategies + operators
    2. Topological sort → assign layer to each node
    3. Within each layer, group nodes by shared connectivity
       (high cohesion / low coupling — not based on Python modules)
    4. Name each group by its most prominent claim
    5. Merge consecutive groups that are tightly connected
    """
    beliefs = beliefs or {}
    priors = priors or {}
    mi_map = mi_per_strategy or {}

    kid_to_k = {k["id"]: k for k in coarse["knowledges"]}
    exported_ids = {k["id"] for k in coarse["knowledges"] if k.get("exported")}

    # Build adjacency
    forward: dict[str, list[str]] = {}
    backward: dict[str, list[str]] = {}
    strategy_for_conclusion: dict[str, dict] = {}
    strategy_idx_for_conclusion: dict[str, int] = {}

    for i, s in enumerate(coarse["strategies"]):
        conc = s["conclusion"]
        strategy_for_conclusion[conc] = s
        strategy_idx_for_conclusion[conc] = i
        for p in s["premises"]:
            forward.setdefault(p, []).append(conc)
            backward.setdefault(conc, []).append(p)

    for o in coarse.get("operators", []):
        conc = o.get("conclusion")
        for v in o.get("variables", []):
            if conc:
                forward.setdefault(v, []).append(conc)
                backward.setdefault(conc, []).append(v)

    # Topological sort → layer assignment
    all_kids = {k["id"] for k in coarse["knowledges"] if not k.get("label", "").startswith("__")}
    in_degree: dict[str, int] = {kid: 0 for kid in all_kids}
    for conc, plist in backward.items():
        if conc in all_kids:
            in_degree[conc] = len([p for p in plist if p in all_kids])

    layers: dict[str, int] = {}
    queue = [kid for kid in all_kids if in_degree.get(kid, 0) == 0]
    layer = 0
    while queue:
        next_queue: list[str] = []
        for kid in queue:
            layers[kid] = layer
        for kid in queue:
            for neighbor in forward.get(kid, []):
                if neighbor in all_kids and neighbor not in layers:
                    in_degree[neighbor] -= 1
                    if in_degree[neighbor] <= 0:
                        next_queue.append(neighbor)
        queue = next_queue
        layer += 1

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
        if kid not in all_kids:
            continue

        derived_labels = []
        stype = ""
        mi = 0.0
        if kid in strategy_for_conclusion:
            s = strategy_for_conclusion[kid]
            stype = s.get("type", "")
            derived_labels = [kid_to_k[p].get("label", "?") for p in s["premises"] if p in kid_to_k]
            idx = strategy_idx_for_conclusion.get(kid)
            if idx is not None:
                mi = mi_map.get(idx, 0.0)

        supports_labels = [
            kid_to_k[c].get("label", "?") for c in forward.get(kid, []) if c in kid_to_k
        ]

        entries_by_kid[kid] = NarrativeEntry(
            kid=kid,
            label=label,
            title=k.get("title") or label,
            type=k.get("type", "claim"),
            exported=kid in exported_ids,
            prior=priors.get(kid),
            belief=beliefs.get(kid),
            derived_from=derived_labels,
            supports=supports_labels,
            strategy_type=stype,
            mi_bits=mi,
        )

    # Group within each layer by shared connectivity
    # Two nodes in the same layer are connected if they share a parent or child
    sections: list[NarrativeSection] = []
    for lyr in range(max_layer + 1):
        layer_kids = [kid for kid in all_kids if layers.get(kid) == lyr and kid in entries_by_kid]
        if not layer_kids:
            continue

        # Build affinity edges: two nodes are connected if they share
        # a common premise, a common conclusion, or a common operator
        affinity_edges: list[tuple[str, str]] = []
        # Shared parent: two nodes derived from the same premise
        parent_to_children: dict[str, list[str]] = {}
        for kid in layer_kids:
            for p in backward.get(kid, []):
                parent_to_children.setdefault(p, []).append(kid)
        for _parent, children in parent_to_children.items():
            for i in range(len(children)):
                for j in range(i + 1, len(children)):
                    affinity_edges.append((children[i], children[j]))

        # Shared child: two nodes that support the same conclusion
        child_to_parents: dict[str, list[str]] = {}
        for kid in layer_kids:
            for c in forward.get(kid, []):
                child_to_parents.setdefault(c, []).append(kid)
        for _child, parents in child_to_parents.items():
            for i in range(len(parents)):
                for j in range(i + 1, len(parents)):
                    affinity_edges.append((parents[i], parents[j]))

        groups = _union_find_group(layer_kids, affinity_edges)

        for group in sorted(
            groups,
            key=lambda g: min(entries_by_kid[k].belief or 0 for k in g if k in entries_by_kid),
        ):
            # Name the group by its most prominent entry
            group_entries = [entries_by_kid[kid] for kid in group if kid in entries_by_kid]
            group_entries.sort(key=lambda e: (e.exported, e.belief or 0))

            # Pick a descriptive name: the highest-belief exported claim, or the first entry
            name_entry = group_entries[-1] if group_entries else None
            group_title = name_entry.title if name_entry else f"Layer {lyr}"

            sections.append(
                NarrativeSection(
                    title=group_title,
                    layer=lyr,
                    entries=group_entries,
                )
            )

    return sections


def render_narrative_outline(sections: list[NarrativeSection]) -> str:
    """Render narrative sections as markdown for agent consumption."""
    lines: list[str] = []
    lines.append("# Narrative Outline")
    lines.append("")
    lines.append(
        "Auto-generated from the coarse reasoning graph. "
        "Sections are grouped by connectivity (high cohesion, low coupling) "
        "and ordered by topological layer. Use this as the backbone for "
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
                f"{entry_num}. **{entry.title}{star}** (prior: {prior_str} → belief: {belief_str})"
            )

            if entry.derived_from:
                mi_str = f" [{entry.mi_bits:.2f} bits]" if entry.mi_bits > 0 else ""
                lines.append(
                    f"   - ← {entry.strategy_type}({', '.join(entry.derived_from)}){mi_str}"
                )

            if entry.supports:
                lines.append(f"   - → supports: {', '.join(entry.supports)}")

            lines.append("")

    return "\n".join(lines)
