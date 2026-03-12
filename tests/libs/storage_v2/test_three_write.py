"""Tests for StorageManager three-write consistency and rollback."""

from unittest.mock import AsyncMock

import pytest

from libs.storage_v2.config import StorageConfig
from libs.storage_v2.manager import StorageManager
from libs.storage_v2.models import KnowledgeEmbedding


@pytest.fixture
async def manager(tmp_path) -> StorageManager:
    config = StorageConfig(
        lancedb_path=str(tmp_path / "lance"),
        graph_backend="kuzu",
        kuzu_path=str(tmp_path / "kuzu"),
    )
    mgr = StorageManager(config)
    await mgr.initialize()
    yield mgr
    await mgr.close()


def _make_embeddings(knowledge_items) -> list[KnowledgeEmbedding]:
    return [
        KnowledgeEmbedding(
            knowledge_id=c.knowledge_id,
            version=c.version,
            embedding=[0.1 * i for i in range(8)],
        )
        for c in knowledge_items
    ]


class TestIngestSuccess:
    async def test_ingest_writes_all_stores(
        self, manager, packages, modules, knowledge_items, chains
    ):
        pkg = packages[0]
        pkg_modules = [m for m in modules if m.package_id == pkg.package_id]
        pkg_knowledge_items = [c for c in knowledge_items if c.source_package_id == pkg.package_id]
        pkg_chains = [ch for ch in chains if ch.package_id == pkg.package_id]
        embeddings = _make_embeddings(pkg_knowledge_items)

        await manager.ingest_package(
            package=pkg,
            modules=pkg_modules,
            knowledge_items=pkg_knowledge_items,
            chains=pkg_chains,
            embeddings=embeddings,
        )

        # ContentStore has the package
        p = await manager.content_store.get_package(pkg.package_id)
        assert p is not None

        # ContentStore has knowledge_items
        c = await manager.content_store.get_knowledge(pkg_knowledge_items[0].knowledge_id)
        assert c is not None

        # GraphStore has topology
        sub = await manager.graph_store.get_subgraph(pkg_knowledge_items[0].knowledge_id)
        assert len(sub.knowledge_ids) > 0

        # VectorStore has embeddings
        results = await manager.vector_store.search([0.1 * i for i in range(8)], top_k=1)
        assert len(results) >= 1

    async def test_ingest_without_embeddings(
        self, manager, packages, modules, knowledge_items, chains
    ):
        pkg = packages[0]
        pkg_modules = [m for m in modules if m.package_id == pkg.package_id]
        pkg_knowledge_items = [c for c in knowledge_items if c.source_package_id == pkg.package_id]
        pkg_chains = [ch for ch in chains if ch.package_id == pkg.package_id]

        await manager.ingest_package(
            package=pkg,
            modules=pkg_modules,
            knowledge_items=pkg_knowledge_items,
            chains=pkg_chains,
        )

        p = await manager.content_store.get_package(pkg.package_id)
        assert p is not None

    async def test_ingest_no_graph(self, tmp_path, packages, modules, knowledge_items, chains):
        config = StorageConfig(
            lancedb_path=str(tmp_path / "lance"),
            graph_backend="none",
        )
        mgr = StorageManager(config)
        await mgr.initialize()

        pkg = packages[0]
        pkg_modules = [m for m in modules if m.package_id == pkg.package_id]
        pkg_knowledge_items = [c for c in knowledge_items if c.source_package_id == pkg.package_id]
        pkg_chains = [ch for ch in chains if ch.package_id == pkg.package_id]

        await mgr.ingest_package(
            package=pkg,
            modules=pkg_modules,
            knowledge_items=pkg_knowledge_items,
            chains=pkg_chains,
        )

        p = await mgr.content_store.get_package(pkg.package_id)
        assert p is not None
        await mgr.close()


class TestIngestPartialFailure:
    async def test_graph_failure_leaves_package_invisible(
        self, manager, packages, modules, knowledge_items, chains
    ):
        """If GraphStore fails, package stays in 'preparing' — invisible to reads."""
        pkg = packages[0]
        pkg_modules = [m for m in modules if m.package_id == pkg.package_id]
        pkg_knowledge_items = [c for c in knowledge_items if c.source_package_id == pkg.package_id]
        pkg_chains = [ch for ch in chains if ch.package_id == pkg.package_id]

        manager.graph_store.write_topology = AsyncMock(
            side_effect=RuntimeError("graph write failed")
        )

        with pytest.raises(RuntimeError, match="graph write failed"):
            await manager.ingest_package(
                package=pkg,
                modules=pkg_modules,
                knowledge_items=pkg_knowledge_items,
                chains=pkg_chains,
            )

        # Package is invisible via manager reads (visibility gate)
        p = await manager.get_package(pkg.package_id)
        assert p is None

    async def test_vector_failure_leaves_package_invisible(
        self, manager, packages, modules, knowledge_items, chains
    ):
        pkg = packages[0]
        pkg_modules = [m for m in modules if m.package_id == pkg.package_id]
        pkg_knowledge_items = [c for c in knowledge_items if c.source_package_id == pkg.package_id]
        pkg_chains = [ch for ch in chains if ch.package_id == pkg.package_id]
        embeddings = _make_embeddings(pkg_knowledge_items)

        manager.vector_store.write_embeddings = AsyncMock(
            side_effect=RuntimeError("vector write failed")
        )

        with pytest.raises(RuntimeError, match="vector write failed"):
            await manager.ingest_package(
                package=pkg,
                modules=pkg_modules,
                knowledge_items=pkg_knowledge_items,
                chains=pkg_chains,
                embeddings=embeddings,
            )

        # Package invisible
        p = await manager.get_package(pkg.package_id)
        assert p is None

    async def test_retry_after_failure_succeeds(
        self, manager, packages, modules, knowledge_items, chains
    ):
        """Retrying ingest after a failure should succeed (idempotent writes)."""
        pkg = packages[0]
        pkg_modules = [m for m in modules if m.package_id == pkg.package_id]
        pkg_knowledge_items = [c for c in knowledge_items if c.source_package_id == pkg.package_id]
        pkg_chains = [ch for ch in chains if ch.package_id == pkg.package_id]

        # First attempt fails at graph
        manager.graph_store.write_topology = AsyncMock(
            side_effect=RuntimeError("transient failure")
        )
        with pytest.raises(RuntimeError):
            await manager.ingest_package(
                package=pkg,
                modules=pkg_modules,
                knowledge_items=pkg_knowledge_items,
                chains=pkg_chains,
            )

        # Restore real implementation and retry
        from libs.storage_v2.kuzu_graph_store import KuzuGraphStore

        manager.graph_store.write_topology = KuzuGraphStore.write_topology.__get__(
            manager.graph_store
        )

        await manager.ingest_package(
            package=pkg,
            modules=pkg_modules,
            knowledge_items=pkg_knowledge_items,
            chains=pkg_chains,
        )

        # Now visible
        p = await manager.get_package(pkg.package_id)
        assert p is not None
        assert p.status == "merged"


class TestVersionedRePublish:
    async def test_v1_survives_failed_v2_publish(
        self, manager, packages, modules, knowledge_items, chains
    ):
        """Publishing v1 successfully then failing v2 must leave v1 visible."""
        pkg_v1 = packages[0]
        pkg_modules = [m for m in modules if m.package_id == pkg_v1.package_id]
        pkg_knowledge = [c for c in knowledge_items if c.source_package_id == pkg_v1.package_id]
        pkg_chains = [ch for ch in chains if ch.package_id == pkg_v1.package_id]

        # Publish v1 successfully
        await manager.ingest_package(
            package=pkg_v1,
            modules=pkg_modules,
            knowledge_items=pkg_knowledge,
            chains=pkg_chains,
        )
        p = await manager.get_package(pkg_v1.package_id)
        assert p is not None
        assert p.version == pkg_v1.version

        # Try to publish v2 but fail at graph
        pkg_v2 = pkg_v1.model_copy(update={"version": "2.0.0"})
        manager.graph_store.write_topology = AsyncMock(
            side_effect=RuntimeError("graph write failed")
        )
        with pytest.raises(RuntimeError, match="graph write failed"):
            await manager.ingest_package(
                package=pkg_v2,
                modules=pkg_modules,
                knowledge_items=pkg_knowledge,
                chains=pkg_chains,
            )

        # v1 must still be visible — package, knowledge, modules, chains
        p = await manager.get_package(pkg_v1.package_id)
        assert p is not None, "v1 package should still be visible after v2 failure"
        assert p.version == pkg_v1.version

        k = await manager.get_knowledge(pkg_knowledge[0].knowledge_id)
        assert k is not None, "v1 knowledge should still be visible after v2 failure"
        assert k.source_package_version == pkg_v1.version

        m = await manager.content_store.get_module(pkg_modules[0].module_id)
        assert m is not None, "v1 module should still be visible after v2 failure"
        assert m.package_version == pkg_v1.version

        chain_module_id = pkg_chains[0].module_id
        visible_chains = await manager.content_store.get_chains_by_module(chain_module_id)
        assert len(visible_chains) > 0, "v1 chains should still be visible after v2 failure"
        assert all(c.package_version == pkg_v1.version for c in visible_chains)


class TestPartialWriteVisibility:
    """Reproduce the exact scenarios from PR review:
    partial writes to GraphStore/VectorStore must be invisible through manager reads.
    """

    async def test_partial_graph_write_invisible_via_manager(
        self, manager, packages, modules, knowledge_items, chains
    ):
        """If write_topology partially writes some nodes then fails,
        graph_store.get_subgraph() may return data, but manager.get_subgraph()
        must NOT — the package is still 'preparing'.
        """
        pkg = packages[0]
        pkg_modules = [m for m in modules if m.package_id == pkg.package_id]
        pkg_knowledge = [c for c in knowledge_items if c.source_package_id == pkg.package_id]
        pkg_chains = [ch for ch in chains if ch.package_id == pkg.package_id]

        # Simulate partial graph write: write some data, then fail
        real_write = manager.graph_store.write_topology

        async def partial_then_fail(knowledge_items, chains):
            # Write just the first knowledge item to graph
            await real_write(knowledge_items[:1], [])
            raise RuntimeError("graph partially failed")

        manager.graph_store.write_topology = partial_then_fail

        with pytest.raises(RuntimeError, match="graph partially failed"):
            await manager.ingest_package(
                package=pkg,
                modules=pkg_modules,
                knowledge_items=pkg_knowledge,
                chains=pkg_chains,
            )

        # Direct graph store access shows data (the leak)
        raw_sub = await manager.graph_store.get_subgraph(pkg_knowledge[0].knowledge_id)
        assert len(raw_sub.knowledge_ids) > 0, "graph store has partial data"

        # Manager reads must filter it out (visibility gate)
        filtered_sub = await manager.get_subgraph(pkg_knowledge[0].knowledge_id)
        assert len(filtered_sub.knowledge_ids) == 0, "manager must hide preparing data"

    async def test_partial_vector_write_invisible_via_manager(
        self, manager, packages, modules, knowledge_items, chains
    ):
        """If write_embeddings partially writes then fails,
        vector_store.search() may return data, but manager.search_vector()
        must NOT — the package is still 'preparing'.
        """
        pkg = packages[0]
        pkg_modules = [m for m in modules if m.package_id == pkg.package_id]
        pkg_knowledge = [c for c in knowledge_items if c.source_package_id == pkg.package_id]
        pkg_chains = [ch for ch in chains if ch.package_id == pkg.package_id]
        embeddings = _make_embeddings(pkg_knowledge)

        # Simulate partial vector write: write first embedding, then fail
        real_write = manager.vector_store.write_embeddings

        async def partial_then_fail(items):
            await real_write(items[:1])
            raise RuntimeError("vector partially failed")

        manager.vector_store.write_embeddings = partial_then_fail

        with pytest.raises(RuntimeError, match="vector partially failed"):
            await manager.ingest_package(
                package=pkg,
                modules=pkg_modules,
                knowledge_items=pkg_knowledge,
                chains=pkg_chains,
                embeddings=embeddings,
            )

        # Direct vector store access shows data (the leak)
        raw_results = await manager.vector_store.search([0.1 * i for i in range(8)], top_k=5)
        assert len(raw_results) >= 1, "vector store has partial data"

        # Manager reads must filter it out (visibility gate)
        filtered_results = await manager.search_vector([0.1 * i for i in range(8)], top_k=5)
        assert len(filtered_results) == 0, "manager must hide preparing data"

    async def test_topology_search_invisible_for_preparing(
        self, manager, packages, modules, knowledge_items, chains
    ):
        """search_topology must also filter out preparing package data."""
        pkg = packages[0]
        pkg_modules = [m for m in modules if m.package_id == pkg.package_id]
        pkg_knowledge = [c for c in knowledge_items if c.source_package_id == pkg.package_id]
        pkg_chains = [ch for ch in chains if ch.package_id == pkg.package_id]

        # Write graph data but don't commit (simulate partial failure)
        manager.graph_store.write_topology = AsyncMock(side_effect=RuntimeError("graph failed"))
        with pytest.raises(RuntimeError):
            await manager.ingest_package(
                package=pkg,
                modules=pkg_modules,
                knowledge_items=pkg_knowledge,
                chains=pkg_chains,
            )

        # search_topology through manager should return nothing
        results = await manager.search_topology([pkg_knowledge[0].knowledge_id], hops=1)
        assert len(results) == 0


class TestPassthroughWrites:
    async def test_add_probabilities(
        self, manager, packages, modules, knowledge_items, chains, probabilities
    ):
        pkg = packages[0]
        pkg_modules = [m for m in modules if m.package_id == pkg.package_id]
        pkg_knowledge_items = [c for c in knowledge_items if c.source_package_id == pkg.package_id]
        pkg_chains = [ch for ch in chains if ch.package_id == pkg.package_id]

        await manager.ingest_package(
            package=pkg, modules=pkg_modules, knowledge_items=pkg_knowledge_items, chains=pkg_chains
        )

        pkg_probs = [p for p in probabilities if p.chain_id in {ch.chain_id for ch in pkg_chains}]
        if pkg_probs:
            await manager.add_probabilities(pkg_probs)
            history = await manager.content_store.get_probability_history(pkg_probs[0].chain_id)
            assert len(history) > 0

    async def test_write_beliefs(
        self, manager, packages, modules, knowledge_items, chains, beliefs
    ):
        pkg = packages[0]
        pkg_modules = [m for m in modules if m.package_id == pkg.package_id]
        pkg_knowledge_items = [c for c in knowledge_items if c.source_package_id == pkg.package_id]
        pkg_chains = [ch for ch in chains if ch.package_id == pkg.package_id]

        await manager.ingest_package(
            package=pkg, modules=pkg_modules, knowledge_items=pkg_knowledge_items, chains=pkg_chains
        )

        pkg_beliefs = [
            b for b in beliefs if b.knowledge_id in {c.knowledge_id for c in pkg_knowledge_items}
        ]
        if pkg_beliefs:
            await manager.write_beliefs(pkg_beliefs)
            history = await manager.content_store.get_belief_history(pkg_beliefs[0].knowledge_id)
            assert len(history) > 0

    async def test_write_resources(
        self, manager, packages, modules, knowledge_items, chains, resources, attachments
    ):
        pkg = packages[0]
        pkg_modules = [m for m in modules if m.package_id == pkg.package_id]
        pkg_knowledge_items = [c for c in knowledge_items if c.source_package_id == pkg.package_id]
        pkg_chains = [ch for ch in chains if ch.package_id == pkg.package_id]

        await manager.ingest_package(
            package=pkg, modules=pkg_modules, knowledge_items=pkg_knowledge_items, chains=pkg_chains
        )

        pkg_resources = [r for r in resources if r.source_package_id == pkg.package_id]
        pkg_attachments = [
            a for a in attachments if a.resource_id in {r.resource_id for r in pkg_resources}
        ]
        if pkg_resources:
            await manager.write_resources(pkg_resources, pkg_attachments)
            for a in pkg_attachments:
                found = await manager.content_store.get_resources_for(a.target_type, a.target_id)
                assert isinstance(found, list)
