"""Supplement tests covering uncovered paths in trw_bp, mean_field, factor_graph."""

import pytest

from gaia.bp import FactorGraph, FactorType, TRWBeliefPropagation
from gaia.bp.factor_graph import CROMWELL_EPS
from gaia.bp.mean_field import MeanFieldVI


class TestFactorGraphValidation:
    def test_add_variable_no_prior(self):
        fg = FactorGraph()
        fg.add_variable("A")
        assert "A" in fg.variables
        assert "A" not in fg.unary_factors

    def test_add_variable_after_hard_evidence_consistent(self):
        fg = FactorGraph()
        fg.add_variable("A", 0.5)
        fg.add_evidence("A", 1)
        fg.add_variable("A", 0.9)

    def test_add_variable_after_hard_evidence_contradicts(self):
        fg = FactorGraph()
        fg.add_variable("A", 0.5)
        fg.add_evidence("A", 1)
        with pytest.raises(ValueError, match="contradicts hard evidence"):
            fg.add_variable("A", 0.1)

    def test_add_variable_conflicting_unary(self):
        fg = FactorGraph()
        fg.add_variable("A", 0.3)
        with pytest.raises(ValueError, match="conflicting unary priors"):
            fg.add_variable("A", 0.8)

    def test_add_evidence_unknown_variable(self):
        fg = FactorGraph()
        with pytest.raises(KeyError):
            fg.add_evidence("X", 1)

    def test_add_evidence_invalid_value(self):
        fg = FactorGraph()
        fg.add_variable("A")
        with pytest.raises(ValueError, match="must be 0 or 1"):
            fg.add_evidence("A", 2)

    def test_add_evidence_conflicting(self):
        fg = FactorGraph()
        fg.add_variable("A")
        fg.add_evidence("A", 1)
        with pytest.raises(ValueError, match="conflicting hard evidence"):
            fg.add_evidence("A", 0)

    def test_add_evidence_contradicts_soft_prior(self):
        fg = FactorGraph()
        fg.add_variable("A", 0.1)
        with pytest.raises(ValueError, match="contradicts existing soft prior"):
            fg.add_evidence("A", 1)

    def test_add_factor_conclusion_in_variables_raises(self):
        fg = FactorGraph()
        fg.add_variable("A")
        fg.add_variable("B")
        with pytest.raises(ValueError, match=r"conclusion.*must not appear in variables"):
            fg.add_factor("f", FactorType.SOFT_ENTAILMENT, ["A", "B"], "A", p1=0.8, p2=0.9)

    def test_add_factor_deterministic_with_p1_raises(self):
        fg = FactorGraph()
        fg.add_variable("A")
        fg.add_variable("B")
        fg.add_variable("C")
        with pytest.raises(ValueError, match="must not set p1/p2/cpt"):
            fg.add_factor("f", FactorType.IMPLICATION, ["A", "B"], "C", p1=0.9)

    def test_add_factor_soft_entailment_with_cpt_raises(self):
        fg = FactorGraph()
        fg.add_variable("A")
        fg.add_variable("B")
        with pytest.raises(ValueError, match="must not set cpt"):
            fg.add_factor(
                "f", FactorType.SOFT_ENTAILMENT, ["A"], "B", p1=0.8, p2=0.9, cpt=[0.1, 0.9]
            )

    def test_add_factor_soft_entailment_wrong_var_count(self):
        fg = FactorGraph()
        fg.add_variable("A")
        fg.add_variable("B")
        fg.add_variable("C")
        with pytest.raises(ValueError, match="requires exactly 1 premise"):
            fg.add_factor("f", FactorType.SOFT_ENTAILMENT, ["A", "B"], "C", p1=0.8, p2=0.9)

    def test_add_factor_soft_entailment_missing_p1(self):
        fg = FactorGraph()
        fg.add_variable("A")
        fg.add_variable("B")
        with pytest.raises(ValueError, match="requires p1 and p2"):
            fg.add_factor("f", FactorType.SOFT_ENTAILMENT, ["A"], "B", p2=0.9)

    def test_add_factor_soft_entailment_p1_plus_p2_too_small(self):
        fg = FactorGraph()
        fg.add_variable("A")
        fg.add_variable("B")
        with pytest.raises(ValueError, match=r"p1 \+ p2 > 1"):
            fg.add_factor("f", FactorType.SOFT_ENTAILMENT, ["A"], "B", p1=0.3, p2=0.3)

    def test_add_factor_conditional_with_p1_raises(self):
        fg = FactorGraph()
        fg.add_variable("A")
        fg.add_variable("B")
        with pytest.raises(ValueError, match="must not set p1/p2"):
            fg.add_factor("f", FactorType.CONDITIONAL, ["A"], "B", p1=0.8, cpt=[0.2, 0.9])

    def test_add_factor_conditional_no_variables_raises(self):
        fg = FactorGraph()
        fg.add_variable("B")
        with pytest.raises(ValueError, match="requires at least one premise"):
            fg.add_factor("f", FactorType.CONDITIONAL, [], "B", cpt=[0.5])

    def test_add_factor_conditional_no_cpt_raises(self):
        fg = FactorGraph()
        fg.add_variable("A")
        fg.add_variable("B")
        with pytest.raises(ValueError, match="requires cpt"):
            fg.add_factor("f", FactorType.CONDITIONAL, ["A"], "B")

    def test_add_factor_conditional_wrong_cpt_length(self):
        fg = FactorGraph()
        fg.add_variable("A")
        fg.add_variable("B")
        with pytest.raises(ValueError, match="cpt length must be"):
            fg.add_factor("f", FactorType.CONDITIONAL, ["A"], "B", cpt=[0.2, 0.8, 0.5])

    def test_add_factor_pairwise_with_p1_raises(self):
        fg = FactorGraph()
        fg.add_variable("A")
        fg.add_variable("B")
        with pytest.raises(ValueError, match="must not set p1/p2"):
            fg.add_factor(
                "f", FactorType.PAIRWISE_POTENTIAL, ["A"], "B", p1=0.5, cpt=[0.1, 0.4, 0.4, 0.1]
            )

    def test_add_factor_pairwise_wrong_var_count(self):
        fg = FactorGraph()
        fg.add_variable("A")
        fg.add_variable("B")
        fg.add_variable("C")
        with pytest.raises(ValueError, match="requires exactly 1 variable"):
            fg.add_factor(
                "f", FactorType.PAIRWISE_POTENTIAL, ["A", "B"], "C", cpt=[0.1, 0.4, 0.4, 0.1]
            )

    def test_add_factor_pairwise_no_cpt_raises(self):
        fg = FactorGraph()
        fg.add_variable("A")
        fg.add_variable("B")
        with pytest.raises(ValueError, match="requires cpt"):
            fg.add_factor("f", FactorType.PAIRWISE_POTENTIAL, ["A"], "B")

    def test_add_factor_pairwise_wrong_cpt_length(self):
        fg = FactorGraph()
        fg.add_variable("A")
        fg.add_variable("B")
        with pytest.raises(ValueError, match="cpt length must be 4"):
            fg.add_factor("f", FactorType.PAIRWISE_POTENTIAL, ["A"], "B", cpt=[0.1, 0.4, 0.5])

    def test_add_factor_pairwise_negative_weight(self):
        fg = FactorGraph()
        fg.add_variable("A")
        fg.add_variable("B")
        with pytest.raises(ValueError, match="finite non-negative"):
            fg.add_factor("f", FactorType.PAIRWISE_POTENTIAL, ["A"], "B", cpt=[-0.1, 0.4, 0.4, 0.3])

    def test_add_factor_pairwise_all_zero(self):
        fg = FactorGraph()
        fg.add_variable("A")
        fg.add_variable("B")
        with pytest.raises(ValueError, match="at least one positive"):
            fg.add_factor("f", FactorType.PAIRWISE_POTENTIAL, ["A"], "B", cpt=[0.0, 0.0, 0.0, 0.0])

    def test_validate_deterministic_implication_wrong_vars(self):
        fg = FactorGraph()
        fg.add_variable("A")
        fg.add_variable("B")
        with pytest.raises(ValueError, match="requires exactly 2 variables"):
            fg.add_factor("f", FactorType.IMPLICATION, ["A"], "B")

    def test_validate_deterministic_negation_wrong_vars(self):
        fg = FactorGraph()
        fg.add_variable("A")
        fg.add_variable("B")
        fg.add_variable("C")
        with pytest.raises(ValueError, match="requires exactly 1 variable"):
            fg.add_factor("f", FactorType.NEGATION, ["A", "B"], "C")

    def test_validate_deterministic_conjunction_too_few(self):
        fg = FactorGraph()
        fg.add_variable("A")
        fg.add_variable("B")
        with pytest.raises(ValueError, match="requires at least 2 variables"):
            fg.add_factor("f", FactorType.CONJUNCTION, ["A"], "B")

    def test_validate_deterministic_disjunction_too_few(self):
        fg = FactorGraph()
        fg.add_variable("A")
        fg.add_variable("B")
        with pytest.raises(ValueError, match="requires at least 2 variables"):
            fg.add_factor("f", FactorType.DISJUNCTION, ["A"], "B")

    def test_validate_deterministic_equivalence_wrong_vars(self):
        fg = FactorGraph()
        fg.add_variable("A")
        fg.add_variable("B")
        with pytest.raises(ValueError, match="requires exactly 2 variables"):
            fg.add_factor("f", FactorType.EQUIVALENCE, ["A"], "B")

    def test_validate_graph_no_errors(self):
        fg = FactorGraph()
        fg.add_variable("A")
        fg.add_variable("B")
        fg.add_factor("f", FactorType.SOFT_ENTAILMENT, ["A"], "B", p1=0.8, p2=0.9)
        assert fg.validate() == []

    def test_summary(self):
        fg = FactorGraph()
        fg.add_variable("A", 0.7)
        fg.add_variable("B", 0.5)
        fg.add_factor("f1", FactorType.SOFT_ENTAILMENT, ["A"], "B", p1=0.8, p2=0.9)
        s = fg.summary()
        assert "FactorGraph" in s
        assert "SOFT_ENTAILMENT" in s

    def test_pairwise_potential_inference(self):
        fg = FactorGraph()
        fg.add_variable("A", 0.6)
        fg.add_variable("B", 0.5)
        fg.add_factor("f", FactorType.PAIRWISE_POTENTIAL, ["A"], "B", cpt=[0.1, 0.4, 0.4, 0.1])
        result = TRWBeliefPropagation().run(fg)
        assert 0 < result.beliefs["A"] < 1
        assert 0 < result.beliefs["B"] < 1

    def test_conditional_factor_inference(self):
        fg = FactorGraph()
        fg.add_variable("A", 0.7)
        fg.add_variable("B", 0.5)
        fg.add_factor("f", FactorType.CONDITIONAL, ["A"], "B", cpt=[0.2, 0.9])
        result = TRWBeliefPropagation().run(fg)
        assert result.beliefs["B"] > 0.5


class TestTRWResidualSchedule:
    def test_residual_schedule_not_supported(self):
        with pytest.raises(ValueError, match="schedule must be 'synchronous'"):
            TRWBeliefPropagation(schedule="residual")

    def test_hard_evidence_in_synchronous(self):
        fg = FactorGraph()
        fg.add_variable("A", 0.8)
        fg.add_variable("B", 0.5)
        fg.add_variable("C", 0.5)
        fg.add_factor("f1", FactorType.SOFT_ENTAILMENT, ["A"], "B", p1=0.9, p2=0.9)
        fg.add_factor("f2", FactorType.SOFT_ENTAILMENT, ["B"], "C", p1=0.85, p2=0.9)
        fg.add_evidence("A", 1)
        result = TRWBeliefPropagation(max_iterations=50).run(fg)
        assert result.beliefs["A"] == pytest.approx(1.0 - CROMWELL_EPS, abs=1e-6)
        assert result.beliefs["B"] > 0.7

    def test_convergence_threshold_triggers(self):
        fg = FactorGraph()
        fg.add_variable("A", 0.9)
        fg.add_variable("B", 0.5)
        fg.add_factor("f", FactorType.SOFT_ENTAILMENT, ["A"], "B", p1=0.95, p2=0.95)
        result = TRWBeliefPropagation(convergence_threshold=0.5, max_iterations=200).run(fg)
        assert result.diagnostics.converged

    def test_max_iterations_without_convergence(self):
        fg = FactorGraph()
        fg.add_variable("A", 0.9)
        fg.add_variable("B", 0.5)
        fg.add_variable("H", 0.5)
        fg.add_factor("f1", FactorType.SOFT_ENTAILMENT, ["A"], "B", p1=0.95, p2=0.9)
        fg.add_factor("f2", FactorType.CONTRADICTION, ["A", "B"], "H")
        result = TRWBeliefPropagation(max_iterations=2, convergence_threshold=1e-12).run(fg)
        assert result.diagnostics.iterations_run <= 2

    def test_belief_table(self):
        fg = FactorGraph()
        fg.add_variable("A", 0.7)
        fg.add_variable("B", 0.5)
        fg.add_factor("f", FactorType.SOFT_ENTAILMENT, ["A"], "B", p1=0.8, p2=0.9)
        result = TRWBeliefPropagation().run(fg)
        table = result.diagnostics.belief_table()
        assert "Variable" in table
        assert "A" in table

    def test_belief_table_empty(self):
        from gaia.bp.trw_bp import TRWDiagnostics

        diag = TRWDiagnostics()
        assert "(no belief history)" in diag.belief_table()

    def test_rho_less_than_one_cyclic(self):
        fg = FactorGraph()
        for v in ["A", "B", "C", "D"]:
            fg.add_variable(v, 0.5)
        fg.add_factor("f1", FactorType.SOFT_ENTAILMENT, ["A"], "B", p1=0.8, p2=0.9)
        fg.add_factor("f2", FactorType.SOFT_ENTAILMENT, ["B"], "C", p1=0.8, p2=0.9)
        fg.add_factor("f3", FactorType.SOFT_ENTAILMENT, ["C"], "D", p1=0.8, p2=0.9)
        fg.add_factor("f4", FactorType.SOFT_ENTAILMENT, ["D"], "A", p1=0.8, p2=0.9)
        result = TRWBeliefPropagation(max_iterations=50).run(fg)
        assert result.diagnostics.rho <= 1.0


class TestMeanFieldVI:
    def test_empty_graph(self):
        fg = FactorGraph()
        result = MeanFieldVI().run(fg)
        assert result.beliefs == {}

    def test_simple_chain(self):
        fg = FactorGraph()
        fg.add_variable("A", 0.8)
        fg.add_variable("B", 0.5)
        fg.add_factor("f", FactorType.SOFT_ENTAILMENT, ["A"], "B", p1=0.9, p2=0.9)
        result = MeanFieldVI().run(fg)
        assert result.diagnostics.converged
        assert result.beliefs["B"] > 0.5

    def test_hard_evidence_clamped(self):
        fg = FactorGraph()
        fg.add_variable("A", 0.5)
        fg.add_variable("B", 0.5)
        fg.add_factor("f", FactorType.SOFT_ENTAILMENT, ["A"], "B", p1=0.9, p2=0.9)
        fg.add_evidence("A", 1)
        result = MeanFieldVI().run(fg)
        assert result.beliefs["A"] == pytest.approx(1.0 - CROMWELL_EPS, abs=1e-6)
        assert result.beliefs["B"] > 0.7

    def test_track_elbo(self):
        fg = FactorGraph()
        fg.add_variable("A", 0.7)
        fg.add_variable("B", 0.5)
        fg.add_factor("f", FactorType.SOFT_ENTAILMENT, ["A"], "B", p1=0.8, p2=0.9)
        result = MeanFieldVI(track_elbo=True).run(fg)
        assert len(result.diagnostics.elbo_history) > 1

    def test_max_iterations_without_convergence(self):
        fg = FactorGraph()
        fg.add_variable("A", 0.9)
        fg.add_variable("B", 0.5)
        fg.add_variable("H", 0.5)
        fg.add_factor("f1", FactorType.SOFT_ENTAILMENT, ["A"], "B", p1=0.95, p2=0.9)
        fg.add_factor("f2", FactorType.CONTRADICTION, ["A", "B"], "H")
        result = MeanFieldVI(max_iterations=2, convergence_threshold=1e-12).run(fg)
        assert result.diagnostics.iterations_run == 2
        assert not result.diagnostics.converged

    def test_diamond_graph(self):
        fg = FactorGraph()
        fg.add_variable("A", 0.8)
        fg.add_variable("B", 0.5)
        fg.add_variable("C", 0.5)
        fg.add_variable("M", 0.5)
        fg.add_variable("D", 0.5)
        fg.add_factor("f1", FactorType.SOFT_ENTAILMENT, ["A"], "B", p1=0.9, p2=0.95)
        fg.add_factor("f2", FactorType.SOFT_ENTAILMENT, ["A"], "C", p1=0.85, p2=0.9)
        fg.add_factor("f3", FactorType.CONJUNCTION, ["B", "C"], "M")
        fg.add_factor("f4", FactorType.SOFT_ENTAILMENT, ["M"], "D", p1=0.9, p2=0.95)
        result = MeanFieldVI().run(fg)
        assert 0 < result.beliefs["D"] < 1

    def test_no_factors_returns_priors(self):
        fg = FactorGraph()
        fg.add_variable("A", 0.7)
        fg.add_variable("B", 0.3)
        result = MeanFieldVI().run(fg)
        assert result.beliefs["A"] == pytest.approx(0.7, abs=0.01)
        assert result.beliefs["B"] == pytest.approx(0.3, abs=0.01)


class TestTRWExtraPaths:
    def test_hard_evidence_zero_no_factors(self):
        fg = FactorGraph()
        fg.add_variable("A", 0.5)
        fg.add_variable("B", 0.5)
        fg.add_evidence("A", 0)
        result = TRWBeliefPropagation().run(fg)
        assert result.beliefs["A"] == pytest.approx(CROMWELL_EPS, abs=1e-6)

    def test_hard_evidence_zero_in_synchronous(self):
        fg = FactorGraph()
        fg.add_variable("A", 0.5)
        fg.add_variable("B", 0.5)
        fg.add_factor("f", FactorType.SOFT_ENTAILMENT, ["A"], "B", p1=0.9, p2=0.9)
        fg.add_evidence("A", 0)
        result = TRWBeliefPropagation().run(fg)
        assert result.beliefs["A"] == pytest.approx(CROMWELL_EPS, abs=1e-6)
        assert result.beliefs["B"] < 0.5

    def test_prior_for_hard_evidence_zero(self):
        fg = FactorGraph()
        fg.add_variable("A", 0.5)
        fg.add_variable("B", 0.5)
        fg.add_variable("C", 0.5)
        fg.add_factor("f1", FactorType.SOFT_ENTAILMENT, ["A"], "B", p1=0.9, p2=0.9)
        fg.add_factor("f2", FactorType.SOFT_ENTAILMENT, ["B"], "C", p1=0.9, p2=0.9)
        fg.add_evidence("A", 0)
        result = TRWBeliefPropagation().run(fg)
        assert result.beliefs["B"] < 0.5

    def test_run_residual_via_private_schedule(self):
        fg = FactorGraph()
        fg.add_variable("A", 0.8)
        fg.add_variable("B", 0.5)
        fg.add_variable("C", 0.5)
        fg.add_factor("f1", FactorType.SOFT_ENTAILMENT, ["A"], "B", p1=0.9, p2=0.9)
        fg.add_factor("f2", FactorType.SOFT_ENTAILMENT, ["B"], "C", p1=0.85, p2=0.9)
        bp = TRWBeliefPropagation(max_iterations=50)
        object.__setattr__(bp, "_schedule", "residual")
        result = bp.run(fg)
        assert 0 < result.beliefs["B"] < 1
        assert 0 < result.beliefs["C"] < 1

    def test_run_residual_with_hard_evidence(self):
        fg = FactorGraph()
        fg.add_variable("A", 0.5)
        fg.add_variable("B", 0.5)
        fg.add_factor("f", FactorType.SOFT_ENTAILMENT, ["A"], "B", p1=0.9, p2=0.9)
        fg.add_evidence("A", 1)
        bp = TRWBeliefPropagation(max_iterations=50)
        object.__setattr__(bp, "_schedule", "residual")
        result = bp.run(fg)
        assert result.beliefs["A"] == pytest.approx(1.0 - CROMWELL_EPS, abs=1e-6)

    def test_run_residual_hard_evidence_zero(self):
        fg = FactorGraph()
        fg.add_variable("A", 0.5)
        fg.add_variable("B", 0.5)
        fg.add_factor("f", FactorType.SOFT_ENTAILMENT, ["A"], "B", p1=0.9, p2=0.9)
        fg.add_evidence("A", 0)
        bp = TRWBeliefPropagation(max_iterations=50)
        object.__setattr__(bp, "_schedule", "residual")
        result = bp.run(fg)
        assert result.beliefs["A"] == pytest.approx(CROMWELL_EPS, abs=1e-6)
        assert result.beliefs["B"] < 0.5

    def test_run_residual_convergence(self):
        fg = FactorGraph()
        fg.add_variable("A", 0.9)
        fg.add_variable("B", 0.5)
        fg.add_factor("f", FactorType.SOFT_ENTAILMENT, ["A"], "B", p1=0.95, p2=0.95)
        bp = TRWBeliefPropagation(max_iterations=200, convergence_threshold=1e-4)
        object.__setattr__(bp, "_schedule", "residual")
        result = bp.run(fg)
        assert result.diagnostics.converged

    def test_run_residual_max_iter_exhausted(self):
        fg = FactorGraph()
        fg.add_variable("A", 0.9)
        fg.add_variable("B", 0.5)
        fg.add_variable("H", 0.5)
        fg.add_factor("f1", FactorType.SOFT_ENTAILMENT, ["A"], "B", p1=0.95, p2=0.9)
        fg.add_factor("f2", FactorType.CONTRADICTION, ["A", "B"], "H")
        bp = TRWBeliefPropagation(max_iterations=5, convergence_threshold=1e-300)
        object.__setattr__(bp, "_schedule", "residual")
        result = bp.run(fg)
        assert not result.diagnostics.converged
        assert 0 < result.beliefs["A"] < 1

    def test_prior_for_no_unary_factor(self):
        fg = FactorGraph()
        fg.add_variable("A")
        fg.add_variable("B", 0.5)
        fg.add_factor("f", FactorType.SOFT_ENTAILMENT, ["A"], "B", p1=0.8, p2=0.9)
        result = TRWBeliefPropagation().run(fg)
        assert 0 < result.beliefs["A"] < 1

    def test_synchronous_not_converged_final_beliefs(self):
        fg = FactorGraph()
        fg.add_variable("A", 0.9)
        fg.add_variable("B", 0.5)
        fg.add_variable("H", 0.5)
        fg.add_factor("f1", FactorType.SOFT_ENTAILMENT, ["A"], "B", p1=0.95, p2=0.9)
        fg.add_factor("f2", FactorType.CONTRADICTION, ["A", "B"], "H")
        result = TRWBeliefPropagation(max_iterations=1, convergence_threshold=1e-12).run(fg)
        assert not result.diagnostics.converged
        assert 0 < result.beliefs["A"] < 1
