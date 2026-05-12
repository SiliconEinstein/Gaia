"""Linearize a coarse reasoning graph into a narrative outline.

Topological sort → layering → connectivity-based grouping → narrative sections.
Grouping uses high-cohesion/low-coupling: nodes sharing premises or conclusions
are grouped together, independent of the Python module structure.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


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


@dataclass(frozen=True)
class _NarrativeGraph:
    """Intermediate graph indexes used for narrative linearization."""

    kid_to_k: dict[str, dict[str, Any]]
    exported_ids: set[str]
    forward: dict[str, list[str]]
    backward: dict[str, list[str]]
    strategy_for_conclusion: dict[str, dict[str, Any]]
    strategy_idx_for_conclusion: dict[str, int]
    all_kids: set[str]


def _narrative_graph_indexes(coarse: dict[str, Any]) -> _NarrativeGraph:
    """Build adjacency and strategy lookup indexes for a coarse graph."""
    kid_to_k = {k["id"]: k for k in coarse["knowledges"]}
    exported_ids = {k["id"] for k in coarse["knowledges"] if k.get("exported")}
    forward: dict[str, list[str]] = {}
    backward: dict[str, list[str]] = {}
    strategy_for_conclusion: dict[str, dict[str, Any]] = {}
    strategy_idx_for_conclusion: dict[str, int] = {}

    for i, strategy in enumerate(coarse["strategies"]):
        conclusion = strategy["conclusion"]
        strategy_for_conclusion[conclusion] = strategy
        strategy_idx_for_conclusion[conclusion] = i
        for premise in strategy["premises"]:
            forward.setdefault(premise, []).append(conclusion)
            backward.setdefault(conclusion, []).append(premise)

    for operator in coarse.get("operators", []):
        conclusion = operator.get("conclusion")
        for variable in operator.get("variables", []):
            if conclusion:
                forward.setdefault(variable, []).append(conclusion)
                backward.setdefault(conclusion, []).append(variable)

    all_kids = {k["id"] for k in coarse["knowledges"] if not k.get("label", "").startswith("__")}
    return _NarrativeGraph(
        kid_to_k=kid_to_k,
        exported_ids=exported_ids,
        forward=forward,
        backward=backward,
        strategy_for_conclusion=strategy_for_conclusion,
        strategy_idx_for_conclusion=strategy_idx_for_conclusion,
        all_kids=all_kids,
    )


def _narrative_layers(graph: _NarrativeGraph) -> dict[str, int]:
    """Assign topological layers to non-helper knowledge ids."""
    in_degree: dict[str, int] = dict.fromkeys(graph.all_kids, 0)
    for conclusion, premises in graph.backward.items():
        if conclusion in graph.all_kids:
            in_degree[conclusion] = len([p for p in premises if p in graph.all_kids])

    layers: dict[str, int] = {}
    queue = [kid for kid in graph.all_kids if in_degree.get(kid, 0) == 0]
    layer = 0
    while queue:
        next_queue: list[str] = []
        for kid in queue:
            layers[kid] = layer
        for kid in queue:
            for neighbor in graph.forward.get(kid, []):
                if neighbor in graph.all_kids and neighbor not in layers:
                    in_degree[neighbor] -= 1
                    if in_degree[neighbor] <= 0:
                        next_queue.append(neighbor)
        queue = next_queue
        layer += 1

    for kid in graph.all_kids:
        if kid not in layers:
            layers[kid] = layer
    return layers


def _narrative_entry(
    knowledge: dict[str, Any],
    graph: _NarrativeGraph,
    beliefs: dict[str, float],
    priors: dict[str, float],
    mi_map: dict[int, float],
) -> NarrativeEntry | None:
    """Build one narrative entry, skipping helpers and non-outline nodes."""
    kid = knowledge["id"]
    label = knowledge.get("label", "")
    if label.startswith("__") or kid not in graph.all_kids:
        return None

    derived_labels: list[str] = []
    strategy_type = ""
    mi = 0.0
    if kid in graph.strategy_for_conclusion:
        strategy = graph.strategy_for_conclusion[kid]
        strategy_type = strategy.get("type", "")
        derived_labels = [
            graph.kid_to_k[p].get("label", "?") for p in strategy["premises"] if p in graph.kid_to_k
        ]
        idx = graph.strategy_idx_for_conclusion.get(kid)
        if idx is not None:
            mi = mi_map.get(idx, 0.0)

    supports_labels = [
        graph.kid_to_k[c].get("label", "?")
        for c in graph.forward.get(kid, [])
        if c in graph.kid_to_k
    ]
    return NarrativeEntry(
        kid=kid,
        label=label,
        title=knowledge.get("title") or label,
        type=knowledge.get("type", "claim"),
        exported=kid in graph.exported_ids,
        prior=priors.get(kid),
        belief=beliefs.get(kid),
        derived_from=derived_labels,
        supports=supports_labels,
        strategy_type=strategy_type,
        mi_bits=mi,
    )


def _narrative_entries_by_kid(
    coarse: dict[str, Any],
    graph: _NarrativeGraph,
    beliefs: dict[str, float],
    priors: dict[str, float],
    mi_map: dict[int, float],
) -> dict[str, NarrativeEntry]:
    """Build narrative entries keyed by knowledge id."""
    entries: dict[str, NarrativeEntry] = {}
    for knowledge in coarse["knowledges"]:
        entry = _narrative_entry(knowledge, graph, beliefs, priors, mi_map)
        if entry is not None:
            entries[entry.kid] = entry
    return entries


def _layer_affinity_edges(
    layer_kids: list[str],
    graph: _NarrativeGraph,
) -> list[tuple[str, str]]:
    """Build connectivity edges among nodes in one narrative layer."""
    affinity_edges: list[tuple[str, str]] = []
    parent_to_children: dict[str, list[str]] = {}
    for kid in layer_kids:
        for parent in graph.backward.get(kid, []):
            parent_to_children.setdefault(parent, []).append(kid)
    for children in parent_to_children.values():
        affinity_edges.extend(
            (children[i], children[j])
            for i in range(len(children))
            for j in range(i + 1, len(children))
        )

    child_to_parents: dict[str, list[str]] = {}
    for kid in layer_kids:
        for child in graph.forward.get(kid, []):
            child_to_parents.setdefault(child, []).append(kid)
    for parents in child_to_parents.values():
        affinity_edges.extend(
            (parents[i], parents[j])
            for i in range(len(parents))
            for j in range(i + 1, len(parents))
        )
    return affinity_edges


def _narrative_sections(
    graph: _NarrativeGraph,
    layers: dict[str, int],
    entries_by_kid: dict[str, NarrativeEntry],
) -> list[NarrativeSection]:
    """Group narrative entries by layer and shared connectivity."""
    sections: list[NarrativeSection] = []
    max_layer = max(layers.values()) if layers else 0
    for layer in range(max_layer + 1):
        layer_kids = [
            kid for kid in graph.all_kids if layers.get(kid) == layer and kid in entries_by_kid
        ]
        if not layer_kids:
            continue
        groups = _union_find_group(layer_kids, _layer_affinity_edges(layer_kids, graph))
        for group in sorted(
            groups,
            key=lambda g: min(entries_by_kid[k].belief or 0 for k in g if k in entries_by_kid),
        ):
            group_entries = [entries_by_kid[kid] for kid in group if kid in entries_by_kid]
            group_entries.sort(key=lambda e: (e.exported, e.belief or 0))
            name_entry = group_entries[-1] if group_entries else None
            sections.append(
                NarrativeSection(
                    title=name_entry.title if name_entry else f"Layer {layer}",
                    layer=layer,
                    entries=group_entries,
                )
            )
    return sections


def linearize_narrative(
    coarse: dict[str, Any],
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
    graph = _narrative_graph_indexes(coarse)
    layers = _narrative_layers(graph)
    entries_by_kid = _narrative_entries_by_kid(coarse, graph, beliefs, priors, mi_map)
    return _narrative_sections(graph, layers, entries_by_kid)


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
