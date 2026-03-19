"""Tests for conflict discovery (BP Level 1 + Level 2)."""

from libs.curation.conflict import (
    detect_conflicts_level1,
    detect_conflicts_level2,
)
from libs.inference.bp import BPDiagnostics, BeliefPropagation
from libs.inference.factor_graph import FactorGraph


def _make_contradictory_graph() -> FactorGraph:
    """Create a graph with inherent contradiction: A→B but A∧B is contradictory."""
    g = FactorGraph()
    g.add_variable(1, 0.8)
    g.add_variable(2, 0.8)
    g.add_factor(0, [1], [2], 0.95, "deduction")
    g.add_factor(1, [1, 2], [], 0.95, "relation_contradiction")
    return g


def _make_clean_graph() -> FactorGraph:
    """Create a graph with no contradictions."""
    g = FactorGraph()
    g.add_variable(1, 0.8)
    g.add_variable(2, 0.5)
    g.add_factor(0, [1], [2], 0.9, "deduction")
    return g


# ── Level 1: Oscillation detection ──


def test_level1_finds_oscillating_nodes():
    """Contradictory graph should produce oscillation or uncertain beliefs."""
    g = _make_contradictory_graph()
    bp = BeliefPropagation(max_iterations=50, damping=0.3)
    beliefs, diag = bp.run_with_diagnostics(g)
    # With a contradiction, at least one node should have direction changes
    total_changes = sum(diag.direction_changes.values())
    assert total_changes > 0, "Contradictory graph should cause belief oscillation"
    # Use relaxed threshold to ensure we capture the oscillation
    candidates = detect_conflicts_level1(diag, min_direction_changes=1, belief_range=(0.0, 1.0))
    assert len(candidates) >= 1, "Should find at least one conflict candidate"


def test_level1_clean_graph_no_conflicts():
    """Clean graph should produce no oscillation signals."""
    g = _make_clean_graph()
    bp = BeliefPropagation(max_iterations=50)
    _, diag = bp.run_with_diagnostics(g)
    candidates = detect_conflicts_level1(diag, min_direction_changes=3)
    assert candidates == []


def test_level1_empty_diagnostics():
    """Empty diagnostics produce no candidates."""
    diag = BPDiagnostics()
    assert detect_conflicts_level1(diag) == []


# ── Level 2: Sensitivity analysis ──


def test_level2_finds_antagonistic_pair():
    """Clamping A to true should cause B to drop when they are contradictory."""
    g = _make_contradictory_graph()
    bp = BeliefPropagation(max_iterations=50, damping=0.5)

    # Run baseline
    baseline_beliefs = bp.run(g)

    # Sensitivity analysis for node 2 — clamping the conclusion to true
    # triggers the relation_contradiction on (1,2), pushing node 1's belief down
    candidates = detect_conflicts_level2(
        graph=g,
        probe_node_ids=[2],
        baseline_beliefs=baseline_beliefs,
        bp=bp,
        min_drop=0.01,
    )
    # Clamping node 2 to true with a relation_contradiction on (1,2) should
    # cause node 1's belief to drop significantly.
    assert len(candidates) >= 1, "Clamping contradictory node should affect its partner"


def test_level2_clean_graph_no_antagonism():
    """In a supportive graph, clamping A should not cause B to drop significantly."""
    g = _make_clean_graph()
    bp = BeliefPropagation(max_iterations=50)
    baseline_beliefs = bp.run(g)

    candidates = detect_conflicts_level2(
        graph=g,
        probe_node_ids=[1],
        baseline_beliefs=baseline_beliefs,
        bp=bp,
        min_drop=0.1,
    )
    # No antagonistic relationships in a purely supportive graph
    assert candidates == []


def test_level2_empty_probe():
    """No probe nodes means no candidates."""
    g = _make_clean_graph()
    bp = BeliefPropagation()
    baseline = bp.run(g)
    candidates = detect_conflicts_level2(
        graph=g, probe_node_ids=[], baseline_beliefs=baseline, bp=bp
    )
    assert candidates == []
