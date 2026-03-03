from services.review_pipeline.context import PipelineContext, JoinTree


def test_context_init_from_add_edge_ops():
    """Context extracts new node info from add_edge operations."""
    from libs.models import CommitRequest, AddEdgeOp, NewNode, NodeRef

    request = CommitRequest(
        message="test",
        operations=[
            AddEdgeOp(
                tail=[NewNode(content="premise A"), NodeRef(node_id=100)],
                head=[NewNode(content="conclusion B")],
                type="paper-extract",
                reasoning=[{"title": "step1", "content": "because"}],
            )
        ],
    )
    ctx = PipelineContext.from_commit_request(request)
    assert len(ctx.new_nodes) == 2
    assert ctx.new_nodes[0].content == "premise A"
    assert ctx.new_nodes[0].op_index == 0
    assert ctx.new_nodes[0].position == "tail[0]"
    assert ctx.new_nodes[1].content == "conclusion B"
    assert ctx.new_nodes[1].position == "head[0]"
    assert ctx.cancelled is False


def test_context_init_from_modify_ops():
    """Context with only modify ops has no new nodes."""
    from libs.models import CommitRequest, ModifyNodeOp

    request = CommitRequest(
        message="test",
        operations=[ModifyNodeOp(node_id=1, changes={"status": "deleted"})],
    )
    ctx = PipelineContext.from_commit_request(request)
    assert len(ctx.new_nodes) == 0
    assert ctx.affected_node_ids == [1]


def test_join_tree_model():
    tree = JoinTree(
        source_node_index=0,
        target_node_id=251,
        relation="partial_overlap",
        verified=False,
    )
    assert tree.source_node_index == 0
    assert tree.verified is False
