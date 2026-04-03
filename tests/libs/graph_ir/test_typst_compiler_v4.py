"""Tests for v4 Typst → Graph IR compilation."""

from pathlib import Path

import pytest

from libs.graph_ir.typst_compiler import compile_v4_to_raw_graph
from libs.lang.typst_loader import load_typst_package_v4

FIXTURE = Path(__file__).parents[2] / "fixtures" / "ir" / "dark_energy_v4"


@pytest.fixture(scope="module")
def raw_graph():
    data = load_typst_package_v4(FIXTURE)
    return compile_v4_to_raw_graph(data)


def test_local_node_count(raw_graph):
    """All local nodes are compiled (excludes external)."""
    local_nodes = [n for n in raw_graph.knowledge_nodes if not n.raw_node_id.startswith("ext:")]
    # 2 settings + 1 question + 5 claims + 1 action + 1 relation = 10
    assert len(local_nodes) == 10


def test_node_types(raw_graph):
    """Node knowledge_type maps correctly from v4 supplement."""
    by_name = {}
    for n in raw_graph.knowledge_nodes:
        for sr in n.source_refs:
            by_name[sr.knowledge_name] = n
    assert by_name["flat_universe"].knowledge_type == "setting"
    assert by_name["main_question"].knowledge_type == "question"
    assert by_name["sn_observation"].knowledge_type == "claim"
    assert by_name["mcmc_fit"].knowledge_type == "action"
    assert by_name["vacuum_catastrophe"].knowledge_type == "contradiction"


def test_kind_preserved(raw_graph):
    """kind field is preserved on RawKnowledgeNode."""
    by_name = {}
    for n in raw_graph.knowledge_nodes:
        for sr in n.source_refs:
            by_name[sr.knowledge_name] = n
    assert by_name["sn_observation"].kind == "observation"
    assert by_name["mcmc_fit"].kind == "python"
    assert by_name["flat_universe"].kind is None


def test_reasoning_factors(raw_graph):
    """from: parameter generates reasoning (infer) factors."""
    infer_factors = [f for f in raw_graph.factor_nodes if f.type == "infer"]
    # dark_energy_fraction (4 premises), mcmc_fit (1), cross_validation (2)
    assert len(infer_factors) == 3


def test_main_factor_premises(raw_graph):
    """dark_energy_fraction factor has 4 premises."""
    by_name = {}
    for n in raw_graph.knowledge_nodes:
        for sr in n.source_refs:
            by_name[sr.knowledge_name] = n.raw_node_id
    infer_factors = [f for f in raw_graph.factor_nodes if f.type == "infer"]
    main_factor = next(f for f in infer_factors if f.conclusion == by_name["dark_energy_fraction"])
    assert len(main_factor.premises) == 4


def test_constraint_factors(raw_graph):
    """relation between: generates constraint factors."""
    constraint_factors = [f for f in raw_graph.factor_nodes if f.type == "contradiction"]
    assert len(constraint_factors) >= 1


def test_external_nodes_prefixed(raw_graph):
    """External nodes from gaia-bibliography get ext: prefix."""
    ext_nodes = [n for n in raw_graph.knowledge_nodes if n.raw_node_id.startswith("ext:")]
    assert len(ext_nodes) >= 1
    ext = ext_nodes[0]
    assert ext.metadata is not None
    assert ext.metadata.get("ext_package") == "cmb-analysis"
    assert "CMB" in ext.content


def test_deterministic_ids(raw_graph):
    """Node IDs are deterministic (same input → same hash)."""
    data = load_typst_package_v4(FIXTURE)
    graph2 = compile_v4_to_raw_graph(data)
    ids1 = {n.raw_node_id for n in raw_graph.knowledge_nodes}
    ids2 = {n.raw_node_id for n in graph2.knowledge_nodes}
    assert ids1 == ids2
