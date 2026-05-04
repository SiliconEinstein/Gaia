"""Milestone B formula lowering tests."""

from gaia.lang import (
    ClaimKind,
    ClaimAtom,
    Domain,
    Forall,
    PredicateSymbol,
    UserPredicate,
    Variable,
    claim,
    forall,
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

    assert len(implication_ops) == 2
    assert not [
        op
        for op in artifact.graph.operators
        if op.operator == "conjunction"
        and (op.metadata or {}).get("formula_lowering") == "forall_grounding"
    ]


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
