import pytest
from sympy import And, Implies, Not, Symbol

from gaia.engine.ir import FormulaGraph, FormulaNode, formula_node_id
from gaia.engine.ir.logic.diagnostics import (
    DiagnosticCondition,
    FormulaDiagnostic,
    FormulaDiagnosticReport,
    formula_graph_to_sympy,
    inspect_formula_graphs,
)
from gaia.engine.lang import (
    ClaimAtom,
    Domain,
    PredicateSymbol,
    UserPredicate,
    Variable,
    claim,
    forall,
    implies,
    land,
    lnot,
    lor,
)
from gaia.engine.lang.compiler import compile_package_artifact
from gaia.engine.lang.runtime.package import CollectedPackage


def _qid(package: str, label: str) -> str:
    return f"t:{package}::{label}"


def _formula_graph_for(artifact, source_claim_id: str):
    return next(
        formula_graph
        for formula_graph in artifact.graph.formula_graphs
        if formula_graph.source_claim == source_claim_id
    )


def test_formula_diagnostic_models_round_trip_json():
    condition = DiagnosticCondition(
        kind="joint_incompatibility",
        variables=["t:pkg::left", "t:pkg::right"],
        expression={
            "op": "and",
            "args": [{"var": "t:pkg::left"}, {"var": "t:pkg::right"}],
        },
        confidence_basis="hard_logic",
    )
    diagnostic = FormulaDiagnostic(
        code="cross_claim_incompatibility",
        severity="warning",
        scope="claim_pair",
        logic_strength="hard",
        source_claim="t:pkg::left",
        related_claims=["t:pkg::right"],
        formula_nodes=["fg:left", "fg:right"],
        condition=condition,
        message="Claims cannot both hold.",
    )
    report = FormulaDiagnosticReport(diagnostics=[diagnostic])

    round_tripped = FormulaDiagnosticReport.model_validate_json(report.model_dump_json())

    assert round_tripped == report
    assert round_tripped.has_fatal is False
    assert inspect_formula_graphs is not None


def test_formula_graph_to_sympy_projects_claim_atom_connectives():
    package = "formula_diag_projection"
    with CollectedPackage(package, namespace="t") as pkg:
        a = claim("A.")
        a.label = "a"
        b = claim("B.")
        b.label = "b"
        rule = claim(
            "A and not B implies A.",
            formula=implies(land(ClaimAtom(a), lnot(ClaimAtom(b))), ClaimAtom(a)),
        )
        rule.label = "rule"

    artifact = compile_package_artifact(pkg)
    formula_graph = _formula_graph_for(artifact, _qid(package, "rule"))

    expression = formula_graph_to_sympy(formula_graph)

    assert expression == Implies(
        And(Symbol(_qid(package, "a")), Not(Symbol(_qid(package, "b")))),
        Symbol(_qid(package, "a")),
    )


def test_formula_graph_to_sympy_returns_none_for_quantifier_root():
    package = "formula_diag_quantifier"
    with CollectedPackage(package, namespace="t") as pkg:
        domain = Domain(content="Particles", members=["p1"])
        x = Variable(symbol="x", domain=domain)
        stable = PredicateSymbol(name="Stable", arg_domains=(domain,))
        universal = claim(
            "All particles are stable.",
            formula=forall(x, UserPredicate(stable, (x,))),
        )
        universal.label = "universal"

    artifact = compile_package_artifact(pkg)
    formula_graph = _formula_graph_for(artifact, _qid(package, "universal"))

    assert formula_graph_to_sympy(formula_graph) is None


def test_formula_graph_to_sympy_rejects_missing_op_child_id():
    descriptor = {
        "kind": "op",
        "operator": "conjunction",
        "children": ["fg:missing"],
    }
    root = FormulaNode(
        id=formula_node_id(descriptor),
        kind="op",
        descriptor=descriptor,
    )
    graph = FormulaGraph(source_claim="t:pkg::bad", root=root.id, nodes=[root])

    with pytest.raises(ValueError, match="fg:missing"):
        formula_graph_to_sympy(graph)


def test_inspect_formula_graphs_reports_claim_local_unsat_as_fatal():
    package = "formula_diag_local_unsat"
    with CollectedPackage(package, namespace="t") as pkg:
        a = claim("A.")
        a.label = "a"
        impossible = claim("A and not A.", formula=land(ClaimAtom(a), lnot(ClaimAtom(a))))
        impossible.label = "impossible"

    report = inspect_formula_graphs(compile_package_artifact(pkg).graph, include_pairwise=False)

    diagnostic = next(d for d in report.diagnostics if d.code == "formula_unsat")
    assert diagnostic.severity == "fatal"
    assert diagnostic.scope == "claim"
    assert diagnostic.logic_strength == "hard"
    assert diagnostic.source_claim == _qid(package, "impossible")
    assert diagnostic.condition.kind == "formula_unsat"
    assert diagnostic.condition.expression == {"var": _qid(package, "impossible")}
    assert report.has_fatal is True


def test_inspect_formula_graphs_reports_claim_local_tautology_as_warning():
    package = "formula_diag_local_tautology"
    with CollectedPackage(package, namespace="t") as pkg:
        a = claim("A.")
        a.label = "a"
        tautology = claim("A or not A.", formula=lor(ClaimAtom(a), lnot(ClaimAtom(a))))
        tautology.label = "tautology"

    report = inspect_formula_graphs(compile_package_artifact(pkg).graph, include_pairwise=False)

    diagnostic = next(d for d in report.diagnostics if d.code == "formula_tautology")
    assert diagnostic.severity == "warning"
    assert diagnostic.scope == "claim"
    assert diagnostic.source_claim == _qid(package, "tautology")
    assert report.has_fatal is False


def test_inspect_formula_graphs_reports_redundant_operands_as_info():
    package = "formula_diag_redundant_operand"
    with CollectedPackage(package, namespace="t") as pkg:
        a = claim("A.")
        a.label = "a"
        repeated = claim("A and A.", formula=land(ClaimAtom(a), ClaimAtom(a)))
        repeated.label = "repeated"

    report = inspect_formula_graphs(compile_package_artifact(pkg).graph, include_pairwise=False)

    diagnostic = next(d for d in report.diagnostics if d.code == "formula_redundant_operand")
    assert diagnostic.severity == "info"
    assert diagnostic.scope == "claim"
    assert diagnostic.source_claim == _qid(package, "repeated")
    assert diagnostic.details["repeated_children"] == [_qid(package, "a")]


def test_pairwise_incompatibility_is_warning_with_bp_condition():
    package = "formula_diag_pair_incompat"
    with CollectedPackage(package, namespace="t") as pkg:
        a = claim("A.")
        a.label = "a"
        left = claim("A holds.", formula=ClaimAtom(a))
        left.label = "left"
        right = claim("A does not hold.", formula=lnot(ClaimAtom(a)))
        right.label = "right"

    report = inspect_formula_graphs(compile_package_artifact(pkg).graph)

    diagnostic = next(d for d in report.diagnostics if d.code == "cross_claim_incompatibility")
    assert diagnostic.severity == "warning"
    assert diagnostic.scope == "claim_pair"
    assert diagnostic.logic_strength == "hard"
    assert diagnostic.source_claim == _qid(package, "left")
    assert diagnostic.related_claims == [_qid(package, "right")]
    assert diagnostic.condition.kind == "joint_incompatibility"
    assert diagnostic.condition.expression == {
        "op": "and",
        "args": [{"var": _qid(package, "left")}, {"var": _qid(package, "right")}],
    }
    assert report.has_fatal is False


def test_pairwise_entailment_is_info_with_violation_condition():
    package = "formula_diag_pair_entailment"
    with CollectedPackage(package, namespace="t") as pkg:
        a = claim("A.")
        a.label = "a"
        b = claim("B.")
        b.label = "b"
        strong = claim("A and B.", formula=land(ClaimAtom(a), ClaimAtom(b)))
        strong.label = "strong"
        weak = claim("A.", formula=ClaimAtom(a))
        weak.label = "weak"

    report = inspect_formula_graphs(compile_package_artifact(pkg).graph)

    diagnostic = next(d for d in report.diagnostics if d.code == "cross_claim_entailment")
    assert diagnostic.severity == "info"
    assert diagnostic.source_claim == _qid(package, "strong")
    assert diagnostic.related_claims == [_qid(package, "weak")]
    assert diagnostic.condition.kind == "entailment_violation"
    assert diagnostic.condition.expression == {
        "op": "and",
        "args": [
            {"var": _qid(package, "strong")},
            {"op": "not", "arg": {"var": _qid(package, "weak")}},
        ],
    }


def test_pairwise_diagnostics_skip_disjoint_formulas():
    package = "formula_diag_pair_disjoint"
    with CollectedPackage(package, namespace="t") as pkg:
        a = claim("A.")
        a.label = "a"
        b = claim("B.")
        b.label = "b"
        left = claim("A holds.", formula=ClaimAtom(a))
        left.label = "left"
        right = claim("B holds.", formula=ClaimAtom(b))
        right.label = "right"

    report = inspect_formula_graphs(compile_package_artifact(pkg).graph)

    assert [d for d in report.diagnostics if d.scope == "claim_pair"] == []


def test_pairwise_diagnostics_skip_locally_unsat_formulas():
    package = "formula_diag_pair_skip_unsat"
    with CollectedPackage(package, namespace="t") as pkg:
        a = claim("A.")
        a.label = "a"
        impossible = claim("A and not A.", formula=land(ClaimAtom(a), lnot(ClaimAtom(a))))
        impossible.label = "impossible"
        ordinary = claim("A holds.", formula=ClaimAtom(a))
        ordinary.label = "ordinary"

    report = inspect_formula_graphs(compile_package_artifact(pkg).graph)

    assert any(d.code == "formula_unsat" and d.severity == "fatal" for d in report.diagnostics)
    assert [d for d in report.diagnostics if d.scope == "claim_pair"] == []
