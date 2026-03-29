"""Tests for Neo4jGraphStore.

All tests are marked with ``@pytest.mark.neo4j`` and are auto-skipped when
a Neo4j instance is not reachable at bolt://localhost:7687.
"""

from __future__ import annotations

import os

import pytest

NEO4J_URI = os.environ.get("NEO4J_TEST_URI", "bolt://localhost:7687")
NEO4J_USER = os.environ.get("NEO4J_TEST_USER", "neo4j")
NEO4J_PASSWORD = os.environ.get("NEO4J_TEST_PASSWORD", "")

pytestmark = pytest.mark.neo4j


async def _neo4j_available() -> bool:
    """Return True if a Neo4j instance is reachable."""
    try:
        import neo4j

        auth = (NEO4J_USER, NEO4J_PASSWORD) if NEO4J_PASSWORD else None
        driver = neo4j.AsyncGraphDatabase.driver(NEO4J_URI, auth=auth)
        await driver.verify_connectivity()
        await driver.close()
        return True
    except Exception:
        return False


@pytest.fixture
async def graph_store():
    """Yield an initialized, clean Neo4jGraphStore; skip if Neo4j unavailable."""
    if not await _neo4j_available():
        pytest.skip("Neo4j not available")

    from gaia.libs.storage.neo4j import Neo4jGraphStore

    store = Neo4jGraphStore(
        uri=NEO4J_URI,
        user=NEO4J_USER,
        password=NEO4J_PASSWORD,
    )
    await store.initialize()
    await store.clean_all()
    yield store
    await store.close()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_knowledge_node(node_id: str, type_: str = "claim"):
    from gaia.models.graph_ir import KnowledgeNode, KnowledgeType, SourceRef

    return KnowledgeNode(
        id=node_id,
        type=KnowledgeType(type_),
        content=f"Content for {node_id}",
        source_refs=[SourceRef(package="test_pkg", version="1.0")],
    )


def _make_factor(factor_id: str, premises: list[str], conclusion: str | None):
    from gaia.models.graph_ir import (
        FactorCategory,
        FactorNode,
        FactorStage,
        ReasoningType,
        SourceRef,
    )

    if conclusion is None:
        # bilateral factor — no reasoning_type needed for initial stage
        return FactorNode(
            factor_id=factor_id,
            scope="local",
            category=FactorCategory.INFER,
            stage=FactorStage.INITIAL,
            premises=premises,
            conclusion=None,
            source_ref=SourceRef(package="test_pkg", version="1.0"),
        )
    return FactorNode(
        factor_id=factor_id,
        scope="local",
        category=FactorCategory.INFER,
        stage=FactorStage.PERMANENT,
        reasoning_type=ReasoningType.ENTAILMENT,
        premises=premises,
        conclusion=conclusion,
        source_ref=SourceRef(package="test_pkg", version="1.0"),
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestWriteNodes:
    async def test_write_nodes_stores_nodes(self, graph_store):
        """Written nodes are accessible via get_neighbors (returns empty list, no error)."""
        nodes = [_make_knowledge_node("node_a"), _make_knowledge_node("node_b")]
        await graph_store.write_nodes(nodes)

        # Nodes exist but have no connections yet
        neighbors_a = await graph_store.get_neighbors("node_a")
        assert isinstance(neighbors_a, list)
        assert neighbors_a == []

    async def test_write_nodes_idempotent(self, graph_store):
        """Writing the same nodes twice does not duplicate them."""
        nodes = [_make_knowledge_node("node_x")]
        await graph_store.write_nodes(nodes)
        await graph_store.write_nodes(nodes)

        # Still no neighbors (not connected) — no error
        result = await graph_store.get_neighbors("node_x")
        assert result == []

    async def test_write_empty_nodes_no_error(self, graph_store):
        await graph_store.write_nodes([])


class TestWriteFactors:
    async def test_write_factor_creates_connection(self, graph_store):
        """After writing a factor, get_neighbors finds the connected node."""
        node_a = _make_knowledge_node("node_a")
        node_b = _make_knowledge_node("node_b")
        await graph_store.write_nodes([node_a, node_b])

        factor = _make_factor("factor_1", premises=["node_a"], conclusion="node_b")
        await graph_store.write_factors([factor])

        neighbors_a = await graph_store.get_neighbors("node_a")
        assert "node_b" in neighbors_a

        neighbors_b = await graph_store.get_neighbors("node_b")
        assert "node_a" in neighbors_b

    async def test_write_bilateral_factor_no_conclusion_edge(self, graph_store):
        """Bilateral factors (conclusion=None) create PREMISE edges but no CONCLUSION edge."""
        node_a = _make_knowledge_node("node_a")
        node_b = _make_knowledge_node("node_b")
        await graph_store.write_nodes([node_a, node_b])

        bilateral = _make_factor("bilateral_1", premises=["node_a", "node_b"], conclusion=None)
        await graph_store.write_factors([bilateral])

        # Both nodes are connected through the factor
        neighbors_a = await graph_store.get_neighbors("node_a")
        assert "node_b" in neighbors_a

    async def test_write_factors_idempotent(self, graph_store):
        """Writing the same factor twice does not duplicate edges."""
        node_a = _make_knowledge_node("node_a")
        node_b = _make_knowledge_node("node_b")
        await graph_store.write_nodes([node_a, node_b])

        factor = _make_factor("factor_1", premises=["node_a"], conclusion="node_b")
        await graph_store.write_factors([factor])
        await graph_store.write_factors([factor])

        neighbors = await graph_store.get_neighbors("node_a")
        assert neighbors.count("node_b") == 1

    async def test_write_empty_factors_no_error(self, graph_store):
        await graph_store.write_factors([])


class TestGetNeighbors:
    async def test_get_neighbors_unconnected_node(self, graph_store):
        """A node with no factors has no neighbors."""
        await graph_store.write_nodes([_make_knowledge_node("isolated")])
        result = await graph_store.get_neighbors("isolated")
        assert result == []

    async def test_get_neighbors_nonexistent_node(self, graph_store):
        """Querying a nonexistent node returns an empty list."""
        result = await graph_store.get_neighbors("does_not_exist")
        assert result == []

    async def test_get_neighbors_chain(self, graph_store):
        """In A→B→C, neighbors of B includes both A and C."""
        a = _make_knowledge_node("a")
        b = _make_knowledge_node("b")
        c = _make_knowledge_node("c")
        await graph_store.write_nodes([a, b, c])

        f1 = _make_factor("f1", premises=["a"], conclusion="b")
        f2 = _make_factor("f2", premises=["b"], conclusion="c")
        await graph_store.write_factors([f1, f2])

        neighbors_b = await graph_store.get_neighbors("b")
        assert "a" in neighbors_b
        assert "c" in neighbors_b


class TestGetSubgraph:
    async def test_get_subgraph_depth_1(self, graph_store):
        """get_subgraph at depth=1 returns immediate neighbors."""
        a = _make_knowledge_node("a")
        b = _make_knowledge_node("b")
        c = _make_knowledge_node("c")
        await graph_store.write_nodes([a, b, c])

        f1 = _make_factor("f1", premises=["a"], conclusion="b")
        await graph_store.write_factors([f1])

        node_ids, factor_ids = await graph_store.get_subgraph(["a"], depth=1)
        assert "a" in node_ids
        assert "b" in node_ids
        assert "f1" in factor_ids

        # c is not reachable from a
        assert "c" not in node_ids

    async def test_get_subgraph_depth_2(self, graph_store):
        """get_subgraph at depth=2 traverses an A→B→C chain."""
        a = _make_knowledge_node("a")
        b = _make_knowledge_node("b")
        c = _make_knowledge_node("c")
        await graph_store.write_nodes([a, b, c])

        f1 = _make_factor("f1", premises=["a"], conclusion="b")
        f2 = _make_factor("f2", premises=["b"], conclusion="c")
        await graph_store.write_factors([f1, f2])

        node_ids, factor_ids = await graph_store.get_subgraph(["a"], depth=2)
        assert "a" in node_ids
        assert "b" in node_ids
        assert "c" in node_ids
        assert "f1" in factor_ids
        assert "f2" in factor_ids

    async def test_get_subgraph_empty_seeds(self, graph_store):
        """Empty seed list returns empty results."""
        node_ids, factor_ids = await graph_store.get_subgraph([], depth=1)
        assert node_ids == []
        assert factor_ids == []

    async def test_get_subgraph_isolated_node(self, graph_store):
        """Seed node with no connections returns just the seed."""
        await graph_store.write_nodes([_make_knowledge_node("isolated")])
        node_ids, factor_ids = await graph_store.get_subgraph(["isolated"], depth=2)
        assert "isolated" in node_ids
        assert factor_ids == []


class TestCleanAll:
    async def test_clean_all_removes_nodes_and_factors(self, graph_store):
        """clean_all deletes all KnowledgeNodes and FactorNodes."""
        nodes = [_make_knowledge_node("a"), _make_knowledge_node("b")]
        await graph_store.write_nodes(nodes)
        factor = _make_factor("f1", premises=["a"], conclusion="b")
        await graph_store.write_factors([factor])

        # Verify data exists
        neighbors = await graph_store.get_neighbors("a")
        assert "b" in neighbors

        await graph_store.clean_all()

        # After clean, no neighbors
        neighbors = await graph_store.get_neighbors("a")
        assert neighbors == []

    async def test_clean_all_idempotent(self, graph_store):
        """Calling clean_all on an already empty store does not error."""
        await graph_store.clean_all()
        await graph_store.clean_all()
