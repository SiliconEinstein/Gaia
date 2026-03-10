"""Tests for KuzuGraphStore schema initialisation and topology writes."""

import pytest

from libs.storage_v2.kuzu_graph_store import KuzuGraphStore
from libs.storage_v2.models import BeliefSnapshot, Chain, Closure, ResourceAttachment


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
