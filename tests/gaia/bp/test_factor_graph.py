"""Unit tests for gaia.bp.factor_graph — graph construction and validation."""

import pytest

from gaia.bp.factor_graph import CROMWELL_EPS, Factor, FactorGraph, FactorType


# ── Variable management ──


def test_add_variable():
    fg = FactorGraph()
    fg.add_variable("A", 0.7)
    assert "A" in fg.variables
    assert fg.variables["A"] == pytest.approx(0.7)


def test_add_variable_cromwell_clamping():
    fg = FactorGraph()
    fg.add_variable("A", 0.0)
    assert fg.variables["A"] >= CROMWELL_EPS

    fg.add_variable("B", 1.0)
    assert fg.variables["B"] <= 1 - CROMWELL_EPS


def test_observe_hard_evidence():
    fg = FactorGraph()
    fg.add_variable("A", 0.5)
    fg.observe("A", 1)
    assert fg.variables["A"] >= 1 - CROMWELL_EPS


def test_observe_value_zero():
    fg = FactorGraph()
    fg.add_variable("A", 0.5)
    fg.observe("A", 0)
    assert fg.variables["A"] <= CROMWELL_EPS


def test_add_likelihood():
    fg = FactorGraph()
    fg.add_variable("A", 0.5)
    original = fg.variables["A"]
    fg.add_likelihood("A", 3.0)
    assert fg.variables["A"] > original


# ── Factor construction ──


def test_add_implication_factor():
    fg = FactorGraph()
    fg.add_variable("A", 0.5)
    fg.add_variable("B", 0.5)
    fg.add_variable("H", 0.5)
    fg.add_factor("f1", FactorType.IMPLICATION, ["A", "B"], "H")
    assert len(fg.factors) == 1
    assert fg.factors[0].factor_type == FactorType.IMPLICATION


def test_add_conjunction_factor():
    fg = FactorGraph()
    for v in ["A", "B", "M"]:
        fg.add_variable(v, 0.5)
    fg.add_factor("f1", FactorType.CONJUNCTION, ["A", "B"], "M")
    assert fg.factors[0].variables == ["A", "B"]


def test_add_soft_entailment():
    fg = FactorGraph()
    fg.add_variable("M", 0.5)
    fg.add_variable("C", 0.5)
    fg.add_factor("f1", FactorType.SOFT_ENTAILMENT, ["M"], "C", p1=0.9, p2=0.95)
    assert fg.factors[0].p1 == pytest.approx(0.9)


def test_add_conditional():
    fg = FactorGraph()
    for v in ["A", "B", "C"]:
        fg.add_variable(v, 0.5)
    fg.add_factor("f1", FactorType.CONDITIONAL, ["A", "B"], "C", cpt=[0.1, 0.3, 0.6, 0.9])
    assert fg.factors[0].cpt == (0.1, 0.3, 0.6, 0.9)


# ── Validation ──


def test_validate_empty_graph():
    fg = FactorGraph()
    assert fg.validate() == []


def test_validate_missing_variable():
    fg = FactorGraph()
    fg.add_variable("A", 0.5)
    fg.add_variable("B", 0.5)
    fg.factors.append(
        Factor(
            factor_id="f1", factor_type=FactorType.IMPLICATION, variables=["A", "B"], conclusion="H"
        )
    )
    errors = fg.validate()
    assert any("H" in e for e in errors)


def test_validate_good_graph():
    fg = FactorGraph()
    fg.add_variable("A", 0.5)
    fg.add_variable("B", 0.5)
    fg.add_variable("H", 0.5)
    fg.add_factor("f1", FactorType.IMPLICATION, ["A", "B"], "H")
    assert fg.validate() == []


# ── Metadata ──


def test_get_var_to_factors():
    fg = FactorGraph()
    for v in ["A", "B", "C", "H1", "H2"]:
        fg.add_variable(v, 0.5)
    fg.add_factor("f1", FactorType.IMPLICATION, ["A", "B"], "H1")
    fg.add_factor("f2", FactorType.IMPLICATION, ["B", "C"], "H2")
    mapping = fg.get_var_to_factors()
    assert 0 in mapping["A"]
    assert 0 in mapping["B"]
    assert 1 in mapping["B"]
    assert 1 in mapping["C"]


def test_summary():
    fg = FactorGraph()
    fg.add_variable("A", 0.5)
    fg.add_variable("B", 0.5)
    fg.add_variable("H", 0.5)
    fg.add_factor("f1", FactorType.IMPLICATION, ["A", "B"], "H")
    s = fg.summary()
    assert "A" in s


def test_factor_all_vars():
    f = Factor(
        factor_id="f1",
        factor_type=FactorType.CONJUNCTION,
        variables=["A", "B"],
        conclusion="M",
    )
    assert set(f.all_vars) == {"A", "B", "M"}


def test_factor_all_vars_dedup():
    f = Factor(
        factor_id="f1",
        factor_type=FactorType.CONJUNCTION,
        variables=["A", "B"],
        conclusion="A",
    )
    assert f.all_vars.count("A") == 1


# ── Directed factors ──


def test_add_directed_factor():
    """directed=True is stored on the Factor."""
    fg = FactorGraph()
    fg.add_variable("A", 0.5)
    fg.add_variable("B", 0.5)
    fg.add_variable("H", 1.0 - CROMWELL_EPS)
    fg.add_factor("f1", FactorType.IMPLICATION, ["A", "B"], "H", directed=True)
    assert fg.factors[0].directed is True


def test_factor_default_undirected():
    """Factors are undirected by default."""
    fg = FactorGraph()
    fg.add_variable("A", 0.5)
    fg.add_variable("B", 0.5)
    fg.add_variable("H", 1.0 - CROMWELL_EPS)
    fg.add_factor("f1", FactorType.IMPLICATION, ["A", "B"], "H")
    assert fg.factors[0].directed is False
