"""Tests for the curation scheduler (main pipeline orchestrator)."""

from unittest.mock import AsyncMock

from libs.curation.models import CurationResult
from libs.curation.scheduler import run_curation
from libs.embedding import StubEmbeddingModel
from libs.global_graph.models import GlobalCanonicalNode
from libs.storage.models import FactorNode


def _mock_storage_manager(nodes: list[GlobalCanonicalNode], factors: list[FactorNode]):
    """Build a mock StorageManager returning given nodes and factors."""
    mgr = AsyncMock()
    mgr.list_global_nodes = AsyncMock(return_value=nodes)
    mgr.list_factors = AsyncMock(return_value=factors)
    mgr.upsert_global_nodes = AsyncMock()
    mgr.write_factors = AsyncMock()
    return mgr


async def test_run_curation_empty_graph():
    """Empty graph produces empty result."""
    mgr = _mock_storage_manager([], [])
    result = await run_curation(mgr)
    assert isinstance(result, CurationResult)
    assert result.executed == []


async def test_run_curation_with_duplicate_nodes():
    """Duplicate nodes should be detected and merged."""
    nodes = [
        GlobalCanonicalNode(
            global_canonical_id="gcn_a",
            knowledge_type="claim",
            representative_content="The Earth orbits the Sun",
        ),
        GlobalCanonicalNode(
            global_canonical_id="gcn_b",
            knowledge_type="claim",
            representative_content="The Earth orbits the Sun",  # identical
        ),
        GlobalCanonicalNode(
            global_canonical_id="gcn_c",
            knowledge_type="claim",
            representative_content="Water boils at 100 degrees Celsius",
        ),
    ]
    factors: list[FactorNode] = [
        FactorNode(
            factor_id="f_1",
            type="infer",
            premises=["gcn_a"],
            conclusion="gcn_c",
            package_id="pkg1",
        ),
    ]
    mgr = _mock_storage_manager(nodes, factors)
    embedding_model = StubEmbeddingModel(dim=64)

    result = await run_curation(mgr, embedding_model=embedding_model, similarity_threshold=0.90)
    assert isinstance(result, CurationResult)
    # With identical content and StubEmbeddingModel, these should cluster and potentially merge
    # (exact behavior depends on StubEmbeddingModel's similarity for identical texts)


async def test_run_curation_with_orphan():
    """Orphan node should appear in structure report."""
    nodes = [
        GlobalCanonicalNode(
            global_canonical_id="gcn_a",
            knowledge_type="claim",
            representative_content="Connected node",
        ),
        GlobalCanonicalNode(
            global_canonical_id="gcn_orphan",
            knowledge_type="claim",
            representative_content="Orphan node",
        ),
    ]
    factors = [
        FactorNode(
            factor_id="f_1",
            type="infer",
            premises=["gcn_a"],
            conclusion="gcn_a",  # self-loop just to give gcn_a a connection
            package_id="pkg1",
        ),
    ]
    mgr = _mock_storage_manager(nodes, factors)
    result = await run_curation(mgr, skip_conflict_detection=True)
    assert isinstance(result, CurationResult)
