from libs.models import Node, HyperEdge
from services.inference_engine.factor_graph import FactorGraph


def test_add_variable():
    fg = FactorGraph()
    fg.add_variable(1, 0.9)
    assert 1 in fg.variables
    assert fg.variables[1] == 0.9


def test_add_factor():
    fg = FactorGraph()
    fg.add_factor(edge_id=100, tail=[1, 2], head=[3], probability=0.8)
    assert len(fg.factors) == 1
    assert fg.factors[0]["probability"] == 0.8
    assert fg.factors[0]["tail"] == [1, 2]


def test_from_subgraph():
    nodes = [
        Node(id=1, type="paper-extract", content="p1", prior=0.9),
        Node(id=2, type="paper-extract", content="p2", prior=0.8),
        Node(id=3, type="paper-extract", content="p3", prior=1.0),
    ]
    edges = [
        HyperEdge(id=100, type="induction", tail=[1, 2], head=[3], probability=0.85),
    ]
    fg = FactorGraph.from_subgraph(nodes, edges)
    assert len(fg.variables) == 3
    assert len(fg.factors) == 1
    assert fg.variables[1] == 0.9
    assert fg.factors[0]["probability"] == 0.85


def test_from_subgraph_default_probability():
    nodes = [Node(id=1, type="t", content="c", prior=1.0)]
    edges = [HyperEdge(id=100, type="induction", tail=[1], head=[2], probability=None)]
    fg = FactorGraph.from_subgraph(nodes, edges)
    assert fg.factors[0]["probability"] == 1.0


def test_get_var_factors():
    fg = FactorGraph()
    fg.add_variable(10, 0.5)
    fg.add_variable(11, 0.5)
    fg.add_variable(12, 0.5)
    fg.add_variable(13, 0.5)
    fg.add_factor(edge_id=1, tail=[10, 11], head=[12], probability=0.9)
    fg.add_factor(edge_id=2, tail=[12], head=[13], probability=0.8)
    vf = fg.get_var_factors()
    # Node 12 is in factor 0 (head) and factor 1 (tail)
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
