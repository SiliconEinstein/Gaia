"""StorageManager — unified facade for ContentStore, GraphStore, and VectorStore."""

from __future__ import annotations

import logging

from libs.storage_v2.config import StorageConfig
from libs.storage_v2.content_store import ContentStore
from libs.storage_v2.graph_store import GraphStore
from libs.storage_v2.models import (
    BeliefSnapshot,
    Chain,
    Knowledge,
    KnowledgeEmbedding,
    Module,
    Package,
    ProbabilityRecord,
    Resource,
    ResourceAttachment,
    ScoredKnowledge,
    Subgraph,
)
from libs.storage_v2.vector_store import VectorStore

logger = logging.getLogger(__name__)


class StorageManager:
    """Unified storage facade. Domain services only touch this class."""

    def __init__(self, config: StorageConfig) -> None:
        self._config = config
        self.content_store: ContentStore | None = None
        self.graph_store: GraphStore | None = None
        self.vector_store: VectorStore | None = None

    async def initialize(self) -> None:
        """Instantiate and initialize all configured stores."""
        from libs.storage_v2.lance_content_store import LanceContentStore
        from libs.storage_v2.lance_vector_store import LanceVectorStore

        # ContentStore — always required
        cs = LanceContentStore(self._config.lancedb_path)
        await cs.initialize()
        self.content_store = cs

        # GraphStore — optional
        if self._config.graph_backend == "kuzu":
            from libs.storage_v2.kuzu_graph_store import KuzuGraphStore

            kuzu_path = self._config.kuzu_path or (self._config.lancedb_path + "_kuzu")
            gs = KuzuGraphStore(kuzu_path)
            await gs.initialize_schema()
            self.graph_store = gs
        elif self._config.graph_backend == "neo4j":
            logger.warning("Neo4j graph backend not yet implemented in v2; skipping")
        # else: "none" — graph_store stays None

        # VectorStore — always created (same LanceDB path, separate table)
        vs = LanceVectorStore(self._config.lancedb_path)
        self.vector_store = vs

    async def close(self) -> None:
        """Release connections held by stores."""
        if self.graph_store is not None:
            await self.graph_store.close()

    # ── Three-Write: ingest_package ──

    async def ingest_package(
        self,
        package: Package,
        modules: list[Module],
        knowledge_items: list[Knowledge],
        chains: list[Chain],
        embeddings: list[KnowledgeEmbedding] | None = None,
    ) -> None:
        """Write a complete package to all stores with publish state machine.

        1. Write package as 'preparing' (invisible to reads).
        2. Write content, graph, vector idempotently.
        3. Flip status to 'committed' (visible to reads).

        On failure, data stays in 'preparing' — invisible and safe to retry.
        """
        # Force status to 'preparing' during writes
        preparing_pkg = package.model_copy(update={"status": "preparing"})
        pkg_version = preparing_pkg.version

        # Propagate package version to downstream models
        versioned_modules = [m.model_copy(update={"package_version": pkg_version}) for m in modules]
        versioned_knowledge = [
            k.model_copy(update={"source_package_version": pkg_version}) for k in knowledge_items
        ]
        versioned_chains = [c.model_copy(update={"package_version": pkg_version}) for c in chains]

        # Step 1: ContentStore (source of truth)
        await self.content_store.write_package(preparing_pkg, versioned_modules)
        await self.content_store.write_knowledge(versioned_knowledge)
        await self.content_store.write_chains(versioned_chains)

        # Step 2: GraphStore (optional, idempotent)
        if self.graph_store is not None:
            await self.graph_store.write_topology(versioned_knowledge, versioned_chains)

        # Step 3: VectorStore (optional, idempotent)
        if self.vector_store is not None and embeddings:
            await self.vector_store.write_embeddings(embeddings)

        # Step 4: Commit — flip to visible
        await self.content_store.commit_package(preparing_pkg.package_id, pkg_version)

    # ── Passthrough writes ──

    async def add_probabilities(self, records: list[ProbabilityRecord]) -> None:
        """Write probabilities to ContentStore + sync to GraphStore."""
        await self.content_store.write_probabilities(records)
        if self.graph_store is not None:
            for r in records:
                await self.graph_store.update_probability(r.chain_id, r.step_index, r.value)

    async def write_beliefs(self, snapshots: list[BeliefSnapshot]) -> None:
        """Write belief snapshots to ContentStore + sync to GraphStore."""
        await self.content_store.write_belief_snapshots(snapshots)
        if self.graph_store is not None:
            await self.graph_store.update_beliefs(snapshots)

    async def write_resources(
        self, resources: list[Resource], attachments: list[ResourceAttachment]
    ) -> None:
        """Write resources to ContentStore + link in GraphStore."""
        await self.content_store.write_resources(resources, attachments)
        if self.graph_store is not None:
            await self.graph_store.write_resource_links(attachments)

    # ── Read delegation (ContentStore) ──

    async def get_knowledge(self, knowledge_id: str, version: int | None = None):
        return await self.content_store.get_knowledge(knowledge_id, version)

    async def get_knowledge_versions(self, knowledge_id: str):
        return await self.content_store.get_knowledge_versions(knowledge_id)

    async def get_package(self, package_id: str):
        return await self.content_store.get_package(package_id)

    async def get_module(self, module_id: str):
        return await self.content_store.get_module(module_id)

    async def get_chains_by_module(self, module_id: str):
        return await self.content_store.get_chains_by_module(module_id)

    async def get_probability_history(self, chain_id: str, step_index: int | None = None):
        return await self.content_store.get_probability_history(chain_id, step_index)

    async def get_belief_history(self, knowledge_id: str):
        return await self.content_store.get_belief_history(knowledge_id)

    async def get_resources_for(self, target_type: str, target_id: str):
        return await self.content_store.get_resources_for(target_type, target_id)

    async def search_bm25(self, text: str, top_k: int):
        return await self.content_store.search_bm25(text, top_k)

    async def list_knowledge(self):
        return await self.content_store.list_knowledge()

    async def list_chains(self):
        return await self.content_store.list_chains()

    # ── Visibility helpers ──

    async def _filter_subgraph(self, subgraph: Subgraph) -> Subgraph:
        """Filter a Subgraph to only include IDs from committed packages."""
        # Filter knowledge_ids via ContentStore (already visibility-gated)
        visible_kids: set[str] = set()
        for kid in subgraph.knowledge_ids:
            k = await self.content_store.get_knowledge(kid)
            if k is not None:
                visible_kids.add(kid)
        # Filter chain_ids: list_chains() is already visibility-gated
        all_visible_chains = await self.content_store.list_chains()
        visible_chain_ids = {c.chain_id for c in all_visible_chains}
        visible_chains = subgraph.chain_ids & visible_chain_ids
        return Subgraph(knowledge_ids=visible_kids, chain_ids=visible_chains)

    # ── Read delegation (GraphStore — degraded-safe) ──

    async def get_neighbors(
        self,
        knowledge_id: str,
        direction: str = "both",
        chain_types: list[str] | None = None,
        max_hops: int = 1,
    ):
        if self.graph_store is None:
            return Subgraph()
        raw = await self.graph_store.get_neighbors(knowledge_id, direction, chain_types, max_hops)
        return await self._filter_subgraph(raw)

    async def get_subgraph(self, knowledge_id: str, max_knowledge: int = 500):
        if self.graph_store is None:
            return Subgraph()
        raw = await self.graph_store.get_subgraph(knowledge_id, max_knowledge)
        return await self._filter_subgraph(raw)

    async def search_topology(self, seed_ids: list[str], hops: int = 1):
        if self.graph_store is None:
            return []
        results = await self.graph_store.search_topology(seed_ids, hops)
        # Hydrate stubs through ContentStore (visibility-gated)
        filtered: list[ScoredKnowledge] = []
        for r in results:
            k = await self.content_store.get_knowledge(
                r.knowledge.knowledge_id, r.knowledge.version
            )
            if k is not None:
                filtered.append(ScoredKnowledge(knowledge=k, score=r.score))
        return filtered

    # ── Read delegation (VectorStore — degraded-safe) ──

    async def search_vector(self, embedding: list[float], top_k: int):
        if self.vector_store is None:
            return []
        results = await self.vector_store.search(embedding, top_k)
        # VectorStore returns stubs without source_package_id; hydrate via ContentStore
        filtered: list[ScoredKnowledge] = []
        for r in results:
            k = await self.content_store.get_knowledge(
                r.knowledge.knowledge_id, r.knowledge.version
            )
            if k is not None:  # visibility-gated
                filtered.append(ScoredKnowledge(knowledge=k, score=r.score))
        return filtered
