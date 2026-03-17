"""Simplified global canonicalization: local node → global node mapping."""

from __future__ import annotations

from hashlib import sha256

from libs.embedding import EmbeddingModel
from libs.graph_ir.models import FactorNode, LocalCanonicalGraph, LocalParameterization

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

    # ── Step 5: Factor Integration ──
    # Lift local factors to global graph, replacing lcn_ IDs with gcn_ IDs.
    lcn_to_gcn = {b.local_canonical_id: b.global_canonical_id for b in bindings}
    global_factors: list[FactorNode] = []
    unresolved: list[str] = []

    for factor in local_graph.factor_nodes:
        premises_gcn = []
        all_resolved = True
        for p in factor.premises:
            gcn_id = lcn_to_gcn.get(p)
            if gcn_id is not None:
                premises_gcn.append(gcn_id)
            else:
                all_resolved = False
                unresolved.append(p)

        contexts_gcn = []
        for c in factor.contexts:
            gcn_id = lcn_to_gcn.get(c)
            if gcn_id is not None:
                contexts_gcn.append(gcn_id)
            # contexts are optional — don't mark as unresolved

        conclusion_gcn = lcn_to_gcn.get(factor.conclusion)
        if conclusion_gcn is None:
            all_resolved = False
            unresolved.append(factor.conclusion)

        if all_resolved and conclusion_gcn is not None:
            global_factors.append(
                FactorNode(
                    factor_id=factor.factor_id,
                    type=factor.type,
                    premises=premises_gcn,
                    contexts=contexts_gcn,
                    conclusion=conclusion_gcn,
                    source_ref=factor.source_ref,
                    metadata=factor.metadata,
                )
            )

    return CanonicalizationResult(
        bindings=bindings,
        new_global_nodes=new_global_nodes,
        matched_global_nodes=matched_global_nodes,
        global_factors=global_factors,
        unresolved_cross_refs=list(set(unresolved)),
    )
