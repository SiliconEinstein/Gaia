"""Tests for Graph IR elaboration, retraction factors, and orphan filtering."""

from pathlib import Path

from libs.graph_ir.build import (
    build_raw_graph,
    build_singleton_local_graph,
    derive_local_parameterization,
)
from libs.inference.bp import BeliefPropagation
from libs.lang.loader import load_package
from libs.lang.models import (
    Arg,
    ChainExpr,
    Claim,
    Contradiction,
    InferAction,
    Module,
    Package,
    Param,
    Question,
    RetractAction,
    Setting,
    StepApply,
    StepRef,
)

FIXTURES = Path(__file__).parents[2] / "fixtures" / "gaia_language_packages"
GALILEO_DIR = FIXTURES / "galileo_falling_bodies"
NEWTON_DIR = FIXTURES / "newton_principia"


def _load(pkg_dir):
    from libs.lang.resolver import resolve_refs

    return resolve_refs(load_package(pkg_dir))


# ── Retraction factor ──


def _make_retraction_package() -> Package:
    return Package(
        name="retract_pkg",
        version="0.1.0",
        loaded_modules=[
            Module(
                type="reasoning_module",
                name="core",
                knowledge=[
                    Claim(name="old_theory", content="Old theory X", prior=0.7),
                    Contradiction(
                        name="contradiction_found",
                        between=["old_theory", "new_evidence"],
                        content="X contradicts evidence",
                        prior=0.6,
                    ),
                    Claim(name="new_evidence", content="New evidence Y", prior=0.9),
                    RetractAction(
                        name="retract_old",
                        target="old_theory",
                        reason="contradiction_found",
                        content="Retract old theory due to contradiction",
                    ),
                ],
                export=["old_theory", "new_evidence"],
            )
        ],
    )


def test_retraction_stored_as_metadata_not_factor():
    """RetractAction should be an intent annotation, not a BP factor."""
    raw = build_raw_graph(_make_retraction_package())

    # No retraction factors should be generated
    retraction_factors = [
        f for f in raw.factor_nodes if f.metadata and f.metadata.get("edge_type") == "retraction"
    ]
    assert len(retraction_factors) == 0

    # Retraction intent stored in graph metadata
    assert raw.metadata is not None
    intents = raw.metadata.get("retraction_intents", [])
    assert len(intents) == 1
    assert intents[0]["target"] == "old_theory"
    assert intents[0]["reason"] == "contradiction_found"


def test_retract_action_not_in_knowledge_nodes():
    raw = build_raw_graph(_make_retraction_package())

    node_names = {n.source_refs[0].knowledge_name for n in raw.knowledge_nodes}
    assert "retract_old" not in node_names


def test_contradiction_still_suppresses_via_mutex():
    """Even without retraction factor, mutex_constraint + chain should suppress target."""
    pkg = _make_retraction_package()
    raw = build_raw_graph(pkg)
    result = build_singleton_local_graph(raw)
    params = derive_local_parameterization(pkg, result.local_graph)

    from libs.graph_ir import adapt_local_graph_to_factor_graph

    adapted = adapt_local_graph_to_factor_graph(result.local_graph, params)
    beliefs = BeliefPropagation(damping=0.3, max_iterations=100).run(adapted.factor_graph)

    # old_theory should still be suppressed via mutex_constraint
    old_theory_lcn = None
    for node in result.local_graph.knowledge_nodes:
        if node.source_refs[0].knowledge_name == "old_theory":
            old_theory_lcn = node.local_canonical_id
            break
    assert old_theory_lcn is not None

    var_id = adapted.local_id_to_var_id[old_theory_lcn]
    # With contradiction between old_theory and new_evidence (prior=0.9),
    # mutex should push old_theory below its prior of 0.7
    assert beliefs[var_id] < 0.7


def test_galileo_retraction_intent_in_fixture():
    pkg = _load(GALILEO_DIR)
    raw = build_raw_graph(pkg)

    # No retraction factors
    retraction_factors = [
        f for f in raw.factor_nodes if f.metadata and f.metadata.get("edge_type") == "retraction"
    ]
    assert len(retraction_factors) == 0

    # Retraction intent in metadata
    assert raw.metadata is not None
    intents = raw.metadata.get("retraction_intents", [])
    assert len(intents) == 1
    assert intents[0]["target"] == "heavier_falls_faster"
    assert intents[0]["reason"] == "tied_balls_contradiction"


# ── Elaboration: schema → ground + instantiation ──


def _make_elaboration_package() -> Package:
    return Package(
        name="elab_pkg",
        version="0.1.0",
        loaded_modules=[
            Module(
                type="reasoning_module",
                name="core",
                knowledge=[
                    Claim(name="premise_a", content="Premise A holds", prior=0.8),
                    Setting(name="env_b", content="Environment B", prior=1.0),
                    InferAction(
                        name="my_method",
                        params=[
                            Param(name="input", type="claim"),
                            Param(name="context", type="setting"),
                        ],
                        content="Apply method to {input} in {context}",
                        prior=0.9,
                    ),
                    Claim(name="result_c", content="Result C", prior=0.5),
                    ChainExpr(
                        name="main_chain",
                        steps=[
                            StepRef(step=1, ref="premise_a"),
                            StepApply(
                                step=2,
                                apply="my_method",
                                args=[
                                    Arg(ref="premise_a", dependency="direct"),
                                    Arg(ref="env_b", dependency="indirect"),
                                ],
                                prior=0.9,
                            ),
                            StepRef(step=3, ref="result_c"),
                        ],
                    ),
                ],
                export=["premise_a", "result_c"],
            )
        ],
    )


def test_elaboration_creates_ground_node():
    raw = build_raw_graph(_make_elaboration_package())

    ground_nodes = [
        n for n in raw.knowledge_nodes if n.metadata and n.metadata.get("elaborated_from")
    ]
    assert len(ground_nodes) == 1

    gn = ground_nodes[0]
    assert gn.knowledge_type == "action"
    assert gn.parameters == []  # ground, not schema
    assert gn.metadata["elaborated_from"] == "my_method"
    assert "Premise A holds" in gn.content  # substituted


def test_elaboration_creates_instantiation_factor():
    raw = build_raw_graph(_make_elaboration_package())

    inst_factors = [f for f in raw.factor_nodes if f.type == "instantiation"]
    assert len(inst_factors) == 1

    inst = inst_factors[0]
    node_map = {n.source_refs[0].knowledge_name: n.raw_node_id for n in raw.knowledge_nodes}
    assert inst.premises == [node_map["my_method"]]  # schema is premise
    assert inst.metadata["edge_type"] == "instantiation"


def test_ground_action_is_premise_of_reasoning_factor():
    raw = build_raw_graph(_make_elaboration_package())

    reasoning_factors = [f for f in raw.factor_nodes if f.type == "reasoning"]
    assert len(reasoning_factors) == 1

    rf = reasoning_factors[0]
    ground_nodes = [
        n for n in raw.knowledge_nodes if n.metadata and n.metadata.get("elaborated_from")
    ]
    assert ground_nodes[0].raw_node_id in rf.premises


def test_schema_action_kept_in_knowledge_nodes():
    raw = build_raw_graph(_make_elaboration_package())

    schema_nodes = [n for n in raw.knowledge_nodes if n.parameters]
    assert len(schema_nodes) == 1
    assert schema_nodes[0].source_refs[0].knowledge_name == "my_method"


def test_galileo_elaboration_in_fixture():
    pkg = _load(GALILEO_DIR)
    raw = build_raw_graph(pkg)

    inst_factors = [f for f in raw.factor_nodes if f.type == "instantiation"]
    assert len(inst_factors) == 4  # 4 apply steps

    ground_nodes = [
        n for n in raw.knowledge_nodes if n.metadata and n.metadata.get("elaborated_from")
    ]
    assert len(ground_nodes) == 4

    # All ground nodes have no parameters
    assert all(n.parameters == [] for n in ground_nodes)

    # Each ground node is connected to a reasoning factor as premise
    ground_ids = {n.raw_node_id for n in ground_nodes}
    reasoning_factors = [f for f in raw.factor_nodes if f.type == "reasoning"]
    connected_grounds = set()
    for rf in reasoning_factors:
        connected_grounds.update(set(rf.premises) & ground_ids)
    assert connected_grounds == ground_ids


# ── Orphan filtering ──


def test_orphan_question_filtered():
    pkg = Package(
        name="orphan_pkg",
        version="0.1.0",
        loaded_modules=[
            Module(
                type="reasoning_module",
                name="core",
                knowledge=[
                    Question(name="orphan_q", content="Orphan question?"),
                    Claim(name="connected_claim", content="Connected", prior=0.5),
                    Claim(name="premise", content="Premise", prior=0.8),
                    ChainExpr(
                        name="chain",
                        steps=[
                            StepRef(step=1, ref="premise"),
                            StepRef(step=2, ref="connected_claim"),
                        ],
                    ),
                ],
                export=["connected_claim"],
            )
        ],
    )
    raw = build_raw_graph(pkg)

    names = {n.source_refs[0].knowledge_name for n in raw.knowledge_nodes}
    assert "orphan_q" not in names
    assert "connected_claim" in names


def test_orphan_claim_kept():
    pkg = Package(
        name="orphan_pkg",
        version="0.1.0",
        loaded_modules=[
            Module(
                type="reasoning_module",
                name="core",
                knowledge=[
                    Claim(name="orphan_claim", content="Orphan claim", prior=0.5),
                    Claim(name="connected", content="Connected", prior=0.5),
                    Claim(name="premise", content="P", prior=0.8),
                    ChainExpr(
                        name="chain",
                        steps=[
                            StepRef(step=1, ref="premise"),
                            StepRef(step=2, ref="connected"),
                        ],
                    ),
                ],
                export=["connected"],
            )
        ],
    )
    raw = build_raw_graph(pkg)

    names = {n.source_refs[0].knowledge_name for n in raw.knowledge_nodes}
    assert "orphan_claim" in names  # kept even though unconnected


# ── Newton fixture ──


def test_newton_fixture_builds():
    # Newton has cross-package refs that fail resolve_refs, so load without resolving
    pkg = load_package(NEWTON_DIR)
    raw = build_raw_graph(pkg)

    assert len(raw.knowledge_nodes) == 20
    assert len(raw.factor_nodes) == 10  # 4 instantiation + 4 reasoning + 1 equiv + 1 mutex

    types = {n.knowledge_type for n in raw.knowledge_nodes}
    assert "claim" in types
    assert "action" in types
    assert "setting" in types

    factor_types = {f.type for f in raw.factor_nodes}
    assert "reasoning" in factor_types
    assert "instantiation" in factor_types
