import re

import pytest
from pydantic import ValidationError

from gaia.engine.ir import (
    FormulaEdge,
    FormulaGraph,
    FormulaNode,
    Knowledge,
    KnowledgeType,
    LocalCanonicalGraph,
    formula_node_id,
)


def test_formula_node_id_is_stable_for_descriptor_order():
    descriptor = {"symbol": "P", "args": ["x", "y"]}
    same_descriptor = {"args": ["x", "y"], "symbol": "P"}

    node_id = formula_node_id(descriptor)

    assert node_id == formula_node_id(same_descriptor)
    assert re.fullmatch(r"fg:[0-9a-f]{16}", node_id)


def test_formula_node_rejects_mismatched_id():
    with pytest.raises(ValidationError, match="does not match canonical descriptor hash"):
        FormulaNode(id="fg:0000000000000000", kind="atom", descriptor={"symbol": "P"})


def test_formula_graph_round_trips_json():
    root = FormulaNode(
        id=formula_node_id({"symbol": "P", "args": ["x"]}),
        kind="atom",
        descriptor={"symbol": "P", "args": ["x"]},
    )
    graph = FormulaGraph(source_claim="github:test::claim", root=root.id, nodes=[root])

    round_tripped = FormulaGraph.model_validate_json(graph.model_dump_json())

    assert round_tripped == graph


def test_formula_graph_reports_invalid_nodes_as_validation_error():
    with pytest.raises(ValidationError, match="nodes"):
        FormulaGraph(source_claim="github:test::claim", root="fg:missing", nodes=None)


def test_formula_graph_rejects_dangling_edge():
    root = FormulaNode(
        id=formula_node_id({"symbol": "P"}),
        kind="atom",
        descriptor={"symbol": "P"},
    )

    with pytest.raises(ValidationError, match="edge target 'fg:missing' not found"):
        FormulaGraph(
            source_claim="github:test::claim",
            root=root.id,
            nodes=[root],
            edges=[FormulaEdge(source=root.id, target="fg:missing", role="operand")],
        )


def test_formula_graph_rejects_duplicate_id_with_different_descriptor():
    node_id = formula_node_id({"symbol": "P"})
    left = FormulaNode(id=node_id, kind="atom", descriptor={"symbol": "P"})
    right = FormulaNode.model_construct(id=node_id, kind="atom", descriptor={"symbol": "Q"})

    with pytest.raises(ValidationError, match="appears with different descriptors"):
        FormulaGraph(source_claim="github:test::claim", root=node_id, nodes=[left, right])


def test_formula_graph_rejects_duplicate_id_with_different_kind():
    node_id = formula_node_id({"symbol": "P"})
    left = FormulaNode(id=node_id, kind="atom", descriptor={"symbol": "P"})
    right = FormulaNode.model_construct(id=node_id, kind="term", descriptor={"symbol": "P"})

    with pytest.raises(ValidationError, match="appears with different kind or descriptors"):
        FormulaGraph(source_claim="github:test::claim", root=node_id, nodes=[left, right])


def test_formula_graphs_participate_in_ir_hash():
    claim = Knowledge(
        id="github:test::claim",
        label="claim",
        type=KnowledgeType.CLAIM,
        content="claim",
    )
    p_node = FormulaNode(
        id=formula_node_id({"symbol": "P"}),
        kind="atom",
        descriptor={"symbol": "P"},
    )
    q_node = FormulaNode(
        id=formula_node_id({"symbol": "Q"}),
        kind="atom",
        descriptor={"symbol": "Q"},
    )

    p_graph = FormulaGraph(source_claim=claim.id, root=p_node.id, nodes=[p_node])
    q_graph = FormulaGraph(source_claim=claim.id, root=q_node.id, nodes=[q_node])

    p_hash = LocalCanonicalGraph(
        namespace="github",
        package_name="test",
        knowledges=[claim],
        formula_graphs=[p_graph],
    ).ir_hash
    q_hash = LocalCanonicalGraph(
        namespace="github",
        package_name="test",
        knowledges=[claim],
        formula_graphs=[q_graph],
    ).ir_hash

    assert p_hash != q_hash
