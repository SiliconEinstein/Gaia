# tests/libs/test_models.py
from libs.models import (
    Node,
    HyperEdge,
    AddEdgeOp,
    ModifyEdgeOp,
    ModifyNodeOp,
    NewNode,
    NodeRef,
    Commit,
    CommitRequest,
    CommitResponse,
    ValidationResult,
    DedupCandidate,
    ReviewResult,
    MergeResult,
    NNCandidate,
    QualityMetrics,
    AbstractionTreeResults,
    ContradictionResult,
    OverlapResult,
    OperationReviewDetail,
    BPResults,
    DetailedReviewResult,
)


def test_node_defaults():
    node = Node(id=1, type="paper-extract", content="test")
    assert node.status == "active"
    assert node.belief is None
    assert node.prior == 1.0
    assert node.keywords == []
    assert node.extra == {}
    assert node.title is None
    assert node.metadata == {}


def test_node_all_types():
    for t in ("paper-extract", "abstraction", "deduction", "conjecture"):
        node = Node(id=1, type=t, content="x")
        assert node.type == t


def test_node_title():
    node = Node(id=1, type="paper-extract", content="test", title="My Title")
    assert node.title == "My Title"


def test_node_flexible_content():
    """content can be str, dict, or list."""
    n1 = Node(id=1, type="t", content="text")
    assert n1.content == "text"
    n2 = Node(id=2, type="t", content={"key": "val"})
    assert n2.content == {"key": "val"}
    n3 = Node(id=3, type="t", content=["a", "b"])
    assert n3.content == ["a", "b"]


def test_hyperedge_defaults():
    edge = HyperEdge(id=1, type="paper-extract", premises=[1], conclusions=[2])
    assert edge.verified is False
    assert edge.probability is None
    assert edge.metadata == {}
    assert edge.extra == {}
    assert edge.reasoning == []


def test_hyperedge_types():
    for t in ("paper-extract", "abstraction", "induction", "contradiction", "retraction"):
        edge = HyperEdge(id=1, type=t, premises=[1], conclusions=[2])
        assert edge.type == t


def test_hyperedge_flexible_reasoning():
    """reasoning is list (untyped elements)."""
    e1 = HyperEdge(id=1, type="t", premises=[1], conclusions=[2], reasoning=["step1", "step2"])
    assert e1.reasoning == ["step1", "step2"]
    e2 = HyperEdge(
        id=2, type="t", premises=[1], conclusions=[2], reasoning=[{"title": "x", "content": "y"}]
    )
    assert e2.reasoning[0]["title"] == "x"


def test_add_edge_op():
    op = AddEdgeOp(
        premises=[NewNode(content="premise")],
        conclusions=[NodeRef(node_id=42)],
        type="induction",
        reasoning=["logical deduction"],
    )
    assert op.op == "add_edge"
    assert len(op.premises) == 1
    assert len(op.conclusions) == 1


def test_modify_edge_op():
    op = ModifyEdgeOp(edge_id=456, changes={"status": "retracted"})
    assert op.op == "modify_edge"


def test_modify_node_op():
    op = ModifyNodeOp(node_id=789, changes={"content": "updated"})
    assert op.op == "modify_node"


# ── Commit Workflow Tests ──


def test_commit_request():
    req = CommitRequest(
        message="Add new finding",
        operations=[
            AddEdgeOp(
                premises=[NewNode(content="premise A")],
                conclusions=[NodeRef(node_id=42)],
                type="induction",
                reasoning=["deduction"],
            )
        ],
    )
    assert len(req.operations) == 1
    assert req.message == "Add new finding"


def test_commit_defaults():
    commit = Commit(
        commit_id="abc123",
        message="test commit",
        operations=[],
    )
    assert commit.status == "pending_review"
    assert commit.check_results is None
    assert commit.review_results is None
    assert commit.merge_results is None


def test_validation_result():
    vr = ValidationResult(op_index=0, valid=False, errors=["tail is empty"])
    assert not vr.valid
    assert len(vr.errors) == 1


def test_dedup_candidate():
    dc = DedupCandidate(node_id=42, content="existing proposition", score=0.95)
    assert dc.score == 0.95


def test_review_result():
    rr = ReviewResult(approved=True)
    assert rr.issues == []
    assert rr.suggestions == []


def test_merge_result():
    mr = MergeResult(success=True, new_node_ids=[100, 101], new_edge_ids=[50])
    assert mr.success
    assert len(mr.new_node_ids) == 2


def test_commit_response():
    cr = CommitResponse(commit_id="abc", status="pending_review")
    assert cr.commit_id == "abc"


# ── Detailed Review Models Tests ──


def test_nn_candidate_defaults():
    c = NNCandidate(node_id="42", similarity=0.95)
    assert c.node_id == "42"
    assert c.similarity == 0.95


def test_quality_metrics():
    q = QualityMetrics(reasoning_valid=True, tightness=0.8, substantiveness=0.7, novelty=0.6)
    assert q.reasoning_valid is True
    assert q.novelty == 0.6


def test_abstraction_tree_results_defaults():
    jt = AbstractionTreeResults()
    assert jt.cc == []
    assert jt.cp == []


def test_contradiction_result():
    cr = ContradictionResult(node_id="5", edge_id="10", description="Contradicts prior claim")
    assert cr.node_id == "5"
    assert cr.edge_id == "10"
    assert cr.description == "Contradicts prior claim"


def test_overlap_result():
    o = OverlapResult(existing_node_id="7", similarity=0.92, recommendation="merge")
    assert o.existing_node_id == "7"
    assert o.similarity == 0.92
    assert o.recommendation == "merge"


def test_operation_review_detail_defaults():
    detail = OperationReviewDetail(
        op_index=0,
        verdict="pass",
        embedding_generated=True,
        nn_candidates=[],
        abstraction_trees=AbstractionTreeResults(cc=[], cp=[]),
        contradictions=[],
        overlaps=[],
    )
    assert detail.verdict == "pass"
    assert detail.quality is None


def test_bp_results():
    bp = BPResults(
        belief_updates={"1": 0.8, "2": 0.6},
        iterations=5,
        converged=True,
        affected_nodes=["1", "2"],
    )
    assert bp.converged is True
    assert len(bp.affected_nodes) == 2


def test_detailed_review_result():
    result = DetailedReviewResult(
        overall_verdict="pass",
        operations=[
            OperationReviewDetail(
                op_index=0,
                verdict="pass",
                embedding_generated=True,
                nn_candidates=[NNCandidate(node_id="10", similarity=0.9)],
                abstraction_trees=AbstractionTreeResults(cc=[], cp=[]),
                contradictions=[],
                overlaps=[],
            )
        ],
        bp_results=BPResults(belief_updates={}, iterations=3, converged=True, affected_nodes=[]),
    )
    assert result.overall_verdict == "pass"
    assert len(result.operations) == 1
    assert result.bp_results.converged is True


def test_detailed_review_result_no_bp():
    result = DetailedReviewResult(
        overall_verdict="has_overlap",
        operations=[],
    )
    assert result.bp_results is None


def test_merge_result_with_bp_details():
    result = MergeResult(
        success=True,
        new_node_ids=["1", "2"],
        new_edge_ids=["10"],
        errors=[],
        bp_results=BPResults(
            belief_updates={"1": 0.9},
            iterations=5,
            converged=True,
            affected_nodes=["1"],
        ),
        abstraction_edges_created=["10"],
        beliefs_persisted={"1": 0.9},
    )
    assert result.bp_results.converged is True
    assert result.abstraction_edges_created == ["10"]
    assert result.beliefs_persisted == {"1": 0.9}


def test_merge_result_backward_compat():
    result = MergeResult(
        success=True,
        new_node_ids=[],
        new_edge_ids=[],
        errors=[],
    )
    assert result.bp_results is None
    assert result.abstraction_edges_created == []
    assert result.beliefs_persisted == {}


def test_commit_review_job_id():
    commit = Commit(
        commit_id="c1",
        status="pending_review",
        message="test",
        operations=[],
        review_job_id="job-123",
    )
    assert commit.review_job_id == "job-123"


def test_commit_review_job_id_default_none():
    commit = Commit(
        commit_id="c1",
        status="pending_review",
        message="test",
        operations=[],
    )
    assert commit.review_job_id is None
