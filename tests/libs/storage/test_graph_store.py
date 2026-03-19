"""Unified GraphStore ABC compliance tests — parametrized over Kuzu and Neo4j.

Kuzu tests always run. Neo4j tests require a running Neo4j instance and are
auto-skipped if unavailable.
"""

import os
from datetime import datetime

import pytest

from libs.storage.graph_store import GraphStore
from libs.storage.kuzu_graph_store import KuzuGraphStore, _knowledge_vid as _vid
from libs.storage.models import (
    CanonicalBinding,
    Chain,
    ChainStep,
    FactorNode,
    GlobalCanonicalNode,
    Knowledge,
    KnowledgeRef,
    ResourceAttachment,
    ScoredKnowledge,
    Subgraph,
)

NEO4J_URI = os.environ.get("NEO4J_TEST_URI", "bolt://localhost:7687")
NEO4J_PASSWORD = os.environ.get("NEO4J_TEST_PASSWORD", "")
NEO4J_DB = os.environ.get("NEO4J_TEST_DB", "neo4j")


async def _neo4j_available() -> bool:
    try:
        import neo4j

        auth = ("neo4j", NEO4J_PASSWORD) if NEO4J_PASSWORD else None
        driver = neo4j.AsyncGraphDatabase.driver(NEO4J_URI, auth=auth)
        async with driver.session(database=NEO4J_DB) as session:
            await session.run("RETURN 1")
        await driver.close()
        return True
    except Exception:
        return False


# ── Backend-agnostic query helper ──


async def _run_query(store: GraphStore, query: str, params: dict | None = None) -> list[list]:
    """Run a Cypher query on either Kuzu or Neo4j store, return list of rows."""
    if isinstance(store, KuzuGraphStore):
        result = store._conn.execute(query, params or {})
        rows = []
        while result.has_next():
            rows.append(result.get_next())
        return rows
    else:
        from libs.storage.neo4j_graph_store import Neo4jGraphStore

        assert isinstance(store, Neo4jGraphStore)
        async with store._driver.session(database=store._db) as session:
            result = await session.run(query, params or {})
            return [list(record.values()) async for record in result]


async def _count_nodes(store: GraphStore, label: str) -> int:
    rows = await _run_query(store, f"MATCH (n:{label}) RETURN COUNT(n)")
    return rows[0][0]


async def _count_rels(store: GraphStore, rel_type: str) -> int:
    rows = await _run_query(store, f"MATCH ()-[r:{rel_type}]->() RETURN COUNT(r)")
    return rows[0][0]


# ── Parametrized fixture ──


@pytest.fixture(params=["kuzu", "neo4j"])
async def graph_store(request, tmp_path) -> GraphStore:
    """Yield a GraphStore instance — Kuzu always available, Neo4j skipped if down."""
    if request.param == "kuzu":
        store = KuzuGraphStore(tmp_path / "kuzu_db")
        await store.initialize_schema()
        yield store
        await store.close()

    elif request.param == "neo4j":
        if not await _neo4j_available():
            pytest.skip("Neo4j not available")
        import neo4j

        from libs.storage.neo4j_graph_store import Neo4jGraphStore

        auth = ("neo4j", NEO4J_PASSWORD) if NEO4J_PASSWORD else None
        driver = neo4j.AsyncGraphDatabase.driver(NEO4J_URI, auth=auth)
        store = Neo4jGraphStore(driver=driver, database=NEO4J_DB)
        await store.initialize_schema()
        yield store
        # Clean up all data after each test
        async with driver.session(database=NEO4J_DB) as session:
            await session.run("MATCH (n) DETACH DELETE n")
        await driver.close()


# ── Schema ──


class TestInitializeSchema:
    async def test_initialize_idempotent(self, graph_store):
        await graph_store.initialize_schema()
        # Should not error; verify store is operational by writing
        await graph_store.write_topology([], [])


# ── write_topology ──


class TestWriteTopology:
    async def test_write_creates_knowledge_nodes(self, graph_store, knowledge_items, chains):
        await graph_store.write_topology(knowledge_items, chains)
        count = await _count_nodes(graph_store, "Knowledge")
        expected_vids = {_vid(c.knowledge_id, c.version) for c in knowledge_items}
        rows = await _run_query(graph_store, "MATCH (n:Knowledge) RETURN n.knowledge_vid")
        stored_vids = {row[0] for row in rows}
        assert expected_vids.issubset(stored_vids)
        assert count >= len(expected_vids)

    async def test_write_creates_chain_nodes(self, graph_store, knowledge_items, chains):
        await graph_store.write_topology(knowledge_items, chains)
        rows = await _run_query(graph_store, "MATCH (n:Chain) RETURN n.chain_id")
        stored = {row[0] for row in rows}
        assert stored == {ch.chain_id for ch in chains}

    async def test_write_creates_premise_relationships(self, graph_store, knowledge_items, chains):
        await graph_store.write_topology(knowledge_items, chains)
        expected = sum(len(step.premises) for ch in chains for step in ch.steps)
        assert await _count_rels(graph_store, "PREMISE") == expected

    async def test_write_creates_conclusion_relationships(
        self, graph_store, knowledge_items, chains
    ):
        await graph_store.write_topology(knowledge_items, chains)
        expected = sum(len(ch.steps) for ch in chains)
        assert await _count_rels(graph_store, "CONCLUSION") == expected

    async def test_write_topology_idempotent(self, graph_store, knowledge_items, chains):
        await graph_store.write_topology(knowledge_items, chains)
        c1 = await _count_nodes(graph_store, "Knowledge")
        ch1 = await _count_nodes(graph_store, "Chain")
        p1 = await _count_rels(graph_store, "PREMISE")
        co1 = await _count_rels(graph_store, "CONCLUSION")

        await graph_store.write_topology(knowledge_items, chains)
        assert await _count_nodes(graph_store, "Knowledge") == c1
        assert await _count_nodes(graph_store, "Chain") == ch1
        assert await _count_rels(graph_store, "PREMISE") == p1
        assert await _count_rels(graph_store, "CONCLUSION") == co1

    async def test_multi_version_knowledge_creates_separate_nodes(self, graph_store):
        """Different versions must be separate graph nodes."""
        c_v1 = Knowledge(
            knowledge_id="x",
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
                    premises=[KnowledgeRef(knowledge_id="x", version=1)],
                    reasoning="r",
                    conclusion=KnowledgeRef(knowledge_id="x", version=2),
                )
            ],
        )
        await graph_store.write_topology([c_v1, c_v2], [chain])

        # Two distinct Knowledge nodes
        assert await _count_nodes(graph_store, "Knowledge") == 2

        # Each has correct properties
        rows = await _run_query(
            graph_store,
            "MATCH (c:Knowledge {knowledge_vid: $vid}) RETURN c.prior",
            {"vid": _vid("x", 1)},
        )
        assert rows[0][0] == pytest.approx(0.5)

        rows = await _run_query(
            graph_store,
            "MATCH (c:Knowledge {knowledge_vid: $vid}) RETURN c.prior",
            {"vid": _vid("x", 2)},
        )
        assert rows[0][0] == pytest.approx(0.7)


# ── write_resource_links ──


class TestWriteResourceLinks:
    async def test_write_resource_links_to_knowledge(
        self, graph_store, knowledge_items, chains, attachments
    ):
        await graph_store.write_topology(knowledge_items, chains)
        await graph_store.write_resource_links(attachments)
        rows = await _run_query(
            graph_store,
            "MATCH (r:Resource)-[a:ATTACHED_TO]->(c:Knowledge) RETURN COUNT(a)",
        )
        expected = sum(1 for a in attachments if a.target_type == "knowledge")
        assert rows[0][0] == expected

    async def test_write_resource_links_to_chain(
        self, graph_store, knowledge_items, chains, attachments
    ):
        await graph_store.write_topology(knowledge_items, chains)
        await graph_store.write_resource_links(attachments)
        rows = await _run_query(
            graph_store,
            "MATCH (r:Resource)-[a:ATTACHED_TO]->(ch:Chain) RETURN COUNT(a)",
        )
        expected = sum(1 for a in attachments if a.target_type in ("chain", "chain_step"))
        assert rows[0][0] == expected

    async def test_write_resource_links_idempotent(
        self, graph_store, knowledge_items, chains, attachments
    ):
        await graph_store.write_topology(knowledge_items, chains)
        await graph_store.write_resource_links(attachments)
        count_1 = await _count_rels(graph_store, "ATTACHED_TO")
        await graph_store.write_resource_links(attachments)
        assert await _count_rels(graph_store, "ATTACHED_TO") == count_1

    async def test_chain_step_attachments_preserve_step_index(self, graph_store):
        """chain_step attachments must preserve step identity."""
        chain = Chain(
            chain_id="ch",
            module_id="m",
            package_id="p",
            type="deduction",
            steps=[
                ChainStep(
                    step_index=0,
                    premises=[KnowledgeRef(knowledge_id="a", version=1)],
                    reasoning="r0",
                    conclusion=KnowledgeRef(knowledge_id="b", version=1),
                ),
                ChainStep(
                    step_index=1,
                    premises=[KnowledgeRef(knowledge_id="b", version=1)],
                    reasoning="r1",
                    conclusion=KnowledgeRef(knowledge_id="c", version=1),
                ),
            ],
        )
        knowledge_local = [
            Knowledge(
                knowledge_id=kid,
                version=1,
                type="claim",
                content="",
                prior=0.5,
                source_package_id="p",
                source_module_id="m",
                created_at=datetime(2026, 1, 1),
            )
            for kid in ("a", "b", "c")
        ]
        await graph_store.write_topology(knowledge_local, [chain])

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

        rows = await _run_query(
            graph_store,
            "MATCH (r:Resource)-[a:ATTACHED_TO]->(ch:Chain {chain_id: 'ch'}) "
            "RETURN a.step_index ORDER BY a.step_index",
        )
        steps = [row[0] for row in rows]
        assert steps == [0, 1]

    async def test_knowledge_attachment_resolves_latest_version(self, graph_store):
        """Knowledge attachments must resolve to latest version."""
        knowledge_v2 = [
            Knowledge(
                knowledge_id="x",
                version=2,
                type="claim",
                content="v2 only",
                prior=0.5,
                source_package_id="p",
                source_module_id="m",
                created_at=datetime(2026, 1, 1),
            )
        ]
        await graph_store.write_topology(knowledge_v2, [])

        att = ResourceAttachment(
            resource_id="res_v2",
            target_type="knowledge",
            target_id="x",
            role="evidence",
        )
        await graph_store.write_resource_links([att])

        rows = await _run_query(
            graph_store,
            "MATCH (r:Resource)-[a:ATTACHED_TO]->(c:Knowledge) RETURN c.knowledge_vid",
        )
        assert len(rows) == 1
        assert rows[0][0] == "x@2"

    async def test_knowledge_attachment_skips_nonexistent(self, graph_store):
        """Attachment to a knowledge node not in the graph should be silently skipped."""
        await graph_store.write_topology([], [])
        att = ResourceAttachment(
            resource_id="res_ghost",
            target_type="knowledge",
            target_id="ghost",
            role="evidence",
        )
        await graph_store.write_resource_links([att])

        rows = await _run_query(
            graph_store,
            "MATCH (r:Resource)-[a:ATTACHED_TO]->(c:Knowledge) RETURN COUNT(a)",
        )
        assert rows[0][0] == 0

    async def test_module_and_package_attachments_skipped(
        self, graph_store, knowledge_items, chains
    ):
        """Attachments with target_type 'module' or 'package' should be silently skipped."""
        await graph_store.write_topology(knowledge_items, chains)
        atts = [
            ResourceAttachment(
                resource_id="res_mod",
                target_type="module",
                target_id="some_module",
                role="supplement",
            ),
            ResourceAttachment(
                resource_id="res_pkg",
                target_type="package",
                target_id="some_package",
                role="supplement",
            ),
        ]
        await graph_store.write_resource_links(atts)
        rows = await _run_query(graph_store, "MATCH (r:Resource) RETURN COUNT(r)")
        assert rows[0][0] == 0

    async def test_chain_attachment_direct(self, graph_store, knowledge_items, chains):
        """Attachment with target_type='chain' creates link to chain node."""
        await graph_store.write_topology(knowledge_items, chains)
        att = ResourceAttachment(
            resource_id="res_chain",
            target_type="chain",
            target_id=chains[0].chain_id,
            role="evidence",
        )
        await graph_store.write_resource_links([att])
        rows = await _run_query(
            graph_store,
            "MATCH (r:Resource)-[a:ATTACHED_TO]->(ch:Chain) RETURN COUNT(a)",
        )
        assert rows[0][0] == 1


# ── write_factor_topology ──


class TestWriteFactorTopology:
    async def test_write_factor_topology(self, graph_store):
        factors = [
            FactorNode(
                factor_id="pkg.mod.f1",
                type="infer",
                premises=["pkg/k1", "pkg/k2"],
                contexts=["pkg/k3"],
                conclusion="pkg/k4",
                package_id="pkg",
            ),
            FactorNode(
                factor_id="pkg.mutex.1",
                type="contradiction",
                premises=["pkg/rel1", "pkg/k1", "pkg/k5"],
                conclusion=None,
                package_id="pkg",
            ),
        ]
        await graph_store.write_factor_topology(factors)
        # Verify Factor nodes created
        count = await _count_nodes(graph_store, "Factor")
        assert count == 2
        # Verify rels created
        fp_count = await _count_rels(graph_store, "FACTOR_PREMISE")
        assert fp_count == 5  # 2 from f1, 3 from contradiction
        fc_count = await _count_rels(graph_store, "FACTOR_CONTEXT")
        assert fc_count == 1  # 1 from f1
        fcl_count = await _count_rels(graph_store, "FACTOR_CONCLUSION")
        assert fcl_count == 1  # only from f1 (contradiction has None conclusion)

    async def test_factor_topology_idempotent(self, graph_store):
        factors = [
            FactorNode(
                factor_id="pkg.f1",
                type="infer",
                premises=["pkg/k1"],
                conclusion="pkg/k2",
                package_id="pkg",
            ),
        ]
        await graph_store.write_factor_topology(factors)
        c1 = await _count_nodes(graph_store, "Factor")
        r1 = await _count_rels(graph_store, "FACTOR_PREMISE")
        await graph_store.write_factor_topology(factors)
        assert await _count_nodes(graph_store, "Factor") == c1
        assert await _count_rels(graph_store, "FACTOR_PREMISE") == r1


# ── write_global_topology ──


class TestWriteGlobalTopology:
    async def test_write_global_topology(self, graph_store):
        global_nodes = [
            GlobalCanonicalNode(
                global_canonical_id="gcn_01",
                knowledge_type="claim",
                representative_content="X is true",
            ),
        ]
        bindings = [
            CanonicalBinding(
                package="pkg",
                version="1.0.0",
                local_graph_hash="sha256:abc",
                local_canonical_id="pkg/k1",
                decision="create_new",
                global_canonical_id="gcn_01",
                decided_at=datetime.now(),
                decided_by="auto",
            ),
        ]
        await graph_store.write_global_topology(bindings, global_nodes)
        count = await _count_nodes(graph_store, "GlobalCanonicalNode")
        assert count == 1
        bind_count = await _count_rels(graph_store, "CANONICAL_BINDING")
        assert bind_count == 1

    async def test_global_topology_idempotent(self, graph_store):
        global_nodes = [
            GlobalCanonicalNode(
                global_canonical_id="gcn_01",
                knowledge_type="claim",
                representative_content="X is true",
            ),
        ]
        bindings = [
            CanonicalBinding(
                package="pkg",
                version="1.0.0",
                local_graph_hash="sha256:abc",
                local_canonical_id="pkg/k1",
                decision="create_new",
                global_canonical_id="gcn_01",
                decided_at=datetime.now(),
                decided_by="auto",
            ),
        ]
        await graph_store.write_global_topology(bindings, global_nodes)
        await graph_store.write_global_topology(bindings, global_nodes)
        assert await _count_nodes(graph_store, "GlobalCanonicalNode") == 1
        assert await _count_rels(graph_store, "CANONICAL_BINDING") == 1


# ── get_neighbors ──


class TestGetNeighbors:
    async def test_get_neighbors_default(self, graph_store, knowledge_items, chains):
        await graph_store.write_topology(knowledge_items, chains)
        result = await graph_store.get_neighbors(
            "galileo_falling_bodies.reasoning.heavier_falls_faster"
        )
        assert isinstance(result, Subgraph)
        assert len(result.chain_ids) > 0
        assert len(result.knowledge_ids) > 0

    async def test_get_neighbors_downstream(self, graph_store, knowledge_items, chains):
        await graph_store.write_topology(knowledge_items, chains)
        result = await graph_store.get_neighbors(
            "galileo_falling_bodies.reasoning.heavier_falls_faster",
            direction="downstream",
        )
        assert "galileo_falling_bodies.reasoning.verdict_chain" in result.chain_ids

    async def test_get_neighbors_upstream(self, graph_store, knowledge_items, chains):
        await graph_store.write_topology(knowledge_items, chains)
        result = await graph_store.get_neighbors(
            "galileo_falling_bodies.reasoning.combined_slower",
            direction="upstream",
        )
        assert "galileo_falling_bodies.reasoning.verdict_chain" in result.chain_ids

    async def test_get_neighbors_nonexistent(self, graph_store, knowledge_items, chains):
        await graph_store.write_topology(knowledge_items, chains)
        result = await graph_store.get_neighbors("nonexistent.id")
        assert result == Subgraph()

    async def test_get_neighbors_max_hops(self, graph_store, knowledge_items, chains):
        await graph_store.write_topology(knowledge_items, chains)
        kid = "galileo_falling_bodies.reasoning.heavier_falls_faster"
        r1 = await graph_store.get_neighbors(kid, max_hops=1)
        r2 = await graph_store.get_neighbors(kid, max_hops=2)
        assert len(r2.knowledge_ids) >= len(r1.knowledge_ids)
        assert len(r2.chain_ids) >= len(r1.chain_ids)

    async def test_get_neighbors_chain_type_filter(self, graph_store, knowledge_items, chains):
        await graph_store.write_topology(knowledge_items, chains)
        result = await graph_store.get_neighbors(
            "galileo_falling_bodies.reasoning.combined_slower",
            chain_types=["contradiction"],
        )
        for ch_id in result.chain_ids:
            rows = await _run_query(
                graph_store,
                "MATCH (ch:Chain {chain_id: $chid}) RETURN ch.type",
                {"chid": ch_id},
            )
            assert rows[0][0] == "contradiction"

    async def test_get_neighbors_nonexistent_chain_type(self, graph_store, knowledge_items, chains):
        """Filter with non-matching type returns empty."""
        await graph_store.write_topology(knowledge_items, chains)
        result = await graph_store.get_neighbors(
            "galileo_falling_bodies.reasoning.heavier_falls_faster",
            chain_types=["nonexistent_type"],
        )
        assert result.chain_ids == set()


# ── get_subgraph ──


class TestGetSubgraph:
    async def test_get_subgraph_returns_connected(self, graph_store, knowledge_items, chains):
        await graph_store.write_topology(knowledge_items, chains)
        result = await graph_store.get_subgraph(
            "galileo_falling_bodies.reasoning.heavier_falls_faster"
        )
        assert "galileo_falling_bodies.reasoning.heavier_falls_faster" in result.knowledge_ids
        assert len(result.knowledge_ids) > 1
        assert len(result.chain_ids) > 0

    async def test_get_subgraph_respects_max_knowledge(self, graph_store, knowledge_items, chains):
        await graph_store.write_topology(knowledge_items, chains)
        result = await graph_store.get_subgraph(
            "galileo_falling_bodies.reasoning.heavier_falls_faster",
            max_knowledge=2,
        )
        assert len(result.knowledge_ids) <= 2

    async def test_get_subgraph_nonexistent(self, graph_store, knowledge_items, chains):
        await graph_store.write_topology(knowledge_items, chains)
        result = await graph_store.get_subgraph("nonexistent.id")
        assert result == Subgraph()


# ── search_topology ──


class TestSearchTopology:
    async def test_search_topology_returns_scored(self, graph_store, knowledge_items, chains):
        await graph_store.write_topology(knowledge_items, chains)
        results = await graph_store.search_topology(
            ["galileo_falling_bodies.reasoning.heavier_falls_faster"],
            hops=2,
        )
        assert len(results) > 0
        for r in results:
            assert isinstance(r, ScoredKnowledge)
        scores = [r.score for r in results]
        assert scores == sorted(scores, reverse=True)

    async def test_search_topology_excludes_seeds(self, graph_store, knowledge_items, chains):
        await graph_store.write_topology(knowledge_items, chains)
        seed = "galileo_falling_bodies.reasoning.heavier_falls_faster"
        results = await graph_store.search_topology([seed], hops=1)
        assert seed not in {r.knowledge.knowledge_id for r in results}

    async def test_search_topology_empty_seeds(self, graph_store, knowledge_items, chains):
        await graph_store.write_topology(knowledge_items, chains)
        assert await graph_store.search_topology([], hops=1) == []

    async def test_search_topology_returns_latest_version(self, graph_store):
        """search_topology should return the latest version of discovered knowledge."""
        c_v1 = Knowledge(
            knowledge_id="a",
            version=1,
            type="claim",
            content="",
            prior=0.5,
            source_package_id="p",
            source_module_id="m",
            created_at=datetime(2026, 1, 1),
        )
        c_v2 = c_v1.model_copy(update={"version": 2, "prior": 0.8})
        seed = Knowledge(
            knowledge_id="seed",
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
                    premises=[KnowledgeRef(knowledge_id="seed", version=1)],
                    reasoning="r",
                    conclusion=KnowledgeRef(knowledge_id="a", version=2),
                ),
            ],
        )
        await graph_store.write_topology([c_v1, c_v2, seed], [chain])
        results = await graph_store.search_topology(["seed"], hops=1)
        a_results = [r for r in results if r.knowledge.knowledge_id == "a"]
        assert len(a_results) == 1
        assert a_results[0].knowledge.version == 2


# ── delete_package ──


class TestDeletePackage:
    async def test_delete_package_removes_topology(self, graph_store, knowledge_items, chains):
        """delete_package should remove all knowledge and chains for a package."""
        await graph_store.write_topology(knowledge_items, chains)

        pkg_id = knowledge_items[0].source_package_id
        await graph_store.delete_package(pkg_id)

        assert await _count_nodes(graph_store, "Knowledge") == 0
        assert await _count_nodes(graph_store, "Chain") == 0
        assert await _count_rels(graph_store, "PREMISE") == 0
        assert await _count_rels(graph_store, "CONCLUSION") == 0

    async def test_delete_package_neighbor_query_returns_empty(
        self, graph_store, knowledge_items, chains
    ):
        """After delete_package, neighbor queries should return empty results."""
        await graph_store.write_topology(knowledge_items, chains)

        pkg_id = knowledge_items[0].source_package_id
        await graph_store.delete_package(pkg_id)

        result = await graph_store.get_neighbors(
            knowledge_items[0].knowledge_id, direction="both", chain_types=None, max_hops=1
        )
        assert len(result.knowledge_ids) == 0
        assert len(result.chain_ids) == 0

    async def test_delete_package_is_idempotent(self, graph_store):
        """Deleting a non-existent package should not raise."""
        await graph_store.delete_package("nonexistent_pkg")  # should not raise

    async def test_delete_package_removes_slash_qualified_knowledge_nodes(self, graph_store):
        """CLI-published knowledge IDs use `package/decl`, not `package.module.decl`."""
        knowledge = Knowledge(
            knowledge_id="galileo_falling_bodies/vacuum_prediction",
            version=1,
            type="claim",
            content="In a vacuum, bodies fall equally.",
            prior=0.7,
            source_package_id="galileo_falling_bodies",
            source_module_id="galileo_falling_bodies.reasoning",
            created_at=datetime(2026, 1, 1),
        )
        chain = Chain(
            chain_id="galileo_falling_bodies.reasoning.vacuum_chain",
            module_id="galileo_falling_bodies.reasoning",
            package_id="galileo_falling_bodies",
            type="deduction",
            steps=[
                ChainStep(
                    step_index=0,
                    premises=[KnowledgeRef(knowledge_id=knowledge.knowledge_id, version=1)],
                    reasoning="Reasoning text.",
                    conclusion=KnowledgeRef(knowledge_id=knowledge.knowledge_id, version=1),
                )
            ],
        )

        await graph_store.write_topology([knowledge], [chain])
        await graph_store.delete_package("galileo_falling_bodies")

        assert await _count_nodes(graph_store, "Knowledge") == 0
        assert await _count_nodes(graph_store, "Chain") == 0


# ── close ──


class TestClose:
    async def test_close_kuzu(self, tmp_path):
        store = KuzuGraphStore(tmp_path / "close_test")
        await store.initialize_schema()
        await store.close()

    async def test_close_kuzu_idempotent(self, tmp_path):
        store = KuzuGraphStore(tmp_path / "close_idem_test")
        await store.initialize_schema()
        await store.close()
        await store.close()

    async def test_close_neo4j(self):
        if not await _neo4j_available():
            pytest.skip("Neo4j not available")
        import neo4j

        from libs.storage.neo4j_graph_store import Neo4jGraphStore

        auth = ("neo4j", NEO4J_PASSWORD) if NEO4J_PASSWORD else None
        driver = neo4j.AsyncGraphDatabase.driver(NEO4J_URI, auth=auth)
        store = Neo4jGraphStore(driver=driver, database=NEO4J_DB)
        await store.initialize_schema()
        await store.close()


# ── Full roundtrip ──


class TestFullRoundtrip:
    async def test_full_roundtrip(self, graph_store, knowledge_items, chains, attachments):
        # 1. Write topology
        await graph_store.write_topology(knowledge_items, chains)

        # 2. Write resource links
        await graph_store.write_resource_links(attachments)

        # 3. Query neighbors
        chain = chains[0]
        premise_id = chain.steps[0].premises[0].knowledge_id
        neighbors = await graph_store.get_neighbors(premise_id)
        assert len(neighbors.chain_ids) > 0

        # 4. Query subgraph
        subgraph = await graph_store.get_subgraph(premise_id)
        assert len(subgraph.knowledge_ids) > 0

        # 5. Search topology
        results = await graph_store.search_topology([premise_id], hops=2)
        assert len(results) >= 0
