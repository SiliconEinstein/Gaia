"""Milestone B formula lowering tests."""

import pytest

from gaia.engine.bp.exact import exact_inference
from gaia.engine.bp.factor_graph import FactorType
from gaia.engine.bp.lowering import lower_local_graph
from gaia.engine.ir import default_resolution_policy
from gaia.engine.lang import (
    ClaimAtom,
    ClaimKind,
    Constant,
    Domain,
    Equals,
    Exists,
    Forall,
    PredicateSymbol,
    Probability,
    UserPredicate,
    Variable,
    claim,
    forall,
    implies,
    land,
    register_prior,
)
from gaia.engine.lang.compiler.compile import compile_package_artifact
from gaia.engine.lang.dsl.register_prior import resolve_priors_to_metadata
from gaia.engine.lang.runtime.knowledge import _current_package
from gaia.engine.lang.runtime.package import CollectedPackage


def _formula_graph_for(artifact, source_claim_id):
    return next(
        graph for graph in artifact.graph.formula_graphs if graph.source_claim == source_claim_id
    )


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


def test_repeated_predicate_formula_builds_one_canonical_atom_node():
    pkg = CollectedPackage(name="formula_graph_repeated_pkg", namespace="t")
    token = _current_package.set(pkg)
    try:
        particle = Domain(content="Particles", members=["p1", "p2"])
        x = Variable(symbol="x", domain=particle)
        stable = PredicateSymbol(name="Stable", arg_domains=(particle,))
        repeated = claim(
            "Stable x appears twice.",
            formula=land(UserPredicate(stable, (x,)), UserPredicate(stable, (x,))),
        )
        repeated.label = "repeated"
    finally:
        _current_package.reset(token)

    artifact = compile_package_artifact(pkg)
    graph = _formula_graph_for(artifact, "t:formula_graph_repeated_pkg::repeated")

    predicate_nodes = [
        node
        for node in graph.nodes
        if node.kind == "atom" and node.descriptor.get("kind") == "predicate"
    ]
    assert len(predicate_nodes) == 1

    root_edges = [
        edge for edge in graph.edges if edge.source == graph.root and edge.role == "operand"
    ]
    assert len(root_edges) == 2
    assert {edge.target for edge in root_edges} == {predicate_nodes[0].id}


def test_formula_graph_records_nested_connective_shape():
    pkg = CollectedPackage(name="formula_graph_nested_pkg", namespace="t")
    token = _current_package.set(pkg)
    try:
        a = claim("A.")
        a.label = "a"
        b = claim("B.")
        b.label = "b"
        c = claim("C.")
        c.label = "c"
        nested = claim(
            "A and B imply C.",
            formula=implies(land(ClaimAtom(a), ClaimAtom(b)), ClaimAtom(c)),
        )
        nested.label = "nested"
    finally:
        _current_package.reset(token)

    artifact = compile_package_artifact(pkg)
    graph = _formula_graph_for(artifact, "t:formula_graph_nested_pkg::nested")
    nodes = {node.id: node for node in graph.nodes}
    root = nodes[graph.root]

    assert root.kind == "op"
    assert root.descriptor["operator"] == "implication"
    root_edges = {edge.role: edge for edge in graph.edges if edge.source == graph.root}
    assert set(root_edges) == {"antecedent", "consequent"}
    antecedent = nodes[root_edges["antecedent"].target]
    assert antecedent.kind == "op"
    assert antecedent.descriptor["operator"] == "conjunction"


def test_quantifier_formula_graph_preserves_finite_grounding_behavior():
    pkg = CollectedPackage(name="formula_graph_forall_pkg", namespace="t")
    token = _current_package.set(pkg)
    try:
        particle = Domain(content="Particles", members=["p1", "p2"])
        x = Variable(symbol="x", domain=particle)
        stable = PredicateSymbol(name="Stable", arg_domains=(particle,))
        universal = claim(
            "Every particle is stable.",
            formula=forall(x, UserPredicate(stable, (x,))),
            kind=ClaimKind.QUANTIFIED,
        )
        universal.label = "stable_all"
    finally:
        _current_package.reset(token)

    artifact = compile_package_artifact(pkg)
    graph = _formula_graph_for(artifact, "t:formula_graph_forall_pkg::stable_all")
    root = next(node for node in graph.nodes if node.id == graph.root)

    assert root.kind == "quantifier"
    assert root.descriptor["quantifier"] == "forall"
    assert {edge.role for edge in graph.edges if edge.source == graph.root} == {
        "bound_variable",
        "body",
    }
    assert [
        s
        for s in artifact.graph.strategies
        if (s.metadata or {}).get("formula_lowering") == "forall_grounding"
    ]


def test_cross_graph_same_atom_uses_same_formula_node_id():
    pkg = CollectedPackage(name="formula_graph_cross_pkg", namespace="t")
    token = _current_package.set(pkg)
    try:
        particle = Domain(content="Particles", members=["p1", "p2"])
        x = Variable(symbol="x", domain=particle)
        stable = PredicateSymbol(name="Stable", arg_domains=(particle,))
        first = claim("Stable x, first.", formula=UserPredicate(stable, (x,)))
        first.label = "first"
        second = claim("Stable x, second.", formula=UserPredicate(stable, (x,)))
        second.label = "second"
    finally:
        _current_package.reset(token)

    artifact = compile_package_artifact(pkg)
    first_graph = _formula_graph_for(artifact, "t:formula_graph_cross_pkg::first")
    second_graph = _formula_graph_for(artifact, "t:formula_graph_cross_pkg::second")

    first_atom = next(node for node in first_graph.nodes if node.kind == "atom")
    second_atom = next(node for node in second_graph.nodes if node.kind == "atom")
    assert first_atom.id == second_atom.id
    assert first_graph.source_claim != second_graph.source_claim


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


def test_top_level_implies_formula_preserves_source_claim_prior():
    pkg = CollectedPackage(name="formula_implies_pkg", namespace="t")
    token = _current_package.set(pkg)
    try:
        a = claim("A.")
        a.label = "a"
        register_prior(a, 0.6, justification="test fixture")
        b = claim("B.")
        b.label = "b"
        register_prior(b, 0.4, justification="test fixture")
        rule = claim(
            "A implies B.",
            formula=implies(ClaimAtom(a), ClaimAtom(b)),
        )
        rule.label = "a_implies_b"
        register_prior(rule, 0.7, justification="test fixture")
    finally:
        _current_package.reset(token)

    resolve_priors_to_metadata(pkg.knowledge, default_resolution_policy())
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
        a = claim("A.")
        a.label = "a"
        register_prior(a, 0.8, justification="test fixture")
        alias = claim("Alias of A.", formula=ClaimAtom(a))
        alias.label = "alias"
        register_prior(alias, 0.2, justification="test fixture")
    finally:
        _current_package.reset(token)

    resolve_priors_to_metadata(pkg.knowledge, default_resolution_policy())
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
