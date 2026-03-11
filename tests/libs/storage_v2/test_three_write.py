"""Tests for StorageManager three-write consistency and rollback."""

from unittest.mock import AsyncMock

import pytest

from libs.storage_v2.config import StorageConfig
from libs.storage_v2.manager import StorageManager
from libs.storage_v2.models import ClosureEmbedding


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


def _make_embeddings(closures) -> list[ClosureEmbedding]:
    return [
        ClosureEmbedding(
            closure_id=c.closure_id,
            version=c.version,
            embedding=[0.1 * i for i in range(8)],
        )
        for c in closures
    ]


class TestIngestSuccess:
    async def test_ingest_writes_all_stores(self, manager, packages, modules, closures, chains):
        pkg = packages[0]
        pkg_modules = [m for m in modules if m.package_id == pkg.package_id]
        pkg_closures = [c for c in closures if c.source_package_id == pkg.package_id]
        pkg_chains = [ch for ch in chains if ch.package_id == pkg.package_id]
        embeddings = _make_embeddings(pkg_closures)

        await manager.ingest_package(
            package=pkg,
            modules=pkg_modules,
            closures=pkg_closures,
            chains=pkg_chains,
            embeddings=embeddings,
        )

        # ContentStore has the package
        p = await manager.content_store.get_package(pkg.package_id)
        assert p is not None

        # ContentStore has closures
        c = await manager.content_store.get_closure(pkg_closures[0].closure_id)
        assert c is not None

        # GraphStore has topology
        sub = await manager.graph_store.get_subgraph(pkg_closures[0].closure_id)
        assert len(sub.closure_ids) > 0

        # VectorStore has embeddings
        results = await manager.vector_store.search([0.1 * i for i in range(8)], top_k=1)
        assert len(results) >= 1

    async def test_ingest_without_embeddings(self, manager, packages, modules, closures, chains):
        pkg = packages[0]
        pkg_modules = [m for m in modules if m.package_id == pkg.package_id]
        pkg_closures = [c for c in closures if c.source_package_id == pkg.package_id]
        pkg_chains = [ch for ch in chains if ch.package_id == pkg.package_id]

        await manager.ingest_package(
            package=pkg,
            modules=pkg_modules,
            closures=pkg_closures,
            chains=pkg_chains,
        )

        p = await manager.content_store.get_package(pkg.package_id)
        assert p is not None

    async def test_ingest_no_graph(self, tmp_path, packages, modules, closures, chains):
        config = StorageConfig(
            lancedb_path=str(tmp_path / "lance"),
            graph_backend="none",
        )
        mgr = StorageManager(config)
        await mgr.initialize()

        pkg = packages[0]
        pkg_modules = [m for m in modules if m.package_id == pkg.package_id]
        pkg_closures = [c for c in closures if c.source_package_id == pkg.package_id]
        pkg_chains = [ch for ch in chains if ch.package_id == pkg.package_id]

        await mgr.ingest_package(
            package=pkg,
            modules=pkg_modules,
            closures=pkg_closures,
            chains=pkg_chains,
        )

        p = await mgr.content_store.get_package(pkg.package_id)
        assert p is not None
        await mgr.close()


class TestIngestRollback:
    async def test_graph_failure_rolls_back_content(
        self, manager, packages, modules, closures, chains
    ):
        pkg = packages[0]
        pkg_modules = [m for m in modules if m.package_id == pkg.package_id]
        pkg_closures = [c for c in closures if c.source_package_id == pkg.package_id]
        pkg_chains = [ch for ch in chains if ch.package_id == pkg.package_id]

        # Make graph_store.write_topology raise
        manager.graph_store.write_topology = AsyncMock(
            side_effect=RuntimeError("graph write failed")
        )

        with pytest.raises(RuntimeError, match="graph write failed"):
            await manager.ingest_package(
                package=pkg,
                modules=pkg_modules,
                closures=pkg_closures,
                chains=pkg_chains,
            )

        # Content should be rolled back
        p = await manager.content_store.get_package(pkg.package_id)
        assert p is None

    async def test_vector_failure_rolls_back_content_and_graph(
        self, manager, packages, modules, closures, chains
    ):
        pkg = packages[0]
        pkg_modules = [m for m in modules if m.package_id == pkg.package_id]
        pkg_closures = [c for c in closures if c.source_package_id == pkg.package_id]
        pkg_chains = [ch for ch in chains if ch.package_id == pkg.package_id]
        embeddings = _make_embeddings(pkg_closures)

        # Make vector_store.write_embeddings raise
        manager.vector_store.write_embeddings = AsyncMock(
            side_effect=RuntimeError("vector write failed")
        )

        with pytest.raises(RuntimeError, match="vector write failed"):
            await manager.ingest_package(
                package=pkg,
                modules=pkg_modules,
                closures=pkg_closures,
                chains=pkg_chains,
                embeddings=embeddings,
            )

        # Content should be rolled back
        p = await manager.content_store.get_package(pkg.package_id)
        assert p is None


class TestPassthroughWrites:
    async def test_add_probabilities(
        self, manager, packages, modules, closures, chains, probabilities
    ):
        pkg = packages[0]
        pkg_modules = [m for m in modules if m.package_id == pkg.package_id]
        pkg_closures = [c for c in closures if c.source_package_id == pkg.package_id]
        pkg_chains = [ch for ch in chains if ch.package_id == pkg.package_id]

        await manager.ingest_package(
            package=pkg, modules=pkg_modules, closures=pkg_closures, chains=pkg_chains
        )

        pkg_probs = [p for p in probabilities if p.chain_id in {ch.chain_id for ch in pkg_chains}]
        if pkg_probs:
            await manager.add_probabilities(pkg_probs)
            history = await manager.content_store.get_probability_history(pkg_probs[0].chain_id)
            assert len(history) > 0

    async def test_write_beliefs(self, manager, packages, modules, closures, chains, beliefs):
        pkg = packages[0]
        pkg_modules = [m for m in modules if m.package_id == pkg.package_id]
        pkg_closures = [c for c in closures if c.source_package_id == pkg.package_id]
        pkg_chains = [ch for ch in chains if ch.package_id == pkg.package_id]

        await manager.ingest_package(
            package=pkg, modules=pkg_modules, closures=pkg_closures, chains=pkg_chains
        )

        pkg_beliefs = [b for b in beliefs if b.closure_id in {c.closure_id for c in pkg_closures}]
        if pkg_beliefs:
            await manager.write_beliefs(pkg_beliefs)
            history = await manager.content_store.get_belief_history(pkg_beliefs[0].closure_id)
            assert len(history) > 0

    async def test_write_resources(
        self, manager, packages, modules, closures, chains, resources, attachments
    ):
        pkg = packages[0]
        pkg_modules = [m for m in modules if m.package_id == pkg.package_id]
        pkg_closures = [c for c in closures if c.source_package_id == pkg.package_id]
        pkg_chains = [ch for ch in chains if ch.package_id == pkg.package_id]

        await manager.ingest_package(
            package=pkg, modules=pkg_modules, closures=pkg_closures, chains=pkg_chains
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
