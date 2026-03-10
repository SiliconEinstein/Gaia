import pytest

from libs.models import Node, HyperEdge
from libs.inference.factor_graph import FactorGraph


def test_add_variable():
    fg = FactorGraph()
    fg.add_variable(1, 0.9)
    assert 1 in fg.variables
    assert fg.variables[1] == 0.9


def test_add_factor():
    fg = FactorGraph()
    fg.add_factor(
        edge_id=100, premises=[1, 2], conclusions=[3], probability=0.8, edge_type="induction"
    )
    assert len(fg.factors) == 1
    assert fg.factors[0]["probability"] == 0.8
    assert fg.factors[0]["premises"] == [1, 2]
    assert fg.factors[0]["conclusions"] == [3]
    assert fg.factors[0]["edge_id"] == 100
    assert fg.factors[0]["edge_type"] == "induction"


def test_add_factor_with_gate_var():
    fg = FactorGraph()
    fg.add_factor(
        edge_id=100,
        premises=[1, 2],
        conclusions=[],
        probability=0.8,
        edge_type="relation_contradiction",
        gate_var=3,
    )
    assert fg.factors[0]["gate_var"] == 3


def test_from_subgraph():
    nodes = [
        Node(id=1, type="paper-extract", content="p1", prior=0.9),
        Node(id=2, type="paper-extract", content="p2", prior=0.8),
        Node(id=3, type="paper-extract", content="p3", prior=1.0),
    ]
    edges = [
        HyperEdge(id=100, type="induction", premises=[1, 2], conclusions=[3], probability=0.85),
    ]
    fg = FactorGraph.from_subgraph(nodes, edges)
    assert len(fg.variables) == 3
    assert len(fg.factors) == 1
    assert fg.variables[1] == 0.9
    assert fg.factors[0]["probability"] == 0.85
    assert fg.factors[0]["premises"] == [1, 2]
    assert fg.factors[0]["conclusions"] == [3]
    # edge_type should propagate from HyperEdge.type
    assert fg.factors[0]["edge_type"] == "induction"


def test_from_subgraph_default_probability():
    nodes = [Node(id=1, type="t", content="c", prior=1.0)]
    edges = [HyperEdge(id=100, type="induction", premises=[1], conclusions=[2], probability=None)]
    fg = FactorGraph.from_subgraph(nodes, edges)
    # probability=None defaults to 1.0, which is Cromwell-clamped to 1-ε
    assert fg.factors[0]["probability"] == pytest.approx(1.0 - 1e-3)


def test_get_var_factors():
    fg = FactorGraph()
    fg.add_variable(10, 0.5)
    fg.add_variable(11, 0.5)
    fg.add_variable(12, 0.5)
    fg.add_variable(13, 0.5)
    fg.add_factor(edge_id=1, premises=[10, 11], conclusions=[12], probability=0.9)
    fg.add_factor(edge_id=2, premises=[12], conclusions=[13], probability=0.8)
    vf = fg.get_var_factors()
    # Node 12 is in factor 0 (conclusions) and factor 1 (premises)
    assert set(vf[12]) == {0, 1}
    # Node 10 is only in factor 0
    assert vf[10] == [0]
    # Node 13 is only in factor 1
    assert vf[13] == [1]


def test_get_variable_ids():
    fg = FactorGraph()
    fg.add_variable(1, 0.9)
    fg.add_variable(2, 0.8)
    fg.add_variable(3, 1.0)
    ids = fg.get_variable_ids()
    assert set(ids) == {1, 2, 3}


def test_empty_graph():
    fg = FactorGraph()
    assert fg.variables == {}
    assert fg.factors == []
    assert fg.get_variable_ids() == []
    assert fg.get_var_factors() == {}


def test_from_subgraph_empty():
    """from_subgraph with empty inputs returns an empty factor graph."""
    fg = FactorGraph.from_subgraph([], [])
    assert fg.variables == {}
    assert fg.factors == []


def test_add_variable_overwrite():
    """Adding a variable with the same ID overwrites the prior."""
    fg = FactorGraph()
    fg.add_variable(1, 0.9)
    fg.add_variable(1, 0.3)
    assert fg.variables[1] == 0.3
    assert len(fg.variables) == 1


def test_get_var_factors_isolated_variable():
    """A variable with no factors should have an empty factor list."""
    fg = FactorGraph()
    fg.add_variable(1, 0.5)
    fg.add_variable(2, 0.5)
    fg.add_factor(edge_id=1, premises=[1], conclusions=[], probability=0.9)
    vf = fg.get_var_factors()
    assert vf[1] == [0]
    assert vf[2] == []  # isolated: no factors reference it


def test_add_factor_default_edge_type():
    """add_factor without edge_type should default to 'deduction'."""
    fg = FactorGraph()
    fg.add_factor(edge_id=1, premises=[1], conclusions=[2], probability=0.8)
    assert fg.factors[0]["edge_type"] == "deduction"


# ---------------------------------------------------------------------------
# Cromwell clamping tests
# ---------------------------------------------------------------------------


def test_cromwell_clamp_prior_zero():
    """prior=0.0 is clamped to ε at construction time."""
    fg = FactorGraph()
    fg.add_variable(1, 0.0)
    assert fg.variables[1] == pytest.approx(1e-3)


def test_cromwell_clamp_prior_one():
    """prior=1.0 is clamped to 1-ε at construction time."""
    fg = FactorGraph()
    fg.add_variable(1, 1.0)
    assert fg.variables[1] == pytest.approx(1.0 - 1e-3)


def test_cromwell_clamp_probability_zero():
    """probability=0.0 is clamped to ε at construction time."""
    fg = FactorGraph()
    fg.add_factor(edge_id=1, premises=[1], conclusions=[2], probability=0.0)
    assert fg.factors[0]["probability"] == pytest.approx(1e-3)


def test_cromwell_clamp_probability_one():
    """probability=1.0 is clamped to 1-ε at construction time."""
    fg = FactorGraph()
    fg.add_factor(edge_id=1, premises=[1], conclusions=[2], probability=1.0)
    assert fg.factors[0]["probability"] == pytest.approx(1.0 - 1e-3)


def test_cromwell_no_clamp_normal_values():
    """Normal values (0 < p < 1) are NOT clamped."""
    fg = FactorGraph()
    fg.add_variable(1, 0.5)
    fg.add_factor(edge_id=1, premises=[1], conclusions=[2], probability=0.8)
    assert fg.variables[1] == 0.5
    assert fg.factors[0]["probability"] == 0.8
