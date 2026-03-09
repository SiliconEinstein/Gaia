"""Convert DSL Package + beliefs into Node[] + HyperEdge[] for storage."""

from __future__ import annotations

from dataclasses import dataclass, field

from libs.dsl.compiler import DSLFactorGraph
from libs.dsl.models import (
    Declaration,
    Package,
    Question,
    Ref,
    Setting,
)
from libs.models import HyperEdge, Node


@dataclass
class StorageConversionResult:
    nodes: list[Node] = field(default_factory=list)
    edges: list[HyperEdge] = field(default_factory=list)
    name_to_id: dict[str, int] = field(default_factory=dict)


def convert_package_to_storage(
    pkg: Package,
    fg: DSLFactorGraph,
    beliefs: dict[str, float],
    start_node_id: int = 1,
    start_edge_id: int = 1,
) -> StorageConversionResult:
    """Convert a compiled DSL package into storage-layer Node and HyperEdge objects.

    Args:
        pkg: A loaded and resolved DSL Package.
        fg: The compiled factor graph (variables + factors).
        beliefs: Variable name -> posterior belief from BP inference.
        start_node_id: Starting ID for generated nodes.
        start_edge_id: Starting ID for generated edges.

    Returns:
        StorageConversionResult with nodes, edges, and name_to_id mapping.
    """
    result = StorageConversionResult()

    # Build declaration index: name -> resolved Declaration
    decls_by_name: dict[str, Declaration] = {}
    for mod in pkg.loaded_modules:
        for decl in mod.declarations:
            if isinstance(decl, Ref) and decl._resolved is not None:
                decls_by_name[decl.name] = decl._resolved
            else:
                decls_by_name[decl.name] = decl

    # Create a Node for each variable in the factor graph
    name_to_id: dict[str, int] = {}
    node_id = start_node_id
    for var_name, prior in fg.variables.items():
        decl = decls_by_name.get(var_name)
        if decl is None:
            continue

        # Map DSL type to storage node type
        node_type = "claim"
        if isinstance(decl, Setting):
            node_type = "setting"
        elif isinstance(decl, Question):
            node_type = "question"

        content = getattr(decl, "content", "") or ""

        node = Node(
            id=node_id,
            type=node_type,
            title=var_name,
            content=content.strip(),
            prior=prior,
            belief=beliefs.get(var_name),
            metadata={"source": "dsl", "package": pkg.name},
        )
        result.nodes.append(node)
        name_to_id[var_name] = node_id
        node_id += 1

    result.name_to_id = name_to_id

    # Create a HyperEdge for each factor in the factor graph
    edge_id = start_edge_id
    for factor in fg.factors:
        premise_ids = [name_to_id[n] for n in factor["premises"] if n in name_to_id]
        conclusion_ids = [name_to_id[n] for n in factor["conclusions"] if n in name_to_id]

        if not premise_ids and not conclusion_ids:
            continue

        edge = HyperEdge(
            id=edge_id,
            type=factor.get("edge_type", "deduction"),
            premises=premise_ids,
            conclusions=conclusion_ids,
            probability=factor.get("probability"),
            reasoning=[{"title": factor["name"], "content": ""}],
            metadata={"source": "dsl", "package": pkg.name},
        )
        result.edges.append(edge)
        edge_id += 1

    return result
