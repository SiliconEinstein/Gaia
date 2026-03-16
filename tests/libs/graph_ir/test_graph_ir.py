"""Tests for package-local Graph IR builders and adapter."""

from pathlib import Path

from libs.graph_ir import (
    FactorParams,
    LocalParameterization,
    adapt_local_graph_to_factor_graph,
    build_raw_graph,
    build_singleton_local_graph,
    derive_local_parameterization,
)
from libs.inference.bp import BeliefPropagation
from libs.lang.loader import _parse_module, load_package
from libs.lang.models import Claim, Equivalence, Module, Package, StepLambda, StepRef
from libs.lang.resolver import resolve_refs

FIXTURES = Path(__file__).parents[2] / "fixtures" / "gaia_language_packages"
GALILEO_DIR = FIXTURES / "galileo_falling_bodies"


def _load_galileo():
    pkg = load_package(GALILEO_DIR)
    return resolve_refs(pkg)


def _make_duplicate_content_package() -> Package:
    return Package(
        name="duplicate_claims",
        version="0.1.0",
        loaded_modules=[
            Module(
                type="reasoning_module",
                name="first",
                knowledge=[
                    Claim(name="same_a", content="same content", prior=0.6),
                    Claim(name="same_b", content="same content", prior=0.4),
                ],
                export=["same_a", "same_b"],
            )
        ],
    )


def _make_nary_equivalence_package() -> Package:
    return Package(
        name="equiv_pkg",
        version="0.1.0",
        loaded_modules=[
            Module(
                type="reasoning_module",
                name="core",
                knowledge=[
                    Claim(name="a", content="A", prior=0.6),
                    Claim(name="b", content="B", prior=0.6),
                    Claim(name="c", content="C", prior=0.6),
                    Equivalence(
                        name="eq_all",
                        between=["a", "b", "c"],
                        content="A, B, C are equivalent",
                        prior=0.7,
                    ),
                ],
                export=["a", "b", "c", "eq_all"],
            )
        ],
    )


def test_build_raw_graph_has_nodes_and_factors():
    pkg = _load_galileo()
    raw_graph = build_raw_graph(pkg)

    assert raw_graph.package == "galileo_falling_bodies"
    assert raw_graph.knowledge_nodes
    assert raw_graph.factor_nodes
    assert len({node.raw_node_id for node in raw_graph.knowledge_nodes}) == len(
        raw_graph.knowledge_nodes
    )
    assert any(factor.type == "reasoning" for factor in raw_graph.factor_nodes)


def test_build_raw_graph_preserves_duplicate_content_as_distinct_occurrences():
    raw_graph = build_raw_graph(_make_duplicate_content_package())

    raw_ids = [node.raw_node_id for node in raw_graph.knowledge_nodes]
    assert len(raw_ids) == 2
    assert len(set(raw_ids)) == 2


def test_singleton_local_graph_preserves_cardinality_and_logs():
    pkg = _load_galileo()
    raw_graph = build_raw_graph(pkg)
    canonicalization = build_singleton_local_graph(raw_graph)

    assert len(canonicalization.local_graph.knowledge_nodes) == len(raw_graph.knowledge_nodes)
    assert len(canonicalization.log) == len(raw_graph.knowledge_nodes)
    assert all(len(entry.members) == 1 for entry in canonicalization.log)
    assert all(
        node.local_canonical_id.startswith("lcn_")
        for node in canonicalization.local_graph.knowledge_nodes
    )


def test_local_parameterization_covers_nodes_and_reasoning_factors():
    pkg = _load_galileo()
    raw_graph = build_raw_graph(pkg)
    canonicalization = build_singleton_local_graph(raw_graph)
    parameterization = derive_local_parameterization(pkg, canonicalization.local_graph)

    node_ids = {node.local_canonical_id for node in canonicalization.local_graph.knowledge_nodes}
    reasoning_ids = {
        factor.factor_id
        for factor in canonicalization.local_graph.factor_nodes
        if factor.type == "reasoning"
    }

    assert parameterization.graph_hash == canonicalization.local_graph.graph_hash()
    assert set(parameterization.node_priors) == node_ids
    assert set(parameterization.factor_parameters) == reasoning_ids


def test_equivalence_nary_decomposes_to_pairwise_constraint_factors():
    raw_graph = build_raw_graph(_make_nary_equivalence_package())

    pairwise_equiv_factors = [
        factor for factor in raw_graph.factor_nodes if factor.type == "equiv_constraint"
    ]
    assert len(pairwise_equiv_factors) == 3
    assert all(len(factor.premises) == 2 for factor in pairwise_equiv_factors)


def test_adapter_resolves_unambiguous_short_prefixes():
    pkg = _load_galileo()
    raw_graph = build_raw_graph(pkg)
    canonicalization = build_singleton_local_graph(raw_graph)
    full_parameterization = derive_local_parameterization(pkg, canonicalization.local_graph)

    short_node_priors = {
        node_id[:10]: prior for node_id, prior in full_parameterization.node_priors.items()
    }
    short_factor_params = {
        factor_id[:10]: params
        for factor_id, params in full_parameterization.factor_parameters.items()
    }
    short_parameterization = LocalParameterization(
        graph_hash=full_parameterization.graph_hash,
        node_priors=short_node_priors,
        factor_parameters={
            factor_id: FactorParams(conditional_probability=params.conditional_probability)
            for factor_id, params in short_factor_params.items()
        },
    )

    adapted = adapt_local_graph_to_factor_graph(
        canonicalization.local_graph, short_parameterization
    )
    assert len(adapted.factor_graph.variables) == len(canonicalization.local_graph.knowledge_nodes)


def test_adapter_builds_factor_graph_and_bp_runs():
    pkg = _load_galileo()
    raw_graph = build_raw_graph(pkg)
    canonicalization = build_singleton_local_graph(raw_graph)
    parameterization = derive_local_parameterization(pkg, canonicalization.local_graph)
    adapted = adapt_local_graph_to_factor_graph(canonicalization.local_graph, parameterization)

    assert len(adapted.factor_graph.variables) == len(canonicalization.local_graph.knowledge_nodes)
    assert len(adapted.factor_graph.factors) == len(canonicalization.local_graph.factor_nodes)
    assert any("gate_var" in factor for factor in adapted.factor_graph.factors)

    beliefs = BeliefPropagation().run(adapted.factor_graph)
    assert beliefs
    assert len(beliefs) == len(adapted.factor_graph.variables)


def test_build_raw_graph_reads_lambda_args_from_chain_surface():
    module = _parse_module(
        {
            "type": "reasoning_module",
            "name": "m",
            "premises": [
                {"type": "claim", "name": "base", "content": "Base premise", "prior": 0.7},
                {"type": "setting", "name": "regime", "content": "Relevant regime", "prior": 0.9},
            ],
            "chains": [
                {
                    "name": "demo_chain",
                    "steps": [
                        {
                            "id": "obs",
                            "type": "claim",
                            "content": "Observation",
                            "refs": [
                                {"ref": "base", "dependency": "direct"},
                                {"ref": "regime", "dependency": "indirect"},
                            ],
                            "prior": 0.61,
                        }
                    ],
                    "conclusion": {
                        "name": "final_claim",
                        "type": "claim",
                        "content": "Final conclusion",
                        "refs": [{"ref": "obs", "dependency": "direct"}],
                        "prior": 0.84,
                    },
                }
            ],
            "export": ["final_claim"],
        }
    )
    pkg = Package(name="demo_pkg", loaded_modules=[module])

    raw_graph = build_raw_graph(pkg)

    reasoning_factor = next(
        factor for factor in raw_graph.factor_nodes if factor.type == "reasoning"
    )
    raw_nodes = {
        node.source_refs[0].knowledge_name: node.raw_node_id for node in raw_graph.knowledge_nodes
    }
    assert reasoning_factor.premises == [raw_nodes["base"], raw_nodes["demo_chain__obs"]]
    assert reasoning_factor.contexts == [raw_nodes["regime"]]
    assert reasoning_factor.conclusion == raw_nodes["final_claim"]


def test_build_raw_graph_legacy_lambda_uses_previous_ref_and_ignores_unknown_refs():
    module = _parse_module(
        {
            "type": "reasoning_module",
            "name": "m",
            "premises": [
                {"type": "claim", "name": "base", "content": "Base premise", "prior": 0.7}
            ],
            "chains": [
                {
                    "name": "legacy_chain",
                    "steps": [
                        {
                            "id": "mid",
                            "type": "claim",
                            "reasoning": "Derive the bridge from the base premise.",
                            "refs": ["base"],
                            "prior": 0.61,
                        }
                    ],
                    "conclusion": {
                        "name": "final_claim",
                        "type": "claim",
                        "content": "Final conclusion",
                        "refs": [
                            {"ref": "mid", "dependency": "direct"},
                            {"ref": "missing_local", "dependency": "indirect"},
                        ],
                        "prior": 0.84,
                    },
                }
            ],
            "export": ["final_claim"],
        }
    )
    pkg = Package(name="demo_pkg", loaded_modules=[module])

    raw_graph = build_raw_graph(pkg)
    factors = {factor.source_ref.knowledge_name: factor for factor in raw_graph.factor_nodes}
    raw_nodes = {
        node.source_refs[0].knowledge_name: node.raw_node_id for node in raw_graph.knowledge_nodes
    }

    first = factors["legacy_chain"]
    assert first.premises == [raw_nodes["base"], raw_nodes["legacy_chain__mid"]]
    assert first.contexts == []
    assert first.conclusion == raw_nodes["final_claim"]


def test_graph_ir_step_args_helper_covers_apply_explicit_and_legacy_lambda():
    from libs.graph_ir.build import _step_args
    from libs.lang.models import Arg, ChainExpr, StepApply

    apply = StepApply(
        step=1,
        apply="reason_about",
        args=[Arg(ref="a", dependency="direct")],
    )
    apply_chain = ChainExpr(name="apply_chain", steps=[apply])
    assert _step_args(apply_chain, apply)[0].ref == "a"

    explicit_lambda = StepLambda(
        step=3,
        **{"lambda": "explicit"},
        args=[Arg(ref="b", dependency="indirect")],
        prior=0.8,
    )
    explicit_chain = ChainExpr(name="explicit_chain", steps=[explicit_lambda])
    assert _step_args(explicit_chain, explicit_lambda)[0].ref == "b"

    legacy_lambda = StepLambda(step=3, **{"lambda": "legacy"}, prior=0.8)
    legacy_chain = ChainExpr(
        name="legacy_chain",
        steps=[StepRef(step=1, ref="base"), legacy_lambda, StepRef(step=4, ref="out")],
    )
    assert _step_args(legacy_chain, legacy_lambda)[0].ref == "base"
