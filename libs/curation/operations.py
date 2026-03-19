"""Graph modification operations for curation.

merge_nodes: Merge source into target, redirect all factor references.
create_constraint: Create equivalence or contradiction factor.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256

from libs.global_graph.models import GlobalCanonicalNode, PackageRef
from libs.storage.models import FactorNode


@dataclass
class MergeResult:
    """Result of merging two GlobalCanonicalNodes."""

    merged_node: GlobalCanonicalNode
    updated_factors: list[FactorNode]
    removed_node_id: str
    rollback_data: dict = field(default_factory=dict)


def merge_nodes(
    source_id: str,
    target_id: str,
    source: GlobalCanonicalNode,
    target: GlobalCanonicalNode,
    factors: list[FactorNode],
) -> MergeResult:
    """Merge source node into target node.

    - Combines member_local_nodes and provenance
    - Redirects all factor references from source_id -> target_id
    - Returns updated target node and modified factors

    Args:
        source_id: ID of the node to remove.
        target_id: ID of the node to keep.
        source: Source GlobalCanonicalNode.
        target: Target GlobalCanonicalNode (will be modified).
        factors: All factors in the graph (those referencing source will be updated).

    Returns:
        MergeResult with the merged node, updated factors, and rollback data.
    """
    # Combine member_local_nodes
    merged_members = list(target.member_local_nodes) + list(source.member_local_nodes)

    # Deduplicate provenance
    seen_prov: set[tuple[str, str]] = set()
    merged_prov: list[PackageRef] = []
    for p in list(target.provenance) + list(source.provenance):
        key = (p.package, p.version)
        if key not in seen_prov:
            seen_prov.add(key)
            merged_prov.append(p)

    # Merge metadata
    target_meta = dict(target.metadata or {})
    source_meta = dict(source.metadata or {})
    # Merge source_knowledge_names lists
    target_names = target_meta.get("source_knowledge_names", [])
    source_names = source_meta.get("source_knowledge_names", [])
    merged_names = list(dict.fromkeys(target_names + source_names))
    if merged_names:
        target_meta["source_knowledge_names"] = merged_names

    merged_node = target.model_copy(
        update={
            "member_local_nodes": merged_members,
            "provenance": merged_prov,
            "metadata": target_meta if target_meta else None,
        }
    )

    # Redirect factors
    updated_factors: list[FactorNode] = []
    original_factor_data: list[dict] = []

    for factor in factors:
        new_premises = [target_id if p == source_id else p for p in factor.premises]
        new_conclusion = target_id if factor.conclusion == source_id else factor.conclusion
        new_contexts = [target_id if c == source_id else c for c in factor.contexts]

        changed = (
            new_premises != factor.premises
            or new_conclusion != factor.conclusion
            or new_contexts != factor.contexts
        )

        if changed:
            original_factor_data.append(factor.model_dump())

        updated_factors.append(
            factor.model_copy(
                update={
                    "premises": new_premises,
                    "conclusion": new_conclusion,
                    "contexts": new_contexts,
                }
            )
        )

    rollback_data = {
        "source_id": source_id,
        "target_id": target_id,
        "source_node": source.model_dump(),
        "original_target_node": target.model_dump(),
        "original_factors": original_factor_data,
    }

    return MergeResult(
        merged_node=merged_node,
        updated_factors=updated_factors,
        removed_node_id=source_id,
        rollback_data=rollback_data,
    )


@dataclass
class AbstractionResult:
    """Result of creating an abstraction (schema node + instantiation factors)."""

    schema_node: GlobalCanonicalNode
    instantiation_factors: list[FactorNode]


def create_abstraction(
    abstraction_content: str,
    member_ids: list[str],
    reason: str = "",
) -> AbstractionResult:
    """Create a schema node and instantiation factors for an abstraction group.

    Args:
        abstraction_content: The common weaker conclusion text.
        member_ids: IDs of the member nodes being abstracted.
        reason: Why this abstraction was created.

    Returns:
        AbstractionResult with the schema node and per-member instantiation factors.
    """
    # Deterministic schema node ID
    sorted_members = sorted(member_ids)
    digest = sha256(":".join(sorted_members).encode()).hexdigest()[:16]
    schema_id = f"gcn_schema_{digest}"

    schema_node = GlobalCanonicalNode(
        global_canonical_id=schema_id,
        knowledge_type="claim",
        kind="schema",
        representative_content=abstraction_content,
        metadata={
            "curation_created": True,
            "abstraction_source_nodes": sorted_members,
            "abstraction_reason": reason,
        },
    )

    # One instantiation factor per member: schema → member
    factors: list[FactorNode] = []
    for member_id in sorted_members:
        pair_key = f"{schema_id}:{member_id}:instantiation"
        f_digest = sha256(pair_key.encode()).hexdigest()[:16]
        factor = FactorNode(
            factor_id=f"f_inst_{f_digest}",
            type="instantiation",
            premises=[schema_id],
            conclusion=member_id,
            package_id="__curation__",
            metadata={"curation_created": True},
        )
        factors.append(factor)

    return AbstractionResult(schema_node=schema_node, instantiation_factors=factors)


def create_constraint(
    node_a_id: str,
    node_b_id: str,
    constraint_type: str,
) -> tuple[FactorNode, GlobalCanonicalNode]:
    """Create an equivalence or contradiction factor between two nodes.

    Args:
        node_a_id: First node ID.
        node_b_id: Second node ID.
        constraint_type: "equivalence" or "contradiction".

    Returns:
        Tuple of (FactorNode, GlobalCanonicalNode for the relation).
    """
    # Deterministic IDs from the pair
    pair_key = f"{min(node_a_id, node_b_id)}:{max(node_a_id, node_b_id)}:{constraint_type}"
    digest = sha256(pair_key.encode()).hexdigest()[:16]
    factor_id = f"f_cur_{digest}"

    # Create relation node
    relation_node = GlobalCanonicalNode(
        global_canonical_id=f"gcn_rel_{digest}",
        knowledge_type=constraint_type,
        representative_content=f"{constraint_type} between {node_a_id} and {node_b_id}",
    )

    factor = FactorNode(
        factor_id=factor_id,
        type=constraint_type,  # "contradiction" or "equivalence"
        premises=[relation_node.global_canonical_id, node_a_id, node_b_id],
        contexts=[],
        conclusion=None,
        package_id="__curation__",
        metadata={"curation_created": True, "constraint_type": constraint_type},
    )
    return factor, relation_node
