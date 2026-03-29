"""Tests for global BP parameter assembly and execution."""

import pytest
from datetime import datetime, timezone

from gaia.core.global_bp import assemble_parameterization, run_global_bp
from gaia.core.canonicalize import canonicalize_package
from gaia.models import GlobalCanonicalGraph, KnowledgeNode, KnowledgeType, BeliefState
from gaia.models.parameterization import (
    PriorRecord,
    ResolutionPolicy,
    CROMWELL_EPS,
)
from gaia.libs.embedding import StubEmbeddingModel
from tests.gaia.fixtures.graphs import make_galileo_falling_bodies, make_minimal_claim_pair
from tests.gaia.fixtures.parameterizations import make_default_local_params


@pytest.fixture
def embedding_model():
    return StubEmbeddingModel(dim=64)


# ---------------------------------------------------------------------------
# assemble_parameterization tests
# ---------------------------------------------------------------------------


class TestAssembleParameterization:
    def test_latest_picks_newest(self):
        """Two PriorRecords for same gcn_id with different created_at -> picks newest."""
        t1 = datetime(2025, 1, 1, tzinfo=timezone.utc)
        t2 = datetime(2025, 6, 1, tzinfo=timezone.utc)

        records = [
            PriorRecord(gcn_id="gcn_abc", value=0.3, source_id="s1", created_at=t1),
            PriorRecord(gcn_id="gcn_abc", value=0.8, source_id="s2", created_at=t2),
        ]
        policy = ResolutionPolicy(strategy="latest")

        result = assemble_parameterization(records, [], policy)
        assert result["node_priors"]["gcn_abc"] == pytest.approx(0.8, abs=1e-6)

    def test_source_policy_filters(self):
        """Two records from different sources -> source policy picks correct one."""
        t1 = datetime(2025, 1, 1, tzinfo=timezone.utc)
        records = [
            PriorRecord(gcn_id="gcn_abc", value=0.3, source_id="s1", created_at=t1),
            PriorRecord(gcn_id="gcn_abc", value=0.8, source_id="s2", created_at=t1),
        ]
        policy = ResolutionPolicy(strategy="source", source_id="s1")

        result = assemble_parameterization(records, [], policy)
        assert result["node_priors"]["gcn_abc"] == pytest.approx(0.3, abs=1e-6)

    def test_prior_cutoff_filters(self):
        """Record after cutoff is excluded."""
        t1 = datetime(2025, 1, 1, tzinfo=timezone.utc)
        t2 = datetime(2025, 6, 1, tzinfo=timezone.utc)
        cutoff = datetime(2025, 3, 1, tzinfo=timezone.utc)

        records = [
            PriorRecord(gcn_id="gcn_abc", value=0.3, source_id="s1", created_at=t1),
            PriorRecord(gcn_id="gcn_abc", value=0.8, source_id="s1", created_at=t2),
        ]
        policy = ResolutionPolicy(strategy="latest", prior_cutoff=cutoff)

        result = assemble_parameterization(records, [], policy)
        assert result["node_priors"]["gcn_abc"] == pytest.approx(0.3, abs=1e-6)

    def test_empty_records(self):
        """Empty input -> empty output."""
        policy = ResolutionPolicy(strategy="latest")
        result = assemble_parameterization([], [], policy)
        assert result["node_priors"] == {}
        assert result["factor_params"] == {}


# ---------------------------------------------------------------------------
# run_global_bp tests
# ---------------------------------------------------------------------------


async def _canonicalize_to_global(local_graph, local_params, embedding_model):
    """Helper: canonicalize a local graph into a global graph with params."""
    empty_global = GlobalCanonicalGraph(knowledge_nodes=[], factor_nodes=[])
    result = await canonicalize_package(
        local_graph=local_graph,
        local_params=local_params,
        global_graph=empty_global,
        package_id="test_pkg",
        version="1.0",
        embedding_model=embedding_model,
    )
    global_graph = GlobalCanonicalGraph(
        knowledge_nodes=result.new_global_nodes,
        factor_nodes=result.global_factors,
    )
    return global_graph, result.prior_records, result.factor_param_records


class TestRunGlobalBP:
    async def test_minimal_graph_produces_belief_state(self, embedding_model):
        """Canonicalize minimal_claim_pair -> run BP -> get valid BeliefState."""
        local_graph = make_minimal_claim_pair()
        local_params = make_default_local_params(local_graph)
        global_graph, priors, factor_params = await _canonicalize_to_global(
            local_graph, local_params, embedding_model
        )
        policy = ResolutionPolicy(strategy="latest")

        belief_state = await run_global_bp(
            global_graph=global_graph,
            prior_records=priors,
            factor_records=factor_params,
            policy=policy,
        )

        assert isinstance(belief_state, BeliefState)
        assert belief_state.converged is True
        assert len(belief_state.beliefs) > 0
        assert belief_state.iterations >= 1

    async def test_beliefs_only_for_claims(self, embedding_model):
        """Galileo graph has a setting node -> it should NOT appear in beliefs."""
        local_graph, local_params = make_galileo_falling_bodies()
        global_graph, priors, factor_params = await _canonicalize_to_global(
            local_graph, local_params, embedding_model
        )
        policy = ResolutionPolicy(strategy="latest")

        belief_state = await run_global_bp(
            global_graph=global_graph,
            prior_records=priors,
            factor_records=factor_params,
            policy=policy,
        )

        # All galileo nodes are claims — beliefs should exist for all of them.
        claim_gcn_ids = {
            n.id for n in global_graph.knowledge_nodes if n.type == KnowledgeType.CLAIM
        }
        for gcn_id in belief_state.beliefs:
            assert gcn_id in claim_gcn_ids, f"Non-claim node {gcn_id} should not be in beliefs"

        # Also verify: add a setting node to global graph and confirm it has no belief.
        # (Setting nodes don't participate in BP.)
        setting_node = KnowledgeNode(
            id="gcn_setting_test",
            type=KnowledgeType.SETTING,
            content="Background context — not a claim",
            source_refs=[],
        )
        global_graph.knowledge_nodes.append(setting_node)
        belief_state2 = await run_global_bp(
            global_graph=global_graph,
            prior_records=priors,
            factor_records=factor_params,
            policy=policy,
        )
        assert "gcn_setting_test" not in belief_state2.beliefs

    async def test_belief_values_in_cromwell_bounds(self, embedding_model):
        """All beliefs between EPS and 1-EPS."""
        local_graph = make_minimal_claim_pair()
        local_params = make_default_local_params(local_graph)
        global_graph, priors, factor_params = await _canonicalize_to_global(
            local_graph, local_params, embedding_model
        )
        policy = ResolutionPolicy(strategy="latest")

        belief_state = await run_global_bp(
            global_graph=global_graph,
            prior_records=priors,
            factor_records=factor_params,
            policy=policy,
        )

        for gcn_id, belief in belief_state.beliefs.items():
            assert CROMWELL_EPS <= belief <= 1 - CROMWELL_EPS, (
                f"Belief for {gcn_id} = {belief} is outside Cromwell bounds"
            )

    async def test_galileo_graph_with_contradiction(self, embedding_model):
        """Galileo has contradiction -> BP should still converge, beliefs should be valid."""
        local_graph, local_params = make_galileo_falling_bodies()
        global_graph, priors, factor_params = await _canonicalize_to_global(
            local_graph, local_params, embedding_model
        )
        policy = ResolutionPolicy(strategy="latest")

        belief_state = await run_global_bp(
            global_graph=global_graph,
            prior_records=priors,
            factor_records=factor_params,
            policy=policy,
        )

        assert belief_state.converged is True
        assert len(belief_state.beliefs) > 0
        for gcn_id, belief in belief_state.beliefs.items():
            assert CROMWELL_EPS <= belief <= 1 - CROMWELL_EPS
