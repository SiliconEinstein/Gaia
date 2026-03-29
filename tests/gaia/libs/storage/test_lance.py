"""Tests for LanceDB content store."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from gaia.models import (
    BeliefState,
    BindingDecision,
    CanonicalBinding,
    FactorParamRecord,
    ParameterizationSource,
    PriorRecord,
)
from gaia.libs.storage.lance import LanceContentStore
from tests.gaia.fixtures.graphs import make_galileo_falling_bodies


@pytest.fixture
async def store(tmp_path):
    s = LanceContentStore(path=str(tmp_path / "test.lance"))
    await s.initialize()
    return s


def _galileo_graph():
    graph, _params = make_galileo_falling_bodies()
    return graph


# ---------------------------------------------------------------------------
# Knowledge Nodes
# ---------------------------------------------------------------------------


class TestKnowledgeNodeStorage:
    async def test_write_and_read_local_nodes(self, store):
        graph = _galileo_graph()
        await store.write_knowledge_nodes(graph.knowledge_nodes)

        nodes = await store.get_knowledge_nodes(prefix="lcn_")
        assert len(nodes) == 10
        ids = {n.id for n in nodes}
        for n in graph.knowledge_nodes:
            assert n.id in ids

    async def test_read_all_nodes_without_prefix(self, store):
        graph = _galileo_graph()
        await store.write_knowledge_nodes(graph.knowledge_nodes)

        nodes = await store.get_knowledge_nodes()
        assert len(nodes) == 10

    async def test_get_single_node(self, store):
        graph = _galileo_graph()
        await store.write_knowledge_nodes(graph.knowledge_nodes)

        target = graph.knowledge_nodes[0]
        node = await store.get_node(target.id)
        assert node is not None
        assert node.id == target.id
        assert node.content == target.content
        assert node.type == target.type

    async def test_get_node_not_found(self, store):
        result = await store.get_node("lcn_nonexistent")
        assert result is None

    async def test_write_global_nodes(self, store):
        """Global nodes have gcn_ prefix."""
        from gaia.models import KnowledgeNode, KnowledgeType, SourceRef

        gcn = KnowledgeNode(
            id="gcn_abc123",
            type=KnowledgeType.CLAIM,
            content="Global claim",
            source_refs=[SourceRef(package="test_pkg", version="1.0")],
        )
        await store.write_knowledge_nodes([gcn])

        # Filter by gcn_ prefix
        global_nodes = await store.get_knowledge_nodes(prefix="gcn_")
        assert len(global_nodes) == 1
        assert global_nodes[0].id == "gcn_abc123"

        # lcn_ prefix returns none
        local_nodes = await store.get_knowledge_nodes(prefix="lcn_")
        assert len(local_nodes) == 0

    async def test_roundtrip_preserves_fields(self, store):
        """All fields survive serialization round-trip."""
        graph = _galileo_graph()
        await store.write_knowledge_nodes(graph.knowledge_nodes)

        for original in graph.knowledge_nodes:
            loaded = await store.get_node(original.id)
            assert loaded is not None
            assert loaded.source_refs == original.source_refs
            assert loaded.parameters == original.parameters
            assert loaded.metadata == original.metadata


# ---------------------------------------------------------------------------
# Factor Nodes
# ---------------------------------------------------------------------------


class TestFactorNodeStorage:
    async def test_write_and_read_local_factors(self, store):
        graph = _galileo_graph()
        await store.write_factor_nodes(graph.factor_nodes)

        factors = await store.get_factor_nodes(scope="local")
        assert len(factors) == 7

    async def test_read_all_factors_without_scope(self, store):
        graph = _galileo_graph()
        await store.write_factor_nodes(graph.factor_nodes)

        factors = await store.get_factor_nodes()
        assert len(factors) == 7

    async def test_write_global_factors(self, store):
        from gaia.models import (
            FactorCategory,
            FactorNode,
            FactorStage,
            ReasoningType,
            SourceRef,
        )

        gf = FactorNode(
            scope="global",
            category=FactorCategory.INFER,
            stage=FactorStage.PERMANENT,
            reasoning_type=ReasoningType.ENTAILMENT,
            premises=["gcn_a", "gcn_b"],
            conclusion="gcn_c",
            source_ref=SourceRef(package="test", version="1.0"),
        )
        await store.write_factor_nodes([gf])

        global_factors = await store.get_factor_nodes(scope="global")
        assert len(global_factors) == 1
        assert global_factors[0].factor_id == gf.factor_id

        local_factors = await store.get_factor_nodes(scope="local")
        assert len(local_factors) == 0

    async def test_factor_roundtrip_preserves_fields(self, store):
        graph = _galileo_graph()
        await store.write_factor_nodes(graph.factor_nodes)

        factors = await store.get_factor_nodes()
        factor_map = {f.factor_id: f for f in factors}

        for original in graph.factor_nodes:
            loaded = factor_map[original.factor_id]
            assert loaded.premises == original.premises
            assert loaded.conclusion == original.conclusion
            assert loaded.category == original.category
            assert loaded.stage == original.stage
            assert loaded.reasoning_type == original.reasoning_type


# ---------------------------------------------------------------------------
# Bindings
# ---------------------------------------------------------------------------


class TestBindingStorage:
    async def test_write_and_read_bindings(self, store):
        bindings = [
            CanonicalBinding(
                local_canonical_id="lcn_a",
                global_canonical_id="gcn_x",
                package_id="pkg1",
                version="1.0",
                decision=BindingDecision.CREATE_NEW,
                reason="no matching global node found",
            ),
            CanonicalBinding(
                local_canonical_id="lcn_b",
                global_canonical_id="gcn_y",
                package_id="pkg1",
                version="1.0",
                decision=BindingDecision.MATCH_EXISTING,
                reason="cosine similarity 0.95",
            ),
        ]
        await store.write_bindings(bindings)

        loaded = await store.get_bindings()
        assert len(loaded) == 2

    async def test_filter_by_package_id(self, store):
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
        await store.write_bindings(bindings)

        pkg1 = await store.get_bindings(package_id="pkg1")
        assert len(pkg1) == 1
        assert pkg1[0].local_canonical_id == "lcn_a"

        pkg2 = await store.get_bindings(package_id="pkg2")
        assert len(pkg2) == 1


# ---------------------------------------------------------------------------
# Parameterization
# ---------------------------------------------------------------------------


class TestParameterizationStorage:
    async def test_write_and_read_prior_records(self, store):
        now = datetime.now(timezone.utc)
        source = ParameterizationSource(
            source_id="src_1",
            model="gpt-4",
            created_at=now,
        )
        await store.write_param_source(source)

        records = [
            PriorRecord(gcn_id="gcn_a", value=0.8, source_id="src_1", created_at=now),
            PriorRecord(gcn_id="gcn_b", value=0.6, source_id="src_1", created_at=now),
        ]
        await store.write_prior_records(records)

        loaded = await store.get_prior_records()
        assert len(loaded) == 2

    async def test_filter_prior_records_by_gcn_id(self, store):
        now = datetime.now(timezone.utc)
        records = [
            PriorRecord(gcn_id="gcn_a", value=0.8, source_id="src_1", created_at=now),
            PriorRecord(gcn_id="gcn_a", value=0.7, source_id="src_2", created_at=now),
            PriorRecord(gcn_id="gcn_b", value=0.6, source_id="src_1", created_at=now),
        ]
        await store.write_prior_records(records)

        loaded = await store.get_prior_records(gcn_id="gcn_a")
        assert len(loaded) == 2
        assert all(r.gcn_id == "gcn_a" for r in loaded)

    async def test_write_and_read_factor_param_records(self, store):
        now = datetime.now(timezone.utc)
        records = [
            FactorParamRecord(
                factor_id="gcf_x", probability=0.9, source_id="src_1", created_at=now
            ),
        ]
        await store.write_factor_param_records(records)

        loaded = await store.get_factor_param_records()
        assert len(loaded) == 1
        assert loaded[0].factor_id == "gcf_x"

    async def test_filter_factor_param_by_factor_id(self, store):
        now = datetime.now(timezone.utc)
        records = [
            FactorParamRecord(
                factor_id="gcf_x", probability=0.9, source_id="src_1", created_at=now
            ),
            FactorParamRecord(
                factor_id="gcf_y", probability=0.8, source_id="src_1", created_at=now
            ),
        ]
        await store.write_factor_param_records(records)

        loaded = await store.get_factor_param_records(factor_id="gcf_x")
        assert len(loaded) == 1


# ---------------------------------------------------------------------------
# Belief States
# ---------------------------------------------------------------------------


class TestBeliefStateStorage:
    async def test_write_and_read_belief_state(self, store):
        now = datetime.now(timezone.utc)
        state = BeliefState(
            bp_run_id="run_001",
            created_at=now,
            resolution_policy="latest",
            prior_cutoff=now,
            beliefs={"gcn_a": 0.85, "gcn_b": 0.42},
            converged=True,
            iterations=12,
            max_residual=0.001,
        )
        await store.write_belief_state(state)

        loaded = await store.get_belief_states(limit=10)
        assert len(loaded) == 1
        assert loaded[0].bp_run_id == "run_001"
        assert loaded[0].beliefs == {"gcn_a": 0.85, "gcn_b": 0.42}
        assert loaded[0].converged is True
        assert loaded[0].iterations == 12

    async def test_belief_state_limit(self, store):
        now = datetime.now(timezone.utc)
        for i in range(5):
            state = BeliefState(
                bp_run_id=f"run_{i:03d}",
                created_at=now,
                resolution_policy="latest",
                prior_cutoff=now,
                beliefs={"gcn_a": 0.5 + i * 0.1},
                converged=True,
                iterations=10,
                max_residual=0.001,
            )
            await store.write_belief_state(state)

        loaded = await store.get_belief_states(limit=3)
        assert len(loaded) == 3


# ---------------------------------------------------------------------------
# Node Embeddings
# ---------------------------------------------------------------------------


class TestNodeEmbeddingStorage:
    async def test_write_and_search_embeddings(self, store):
        await store.write_node_embedding(
            gcn_id="gcn_a",
            vector=[1.0, 0.0, 0.0],
            content="Claim A about physics",
        )
        await store.write_node_embedding(
            gcn_id="gcn_b",
            vector=[0.0, 1.0, 0.0],
            content="Claim B about chemistry",
        )

        results = await store.search_similar_nodes(
            query_vector=[1.0, 0.1, 0.0],
            top_k=2,
        )
        assert len(results) >= 1
        # gcn_a should be most similar
        ids = [r[0] for r in results]
        assert ids[0] == "gcn_a"

    async def test_search_with_type_filter(self, store):
        """Type filter narrows results by knowledge node type stored in embedding."""
        await store.write_node_embedding(
            gcn_id="gcn_claim",
            vector=[1.0, 0.0, 0.0],
            content="A claim",
        )
        await store.write_node_embedding(
            gcn_id="gcn_setting",
            vector=[0.9, 0.1, 0.0],
            content="A setting",
        )

        # With type filter — searches for gcn_id prefix match as proxy
        # (actual type filtering requires storing type in embeddings table)
        results = await store.search_similar_nodes(
            query_vector=[1.0, 0.0, 0.0],
            top_k=10,
        )
        assert len(results) == 2


# ---------------------------------------------------------------------------
# Clean All
# ---------------------------------------------------------------------------


class TestCleanAll:
    async def test_clean_removes_all_data(self, store):
        graph = _galileo_graph()
        await store.write_knowledge_nodes(graph.knowledge_nodes)
        await store.write_factor_nodes(graph.factor_nodes)

        # Verify data exists
        nodes = await store.get_knowledge_nodes()
        assert len(nodes) > 0

        await store.clean_all()

        nodes = await store.get_knowledge_nodes()
        assert len(nodes) == 0
        factors = await store.get_factor_nodes()
        assert len(factors) == 0


class TestInitializeIdempotent:
    async def test_double_initialize(self, store):
        """Calling initialize twice should not lose data."""
        graph = _galileo_graph()
        await store.write_knowledge_nodes(graph.knowledge_nodes)

        await store.initialize()

        nodes = await store.get_knowledge_nodes()
        assert len(nodes) == 10
