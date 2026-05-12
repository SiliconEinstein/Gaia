"""Milestone B formula lowering tests."""

import pytest

from gaia.bp.exact import exact_inference
from gaia.bp.factor_graph import FactorType
from gaia.bp.lowering import lower_local_graph
from gaia.lang import (
    Causes,
    ClaimAtom,
    ClaimKind,
    Constant,
    Domain,
    Equals,
    Exists,
    Forall,
    PredicateSymbol,
    Probability,
    Real,
    UserPredicate,
    Variable,
    claim,
    forall,
    implies,
    land,
)
from gaia.lang.compiler.compile import compile_package_artifact
from gaia.lang.runtime.knowledge import _current_package
from gaia.lang.runtime.package import CollectedPackage


def test_formula_dsl_helpers_construct_formula_ast():
    particle = Domain(content="Particles", members=["p1", "p2"])
    x = Variable(symbol="x", domain=particle)
    stable = PredicateSymbol(name="Stable", arg_domains=(particle,))

    formula = forall(x, land(UserPredicate(stable, (x,)), UserPredicate(stable, (x,))))

    assert isinstance(formula, Forall)
    assert formula.variable is x
    assert len(formula.body.operands) == 2


def test_forall_lowers_to_implication_per_domain_member_not_conjunction():
    pkg = CollectedPackage(name="formula_forall_pkg", namespace="t")
    token = _current_package.set(pkg)
    try:
        particle = Domain(content="Particles", members=["p1", "p2"])
        x = Variable(symbol="x", domain=particle)
        stable = PredicateSymbol(name="Stable", arg_domains=(particle,))
        universal = claim(
            "Every particle is stable.",
            formula=Forall(variable=x, body=UserPredicate(stable, (x,))),
            kind=ClaimKind.QUANTIFIED,
            prior=0.9,
        )
        universal.label = "stable_all"
    finally:
        _current_package.reset(token)

    artifact = compile_package_artifact(pkg)
    universal_id = "t:formula_forall_pkg::stable_all"
    instance_claims = [
        k
        for k in artifact.graph.knowledges
        if (k.metadata or {}).get("formula_lowering") == "forall_instance"
    ]
    assert len(instance_claims) == 2
    assert {k.metadata["binding"]["value"] for k in instance_claims} == {"p1", "p2"}
    assert {k.metadata["source_claim"] for k in instance_claims} == {universal_id}
    assert {k.metadata["formula_atom"]["kind"] for k in instance_claims} == {"predicate"}
    assert {k.metadata["formula_atom"]["symbol"]["name"] for k in instance_claims} == {"Stable"}
    assert {k.metadata["formula_atom"]["args"][0]["value"] for k in instance_claims} == {
        "p1",
        "p2",
    }
    assert {(k.parameters[0].name, k.parameters[0].value) for k in instance_claims} == {
        ("x", "p1"),
        ("x", "p2"),
    }

    formula_strategies = [
        s
        for s in artifact.graph.strategies
        if (s.metadata or {}).get("formula_lowering") == "forall_grounding"
    ]
    assert len(formula_strategies) == 2
    assert {s.premises[0] for s in formula_strategies} == {universal_id}
    assert {s.conclusion for s in formula_strategies} == {k.id for k in instance_claims}

    implication_ops = []
    for strategy in formula_strategies:
        ops = strategy.formal_expr.operators
        assert len(ops) == 1
        op = ops[0]
        assert op.operator == "implication"
        assert op.variables == [universal_id, strategy.conclusion]
        implication_ops.append(op)

        helper = next(k for k in artifact.graph.knowledges if k.id == op.conclusion)
        assert helper.metadata["helper_kind"] == "implication_result"
        assert "prior" not in helper.metadata

    assert len(implication_ops) == 2
    assert not [
        op
        for op in artifact.graph.operators
        if op.operator == "conjunction"
        and (op.metadata or {}).get("formula_lowering") == "forall_grounding"
    ]

    fg = lower_local_graph(artifact.graph)
    instance_ids = {k.id for k in instance_claims}
    formula_factors = [f for f in fg.factors if f.conclusion in instance_ids]
    assert len(formula_factors) == 2
    assert {f.factor_type for f in formula_factors} == {FactorType.CONDITIONAL}
    beliefs, _ = exact_inference(fg)
    assert beliefs[universal_id] == pytest.approx(0.9)


def test_exists_lowers_to_disjunction_over_domain_instances():
    pkg = CollectedPackage(name="formula_exists_pkg", namespace="t")
    token = _current_package.set(pkg)
    try:
        particle = Domain(content="Particles", members=["p1", "p2"])
        x = Variable(symbol="x", domain=particle)
        stable = PredicateSymbol(name="Stable", arg_domains=(particle,))
        existential = claim(
            "Some particle is stable.",
            formula=Exists(variable=x, body=UserPredicate(stable, (x,))),
            kind=ClaimKind.QUANTIFIED,
            prior=0.6,
        )
        existential.label = "stable_some"
    finally:
        _current_package.reset(token)

    artifact = compile_package_artifact(pkg)
    source_id = "t:formula_exists_pkg::stable_some"
    instance_claims = [
        k
        for k in artifact.graph.knowledges
        if (k.metadata or {}).get("formula_lowering") == "exists_instance"
    ]
    assert len(instance_claims) == 2
    assert {k.metadata["binding"]["value"] for k in instance_claims} == {"p1", "p2"}
    assert {k.metadata["source_claim"] for k in instance_claims} == {source_id}
    assert {k.metadata["formula_atom"]["kind"] for k in instance_claims} == {"predicate"}
    assert {k.metadata["formula_atom"]["symbol"]["name"] for k in instance_claims} == {"Stable"}
    assert {k.metadata["formula_atom"]["args"][0]["value"] for k in instance_claims} == {
        "p1",
        "p2",
    }
    assert {(k.parameters[0].name, k.parameters[0].value) for k in instance_claims} == {
        ("x", "p1"),
        ("x", "p2"),
    }

    op = next(
        op
        for op in artifact.graph.operators
        if (op.metadata or {}).get("formula_lowering") == "exists_grounding"
    )
    assert op.operator == "disjunction"
    assert set(op.variables) == {k.id for k in instance_claims}
    assert op.conclusion == source_id
    assert [
        s
        for s in artifact.graph.strategies
        if (s.metadata or {}).get("formula_lowering") == "exists_grounding"
    ] == []


def test_singleton_exists_lowers_to_equivalence_with_grounded_body():
    pkg = CollectedPackage(name="formula_exists_singleton_pkg", namespace="t")
    token = _current_package.set(pkg)
    try:
        particle = Domain(content="Particles", members=["p1"])
        x = Variable(symbol="x", domain=particle)
        stable = PredicateSymbol(name="Stable", arg_domains=(particle,))
        existential = claim(
            "Some particle is stable.",
            formula=Exists(variable=x, body=UserPredicate(stable, (x,))),
            kind=ClaimKind.QUANTIFIED,
            prior=0.6,
        )
        existential.label = "stable_some"
    finally:
        _current_package.reset(token)

    artifact = compile_package_artifact(pkg)
    source_id = "t:formula_exists_singleton_pkg::stable_some"
    instance = next(
        k
        for k in artifact.graph.knowledges
        if (k.metadata or {}).get("formula_lowering") == "exists_instance"
    )
    assert instance.metadata["formula_atom"]["symbol"]["name"] == "Stable"
    assert instance.metadata["formula_atom"]["args"][0]["value"] == "p1"

    op = next(
        op
        for op in artifact.graph.operators
        if (op.metadata or {}).get("formula_lowering") == "exists_grounding"
    )
    assert op.operator == "equivalence"
    assert set(op.variables) == {source_id, instance.id}
    helper = next(k for k in artifact.graph.knowledges if k.id == op.conclusion)
    assert helper.metadata["helper_kind"] == "equivalence_result"


def test_land_claim_atom_formula_lowers_to_conjunction_operator():
    pkg = CollectedPackage(name="formula_land_pkg", namespace="t")
    token = _current_package.set(pkg)
    try:
        a = claim("A.")
        a.label = "a"
        b = claim("B.")
        b.label = "b"
        both = claim("A and B.", formula=land(ClaimAtom(a), ClaimAtom(b)))
        both.label = "both"
    finally:
        _current_package.reset(token)

    artifact = compile_package_artifact(pkg)
    op = next(
        op
        for op in artifact.graph.operators
        if (op.metadata or {}).get("formula_lowering") == "connective"
    )

    assert op.operator == "conjunction"
    assert op.variables == ["t:formula_land_pkg::a", "t:formula_land_pkg::b"]
    assert op.conclusion == "t:formula_land_pkg::both"


def test_top_level_equals_formula_records_binding_without_orphan_atom():
    pkg = CollectedPackage(name="formula_equals_pkg", namespace="t")
    token = _current_package.set(pkg)
    try:
        p = Variable(symbol="p", domain=Probability)
        value = claim(
            "The success probability is 0.75.",
            formula=Equals(p, Constant(0.75, Probability)),
            kind=ClaimKind.PARAMETER,
            prior=0.8,
        )
        value.label = "p_value"
    finally:
        _current_package.reset(token)

    artifact = compile_package_artifact(pkg)
    source = next(k for k in artifact.graph.knowledges if k.id == "t:formula_equals_pkg::p_value")

    assert source.parameters[0].name == "p"
    assert source.parameters[0].type == "Probability"
    assert source.parameters[0].value == 0.75
    assert source.metadata["formula_lowering"] == "atom"
    assert source.metadata["formula_atom"]["kind"] == "equals"
    assert source.metadata["formula_bindings"] == [
        {
            "symbol": "p",
            "domain": "Probability",
            "value": 0.75,
            "source": "formula",
        }
    ]
    assert not [
        k
        for k in artifact.graph.knowledges
        if (k.metadata or {}).get("generated_kind") == "formula_atom"
    ]
    assert artifact.graph.operators == []
    assert artifact.graph.strategies == []


def test_top_level_causes_formula_records_causal_marker_without_implication():
    pkg = CollectedPackage(name="formula_causes_pkg", namespace="t")
    token = _current_package.set(pkg)
    try:
        co2 = Variable(symbol="co2", domain=Real)
        temp = Variable(symbol="temp", domain=Real)
        causal = claim(
            "CO2 level causes temperature change.",
            formula=Causes(co2, temp),
            kind=ClaimKind.CAUSAL,
            prior=0.9,
        )
        causal.label = "co2_causes_temp"
    finally:
        _current_package.reset(token)

    artifact = compile_package_artifact(pkg)
    source = next(
        k for k in artifact.graph.knowledges if k.id == "t:formula_causes_pkg::co2_causes_temp"
    )

    assert source.metadata["formula_lowering"] == "atom"
    assert source.metadata["formula_atom"]["kind"] == "causes"
    assert source.metadata["causal"] == {
        "cause": {"kind": "variable", "symbol": "co2", "domain": "Real"},
        "effect": {"kind": "variable", "symbol": "temp", "domain": "Real"},
    }
    assert not [
        k
        for k in artifact.graph.knowledges
        if (k.metadata or {}).get("generated_kind") == "formula_atom"
    ]
    assert artifact.graph.operators == []
    assert artifact.graph.strategies == []


def test_top_level_implies_formula_preserves_source_claim_prior():
    pkg = CollectedPackage(name="formula_implies_pkg", namespace="t")
    token = _current_package.set(pkg)
    try:
        a = claim("A.", prior=0.6)
        a.label = "a"
        b = claim("B.", prior=0.4)
        b.label = "b"
        rule = claim(
            "A implies B.",
            formula=implies(ClaimAtom(a), ClaimAtom(b)),
            prior=0.7,
        )
        rule.label = "a_implies_b"
    finally:
        _current_package.reset(token)

    artifact = compile_package_artifact(pkg)
    rule_id = "t:formula_implies_pkg::a_implies_b"
    op = next(
        op
        for op in artifact.graph.operators
        if (op.metadata or {}).get("formula_lowering") == "connective"
    )
    assert op.operator == "implication"
    assert op.variables == ["t:formula_implies_pkg::a", "t:formula_implies_pkg::b"]
    assert op.conclusion == rule_id

    fg = lower_local_graph(artifact.graph)
    assert fg.variables[rule_id] == pytest.approx(0.7)
    assert fg.unary_factors[rule_id] == pytest.approx(0.7)


def test_top_level_claim_atom_lowers_to_equivalence_alias():
    pkg = CollectedPackage(name="formula_claim_atom_pkg", namespace="t")
    token = _current_package.set(pkg)
    try:
        a = claim("A.", prior=0.8)
        a.label = "a"
        alias = claim("Alias of A.", formula=ClaimAtom(a), prior=0.2)
        alias.label = "alias"
    finally:
        _current_package.reset(token)

    artifact = compile_package_artifact(pkg)
    alias_id = "t:formula_claim_atom_pkg::alias"
    source = next(k for k in artifact.graph.knowledges if k.id == alias_id)
    assert source.metadata["formula_atom"] == {
        "kind": "claim",
        "qid": "t:formula_claim_atom_pkg::a",
    }

    op = next(
        op
        for op in artifact.graph.operators
        if (op.metadata or {}).get("formula_lowering") == "claim_atom_alias"
    )
    assert op.operator == "equivalence"
    assert set(op.variables) == {"t:formula_claim_atom_pkg::a", alias_id}
    helper = next(k for k in artifact.graph.knowledges if k.id == op.conclusion)
    assert helper.metadata["helper_kind"] == "equivalence_result"
