import pytest

from gaia.lang import Claim, and_, or_
from gaia.lang.compiler import compile_package_artifact
from gaia.lang.runtime.package import CollectedPackage


def test_claim_boolean_truth_value_is_not_allowed():
    a = Claim("A.")
    with pytest.raises(TypeError, match="Gaia logical expressions"):
        bool(a)


def test_claim_logical_operator_overloads_create_expression_helpers():
    a = Claim("A.")
    b = Claim("B.")

    not_a = ~a
    both = a & b
    either = a | b

    assert not_a.metadata["helper_kind"] == "negation_result"
    assert both.metadata["helper_kind"] == "conjunction_result"
    assert either.metadata["helper_kind"] == "disjunction_result"
    assert not_a.metadata["review"] is False
    assert both.metadata["review"] is False
    assert either.metadata["review"] is False


def test_explicit_and_or_functions_accept_multiple_claims():
    a = Claim("A.")
    b = Claim("B.")
    c = Claim("C.")

    both = and_(a, b, c)
    either = or_(a, b, c)

    assert both.metadata["helper_kind"] == "conjunction_result"
    assert either.metadata["helper_kind"] == "disjunction_result"


def test_propositional_functions_reject_non_claim_inputs():
    a = Claim("A.")
    with pytest.raises(TypeError, match="Claim"):
        and_(a, object())
    with pytest.raises(TypeError, match="Claim"):
        or_(a, object())


def test_compile_propositional_expression_helpers_to_nonreviewed_operators():
    with CollectedPackage("prop_pkg") as pkg:
        a = Claim("A.")
        a.label = "a"
        b = Claim("B.")
        b.label = "b"
        not_a = ~a
        not_a.label = "not_a"
        both = a & b
        both.label = "both"
        either = a | b
        either.label = "either"

    compiled = compile_package_artifact(pkg)
    by_conclusion = {op.conclusion: op for op in compiled.graph.operators}

    assert by_conclusion["github:prop_pkg::not_a"].operator == "negation"
    assert by_conclusion["github:prop_pkg::not_a"].variables == ["github:prop_pkg::a"]
    assert by_conclusion["github:prop_pkg::both"].operator == "conjunction"
    assert by_conclusion["github:prop_pkg::either"].operator == "disjunction"
    assert all("action_label" not in (op.metadata or {}) for op in compiled.graph.operators)
    assert compiled.review is not None
    assert compiled.review.reviews == []
