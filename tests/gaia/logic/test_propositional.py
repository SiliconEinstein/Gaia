from sympy import Symbol

from gaia.lang import Claim, exclusive
from gaia.lang.compiler import compile_package_artifact
from gaia.lang.runtime.package import CollectedPackage
from gaia.logic import (
    are_equivalent,
    is_satisfiable,
    simplify_proposition,
    to_cnf_proposition,
)


def _kid(package: str, label: str) -> str:
    return f"github:{package}::{label}"


def test_simplify_proposition_collapses_double_negation():
    with CollectedPackage("logic_double_negation") as pkg:
        a = Claim("A.")
        a.label = "a"
        double = ~~a
        double.label = "double"

    graph = compile_package_artifact(pkg).graph

    assert simplify_proposition(graph, _kid("logic_double_negation", "double")) == Symbol(
        _kid("logic_double_negation", "a")
    )


def test_cnf_and_equivalence_use_demorgan_law():
    with CollectedPackage("logic_demorgan") as pkg:
        a = Claim("A.")
        a.label = "a"
        b = Claim("B.")
        b.label = "b"
        both = a & b
        both.label = "both"
        left = ~both
        left.label = "left"
        not_a = ~a
        not_a.label = "not_a"
        not_b = ~b
        not_b.label = "not_b"
        right = not_a | not_b
        right.label = "right"

    graph = compile_package_artifact(pkg).graph

    assert are_equivalent(graph, _kid("logic_demorgan", "left"), _kid("logic_demorgan", "right"))
    assert str(to_cnf_proposition(graph, _kid("logic_demorgan", "left"), simplify=True)) in {
        "~github:logic_demorgan::a | ~github:logic_demorgan::b",
        "~github:logic_demorgan::b | ~github:logic_demorgan::a",
    }


def test_satisfiability_detects_contradictory_formula():
    with CollectedPackage("logic_unsat") as pkg:
        a = Claim("A.")
        a.label = "a"
        not_a = ~a
        not_a.label = "not_a"
        impossible = a & not_a
        impossible.label = "impossible"

    graph = compile_package_artifact(pkg).graph

    assert is_satisfiable(graph, _kid("logic_unsat", "a"))
    assert not is_satisfiable(graph, _kid("logic_unsat", "impossible"))


def test_exclusive_relation_is_equivalent_to_or_and_not_both():
    with CollectedPackage("logic_exclusive") as pkg:
        a = Claim("A.")
        a.label = "a"
        b = Claim("B.")
        b.label = "b"
        one_of = exclusive(a, b, rationale="closed binary split")
        one_of.label = "one_of"
        either = a | b
        either.label = "either"
        both = a & b
        both.label = "both"
        not_both = ~both
        not_both.label = "not_both"
        formula = either & not_both
        formula.label = "formula"

    graph = compile_package_artifact(pkg).graph

    assert are_equivalent(graph, _kid("logic_exclusive", "one_of"), _kid("logic_exclusive", "formula"))
