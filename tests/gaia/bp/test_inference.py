"""Unit tests for BP inference algorithms: trw_bp, exact, junction_tree, engine."""

import pytest

from gaia.bp import FactorGraph, FactorType, TRWBeliefPropagation
from gaia.bp.engine import EngineConfig, InferenceEngine
from gaia.bp.exact import exact_inference
from gaia.bp.factor_graph import CROMWELL_EPS
from gaia.bp.junction_tree import JunctionTreeInference, jt_treewidth
from gaia.bp.trw_bp import TRWResult

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


# ── TRWBeliefPropagation ──


class TestTRWBeliefPropagation:
    def test_empty_graph(self):
        fg = FactorGraph()
        result = TRWBeliefPropagation().run(fg)
        assert result.beliefs == {}
        assert result.diagnostics.converged

    def test_no_factors_returns_priors(self):
        fg = FactorGraph()
        fg.add_variable("A", 0.7)
        fg.add_variable("B", 0.3)
        result = TRWBeliefPropagation().run(fg)
        assert result.beliefs["A"] == pytest.approx(0.7, abs=0.01)
        assert result.beliefs["B"] == pytest.approx(0.3, abs=0.01)

    def test_simple_chain_converges(self):
        result = TRWBeliefPropagation(damping=0.5, max_iterations=100).run(_simple_chain())
        assert result.diagnostics.converged
        assert 0 < result.beliefs["A"] < 1
        assert 0 < result.beliefs["B"] < 1
        assert 0 < result.beliefs["C"] < 1

    def test_implication_propagates(self):
        result = TRWBeliefPropagation().run(_implication_chain())
        assert result.beliefs["B"] > 0.5
        assert result.beliefs["C"] > 0.5

    def test_contradiction_pushes_apart(self):
        result = TRWBeliefPropagation().run(_contradiction_graph())
        assert result.beliefs["A"] > result.beliefs["B"]

    def test_diamond_converges(self):
        result = TRWBeliefPropagation().run(_diamond_graph())
        assert result.diagnostics.converged
        assert 0 < result.beliefs["D"] < 1

    def test_damping_affects_convergence(self):
        fg = _diamond_graph()
        r_fast = TRWBeliefPropagation(damping=1.0, max_iterations=200).run(fg)
        r_slow = TRWBeliefPropagation(damping=0.3, max_iterations=200).run(fg)
        for v in fg.variables:
            assert r_fast.beliefs[v] == pytest.approx(r_slow.beliefs[v], abs=0.05)

    def test_observed_variable(self):
        fg = FactorGraph()
        fg.add_variable("A", 0.5)
        fg.add_variable("B", 0.5)
        fg.add_variable("H", 1.0 - 1e-3)
        fg.add_factor("f1", FactorType.IMPLICATION, ["A", "B"], "H")
        fg.observe("A", 1)
        result = TRWBeliefPropagation().run(fg)
        assert result.beliefs["A"] > 0.99
        assert result.beliefs["B"] > 0.99

    def test_diagnostics_history(self):
        result = TRWBeliefPropagation(max_iterations=50).run(_simple_chain())
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
        beliefs, _Z = exact_inference(_implication_chain())
        assert beliefs["B"] > 0.5
        assert beliefs["C"] > 0.5

    def test_contradiction(self):
        beliefs, _Z = exact_inference(_contradiction_graph())
        assert beliefs["A"] > beliefs["B"]

    def test_diamond(self):
        beliefs, _Z = exact_inference(_diamond_graph())
        assert 0 < beliefs["D"] < 1

    def test_no_factors(self):
        fg = FactorGraph()
        fg.add_variable("X", 0.6)
        beliefs, _Z = exact_inference(fg)
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
        _name, builder = request.param
        return builder()

    def test_bp_close_to_exact(self, graph_pair):
        fg = graph_pair
        exact_beliefs, _ = exact_inference(fg)
        bp_result = TRWBeliefPropagation(damping=0.5, max_iterations=200).run(fg)
        for var in fg.variables:
            assert bp_result.beliefs[var] == pytest.approx(exact_beliefs[var], abs=0.15), (
                f"BP belief for {var} ({bp_result.beliefs[var]:.4f}) "
                f"differs from exact ({exact_beliefs[var]:.4f})"
            )


# ── Junction Tree ──


class TestJunctionTree:
    def test_simple_chain(self):
        result = JunctionTreeInference().run(_simple_chain())
        assert isinstance(result, TRWResult)
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


# ── InferenceEngine ──


class TestInferenceEngine:
    def test_auto_selects_method(self):
        engine = InferenceEngine()
        result = engine.run(_simple_chain())
        assert result.method_used in ("jt", "trw_bp", "mean_field", "exact")
        assert 0 < result.beliefs["A"] < 1

    def test_force_bp(self):
        engine = InferenceEngine()
        result = engine.run(_simple_chain(), method="trw_bp")
        assert result.method_used == "trw_bp"

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

    def test_force_mean_field(self):
        engine = InferenceEngine()
        result = engine.run(_diamond_graph(), method="mean_field")
        assert result.method_used == "mean_field"

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


class TestBPNonConvergence:
    """Test the non-convergence code path (bp.py L411-416)."""

    def test_insufficient_iterations_does_not_converge(self):
        """Diamond graph with 3 iterations and tight threshold should not converge."""
        result = TRWBeliefPropagation(max_iterations=3, convergence_threshold=1e-15).run(
            _diamond_graph()
        )
        assert result.diagnostics.converged is False
        assert result.diagnostics.iterations_run == 3
        assert result.diagnostics.max_change_at_stop > 1e-15
        for var in _diamond_graph().variables:
            assert 0 < result.beliefs[var] < 1


# ── SOFT_ENTAILMENT CPT: fan-out elimination via proper CPTs ──


def _soft_entailment_fanout_graph() -> FactorGraph:
    """A with 4 SOFT_ENTAILMENT children (proper CPT, p2=0.5 MaxEnt)."""
    fg = FactorGraph()
    fg.add_variable("A", 0.5)
    for i in range(4):
        fg.add_variable(f"B{i}", 0.5)
        fg.add_factor(
            f"f{i}",
            FactorType.SOFT_ENTAILMENT,
            ["A"],
            f"B{i}",
            p1=1.0 - CROMWELL_EPS,
            p2=0.5,
        )
    return fg


class TestSoftEntailmentFanout:
    """SOFT_ENTAILMENT with p2=0.5 eliminates fan-out while preserving backward inference."""

    def test_constraint_implication_has_fanout(self):
        """Baseline: constraint implication with 4 children drags A far below 0.5."""
        fg = FactorGraph()
        fg.add_variable("A", 0.5)
        for i in range(4):
            fg.add_variable(f"B{i}", 0.5)
            fg.add_variable(f"H{i}", 1.0 - CROMWELL_EPS)
            fg.add_factor(
                f"f{i}",
                FactorType.IMPLICATION,
                ["A", f"B{i}"],
                f"H{i}",
            )
        result = TRWBeliefPropagation().run(fg)
        assert result.beliefs["A"] < 0.15  # severe fan-out penalty

    def test_soft_entailment_eliminates_fanout(self):
        """SOFT_ENTAILMENT with p2=0.5: A stays at its prior (neutral children)."""
        fg = _soft_entailment_fanout_graph()
        result = TRWBeliefPropagation().run(fg)
        assert result.beliefs["A"] == pytest.approx(0.5, abs=0.02)

    def test_soft_entailment_forward_propagation(self):
        """SOFT_ENTAILMENT propagates from premise to conclusion (forward)."""
        fg = FactorGraph()
        fg.add_variable("A", 0.9)
        fg.add_variable("B", 0.5)
        fg.add_factor("f1", FactorType.SOFT_ENTAILMENT, ["A"], "B", p1=1.0 - CROMWELL_EPS, p2=0.5)
        result = TRWBeliefPropagation().run(fg)
        # B should be pulled up by A's high belief
        assert result.beliefs["B"] > 0.6

    def test_soft_entailment_backward_inference(self):
        """SOFT_ENTAILMENT preserves backward inference (weak syllogism).

        When B is observed true, A should be pulled above its prior.
        This is Jaynes' backward inference: P(H|E) > P(H) when E follows from H.
        """
        fg = FactorGraph()
        fg.add_variable("A", 0.5)
        fg.add_variable("B", 0.5)
        fg.add_factor("f1", FactorType.SOFT_ENTAILMENT, ["A"], "B", p1=0.95, p2=0.5)
        fg.observe("B", 1)
        result = TRWBeliefPropagation().run(fg)
        # A should be pulled above 0.5 (backward inference works)
        assert result.beliefs["A"] > 0.6

    def test_soft_entailment_chain_no_cascade(self):
        """Chain P → A → B1...B4: SOFT_ENTAILMENT doesn't cascade fan-out."""
        fg = FactorGraph()
        fg.add_variable("P", 0.2)
        fg.add_variable("A", 0.5)
        fg.add_factor("f_up", FactorType.SOFT_ENTAILMENT, ["P"], "A", p1=1.0 - CROMWELL_EPS, p2=0.5)
        for i in range(4):
            fg.add_variable(f"B{i}", 0.5)
            fg.add_factor(
                f"f{i}",
                FactorType.SOFT_ENTAILMENT,
                ["A"],
                f"B{i}",
                p1=1.0 - CROMWELL_EPS,
                p2=0.5,
            )
        result = TRWBeliefPropagation().run(fg)
        # P should stay near its prior (no cascade from downstream)
        assert result.beliefs["P"] == pytest.approx(0.2, abs=0.03)
