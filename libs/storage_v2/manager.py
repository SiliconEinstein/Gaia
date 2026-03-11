"""StorageManager — unified facade for ContentStore, GraphStore, and VectorStore."""

from __future__ import annotations

import logging

from libs.storage_v2.config import StorageConfig
from libs.storage_v2.content_store import ContentStore
from libs.storage_v2.graph_store import GraphStore
from libs.storage_v2.models import (
    Chain,
    Closure,
    ClosureEmbedding,
    Module,
    Package,
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
        closures: list[Closure],
        chains: list[Chain],
        embeddings: list[ClosureEmbedding] | None = None,
    ) -> None:
        """Write a complete package to all stores with compensating rollback.

        Write order: ContentStore → GraphStore → VectorStore.
        On failure, previously-written stores are cleaned up via delete_package.
        """
        package_id = package.package_id

        # Step 1: ContentStore (source of truth)
        await self.content_store.write_package(package, modules)
        await self.content_store.write_closures(closures)
        await self.content_store.write_chains(chains)

        # Step 2: GraphStore (optional)
        if self.graph_store is not None:
            try:
                await self.graph_store.write_topology(closures, chains)
            except Exception:
                logger.error("GraphStore write failed; rolling back ContentStore")
                await self.content_store.delete_package(package_id)
                raise

        # Step 3: VectorStore (optional)
        if self.vector_store is not None and embeddings:
            try:
                await self.vector_store.write_embeddings(embeddings)
            except Exception:
                logger.error("VectorStore write failed; rolling back ContentStore + GraphStore")
                if self.graph_store is not None:
                    await self.graph_store.delete_package(package_id)
                await self.content_store.delete_package(package_id)
                raise

    # ── Read delegation (ContentStore) ──

    async def get_closure(self, closure_id: str, version: int | None = None):
        return await self.content_store.get_closure(closure_id, version)

    async def get_closure_versions(self, closure_id: str):
        return await self.content_store.get_closure_versions(closure_id)

    async def get_package(self, package_id: str):
        return await self.content_store.get_package(package_id)

    async def get_module(self, module_id: str):
        return await self.content_store.get_module(module_id)

    async def get_chains_by_module(self, module_id: str):
        return await self.content_store.get_chains_by_module(module_id)

    async def get_probability_history(self, chain_id: str, step_index: int | None = None):
        return await self.content_store.get_probability_history(chain_id, step_index)

    async def get_belief_history(self, closure_id: str):
        return await self.content_store.get_belief_history(closure_id)

    async def get_resources_for(self, target_type: str, target_id: str):
        return await self.content_store.get_resources_for(target_type, target_id)

    async def search_bm25(self, text: str, top_k: int):
        return await self.content_store.search_bm25(text, top_k)

    async def list_closures(self):
        return await self.content_store.list_closures()

    async def list_chains(self):
        return await self.content_store.list_chains()

    # ── Read delegation (GraphStore — degraded-safe) ──

    async def get_neighbors(
        self,
        closure_id: str,
        direction: str = "both",
        chain_types: list[str] | None = None,
        max_hops: int = 1,
    ):
        if self.graph_store is None:
            return Subgraph()
        return await self.graph_store.get_neighbors(closure_id, direction, chain_types, max_hops)

    async def get_subgraph(self, closure_id: str, max_closures: int = 500):
        if self.graph_store is None:
            return Subgraph()
        return await self.graph_store.get_subgraph(closure_id, max_closures)

    async def search_topology(self, seed_ids: list[str], hops: int = 1):
        if self.graph_store is None:
            return []
        return await self.graph_store.search_topology(seed_ids, hops)

    # ── Read delegation (VectorStore — degraded-safe) ──

    async def search_vector(self, embedding: list[float], top_k: int):
        if self.vector_store is None:
            return []
        return await self.vector_store.search(embedding, top_k)
