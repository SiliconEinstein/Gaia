"""Tests for global graph data models."""

from libs.global_graph.models import (
    CanonicalBinding,
    CanonicalizationResult,
    GlobalCanonicalNode,
    GlobalGraph,
    GlobalInferenceState,
    LocalCanonicalRef,
    PackageRef,
)
from libs.graph_ir.models import FactorParams, Parameter


class TestGlobalCanonicalNode:
    def test_create_minimal(self):
        node = GlobalCanonicalNode(
            global_canonical_id="gcn_001",
            knowledge_type="claim",
            representative_content="Test claim",
        )
        assert node.global_canonical_id == "gcn_001"
        assert node.kind is None
        assert node.parameters == []
        assert node.member_local_nodes == []
        assert node.provenance == []

    def test_create_with_members(self):
        node = GlobalCanonicalNode(
            global_canonical_id="gcn_002",
            knowledge_type="claim",
            representative_content="Shared claim",
            member_local_nodes=[
                LocalCanonicalRef(package="pkg_a", version="1.0.0", local_canonical_id="lcn_aaa"),
                LocalCanonicalRef(package="pkg_b", version="1.0.0", local_canonical_id="lcn_bbb"),
            ],
            provenance=[
                PackageRef(package="pkg_a", version="1.0.0"),
                PackageRef(package="pkg_b", version="1.0.0"),
            ],
        )
        assert len(node.member_local_nodes) == 2
        assert len(node.provenance) == 2

    def test_with_parameters(self):
        node = GlobalCanonicalNode(
            global_canonical_id="gcn_003",
            knowledge_type="action",
            kind="infer_action",
            representative_content="Apply {method} to {input}",
            parameters=[
                Parameter(name="method", constraint="unknown"),
                Parameter(name="input", constraint="unknown"),
            ],
        )
        assert len(node.parameters) == 2
        assert node.kind == "infer_action"


class TestCanonicalBinding:
    def test_match_existing(self):
        binding = CanonicalBinding(
            package="pkg_a",
            version="1.0.0",
            local_graph_hash="sha256:abc123",
            local_canonical_id="lcn_aaa",
            decision="match_existing",
            global_canonical_id="gcn_001",
            decided_by="auto_canonicalize",
            reason="cosine similarity 0.95",
        )
        assert binding.decision == "match_existing"

    def test_create_new(self):
        binding = CanonicalBinding(
            package="pkg_a",
            version="1.0.0",
            local_graph_hash="sha256:abc123",
            local_canonical_id="lcn_bbb",
            decision="create_new",
            global_canonical_id="gcn_new",
            decided_by="auto_canonicalize",
        )
        assert binding.decision == "create_new"
        assert binding.reason is None


class TestGlobalGraph:
    def test_empty_graph(self):
        g = GlobalGraph()
        assert g.knowledge_nodes == []
        assert g.factor_nodes == []
        assert len(g.node_index) == 0

    def test_node_index(self):
        n = GlobalCanonicalNode(
            global_canonical_id="gcn_001",
            knowledge_type="claim",
            representative_content="X",
        )
        g = GlobalGraph(knowledge_nodes=[n])
        assert g.node_index["gcn_001"] is n

    def test_add_node(self):
        g = GlobalGraph()
        n = GlobalCanonicalNode(
            global_canonical_id="gcn_001",
            knowledge_type="claim",
            representative_content="X",
        )
        g.add_node(n)
        assert len(g.knowledge_nodes) == 1
        assert "gcn_001" in g.node_index


class TestGlobalInferenceState:
    def test_create(self):
        state = GlobalInferenceState(
            graph_hash="sha256:abc",
            node_priors={"gcn_001": 0.7},
            factor_parameters={"f_001": FactorParams(conditional_probability=0.9)},
            node_beliefs={"gcn_001": 0.65},
        )
        assert state.node_priors["gcn_001"] == 0.7


class TestCanonicalizationResult:
    def test_create(self):
        result = CanonicalizationResult(
            bindings=[],
            new_global_nodes=[],
            matched_global_nodes=[],
            unresolved_cross_refs=[],
        )
        assert result.bindings == []
