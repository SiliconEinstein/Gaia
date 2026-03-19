"""Structure inspection — check graph health.

Detects: orphan nodes, dangling factors, high-degree nodes, disconnected components.
"""

from __future__ import annotations

from collections import defaultdict

from libs.global_graph.models import GlobalCanonicalNode
from libs.storage.models import FactorNode

from .models import StructureIssue, StructureReport


def inspect_structure(
    nodes: list[GlobalCanonicalNode],
    factors: list[FactorNode],
    high_degree_threshold: int = 20,
) -> StructureReport:
    """Inspect the global graph structure for health issues.

    Args:
        nodes: All GlobalCanonicalNodes in the graph.
        factors: All FactorNodes in the graph.
        high_degree_threshold: Flag nodes with degree above this.

    Returns:
        StructureReport with categorized issues.
    """
    if not nodes and not factors:
        return StructureReport()

    node_ids = {n.global_canonical_id for n in nodes}
    issues: list[StructureIssue] = []

    # Build degree map + adjacency for components
    degree: dict[str, int] = defaultdict(int)
    adjacency: dict[str, set[str]] = defaultdict(set)

    for factor in factors:
        all_refs = list(factor.premises) + ([factor.conclusion] if factor.conclusion else [])

        # Check for dangling references
        dangling = [ref for ref in all_refs if ref not in node_ids]
        if dangling:
            issues.append(
                StructureIssue(
                    issue_type="dangling_factor",
                    severity="error",
                    node_ids=dangling,
                    factor_ids=[factor.factor_id],
                    detail=f"Factor {factor.factor_id} references non-existent node(s): {dangling}",
                )
            )

        # Update degree and adjacency (only for existing nodes)
        existing_refs = [ref for ref in all_refs if ref in node_ids]
        for ref in existing_refs:
            degree[ref] += 1
        for i in range(len(existing_refs)):
            for j in range(i + 1, len(existing_refs)):
                adjacency[existing_refs[i]].add(existing_refs[j])
                adjacency[existing_refs[j]].add(existing_refs[i])

    # Orphan nodes: no factor connections
    for nid in node_ids:
        if degree[nid] == 0:
            issues.append(
                StructureIssue(
                    issue_type="orphan_node",
                    severity="warning",
                    node_ids=[nid],
                    detail=f"Node {nid} has no factor connections",
                )
            )

    # High-degree nodes
    for nid, deg in degree.items():
        if deg > high_degree_threshold:
            issues.append(
                StructureIssue(
                    issue_type="high_degree",
                    severity="info",
                    node_ids=[nid],
                    detail=f"Node {nid} has degree {deg} (threshold: {high_degree_threshold})",
                )
            )

    # Disconnected components (BFS)
    # Only check nodes that participate in at least one factor
    connected_nodes = {nid for nid in node_ids if degree[nid] > 0}
    if len(connected_nodes) > 1:
        visited: set[str] = set()
        component_count = 0
        for start in connected_nodes:
            if start in visited:
                continue
            component_count += 1
            queue = [start]
            while queue:
                current = queue.pop()
                if current in visited:
                    continue
                visited.add(current)
                for neighbor in adjacency[current]:
                    if neighbor not in visited:
                        queue.append(neighbor)

        if component_count > 1:
            issues.append(
                StructureIssue(
                    issue_type="disconnected_component",
                    severity="info",
                    detail=f"Graph has {component_count} disconnected components",
                )
            )

    return StructureReport(issues=issues)
