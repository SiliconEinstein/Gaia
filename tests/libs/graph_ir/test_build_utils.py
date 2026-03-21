"""Tests for Graph IR build utilities."""

from libs.graph_ir.build_utils import (
    CanonicalizationResult,
    build_singleton_local_graph,
    derive_local_parameterization_from_raw,
    extract_parameters,
    factor_id,
    local_canonical_id,
    raw_node_id,
)
from libs.graph_ir.models import (
    FactorNode,
    RawGraph,
    RawKnowledgeNode,
    SourceRef,
)


def test_raw_node_id_is_deterministic():
    id1 = raw_node_id(
        package="pkg",
        version="1.0.0",
        module_name="mod",
        knowledge_name="claim_a",
        knowledge_type="claim",
        kind=None,
        content="hello",
        parameters=[],
    )
    id2 = raw_node_id(
        package="pkg",
        version="1.0.0",
        module_name="mod",
        knowledge_name="claim_a",
        knowledge_type="claim",
        kind=None,
        content="hello",
        parameters=[],
    )
    assert id1 == id2
    assert id1.startswith("raw_")
    assert len(id1) == 4 + 16  # "raw_" + 16 hex chars


def test_raw_node_id_differs_on_content():
    id1 = raw_node_id("p", "1", "m", "k", "claim", None, "aaa", [])
    id2 = raw_node_id("p", "1", "m", "k", "claim", None, "bbb", [])
    assert id1 != id2


def test_local_canonical_id_is_deterministic():
    lcn1 = local_canonical_id("raw_abc123")
    lcn2 = local_canonical_id("raw_abc123")
    assert lcn1 == lcn2
    assert lcn1.startswith("lcn_")


def test_factor_id_is_deterministic():
    fid1 = factor_id("reasoning", "mod", "chain_a")
    fid2 = factor_id("reasoning", "mod", "chain_a")
    assert fid1 == fid2
    assert fid1.startswith("f_")


def test_factor_id_with_suffix():
    fid1 = factor_id("equiv", "mod", "name", suffix="1")
    fid2 = factor_id("equiv", "mod", "name", suffix="2")
    assert fid1 != fid2


def test_extract_parameters_empty():
    assert extract_parameters("no placeholders here") == []


def test_extract_parameters_finds_placeholders():
    params = extract_parameters("For all {X}, if {Y} then {X}")
    names = [p.name for p in params]
    assert names == ["X", "Y"]  # sorted, deduplicated


def test_build_singleton_local_graph():
    raw = RawGraph(
        package="test_pkg",
        version="1.0.0",
        knowledge_nodes=[
            RawKnowledgeNode(
                raw_node_id="raw_a",
                knowledge_type="claim",
                content="A is true",
                source_refs=[
                    SourceRef(package="test_pkg", version="1.0.0", module="m", knowledge_name="a")
                ],
            ),
            RawKnowledgeNode(
                raw_node_id="raw_b",
                knowledge_type="observation",
                content="B observed",
                source_refs=[
                    SourceRef(package="test_pkg", version="1.0.0", module="m", knowledge_name="b")
                ],
            ),
        ],
        factor_nodes=[
            FactorNode(
                factor_id="f_test",
                type="reasoning",
                premises=["raw_b"],
                conclusion="raw_a",
                source_ref=SourceRef(
                    package="test_pkg", version="1.0.0", module="m", knowledge_name="chain_a"
                ),
            ),
        ],
    )
    result = build_singleton_local_graph(raw)
    assert isinstance(result, CanonicalizationResult)
    assert len(result.local_graph.knowledge_nodes) == 2
    assert len(result.local_graph.factor_nodes) == 1
    assert result.local_graph.package == "test_pkg"

    # Factor premises/conclusion should be remapped to local IDs
    factor = result.local_graph.factor_nodes[0]
    assert factor.conclusion.startswith("lcn_")
    assert all(p.startswith("lcn_") for p in factor.premises)


def test_derive_local_parameterization_defaults_only_settings_to_one():
    raw = RawGraph(
        package="test_pkg",
        version="1.0.0",
        knowledge_nodes=[
            RawKnowledgeNode(
                raw_node_id="raw_setting",
                knowledge_type="setting",
                content="In vacuum conditions.",
                source_refs=[
                    SourceRef(
                        package="test_pkg",
                        version="1.0.0",
                        module="m",
                        knowledge_name="vacuum_env",
                    )
                ],
            ),
            RawKnowledgeNode(
                raw_node_id="raw_obs",
                knowledge_type="observation",
                content="A detector reading was observed.",
                source_refs=[
                    SourceRef(
                        package="test_pkg",
                        version="1.0.0",
                        module="m",
                        knowledge_name="detector_observation",
                    )
                ],
            ),
            RawKnowledgeNode(
                raw_node_id="raw_claim",
                knowledge_type="claim",
                content="A hypothesis holds.",
                source_refs=[
                    SourceRef(
                        package="test_pkg",
                        version="1.0.0",
                        module="m",
                        knowledge_name="hypothesis",
                    )
                ],
            ),
        ],
        factor_nodes=[],
    )

    result = build_singleton_local_graph(raw)
    params = derive_local_parameterization_from_raw(raw, result.local_graph)
    by_name = {
        node.source_refs[0].knowledge_name: params.node_priors[node.local_canonical_id]
        for node in result.local_graph.knowledge_nodes
    }

    assert by_name["vacuum_env"] == 1.0
    assert by_name["detector_observation"] == 0.5
    assert by_name["hypothesis"] == 0.5
