# tests/services/test_commit_engine/test_validator.py
import pytest
from libs.models import AddEdgeOp, ModifyEdgeOp, ModifyNodeOp, NewNode, NodeRef
from services.commit_engine.validator import Validator


@pytest.fixture
def validator():
    return Validator()


async def test_valid_add_edge(validator):
    op = AddEdgeOp(
        tail=[NewNode(content="p1")],
        head=[NodeRef(node_id=1)],
        type="meet",
        reasoning=["deduction"],
    )
    results = await validator.validate([op])
    assert len(results) == 1
    assert results[0].valid is True


async def test_add_edge_empty_tail(validator):
    op = AddEdgeOp(tail=[], head=[NodeRef(node_id=1)], type="meet", reasoning=["x"])
    results = await validator.validate([op])
    assert results[0].valid is False
    assert any("tail" in e.lower() for e in results[0].errors)


async def test_add_edge_empty_head(validator):
    op = AddEdgeOp(tail=[NewNode(content="p")], head=[], type="meet", reasoning=["x"])
    results = await validator.validate([op])
    assert results[0].valid is False
    assert any("head" in e.lower() for e in results[0].errors)


async def test_add_edge_empty_reasoning(validator):
    op = AddEdgeOp(
        tail=[NewNode(content="p")], head=[NodeRef(node_id=1)], type="meet", reasoning=[]
    )
    results = await validator.validate([op])
    assert results[0].valid is False
    assert any("reasoning" in e.lower() for e in results[0].errors)


async def test_valid_modify_edge(validator):
    op = ModifyEdgeOp(edge_id=42, changes={"verified": True})
    results = await validator.validate([op])
    assert results[0].valid is True


async def test_modify_edge_empty_changes(validator):
    op = ModifyEdgeOp(edge_id=42, changes={})
    results = await validator.validate([op])
    assert results[0].valid is False


async def test_valid_modify_node(validator):
    op = ModifyNodeOp(node_id=10, changes={"content": "updated"})
    results = await validator.validate([op])
    assert results[0].valid is True


async def test_modify_node_empty_changes(validator):
    op = ModifyNodeOp(node_id=10, changes={})
    results = await validator.validate([op])
    assert results[0].valid is False


async def test_multiple_operations(validator):
    ops = [
        AddEdgeOp(
            tail=[NewNode(content="p")], head=[NodeRef(node_id=1)], type="meet", reasoning=["x"]
        ),
        ModifyEdgeOp(edge_id=42, changes={}),  # invalid
        ModifyNodeOp(node_id=10, changes={"content": "y"}),
    ]
    results = await validator.validate(ops)
    assert len(results) == 3
    assert results[0].valid is True
    assert results[1].valid is False
    assert results[2].valid is True
    assert results[0].op_index == 0
    assert results[1].op_index == 1
    assert results[2].op_index == 2
