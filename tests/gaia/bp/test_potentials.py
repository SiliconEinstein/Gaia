"""Unit tests for gaia.bp.potentials — potential function evaluation."""

import pytest

from gaia.bp.factor_graph import Factor, FactorType
from gaia.bp.potentials import (
    complement_potential,
    conditional_potential,
    conjunction_potential,
    contradiction_potential,
    disjunction_potential,
    equivalence_potential,
    evaluate_potential,
    implication_potential,
    soft_entailment_potential,
)

EPS = 2e-3  # potentials use soft binary ~0.999/0.001; need margin above that


# ── implication: ternary with helper H ──


def test_implication_h1_a1_b1():
    """H=1 (implication holds), A=1,B=1 → HIGH."""
    assert implication_potential({"A": 1, "B": 1, "H": 1}, "A", "B", "H") > 1 - EPS


def test_implication_h1_a1_b0_forbidden():
    """H=1 (implication holds), A=1,B=0 → LOW (forbidden)."""
    assert implication_potential({"A": 1, "B": 0, "H": 1}, "A", "B", "H") < EPS


def test_implication_h1_a0_b_any():
    """H=1, A=0 → B can be anything."""
    assert implication_potential({"A": 0, "B": 0, "H": 1}, "A", "B", "H") > 1 - EPS
    assert implication_potential({"A": 0, "B": 1, "H": 1}, "A", "B", "H") > 1 - EPS


def test_implication_h0_a1_b0_high():
    """H=0 (implication fails), A=1,B=0 → HIGH (complement)."""
    assert implication_potential({"A": 1, "B": 0, "H": 0}, "A", "B", "H") > 1 - EPS


def test_implication_h0_other_low():
    """H=0 (implication fails), any other assignment → LOW."""
    assert implication_potential({"A": 1, "B": 1, "H": 0}, "A", "B", "H") < EPS
    assert implication_potential({"A": 0, "B": 0, "H": 0}, "A", "B", "H") < EPS
    assert implication_potential({"A": 0, "B": 1, "H": 0}, "A", "B", "H") < EPS


# ── conjunction: M = AND(inputs) ──


def test_conjunction_all_true():
    assert conjunction_potential({"A": 1, "B": 1, "M": 1}, ["A", "B"], "M") > 1 - EPS


def test_conjunction_all_true_m0():
    assert conjunction_potential({"A": 1, "B": 1, "M": 0}, ["A", "B"], "M") < EPS


def test_conjunction_one_false_m0():
    assert conjunction_potential({"A": 1, "B": 0, "M": 0}, ["A", "B"], "M") > 1 - EPS


def test_conjunction_one_false_m1():
    assert conjunction_potential({"A": 1, "B": 0, "M": 1}, ["A", "B"], "M") < EPS


# ── disjunction: D = OR(inputs) ──


def test_disjunction_any_true():
    assert disjunction_potential({"A": 1, "B": 0, "D": 1}, ["A", "B"], "D") > 1 - EPS


def test_disjunction_all_false_d0():
    assert disjunction_potential({"A": 0, "B": 0, "D": 0}, ["A", "B"], "D") > 1 - EPS


def test_disjunction_all_false_d1():
    assert disjunction_potential({"A": 0, "B": 0, "D": 1}, ["A", "B"], "D") < EPS


def test_disjunction_any_true_d0():
    assert disjunction_potential({"A": 1, "B": 0, "D": 0}, ["A", "B"], "D") < EPS


# ── equivalence: H = (A == B) ──


def test_equivalence_same_h1():
    assert equivalence_potential({"A": 1, "B": 1, "H": 1}, "A", "B", "H") > 1 - EPS
    assert equivalence_potential({"A": 0, "B": 0, "H": 1}, "A", "B", "H") > 1 - EPS


def test_equivalence_different_h0():
    assert equivalence_potential({"A": 1, "B": 0, "H": 0}, "A", "B", "H") > 1 - EPS


def test_equivalence_same_h0():
    assert equivalence_potential({"A": 1, "B": 1, "H": 0}, "A", "B", "H") < EPS


# ── contradiction: H = NOT(A AND B) ──


def test_contradiction_both_true_h0():
    assert contradiction_potential({"A": 1, "B": 1, "H": 0}, "A", "B", "H") > 1 - EPS


def test_contradiction_both_true_h1():
    assert contradiction_potential({"A": 1, "B": 1, "H": 1}, "A", "B", "H") < EPS


def test_contradiction_not_both_h1():
    assert contradiction_potential({"A": 1, "B": 0, "H": 1}, "A", "B", "H") > 1 - EPS
    assert contradiction_potential({"A": 0, "B": 0, "H": 1}, "A", "B", "H") > 1 - EPS


# ── complement: H = (A XOR B) ──


def test_complement_different_h1():
    assert complement_potential({"A": 1, "B": 0, "H": 1}, "A", "B", "H") > 1 - EPS
    assert complement_potential({"A": 0, "B": 1, "H": 1}, "A", "B", "H") > 1 - EPS


def test_complement_same_h0():
    assert complement_potential({"A": 1, "B": 1, "H": 0}, "A", "B", "H") > 1 - EPS
    assert complement_potential({"A": 0, "B": 0, "H": 0}, "A", "B", "H") > 1 - EPS


# ── soft_entailment ──


def test_soft_entailment_premise_true():
    p1, p2 = 0.9, 0.95
    assert soft_entailment_potential({"M": 1, "C": 1}, "M", "C", p1, p2) == pytest.approx(p1)
    assert soft_entailment_potential({"M": 1, "C": 0}, "M", "C", p1, p2) == pytest.approx(1 - p1)


def test_soft_entailment_premise_false():
    p1, p2 = 0.9, 0.95
    assert soft_entailment_potential({"M": 0, "C": 0}, "M", "C", p1, p2) == pytest.approx(p2)
    assert soft_entailment_potential({"M": 0, "C": 1}, "M", "C", p1, p2) == pytest.approx(1 - p2)


# ── conditional (CPT) ──


def test_conditional_two_parents():
    # P(C=1|A=0,B=0)=0.1, P(C=1|A=1,B=0)=0.3, P(C=1|A=0,B=1)=0.6, P(C=1|A=1,B=1)=0.9
    cpt = (0.1, 0.3, 0.6, 0.9)
    assert conditional_potential({"A": 0, "B": 0, "C": 1}, ["A", "B"], "C", cpt) == pytest.approx(
        0.1
    )
    assert conditional_potential({"A": 1, "B": 1, "C": 1}, ["A", "B"], "C", cpt) == pytest.approx(
        0.9
    )
    assert conditional_potential({"A": 1, "B": 1, "C": 0}, ["A", "B"], "C", cpt) == pytest.approx(
        0.1
    )


# ── evaluate_potential dispatcher ──


def test_evaluate_potential_routes_correctly():
    factor = Factor(
        factor_id="f1",
        factor_type=FactorType.IMPLICATION,
        variables=["A", "B"],
        conclusion="H",
    )
    assert evaluate_potential(factor, {"A": 1, "B": 1, "H": 1}) > 1 - EPS
    assert evaluate_potential(factor, {"A": 1, "B": 0, "H": 1}) < EPS
    assert evaluate_potential(factor, {"A": 1, "B": 0, "H": 0}) > 1 - EPS


def test_evaluate_potential_soft_entailment():
    factor = Factor(
        factor_id="f1",
        factor_type=FactorType.SOFT_ENTAILMENT,
        variables=["M"],
        conclusion="C",
        p1=0.8,
        p2=0.9,
    )
    assert evaluate_potential(factor, {"M": 1, "C": 1}) == pytest.approx(0.8)


def test_evaluate_potential_conditional():
    factor = Factor(
        factor_id="f1",
        factor_type=FactorType.CONDITIONAL,
        variables=["A"],
        conclusion="B",
        cpt=(0.2, 0.8),
    )
    assert evaluate_potential(factor, {"A": 0, "B": 1}) == pytest.approx(0.2)
    assert evaluate_potential(factor, {"A": 1, "B": 1}) == pytest.approx(0.8)
