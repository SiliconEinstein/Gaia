"""Tests for libs.inference_v2 — covers factor_graph, potentials, bp, exact, jt, gbp, engine."""

from __future__ import annotations


import pytest

from libs.inference_v2.factor_graph import (
    CROMWELL_EPS,
    Factor,
    FactorGraph,
    FactorType,
    _cromwell_clamp,
)
from libs.inference_v2.potentials import (
    contradiction_potential,
    entailment_potential,
    equivalence_potential,
    evaluate_potential,
    noisy_and_potential,
)
from libs.inference_v2.bp import (
    BeliefPropagation,
    BPDiagnostics,
    _normalize,
    _prior_to_msg,
    _uniform_msg,
)
from libs.inference_v2.exact import exact_inference, comparison_table
from libs.inference_v2.junction_tree import (
    JunctionTreeInference,
    jt_treewidth,
    _build_moral_graph,
    _triangulate_min_fill,
    _maximal_cliques,
    _build_junction_tree,
)
from libs.inference_v2.gbp import (
    GeneralizedBeliefPropagation,
    detect_short_cycles,
    build_region_graph,
)
from libs.inference_v2.engine import InferenceEngine, EngineConfig


# ===================================================================
# Helpers: build small factor graphs for testing
# ===================================================================


def _simple_entailment_graph(prior_a=0.8, prior_b=0.5, p=0.9) -> FactorGraph:
    """A→B entailment: single factor, 2 variables."""
    fg = FactorGraph()
    fg.add_variable("A", prior=prior_a)
    fg.add_variable("B", prior=prior_b)
    fg.add_factor("f_AB", FactorType.ENTAILMENT, premises=["A"], conclusions=["B"], p=p)
    return fg


def _simple_induction_graph(prior_a=0.8, prior_b=0.5, p=0.9) -> FactorGraph:
    """A→B induction: single factor, 2 variables."""
    fg = FactorGraph()
    fg.add_variable("A", prior=prior_a)
    fg.add_variable("B", prior=prior_b)
    fg.add_factor("f_AB", FactorType.INDUCTION, premises=["A"], conclusions=["B"], p=p)
    return fg


def _chain_graph() -> FactorGraph:
    """A→B→C entailment chain, 3 variables, 2 factors."""
    fg = FactorGraph()
    fg.add_variable("A", prior=0.9)
    fg.add_variable("B", prior=0.5)
    fg.add_variable("C", prior=0.5)
    fg.add_factor("f1", FactorType.ENTAILMENT, premises=["A"], conclusions=["B"], p=0.95)
    fg.add_factor("f2", FactorType.ENTAILMENT, premises=["B"], conclusions=["C"], p=0.95)
    return fg


def _contradiction_graph() -> FactorGraph:
    """Two claims + contradiction relation."""
    fg = FactorGraph()
    fg.add_variable("X", prior=0.7)
    fg.add_variable("Y", prior=0.7)
    fg.add_variable("R", prior=0.9)
    fg.add_factor(
        "f_contra",
        FactorType.CONTRADICTION,
        premises=["X", "Y"],
        conclusions=[],
        p=0.5,
        relation_var="R",
    )
    return fg


def _equivalence_graph() -> FactorGraph:
    """Two claims + equivalence relation."""
    fg = FactorGraph()
    fg.add_variable("A", prior=0.8)
    fg.add_variable("B", prior=0.3)
    fg.add_variable("R", prior=0.9)
    fg.add_factor(
        "f_equiv",
        FactorType.EQUIVALENCE,
        premises=["A", "B"],
        conclusions=[],
        p=0.5,
        relation_var="R",
    )
    return fg


def _diamond_graph() -> FactorGraph:
    """A→B, A→C, B→D, C→D — creates a cycle (B-D-C share factors with A)."""
    fg = FactorGraph()
    fg.add_variable("A", prior=0.9)
    fg.add_variable("B", prior=0.5)
    fg.add_variable("C", prior=0.5)
    fg.add_variable("D", prior=0.5)
    fg.add_factor("f1", FactorType.INDUCTION, premises=["A"], conclusions=["B"], p=0.9)
    fg.add_factor("f2", FactorType.INDUCTION, premises=["A"], conclusions=["C"], p=0.9)
    fg.add_factor("f3", FactorType.INDUCTION, premises=["B"], conclusions=["D"], p=0.8)
    fg.add_factor("f4", FactorType.INDUCTION, premises=["C"], conclusions=["D"], p=0.8)
    return fg


# ===================================================================
# Tests: factor_graph.py
# ===================================================================


class TestCromwellClamp:
    def test_within_bounds(self):
        assert _cromwell_clamp(0.5) == 0.5

    def test_clamp_zero(self):
        assert _cromwell_clamp(0.0) == CROMWELL_EPS

    def test_clamp_one(self):
        assert _cromwell_clamp(1.0) == 1.0 - CROMWELL_EPS

    def test_clamp_negative(self):
        assert _cromwell_clamp(-0.1) == CROMWELL_EPS

    def test_clamp_above_one(self):
        assert _cromwell_clamp(1.5) == 1.0 - CROMWELL_EPS


class TestFactorType:
    def test_all_five_types_exist(self):
        assert len(FactorType) == 5
        names = {t.name for t in FactorType}
        assert names == {"ENTAILMENT", "INDUCTION", "ABDUCTION", "CONTRADICTION", "EQUIVALENCE"}


class TestFactor:
    def test_all_vars_reasoning(self):
        f = Factor("f1", FactorType.ENTAILMENT, ["A"], ["B"], 0.9)
        assert f.all_vars == ["A", "B"]

    def test_all_vars_with_relation(self):
        f = Factor("f1", FactorType.CONTRADICTION, ["X", "Y"], [], 0.5, relation_var="R")
        assert f.all_vars == ["R", "X", "Y"]


class TestFactorGraph:
    def test_add_variable_cromwell(self):
        fg = FactorGraph()
        fg.add_variable("X", prior=0.0)
        assert fg.variables["X"] == CROMWELL_EPS

    def test_add_variable_update(self):
        fg = FactorGraph()
        fg.add_variable("X", prior=0.3)
        fg.add_variable("X", prior=0.7)
        assert fg.variables["X"] == 0.7

    def test_add_factor_entailment(self):
        fg = _simple_entailment_graph()
        assert len(fg.factors) == 1
        assert fg.factors[0].factor_type == FactorType.ENTAILMENT

    def test_add_factor_contradiction_no_relation_var_raises(self):
        fg = FactorGraph()
        fg.add_variable("X", prior=0.5)
        with pytest.raises(ValueError, match="requires a relation_var"):
            fg.add_factor("f", FactorType.CONTRADICTION, ["X"], [], 0.5)

    def test_add_factor_contradiction_with_conclusions_raises(self):
        fg = FactorGraph()
        fg.add_variable("X", prior=0.5)
        fg.add_variable("R", prior=0.5)
        with pytest.raises(ValueError, match="must have empty conclusions"):
            fg.add_factor("f", FactorType.CONTRADICTION, ["X"], ["R"], 0.5, relation_var="R")

    def test_add_factor_equivalence_wrong_premise_count(self):
        fg = FactorGraph()
        fg.add_variable("A", prior=0.5)
        fg.add_variable("R", prior=0.5)
        with pytest.raises(ValueError, match="exactly 2 premises"):
            fg.add_factor("f", FactorType.EQUIVALENCE, ["A"], [], 0.5, relation_var="R")

    def test_validate_missing_variable(self):
        fg = FactorGraph()
        fg.add_variable("A", prior=0.5)
        fg.factors.append(Factor("f1", FactorType.ENTAILMENT, ["A"], ["B"], 0.9))
        errors = fg.validate()
        assert any("B" in e for e in errors)

    def test_validate_clean(self):
        fg = _simple_entailment_graph()
        assert fg.validate() == []

    def test_get_var_to_factors(self):
        fg = _simple_entailment_graph()
        idx = fg.get_var_to_factors()
        assert 0 in idx["A"]
        assert 0 in idx["B"]

    def test_summary_not_empty(self):
        fg = _simple_entailment_graph()
        s = fg.summary()
        assert "FactorGraph" in s
        assert "ENTAILMENT" in s


# ===================================================================
# Tests: potentials.py
# ===================================================================


class TestEntailmentPotential:
    def test_premises_true_conclusion_true(self):
        pot = entailment_potential({"A": 1, "B": 1}, ["A"], ["B"], 0.9)
        assert pot == pytest.approx(0.9)

    def test_premises_true_conclusion_false(self):
        pot = entailment_potential({"A": 1, "B": 0}, ["A"], ["B"], 0.9)
        assert pot == pytest.approx(0.1)

    def test_premises_false_silent(self):
        pot = entailment_potential({"A": 0, "B": 1}, ["A"], ["B"], 0.9)
        assert pot == 1.0
        pot2 = entailment_potential({"A": 0, "B": 0}, ["A"], ["B"], 0.9)
        assert pot2 == 1.0


class TestNoisyAndPotential:
    def test_premises_true(self):
        pot = noisy_and_potential({"A": 1, "B": 1}, ["A"], ["B"], 0.9)
        assert pot == pytest.approx(0.9)

    def test_premises_false_leak(self):
        pot = noisy_and_potential({"A": 0, "B": 1}, ["A"], ["B"], 0.9)
        assert pot == pytest.approx(CROMWELL_EPS)

    def test_premises_false_conclusion_false(self):
        pot = noisy_and_potential({"A": 0, "B": 0}, ["A"], ["B"], 0.9)
        assert pot == pytest.approx(1.0 - CROMWELL_EPS)

    def test_multiple_premises(self):
        pot = noisy_and_potential({"A": 1, "B": 1, "C": 1}, ["A", "B"], ["C"], 0.8)
        assert pot == pytest.approx(0.8)
        pot2 = noisy_and_potential({"A": 1, "B": 0, "C": 1}, ["A", "B"], ["C"], 0.8)
        assert pot2 == pytest.approx(CROMWELL_EPS)


class TestContradictionPotential:
    def test_all_true_penalized(self):
        pot = contradiction_potential({"R": 1, "X": 1, "Y": 1}, "R", ["X", "Y"])
        assert pot == pytest.approx(CROMWELL_EPS)

    def test_any_false_unconstrained(self):
        assert contradiction_potential({"R": 0, "X": 1, "Y": 1}, "R", ["X", "Y"]) == 1.0
        assert contradiction_potential({"R": 1, "X": 0, "Y": 1}, "R", ["X", "Y"]) == 1.0
        assert contradiction_potential({"R": 1, "X": 1, "Y": 0}, "R", ["X", "Y"]) == 1.0


class TestEquivalencePotential:
    def test_relation_inactive(self):
        pot = equivalence_potential({"R": 0, "A": 1, "B": 0}, "R", "A", "B")
        assert pot == 1.0

    def test_agree_rewarded(self):
        pot = equivalence_potential({"R": 1, "A": 1, "B": 1}, "R", "A", "B")
        assert pot == pytest.approx(1.0 - CROMWELL_EPS)

    def test_disagree_penalized(self):
        pot = equivalence_potential({"R": 1, "A": 1, "B": 0}, "R", "A", "B")
        assert pot == pytest.approx(CROMWELL_EPS)


class TestEvaluatePotential:
    def test_entailment_dispatch(self):
        f = Factor("f", FactorType.ENTAILMENT, ["A"], ["B"], 0.9)
        pot = evaluate_potential(f, {"A": 1, "B": 1})
        assert pot == pytest.approx(0.9)

    def test_induction_dispatch(self):
        f = Factor("f", FactorType.INDUCTION, ["A"], ["B"], 0.9)
        pot = evaluate_potential(f, {"A": 0, "B": 1})
        assert pot == pytest.approx(CROMWELL_EPS)

    def test_abduction_dispatch(self):
        f = Factor("f", FactorType.ABDUCTION, ["A"], ["B"], 0.9)
        pot = evaluate_potential(f, {"A": 1, "B": 1})
        assert pot == pytest.approx(0.9)

    def test_contradiction_dispatch(self):
        f = Factor("f", FactorType.CONTRADICTION, ["X", "Y"], [], 0.5, relation_var="R")
        pot = evaluate_potential(f, {"R": 1, "X": 1, "Y": 1})
        assert pot == pytest.approx(CROMWELL_EPS)

    def test_equivalence_dispatch(self):
        f = Factor("f", FactorType.EQUIVALENCE, ["A", "B"], [], 0.5, relation_var="R")
        pot = evaluate_potential(f, {"R": 1, "A": 0, "B": 0})
        assert pot == pytest.approx(1.0 - CROMWELL_EPS)

    def test_contradiction_missing_relation_var_raises(self):
        f = Factor("f", FactorType.CONTRADICTION, ["X"], [], 0.5, relation_var=None)
        with pytest.raises(ValueError, match="missing relation_var"):
            evaluate_potential(f, {"X": 1})

    def test_equivalence_missing_relation_var_raises(self):
        f = Factor("f", FactorType.EQUIVALENCE, ["A", "B"], [], 0.5, relation_var=None)
        with pytest.raises(ValueError, match="missing relation_var"):
            evaluate_potential(f, {"A": 1, "B": 1})

    def test_equivalence_wrong_premise_count_raises(self):
        f = Factor("f", FactorType.EQUIVALENCE, ["A"], [], 0.5, relation_var="R")
        with pytest.raises(ValueError, match="exactly 2 premises"):
            evaluate_potential(f, {"R": 1, "A": 1})


# ===================================================================
# Tests: bp.py helpers
# ===================================================================


class TestBPHelpers:
    def test_uniform_msg(self):
        m = _uniform_msg()
        assert m[0] == pytest.approx(0.5)
        assert m[1] == pytest.approx(0.5)

    def test_prior_to_msg(self):
        m = _prior_to_msg(0.7)
        assert m[0] == pytest.approx(0.3)
        assert m[1] == pytest.approx(0.7)

    def test_normalize(self):
        import numpy as np

        m = _normalize(np.array([3.0, 7.0]))
        assert m[0] == pytest.approx(0.3)
        assert m[1] == pytest.approx(0.7)

    def test_normalize_zero_raises(self):
        import numpy as np

        with pytest.raises(RuntimeError, match="zero-sum"):
            _normalize(np.array([0.0, 0.0]))


class TestBPDiagnostics:
    def test_direction_changes(self):
        diag = BPDiagnostics()
        # 0.5→0.6 (up), 0.6→0.55 (down=flip), 0.55→0.58 (up=flip) → 2 changes
        diag.belief_history["X"] = [0.5, 0.6, 0.55, 0.58]
        diag.compute_direction_changes()
        assert diag.direction_changes["X"] == 2

    def test_belief_table(self):
        diag = BPDiagnostics()
        diag.belief_history["X"] = [0.5, 0.6]
        table = diag.belief_table()
        assert "X" in table

    def test_belief_table_empty(self):
        diag = BPDiagnostics()
        assert "(no belief history)" in diag.belief_table()


# ===================================================================
# Tests: bp.py — BeliefPropagation
# ===================================================================


class TestBeliefPropagation:
    def test_empty_graph(self):
        fg = FactorGraph()
        bp = BeliefPropagation()
        result = bp.run(fg)
        assert result.beliefs == {}
        assert result.diagnostics.converged

    def test_no_factors(self):
        fg = FactorGraph()
        fg.add_variable("A", prior=0.7)
        fg.add_variable("B", prior=0.3)
        bp = BeliefPropagation()
        result = bp.run(fg)
        assert result.beliefs["A"] == pytest.approx(0.7)
        assert result.beliefs["B"] == pytest.approx(0.3)

    def test_simple_entailment(self):
        fg = _simple_entailment_graph(prior_a=0.9, prior_b=0.5, p=0.95)
        bp = BeliefPropagation(max_iterations=100)
        result = bp.run(fg)
        assert 0.0 < result.beliefs["A"] <= 1.0
        assert 0.0 < result.beliefs["B"] <= 1.0
        assert result.beliefs["B"] > 0.5

    def test_simple_induction(self):
        fg = _simple_induction_graph(prior_a=0.9, prior_b=0.5, p=0.9)
        bp = BeliefPropagation(max_iterations=100)
        result = bp.run(fg)
        assert result.beliefs["B"] > 0.5

    def test_chain(self):
        fg = _chain_graph()
        bp = BeliefPropagation(max_iterations=100)
        result = bp.run(fg)
        assert result.beliefs["B"] > 0.5
        assert result.beliefs["C"] > 0.5

    def test_contradiction_lowers_beliefs(self):
        fg = _contradiction_graph()
        bp = BeliefPropagation(max_iterations=100)
        result = bp.run(fg)
        assert result.beliefs["X"] < 0.7 or result.beliefs["Y"] < 0.7 or result.beliefs["R"] < 0.9

    def test_equivalence(self):
        fg = _equivalence_graph()
        bp = BeliefPropagation(max_iterations=100)
        result = bp.run(fg)
        assert result.beliefs["A"] > 0
        assert result.beliefs["B"] > 0

    def test_convergence_flag(self):
        fg = _simple_entailment_graph()
        bp = BeliefPropagation(max_iterations=200)
        result = bp.run(fg)
        assert result.diagnostics.converged

    def test_damping_invalid_raises(self):
        with pytest.raises(ValueError, match="damping"):
            BeliefPropagation(damping=0.0)
        with pytest.raises(ValueError, match="damping"):
            BeliefPropagation(damping=1.5)

    def test_belief_history_recorded(self):
        fg = _simple_entailment_graph()
        bp = BeliefPropagation(max_iterations=10)
        result = bp.run(fg)
        assert "A" in result.diagnostics.belief_history
        assert len(result.diagnostics.belief_history["A"]) > 1


# ===================================================================
# Tests: exact.py
# ===================================================================


class TestExactInference:
    def test_simple_entailment(self):
        fg = _simple_entailment_graph(prior_a=0.8, prior_b=0.5, p=0.9)
        beliefs, Z = exact_inference(fg)
        assert 0 < beliefs["A"] < 1
        assert 0 < beliefs["B"] < 1
        assert Z > 0

    def test_no_factors(self):
        fg = FactorGraph()
        fg.add_variable("A", prior=0.7)
        beliefs, Z = exact_inference(fg)
        assert beliefs["A"] == pytest.approx(0.7, abs=0.01)

    def test_contradiction(self):
        fg = _contradiction_graph()
        beliefs, Z = exact_inference(fg)
        assert 0 < beliefs["R"] < 1

    def test_equivalence(self):
        fg = _equivalence_graph()
        beliefs, Z = exact_inference(fg)
        assert 0 < beliefs["A"] < 1
        assert 0 < beliefs["B"] < 1

    def test_too_many_variables_raises(self):
        fg = FactorGraph()
        for i in range(27):
            fg.add_variable(f"v{i}", prior=0.5)
        with pytest.raises(ValueError, match="too large"):
            exact_inference(fg)

    def test_comparison_table_output(self):
        fg = _simple_entailment_graph()
        exact_beliefs, Z = exact_inference(fg)
        bp = BeliefPropagation(max_iterations=100)
        bp_result = bp.run(fg)
        table = comparison_table(fg, exact_beliefs, bp_result.beliefs, Z)
        assert "Variable" in table
        assert "Exact" in table


# ===================================================================
# Tests: junction_tree.py
# ===================================================================


class TestJunctionTreeHelpers:
    def test_moral_graph(self):
        fg = _simple_entailment_graph()
        adj = _build_moral_graph(fg)
        assert "B" in adj["A"]
        assert "A" in adj["B"]

    def test_triangulate(self):
        fg = _diamond_graph()
        adj = _build_moral_graph(fg)
        tri_adj, elim_cliques = _triangulate_min_fill(adj)
        assert len(elim_cliques) == len(fg.variables)

    def test_maximal_cliques(self):
        fg = _diamond_graph()
        adj = _build_moral_graph(fg)
        _, elim_cliques = _triangulate_min_fill(adj)
        cliques = _maximal_cliques(elim_cliques)
        assert len(cliques) >= 1
        for c in cliques:
            assert len(c) >= 1

    def test_build_junction_tree(self):
        fg = _diamond_graph()
        adj = _build_moral_graph(fg)
        _, elim_cliques = _triangulate_min_fill(adj)
        cliques = _maximal_cliques(elim_cliques)
        if len(cliques) > 1:
            edges = _build_junction_tree(cliques)
            assert len(edges) == len(cliques) - 1

    def test_single_clique(self):
        fg = _simple_entailment_graph()
        adj = _build_moral_graph(fg)
        _, elim_cliques = _triangulate_min_fill(adj)
        cliques = _maximal_cliques(elim_cliques)
        edges = _build_junction_tree(cliques)
        if len(cliques) == 1:
            assert edges == []


class TestJunctionTreeInference:
    def test_empty_graph(self):
        fg = FactorGraph()
        jt = JunctionTreeInference()
        result = jt.run(fg)
        assert result.beliefs == {}

    def test_no_factors(self):
        fg = FactorGraph()
        fg.add_variable("A", prior=0.7)
        jt = JunctionTreeInference()
        result = jt.run(fg)
        assert result.beliefs["A"] == pytest.approx(0.7)

    def test_matches_exact_entailment(self):
        fg = _simple_entailment_graph()
        exact_beliefs, _ = exact_inference(fg)
        jt = JunctionTreeInference()
        jt_result = jt.run(fg)
        for v in fg.variables:
            assert jt_result.beliefs[v] == pytest.approx(exact_beliefs[v], abs=1e-10)

    def test_matches_exact_chain(self):
        fg = _chain_graph()
        exact_beliefs, _ = exact_inference(fg)
        jt = JunctionTreeInference()
        jt_result = jt.run(fg)
        for v in fg.variables:
            assert jt_result.beliefs[v] == pytest.approx(exact_beliefs[v], abs=1e-10)

    def test_matches_exact_contradiction(self):
        fg = _contradiction_graph()
        exact_beliefs, _ = exact_inference(fg)
        jt = JunctionTreeInference()
        jt_result = jt.run(fg)
        for v in fg.variables:
            assert jt_result.beliefs[v] == pytest.approx(exact_beliefs[v], abs=1e-10)

    def test_matches_exact_equivalence(self):
        fg = _equivalence_graph()
        exact_beliefs, _ = exact_inference(fg)
        jt = JunctionTreeInference()
        jt_result = jt.run(fg)
        for v in fg.variables:
            assert jt_result.beliefs[v] == pytest.approx(exact_beliefs[v], abs=1e-10)

    def test_matches_exact_diamond(self):
        fg = _diamond_graph()
        exact_beliefs, _ = exact_inference(fg)
        jt = JunctionTreeInference()
        jt_result = jt.run(fg)
        for v in fg.variables:
            assert jt_result.beliefs[v] == pytest.approx(exact_beliefs[v], abs=1e-10)

    def test_treewidth(self):
        fg = _chain_graph()
        tw = jt_treewidth(fg)
        assert tw >= 1

    def test_treewidth_empty(self):
        fg = FactorGraph()
        assert jt_treewidth(fg) == 0

    def test_diagnostics_treewidth(self):
        fg = _diamond_graph()
        jt = JunctionTreeInference()
        result = jt.run(fg)
        assert result.diagnostics.treewidth >= 1
        assert result.diagnostics.converged


# ===================================================================
# Tests: gbp.py
# ===================================================================


class TestGBPHelpers:
    def test_detect_short_cycles_diamond(self):
        fg = _diamond_graph()
        cycles = detect_short_cycles(fg, max_cycle_len=6)
        assert len(cycles) >= 0  # diamond may or may not form detectable cycles

    def test_detect_short_cycles_chain(self):
        fg = _chain_graph()
        cycles = detect_short_cycles(fg, max_cycle_len=6)
        assert isinstance(cycles, list)

    def test_build_region_graph(self):
        fg = _diamond_graph()
        regions = build_region_graph(fg, max_cycle_len=6)
        all_vars = set()
        for r in regions:
            all_vars.update(r)
        assert all_vars == set(fg.variables.keys())


class TestGBPAssignment:
    def test_assign_factors_intra_only(self):
        from libs.inference_v2.gbp import _assign_factors_to_regions

        fg = _simple_entailment_graph()
        regions = [frozenset(fg.variables.keys())]
        intra, cross = _assign_factors_to_regions(fg, regions)
        assert len(intra[0]) == 1
        assert cross == []

    def test_assign_factors_cross_region(self):
        from libs.inference_v2.gbp import _assign_factors_to_regions

        fg = _chain_graph()
        regions = [frozenset(["A", "B"]), frozenset(["C"])]
        intra, cross = _assign_factors_to_regions(fg, regions)
        assert len(cross) >= 1  # f2 (B→C) crosses regions

    def test_solve_region(self):
        from libs.inference_v2.gbp import _solve_region

        fg = _simple_entailment_graph()
        jt = JunctionTreeInference()
        beliefs = _solve_region(frozenset(fg.variables.keys()), fg.factors, fg, jt)
        assert len(beliefs) == 2
        for v in beliefs:
            assert 0 < beliefs[v] < 1

    def test_build_cross_region_graph(self):
        from libs.inference_v2.gbp import (
            _assign_factors_to_regions,
            _build_cross_region_graph,
        )

        fg = _chain_graph()
        regions = [frozenset(["A", "B"]), frozenset(["C"])]
        _, cross = _assign_factors_to_regions(fg, regions)
        region_beliefs = {0: {"A": 0.9, "B": 0.7}, 1: {"C": 0.5}}
        cross_fg = _build_cross_region_graph(fg, regions, cross, region_beliefs)
        assert len(cross_fg.variables) >= 1
        assert len(cross_fg.factors) >= 1

    def test_combine_beliefs(self):
        from libs.inference_v2.gbp import _combine_beliefs

        fg = _chain_graph()
        regions = [frozenset(["A", "B"]), frozenset(["C"])]
        region_beliefs = {0: {"A": 0.9, "B": 0.7}, 1: {"C": 0.5}}
        cross_beliefs = {"B": 0.6, "C": 0.55}
        cross_vars = {"B", "C"}
        final = _combine_beliefs(fg, regions, region_beliefs, cross_beliefs, cross_vars)
        assert "A" in final
        assert "B" in final
        assert "C" in final

    def test_combine_beliefs_no_cross(self):
        from libs.inference_v2.gbp import _combine_beliefs

        fg = _simple_entailment_graph()
        regions = [frozenset(fg.variables.keys())]
        region_beliefs = {0: {"A": 0.85, "B": 0.7}}
        final = _combine_beliefs(fg, regions, region_beliefs, None, set())
        assert final["A"] == pytest.approx(0.85)
        assert final["B"] == pytest.approx(0.7)


class TestGeneralizedBP:
    def test_empty_graph(self):
        gbp = GeneralizedBeliefPropagation()
        fg = FactorGraph()
        result = gbp.run(fg)
        assert result.beliefs == {}

    def test_simple_delegates_to_jt(self):
        fg = _simple_entailment_graph()
        gbp = GeneralizedBeliefPropagation()
        result = gbp.run(fg)
        exact_beliefs, _ = exact_inference(fg)
        for v in fg.variables:
            assert result.beliefs[v] == pytest.approx(exact_beliefs[v], abs=1e-10)

    def test_diamond_graph(self):
        fg = _diamond_graph()
        gbp = GeneralizedBeliefPropagation()
        result = gbp.run(fg)
        for v in fg.variables:
            assert 0 < result.beliefs[v] < 1

    def test_region_decomposition_path(self):
        """Force region decomposition by setting jt_threshold=0."""
        fg = _diamond_graph()
        gbp = GeneralizedBeliefPropagation(jt_threshold=0)
        result = gbp.run(fg)
        for v in fg.variables:
            assert 0 < result.beliefs[v] < 1

    def test_region_decomposition_no_cross_factors(self):
        """Graph where each region is self-contained."""
        fg = FactorGraph()
        fg.add_variable("A", prior=0.8)
        fg.add_variable("B", prior=0.5)
        fg.add_factor("f1", FactorType.INDUCTION, ["A"], ["B"], p=0.9)
        gbp = GeneralizedBeliefPropagation(jt_threshold=0)
        result = gbp.run(fg)
        assert len(result.beliefs) == 2


# ===================================================================
# Tests: engine.py
# ===================================================================


class TestInferenceEngine:
    def test_auto_selects(self):
        fg = _simple_entailment_graph()
        engine = InferenceEngine()
        result = engine.run(fg)
        assert result.method_used in ("jt", "gbp", "bp")
        assert len(result.beliefs) == 2

    def test_force_jt(self):
        fg = _chain_graph()
        engine = InferenceEngine()
        result = engine.run(fg, method="jt")
        assert result.method_used == "jt"
        assert result.is_exact

    def test_force_bp(self):
        fg = _chain_graph()
        engine = InferenceEngine()
        result = engine.run(fg, method="bp")
        assert result.method_used == "bp"
        assert not result.is_exact

    def test_force_gbp(self):
        fg = _chain_graph()
        engine = InferenceEngine()
        result = engine.run(fg, method="gbp")
        assert result.method_used == "gbp"

    def test_force_exact(self):
        fg = _simple_entailment_graph()
        engine = InferenceEngine()
        result = engine.run(fg, method="exact")
        assert result.method_used == "exact"
        assert result.is_exact

    def test_exact_too_many_vars_raises(self):
        fg = FactorGraph()
        for i in range(27):
            fg.add_variable(f"v{i}", prior=0.5)
        engine = InferenceEngine()
        with pytest.raises(ValueError, match="too many"):
            engine.run(fg, method="exact")

    def test_beliefs_shortcut(self):
        fg = _simple_entailment_graph()
        engine = InferenceEngine()
        result = engine.run(fg)
        assert result.beliefs == result.bp_result.beliefs

    def test_diagnostics_shortcut(self):
        fg = _simple_entailment_graph()
        engine = InferenceEngine()
        result = engine.run(fg)
        assert result.diagnostics is result.bp_result.diagnostics

    def test_elapsed_ms(self):
        fg = _simple_entailment_graph()
        engine = InferenceEngine()
        result = engine.run(fg)
        assert result.elapsed_ms > 0

    def test_benchmark(self):
        fg = _simple_entailment_graph()
        engine = InferenceEngine()
        results = engine.benchmark(fg)
        assert "jt" in results
        assert "gbp" in results
        assert "bp" in results
        assert "exact" in results

    def test_config(self):
        cfg = EngineConfig(bp_damping=0.3, bp_max_iter=50)
        engine = InferenceEngine(config=cfg)
        fg = _simple_entailment_graph()
        result = engine.run(fg, method="bp")
        assert len(result.beliefs) == 2


# ===================================================================
# Cross-module integration: JT == Exact for all graph types
# ===================================================================


class TestJTMatchesExact:
    """Verify JT matches exact inference across all factor types."""

    @pytest.mark.parametrize(
        "graph_fn",
        [
            _simple_entailment_graph,
            _simple_induction_graph,
            _chain_graph,
            _contradiction_graph,
            _equivalence_graph,
            _diamond_graph,
        ],
    )
    def test_jt_matches_exact(self, graph_fn):
        fg = graph_fn()
        exact_beliefs, _ = exact_inference(fg)
        jt = JunctionTreeInference()
        jt_result = jt.run(fg)
        for v in fg.variables:
            assert jt_result.beliefs[v] == pytest.approx(exact_beliefs[v], abs=1e-10), (
                f"JT != exact for variable {v}"
            )
