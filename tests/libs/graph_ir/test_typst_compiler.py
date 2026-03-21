"""Tests for Typst -> RawGraph compiler."""

from pathlib import Path

import pytest

from libs.graph_ir.build_utils import build_singleton_local_graph
from libs.graph_ir.models import RawGraph
from libs.graph_ir.typst_compiler import compile_typst_to_raw_graph
from libs.lang.typst_loader import load_typst_package


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
    assert factor.type == "infer"
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
    constraint_factors = [f for f in raw.factor_nodes if f.type == "contradiction"]
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
    equiv_factors = [f for f in raw.factor_nodes if f.type == "equivalence"]
    assert len(equiv_factors) == 1
    assert equiv_factors[0].metadata == {"edge_type": "relation_equivalence"}


# -- Factor type canonicalization --


def test_reasoning_factor_uses_infer_type():
    """Reasoning factors must emit type='infer' (not 'reasoning')."""
    data = _make_graph_data(
        nodes=[
            {"name": "p", "type": "observation", "content": "P", "module": "m"},
            {"name": "q", "type": "claim", "content": "Q", "module": "m"},
        ],
        factors=[
            {"type": "reasoning", "premise": ["p"], "conclusion": "q"},
        ],
    )
    raw = compile_typst_to_raw_graph(data)
    factor = raw.factor_nodes[0]
    assert factor.type == "infer"
    # factor_id should also be based on "infer" kind
    assert factor.factor_id.startswith("f_")


def test_contradiction_constraint_uses_canonical_type():
    """Contradiction constraints must emit type='contradiction' (not 'mutex_constraint')."""
    data = _make_graph_data(
        nodes=[
            {"name": "x", "type": "claim", "content": "X", "module": "m"},
            {"name": "y", "type": "claim", "content": "Y", "module": "m"},
            {"name": "rel", "type": "contradiction", "content": "R", "module": "m"},
        ],
        constraints=[
            {"name": "rel", "type": "contradiction", "between": ["x", "y"]},
        ],
    )
    raw = compile_typst_to_raw_graph(data)
    factor = raw.factor_nodes[0]
    assert factor.type == "contradiction"


def test_equivalence_constraint_uses_canonical_type():
    """Equivalence constraints must emit type='equivalence' (not 'equiv_constraint')."""
    data = _make_graph_data(
        nodes=[
            {"name": "x", "type": "claim", "content": "X", "module": "m"},
            {"name": "y", "type": "claim", "content": "Y", "module": "m"},
            {"name": "eq", "type": "equivalence", "content": "E", "module": "m"},
        ],
        constraints=[
            {"name": "eq", "type": "equivalence", "between": ["x", "y"]},
        ],
    )
    raw = compile_typst_to_raw_graph(data)
    factor = raw.factor_nodes[0]
    assert factor.type == "equivalence"


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


# -- Integration tests (Typst fixture → RawGraph) --

GALILEO_V3 = (
    Path(__file__).parent.parent.parent
    / "fixtures"
    / "gaia_language_packages"
    / "galileo_falling_bodies_v3"
)


def test_galileo_v3_full_compile():
    """End-to-end: load Typst fixture -> compile -> verify RawGraph structure."""
    graph_data = load_typst_package(GALILEO_V3)
    raw = compile_typst_to_raw_graph(graph_data)

    assert raw.package == "galileo_falling_bodies"
    assert raw.version == "3.0.0"

    # Should have nodes for observations, settings, claims, and constraints
    types = {n.knowledge_type for n in raw.knowledge_nodes}
    assert "observation" in types
    assert "claim" in types

    # Should have reasoning factors (type="infer")
    reasoning = [f for f in raw.factor_nodes if f.type == "infer"]
    assert len(reasoning) >= 3  # vacuum_prediction, composite_is_slower, etc.

    # Should have constraint factor for tied_balls_contradiction (type="contradiction")
    constraints = [f for f in raw.factor_nodes if f.type == "contradiction"]
    assert len(constraints) >= 1

    # All factor premises/conclusions should reference valid node IDs
    node_ids = {n.raw_node_id for n in raw.knowledge_nodes}
    for factor in raw.factor_nodes:
        assert factor.conclusion in node_ids, f"conclusion {factor.conclusion} not in nodes"
        for p in factor.premises:
            assert p in node_ids, f"premise {p} not in nodes"


def test_galileo_v3_through_canonicalization():
    """End-to-end: Typst -> RawGraph -> LocalCanonicalGraph."""
    graph_data = load_typst_package(GALILEO_V3)
    raw = compile_typst_to_raw_graph(graph_data)
    result = build_singleton_local_graph(raw)

    assert len(result.local_graph.knowledge_nodes) == len(raw.knowledge_nodes)
    assert len(result.local_graph.factor_nodes) == len(raw.factor_nodes)

    # All local IDs should start with "lcn_"
    for node in result.local_graph.knowledge_nodes:
        assert node.local_canonical_id.startswith("lcn_")
