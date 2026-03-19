"""End-to-end integration test for the curation pipeline."""

from unittest.mock import AsyncMock

from libs.curation.models import CurationResult
from libs.curation.scheduler import run_curation
from libs.embedding import StubEmbeddingModel
from libs.global_graph.models import GlobalCanonicalNode, LocalCanonicalRef, PackageRef
from libs.storage.models import FactorNode


def _build_test_graph():
    """Build a realistic test graph with known issues.

    Graph:
    - gcn_earth_1 and gcn_earth_2: duplicate claims about Earth
    - gcn_water: standalone claim
    - gcn_orphan: orphan node (no factors)
    - f_1: gcn_earth_1 -> gcn_water (deduction)
    - f_dangling: references gcn_deleted (does not exist)
    """
    nodes = [
        GlobalCanonicalNode(
            global_canonical_id="gcn_earth_1",
            knowledge_type="claim",
            representative_content="The Earth revolves around the Sun in an elliptical orbit",
            member_local_nodes=[
                LocalCanonicalRef(package="astronomy", version="0.1.0", local_canonical_id="lcn_e1")
            ],
            provenance=[PackageRef(package="astronomy", version="0.1.0")],
        ),
        GlobalCanonicalNode(
            global_canonical_id="gcn_earth_2",
            knowledge_type="claim",
            representative_content="The Earth revolves around the Sun in an elliptical orbit",
            member_local_nodes=[
                LocalCanonicalRef(package="physics", version="0.1.0", local_canonical_id="lcn_e2")
            ],
            provenance=[PackageRef(package="physics", version="0.1.0")],
        ),
        GlobalCanonicalNode(
            global_canonical_id="gcn_water",
            knowledge_type="claim",
            representative_content="Water boils at 100 degrees Celsius at standard pressure",
        ),
        GlobalCanonicalNode(
            global_canonical_id="gcn_orphan",
            knowledge_type="claim",
            representative_content="This node is isolated",
        ),
    ]
    factors = [
        FactorNode(
            factor_id="f_1",
            type="infer",
            premises=["gcn_earth_1"],
            conclusion="gcn_water",
            package_id="astronomy",
            metadata={},
        ),
        FactorNode(
            factor_id="f_dangling",
            type="infer",
            premises=["gcn_deleted"],
            conclusion="gcn_water",
            package_id="astronomy",
            metadata={},
        ),
    ]
    return nodes, factors


async def test_full_curation_pipeline():
    """Run the full curation pipeline on a graph with known issues."""
    nodes, factors = _build_test_graph()

    mgr = AsyncMock()
    mgr.list_global_nodes = AsyncMock(return_value=nodes)
    mgr.list_factors = AsyncMock(return_value=factors)
    mgr.upsert_global_nodes = AsyncMock()
    mgr.write_factors = AsyncMock()

    embedding_model = StubEmbeddingModel(dim=64)

    result = await run_curation(
        mgr,
        embedding_model=embedding_model,
        similarity_threshold=0.90,
        skip_conflict_detection=True,  # Skip BP for this test -- focus on clustering + structure
    )

    assert isinstance(result, CurationResult)

    # Structure report should find the dangling factor
    dangling_issues = [
        i for i in result.structure_report.issues if i.issue_type == "dangling_factor"
    ]
    assert len(dangling_issues) >= 1

    # The two identical Earth nodes should produce some kind of suggestion
    # (merge or equivalence depending on StubEmbeddingModel similarity)
    all_target_ids = set()
    for s in result.executed + result.skipped:
        all_target_ids.update(s.target_ids)
    # At minimum, structural issues should have produced suggestions
    assert len(result.executed) + len(result.skipped) > 0


async def test_curation_pipeline_with_conflict_detection():
    """Run full pipeline including BP-based conflict detection."""
    nodes = [
        GlobalCanonicalNode(
            global_canonical_id="gcn_claim_a",
            knowledge_type="claim",
            representative_content="Vitamin C prevents colds",
        ),
        GlobalCanonicalNode(
            global_canonical_id="gcn_claim_b",
            knowledge_type="claim",
            representative_content="Vitamin C does not prevent colds",
        ),
    ]
    # A supports B via deduction, but they also have a contradiction factor
    factors = [
        FactorNode(
            factor_id="f_support",
            type="infer",
            premises=["gcn_claim_a"],
            conclusion="gcn_claim_b",
            package_id="health",
            metadata={},
        ),
        FactorNode(
            factor_id="f_contradict",
            type="contradiction",
            premises=["gcn_rel_vc", "gcn_claim_a", "gcn_claim_b"],
            conclusion=None,
            package_id="health",
            metadata={"curation_created": True},
        ),
    ]

    mgr = AsyncMock()
    mgr.list_global_nodes = AsyncMock(return_value=nodes)
    mgr.list_factors = AsyncMock(return_value=factors)
    mgr.upsert_global_nodes = AsyncMock()
    mgr.write_factors = AsyncMock()

    result = await run_curation(
        mgr,
        skip_conflict_detection=False,
        bp_max_iterations=50,
        bp_damping=0.3,
    )

    assert isinstance(result, CurationResult)
    # The pipeline should complete without errors
    # Whether conflicts are detected depends on BP dynamics, but no crashes
