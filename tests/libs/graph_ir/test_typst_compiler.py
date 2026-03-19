"""Tests for Typst -> RawGraph compiler."""

import pytest

from libs.graph_ir.models import RawGraph
from libs.graph_ir.typst_compiler import compile_typst_to_raw_graph


def _make_graph_data(
    nodes=None,
    factors=None,
    constraints=None,
    package="test_pkg",
    version="1.0.0",
):
    """Build a minimal graph_data dict for testing."""
    return {
        "package": package,
        "version": version,
        "nodes": nodes or [],
        "factors": factors or [],
        "constraints": constraints or [],
    }


# -- Node compilation --


def test_empty_graph():
    data = _make_graph_data()
    raw = compile_typst_to_raw_graph(data)
    assert isinstance(raw, RawGraph)
    assert raw.package == "test_pkg"
    assert raw.version == "1.0.0"
    assert raw.knowledge_nodes == []
    assert raw.factor_nodes == []


def test_single_observation_node():
    data = _make_graph_data(
        nodes=[
            {"name": "obs_a", "type": "observation", "content": "A observed", "module": "mod1"},
        ]
    )
    raw = compile_typst_to_raw_graph(data)
    assert len(raw.knowledge_nodes) == 1
    node = raw.knowledge_nodes[0]
    assert node.raw_node_id.startswith("raw_")
    assert node.knowledge_type == "observation"
    assert node.content == "A observed"
    assert node.kind is None
    assert node.parameters == []
    assert len(node.source_refs) == 1
    sr = node.source_refs[0]
    assert sr.package == "test_pkg"
    assert sr.version == "1.0.0"
    assert sr.module == "mod1"
    assert sr.knowledge_name == "obs_a"


def test_claim_node():
    data = _make_graph_data(
        nodes=[
            {"name": "claim_x", "type": "claim", "content": "X is true", "module": "mod1"},
        ]
    )
    raw = compile_typst_to_raw_graph(data)
    node = raw.knowledge_nodes[0]
    assert node.knowledge_type == "claim"


def test_constraint_node_has_between_metadata():
    data = _make_graph_data(
        nodes=[
            {"name": "a", "type": "claim", "content": "A", "module": "m"},
            {"name": "b", "type": "claim", "content": "B", "module": "m"},
            {"name": "c_rel", "type": "contradiction", "content": "C", "module": "m"},
        ],
        constraints=[
            {"name": "c_rel", "type": "contradiction", "between": ["a", "b"]},
        ],
    )
    raw = compile_typst_to_raw_graph(data)
    rel_node = [n for n in raw.knowledge_nodes if n.knowledge_type == "contradiction"][0]
    assert rel_node.metadata == {"between": ["a", "b"]}


def test_node_ids_are_deterministic():
    data = _make_graph_data(
        nodes=[
            {"name": "obs_a", "type": "observation", "content": "A", "module": "m"},
        ]
    )
    raw1 = compile_typst_to_raw_graph(data)
    raw2 = compile_typst_to_raw_graph(data)
    assert raw1.knowledge_nodes[0].raw_node_id == raw2.knowledge_nodes[0].raw_node_id


# -- Factor compilation --


def test_reasoning_factor():
    data = _make_graph_data(
        nodes=[
            {"name": "obs_a", "type": "observation", "content": "A", "module": "m"},
            {"name": "claim_b", "type": "claim", "content": "B", "module": "m"},
        ],
        factors=[
            {"type": "reasoning", "premise": ["obs_a"], "conclusion": "claim_b"},
        ],
    )
    raw = compile_typst_to_raw_graph(data)
    assert len(raw.factor_nodes) == 1
    factor = raw.factor_nodes[0]
    assert factor.type == "reasoning"
    assert factor.factor_id.startswith("f_")
    assert factor.contexts == []
    assert factor.metadata == {"edge_type": "deduction"}

    # premises and conclusion should be raw_node_ids, not names
    node_ids = {n.raw_node_id for n in raw.knowledge_nodes}
    assert factor.conclusion in node_ids
    assert all(p in node_ids for p in factor.premises)

    # source_ref should point to conclusion
    assert factor.source_ref is not None
    assert factor.source_ref.knowledge_name == "claim_b"


def test_reasoning_factor_multiple_premises():
    data = _make_graph_data(
        nodes=[
            {"name": "a", "type": "observation", "content": "A", "module": "m"},
            {"name": "b", "type": "observation", "content": "B", "module": "m"},
            {"name": "c", "type": "claim", "content": "C", "module": "m"},
        ],
        factors=[
            {"type": "reasoning", "premise": ["a", "b"], "conclusion": "c"},
        ],
    )
    raw = compile_typst_to_raw_graph(data)
    factor = raw.factor_nodes[0]
    assert len(factor.premises) == 2


# -- Constraint compilation --


def test_contradiction_constraint():
    data = _make_graph_data(
        nodes=[
            {"name": "a", "type": "claim", "content": "A", "module": "m"},
            {"name": "b", "type": "claim", "content": "B", "module": "m"},
            {"name": "c", "type": "contradiction", "content": "C", "module": "m"},
        ],
        constraints=[
            {"name": "c", "type": "contradiction", "between": ["a", "b"]},
        ],
    )
    raw = compile_typst_to_raw_graph(data)
    constraint_factors = [f for f in raw.factor_nodes if f.type == "mutex_constraint"]
    assert len(constraint_factors) == 1
    cf = constraint_factors[0]
    assert len(cf.premises) == 2
    assert cf.metadata == {"edge_type": "relation_contradiction"}

    # conclusion should be the constraint node's ID
    node_map = {n.knowledge_type: n.raw_node_id for n in raw.knowledge_nodes}
    assert cf.conclusion == node_map["contradiction"]


def test_equivalence_constraint():
    data = _make_graph_data(
        nodes=[
            {"name": "a", "type": "claim", "content": "A", "module": "m"},
            {"name": "b", "type": "claim", "content": "B", "module": "m"},
            {"name": "eq", "type": "equivalence", "content": "E", "module": "m"},
        ],
        constraints=[
            {"name": "eq", "type": "equivalence", "between": ["a", "b"]},
        ],
    )
    raw = compile_typst_to_raw_graph(data)
    equiv_factors = [f for f in raw.factor_nodes if f.type == "equiv_constraint"]
    assert len(equiv_factors) == 1
    assert equiv_factors[0].metadata == {"edge_type": "relation_equivalence"}


# -- Duplicate detection --


def test_duplicate_node_name_raises():
    """Duplicate node names within a package should raise ValueError."""
    data = _make_graph_data(
        nodes=[
            {"name": "obs", "type": "observation", "content": "Same", "module": "mod_a"},
            {"name": "obs", "type": "observation", "content": "Same", "module": "mod_b"},
        ]
    )
    with pytest.raises(ValueError, match="Duplicate node name"):
        compile_typst_to_raw_graph(data)
