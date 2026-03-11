"""Tests for StorageManager — unified storage facade."""

import pytest

from libs.storage_v2.config import StorageConfig
from libs.storage_v2.manager import StorageManager
from libs.storage_v2.models import Subgraph


@pytest.fixture
async def full_manager(tmp_path) -> StorageManager:
    """Manager with all three stores."""
    config = StorageConfig(
        lancedb_path=str(tmp_path / "lance"),
        graph_backend="kuzu",
        kuzu_path=str(tmp_path / "kuzu"),
    )
    mgr = StorageManager(config)
    await mgr.initialize()
    yield mgr
    await mgr.close()


@pytest.fixture
async def no_graph_manager(tmp_path) -> StorageManager:
    """Manager with graph_backend=none."""
    config = StorageConfig(
        lancedb_path=str(tmp_path / "lance"),
        graph_backend="none",
    )
    mgr = StorageManager(config)
    await mgr.initialize()
    yield mgr
    await mgr.close()


class TestInitialization:
    async def test_full_init(self, full_manager):
        assert full_manager.content_store is not None
        assert full_manager.graph_store is not None
        assert full_manager.vector_store is not None

    async def test_no_graph_init(self, no_graph_manager):
        assert no_graph_manager.content_store is not None
        assert no_graph_manager.graph_store is None
        assert no_graph_manager.vector_store is not None

    async def test_close_idempotent(self, full_manager):
        await full_manager.close()
        await full_manager.close()  # should not raise


class TestReadDelegation:
    async def test_get_knowledge_delegates(
        self, full_manager, packages, modules, knowledge_items, chains
    ):
        pkg, mods = packages[0], [m for m in modules if m.package_id == packages[0].package_id]
        await full_manager.content_store.write_package(pkg, mods)
        await full_manager.content_store.write_knowledge(knowledge_items)
        c = await full_manager.get_knowledge(knowledge_items[0].knowledge_id)
        assert c is not None
        assert c.knowledge_id == knowledge_items[0].knowledge_id

    async def test_get_package_delegates(self, full_manager, packages, modules):
        pkg, mods = packages[0], [m for m in modules if m.package_id == packages[0].package_id]
        await full_manager.content_store.write_package(pkg, mods)
        p = await full_manager.get_package(pkg.package_id)
        assert p is not None
        assert p.package_id == pkg.package_id

    async def test_search_bm25_delegates(self, full_manager, packages, modules, knowledge_items):
        pkg, mods = packages[0], [m for m in modules if m.package_id == packages[0].package_id]
        await full_manager.content_store.write_package(pkg, mods)
        await full_manager.content_store.write_knowledge(knowledge_items)
        results = await full_manager.search_bm25("gravity", top_k=5)
        assert isinstance(results, list)


class TestDegradedMode:
    async def test_graph_none_returns_empty_subgraph(self, no_graph_manager):
        result = await no_graph_manager.get_neighbors("nonexistent")
        assert result == Subgraph()

    async def test_graph_none_search_topology_returns_empty(self, no_graph_manager):
        result = await no_graph_manager.search_topology(["nonexistent"])
        assert result == []

    async def test_graph_none_get_subgraph_returns_empty(self, no_graph_manager):
        result = await no_graph_manager.get_subgraph("nonexistent")
        assert result == Subgraph()

    async def test_vector_none_search_returns_empty(self, tmp_path):
        config = StorageConfig(
            lancedb_path=str(tmp_path / "lance"),
            graph_backend="none",
        )
        mgr = StorageManager(config)
        mgr.content_store = None  # skip init for this test
        mgr.vector_store = None
        result = await mgr.search_vector([0.1] * 8, top_k=5)
        assert result == []

    async def test_neo4j_backend_logs_warning(self, tmp_path):
        """graph_backend='neo4j' should skip gracefully (not implemented)."""
        config = StorageConfig(
            lancedb_path=str(tmp_path / "lance"),
            graph_backend="neo4j",
        )
        mgr = StorageManager(config)
        await mgr.initialize()
        assert mgr.graph_store is None
        await mgr.close()


class TestReadDelegationFull:
    """Cover all remaining read delegation methods on StorageManager."""

    @pytest.fixture
    async def seeded_manager(
        self,
        tmp_path,
        packages,
        modules,
        knowledge_items,
        chains,
        probabilities,
        beliefs,
        resources,
        attachments,
    ):
        config = StorageConfig(
            lancedb_path=str(tmp_path / "lance"),
            graph_backend="kuzu",
            kuzu_path=str(tmp_path / "kuzu"),
        )
        mgr = StorageManager(config)
        await mgr.initialize()
        pkg = packages[0]
        pkg_modules = [m for m in modules if m.package_id == pkg.package_id]
        pkg_knowledge_items = [c for c in knowledge_items if c.source_package_id == pkg.package_id]
        pkg_chains = [ch for ch in chains if ch.package_id == pkg.package_id]
        from libs.storage_v2.models import KnowledgeEmbedding

        embeddings = [
            KnowledgeEmbedding(
                knowledge_id=c.knowledge_id,
                version=c.version,
                embedding=[0.1 * i for i in range(8)],
            )
            for c in pkg_knowledge_items
        ]
        await mgr.ingest_package(
            package=pkg,
            modules=pkg_modules,
            knowledge_items=pkg_knowledge_items,
            chains=pkg_chains,
            embeddings=embeddings,
        )
        pkg_probs = [p for p in probabilities if p.chain_id in {ch.chain_id for ch in pkg_chains}]
        if pkg_probs:
            await mgr.add_probabilities(pkg_probs)
        pkg_beliefs = [
            b for b in beliefs if b.knowledge_id in {c.knowledge_id for c in pkg_knowledge_items}
        ]
        if pkg_beliefs:
            await mgr.write_beliefs(pkg_beliefs)
        pkg_resources = [r for r in resources if r.source_package_id == pkg.package_id]
        pkg_attachments = [
            a for a in attachments if a.resource_id in {r.resource_id for r in pkg_resources}
        ]
        if pkg_resources:
            await mgr.write_resources(pkg_resources, pkg_attachments)
        yield (
            mgr,
            pkg,
            pkg_modules,
            pkg_knowledge_items,
            pkg_chains,
            pkg_probs,
            pkg_beliefs,
            pkg_resources,
            pkg_attachments,
        )
        await mgr.close()

    async def test_get_knowledge_versions(self, seeded_manager):
        mgr, _, _, knowledge_items, *_ = seeded_manager
        versions = await mgr.get_knowledge_versions(knowledge_items[0].knowledge_id)
        assert len(versions) >= 1

    async def test_get_module(self, seeded_manager):
        mgr, _, modules, *_ = seeded_manager
        mod = await mgr.get_module(modules[0].module_id)
        assert mod is not None
        assert mod.module_id == modules[0].module_id

    async def test_get_chains_by_module(self, seeded_manager):
        mgr, _, modules, _, chains, *_ = seeded_manager
        result = await mgr.get_chains_by_module(modules[0].module_id)
        assert isinstance(result, list)

    async def test_get_probability_history(self, seeded_manager):
        mgr, _, _, _, chains, probs, *_ = seeded_manager
        if probs:
            result = await mgr.get_probability_history(probs[0].chain_id)
            assert len(result) > 0

    async def test_get_belief_history(self, seeded_manager):
        mgr, _, _, knowledge_items, _, _, beliefs, *_ = seeded_manager
        if beliefs:
            result = await mgr.get_belief_history(beliefs[0].knowledge_id)
            assert len(result) > 0

    async def test_get_resources_for(self, seeded_manager):
        mgr, _, _, _, _, _, _, resources, attachments = seeded_manager
        if attachments:
            result = await mgr.get_resources_for(
                attachments[0].target_type, attachments[0].target_id
            )
            assert isinstance(result, list)

    async def test_list_knowledge(self, seeded_manager):
        mgr, *_ = seeded_manager
        result = await mgr.list_knowledge()
        assert len(result) > 0

    async def test_list_chains(self, seeded_manager):
        mgr, *_ = seeded_manager
        result = await mgr.list_chains()
        assert len(result) > 0

    async def test_get_neighbors_with_graph(self, seeded_manager):
        mgr, _, _, knowledge_items, *_ = seeded_manager
        result = await mgr.get_neighbors(knowledge_items[0].knowledge_id)
        assert isinstance(result, Subgraph)

    async def test_get_subgraph_with_graph(self, seeded_manager):
        mgr, _, _, knowledge_items, *_ = seeded_manager
        result = await mgr.get_subgraph(knowledge_items[0].knowledge_id)
        assert isinstance(result, Subgraph)

    async def test_search_topology_with_graph(self, seeded_manager):
        mgr, _, _, knowledge_items, *_ = seeded_manager
        result = await mgr.search_topology([knowledge_items[0].knowledge_id])
        assert isinstance(result, list)

    async def test_search_vector_with_store(self, seeded_manager):
        mgr, *_ = seeded_manager
        result = await mgr.search_vector([0.1 * i for i in range(8)], top_k=5)
        assert isinstance(result, list)
