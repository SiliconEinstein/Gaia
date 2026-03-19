"""Compile Typst loader output to Graph IR RawGraph.

Takes the dict produced by typst_loader.load_typst_package() and
produces a RawGraph with deterministic IDs and full source refs.
"""

from __future__ import annotations

from .build_utils import factor_id, raw_node_id
from .models import (
    FactorNode,
    RawGraph,
    RawKnowledgeNode,
    SourceRef,
)

_CONSTRAINT_TYPE_TO_FACTOR_TYPE = {
    "contradiction": "contradiction",
    "equivalence": "equivalence",
}


def compile_typst_to_raw_graph(graph_data: dict) -> RawGraph:
    """Compile typst_loader output dict to RawGraph.

    Args:
        graph_data: Dict with keys: package, version, nodes, factors, constraints.
                    Produced by typst_loader.load_typst_package().

    Returns:
        A RawGraph with deterministic node/factor IDs and source refs.
    """
    package = graph_data.get("package") or "unknown"
    version = graph_data.get("version") or "0.0.0"

    # Build constraint lookup for metadata injection
    constraint_map: dict[str, dict] = {}
    for constraint in graph_data.get("constraints", []):
        constraint_map[constraint["name"]] = constraint

    # 1. Compile nodes
    knowledge_nodes: list[RawKnowledgeNode] = []
    name_to_raw_id: dict[str, str] = {}

    for node in graph_data.get("nodes", []):
        name = node["name"]
        knowledge_type = node["type"]
        content = node.get("content", "")
        module = node.get("module", "unknown")

        if name in name_to_raw_id:
            raise ValueError(
                f"Duplicate node name '{name}' in package '{package}'. "
                "Node names must be unique within a package."
            )

        node_id = raw_node_id(
            package=package,
            version=version,
            module_name=module,
            knowledge_name=name,
            knowledge_type=knowledge_type,
            kind=None,
            content=content,
            parameters=[],
        )

        metadata = None
        if name in constraint_map:
            metadata = {"between": list(constraint_map[name]["between"])}

        knowledge_nodes.append(
            RawKnowledgeNode(
                raw_node_id=node_id,
                knowledge_type=knowledge_type,
                kind=None,
                content=content,
                parameters=[],
                source_refs=[
                    SourceRef(
                        package=package,
                        version=version,
                        module=module,
                        knowledge_name=name,
                    )
                ],
                metadata=metadata,
            )
        )
        name_to_raw_id[name] = node_id

    # 2. Compile reasoning factors
    factor_nodes: list[FactorNode] = []

    for factor in graph_data.get("factors", []):
        if factor.get("type") != "reasoning":
            continue

        conclusion_name = factor["conclusion"]
        premise_names = factor.get("premise", [])

        if conclusion_name not in name_to_raw_id:
            continue
        premise_ids = [name_to_raw_id[p] for p in premise_names if p in name_to_raw_id]
        if not premise_ids:
            continue

        # Determine module from the conclusion node
        conclusion_module = _find_node_module(graph_data["nodes"], conclusion_name)

        factor_nodes.append(
            FactorNode(
                factor_id=factor_id("infer", conclusion_module, conclusion_name),
                type="infer",
                premises=premise_ids,
                contexts=[],
                conclusion=name_to_raw_id[conclusion_name],
                source_ref=SourceRef(
                    package=package,
                    version=version,
                    module=conclusion_module,
                    knowledge_name=conclusion_name,
                ),
                metadata={"edge_type": "deduction"},
            )
        )

    # 3. Compile constraint factors
    for constraint in graph_data.get("constraints", []):
        constraint_name = constraint["name"]
        constraint_type = constraint["type"]
        between = constraint.get("between", [])

        if constraint_name not in name_to_raw_id:
            continue
        related_ids = [name_to_raw_id[b] for b in between if b in name_to_raw_id]
        if len(related_ids) < 2:
            continue

        ft = _CONSTRAINT_TYPE_TO_FACTOR_TYPE.get(constraint_type)
        if ft is None:
            continue

        constraint_module = _find_node_module(graph_data["nodes"], constraint_name)

        factor_nodes.append(
            FactorNode(
                factor_id=factor_id(ft, constraint_module, constraint_name),
                type=ft,
                premises=related_ids,
                contexts=[],
                conclusion=name_to_raw_id[constraint_name],
                source_ref=SourceRef(
                    package=package,
                    version=version,
                    module=constraint_module,
                    knowledge_name=constraint_name,
                ),
                metadata={"edge_type": f"relation_{constraint_type}"},
            )
        )

    return RawGraph(
        package=package,
        version=version,
        knowledge_nodes=knowledge_nodes,
        factor_nodes=factor_nodes,
    )


def _find_node_module(nodes: list[dict], name: str) -> str:
    """Find the module of a node by name."""
    for node in nodes:
        if node["name"] == name:
            return node.get("module", "unknown")
    return "unknown"
