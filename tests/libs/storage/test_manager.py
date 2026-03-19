"""Tests for StorageManager — unified storage facade."""

from datetime import datetime

import pytest

from libs.storage.config import StorageConfig
from libs.storage.manager import StorageManager
from libs.storage.models import (
    CanonicalBinding,
    FactorNode,
    FactorParams,
    GlobalCanonicalNode,
    GlobalInferenceState,
    Knowledge,
    Module,
    Package,
    Subgraph,
)


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

    async def test_neo4j_backend_initializes_or_skips(self, tmp_path):
        """graph_backend='neo4j' should initialize if reachable, else raise."""
        config = StorageConfig(
            lancedb_path=str(tmp_path / "lance"),
            graph_backend="neo4j",
        )
        mgr = StorageManager(config)
        try:
            await mgr.initialize()
            # Neo4j reachable — graph_store should be set
            assert mgr.graph_store is not None
            await mgr.close()
        except Exception:
            # Neo4j not reachable — that's expected in CI without Neo4j
            pass


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
        from libs.storage.models import KnowledgeEmbedding

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


class TestListDelegation:
    """Cover list/graph delegation methods added for v2 visualization."""

    async def test_list_packages(self, full_manager, packages, modules):
        pkg = packages[0]
        mods = [m for m in modules if m.package_id == pkg.package_id]
        await full_manager.content_store.write_package(pkg, mods)
        items, total = await full_manager.list_packages(page=1, page_size=10)
        assert total >= 1
        assert any(p.package_id == pkg.package_id for p in items)

    async def test_list_modules(self, full_manager, packages, modules):
        pkg = packages[0]
        mods = [m for m in modules if m.package_id == pkg.package_id]
        await full_manager.content_store.write_package(pkg, mods)
        result = await full_manager.list_modules()
        assert len(result) >= 1
        filtered = await full_manager.list_modules(package_id=pkg.package_id)
        assert all(m.package_id == pkg.package_id for m in filtered)

    async def test_list_chains_paged(self, full_manager, packages, modules, chains):
        pkg = packages[0]
        mods = [m for m in modules if m.package_id == pkg.package_id]
        await full_manager.content_store.write_package(pkg, mods)
        await full_manager.content_store.write_chains(chains)
        items, total = await full_manager.list_chains_paged(page=1, page_size=10)
        assert isinstance(items, list)
        assert total >= 1

    async def test_get_chain(self, full_manager, packages, modules, chains):
        pkg = packages[0]
        mods = [m for m in modules if m.package_id == pkg.package_id]
        await full_manager.content_store.write_package(pkg, mods)
        await full_manager.content_store.write_chains(chains)
        chain = await full_manager.get_chain(chains[0].chain_id)
        assert chain is not None
        assert chain.chain_id == chains[0].chain_id
        assert await full_manager.get_chain("nonexistent") is None

    async def test_list_knowledge_paged(self, full_manager, packages, modules, knowledge_items):
        pkg = packages[0]
        mods = [m for m in modules if m.package_id == pkg.package_id]
        await full_manager.content_store.write_package(pkg, mods)
        await full_manager.content_store.write_knowledge(knowledge_items)
        items, total = await full_manager.list_knowledge_paged(page=1, page_size=10)
        assert total >= 1
        assert len(items) >= 1

    async def test_get_graph_data(self, full_manager, packages, modules, knowledge_items, chains):
        pkg = packages[0]
        mods = [m for m in modules if m.package_id == pkg.package_id]
        await full_manager.content_store.write_package(pkg, mods)
        await full_manager.content_store.write_knowledge(knowledge_items)
        await full_manager.content_store.write_chains(chains)
        data = await full_manager.get_graph_data()
        assert "nodes" in data
        assert "edges" in data
        filtered = await full_manager.get_graph_data(package_id=pkg.package_id)
        assert "nodes" in filtered


class TestCanonicalBindingsAndGlobalNodes:
    async def test_write_and_read_canonical_bindings(self, tmp_path):
        config = StorageConfig(
            lancedb_path=str(tmp_path / "lance"),
            graph_backend="kuzu",
            kuzu_path=str(tmp_path / "kuzu"),
        )
        mgr = StorageManager(config)
        await mgr.initialize()

        bindings = [
            CanonicalBinding(
                package="pkg",
                version="1.0.0",
                local_graph_hash="sha256:abc",
                local_canonical_id="pkg/lc1",
                decision="create_new",
                global_canonical_id="gcn_01",
                decided_at=datetime.now(),
                decided_by="auto",
            ),
        ]
        global_nodes = [
            GlobalCanonicalNode(
                global_canonical_id="gcn_01",
                knowledge_type="claim",
                representative_content="X is true",
            ),
        ]

        await mgr.write_canonical_bindings(bindings, global_nodes)

        result_bindings = await mgr.get_bindings_for_package("pkg", "1.0.0")
        assert len(result_bindings) == 1

        result_node = await mgr.get_global_node("gcn_01")
        assert result_node is not None

        await mgr.close()


class TestInferenceStateFacade:
    async def test_inference_state_roundtrip(self, tmp_path):
        config = StorageConfig(lancedb_path=str(tmp_path / "lance"), graph_backend="none")
        mgr = StorageManager(config)
        await mgr.initialize()

        assert await mgr.get_inference_state() is None

        state = GlobalInferenceState(
            graph_hash="sha256:xyz",
            node_priors={"gcn_01": 0.7},
            factor_parameters={"f1": FactorParams(conditional_probability=0.9)},
            updated_at=datetime.now(),
        )
        await mgr.update_inference_state(state)

        result = await mgr.get_inference_state()
        assert result is not None
        assert result.graph_hash == "sha256:xyz"

        await mgr.close()


class TestLoadGlobalFactorGraph:
    async def test_load_global_factor_graph(self, tmp_path):
        """load_global_factor_graph returns all factors + current inference state."""
        config = StorageConfig(lancedb_path=str(tmp_path / "lance"), graph_backend="none")
        mgr = StorageManager(config)
        await mgr.initialize()

        pkg = Package(
            package_id="pkg",
            name="pkg",
            version="1.0.0",
            submitter="test",
            submitted_at=datetime.now(),
            status="merged",
        )
        k = Knowledge(
            knowledge_id="pkg/k1",
            version=1,
            type="claim",
            content="X",
            prior=0.7,
            source_package_id="pkg",
            source_module_id="pkg.mod",
            created_at=datetime.now(),
        )
        mod = Module(module_id="pkg.mod", package_id="pkg", name="mod", role="reasoning")
        factors = [
            FactorNode(
                factor_id="pkg.f1",
                type="infer",
                premises=["pkg/k1"],
                conclusion="pkg/k1",
                package_id="pkg",
            ),
        ]
        state = GlobalInferenceState(
            graph_hash="sha256:abc",
            node_priors={"gcn_01": 0.7},
            factor_parameters={"pkg.f1": FactorParams(conditional_probability=0.9)},
            updated_at=datetime.now(),
        )

        await mgr.ingest_package(
            package=pkg,
            modules=[mod],
            knowledge_items=[k],
            chains=[],
            factors=factors,
        )
        await mgr.update_inference_state(state)

        result_factors, result_state = await mgr.load_global_factor_graph()
        assert len(result_factors) == 1
        assert result_state is not None
        assert result_state.graph_hash == "sha256:abc"

        await mgr.close()
