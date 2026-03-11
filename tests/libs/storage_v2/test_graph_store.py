"""Tests for KuzuGraphStore — version-aware graph topology."""

from datetime import datetime

import pytest

from libs.storage_v2.kuzu_graph_store import KuzuGraphStore, _vid
from libs.storage_v2.models import (
    BeliefSnapshot,
    Chain,
    ChainStep,
    Closure,
    ClosureRef,
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
    result = store._execute("CALL show_tables() RETURN *")
    names: set[str] = set()
    while result.has_next():
        names.add(result.get_next()[1])
    return names


def _count_nodes(store: KuzuGraphStore, label: str) -> int:
    result = store._execute(f"MATCH (n:{label}) RETURN COUNT(n)")
    return result.get_next()[0]


def _count_rels(store: KuzuGraphStore, rel_type: str) -> int:
    result = store._execute(f"MATCH ()-[r:{rel_type}]->() RETURN COUNT(r)")
    return result.get_next()[0]


# ── Schema ──


class TestInitializeSchema:
    async def test_initialize_creates_tables(self, graph_store):
        tables = _table_names(graph_store)
        for expected in ("Closure", "Chain", "PREMISE", "CONCLUSION", "Resource"):
            assert expected in tables

    async def test_initialize_idempotent(self, graph_store):
        await graph_store.initialize_schema()
        tables = _table_names(graph_store)
        assert "Closure" in tables


# ── write_topology ──


class TestWriteTopology:
    async def test_write_creates_closure_nodes(self, graph_store, closures, chains):
        await graph_store.write_topology(closures, chains)
        # Each (closure_id, version) gets its own node
        count = _count_nodes(graph_store, "Closure")
        # closures from fixtures + any extra refs from chain steps
        expected_vids = {_vid(c.closure_id, c.version) for c in closures}
        result = graph_store._execute("MATCH (n:Closure) RETURN n.closure_vid")
        stored_vids: set[str] = set()
        while result.has_next():
            stored_vids.add(result.get_next()[0])
        assert expected_vids.issubset(stored_vids)
        assert count >= len(expected_vids)

    async def test_write_creates_chain_nodes(self, graph_store, closures, chains):
        await graph_store.write_topology(closures, chains)
        result = graph_store._execute("MATCH (n:Chain) RETURN n.chain_id")
        stored = set()
        while result.has_next():
            stored.add(result.get_next()[0])
        assert stored == {ch.chain_id for ch in chains}

    async def test_write_creates_premise_relationships(self, graph_store, closures, chains):
        await graph_store.write_topology(closures, chains)
        expected = sum(len(step.premises) for ch in chains for step in ch.steps)
        assert _count_rels(graph_store, "PREMISE") == expected

    async def test_write_creates_conclusion_relationships(self, graph_store, closures, chains):
        await graph_store.write_topology(closures, chains)
        expected = sum(len(ch.steps) for ch in chains)
        assert _count_rels(graph_store, "CONCLUSION") == expected

    async def test_write_topology_idempotent(self, graph_store, closures, chains):
        await graph_store.write_topology(closures, chains)
        c1 = _count_nodes(graph_store, "Closure")
        ch1 = _count_nodes(graph_store, "Chain")
        p1 = _count_rels(graph_store, "PREMISE")
        co1 = _count_rels(graph_store, "CONCLUSION")

        await graph_store.write_topology(closures, chains)
        assert _count_nodes(graph_store, "Closure") == c1
        assert _count_nodes(graph_store, "Chain") == ch1
        assert _count_rels(graph_store, "PREMISE") == p1
        assert _count_rels(graph_store, "CONCLUSION") == co1

    async def test_multi_version_closure_creates_separate_nodes(self, graph_store):
        """PR #100 comment 1: different versions must be separate graph nodes."""
        c_v1 = Closure(
            closure_id="x",
            version=1,
            type="claim",
            content="v1",
            prior=0.5,
            source_package_id="p",
            source_module_id="m",
            created_at=datetime(2026, 1, 1),
        )
        c_v2 = c_v1.model_copy(update={"version": 2, "content": "v2", "prior": 0.7})
        chain = Chain(
            chain_id="ch1",
            module_id="m",
            package_id="p",
            type="deduction",
            steps=[
                ChainStep(
                    step_index=0,
                    premises=[ClosureRef(closure_id="x", version=1)],
                    reasoning="r",
                    conclusion=ClosureRef(closure_id="x", version=2),
                )
            ],
        )
        await graph_store.write_topology([c_v1, c_v2], [chain])

        # Two distinct Closure nodes
        assert _count_nodes(graph_store, "Closure") == 2

        # Each has correct properties
        res = graph_store._conn.execute(
            "MATCH (c:Closure {closure_vid: $vid}) RETURN c.prior",
            {"vid": _vid("x", 1)},
        )
        assert res.get_next()[0] == pytest.approx(0.5)

        res = graph_store._conn.execute(
            "MATCH (c:Closure {closure_vid: $vid}) RETURN c.prior",
            {"vid": _vid("x", 2)},
        )
        assert res.get_next()[0] == pytest.approx(0.7)


# ── write_resource_links ──


class TestWriteResourceLinks:
    async def test_write_resource_links_to_closure(
        self, graph_store, closures, chains, attachments
    ):
        await graph_store.write_topology(closures, chains)
        await graph_store.write_resource_links(attachments)
        result = graph_store._execute(
            "MATCH (r:Resource)-[a:ATTACHED_TO]->(c:Closure) RETURN COUNT(a)"
        )
        expected = sum(1 for a in attachments if a.target_type == "closure")
        assert result.get_next()[0] == expected

    async def test_write_resource_links_to_chain(self, graph_store, closures, chains, attachments):
        await graph_store.write_topology(closures, chains)
        await graph_store.write_resource_links(attachments)
        result = graph_store._execute(
            "MATCH (r:Resource)-[a:ATTACHED_TO]->(ch:Chain) RETURN COUNT(a)"
        )
        expected = sum(1 for a in attachments if a.target_type in ("chain", "chain_step"))
        assert result.get_next()[0] == expected

    async def test_write_resource_links_idempotent(
        self, graph_store, closures, chains, attachments
    ):
        await graph_store.write_topology(closures, chains)
        await graph_store.write_resource_links(attachments)
        count_1 = _count_rels(graph_store, "ATTACHED_TO")
        await graph_store.write_resource_links(attachments)
        assert _count_rels(graph_store, "ATTACHED_TO") == count_1

    async def test_chain_step_attachments_preserve_step_index(self, graph_store):
        """PR #100 comment 4: chain_step attachments must preserve step identity."""
        chain = Chain(
            chain_id="ch",
            module_id="m",
            package_id="p",
            type="deduction",
            steps=[
                ChainStep(
                    step_index=0,
                    premises=[ClosureRef(closure_id="a", version=1)],
                    reasoning="r0",
                    conclusion=ClosureRef(closure_id="b", version=1),
                ),
                ChainStep(
                    step_index=1,
                    premises=[ClosureRef(closure_id="b", version=1)],
                    reasoning="r1",
                    conclusion=ClosureRef(closure_id="c", version=1),
                ),
            ],
        )
        closures_local = [
            Closure(
                closure_id=cid,
                version=1,
                type="claim",
                content="",
                prior=0.5,
                source_package_id="p",
                source_module_id="m",
                created_at=datetime(2026, 1, 1),
            )
            for cid in ("a", "b", "c")
        ]
        await graph_store.write_topology(closures_local, [chain])

        # Two attachments to same chain, same resource, same role, different steps
        att0 = ResourceAttachment(
            resource_id="res1",
            target_type="chain_step",
            target_id="ch:0",
            role="evidence",
        )
        att1 = ResourceAttachment(
            resource_id="res1",
            target_type="chain_step",
            target_id="ch:1",
            role="evidence",
        )
        await graph_store.write_resource_links([att0, att1])

        # Both should exist (not collapsed)
        result = graph_store._conn.execute(
            "MATCH (r:Resource)-[a:ATTACHED_TO]->(ch:Chain {chain_id: 'ch'}) "
            "RETURN a.step_index ORDER BY a.step_index"
        )
        steps = []
        while result.has_next():
            steps.append(result.get_next()[0])
        assert steps == [0, 1]

    async def test_closure_attachment_resolves_latest_version(self, graph_store):
        """PR #100 follow-up: closure attachments must resolve to latest version,
        not hardcode @1. If only v2 exists, attachment should still succeed."""
        closures_v2 = [
            Closure(
                closure_id="x",
                version=2,
                type="claim",
                content="v2 only",
                prior=0.5,
                source_package_id="p",
                source_module_id="m",
                created_at=datetime(2026, 1, 1),
            )
        ]
        await graph_store.write_topology(closures_v2, [])

        att = ResourceAttachment(
            resource_id="res_v2",
            target_type="closure",
            target_id="x",
            role="evidence",
        )
        await graph_store.write_resource_links([att])

        result = graph_store._conn.execute(
            "MATCH (r:Resource)-[a:ATTACHED_TO]->(c:Closure) RETURN c.closure_vid"
        )
        assert result.has_next()
        assert result.get_next()[0] == "x@2"

    async def test_closure_attachment_skips_nonexistent(self, graph_store):
        """Attachment to a closure not in the graph should be silently skipped."""
        await graph_store.write_topology([], [])
        att = ResourceAttachment(
            resource_id="res_ghost",
            target_type="closure",
            target_id="ghost",
            role="evidence",
        )
        await graph_store.write_resource_links([att])

        result = graph_store._conn.execute(
            "MATCH (r:Resource)-[a:ATTACHED_TO]->(c:Closure) RETURN COUNT(a)"
        )
        assert result.get_next()[0] == 0


# ── update_beliefs ──


class TestUpdateBeliefs:
    async def test_update_beliefs_sets_value(self, graph_store, closures, chains, beliefs):
        await graph_store.write_topology(closures, chains)
        await graph_store.update_beliefs(beliefs)

        # Last write per (closure_id, version) wins
        expected: dict[str, float] = {}
        for snap in beliefs:
            expected[_vid(snap.closure_id, snap.version)] = snap.belief

        for vid, expected_belief in expected.items():
            result = graph_store._conn.execute(
                "MATCH (cl:Closure {closure_vid: $vid}) RETURN cl.belief",
                {"vid": vid},
            )
            if result.has_next():
                assert result.get_next()[0] == pytest.approx(expected_belief)

    async def test_update_beliefs_nonexistent_closure(self, graph_store):
        snap = BeliefSnapshot(
            closure_id="nonexistent",
            version=1,
            belief=0.5,
            bp_run_id="bp_test",
            computed_at="2026-01-01T00:00:00Z",
        )
        await graph_store.update_beliefs([snap])  # should not raise

    async def test_update_beliefs_version_aware(self, graph_store):
        """PR #100 comment 2: beliefs for different versions are independent."""
        c_v1 = Closure(
            closure_id="x",
            version=1,
            type="claim",
            content="",
            prior=0.5,
            source_package_id="p",
            source_module_id="m",
            created_at=datetime(2026, 1, 1),
        )
        c_v2 = c_v1.model_copy(update={"version": 2})
        await graph_store.write_topology([c_v1, c_v2], [])

        snap_v1 = BeliefSnapshot(
            closure_id="x",
            version=1,
            belief=0.3,
            bp_run_id="r1",
            computed_at=datetime(2026, 1, 1),
        )
        snap_v2 = BeliefSnapshot(
            closure_id="x",
            version=2,
            belief=0.9,
            bp_run_id="r1",
            computed_at=datetime(2026, 1, 1),
        )
        await graph_store.update_beliefs([snap_v1, snap_v2])

        # v1 and v2 should have independent belief values
        r1 = graph_store._conn.execute(
            "MATCH (c:Closure {closure_vid: $vid}) RETURN c.belief",
            {"vid": _vid("x", 1)},
        )
        assert r1.get_next()[0] == pytest.approx(0.3)

        r2 = graph_store._conn.execute(
            "MATCH (c:Closure {closure_vid: $vid}) RETURN c.belief",
            {"vid": _vid("x", 2)},
        )
        assert r2.get_next()[0] == pytest.approx(0.9)


# ── update_probability ──


class TestUpdateProbability:
    async def test_update_probability_sets_value(self, graph_store, closures, chains):
        await graph_store.write_topology(closures, chains)
        chain = chains[0]
        await graph_store.update_probability(chain.chain_id, 0, 0.95)

        result = graph_store._conn.execute(
            "MATCH (ch:Chain {chain_id: $chid})-[r:CONCLUSION]->(:Closure) "
            "WHERE r.step_index = 0 RETURN r.probability",
            {"chid": chain.chain_id},
        )
        assert result.get_next()[0] == pytest.approx(0.95)

    async def test_update_probability_per_step(self, graph_store):
        """PR #100 comment 3: probability must be per (chain_id, step_index)."""
        closures_local = [
            Closure(
                closure_id=cid,
                version=1,
                type="claim",
                content="",
                prior=0.5,
                source_package_id="p",
                source_module_id="m",
                created_at=datetime(2026, 1, 1),
            )
            for cid in ("a", "b", "c")
        ]
        chain = Chain(
            chain_id="ch",
            module_id="m",
            package_id="p",
            type="deduction",
            steps=[
                ChainStep(
                    step_index=0,
                    premises=[ClosureRef(closure_id="a", version=1)],
                    reasoning="r0",
                    conclusion=ClosureRef(closure_id="b", version=1),
                ),
                ChainStep(
                    step_index=1,
                    premises=[ClosureRef(closure_id="b", version=1)],
                    reasoning="r1",
                    conclusion=ClosureRef(closure_id="c", version=1),
                ),
            ],
        )
        await graph_store.write_topology(closures_local, [chain])

        # Set different probabilities for each step
        await graph_store.update_probability("ch", 0, 0.2)
        await graph_store.update_probability("ch", 1, 0.9)

        # Both should be independently stored
        r0 = graph_store._conn.execute(
            "MATCH (ch:Chain {chain_id: 'ch'})-[r:CONCLUSION]->(:Closure) "
            "WHERE r.step_index = 0 RETURN r.probability",
        )
        assert r0.get_next()[0] == pytest.approx(0.2)

        r1 = graph_store._conn.execute(
            "MATCH (ch:Chain {chain_id: 'ch'})-[r:CONCLUSION]->(:Closure) "
            "WHERE r.step_index = 1 RETURN r.probability",
        )
        assert r1.get_next()[0] == pytest.approx(0.9)


# ── get_neighbors ──


class TestGetNeighbors:
    async def test_get_neighbors_default(self, graph_store, closures, chains):
        await graph_store.write_topology(closures, chains)
        result = await graph_store.get_neighbors(
            "galileo_falling_bodies.reasoning.heavier_falls_faster"
        )
        assert isinstance(result, Subgraph)
        assert len(result.chain_ids) > 0
        assert len(result.closure_ids) > 0

    async def test_get_neighbors_downstream(self, graph_store, closures, chains):
        await graph_store.write_topology(closures, chains)
        result = await graph_store.get_neighbors(
            "galileo_falling_bodies.reasoning.heavier_falls_faster",
            direction="downstream",
        )
        assert "galileo_falling_bodies.reasoning.verdict_chain" in result.chain_ids

    async def test_get_neighbors_upstream(self, graph_store, closures, chains):
        await graph_store.write_topology(closures, chains)
        result = await graph_store.get_neighbors(
            "galileo_falling_bodies.reasoning.combined_slower",
            direction="upstream",
        )
        assert "galileo_falling_bodies.reasoning.verdict_chain" in result.chain_ids

    async def test_get_neighbors_nonexistent(self, graph_store, closures, chains):
        await graph_store.write_topology(closures, chains)
        result = await graph_store.get_neighbors("nonexistent.id")
        assert result == Subgraph()

    async def test_get_neighbors_max_hops(self, graph_store, closures, chains):
        await graph_store.write_topology(closures, chains)
        cid = "galileo_falling_bodies.reasoning.heavier_falls_faster"
        r1 = await graph_store.get_neighbors(cid, max_hops=1)
        r2 = await graph_store.get_neighbors(cid, max_hops=2)
        assert len(r2.closure_ids) >= len(r1.closure_ids)
        assert len(r2.chain_ids) >= len(r1.chain_ids)

    async def test_get_neighbors_chain_type_filter(self, graph_store, closures, chains):
        await graph_store.write_topology(closures, chains)
        result = await graph_store.get_neighbors(
            "galileo_falling_bodies.reasoning.combined_slower",
            chain_types=["contradiction"],
        )
        for ch_id in result.chain_ids:
            res = graph_store._conn.execute(
                "MATCH (ch:Chain {chain_id: $chid}) RETURN ch.type",
                {"chid": ch_id},
            )
            assert res.get_next()[0] == "contradiction"

    async def test_get_neighbors_nonexistent_chain_type(self, graph_store, closures, chains):
        """Filter with non-matching type returns empty."""
        await graph_store.write_topology(closures, chains)
        result = await graph_store.get_neighbors(
            "galileo_falling_bodies.reasoning.heavier_falls_faster",
            chain_types=["nonexistent_type"],
        )
        assert result.chain_ids == set()


# ── get_subgraph ──


class TestGetSubgraph:
    async def test_get_subgraph_returns_connected(self, graph_store, closures, chains):
        await graph_store.write_topology(closures, chains)
        result = await graph_store.get_subgraph(
            "galileo_falling_bodies.reasoning.heavier_falls_faster"
        )
        assert "galileo_falling_bodies.reasoning.heavier_falls_faster" in result.closure_ids
        assert len(result.closure_ids) > 1
        assert len(result.chain_ids) > 0

    async def test_get_subgraph_respects_max_closures(self, graph_store, closures, chains):
        await graph_store.write_topology(closures, chains)
        result = await graph_store.get_subgraph(
            "galileo_falling_bodies.reasoning.heavier_falls_faster",
            max_closures=2,
        )
        assert len(result.closure_ids) <= 2

    async def test_get_subgraph_nonexistent(self, graph_store, closures, chains):
        await graph_store.write_topology(closures, chains)
        result = await graph_store.get_subgraph("nonexistent.id")
        assert result == Subgraph()


# ── search_topology ──


class TestSearchTopology:
    async def test_search_topology_returns_scored(self, graph_store, closures, chains):
        await graph_store.write_topology(closures, chains)
        results = await graph_store.search_topology(
            ["galileo_falling_bodies.reasoning.heavier_falls_faster"],
            hops=2,
        )
        assert len(results) > 0
        for r in results:
            assert isinstance(r, ScoredClosure)
        scores = [r.score for r in results]
        assert scores == sorted(scores, reverse=True)

    async def test_search_topology_excludes_seeds(self, graph_store, closures, chains):
        await graph_store.write_topology(closures, chains)
        seed = "galileo_falling_bodies.reasoning.heavier_falls_faster"
        results = await graph_store.search_topology([seed], hops=1)
        assert seed not in {r.closure.closure_id for r in results}

    async def test_search_topology_empty_seeds(self, graph_store, closures, chains):
        await graph_store.write_topology(closures, chains)
        assert await graph_store.search_topology([], hops=1) == []

    async def test_search_topology_returns_latest_version(self, graph_store):
        """search_topology should return the latest version of discovered closures."""
        c_v1 = Closure(
            closure_id="a",
            version=1,
            type="claim",
            content="",
            prior=0.5,
            source_package_id="p",
            source_module_id="m",
            created_at=datetime(2026, 1, 1),
        )
        c_v2 = c_v1.model_copy(update={"version": 2, "prior": 0.8})
        seed = Closure(
            closure_id="seed",
            version=1,
            type="claim",
            content="",
            prior=0.5,
            source_package_id="p",
            source_module_id="m",
            created_at=datetime(2026, 1, 1),
        )
        chain = Chain(
            chain_id="ch",
            module_id="m",
            package_id="p",
            type="deduction",
            steps=[
                ChainStep(
                    step_index=0,
                    premises=[ClosureRef(closure_id="seed", version=1)],
                    reasoning="r",
                    conclusion=ClosureRef(closure_id="a", version=2),
                ),
            ],
        )
        await graph_store.write_topology([c_v1, c_v2, seed], [chain])
        results = await graph_store.search_topology(["seed"], hops=1)
        a_results = [r for r in results if r.closure.closure_id == "a"]
        assert len(a_results) == 1
        assert a_results[0].closure.version == 2


# ── delete_package ──


class TestDeletePackage:
    async def test_delete_package_removes_topology(self, graph_store, closures, chains):
        """delete_package should remove all closures and chains for a package."""
        await graph_store.write_topology(closures, chains)

        pkg_id = closures[0].source_package_id
        await graph_store.delete_package(pkg_id)

        # Verify closure nodes are gone
        assert _count_nodes(graph_store, "Closure") == 0

        # Verify chain nodes are gone
        assert _count_nodes(graph_store, "Chain") == 0

        # Verify relationships are gone
        assert _count_rels(graph_store, "PREMISE") == 0
        assert _count_rels(graph_store, "CONCLUSION") == 0

    async def test_delete_package_neighbor_query_returns_empty(self, graph_store, closures, chains):
        """After delete_package, neighbor queries should return empty results."""
        await graph_store.write_topology(closures, chains)

        pkg_id = closures[0].source_package_id
        await graph_store.delete_package(pkg_id)

        result = await graph_store.get_neighbors(
            closures[0].closure_id, direction="both", chain_types=None, max_hops=1
        )
        assert len(result.closure_ids) == 0
        assert len(result.chain_ids) == 0

    async def test_delete_package_is_idempotent(self, graph_store):
        """Deleting a non-existent package should not raise."""
        await graph_store.delete_package("nonexistent_pkg")  # should not raise


# ── close ──


class TestClose:
    async def test_close_does_not_error(self, tmp_path):
        store = KuzuGraphStore(tmp_path / "close_test")
        await store.initialize_schema()
        await store.close()

    async def test_close_idempotent(self, tmp_path):
        store = KuzuGraphStore(tmp_path / "close_idem_test")
        await store.initialize_schema()
        await store.close()
        await store.close()


# ── Full roundtrip ──


class TestFullRoundtrip:
    async def test_full_roundtrip(self, graph_store, closures, chains, attachments, beliefs):
        # 1. Write topology
        await graph_store.write_topology(closures, chains)

        # 2. Write resource links
        await graph_store.write_resource_links(attachments)

        # 3. Update beliefs
        await graph_store.update_beliefs(beliefs)

        # 4. Update probability per step
        chain = chains[0]
        await graph_store.update_probability(chain.chain_id, 0, 0.9)

        # 5. Query neighbors
        premise_id = chain.steps[0].premises[0].closure_id
        neighbors = await graph_store.get_neighbors(premise_id)
        assert len(neighbors.chain_ids) > 0

        # 6. Query subgraph
        subgraph = await graph_store.get_subgraph(premise_id)
        assert len(subgraph.closure_ids) > 0

        # 7. Search topology
        results = await graph_store.search_topology([premise_id], hops=2)
        assert len(results) >= 0

        # 8. Verify belief was updated (version-aware)
        last_belief = beliefs[-1]
        vid = _vid(last_belief.closure_id, last_belief.version)
        result = graph_store._conn.execute(
            "MATCH (c:Closure {closure_vid: $vid}) RETURN c.belief",
            {"vid": vid},
        )
        if result.has_next():
            assert result.get_next()[0] == pytest.approx(last_belief.belief)

        # 9. Verify probability was updated per step
        result = graph_store._conn.execute(
            "MATCH (ch:Chain {chain_id: $chid})-[r:CONCLUSION]->(:Closure) "
            "WHERE r.step_index = 0 RETURN r.probability",
            {"chid": chain.chain_id},
        )
        assert result.get_next()[0] == pytest.approx(0.9)
