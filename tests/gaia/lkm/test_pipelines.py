"""Tests for gaia.lkm.pipelines.run_ingest."""

import pytest

from gaia.libs.embedding import StubEmbeddingModel
from gaia.models.binding import BindingDecision
from gaia.libs.storage.config import StorageConfig
from gaia.libs.storage.manager import StorageManager
from gaia.lkm.pipelines.run_ingest import run_ingest
from tests.gaia.fixtures.graphs import make_galileo_falling_bodies, make_newton_gravity


@pytest.fixture
async def storage(tmp_path):
    config = StorageConfig(lancedb_path=str(tmp_path / "test.lance"))
    mgr = StorageManager(config)
    await mgr.initialize()
    return mgr


@pytest.fixture
def embedding_model():
    return StubEmbeddingModel(dim=64)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _ingest_galileo(storage, embedding_model):
    graph, params = make_galileo_falling_bodies()
    result = await run_ingest(
        local_graph=graph,
        local_params=params,
        package_id="galileo_falling_bodies",
        version="1.0",
        storage=storage,
        embedding_model=embedding_model,
    )
    return graph, params, result


async def _ingest_newton(storage, embedding_model):
    graph, params = make_newton_gravity()
    result = await run_ingest(
        local_graph=graph,
        local_params=params,
        package_id="newton_principia",
        version="1.0",
        storage=storage,
        embedding_model=embedding_model,
    )
    return graph, params, result


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_ingest_first_package(storage, embedding_model):
    """Ingest galileo: verify global nodes, factors, bindings, prior_records all persisted."""
    graph, params, result = await _ingest_galileo(storage, embedding_model)

    # All local nodes should get CREATE_NEW bindings (no prior global nodes)
    assert len(result.bindings) == len(graph.knowledge_nodes)
    for binding in result.bindings:
        assert binding.decision == BindingDecision.CREATE_NEW

    # New global nodes created for every local node
    assert len(result.new_global_nodes) == len(graph.knowledge_nodes)
    assert all(n.id.startswith("gcn_") for n in result.new_global_nodes)

    # Global factors lifted from local factors
    assert len(result.global_factors) == len(graph.factor_nodes)

    # Prior records created for claim nodes (not setting)
    claim_count = sum(1 for n in graph.knowledge_nodes if n.type == "claim")
    assert len(result.prior_records) == claim_count

    # Verify persistence: global nodes readable from storage
    persisted_gcn = await storage.get_knowledge_nodes(prefix="gcn_")
    assert len(persisted_gcn) == len(result.new_global_nodes)

    # Verify persistence: bindings readable
    persisted_bindings = await storage.get_bindings(package_id="galileo_falling_bodies")
    assert len(persisted_bindings) == len(result.bindings)

    # Verify persistence: prior records readable
    persisted_priors = await storage.get_prior_records()
    assert len(persisted_priors) == len(result.prior_records)

    # Verify persistence: factor param records readable
    persisted_fparams = await storage.get_factor_param_records()
    assert len(persisted_fparams) == len(result.factor_param_records)


async def test_ingest_persists_local_nodes(storage, embedding_model):
    """After ingest, local lcn_ nodes are retrievable from storage."""
    graph, _params, _result = await _ingest_galileo(storage, embedding_model)

    local_nodes = await storage.get_knowledge_nodes(prefix="lcn_")
    assert len(local_nodes) == len(graph.knowledge_nodes)

    local_factors = await storage.get_factor_nodes(scope="local")
    assert len(local_factors) == len(graph.factor_nodes)


async def test_ingest_second_package(storage, embedding_model):
    """Ingest galileo then newton: newton has some matches, more global nodes created."""
    # First package
    _g_graph, _g_params, g_result = await _ingest_galileo(storage, embedding_model)
    gcn_count_after_galileo = len(g_result.new_global_nodes)

    # Second package
    n_graph, _n_params, n_result = await _ingest_newton(storage, embedding_model)

    # Newton should have bindings for all its local nodes
    assert len(n_result.bindings) == len(n_graph.knowledge_nodes)

    # At least some new global nodes should be created
    assert len(n_result.new_global_nodes) > 0

    # Total global nodes should have grown
    all_gcn = await storage.get_knowledge_nodes(prefix="gcn_")
    assert len(all_gcn) > gcn_count_after_galileo

    # Newton bindings should be retrievable
    newton_bindings = await storage.get_bindings(package_id="newton_principia")
    assert len(newton_bindings) == len(n_result.bindings)


async def test_ingest_result_structure(storage, embedding_model):
    """Verify CanonicalizationResult fields are populated correctly."""
    _graph, _params, result = await _ingest_galileo(storage, embedding_model)

    # param_source should be set
    assert result.param_source is not None
    assert result.param_source.source_id == "canonicalize:galileo_falling_bodies:1.0"
    assert result.param_source.model == "canonicalize"

    # bindings should have correct package info
    for binding in result.bindings:
        assert binding.package_id == "galileo_falling_bodies"
        assert binding.version == "1.0"
        assert binding.local_canonical_id.startswith("lcn_")
        assert binding.global_canonical_id.startswith("gcn_")

    # new_global_nodes should have provenance
    for node in result.new_global_nodes:
        assert node.provenance is not None
        assert len(node.provenance) == 1
        assert node.provenance[0].package_id == "galileo_falling_bodies"

    # No unresolved cross-refs for a self-contained graph
    assert result.unresolved_cross_refs == []
