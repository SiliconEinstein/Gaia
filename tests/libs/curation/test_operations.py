"""Tests for curation graph operations."""

from libs.curation.operations import create_constraint, merge_nodes
from libs.global_graph.models import GlobalCanonicalNode, LocalCanonicalRef, PackageRef
from libs.storage.models import FactorNode


def _make_node(gid: str, content: str, members: int = 1) -> GlobalCanonicalNode:
    return GlobalCanonicalNode(
        global_canonical_id=gid,
        knowledge_type="claim",
        representative_content=content,
        member_local_nodes=[
            LocalCanonicalRef(
                package=f"pkg{i}", version="0.1.0", local_canonical_id=f"lcn_{gid}_{i}"
            )
            for i in range(members)
        ],
        provenance=[PackageRef(package=f"pkg{i}", version="0.1.0") for i in range(members)],
    )


# ── merge_nodes ──


def test_merge_nodes_combines_members():
    """Merging two nodes should combine their member_local_nodes."""
    source = _make_node("gcn_source", "The Earth orbits the Sun", members=1)
    target = _make_node("gcn_target", "The Earth orbits the Sun", members=1)
    factors = [
        FactorNode(
            factor_id="f_1",
            type="infer",
            premises=["gcn_source"],
            conclusion="gcn_other",
            package_id="pkg1",
        ),
        FactorNode(
            factor_id="f_2",
            type="infer",
            premises=["gcn_other"],
            conclusion="gcn_target",
            package_id="pkg1",
        ),
    ]

    result = merge_nodes("gcn_source", "gcn_target", source, target, factors)
    assert result.merged_node.global_canonical_id == "gcn_target"
    # Target should now have members from both
    assert len(result.merged_node.member_local_nodes) == 2
    # Factors referencing source should be redirected to target
    assert all("gcn_source" not in (f.premises + [f.conclusion]) for f in result.updated_factors)
    # Rollback data should record what was merged
    assert result.rollback_data["source_id"] == "gcn_source"


def test_merge_nodes_deduplicates_provenance():
    """Provenance from both nodes is deduplicated."""
    source = _make_node("gcn_s", "Content", members=1)
    target = _make_node("gcn_t", "Content", members=1)
    # Give them same provenance
    target.provenance = list(source.provenance)

    result = merge_nodes("gcn_s", "gcn_t", source, target, [])
    # Should not have duplicate provenance
    prov_set = {(p.package, p.version) for p in result.merged_node.provenance}
    assert len(prov_set) == len(result.merged_node.provenance)


# ── create_constraint ──


def test_create_equivalence_constraint():
    """Create an equivalence factor between two nodes."""
    factor, relation_node = create_constraint("gcn_a", "gcn_b", "equivalence")
    assert factor.type == "equivalence"
    assert relation_node.global_canonical_id in factor.premises
    assert "gcn_a" in factor.premises
    assert "gcn_b" in factor.premises
    assert factor.conclusion is None
    assert factor.metadata["curation_created"] is True
    assert relation_node.knowledge_type == "equivalence"


def test_create_contradiction_constraint():
    """Create a contradiction factor between two nodes."""
    factor, relation_node = create_constraint("gcn_a", "gcn_b", "contradiction")
    assert factor.type == "contradiction"
    assert relation_node.global_canonical_id in factor.premises
    assert "gcn_a" in factor.premises
    assert "gcn_b" in factor.premises
    assert factor.conclusion is None
