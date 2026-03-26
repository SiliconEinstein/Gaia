"""Orchestrate package ingest: persist_local -> canonicalize -> persist_global."""

from __future__ import annotations

from gaia.core.canonicalize import CanonicalizationResult, canonicalize_package
from gaia.core.local_params import LocalParameterization
from gaia.libs.embedding import EmbeddingModel
from gaia.libs.models.graph_ir import GlobalCanonicalGraph, LocalCanonicalGraph
from gaia.libs.storage.manager import StorageManager


async def run_ingest(
    local_graph: LocalCanonicalGraph,
    local_params: LocalParameterization,
    package_id: str,
    version: str,
    storage: StorageManager,
    embedding_model: EmbeddingModel | None = None,
) -> CanonicalizationResult:
    """Ingest a package: persist local, canonicalize, persist global.

    Orchestrates spec modules 1-3:
    1. persist_local: write local knowledge + factor nodes
    2. canonicalize: map lcn->gcn, lift factors, integrate params
    3. persist_global: write global nodes, factors, bindings, params
    """
    # Module 1: persist local graph
    await storage.write_knowledge_nodes(local_graph.knowledge_nodes)
    await storage.write_factor_nodes(local_graph.factor_nodes)

    # Module 2: canonicalize
    existing_nodes = await storage.get_knowledge_nodes(prefix="gcn_")
    existing_factors = await storage.get_factor_nodes(scope="global")
    global_graph = GlobalCanonicalGraph(
        knowledge_nodes=existing_nodes, factor_nodes=existing_factors
    )
    result = await canonicalize_package(
        local_graph=local_graph,
        local_params=local_params,
        global_graph=global_graph,
        package_id=package_id,
        version=version,
        embedding_model=embedding_model,
    )

    # Module 3: persist global results
    if result.new_global_nodes:
        await storage.write_knowledge_nodes(result.new_global_nodes)
    if result.global_factors:
        await storage.write_factor_nodes(result.global_factors)
    if result.bindings:
        await storage.write_bindings(result.bindings)
    if result.prior_records:
        await storage.write_prior_records(result.prior_records)
    if result.factor_param_records:
        await storage.write_factor_param_records(result.factor_param_records)
    if result.param_source is not None:
        await storage.write_param_source(result.param_source)

    return result
