"""Tests for StorageManager — unified storage facade."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from gaia.models import (
    BindingDecision,
    CanonicalBinding,
    FactorParamRecord,
    ParameterizationSource,
    PriorRecord,
)
from gaia.libs.storage.config import StorageConfig
from gaia.libs.storage.manager import StorageManager
from tests.gaia.fixtures.graphs import make_galileo_falling_bodies


@pytest.fixture
async def manager(tmp_path):
    config = StorageConfig(lancedb_path=str(tmp_path / "test.lance"))
    mgr = StorageManager(config)
    await mgr.initialize()
    return mgr


def _galileo():
    graph, _params = make_galileo_falling_bodies()
    return graph


# ---------------------------------------------------------------------------
# Initialization
# ---------------------------------------------------------------------------


class TestInitialize:
    async def test_initialize_creates_content_store(self, manager):
        """content_store is not None after initialize."""
        assert manager.content_store is not None

    async def test_no_neo4j_graph_store_is_none(self, manager):
        """Without Neo4j configured, graph_store is None."""
        assert manager.graph_store is None


# ---------------------------------------------------------------------------
# Knowledge Nodes
# ---------------------------------------------------------------------------


class TestWriteAndReadKnowledgeNodes:
    async def test_write_and_read_by_prefix(self, manager):
        graph = _galileo()
        await manager.write_knowledge_nodes(graph.knowledge_nodes)

        nodes = await manager.get_knowledge_nodes(prefix="lcn_")
        assert len(nodes) == 10

    async def test_read_all_without_prefix(self, manager):
        graph = _galileo()
        await manager.write_knowledge_nodes(graph.knowledge_nodes)

        nodes = await manager.get_knowledge_nodes()
        assert len(nodes) == 10

    async def test_get_node_by_id(self, manager):
        graph = _galileo()
        await manager.write_knowledge_nodes(graph.knowledge_nodes)

        target = graph.knowledge_nodes[0]
        node = await manager.get_node(target.id)
        assert node is not None
        assert node.id == target.id
        assert node.content == target.content

    async def test_get_node_not_found(self, manager):
        result = await manager.get_node("lcn_nonexistent")
        assert result is None


# ---------------------------------------------------------------------------
# Factor Nodes
# ---------------------------------------------------------------------------


class TestWriteAndReadFactorNodes:
    async def test_write_and_read_by_scope(self, manager):
        graph = _galileo()
        await manager.write_factor_nodes(graph.factor_nodes)

        factors = await manager.get_factor_nodes(scope="local")
        assert len(factors) == 7

    async def test_read_all_without_scope(self, manager):
        graph = _galileo()
        await manager.write_factor_nodes(graph.factor_nodes)

        factors = await manager.get_factor_nodes()
        assert len(factors) == 7


# ---------------------------------------------------------------------------
# Bindings
# ---------------------------------------------------------------------------


class TestWriteAndReadBindings:
    async def test_write_and_read_bindings(self, manager):
        bindings = [
            CanonicalBinding(
                local_canonical_id="lcn_a",
                global_canonical_id="gcn_x",
                package_id="pkg1",
                version="1.0",
                decision=BindingDecision.CREATE_NEW,
                reason="new",
            ),
            CanonicalBinding(
                local_canonical_id="lcn_b",
                global_canonical_id="gcn_y",
                package_id="pkg2",
                version="1.0",
                decision=BindingDecision.MATCH_EXISTING,
                reason="match",
            ),
        ]
        await manager.write_bindings(bindings)

        loaded = await manager.get_bindings()
        assert len(loaded) == 2

    async def test_filter_by_package_id(self, manager):
        bindings = [
            CanonicalBinding(
                local_canonical_id="lcn_a",
                global_canonical_id="gcn_x",
                package_id="pkg1",
                version="1.0",
                decision=BindingDecision.CREATE_NEW,
                reason="new",
            ),
            CanonicalBinding(
                local_canonical_id="lcn_b",
                global_canonical_id="gcn_y",
                package_id="pkg2",
                version="1.0",
                decision=BindingDecision.CREATE_NEW,
                reason="new",
            ),
        ]
        await manager.write_bindings(bindings)

        pkg1 = await manager.get_bindings(package_id="pkg1")
        assert len(pkg1) == 1
        assert pkg1[0].local_canonical_id == "lcn_a"


# ---------------------------------------------------------------------------
# Prior Records
# ---------------------------------------------------------------------------


class TestWriteAndReadPriorRecords:
    async def test_write_and_read_priors(self, manager):
        now = datetime.now(timezone.utc)
        records = [
            PriorRecord(gcn_id="gcn_a", value=0.8, source_id="src_1", created_at=now),
            PriorRecord(gcn_id="gcn_b", value=0.6, source_id="src_1", created_at=now),
        ]
        await manager.write_prior_records(records)

        loaded = await manager.get_prior_records()
        assert len(loaded) == 2

    async def test_filter_by_gcn_id(self, manager):
        now = datetime.now(timezone.utc)
        records = [
            PriorRecord(gcn_id="gcn_a", value=0.8, source_id="src_1", created_at=now),
            PriorRecord(gcn_id="gcn_b", value=0.6, source_id="src_1", created_at=now),
        ]
        await manager.write_prior_records(records)

        loaded = await manager.get_prior_records(gcn_id="gcn_a")
        assert len(loaded) == 1
        assert loaded[0].gcn_id == "gcn_a"


# ---------------------------------------------------------------------------
# Factor Param Records
# ---------------------------------------------------------------------------


class TestWriteAndReadFactorParamRecords:
    async def test_write_and_read_factor_params(self, manager):
        now = datetime.now(timezone.utc)
        records = [
            FactorParamRecord(
                factor_id="gcf_x", probability=0.9, source_id="src_1", created_at=now
            ),
        ]
        await manager.write_factor_param_records(records)

        loaded = await manager.get_factor_param_records()
        assert len(loaded) == 1
        assert loaded[0].factor_id == "gcf_x"


# ---------------------------------------------------------------------------
# Write-only delegation (param source, belief state, embeddings)
# ---------------------------------------------------------------------------


class TestWriteOnlyDelegation:
    async def test_write_param_source(self, manager):
        now = datetime.now(timezone.utc)
        source = ParameterizationSource(
            source_id="src_1",
            model="gpt-4",
            created_at=now,
        )
        # Should not raise
        await manager.write_param_source(source)

    async def test_write_belief_state(self, manager):
        from gaia.models import BeliefState

        now = datetime.now(timezone.utc)
        state = BeliefState(
            bp_run_id="run_001",
            created_at=now,
            resolution_policy="latest",
            prior_cutoff=now,
            beliefs={"gcn_a": 0.85},
            converged=True,
            iterations=10,
            max_residual=0.001,
        )
        await manager.write_belief_state(state)

        loaded = await manager.get_belief_states(limit=5)
        assert len(loaded) == 1
        assert loaded[0].bp_run_id == "run_001"

    async def test_write_node_embedding(self, manager):
        await manager.write_node_embedding(
            gcn_id="gcn_a",
            vector=[1.0, 0.0, 0.0],
            content="Test content",
        )
        # Verify via search
        results = await manager.search_similar_nodes(
            query_vector=[1.0, 0.0, 0.0],
            top_k=5,
        )
        assert len(results) >= 1
        assert results[0][0] == "gcn_a"


# ---------------------------------------------------------------------------
# Clean All
# ---------------------------------------------------------------------------


class TestCleanAll:
    async def test_clean_removes_all_data(self, manager):
        graph = _galileo()
        await manager.write_knowledge_nodes(graph.knowledge_nodes)
        await manager.write_factor_nodes(graph.factor_nodes)

        # Verify data exists
        nodes = await manager.get_knowledge_nodes()
        assert len(nodes) > 0

        await manager.clean_all()

        nodes = await manager.get_knowledge_nodes()
        assert len(nodes) == 0
        factors = await manager.get_factor_nodes()
        assert len(factors) == 0


# ---------------------------------------------------------------------------
# Graph Store Optional
# ---------------------------------------------------------------------------


class TestGraphStoreOptional:
    async def test_all_operations_work_without_graph_store(self, manager):
        """System works without graph store (no Neo4j configured)."""
        assert manager.graph_store is None

        # Write and read should still work fine
        graph = _galileo()
        await manager.write_knowledge_nodes(graph.knowledge_nodes)
        await manager.write_factor_nodes(graph.factor_nodes)

        nodes = await manager.get_knowledge_nodes()
        assert len(nodes) == 10
        factors = await manager.get_factor_nodes()
        assert len(factors) == 7
