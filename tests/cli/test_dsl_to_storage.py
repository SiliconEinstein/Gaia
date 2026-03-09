"""Tests for DSL → Storage model conversion."""

from pathlib import Path

from cli.dsl_to_storage import convert_package_to_storage
from libs.dsl.compiler import compile_factor_graph
from libs.dsl.loader import load_package
from libs.dsl.resolver import resolve_refs
from libs.models import HyperEdge, Node


FIXTURE_PATH = Path("tests/fixtures/dsl_packages/galileo_falling_bodies")


def _load_galileo():
    pkg = load_package(FIXTURE_PATH)
    pkg = resolve_refs(pkg)
    fg = compile_factor_graph(pkg)
    beliefs = {name: 0.5 for name in fg.variables}
    beliefs["heavier_falls_faster"] = 0.30
    beliefs["vacuum_prediction"] = 0.79
    return pkg, fg, beliefs


def test_convert_produces_nodes_and_edges():
    pkg, fg, beliefs = _load_galileo()
    result = convert_package_to_storage(pkg, fg, beliefs)
    assert len(result.nodes) > 0
    assert len(result.edges) > 0
    assert all(isinstance(n, Node) for n in result.nodes)
    assert all(isinstance(e, HyperEdge) for e in result.edges)


def test_convert_node_has_correct_fields():
    pkg, fg, beliefs = _load_galileo()
    result = convert_package_to_storage(pkg, fg, beliefs)
    hff = next(n for n in result.nodes if n.title == "heavier_falls_faster")
    assert hff.type == "claim"
    assert hff.prior == 0.7
    assert hff.belief == 0.30
    assert "重的物体" in str(hff.content)


def test_convert_node_ids_are_unique():
    pkg, fg, beliefs = _load_galileo()
    result = convert_package_to_storage(pkg, fg, beliefs)
    ids = [n.id for n in result.nodes]
    assert len(ids) == len(set(ids))


def test_convert_edge_tail_head_are_valid_node_ids():
    pkg, fg, beliefs = _load_galileo()
    result = convert_package_to_storage(pkg, fg, beliefs)
    node_ids = {n.id for n in result.nodes}
    for edge in result.edges:
        for tid in edge.tail:
            assert tid in node_ids, f"tail id {tid} not in node_ids"
        for hid in edge.head:
            assert hid in node_ids, f"head id {hid} not in node_ids"


def test_convert_edge_has_probability_and_type():
    pkg, fg, beliefs = _load_galileo()
    result = convert_package_to_storage(pkg, fg, beliefs)
    edge_types = {e.type for e in result.edges}
    assert "deduction" in edge_types
    assert any(e.probability is not None for e in result.edges)


def test_convert_name_to_id_mapping():
    pkg, fg, beliefs = _load_galileo()
    result = convert_package_to_storage(pkg, fg, beliefs)
    assert "heavier_falls_faster" in result.name_to_id
    nid = result.name_to_id["heavier_falls_faster"]
    hff = next(n for n in result.nodes if n.id == nid)
    assert hff.title == "heavier_falls_faster"
