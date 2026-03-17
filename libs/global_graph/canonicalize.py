"""Simplified global canonicalization: local node → global node mapping."""

from __future__ import annotations

from hashlib import sha256

from libs.embedding import EmbeddingModel
from libs.graph_ir.models import LocalCanonicalGraph, LocalParameterization

from .models import (
    CanonicalBinding,
    CanonicalizationResult,
    GlobalCanonicalNode,
    GlobalGraph,
    LocalCanonicalRef,
    PackageRef,
)
from .similarity import find_best_match

MATCH_THRESHOLD = 0.90


def _generate_gcn_id(content: str, knowledge_type: str, counter: int) -> str:
    """Generate a deterministic global canonical ID."""
    payload = f"{knowledge_type}:{content}:{counter}"
    digest = sha256(payload.encode("utf-8")).hexdigest()
    return f"gcn_{digest[:16]}"


async def canonicalize_package(
    local_graph: LocalCanonicalGraph,
    local_params: LocalParameterization,
    global_graph: GlobalGraph,
    threshold: float = MATCH_THRESHOLD,
    embedding_model: EmbeddingModel | None = None,
) -> CanonicalizationResult:
    """Map local canonical nodes to global graph.

    For each LocalCanonicalNode:
    - Search global graph for best match above threshold
    - match_existing: bind to existing GlobalCanonicalNode
    - create_new: create new GlobalCanonicalNode

    Returns CanonicalizationResult with bindings and new/matched nodes.
    """
    bindings: list[CanonicalBinding] = []
    new_global_nodes: list[GlobalCanonicalNode] = []
    matched_global_nodes: list[str] = []

    graph_hash = local_graph.graph_hash()
    existing_nodes = list(global_graph.knowledge_nodes)

    for node in local_graph.knowledge_nodes:
        content = node.representative_content
        match = await find_best_match(
            content,
            node.knowledge_type,
            node.kind,
            existing_nodes,
            threshold,
            embedding_model=embedding_model,
        )

        if match is not None:
            gcn_id, score = match
            bindings.append(
                CanonicalBinding(
                    package=local_graph.package,
                    version=local_graph.version,
                    local_graph_hash=graph_hash,
                    local_canonical_id=node.local_canonical_id,
                    decision="match_existing",
                    global_canonical_id=gcn_id,
                    reason=f"cosine similarity {score:.3f}",
                )
            )
            matched_global_nodes.append(gcn_id)

            # Update existing node's membership
            existing_node = global_graph.node_index.get(gcn_id)
            if existing_node is not None:
                existing_node.member_local_nodes.append(
                    LocalCanonicalRef(
                        package=local_graph.package,
                        version=local_graph.version,
                        local_canonical_id=node.local_canonical_id,
                    )
                )
                pkg_ref = PackageRef(package=local_graph.package, version=local_graph.version)
                if pkg_ref not in existing_node.provenance:
                    existing_node.provenance.append(pkg_ref)
        else:
            gcn_id = _generate_gcn_id(
                content,
                node.knowledge_type,
                len(existing_nodes) + len(new_global_nodes),
            )
            gcn = GlobalCanonicalNode(
                global_canonical_id=gcn_id,
                knowledge_type=node.knowledge_type,
                kind=node.kind,
                representative_content=content,
                parameters=node.parameters,
                member_local_nodes=[
                    LocalCanonicalRef(
                        package=local_graph.package,
                        version=local_graph.version,
                        local_canonical_id=node.local_canonical_id,
                    )
                ],
                provenance=[PackageRef(package=local_graph.package, version=local_graph.version)],
                metadata=node.metadata,
            )
            new_global_nodes.append(gcn)
            existing_nodes.append(gcn)

            bindings.append(
                CanonicalBinding(
                    package=local_graph.package,
                    version=local_graph.version,
                    local_graph_hash=graph_hash,
                    local_canonical_id=node.local_canonical_id,
                    decision="create_new",
                    global_canonical_id=gcn_id,
                )
            )

    return CanonicalizationResult(
        bindings=bindings,
        new_global_nodes=new_global_nodes,
        matched_global_nodes=matched_global_nodes,
        unresolved_cross_refs=[],
    )
