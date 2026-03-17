"""StorageManager — unified facade for ContentStore, GraphStore, and VectorStore."""

from __future__ import annotations

import logging

from libs.storage.config import StorageConfig
from libs.storage.content_store import ContentStore
from libs.storage.graph_store import GraphStore
from libs.storage.models import (
    BeliefSnapshot,
    CanonicalBinding,
    Chain,
    FactorNode,
    GlobalCanonicalNode,
    GlobalInferenceState,
    Knowledge,
    KnowledgeEmbedding,
    Module,
    Package,
    PackageSubmissionArtifact,
    ProbabilityRecord,
    Resource,
    ResourceAttachment,
    ScoredKnowledge,
    Subgraph,
)
from libs.storage.vector_store import VectorStore

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
        from libs.storage.lance_content_store import LanceContentStore
        from libs.storage.lance_vector_store import LanceVectorStore

        # ContentStore — always required
        cs = LanceContentStore(self._config.lancedb_path)
        await cs.initialize()
        self.content_store = cs

        # GraphStore — optional
        if self._config.graph_backend == "kuzu":
            from libs.storage.kuzu_graph_store import KuzuGraphStore

            kuzu_path = self._config.kuzu_path or (self._config.lancedb_path + "_kuzu")
            gs = KuzuGraphStore(kuzu_path)
            await gs.initialize_schema()
            self.graph_store = gs
        elif self._config.graph_backend == "neo4j":
            import neo4j

            from libs.storage.neo4j_graph_store import Neo4jGraphStore

            driver = neo4j.AsyncGraphDatabase.driver(
                self._config.neo4j_uri,
                auth=(self._config.neo4j_user, self._config.neo4j_password)
                if self._config.neo4j_password
                else None,
            )
            gs = Neo4jGraphStore(driver, self._config.neo4j_database)
            await gs.initialize_schema()
            self.graph_store = gs
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
        factors: list[FactorNode] | None = None,
        submission_artifact: PackageSubmissionArtifact | None = None,
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
        if factors:
            await self.content_store.write_factors(factors)
        if submission_artifact:
            await self.content_store.write_submission_artifact(submission_artifact)

        # Step 2: GraphStore (optional, idempotent)
        if self.graph_store is not None:
            await self.graph_store.write_topology(versioned_knowledge, versioned_chains)
            if factors:
                await self.graph_store.write_factor_topology(factors)

        # Step 3: VectorStore (optional, idempotent)
        if self.vector_store is not None and embeddings:
            await self.vector_store.write_embeddings(embeddings)

        # Step 4: Commit — flip to visible
        await self.content_store.commit_package(preparing_pkg.package_id, pkg_version)

    # ── Passthrough writes ──

    async def add_probabilities(self, records: list[ProbabilityRecord]) -> None:
        """Write probabilities to ContentStore."""
        await self.content_store.write_probabilities(records)

    async def write_beliefs(self, snapshots: list[BeliefSnapshot]) -> None:
        """Write belief snapshots to ContentStore."""
        await self.content_store.write_belief_snapshots(snapshots)

    async def write_resources(
        self, resources: list[Resource], attachments: list[ResourceAttachment]
    ) -> None:
        """Write resources to ContentStore + link in GraphStore."""
        await self.content_store.write_resources(resources, attachments)
        if self.graph_store is not None:
            await self.graph_store.write_resource_links(attachments)

    # ── Factor & Graph IR writes ──

    async def list_factors(self) -> list[FactorNode]:
        return await self.content_store.list_factors()

    async def get_factors_by_package(self, package_id: str) -> list[FactorNode]:
        return await self.content_store.get_factors_by_package(package_id)

    async def get_submission_artifact(
        self, package: str, commit_hash: str
    ) -> PackageSubmissionArtifact | None:
        return await self.content_store.get_submission_artifact(package, commit_hash)

    # ── Canonical Bindings & Global Nodes ──

    async def write_canonical_bindings(
        self,
        bindings: list[CanonicalBinding],
        global_nodes: list[GlobalCanonicalNode],
    ) -> None:
        """Write canonical bindings and global nodes to ContentStore + GraphStore."""
        await self.content_store.write_canonical_bindings(bindings)
        await self.content_store.upsert_global_nodes(global_nodes)
        if self.graph_store is not None:
            await self.graph_store.write_global_topology(bindings, global_nodes)

    async def get_bindings_for_package(self, package: str, version: str) -> list[CanonicalBinding]:
        return await self.content_store.get_canonical_bindings(package, version)

    async def get_global_node(self, global_id: str) -> GlobalCanonicalNode | None:
        return await self.content_store.get_global_node(global_id)

    async def list_global_nodes(self) -> list[GlobalCanonicalNode]:
        return await self.content_store.list_global_nodes()

    async def upsert_global_nodes(self, nodes: list[GlobalCanonicalNode]) -> None:
        """Upsert global nodes to ContentStore + GraphStore."""
        await self.content_store.upsert_global_nodes(nodes)
        if self.graph_store is not None:
            await self.graph_store.write_global_topology([], nodes)

    async def write_factors(self, factors: list[FactorNode]) -> None:
        """Write factors to ContentStore + GraphStore."""
        await self.content_store.write_factors(factors)
        if self.graph_store is not None:
            await self.graph_store.write_factor_topology(factors)

    # ── Global Inference State ──

    async def get_inference_state(self) -> GlobalInferenceState | None:
        return await self.content_store.get_inference_state()

    async def update_inference_state(self, state: GlobalInferenceState) -> None:
        await self.content_store.update_inference_state(state)

    # ── BP Execution ──

    async def load_global_factor_graph(
        self,
    ) -> tuple[list[FactorNode], GlobalInferenceState | None]:
        """Load all factors and the current global inference state for BP execution."""
        factors = await self.content_store.list_factors()
        state = await self.content_store.get_inference_state()
        return factors, state

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

    async def list_packages(self, page: int = 1, page_size: int = 20) -> tuple[list[Package], int]:
        return await self.content_store.list_packages(page=page, page_size=page_size)

    async def list_modules(self, package_id: str | None = None) -> list[Module]:
        return await self.content_store.list_modules(package_id=package_id)

    async def list_chains_paged(
        self, page: int = 1, page_size: int = 20, module_id: str | None = None
    ) -> tuple[list[Chain], int]:
        return await self.content_store.list_chains_paged(
            page=page, page_size=page_size, module_id=module_id
        )

    async def get_chain(self, chain_id: str) -> Chain | None:
        return await self.content_store.get_chain(chain_id)

    async def get_graph_data(self, package_id: str | None = None) -> dict:
        return await self.content_store.get_graph_data(package_id=package_id)

    async def list_knowledge_paged(
        self, page: int = 1, page_size: int = 20, type_filter: str | None = None
    ) -> tuple[list[Knowledge], int]:
        return await self.content_store.list_knowledge_paged(
            page=page, page_size=page_size, type_filter=type_filter
        )

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
