"""Unit tests for Neo4jGraphStore — mocked Neo4j driver."""

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from gaia.lkm.models import GlobalFactorNode, GlobalVariableNode, LocalCanonicalRef
from gaia.lkm.storage.neo4j_store import Neo4jGraphStore


def _make_var(gcn_id: str, var_type: str = "claim") -> GlobalVariableNode:
    return GlobalVariableNode(
        id=gcn_id,
        type=var_type,
        visibility="public",
        content_hash="hash_" + gcn_id,
        parameters=[],
        representative_lcn=LocalCanonicalRef(
            package_id="pkg", version="v1", local_id="local_" + gcn_id
        ),
        local_members=[],
    )


def _make_factor(gfac_id: str, premises: list[str], conclusion: str) -> GlobalFactorNode:
    return GlobalFactorNode(
        id=gfac_id,
        factor_type="deduction",
        subtype="noisy_and",
        premises=premises,
        conclusion=conclusion,
        steps=[],
        representative_lfn="lfac_dummy",
        source_package="pkg",
    )


@pytest.fixture
def mock_driver():
    """Create a mock Neo4j async driver with proper async context manager."""
    driver = MagicMock()
    session = AsyncMock()

    @asynccontextmanager
    async def fake_session(**kwargs):
        yield session

    driver.session = fake_session
    driver.close = AsyncMock()
    return driver, session


@pytest.fixture
def store(mock_driver):
    driver, _ = mock_driver
    return Neo4jGraphStore(driver, database="testdb")


class TestWriteVariables:
    async def test_write_variables_calls_merge(self, store, mock_driver):
        _, session = mock_driver
        vars = [_make_var("gcn_aaa"), _make_var("gcn_bbb")]
        await store.write_variables(vars)
        session.run.assert_called_once()
        call_args = session.run.call_args
        assert "MERGE (v:Variable {gcn_id: n.gcn_id})" in call_args[0][0]
        assert len(call_args[1]["nodes"]) == 2

    async def test_write_empty_variables_noop(self, store, mock_driver):
        _, session = mock_driver
        await store.write_variables([])
        session.run.assert_not_called()


class TestWriteFactors:
    async def test_write_factors_calls_merge(self, store, mock_driver):
        _, session = mock_driver
        factors = [_make_factor("gfac_x", ["gcn_a"], "gcn_b")]
        await store.write_factors(factors)
        session.run.assert_called_once()
        call_args = session.run.call_args
        assert "MERGE (f:Factor {gfac_id: n.gfac_id})" in call_args[0][0]

    async def test_write_empty_factors_noop(self, store, mock_driver):
        _, session = mock_driver
        await store.write_factors([])
        session.run.assert_not_called()


class TestWriteEdges:
    async def test_write_edges_creates_premise_and_conclusion(self, store, mock_driver):
        _, session = mock_driver
        factors = [_make_factor("gfac_1", ["gcn_a", "gcn_b"], "gcn_c")]
        await store.write_edges([], factors)
        # 2 calls: premise edges + conclusion edges
        assert session.run.call_count == 2
        premise_call = session.run.call_args_list[0]
        assert "PREMISE" in premise_call[0][0]
        assert len(premise_call[1]["edges"]) == 2
        conclusion_call = session.run.call_args_list[1]
        assert "CONCLUSION" in conclusion_call[0][0]

    async def test_write_empty_factors_noop(self, store, mock_driver):
        _, session = mock_driver
        await store.write_edges([], [])
        session.run.assert_not_called()


class TestGetSubgraph:
    async def test_subgraph_returns_nodes_and_edges(self, store, mock_driver):
        _, session = mock_driver

        var_node = MagicMock()
        var_node.labels = {"Variable"}
        var_node.__getitem__ = lambda self, k: {
            "gcn_id": "gcn_a",
            "type": "claim",
            "visibility": "public",
        }[k]
        var_node.get = lambda k, d=None: {
            "gcn_id": "gcn_a",
            "type": "claim",
            "visibility": "public",
        }.get(k, d)

        fac_node = MagicMock()
        fac_node.labels = {"Factor"}
        fac_node.__getitem__ = lambda self, k: {
            "gfac_id": "gfac_1",
            "subtype": "noisy_and",
            "factor_type": "deduction",
        }[k]
        fac_node.get = lambda k, d=None: {
            "gfac_id": "gfac_1",
            "subtype": "noisy_and",
            "factor_type": "deduction",
        }.get(k, d)

        rel = MagicMock()
        rel.type = "PREMISE"
        rel.start_node = var_node
        rel.end_node = fac_node

        record = {"all_nodes": [var_node, fac_node], "all_rels": [rel]}
        result_mock = AsyncMock()
        result_mock.single.return_value = record
        session.run.return_value = result_mock

        subgraph = await store.get_subgraph("gcn_a", hops=2)

        assert len(subgraph["nodes"]) == 2
        assert subgraph["nodes"][0]["id"] == "gcn_a"
        assert subgraph["nodes"][0]["type"] == "variable"
        assert subgraph["nodes"][1]["id"] == "gfac_1"
        assert subgraph["nodes"][1]["type"] == "factor"
        assert len(subgraph["edges"]) == 1
        assert subgraph["edges"][0]["type"] == "premise"

    async def test_subgraph_empty_when_no_match(self, store, mock_driver):
        _, session = mock_driver
        result_mock = AsyncMock()
        result_mock.single.return_value = None
        session.run.return_value = result_mock

        subgraph = await store.get_subgraph("gcn_missing", hops=1)
        assert subgraph == {"nodes": [], "edges": []}

    async def test_hops_inlined_in_cypher(self, store, mock_driver):
        """Verify hops is in the query text, not as a parameter."""
        _, session = mock_driver
        result_mock = AsyncMock()
        result_mock.single.return_value = None
        session.run.return_value = result_mock

        await store.get_subgraph("gcn_x", hops=3)
        query = session.run.call_args[0][0]
        assert "[*1..3]" in query
        kwargs = session.run.call_args[1]
        assert "hops" not in kwargs


class TestGetNeighbors:
    async def test_neighbors_returns_list(self, store, mock_driver):
        _, session = mock_driver

        var_node = MagicMock()
        var_node.labels = {"Variable"}
        var_node.__getitem__ = lambda self, k: {"gcn_id": "gcn_b", "type": "claim"}[k]
        var_node.get = lambda k, d=None: {"gcn_id": "gcn_b", "type": "claim"}.get(k, d)

        record = MagicMock()
        record.__getitem__ = lambda self, k: var_node

        class AsyncIterResult:
            def __aiter__(self):
                return self

            async def __anext__(self):
                if not hasattr(self, "_done"):
                    self._done = True
                    return record
                raise StopAsyncIteration

        session.run.return_value = AsyncIterResult()

        neighbors = await store.get_neighbors("gcn_a")
        assert len(neighbors) == 1
        assert neighbors[0]["id"] == "gcn_b"


class TestCountNodes:
    async def test_count_nodes(self, store, mock_driver):
        _, session = mock_driver

        var_result = AsyncMock()
        var_result.single.return_value = {"c": 100}
        fac_result = AsyncMock()
        fac_result.single.return_value = {"c": 50}

        session.run.side_effect = [var_result, fac_result]

        counts = await store.count_nodes()
        assert counts == {"variables": 100, "factors": 50}


class TestWriteGlobalGraph:
    async def test_write_global_graph_calls_all_three(self, store):
        with (
            patch.object(store, "write_variables", new_callable=AsyncMock) as wv,
            patch.object(store, "write_factors", new_callable=AsyncMock) as wf,
            patch.object(store, "write_edges", new_callable=AsyncMock) as we,
        ):
            vars = [_make_var("gcn_1")]
            facs = [_make_factor("gfac_1", ["gcn_1"], "gcn_2")]
            await store.write_global_graph(vars, facs)
            wv.assert_called_once_with(vars)
            wf.assert_called_once_with(facs)
            we.assert_called_once_with(vars, facs)
