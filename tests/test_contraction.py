"""Tests for gaia.bp.contraction (tensor-based CPT computation)."""

from __future__ import annotations

from gaia.bp.contraction import factor_to_tensor
from gaia.bp.factor_graph import CROMWELL_EPS, Factor, FactorGraph, FactorType

_HIGH = 1.0 - CROMWELL_EPS
_LOW = CROMWELL_EPS


def _almost(a, b, eps=1e-9):
    return abs(a - b) < eps


def test_factor_to_tensor_implication():
    f = Factor(
        factor_id="f1",
        factor_type=FactorType.IMPLICATION,
        variables=["A"],
        conclusion="B",
    )
    t, axes = factor_to_tensor(f)
    assert axes == ["A", "B"]
    assert t.shape == (2, 2)
    # Forbid A=1, B=0
    assert _almost(t[1, 0], _LOW)
    assert _almost(t[0, 0], _HIGH)
    assert _almost(t[0, 1], _HIGH)
    assert _almost(t[1, 1], _HIGH)


def test_factor_to_tensor_conjunction_two_inputs():
    f = Factor(
        factor_id="f1",
        factor_type=FactorType.CONJUNCTION,
        variables=["A", "B"],
        conclusion="M",
    )
    t, axes = factor_to_tensor(f)
    assert axes == ["A", "B", "M"]
    assert t.shape == (2, 2, 2)
    # M == (A AND B)
    assert _almost(t[0, 0, 0], _HIGH)
    assert _almost(t[0, 0, 1], _LOW)
    assert _almost(t[0, 1, 0], _HIGH)
    assert _almost(t[0, 1, 1], _LOW)
    assert _almost(t[1, 0, 0], _HIGH)
    assert _almost(t[1, 0, 1], _LOW)
    assert _almost(t[1, 1, 0], _LOW)
    assert _almost(t[1, 1, 1], _HIGH)


def test_factor_to_tensor_conjunction_three_inputs():
    f = Factor(
        factor_id="f1",
        factor_type=FactorType.CONJUNCTION,
        variables=["A", "B", "C"],
        conclusion="M",
    )
    t, axes = factor_to_tensor(f)
    assert axes == ["A", "B", "C", "M"]
    assert t.shape == (2, 2, 2, 2)
    assert _almost(t[1, 1, 1, 1], _HIGH)
    assert _almost(t[1, 1, 0, 0], _HIGH)
    assert _almost(t[1, 1, 1, 0], _LOW)
    assert _almost(t[0, 0, 0, 0], _HIGH)


def test_factor_to_tensor_disjunction():
    f = Factor(
        factor_id="f1",
        factor_type=FactorType.DISJUNCTION,
        variables=["A", "B"],
        conclusion="D",
    )
    t, axes = factor_to_tensor(f)
    assert axes == ["A", "B", "D"]
    # D == (A OR B)
    assert _almost(t[0, 0, 0], _HIGH)
    assert _almost(t[0, 0, 1], _LOW)
    assert _almost(t[0, 1, 1], _HIGH)
    assert _almost(t[1, 0, 1], _HIGH)
    assert _almost(t[1, 1, 1], _HIGH)
    assert _almost(t[1, 1, 0], _LOW)


def test_factor_to_tensor_equivalence():
    f = Factor(
        factor_id="f1",
        factor_type=FactorType.EQUIVALENCE,
        variables=["A", "B"],
        conclusion="H",
    )
    t, axes = factor_to_tensor(f)
    assert axes == ["A", "B", "H"]
    # H == (A == B)
    assert _almost(t[0, 0, 1], _HIGH)
    assert _almost(t[0, 0, 0], _LOW)
    assert _almost(t[1, 1, 1], _HIGH)
    assert _almost(t[0, 1, 1], _LOW)
    assert _almost(t[0, 1, 0], _HIGH)
    assert _almost(t[1, 0, 0], _HIGH)


def test_factor_to_tensor_contradiction():
    f = Factor(
        factor_id="f1",
        factor_type=FactorType.CONTRADICTION,
        variables=["A", "B"],
        conclusion="H",
    )
    t, axes = factor_to_tensor(f)
    assert axes == ["A", "B", "H"]
    # H == NOT(A AND B)
    assert _almost(t[1, 1, 0], _HIGH)
    assert _almost(t[1, 1, 1], _LOW)
    assert _almost(t[0, 0, 1], _HIGH)
    assert _almost(t[0, 1, 1], _HIGH)
    assert _almost(t[1, 0, 1], _HIGH)
    assert _almost(t[0, 0, 0], _LOW)


def test_factor_to_tensor_complement():
    f = Factor(
        factor_id="f1",
        factor_type=FactorType.COMPLEMENT,
        variables=["A", "B"],
        conclusion="H",
    )
    t, axes = factor_to_tensor(f)
    assert axes == ["A", "B", "H"]
    # H == (A XOR B)
    assert _almost(t[0, 0, 0], _HIGH)
    assert _almost(t[0, 0, 1], _LOW)
    assert _almost(t[0, 1, 1], _HIGH)
    assert _almost(t[1, 0, 1], _HIGH)
    assert _almost(t[1, 1, 0], _HIGH)
    assert _almost(t[1, 1, 1], _LOW)


def test_factor_to_tensor_soft_entailment():
    fg = FactorGraph()
    fg.add_variable("A", 0.5)
    fg.add_variable("C", 0.5)
    fg.add_factor("f1", FactorType.SOFT_ENTAILMENT, ["A"], "C", p1=0.8, p2=0.9)
    f = fg.factors[0]
    t, axes = factor_to_tensor(f)
    assert axes == ["A", "C"]
    assert t.shape == (2, 2)
    assert _almost(t[1, 1], 0.8)
    assert _almost(t[1, 0], 0.2)
    assert _almost(t[0, 0], 0.9)
    assert _almost(t[0, 1], 0.1)


def test_factor_to_tensor_conditional():
    # Two premises; cpt is 2^2 = 4 entries.
    cpt = [0.1, 0.4, 0.6, 0.95]  # indexed by v0 | v1<<1
    fg = FactorGraph()
    fg.add_variable("A", 0.5)
    fg.add_variable("B", 0.5)
    fg.add_variable("C", 0.5)
    fg.add_factor("f1", FactorType.CONDITIONAL, ["A", "B"], "C", cpt=cpt)
    f = fg.factors[0]
    t, axes = factor_to_tensor(f)
    assert axes == ["A", "B", "C"]
    assert t.shape == (2, 2, 2)
    # (A=0, B=0): cpt[0]
    assert _almost(t[0, 0, 1], 0.1)
    assert _almost(t[0, 0, 0], 0.9)
    # (A=1, B=0): cpt[1]
    assert _almost(t[1, 0, 1], 0.4)
    assert _almost(t[1, 0, 0], 0.6)
    # (A=0, B=1): cpt[2]
    assert _almost(t[0, 1, 1], 0.6)
    assert _almost(t[0, 1, 0], 0.4)
    # (A=1, B=1): cpt[3]
    assert _almost(t[1, 1, 1], 0.95)
    assert _almost(t[1, 1, 0], 0.05)
