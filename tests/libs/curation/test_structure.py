"""Tests for graph structure inspection."""

from libs.curation.structure import inspect_structure
from libs.global_graph.models import GlobalCanonicalNode
from libs.storage.models import FactorNode


def _make_nodes(*ids: str) -> list[GlobalCanonicalNode]:
    return [
        GlobalCanonicalNode(
            global_canonical_id=gid,
            knowledge_type="claim",
            representative_content=f"Content of {gid}",
        )
        for gid in ids
    ]


def test_orphan_node_detected():
    """Node with no factor connections is flagged as orphan."""
    nodes = _make_nodes("gcn_a", "gcn_b", "gcn_orphan")
    factors = [
        FactorNode(
            factor_id="f_1",
            type="reasoning",
            premises=["gcn_a"],
            conclusion="gcn_b",
            package_id="pkg1",
        )
    ]
    report = inspect_structure(nodes, factors)
    orphan_issues = [i for i in report.issues if i.issue_type == "orphan_node"]
    assert len(orphan_issues) == 1
    assert "gcn_orphan" in orphan_issues[0].node_ids


def test_dangling_factor_detected():
    """Factor referencing non-existent node is flagged."""
    nodes = _make_nodes("gcn_a")
    factors = [
        FactorNode(
            factor_id="f_1",
            type="reasoning",
            premises=["gcn_a"],
            conclusion="gcn_deleted",  # does not exist
            package_id="pkg1",
        )
    ]
    report = inspect_structure(nodes, factors)
    dangling = [i for i in report.issues if i.issue_type == "dangling_factor"]
    assert len(dangling) == 1
    assert dangling[0].severity == "error"
    assert "f_1" in dangling[0].factor_ids


def test_high_degree_detected():
    """Node participating in many factors is flagged as high-degree."""
    nodes = _make_nodes("gcn_hub", "gcn_1", "gcn_2", "gcn_3", "gcn_4", "gcn_5")
    factors = [
        FactorNode(
            factor_id=f"f_{i}",
            type="reasoning",
            premises=["gcn_hub"],
            conclusion=f"gcn_{i}",
            package_id="pkg1",
        )
        for i in range(1, 6)
    ]
    report = inspect_structure(nodes, factors, high_degree_threshold=4)
    high_deg = [i for i in report.issues if i.issue_type == "high_degree"]
    assert len(high_deg) == 1
    assert "gcn_hub" in high_deg[0].node_ids


def test_clean_graph_no_issues():
    """Well-formed graph has no error/warning issues."""
    nodes = _make_nodes("gcn_a", "gcn_b")
    factors = [
        FactorNode(
            factor_id="f_1",
            type="reasoning",
            premises=["gcn_a"],
            conclusion="gcn_b",
            package_id="pkg1",
        )
    ]
    report = inspect_structure(nodes, factors)
    assert len(report.errors) == 0
    assert len(report.warnings) == 0


def test_empty_graph():
    """Empty graph produces no issues."""
    report = inspect_structure([], [])
    assert report.issues == []


def test_disconnected_components():
    """Two separate subgraphs should be flagged as disconnected."""
    nodes = _make_nodes("gcn_a", "gcn_b", "gcn_c", "gcn_d")
    factors = [
        FactorNode(
            factor_id="f_1",
            type="reasoning",
            premises=["gcn_a"],
            conclusion="gcn_b",
            package_id="pkg1",
        ),
        FactorNode(
            factor_id="f_2",
            type="reasoning",
            premises=["gcn_c"],
            conclusion="gcn_d",
            package_id="pkg1",
        ),
    ]
    report = inspect_structure(nodes, factors)
    disconnected = [i for i in report.issues if i.issue_type == "disconnected_component"]
    assert len(disconnected) == 1
    assert disconnected[0].severity == "info"
