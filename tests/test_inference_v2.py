"""Tests for gaia.bp — factor_graph, potentials, bp, exact, jt, gbp, engine, lowering."""

from __future__ import annotations

import pytest

from gaia.bp.factor_graph import CROMWELL_EPS, Factor, FactorGraph, FactorType, _cromwell_clamp
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
from gaia.bp.bp import BeliefPropagation, _normalize, _uniform_msg
from gaia.bp.exact import exact_inference
from gaia.bp.junction_tree import JunctionTreeInference
from gaia.bp.gbp import GeneralizedBeliefPropagation
from gaia.bp.engine import InferenceEngine


def _graph_soft_silence(*, pa=0.8, pb=0.5, p1=0.9) -> FactorGraph:
    fg = FactorGraph()
    fg.add_variable("A", prior=pa)
    fg.add_variable("B", prior=pb)
    fg.add_factor("f", FactorType.SOFT_ENTAILMENT, ["A"], "B", p1=p1, p2=0.5)
    return fg


def _graph_soft_noisy(*, pa=0.8, pb=0.5, p1=0.9) -> FactorGraph:
    fg = FactorGraph()
    fg.add_variable("A", prior=pa)
    fg.add_variable("B", prior=pb)
    fg.add_factor(
        "f",
        FactorType.SOFT_ENTAILMENT,
        ["A"],
        "B",
        p1=p1,
        p2=1.0 - CROMWELL_EPS,
    )
    return fg


def _chain_implication() -> FactorGraph:
    fg = FactorGraph()
    fg.add_variable("A", prior=0.9)
    fg.add_variable("B", prior=0.5)
    fg.add_variable("C", prior=0.5)
    fg.add_factor("f1", FactorType.IMPLICATION, ["A"], "B")
    fg.add_factor("f2", FactorType.IMPLICATION, ["B"], "C")
    return fg


def _contradiction_graph() -> FactorGraph:
    fg = FactorGraph()
    fg.add_variable("X", prior=0.7)
    fg.add_variable("Y", prior=0.7)
    fg.add_variable("R", prior=0.9)
    fg.add_factor("f", FactorType.CONTRADICTION, ["X", "Y"], "R")
    return fg


def _equivalence_graph() -> FactorGraph:
    fg = FactorGraph()
    fg.add_variable("A", prior=0.8)
    fg.add_variable("B", prior=0.3)
    fg.add_variable("R", prior=0.9)
    fg.add_factor("f", FactorType.EQUIVALENCE, ["A", "B"], "R")
    return fg


def _diamond_noisy() -> FactorGraph:
    fg = FactorGraph()
    fg.add_variable("A", prior=0.9)
    fg.add_variable("B", prior=0.5)
    fg.add_variable("C", prior=0.5)
    fg.add_variable("D", prior=0.5)
    p2 = 1.0 - CROMWELL_EPS
    fg.add_factor("f1", FactorType.SOFT_ENTAILMENT, ["A"], "B", p1=0.9, p2=p2)
    fg.add_factor("f2", FactorType.SOFT_ENTAILMENT, ["A"], "C", p1=0.9, p2=p2)
    fg.add_factor("f3", FactorType.SOFT_ENTAILMENT, ["B"], "D", p1=0.8, p2=p2)
    fg.add_factor("f4", FactorType.SOFT_ENTAILMENT, ["C"], "D", p1=0.8, p2=p2)
    return fg


class TestCromwellClamp:
    def test_within_bounds(self):
        assert _cromwell_clamp(0.5) == 0.5

    def test_clamp_zero(self):
        assert _cromwell_clamp(0.0) == CROMWELL_EPS

    def test_clamp_one(self):
        assert _cromwell_clamp(1.0) == 1.0 - CROMWELL_EPS


class TestFactorType:
    def test_eight_types(self):
        assert len(FactorType) == 8


class TestFactor:
    def test_all_vars(self):
        f = Factor("f1", FactorType.IMPLICATION, ["A"], "B")
        assert f.all_vars == ["A", "B"]


class TestFactorGraph:
    def test_add_variable_cromwell(self):
        fg = FactorGraph()
        fg.add_variable("X", prior=0.0)
        assert fg.variables["X"] == CROMWELL_EPS

    def test_soft_entailment_requires_p1p2(self):
        fg = FactorGraph()
        fg.add_variable("A", 0.5)
        fg.add_variable("B", 0.5)
        with pytest.raises(ValueError, match="p1 and p2"):
            fg.add_factor("f", FactorType.SOFT_ENTAILMENT, ["A"], "B")

    def test_validate_missing_variable(self):
        fg = FactorGraph()
        fg.add_variable("A", prior=0.5)
        fg.factors.append(Factor("f1", FactorType.IMPLICATION, ["A"], "B"))
        errors = fg.validate()
        assert any("B" in e for e in errors)


class TestDeterministicPotentials:
    def test_implication_forbidden_row(self):
        lo = CROMWELL_EPS
        hi = 1.0 - CROMWELL_EPS
        assert implication_potential({"A": 1, "B": 0}, "A", "B") == pytest.approx(lo)
        assert implication_potential({"A": 1, "B": 1}, "A", "B") == pytest.approx(hi)

    def test_conjunction(self):
        hi = 1.0 - CROMWELL_EPS
        lo = CROMWELL_EPS
        assert conjunction_potential({"A": 1, "B": 1, "M": 1}, ["A", "B"], "M") == pytest.approx(hi)
        assert conjunction_potential({"A": 1, "B": 1, "M": 0}, ["A", "B"], "M") == pytest.approx(lo)

    def test_disjunction(self):
        hi = 1.0 - CROMWELL_EPS
        lo = CROMWELL_EPS
        assert disjunction_potential({"A": 0, "B": 0, "D": 0}, ["A", "B"], "D") == pytest.approx(hi)
        assert disjunction_potential({"A": 1, "B": 0, "D": 0}, ["A", "B"], "D") == pytest.approx(lo)

    def test_equivalence_helper(self):
        hi = 1.0 - CROMWELL_EPS
        lo = CROMWELL_EPS
        assert equivalence_potential({"A": 1, "B": 1, "H": 1}, "A", "B", "H") == pytest.approx(hi)
        assert equivalence_potential({"A": 1, "B": 0, "H": 1}, "A", "B", "H") == pytest.approx(lo)

    def test_contradiction_helper(self):
        hi = 1.0 - CROMWELL_EPS
        lo = CROMWELL_EPS
        assert contradiction_potential({"A": 1, "B": 1, "H": 0}, "A", "B", "H") == pytest.approx(hi)
        assert contradiction_potential({"A": 1, "B": 1, "H": 1}, "A", "B", "H") == pytest.approx(lo)

    def test_complement(self):
        hi = 1.0 - CROMWELL_EPS
        assert complement_potential({"A": 0, "B": 1, "H": 1}, "A", "B", "H") == pytest.approx(hi)


class TestSoftEntailmentPotential:
    def test_rows(self):
        p1, p2 = 0.85, 0.75
        assert soft_entailment_potential({"M": 1, "C": 1}, "M", "C", p1, p2) == pytest.approx(p1)
        assert soft_entailment_potential({"M": 0, "C": 0}, "M", "C", p1, p2) == pytest.approx(p2)


class TestConditionalPotential:
    def test_single_parent(self):
        cpt = (0.2, 0.9)
        assert conditional_potential({"A": 1, "C": 1}, ["A"], "C", cpt) == pytest.approx(0.9)
        assert conditional_potential({"A": 0, "C": 1}, ["A"], "C", cpt) == pytest.approx(0.2)


class TestEvaluatePotential:
    def test_dispatch_implication(self):
        f = Factor("f", FactorType.IMPLICATION, ["A"], "B")
        pot = evaluate_potential(f, {"A": 1, "B": 1})
        assert pot == pytest.approx(1.0 - CROMWELL_EPS)


class TestBPHelpers:
    def test_uniform_msg(self):
        m = _uniform_msg()
        assert m[0] == pytest.approx(0.5)

    def test_normalize(self):
        import numpy as np

        m = _normalize(np.array([3.0, 7.0]))
        assert m[0] == pytest.approx(0.3)


class TestBeliefPropagation:
    def test_simple_soft_silence(self):
        fg = _graph_soft_silence()
        r = BeliefPropagation(max_iterations=100).run(fg)
        assert r.beliefs["B"] > 0.5

    def test_simple_soft_noisy(self):
        fg = _graph_soft_noisy()
        r = BeliefPropagation(max_iterations=100).run(fg)
        assert r.beliefs["B"] > 0.5

    def test_contradiction_adjusts(self):
        fg = _contradiction_graph()
        r = BeliefPropagation(max_iterations=100).run(fg)
        assert r.beliefs["X"] < 0.7 or r.beliefs["Y"] < 0.7 or r.beliefs["R"] < 0.9


class TestExactInference:
    def test_soft_silence(self):
        fg = _graph_soft_silence()
        beliefs, z = exact_inference(fg)
        assert z > 0
        assert 0 < beliefs["B"] < 1

    def test_too_many_variables_raises(self):
        fg = FactorGraph()
        for i in range(27):
            fg.add_variable(f"v{i}", prior=0.5)
        with pytest.raises(ValueError, match="too large"):
            exact_inference(fg)


class TestJunctionTreeInference:
    def test_matches_exact_chain(self):
        fg = _chain_implication()
        ex, _ = exact_inference(fg)
        jt = JunctionTreeInference().run(fg)
        for v in fg.variables:
            assert jt.beliefs[v] == pytest.approx(ex[v], abs=1e-9)

    def test_matches_exact_contradiction(self):
        fg = _contradiction_graph()
        ex, _ = exact_inference(fg)
        jt = JunctionTreeInference().run(fg)
        for v in fg.variables:
            assert jt.beliefs[v] == pytest.approx(ex[v], abs=1e-9)

    def test_matches_exact_diamond(self):
        fg = _diamond_noisy()
        ex, _ = exact_inference(fg)
        jt = JunctionTreeInference().run(fg)
        for v in fg.variables:
            assert jt.beliefs[v] == pytest.approx(ex[v], abs=1e-9)


class TestGeneralizedBP:
    def test_simple_delegates_to_jt(self):
        fg = _graph_soft_silence()
        r = GeneralizedBeliefPropagation().run(fg)
        ex, _ = exact_inference(fg)
        for v in fg.variables:
            assert r.beliefs[v] == pytest.approx(ex[v], abs=1e-9)


class TestInferenceEngine:
    def test_force_exact(self):
        fg = _graph_soft_silence()
        r = InferenceEngine().run(fg, method="exact")
        assert r.method_used == "exact"
        assert r.is_exact


class TestJTMatchesExact:
    @pytest.mark.parametrize(
        "builder",
        [
            _graph_soft_silence,
            _graph_soft_noisy,
            _chain_implication,
            _contradiction_graph,
            _equivalence_graph,
            _diamond_noisy,
        ],
    )
    def test_jt_matches_exact(self, builder):
        fg = builder()
        ex, _ = exact_inference(fg)
        jt = JunctionTreeInference().run(fg)
        for v in fg.variables:
            assert jt.beliefs[v] == pytest.approx(ex[v], abs=1e-9), v


class TestFourSyllogismsSoftEntailment:
    """Sanity checks consistent with 07-belief-propagation.md §2.3 (weak support)."""

    def test_c1_strengthening_premise_raises_conclusion(self):
        fg_lo = FactorGraph()
        fg_lo.add_variable("A", 0.5)
        fg_lo.add_variable("B", 0.5)
        fg_lo.add_factor("f", FactorType.SOFT_ENTAILMENT, ["A"], "B", p1=0.8, p2=0.6)
        fg_hi = FactorGraph()
        fg_hi.add_variable("A", 0.85)
        fg_hi.add_variable("B", 0.5)
        fg_hi.add_factor("f", FactorType.SOFT_ENTAILMENT, ["A"], "B", p1=0.8, p2=0.6)
        b_lo, _ = exact_inference(fg_lo)
        b_hi, _ = exact_inference(fg_hi)
        assert b_hi["B"] > b_lo["B"]

    def test_c2_conclusion_true_raises_premise(self):
        """Weak syllogism 2 (abduction): C true → M belief rises."""
        fg = FactorGraph()
        fg.add_variable("M", 0.5)
        fg.add_variable("C", 0.95)
        fg.add_factor("f", FactorType.SOFT_ENTAILMENT, ["M"], "C", p1=0.9, p2=0.6)
        b, _ = exact_inference(fg)
        assert b["M"] > 0.5

    def test_c3_conclusion_false_lowers_premise(self):
        """Weak syllogism 3 (modus tollens): C false → M belief drops."""
        fg = FactorGraph()
        fg.add_variable("M", 0.7)
        fg.add_variable("C", 0.05)
        fg.add_factor("f", FactorType.SOFT_ENTAILMENT, ["M"], "C", p1=0.9, p2=0.6)
        b, _ = exact_inference(fg)
        assert b["M"] < 0.7

    def test_c4_false_premise_weakens_noisy(self):
        """Weak syllogism 4: M false → C belief drops (p2 > 0.5)."""
        fg = FactorGraph()
        fg.add_variable("A", 0.01)
        fg.add_variable("B", 0.9)
        fg.add_factor(
            "f",
            FactorType.SOFT_ENTAILMENT,
            ["A"],
            "B",
            p1=0.99,
            p2=1.0 - CROMWELL_EPS,
        )
        b, _ = exact_inference(fg)
        assert b["B"] < 0.9


class TestConditionalMatchesNoisyAndShape:
    """2-premise noisy-and CPT equals CONJUNCTION + SOFT_ENTAILMENT marginals."""

    def test_two_premises(self):
        p = 0.88
        eps = CROMWELL_EPS
        # idx = A + 2*B; noisy-and: P(C=1|prem) = eps unless A=B=1, then p
        cpt = (eps, eps, eps, p)

        fg_c = FactorGraph()
        for vid in ("A", "B", "C"):
            fg_c.add_variable(vid, 0.5)
        fg_c.add_factor("cpt", FactorType.CONDITIONAL, ["A", "B"], "C", cpt=cpt)

        fg_d = FactorGraph()
        for vid in ("A", "B", "C", "M"):
            fg_d.add_variable(vid, 0.5)
        fg_d.add_factor("conj", FactorType.CONJUNCTION, ["A", "B"], "M")
        fg_d.add_factor(
            "se",
            FactorType.SOFT_ENTAILMENT,
            ["M"],
            "C",
            p1=p,
            p2=1.0 - eps,
        )

        ec, _ = exact_inference(fg_c)
        ed, _ = exact_inference(fg_d)
        for v in ("A", "B", "C"):
            assert ec[v] == pytest.approx(ed[v], abs=5e-3), v


class TestEvidence:
    """07-bp §1.7: evidence incorporation."""

    def test_observe_hard_evidence(self):
        fg = FactorGraph()
        fg.add_variable("A", 0.5)
        fg.add_variable("B", 0.5)
        fg.add_factor("f", FactorType.SOFT_ENTAILMENT, ["A"], "B", p1=0.9, p2=0.6)
        fg.observe("A", 1)
        assert fg.variables["A"] == pytest.approx(1.0 - CROMWELL_EPS)
        b, _ = exact_inference(fg)
        assert b["B"] > 0.8

    def test_observe_zero(self):
        fg = FactorGraph()
        fg.add_variable("X", 0.7)
        fg.observe("X", 0)
        assert fg.variables["X"] == pytest.approx(CROMWELL_EPS)

    def test_observe_invalid_value_raises(self):
        fg = FactorGraph()
        fg.add_variable("X", 0.5)
        with pytest.raises(ValueError, match="0 or 1"):
            fg.observe("X", 2)

    def test_observe_unknown_var_raises(self):
        fg = FactorGraph()
        with pytest.raises(KeyError):
            fg.observe("X", 1)

    def test_likelihood_soft_evidence(self):
        fg = FactorGraph()
        fg.add_variable("H", 0.5)
        fg.add_likelihood("H", 4.0)
        assert fg.variables["H"] > 0.5
        assert fg.variables["H"] == pytest.approx(0.8, abs=0.01)

    def test_likelihood_weakens(self):
        fg = FactorGraph()
        fg.add_variable("H", 0.8)
        fg.add_likelihood("H", 0.1)
        assert fg.variables["H"] < 0.8
