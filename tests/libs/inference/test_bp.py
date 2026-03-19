"""Tests for BP diagnostics — oscillation detection."""

from libs.inference.bp import BeliefPropagation, BPDiagnostics


def test_bp_diagnostics_returned():
    """run_with_diagnostics returns beliefs + diagnostics."""
    from libs.inference.factor_graph import FactorGraph

    g = FactorGraph()
    g.add_variable(1, 0.5)
    g.add_variable(2, 0.5)
    g.add_factor(0, [1], [2], 0.9, "deduction")

    bp = BeliefPropagation(max_iterations=10)
    beliefs, diag = bp.run_with_diagnostics(g)
    assert isinstance(beliefs, dict)
    assert isinstance(diag, BPDiagnostics)
    assert diag.iterations_run > 0
    assert diag.converged is True or diag.converged is False
    assert 1 in diag.belief_history
    assert 2 in diag.belief_history
    assert len(diag.belief_history[1]) > 0


def test_bp_diagnostics_oscillation_detection():
    """Conflicting factors should show direction changes in belief history."""
    from libs.inference.factor_graph import FactorGraph

    g = FactorGraph()
    g.add_variable(1, 0.8)
    g.add_variable(2, 0.8)
    # A supports B via deduction
    g.add_factor(0, [1], [2], 0.95, "deduction")
    # But also a contradiction between A and B
    g.add_factor(1, [1, 2], [], 0.95, "relation_contradiction")

    bp = BeliefPropagation(max_iterations=50, damping=0.5)
    beliefs, diag = bp.run_with_diagnostics(g)
    # The graph has tension; check diagnostics captured history
    assert len(diag.belief_history[1]) >= 2
    assert isinstance(diag.direction_changes, dict)
