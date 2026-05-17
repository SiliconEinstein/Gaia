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
