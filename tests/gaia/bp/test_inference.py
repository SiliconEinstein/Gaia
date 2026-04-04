"""Unit tests for BP inference algorithms: bp, exact, junction_tree, gbp, engine."""

import pytest

from gaia.bp import BeliefPropagation, FactorGraph, FactorType
from gaia.bp.bp import BPResult
from gaia.bp.exact import exact_inference
from gaia.bp.junction_tree import JunctionTreeInference, jt_treewidth
from gaia.bp.gbp import GeneralizedBeliefPropagation
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
    """A → B → C (deterministic)."""
    fg = FactorGraph()
    fg.add_variable("A", 0.8)
    fg.add_variable("B", 0.5)
    fg.add_variable("C", 0.5)
    fg.add_factor("f1", FactorType.IMPLICATION, ["A"], "B")
    fg.add_factor("f2", FactorType.IMPLICATION, ["B"], "C")
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
        # A=0.8 implies B, B implies C; beliefs should propagate
        assert result.beliefs["B"] > 0.5
        assert result.beliefs["C"] > 0.5

    def test_contradiction_pushes_apart(self):
        result = BeliefPropagation().run(_contradiction_graph())
        # A=0.7 prior, B=0.3 prior; contradiction should push them further apart
        assert result.beliefs["A"] > result.beliefs["B"]

    def test_diamond_converges(self):
        result = BeliefPropagation().run(_diamond_graph())
        assert result.diagnostics.converged
        assert 0 < result.beliefs["D"] < 1

    def test_damping_affects_convergence(self):
        fg = _diamond_graph()
        # High damping (fast but may oscillate)
        r_fast = BeliefPropagation(damping=1.0, max_iterations=200).run(fg)
        # Low damping (slow but stable)
        r_slow = BeliefPropagation(damping=0.3, max_iterations=200).run(fg)
        # Both should converge to similar beliefs
        for v in fg.variables:
            assert r_fast.beliefs[v] == pytest.approx(r_slow.beliefs[v], abs=0.05)

    def test_observed_variable(self):
        fg = FactorGraph()
        fg.add_variable("A", 0.5)
        fg.add_variable("B", 0.5)
        fg.add_factor("f1", FactorType.IMPLICATION, ["A"], "B")
        fg.observe("A", 1)
        result = BeliefPropagation().run(fg)
        assert result.beliefs["A"] > 0.99
        assert result.beliefs["B"] > 0.99

    def test_diagnostics_history(self):
        result = BeliefPropagation(max_iterations=50).run(_simple_chain())
        # History should have entries for each iteration
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
        # A → B → C with A prior 0.8
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
            # Loopy BP is approximate on cyclic graphs; allow wider tolerance
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
        assert tw >= 1  # at least 1 for any connected graph

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
        # Small graph → treewidth low → JT expected
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
