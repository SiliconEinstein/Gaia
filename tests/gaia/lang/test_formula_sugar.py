"""Milestone B2 formula authoring sugar tests."""

import pytest

from gaia.bp.exact import exact_inference
from gaia.bp.lowering import lower_local_graph
from gaia.lang import (
    ClaimKind,
    Constant,
    Domain,
    Equals,
    Land,
    Nat,
    Probability,
    Real,
    Variable,
    causal,
    infer,
    observation,
    parameter,
)
from gaia.lang.compiler.compile import compile_package_artifact
from gaia.lang.runtime.knowledge import _current_package
from gaia.lang.runtime.package import CollectedPackage


def _compiled_knowledge_by_label(pkg: CollectedPackage):
    artifact = compile_package_artifact(pkg)
    return {k.label: k for k in artifact.graph.knowledges if k.label}


def test_parameter_sugar_constructs_parameter_claim_and_compiles_binding():
    pkg = CollectedPackage(name="formula_parameter_sugar_pkg", namespace="t")
    token = _current_package.set(pkg)
    try:
        p = Variable(symbol="p", domain=Probability)
        h = parameter(
            p,
            0.75,
            describe="Mendelian 3:1 segregation fixes P(dominant) at 0.75.",
            prior=0.5,
        )
        h.label = "mendelian_probability"
    finally:
        _current_package.reset(token)

    assert h.kind is ClaimKind.PARAMETER
    assert isinstance(h.formula, Equals)
    assert h.formula.left is p
    assert h.formula.right == Constant(0.75, Probability)

    source = _compiled_knowledge_by_label(pkg)["mendelian_probability"]
    assert [(p.name, p.type, p.value) for p in source.parameters] == [("p", "Probability", 0.75)]
    assert source.metadata["formula_bindings"] == [
        {"symbol": "p", "domain": "Probability", "value": 0.75, "source": "formula"}
    ]


def test_observation_sugar_records_multiple_primitive_bindings_on_source_claim():
    pkg = CollectedPackage(name="formula_observation_sugar_pkg", namespace="t")
    token = _current_package.set(pkg)
    try:
        n = Variable(symbol="n", domain=Nat, value=395)
        k = Variable(symbol="k", domain=Nat, value=295)
        obs = observation(
            n=n,
            k=k,
            describe="Observed 295 dominant phenotypes out of 395 F2 plants.",
            prior=0.95,
        )
        obs.label = "f2_count_observation"
    finally:
        _current_package.reset(token)

    assert obs.kind is ClaimKind.OBSERVATION
    assert isinstance(obs.formula, Land)
    assert len(obs.formula.operands) == 2

    artifact = compile_package_artifact(pkg)
    source = next(
        k
        for k in artifact.graph.knowledges
        if k.id == "t:formula_observation_sugar_pkg::f2_count_observation"
    )
    assert {(p.name, p.type, p.value) for p in source.parameters} == {
        ("n", "Nat", 395),
        ("k", "Nat", 295),
    }
    assert source.metadata["formula_bindings"] == [
        {"symbol": "n", "domain": "Nat", "value": 395, "source": "formula"},
        {"symbol": "k", "domain": "Nat", "value": 295, "source": "formula"},
    ]
    assert [
        k
        for k in artifact.graph.knowledges
        if (k.metadata or {}).get("generated_kind") == "formula_atom"
    ] == []
    assert [
        op
        for op in artifact.graph.operators
        if (op.metadata or {}).get("formula_lowering") == "connective"
    ] == []

    fg = lower_local_graph(artifact.graph)
    beliefs, _ = exact_inference(fg)
    assert beliefs[source.id] == pytest.approx(0.95)


def test_causal_sugar_constructs_causal_claim_and_compiles_marker():
    pkg = CollectedPackage(name="formula_causal_sugar_pkg", namespace="t")
    token = _current_package.set(pkg)
    try:
        co2 = Variable(symbol="co2", domain=Real)
        temp = Variable(symbol="temp", domain=Real)
        c = causal(
            co2,
            temp,
            describe="Rising CO2 causes increased global mean temperature.",
            prior=0.9,
        )
        c.label = "co2_causes_temp"
    finally:
        _current_package.reset(token)

    assert c.kind is ClaimKind.CAUSAL

    source = _compiled_knowledge_by_label(pkg)["co2_causes_temp"]
    assert source.metadata["formula_atom"]["kind"] == "causes"
    assert source.metadata["causal"] == {
        "cause": {"kind": "variable", "symbol": "co2", "domain": "Real"},
        "effect": {"kind": "variable", "symbol": "temp", "domain": "Real"},
    }


def test_formula_sugar_rejects_invalid_structured_inputs():
    p = Variable(symbol="p", domain=Probability)
    with pytest.raises(TypeError, match="either content or describe"):
        parameter(p, 0.75, content="p = 0.75", describe="duplicate")

    with pytest.raises(TypeError, match="expected a Variable"):
        parameter("p", 0.75)  # type: ignore[arg-type]

    finite = Domain(content="Finite", members=["a"])
    x = Variable(symbol="x", domain=finite)
    with pytest.raises(TypeError, match="PrimitiveType"):
        parameter(x, "a")

    valued = Variable(symbol="q", domain=Probability, value=0.25)
    with pytest.raises(ValueError, match="already has value"):
        parameter(valued, 0.75)

    with pytest.raises(ValueError, match="at least one"):
        observation()

    with pytest.raises(TypeError, match="must be a Variable"):
        observation(n=1)  # type: ignore[arg-type]

    with pytest.raises(ValueError, match="must have value set"):
        observation(n=Variable(symbol="n", domain=Nat))


def test_mendel_formula_sugar_compiles_with_likelihood_infer_action():
    pkg = CollectedPackage(name="formula_mendel_sugar_pkg", namespace="t")
    token = _current_package.set(pkg)
    try:
        p = Variable(symbol="p", domain=Probability)
        n = Variable(symbol="n", domain=Nat, value=395)
        k = Variable(symbol="k", domain=Nat, value=295)
        h = parameter(
            p,
            0.75,
            describe="Mendelian 3:1 segregation fixes P(dominant) at 0.75.",
            prior=0.5,
        )
        h.label = "mendelian_probability"
        d = observation(
            n=n,
            k=k,
            describe="Observed 295 dominant phenotypes out of 395 F2 plants.",
            prior=0.95,
        )
        d.label = "f2_count_observation"
        infer(
            d,
            hypothesis=h,
            p_e_given_h=0.024,
            p_e_given_not_h=0.5,
            rationale="Use the point binomial likelihood for the observed count.",
            label="mendel_count_likelihood",
        )
    finally:
        _current_package.reset(token)

    artifact = compile_package_artifact(pkg)
    by_label = {k.label: k for k in artifact.graph.knowledges if k.label}
    assert by_label["mendelian_probability"].parameters[0].value == 0.75
    assert {(p.name, p.value) for p in by_label["f2_count_observation"].parameters} == {
        ("n", 395),
        ("k", 295),
    }
    likelihoods = [
        k
        for k in artifact.graph.knowledges
        if (k.metadata or {}).get("helper_kind") == "likelihood"
    ]
    assert len(likelihoods) == 1
    assert (
        likelihoods[0].metadata["action_label"]
        == "t:formula_mendel_sugar_pkg::action::mendel_count_likelihood"
    )
