"""Tests for KuzuGraphStore schema initialisation, topology writes, and queries."""

import pytest

from libs.storage_v2.kuzu_graph_store import KuzuGraphStore
from libs.storage_v2.models import (
    BeliefSnapshot,
    Chain,
    Closure,
    ResourceAttachment,
    ScoredClosure,
    Subgraph,
)


@pytest.fixture
async def graph_store(tmp_path):
    """Create a KuzuGraphStore in a temporary directory with schema initialized."""
    store = KuzuGraphStore(tmp_path / "kuzu_db")
    await store.initialize_schema()
    yield store
    await store.close()


def _table_names(store: KuzuGraphStore) -> set[str]:
    """Return the set of table names in the database."""
    result = store._execute("CALL show_tables() RETURN *")
    names: set[str] = set()
    while result.has_next():
        row = result.get_next()
        names.add(row[1])
    return names


class TestInitializeSchema:
    """Verify that initialize_schema creates the expected tables."""

    async def test_initialize_creates_tables(self, graph_store: KuzuGraphStore):
        tables = _table_names(graph_store)
        assert "Closure" in tables
        assert "Chain" in tables
        assert "PREMISE" in tables
        assert "CONCLUSION" in tables

    async def test_initialize_idempotent(self, graph_store: KuzuGraphStore):
        """Calling initialize_schema a second time should not raise."""
        await graph_store.initialize_schema()
        tables = _table_names(graph_store)
        assert "Closure" in tables
        assert "Chain" in tables


def _count_nodes(store: KuzuGraphStore, label: str) -> int:
    """Return the number of nodes of a given label."""
    result = store._execute(f"MATCH (n:{label}) RETURN COUNT(n)")
    return result.get_next()[0]


def _count_rels(store: KuzuGraphStore, rel_type: str) -> int:
    """Return the number of relationships of a given type."""
    result = store._execute(f"MATCH ()-[r:{rel_type}]->() RETURN COUNT(r)")
    return result.get_next()[0]


def _get_node_ids(store: KuzuGraphStore, label: str, key: str) -> set[str]:
    """Return all primary key values for a node label."""
    result = store._execute(f"MATCH (n:{label}) RETURN n.{key}")
    ids: set[str] = set()
    while result.has_next():
        ids.add(result.get_next()[0])
    return ids


class TestWriteTopology:
    """Verify that write_topology creates nodes and relationships."""

    async def test_write_creates_closure_nodes(
        self,
        graph_store: KuzuGraphStore,
        closures: list[Closure],
        chains: list[Chain],
    ):
        await graph_store.write_topology(closures, chains)
        # All unique closure_ids from the fixtures must be present
        stored_ids = _get_node_ids(graph_store, "Closure", "closure_id")
        expected_ids = {c.closure_id for c in closures}
        assert expected_ids.issubset(stored_ids)

    async def test_write_creates_chain_nodes(
        self,
        graph_store: KuzuGraphStore,
        closures: list[Closure],
        chains: list[Chain],
    ):
        await graph_store.write_topology(closures, chains)
        stored_ids = _get_node_ids(graph_store, "Chain", "chain_id")
        expected_ids = {ch.chain_id for ch in chains}
        assert expected_ids == stored_ids

    async def test_write_creates_premise_relationships(
        self,
        graph_store: KuzuGraphStore,
        closures: list[Closure],
        chains: list[Chain],
    ):
        await graph_store.write_topology(closures, chains)
        # Count expected PREMISE rels from fixture data
        expected = sum(len(step.premises) for ch in chains for step in ch.steps)
        assert _count_rels(graph_store, "PREMISE") == expected

    async def test_write_creates_conclusion_relationships(
        self,
        graph_store: KuzuGraphStore,
        closures: list[Closure],
        chains: list[Chain],
    ):
        await graph_store.write_topology(closures, chains)
        # One CONCLUSION rel per step
        expected = sum(len(ch.steps) for ch in chains)
        assert _count_rels(graph_store, "CONCLUSION") == expected

    async def test_write_topology_idempotent(
        self,
        graph_store: KuzuGraphStore,
        closures: list[Closure],
        chains: list[Chain],
    ):
        """Writing twice should not create duplicate nodes or relationships."""
        await graph_store.write_topology(closures, chains)
        closure_count_1 = _count_nodes(graph_store, "Closure")
        chain_count_1 = _count_nodes(graph_store, "Chain")
        premise_count_1 = _count_rels(graph_store, "PREMISE")
        conclusion_count_1 = _count_rels(graph_store, "CONCLUSION")

        await graph_store.write_topology(closures, chains)
        assert _count_nodes(graph_store, "Closure") == closure_count_1
        assert _count_nodes(graph_store, "Chain") == chain_count_1
        assert _count_rels(graph_store, "PREMISE") == premise_count_1
        assert _count_rels(graph_store, "CONCLUSION") == conclusion_count_1


class TestWriteResourceLinks:
    """Verify that write_resource_links creates Resource nodes and ATTACHED_TO rels."""

    async def test_write_resource_links_to_closure(
        self,
        graph_store: KuzuGraphStore,
        closures: list[Closure],
        chains: list[Chain],
        attachments: list[ResourceAttachment],
    ):
        """Resource links to closures should create ATTACHED_TO relationships."""
        await graph_store.write_topology(closures, chains)
        await graph_store.write_resource_links(attachments)

        result = graph_store._execute(
            "MATCH (r:Resource)-[a:ATTACHED_TO]->(c:Closure) RETURN COUNT(a)"
        )
        count = result.get_next()[0]
        # Count expected: attachments targeting closures
        expected = sum(1 for a in attachments if a.target_type == "closure")
        assert count == expected

    async def test_write_resource_links_to_chain(
        self,
        graph_store: KuzuGraphStore,
        closures: list[Closure],
        chains: list[Chain],
        attachments: list[ResourceAttachment],
    ):
        """Resource links to chains (including chain_step) should target Chain nodes."""
        await graph_store.write_topology(closures, chains)
        await graph_store.write_resource_links(attachments)

        result = graph_store._execute(
            "MATCH (r:Resource)-[a:ATTACHED_TO]->(ch:Chain) RETURN COUNT(a)"
        )
        count = result.get_next()[0]
        # chain and chain_step both target Chain nodes
        expected = sum(1 for a in attachments if a.target_type in ("chain", "chain_step"))
        assert count == expected

    async def test_write_resource_links_idempotent(
        self,
        graph_store: KuzuGraphStore,
        closures: list[Closure],
        chains: list[Chain],
        attachments: list[ResourceAttachment],
    ):
        """Writing resource links twice should not double the count."""
        await graph_store.write_topology(closures, chains)
        await graph_store.write_resource_links(attachments)
        count_1 = _count_rels(graph_store, "ATTACHED_TO")

        await graph_store.write_resource_links(attachments)
        assert _count_rels(graph_store, "ATTACHED_TO") == count_1


class TestUpdateBeliefs:
    """Verify that update_beliefs sets belief values on Closure nodes."""

    async def test_update_beliefs_sets_value(
        self,
        graph_store: KuzuGraphStore,
        closures: list[Closure],
        chains: list[Chain],
        beliefs: list[BeliefSnapshot],
    ):
        await graph_store.write_topology(closures, chains)
        await graph_store.update_beliefs(beliefs)

        # Check the last belief written for each closure_id
        for snap in beliefs:
            result = graph_store._execute(
                f"MATCH (cl:Closure {{closure_id: '{snap.closure_id}'}}) RETURN cl.belief"
            )
            row = result.get_next()
            assert row[0] is not None

    async def test_update_beliefs_nonexistent_closure(
        self,
        graph_store: KuzuGraphStore,
    ):
        """Updating beliefs for a non-existent closure should not raise."""
        snap = BeliefSnapshot(
            closure_id="nonexistent.closure",
            version=1,
            belief=0.5,
            bp_run_id="bp_test",
            computed_at="2026-01-01T00:00:00Z",
        )
        await graph_store.update_beliefs([snap])


class TestUpdateProbability:
    """Verify that update_probability sets probability on Chain nodes."""

    async def test_update_probability_sets_value(
        self,
        graph_store: KuzuGraphStore,
        closures: list[Closure],
        chains: list[Chain],
    ):
        await graph_store.write_topology(closures, chains)
        chain = chains[0]
        await graph_store.update_probability(chain.chain_id, 0, 0.95)

        result = graph_store._execute(
            f"MATCH (ch:Chain {{chain_id: '{chain.chain_id}'}}) RETURN ch.probability"
        )
        assert result.get_next()[0] == pytest.approx(0.95)


class TestGetNeighbors:
    """Verify BFS neighbor traversal through chains."""

    async def test_get_neighbors_default(
        self,
        graph_store: KuzuGraphStore,
        closures: list[Closure],
        chains: list[Chain],
    ):
        """A premise closure should discover chains and closures in both directions."""
        await graph_store.write_topology(closures, chains)
        # heavier_falls_faster is a premise in verdict_chain
        result = await graph_store.get_neighbors(
            "galileo_falling_bodies.reasoning.heavier_falls_faster"
        )
        assert isinstance(result, Subgraph)
        assert len(result.chain_ids) > 0
        assert len(result.closure_ids) > 0

    async def test_get_neighbors_downstream(
        self,
        graph_store: KuzuGraphStore,
        closures: list[Closure],
        chains: list[Chain],
    ):
        """Downstream from a premise should find chains it feeds into."""
        await graph_store.write_topology(closures, chains)
        result = await graph_store.get_neighbors(
            "galileo_falling_bodies.reasoning.heavier_falls_faster",
            direction="downstream",
        )
        assert len(result.chain_ids) > 0
        # Should find verdict_chain (heavier_falls_faster is a premise)
        assert "galileo_falling_bodies.reasoning.verdict_chain" in result.chain_ids

    async def test_get_neighbors_upstream(
        self,
        graph_store: KuzuGraphStore,
        closures: list[Closure],
        chains: list[Chain],
    ):
        """Upstream from a conclusion should find chains that produce it."""
        await graph_store.write_topology(closures, chains)
        # combined_slower is a conclusion of verdict_chain step 0
        result = await graph_store.get_neighbors(
            "galileo_falling_bodies.reasoning.combined_slower",
            direction="upstream",
        )
        assert len(result.chain_ids) > 0
        assert "galileo_falling_bodies.reasoning.verdict_chain" in result.chain_ids

    async def test_get_neighbors_nonexistent(
        self,
        graph_store: KuzuGraphStore,
        closures: list[Closure],
        chains: list[Chain],
    ):
        """Non-existent closure should return empty Subgraph."""
        await graph_store.write_topology(closures, chains)
        result = await graph_store.get_neighbors("nonexistent.closure.id")
        assert result == Subgraph()

    async def test_get_neighbors_max_hops(
        self,
        graph_store: KuzuGraphStore,
        closures: list[Closure],
        chains: list[Chain],
    ):
        """Two hops should discover at least as many nodes as one hop."""
        await graph_store.write_topology(closures, chains)
        cid = "galileo_falling_bodies.reasoning.heavier_falls_faster"
        result_1 = await graph_store.get_neighbors(cid, max_hops=1)
        result_2 = await graph_store.get_neighbors(cid, max_hops=2)
        assert len(result_2.closure_ids) >= len(result_1.closure_ids)
        assert len(result_2.chain_ids) >= len(result_1.chain_ids)

    async def test_get_neighbors_chain_type_filter(
        self,
        graph_store: KuzuGraphStore,
        closures: list[Closure],
        chains: list[Chain],
    ):
        """Filtering by chain type should only return matching types."""
        await graph_store.write_topology(closures, chains)
        # combined_slower is premise of contradiction_chain and conclusion of verdict_chain
        result = await graph_store.get_neighbors(
            "galileo_falling_bodies.reasoning.combined_slower",
            chain_types=["contradiction"],
        )
        # Should only find the contradiction chain
        for ch_id in result.chain_ids:
            res = graph_store._execute(f"MATCH (ch:Chain {{chain_id: '{ch_id}'}}) RETURN ch.type")
            assert res.get_next()[0] == "contradiction"


class TestGetSubgraph:
    """Verify BFS subgraph extraction."""

    async def test_get_subgraph_returns_connected(
        self,
        graph_store: KuzuGraphStore,
        closures: list[Closure],
        chains: list[Chain],
    ):
        """Subgraph from a connected closure should include the seed and neighbors."""
        await graph_store.write_topology(closures, chains)
        result = await graph_store.get_subgraph(
            "galileo_falling_bodies.reasoning.heavier_falls_faster"
        )
        assert isinstance(result, Subgraph)
        # Seed must be included
        assert "galileo_falling_bodies.reasoning.heavier_falls_faster" in result.closure_ids
        # Should find other connected closures
        assert len(result.closure_ids) > 1
        assert len(result.chain_ids) > 0

    async def test_get_subgraph_respects_max_closures(
        self,
        graph_store: KuzuGraphStore,
        closures: list[Closure],
        chains: list[Chain],
    ):
        """max_closures=2 should limit the number of closure IDs returned."""
        await graph_store.write_topology(closures, chains)
        result = await graph_store.get_subgraph(
            "galileo_falling_bodies.reasoning.heavier_falls_faster",
            max_closures=2,
        )
        assert len(result.closure_ids) <= 2

    async def test_get_subgraph_nonexistent(
        self,
        graph_store: KuzuGraphStore,
        closures: list[Closure],
        chains: list[Chain],
    ):
        """Non-existent closure should return empty Subgraph."""
        await graph_store.write_topology(closures, chains)
        result = await graph_store.get_subgraph("nonexistent.closure.id")
        assert result == Subgraph()


class TestSearchTopology:
    """Verify topology-based search with distance scoring."""

    async def test_search_topology_returns_scored(
        self,
        graph_store: KuzuGraphStore,
        closures: list[Closure],
        chains: list[Chain],
    ):
        """Results should be ScoredClosure instances sorted by score descending."""
        await graph_store.write_topology(closures, chains)
        results = await graph_store.search_topology(
            ["galileo_falling_bodies.reasoning.heavier_falls_faster"],
            hops=2,
        )
        assert len(results) > 0
        for r in results:
            assert isinstance(r, ScoredClosure)
        # Check descending order
        scores = [r.score for r in results]
        assert scores == sorted(scores, reverse=True)

    async def test_search_topology_excludes_seeds(
        self,
        graph_store: KuzuGraphStore,
        closures: list[Closure],
        chains: list[Chain],
    ):
        """Seed closures should not appear in results."""
        await graph_store.write_topology(closures, chains)
        seed = "galileo_falling_bodies.reasoning.heavier_falls_faster"
        results = await graph_store.search_topology([seed], hops=1)
        result_ids = {r.closure.closure_id for r in results}
        assert seed not in result_ids

    async def test_search_topology_empty_seeds(
        self,
        graph_store: KuzuGraphStore,
        closures: list[Closure],
        chains: list[Chain],
    ):
        """Empty seed list should return empty results."""
        await graph_store.write_topology(closures, chains)
        results = await graph_store.search_topology([], hops=1)
        assert results == []
