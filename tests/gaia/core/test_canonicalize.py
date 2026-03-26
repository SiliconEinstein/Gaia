"""Tests for gaia.core.canonicalize — global canonicalization."""

import pytest

from gaia.core.canonicalize import CanonicalizationResult, canonicalize_package
from gaia.libs.embedding import StubEmbeddingModel
from gaia.libs.models import (
    FactorNode,
    GlobalCanonicalGraph,
    KnowledgeNode,
    KnowledgeType,
    LocalCanonicalGraph,
    SourceRef,
)
from gaia.libs.models.binding import BindingDecision
from tests.gaia.fixtures.graphs import (
    make_einstein_equivalence,
    make_galileo_falling_bodies,
    make_minimal_claim_pair,
    make_newton_gravity,
)
from tests.gaia.fixtures.parameterizations import make_default_local_params


@pytest.fixture
def embedding_model():
    return StubEmbeddingModel(dim=64)


@pytest.fixture
def empty_global_graph():
    return GlobalCanonicalGraph(knowledge_nodes=[], factor_nodes=[])


# ---------------------------------------------------------------------------
# 1. First package — all create_new
# ---------------------------------------------------------------------------


async def test_first_package_all_create_new(embedding_model, empty_global_graph):
    """Empty global graph → all bindings are create_new."""
    local = make_galileo_falling_bodies()
    params = make_default_local_params(local)

    result = await canonicalize_package(
        local_graph=local,
        local_params=params,
        global_graph=empty_global_graph,
        package_id="galileo_falling_bodies",
        version="1.0",
        embedding_model=embedding_model,
    )

    assert isinstance(result, CanonicalizationResult)
    assert len(result.bindings) == len(local.knowledge_nodes)
    assert all(b.decision == BindingDecision.CREATE_NEW for b in result.bindings)
    assert len(result.new_global_nodes) == len(local.knowledge_nodes)
    assert len(result.matched_global_nodes) == 0
    # Global factors created for each local factor
    assert len(result.global_factors) == len(local.factor_nodes)
    # All global factors have gcf_ prefix
    assert all(f.factor_id.startswith("gcf_") for f in result.global_factors)


# ---------------------------------------------------------------------------
# 2. Bindings have gcn_ IDs
# ---------------------------------------------------------------------------


async def test_bindings_have_gcn_ids(embedding_model, empty_global_graph):
    """All bindings should have gcn_ global_canonical_id."""
    local = make_minimal_claim_pair()
    params = make_default_local_params(local)

    result = await canonicalize_package(
        local_graph=local,
        local_params=params,
        global_graph=empty_global_graph,
        package_id="minimal_test",
        version="1.0",
        embedding_model=embedding_model,
    )

    for binding in result.bindings:
        assert binding.global_canonical_id.startswith("gcn_"), (
            f"Expected gcn_ prefix, got {binding.global_canonical_id}"
        )
        assert binding.local_canonical_id.startswith("lcn_"), (
            f"Expected lcn_ prefix, got {binding.local_canonical_id}"
        )


# ---------------------------------------------------------------------------
# 3. PriorRecords created only for claims
# ---------------------------------------------------------------------------


async def test_prior_records_created_for_claims(embedding_model, empty_global_graph):
    """Only claim nodes get PriorRecord. Setting nodes do not."""
    local = make_galileo_falling_bodies()
    params = make_default_local_params(local)

    result = await canonicalize_package(
        local_graph=local,
        local_params=params,
        global_graph=empty_global_graph,
        package_id="galileo_falling_bodies",
        version="1.0",
        embedding_model=embedding_model,
    )

    # Galileo has 1 setting + 4 claims
    claim_count = sum(1 for n in local.knowledge_nodes if n.type == KnowledgeType.CLAIM)
    assert len(result.prior_records) == claim_count

    # All prior records reference gcn_ IDs
    for pr in result.prior_records:
        assert pr.gcn_id.startswith("gcn_")


# ---------------------------------------------------------------------------
# 4. FactorParamRecords created
# ---------------------------------------------------------------------------


async def test_factor_param_records_created(embedding_model, empty_global_graph):
    """Global factors get FactorParamRecord with values from local_params."""
    local = make_minimal_claim_pair()
    params = make_default_local_params(local, factor_prob=0.8)

    result = await canonicalize_package(
        local_graph=local,
        local_params=params,
        global_graph=empty_global_graph,
        package_id="minimal_test",
        version="1.0",
        embedding_model=embedding_model,
    )

    assert len(result.factor_param_records) >= len(result.global_factors)
    for fpr in result.factor_param_records:
        assert fpr.factor_id.startswith("gcf_")


# ---------------------------------------------------------------------------
# 5. ParameterizationSource created
# ---------------------------------------------------------------------------


async def test_param_source_created(embedding_model, empty_global_graph):
    """CanonicalizationResult has a valid ParameterizationSource."""
    local = make_minimal_claim_pair()
    params = make_default_local_params(local)

    result = await canonicalize_package(
        local_graph=local,
        local_params=params,
        global_graph=empty_global_graph,
        package_id="minimal_test",
        version="1.0",
        embedding_model=embedding_model,
    )

    assert result.param_source is not None
    assert result.param_source.source_id
    assert result.param_source.model == "canonicalize"


# ---------------------------------------------------------------------------
# 6. Global factors drop steps and weak_points
# ---------------------------------------------------------------------------


async def test_global_factors_drop_steps_and_weak_points(embedding_model, empty_global_graph):
    """All global factors have steps=None, weak_points=None."""
    # Einstein equivalence has weak_points on a factor
    local = make_einstein_equivalence()
    params = make_default_local_params(local)

    # Verify local has weak_points
    assert any(f.weak_points for f in local.factor_nodes)

    result = await canonicalize_package(
        local_graph=local,
        local_params=params,
        global_graph=empty_global_graph,
        package_id="einstein_equivalence",
        version="1.0",
        embedding_model=embedding_model,
    )

    for gf in result.global_factors:
        assert gf.steps is None, f"Global factor {gf.factor_id} should have steps=None"
        assert gf.weak_points is None, f"Global factor {gf.factor_id} should have weak_points=None"


# ---------------------------------------------------------------------------
# 7. Global factors have global scope
# ---------------------------------------------------------------------------


async def test_global_factors_have_global_scope(embedding_model, empty_global_graph):
    """All global factors have scope='global'."""
    local = make_galileo_falling_bodies()
    params = make_default_local_params(local)

    result = await canonicalize_package(
        local_graph=local,
        local_params=params,
        global_graph=empty_global_graph,
        package_id="galileo_falling_bodies",
        version="1.0",
        embedding_model=embedding_model,
    )

    for gf in result.global_factors:
        assert gf.scope == "global"


# ---------------------------------------------------------------------------
# 8. Second package cross-match
# ---------------------------------------------------------------------------


async def test_second_package_cross_match(embedding_model):
    """Canonicalize galileo, then newton. Newton's vacuum claim should match."""
    # First: canonicalize galileo into empty global graph
    galileo = make_galileo_falling_bodies()
    galileo_params = make_default_local_params(galileo)
    global_graph = GlobalCanonicalGraph(knowledge_nodes=[], factor_nodes=[])

    result1 = await canonicalize_package(
        local_graph=galileo,
        local_params=galileo_params,
        global_graph=global_graph,
        package_id="galileo_falling_bodies",
        version="1.0",
        embedding_model=embedding_model,
    )

    # Apply result to global graph
    global_graph = GlobalCanonicalGraph(
        knowledge_nodes=global_graph.knowledge_nodes + result1.new_global_nodes,
        factor_nodes=global_graph.factor_nodes + result1.global_factors,
    )

    # Second: canonicalize newton against populated global graph
    newton = make_newton_gravity()
    newton_params = make_default_local_params(newton)

    result2 = await canonicalize_package(
        local_graph=newton,
        local_params=newton_params,
        global_graph=global_graph,
        package_id="newton_principia",
        version="1.0",
        embedding_model=embedding_model,
    )

    # Newton's vacuum claim has identical content to galileo's → should match
    decisions = {b.local_canonical_id: b.decision for b in result2.bindings}

    # Find the newton vacuum node
    vacuum_node = None
    for n in newton.knowledge_nodes:
        if n.content and "vacuum" in n.content.lower() and "all objects fall" in n.content.lower():
            vacuum_node = n
            break
    assert vacuum_node is not None, "Newton's vacuum node not found"

    # It should be match_existing or equivalent_candidate (depending on role)
    decision = decisions[vacuum_node.id]
    assert decision in (BindingDecision.MATCH_EXISTING, BindingDecision.EQUIVALENT_CANDIDATE), (
        f"Expected vacuum node to match, got {decision}"
    )

    # At least one matched global node
    assert len(result2.matched_global_nodes) > 0


# ---------------------------------------------------------------------------
# 9. Factor lifting rewrites IDs
# ---------------------------------------------------------------------------


async def test_factor_lifting_rewrites_ids(embedding_model, empty_global_graph):
    """All premises/conclusions in global factors use gcn_ IDs."""
    local = make_galileo_falling_bodies()
    params = make_default_local_params(local)

    result = await canonicalize_package(
        local_graph=local,
        local_params=params,
        global_graph=empty_global_graph,
        package_id="galileo_falling_bodies",
        version="1.0",
        embedding_model=embedding_model,
    )

    for gf in result.global_factors:
        for premise_id in gf.premises:
            assert premise_id.startswith("gcn_"), (
                f"Expected gcn_ prefix in premises, got {premise_id}"
            )
        if gf.conclusion is not None:
            assert gf.conclusion.startswith("gcn_"), (
                f"Expected gcn_ prefix in conclusion, got {gf.conclusion}"
            )


# ---------------------------------------------------------------------------
# 10. All knowledge types canonicalized
# ---------------------------------------------------------------------------


async def test_all_knowledge_types_canonicalized(embedding_model, empty_global_graph):
    """Graph with setting, question, template nodes → all get bindings."""
    # Build a graph with multiple types
    nodes = [
        KnowledgeNode(
            type=KnowledgeType.SETTING,
            content="Background setting for test",
            source_refs=[SourceRef(package="multi_type", version="1.0")],
        ),
        KnowledgeNode(
            type=KnowledgeType.QUESTION,
            content="What is the answer to this test question?",
            source_refs=[SourceRef(package="multi_type", version="1.0")],
        ),
        KnowledgeNode(
            type=KnowledgeType.CLAIM,
            content="This is a test claim about science",
            source_refs=[SourceRef(package="multi_type", version="1.0")],
        ),
    ]
    factor = FactorNode(
        scope="local",
        category="infer",
        stage="initial",
        premises=[nodes[0].id, nodes[1].id],
        conclusion=nodes[2].id,
        source_ref=SourceRef(package="multi_type", version="1.0"),
    )
    local = LocalCanonicalGraph(knowledge_nodes=nodes, factor_nodes=[factor])
    params = make_default_local_params(local)

    result = await canonicalize_package(
        local_graph=local,
        local_params=params,
        global_graph=empty_global_graph,
        package_id="multi_type",
        version="1.0",
        embedding_model=embedding_model,
    )

    # All 3 nodes should have bindings
    assert len(result.bindings) == 3
    bound_types = set()
    for b in result.bindings:
        # Find the local node
        for n in local.knowledge_nodes:
            if n.id == b.local_canonical_id:
                bound_types.add(n.type)
    assert KnowledgeType.SETTING in bound_types
    assert KnowledgeType.QUESTION in bound_types
    assert KnowledgeType.CLAIM in bound_types
