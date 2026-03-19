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


def _build_ext_resolver(global_graph: GlobalGraph) -> dict[str, str]:
    """Build a mapping from ext:package.knowledge_name → gcn_id.

    Uses source_knowledge_names stored in GlobalCanonicalNode metadata
    during canonicalization.
    """
    ext_to_gcn: dict[str, str] = {}
    for node in global_graph.knowledge_nodes:
        # Each global node stores which (package, knowledge_name) pairs it represents
        source_names = (node.metadata or {}).get("source_knowledge_names", [])
        for entry in source_names:
            # entry format: "package.knowledge_name"
            ext_to_gcn[f"ext:{entry}"] = node.global_canonical_id
    return ext_to_gcn


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

    Then lift local factors to global graph, resolving ext: cross-package
    references against existing global nodes.
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

        # Derive source knowledge_name for ext: resolution later
        source_name = node.source_refs[0].knowledge_name if node.source_refs else ""
        source_entry = f"{local_graph.package}.{source_name}"

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
                # Add source_knowledge_name for ext: resolution
                meta = existing_node.metadata or {}
                names = meta.get("source_knowledge_names", [])
                if source_entry not in names:
                    names.append(source_entry)
                meta["source_knowledge_names"] = names
                existing_node.metadata = meta
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
                metadata={
                    **(node.metadata or {}),
                    "source_knowledge_names": [source_entry],
                },
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
    # Build ID resolver: lcn_ → gcn_ for local nodes, ext: → gcn_ for cross-package
    lcn_to_gcn = {b.local_canonical_id: b.global_canonical_id for b in bindings}

    # Rebuild ext: resolver including newly created nodes
    temp_graph = GlobalGraph(knowledge_nodes=list(global_graph.knowledge_nodes) + new_global_nodes)
    ext_to_gcn = _build_ext_resolver(temp_graph)

    def _resolve_id(ref_id: str) -> str | None:
        if ref_id.startswith("ext:"):
            return ext_to_gcn.get(ref_id)
        return lcn_to_gcn.get(ref_id)

    global_factors: list[FactorNode] = []
    unresolved: list[str] = []

    for factor in local_graph.factor_nodes:
        premises_gcn = []
        all_resolved = True
        for p in factor.premises:
            gcn_id = _resolve_id(p)
            if gcn_id is not None:
                premises_gcn.append(gcn_id)
            else:
                all_resolved = False
                unresolved.append(p)

        contexts_gcn = []
        for c in factor.contexts:
            gcn_id = _resolve_id(c)
            if gcn_id is not None:
                contexts_gcn.append(gcn_id)

        conclusion_gcn = _resolve_id(factor.conclusion)
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
