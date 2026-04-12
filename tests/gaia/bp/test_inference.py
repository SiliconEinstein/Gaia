"""Unit tests for BP inference algorithms: bp, exact, junction_tree, gbp, engine."""

import pytest

from gaia.bp import BeliefPropagation, FactorGraph, FactorType
from gaia.bp.bp import BPResult
from gaia.bp.exact import exact_inference
from gaia.bp.junction_tree import JunctionTreeInference, jt_treewidth
from gaia.bp.gbp import GeneralizedBeliefPropagation, build_region_graph, detect_short_cycles
from gaia.bp.engine import InferenceEngine, EngineConfig


# ── Shared fixtures ──


def _simple_chain() -> FactorGraph:
    """A → B → C with soft entailment."""
    fg = FactorGraph()
    fg.add_variable("A", 0.9)
    fg.add_variable("B", 0.5)
    fg.add_variable("C", 0.5)
    fg.add_factor("f1", FactorType.SOFT_ENTAILMENT, ["A"], "B", p1=0.8, p2=0.9)
    fg.add_factor("f2", FactorType.SOFT_ENTAILMENT, ["B"], "C", p1=0.85, p2=0.9)
    return fg


def _diamond_graph() -> FactorGraph:
    """A → B, A → C, B+C → D (noisy-and style)."""
    fg = FactorGraph()
    fg.add_variable("A", 0.8)
    fg.add_variable("B", 0.5)
    fg.add_variable("C", 0.5)
    fg.add_variable("M", 0.5)  # conjunction helper
    fg.add_variable("D", 0.5)
    fg.add_factor("f1", FactorType.SOFT_ENTAILMENT, ["A"], "B", p1=0.9, p2=0.95)
    fg.add_factor("f2", FactorType.SOFT_ENTAILMENT, ["A"], "C", p1=0.85, p2=0.9)
    fg.add_factor("f3", FactorType.CONJUNCTION, ["B", "C"], "M")
    fg.add_factor("f4", FactorType.SOFT_ENTAILMENT, ["M"], "D", p1=0.9, p2=0.95)
    return fg


def _contradiction_graph() -> FactorGraph:
    """A and B cannot both be true."""
    fg = FactorGraph()
    fg.add_variable("A", 0.7)
    fg.add_variable("B", 0.3)
    fg.add_variable("H", 0.5)
    fg.add_factor("f1", FactorType.CONTRADICTION, ["A", "B"], "H")
    return fg


def _implication_chain() -> FactorGraph:
    """A → B → C (deterministic) with helper claims."""
    fg = FactorGraph()
    fg.add_variable("A", 0.8)
    fg.add_variable("B", 0.5)
    fg.add_variable("C", 0.5)
    fg.add_variable("H1", 1.0 - 1e-3)
    fg.add_variable("H2", 1.0 - 1e-3)
    fg.add_factor("f1", FactorType.IMPLICATION, ["A", "B"], "H1")
    fg.add_factor("f2", FactorType.IMPLICATION, ["B", "C"], "H2")
    return fg


def _frustrated_graph() -> FactorGraph:
    """A chain that feeds into contradictions: double frustration.

    A (0.9) → B → C, but both (A, C) and (B, C) contradict.
    Helpers H1, H2 absorb the tension and show direction changes
    in their belief history — the oscillation signal consumed by
    curation conflict discovery (docs/specs/2026-03-31-m6-curation.md).
    """
    fg = FactorGraph()
    fg.add_variable("A", 0.9)
    fg.add_variable("B", 0.5)
    fg.add_variable("C", 0.5)
    fg.add_variable("H1", 0.5)
    fg.add_variable("H2", 0.5)
    fg.add_factor("f1", FactorType.SOFT_ENTAILMENT, ["A"], "B", p1=0.95, p2=0.9)
    fg.add_factor("f2", FactorType.SOFT_ENTAILMENT, ["B"], "C", p1=0.95, p2=0.9)
    fg.add_factor("f3", FactorType.CONTRADICTION, ["A", "C"], "H1")
    fg.add_factor("f4", FactorType.CONTRADICTION, ["B", "C"], "H2")
    return fg


def _two_cluster_graph() -> FactorGraph:
    """Two clusters connected by a cross-region conjunction factor.

    Cluster 1: A → B (soft entailment)
    Cluster 2: C → D (soft entailment)
    Cross:     B + C → M (conjunction)
    """
    fg = FactorGraph()
    fg.add_variable("A", 0.9)
    fg.add_variable("B", 0.5)
    fg.add_variable("C", 0.8)
    fg.add_variable("D", 0.5)
    fg.add_variable("M", 0.5)
    fg.add_factor("f1", FactorType.SOFT_ENTAILMENT, ["A"], "B", p1=0.9, p2=0.9)
    fg.add_factor("f2", FactorType.SOFT_ENTAILMENT, ["C"], "D", p1=0.85, p2=0.9)
    fg.add_factor("f3", FactorType.CONJUNCTION, ["B", "C"], "M")
    return fg


# ── BeliefPropagation ──


class TestBeliefPropagation:
    def test_empty_graph(self):
        fg = FactorGraph()
        result = BeliefPropagation().run(fg)
        assert result.beliefs == {}
        assert result.diagnostics.converged

    def test_no_factors_returns_priors(self):
        fg = FactorGraph()
        fg.add_variable("A", 0.7)
        fg.add_variable("B", 0.3)
        result = BeliefPropagation().run(fg)
        assert result.beliefs["A"] == pytest.approx(0.7, abs=0.01)
        assert result.beliefs["B"] == pytest.approx(0.3, abs=0.01)

    def test_simple_chain_converges(self):
        result = BeliefPropagation(damping=0.5, max_iterations=100).run(_simple_chain())
        assert result.diagnostics.converged
        assert 0 < result.beliefs["A"] < 1
        assert 0 < result.beliefs["B"] < 1
        assert 0 < result.beliefs["C"] < 1

    def test_implication_propagates(self):
        result = BeliefPropagation().run(_implication_chain())
        assert result.beliefs["B"] > 0.5
        assert result.beliefs["C"] > 0.5

    def test_contradiction_pushes_apart(self):
        result = BeliefPropagation().run(_contradiction_graph())
        assert result.beliefs["A"] > result.beliefs["B"]

    def test_diamond_converges(self):
        result = BeliefPropagation().run(_diamond_graph())
        assert result.diagnostics.converged
        assert 0 < result.beliefs["D"] < 1

    def test_damping_affects_convergence(self):
        fg = _diamond_graph()
        r_fast = BeliefPropagation(damping=1.0, max_iterations=200).run(fg)
        r_slow = BeliefPropagation(damping=0.3, max_iterations=200).run(fg)
        for v in fg.variables:
            assert r_fast.beliefs[v] == pytest.approx(r_slow.beliefs[v], abs=0.05)

    def test_observed_variable(self):
        fg = FactorGraph()
        fg.add_variable("A", 0.5)
        fg.add_variable("B", 0.5)
        fg.add_variable("H", 1.0 - 1e-3)
        fg.add_factor("f1", FactorType.IMPLICATION, ["A", "B"], "H")
        fg.observe("A", 1)
        result = BeliefPropagation().run(fg)
        assert result.beliefs["A"] > 0.99
        assert result.beliefs["B"] > 0.99

    def test_diagnostics_history(self):
        result = BeliefPropagation(max_iterations=50).run(_simple_chain())
        for var in ["A", "B", "C"]:
            assert len(result.diagnostics.belief_history.get(var, [])) > 0


# ── Exact inference ──


class TestExactInference:
    def test_simple_chain(self):
        beliefs, Z = exact_inference(_simple_chain())
        assert Z > 0
        assert 0 < beliefs["A"] < 1
        assert 0 < beliefs["B"] < 1

    def test_implication_chain(self):
        beliefs, Z = exact_inference(_implication_chain())
        assert beliefs["B"] > 0.5
        assert beliefs["C"] > 0.5

    def test_contradiction(self):
        beliefs, Z = exact_inference(_contradiction_graph())
        assert beliefs["A"] > beliefs["B"]

    def test_diamond(self):
        beliefs, Z = exact_inference(_diamond_graph())
        assert 0 < beliefs["D"] < 1

    def test_no_factors(self):
        fg = FactorGraph()
        fg.add_variable("X", 0.6)
        beliefs, Z = exact_inference(fg)
        assert beliefs["X"] == pytest.approx(0.6, abs=0.01)


# ── BP vs Exact comparison ──


class TestBPvsExact:
    """Verify BP produces results close to exact inference on small graphs."""

    @pytest.fixture(
        params=[
            ("chain", _simple_chain),
            ("diamond", _diamond_graph),
            ("contradiction", _contradiction_graph),
            ("implication", _implication_chain),
        ],
        ids=lambda p: p[0],
    )
    def graph_pair(self, request):
        name, builder = request.param
        return builder()

    def test_bp_close_to_exact(self, graph_pair):
        fg = graph_pair
        exact_beliefs, _ = exact_inference(fg)
        bp_result = BeliefPropagation(damping=0.5, max_iterations=200).run(fg)
        for var in fg.variables:
            assert bp_result.beliefs[var] == pytest.approx(exact_beliefs[var], abs=0.15), (
                f"BP belief for {var} ({bp_result.beliefs[var]:.4f}) "
                f"differs from exact ({exact_beliefs[var]:.4f})"
            )


# ── Junction Tree ──


class TestJunctionTree:
    def test_simple_chain(self):
        result = JunctionTreeInference().run(_simple_chain())
        assert isinstance(result, BPResult)
        assert 0 < result.beliefs["A"] < 1

    def test_jt_matches_exact(self):
        fg = _diamond_graph()
        exact_beliefs, _ = exact_inference(fg)
        jt_result = JunctionTreeInference().run(fg)
        for var in fg.variables:
            assert jt_result.beliefs[var] == pytest.approx(exact_beliefs[var], abs=0.01), (
                f"JT belief for {var} ({jt_result.beliefs[var]:.4f}) "
                f"differs from exact ({exact_beliefs[var]:.4f})"
            )

    def test_treewidth_estimation(self):
        fg = _simple_chain()
        tw = jt_treewidth(fg)
        assert tw >= 1

    def test_contradiction(self):
        result = JunctionTreeInference().run(_contradiction_graph())
        assert result.beliefs["A"] > result.beliefs["B"]


# ── Generalized BP ──


class TestGBP:
    def test_simple_chain(self):
        result = GeneralizedBeliefPropagation().run(_simple_chain())
        assert isinstance(result, BPResult)
        assert 0 < result.beliefs["A"] < 1

    def test_gbp_close_to_exact(self):
        fg = _diamond_graph()
        exact_beliefs, _ = exact_inference(fg)
        gbp_result = GeneralizedBeliefPropagation().run(fg)
        for var in fg.variables:
            assert gbp_result.beliefs[var] == pytest.approx(exact_beliefs[var], abs=0.05)


# ── InferenceEngine ──


class TestInferenceEngine:
    def test_auto_selects_method(self):
        engine = InferenceEngine()
        result = engine.run(_simple_chain())
        assert result.method_used in ("jt", "gbp", "bp", "exact")
        assert 0 < result.beliefs["A"] < 1

    def test_force_bp(self):
        engine = InferenceEngine()
        result = engine.run(_simple_chain(), method="bp")
        assert result.method_used == "bp"

    def test_force_jt(self):
        engine = InferenceEngine()
        result = engine.run(_simple_chain(), method="jt")
        assert result.method_used == "jt"
        assert result.is_exact

    def test_force_exact(self):
        engine = InferenceEngine()
        result = engine.run(_simple_chain(), method="exact")
        assert result.method_used == "exact"
        assert result.is_exact

    def test_force_gbp(self):
        engine = InferenceEngine()
        result = engine.run(_diamond_graph(), method="gbp")
        assert result.method_used == "gbp"

    def test_auto_prefers_jt_for_small_treewidth(self):
        engine = InferenceEngine(config=EngineConfig(jt_max_treewidth=15))
        result = engine.run(_simple_chain())
        assert result.method_used == "jt"

    def test_elapsed_ms(self):
        engine = InferenceEngine()
        result = engine.run(_simple_chain())
        assert result.elapsed_ms >= 0

    def test_treewidth_reported(self):
        engine = InferenceEngine()
        result = engine.run(_simple_chain())
        assert result.treewidth >= 0

    def test_benchmark(self):
        engine = InferenceEngine()
        report = engine.benchmark(_simple_chain())
        assert "jt" in report or "bp" in report
        for method_data in report.values():
            assert "beliefs" in method_data
            assert "elapsed_ms" in method_data


# ── Oscillation diagnostics ──


class TestOscillationDiagnostics:
    """Tests for BPDiagnostics.direction_changes — the oscillation detection
    signal consumed by curation conflict discovery (m6-curation spec)."""

    def test_frustrated_graph_has_direction_changes(self):
        """Chain + double contradiction creates tension in helper variables.

        In v2 BP, contradiction helpers (H1, H2) absorb tension and show
        direction changes. The curation spec uses total direction_changes > 0
        as a conflict signal.
        """
        result = BeliefPropagation(max_iterations=50, damping=0.9).run(_frustrated_graph())
        diag = result.diagnostics
        assert isinstance(diag.direction_changes, dict)
        assert len(diag.direction_changes) == len(_frustrated_graph().variables)
        total_changes = sum(diag.direction_changes.values())
        assert total_changes >= 2, (
            f"Frustrated graph (chain + double contradiction) should produce "
            f"direction changes in helper variables, got total={total_changes}"
        )

    def test_clean_chain_below_conflict_threshold(self):
        """Tree graph: no variable exceeds the curation conflict threshold.

        Synchronous BP scheduling may cause 1 direction change on leaf variables
        (initial overshoot), but no variable should reach the curation threshold
        of min_direction_changes=2 (per m6-curation spec §Level 1).
        """
        result = BeliefPropagation(max_iterations=50).run(_simple_chain())
        diag = result.diagnostics
        assert diag.converged
        for vid, changes in diag.direction_changes.items():
            assert changes < 2, (
                f"Tree graph variable {vid} has {changes} direction changes, "
                f"should be below curation threshold of 2"
            )

    def test_belief_table_formatting(self):
        """BPDiagnostics.belief_table() returns a formatted string with headers."""
        result = BeliefPropagation(max_iterations=20).run(_simple_chain())
        table = result.diagnostics.belief_table()
        assert "A" in table
        assert "iter" in table

    def test_direction_changes_count_matches_sign_flips(self):
        """Verify direction_changes counts actual sign flips in belief_history."""
        result = BeliefPropagation(max_iterations=50, damping=0.9).run(_frustrated_graph())
        diag = result.diagnostics
        for vid, history in diag.belief_history.items():
            expected = 0
            for k in range(2, len(history)):
                d_prev = history[k - 1] - history[k - 2]
                d_curr = history[k] - history[k - 1]
                if d_prev * d_curr < 0:
                    expected += 1
            assert diag.direction_changes[vid] == expected, (
                f"direction_changes[{vid}] = {diag.direction_changes[vid]} "
                f"but manual count from belief_history = {expected}"
            )


# ── BP non-convergence ──


class TestBPNonConvergence:
    """Test the non-convergence code path (bp.py L411-416)."""

    def test_insufficient_iterations_does_not_converge(self):
        """Diamond graph with 3 iterations and tight threshold should not converge."""
        result = BeliefPropagation(max_iterations=3, convergence_threshold=1e-15).run(
            _diamond_graph()
        )
        assert result.diagnostics.converged is False
        assert result.diagnostics.iterations_run == 3
        assert result.diagnostics.max_change_at_stop > 1e-15
        for var in _diamond_graph().variables:
            assert 0 < result.beliefs[var] < 1


# ── GBP region decomposition ──


class TestGBPRegionDecomposition:
    """Test GBP's region decomposition path by setting jt_threshold=0.

    With jt_threshold=0, any graph with treewidth >= 1 bypasses the JT
    delegation shortcut and exercises the full region decomposition pipeline:
    cycle detection → region merging → intra-region JT → cross-region BP →
    belief combination via likelihood ratio.
    """

    def test_chain_via_region_decomposition(self):
        """Chain (no cycles): singleton regions, all factors are cross-region."""
        gbp = GeneralizedBeliefPropagation(jt_threshold=0)
        fg = _simple_chain()
        result = gbp.run(fg)
        exact_beliefs, _ = exact_inference(fg)
        for var in fg.variables:
            assert result.beliefs[var] == pytest.approx(exact_beliefs[var], abs=0.05), (
                f"GBP region decomp for {var}: "
                f"got {result.beliefs[var]:.4f}, exact {exact_beliefs[var]:.4f}"
            )

    def test_diamond_via_region_decomposition(self):
        """Diamond (has cycles): variables should merge into regions."""
        gbp = GeneralizedBeliefPropagation(jt_threshold=0)
        fg = _diamond_graph()
        result = gbp.run(fg)
        exact_beliefs, _ = exact_inference(fg)
        for var in fg.variables:
            assert result.beliefs[var] == pytest.approx(exact_beliefs[var], abs=0.15), (
                f"GBP region decomp for {var}: "
                f"got {result.beliefs[var]:.4f}, exact {exact_beliefs[var]:.4f}"
            )

    def test_contradiction_via_region_decomposition(self):
        """Contradiction graph through region path preserves A > B ordering."""
        gbp = GeneralizedBeliefPropagation(jt_threshold=0)
        result = gbp.run(_contradiction_graph())
        assert result.beliefs["A"] > result.beliefs["B"]

    def test_two_clusters_with_cross_factor(self):
        """Two clusters connected by conjunction: exercises cross-region BP.

        GBP region decomposition introduces approximation error on variables
        that sit at cross-region factor boundaries (here: M = AND(B, C)).
        Primary variables (A, B, C, D) should be within 0.05; conjunction
        helper M has larger error (~0.25) due to the likelihood-ratio
        combination step across singleton regions.
        """
        gbp = GeneralizedBeliefPropagation(jt_threshold=0)
        fg = _two_cluster_graph()
        result = gbp.run(fg)
        exact_beliefs, _ = exact_inference(fg)
        for var in fg.variables:
            tol = 0.30 if var == "M" else 0.05
            assert result.beliefs[var] == pytest.approx(exact_beliefs[var], abs=tol), (
                f"GBP two-cluster for {var}: "
                f"got {result.beliefs[var]:.4f}, exact {exact_beliefs[var]:.4f}"
            )

    def test_detect_short_cycles_on_diamond(self):
        """Diamond moral graph should contain at least one short cycle."""
        cycles = detect_short_cycles(_diamond_graph(), max_cycle_len=6)
        assert isinstance(cycles, list)
        assert len(cycles) >= 1, (
            "Diamond graph moral graph has cycle A-B-M-C-A; detect_short_cycles should find it"
        )

    def test_detect_short_cycles_on_chain(self):
        """Chain graph has no cycles."""
        cycles = detect_short_cycles(_simple_chain(), max_cycle_len=6)
        assert cycles == []

    def test_build_region_graph_chain_singletons(self):
        """Chain (no cycles) → each variable is its own singleton region."""
        regions = build_region_graph(_simple_chain(), max_cycle_len=6)
        all_vars = set(_simple_chain().variables.keys())
        covered = set()
        for region in regions:
            covered |= region
        assert covered == all_vars
        for region in regions:
            assert len(region) == 1, (
                f"Chain graph should have singleton regions, got region with {len(region)} vars"
            )

    def test_build_region_graph_diamond_merges(self):
        """Diamond graph cycles should cause variable merging into larger regions."""
        regions = build_region_graph(_diamond_graph(), max_cycle_len=6)
        all_vars = set(_diamond_graph().variables.keys())
        covered = set()
        for region in regions:
            covered |= region
        assert covered == all_vars
        max_region_size = max(len(r) for r in regions)
        assert max_region_size >= 2, (
            "Diamond graph has cycles; at least one region should merge multiple variables"
        )
