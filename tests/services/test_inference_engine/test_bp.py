"""Tests for the sum-product loopy BeliefPropagation algorithm."""

from __future__ import annotations

import pytest

from services.inference_engine.bp import BeliefPropagation
from services.inference_engine.factor_graph import FactorGraph


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _simple_chain() -> FactorGraph:
    """A -> B with probability 0.8"""
    fg = FactorGraph()
    fg.add_variable(1, 0.9)  # A: high prior
    fg.add_variable(2, 0.5)  # B: neutral prior
    fg.add_factor(edge_id=100, tail=[1], head=[2], probability=0.8)
    return fg


def _two_step_chain() -> FactorGraph:
    """A -> B -> C"""
    fg = FactorGraph()
    fg.add_variable(1, 0.9)
    fg.add_variable(2, 0.5)
    fg.add_variable(3, 0.5)
    fg.add_factor(edge_id=100, tail=[1], head=[2], probability=0.8)
    fg.add_factor(edge_id=101, tail=[2], head=[3], probability=0.7)
    return fg


# ---------------------------------------------------------------------------
# Basic tests
# ---------------------------------------------------------------------------


def test_empty_graph():
    fg = FactorGraph()
    bp = BeliefPropagation()
    beliefs = bp.run(fg)
    assert beliefs == {}


def test_single_node_no_factors():
    fg = FactorGraph()
    fg.add_variable(1, 0.75)
    bp = BeliefPropagation()
    beliefs = bp.run(fg)
    assert beliefs[1] == pytest.approx(0.75)


def test_simple_chain():
    fg = _simple_chain()
    bp = BeliefPropagation(damping=1.0, max_iterations=50)
    beliefs = bp.run(fg)
    assert 1 in beliefs
    assert 2 in beliefs
    # B's belief should be pulled up from 0.5 by A's high prior + edge prob 0.8
    assert beliefs[2] > 0.5


def test_chain_propagation():
    fg = _two_step_chain()
    bp = BeliefPropagation(damping=1.0, max_iterations=50)
    beliefs = bp.run(fg)
    # Source node with high prior should have highest belief
    # End-of-chain node should have lowest (evidence attenuates)
    assert beliefs[1] >= beliefs[3], f"Source should >= end: {beliefs[1]} vs {beliefs[3]}"


def test_convergence():
    """BP should converge within max_iterations."""
    fg = FactorGraph()
    for i in range(1, 6):
        fg.add_variable(i, 0.8)
    fg.add_factor(1, [1], [2], 0.9)
    fg.add_factor(2, [2], [3], 0.8)
    fg.add_factor(3, [3], [4], 0.7)
    fg.add_factor(4, [4], [5], 0.6)
    bp = BeliefPropagation(max_iterations=100, convergence_threshold=1e-6)
    beliefs = bp.run(fg)
    for b in beliefs.values():
        assert 0.0 <= b <= 1.0


def test_low_probability_edge():
    fg = FactorGraph()
    fg.add_variable(1, 0.9)
    fg.add_variable(2, 0.5)
    fg.add_factor(edge_id=100, tail=[1], head=[2], probability=0.1)
    bp = BeliefPropagation(damping=1.0, max_iterations=50)
    beliefs = bp.run(fg)
    # With low edge probability, B should not get high belief
    assert beliefs[2] < 0.5


def test_multi_tail_factor():
    """Multiple premises needed for conclusion."""
    fg = FactorGraph()
    fg.add_variable(1, 0.9)  # premise 1
    fg.add_variable(2, 0.8)  # premise 2
    fg.add_variable(3, 0.5)  # conclusion
    fg.add_factor(edge_id=100, tail=[1, 2], head=[3], probability=0.9)
    bp = BeliefPropagation(damping=1.0, max_iterations=50)
    beliefs = bp.run(fg)
    assert 0.0 <= beliefs[3] <= 1.0
    # Conclusion should be pulled up from 0.5 by strong premises
    assert beliefs[3] > 0.5


def test_damping_effect():
    """Higher damping should converge faster (deviate more from initial state)."""
    fg = _simple_chain()
    # Run only 1 iteration — damping controls how much we move
    bp_low = BeliefPropagation(damping=0.1, max_iterations=1)
    bp_high = BeliefPropagation(damping=0.9, max_iterations=1)
    beliefs_low = bp_low.run(fg)
    beliefs_high = bp_high.run(fg)
    # Node 2 starts at prior 0.5; with more damping, moves more in 1 iteration
    deviation_low = abs(beliefs_low[2] - 0.5)
    deviation_high = abs(beliefs_high[2] - 0.5)
    assert deviation_high > deviation_low, (
        f"High damping should deviate more: low={deviation_low}, high={deviation_high}"
    )


# ---------------------------------------------------------------------------
# Type-aware BP tests (retraction + contradiction)
# ---------------------------------------------------------------------------


def test_retraction_edge():
    """A retraction edge should decrease the head node's belief."""
    fg = FactorGraph()
    fg.add_variable(1, 0.9)  # Strong tail evidence
    fg.add_variable(2, 0.7)  # Moderate prior on head
    fg.add_factor(edge_id=100, tail=[1], head=[2], probability=0.8, edge_type="retraction")
    bp = BeliefPropagation(damping=1.0, max_iterations=50)
    beliefs = bp.run(fg)
    # Retraction: strong tail + high prob → head should decrease from prior
    assert beliefs[2] < 0.7, f"Retraction should reduce head belief, got {beliefs[2]}"


def test_contradiction_confirms_conclusion():
    """Contradiction head should still be confirmed (contradiction exists)."""
    fg = FactorGraph()
    fg.add_variable(1, 0.9)  # premise A
    fg.add_variable(2, 0.85)  # premise B
    fg.add_variable(3, 0.5)  # conclusion C — neutral prior
    fg.add_factor(edge_id=100, tail=[1, 2], head=[3], probability=0.8, edge_type="contradiction")
    bp = BeliefPropagation(damping=1.0, max_iterations=50)
    beliefs = bp.run(fg)
    # Head should still rise above 0.5: the contradiction IS confirmed
    # (Jaynes potential: when tails true, head=1 gets (1-p)=0.2, head=0 gets ~0,
    #  so head=1 is still favored over head=0 in the all-tails-true config)
    assert beliefs[3] > 0.5, f"Contradiction should confirm conclusion, got {beliefs[3]}"


def test_contradiction_inhibits_premises():
    """Contradiction tail nodes should decrease from priors (Jaynes backward inhibition)."""
    fg = FactorGraph()
    fg.add_variable(1, 0.9)  # premise A
    fg.add_variable(2, 0.85)  # premise B
    fg.add_variable(3, 0.5)  # conclusion C
    fg.add_factor(edge_id=100, tail=[1, 2], head=[3], probability=0.8, edge_type="contradiction")
    bp = BeliefPropagation(damping=1.0, max_iterations=50)
    beliefs = bp.run(fg)
    # Jaynes: contradiction penalizes all-tails-true → strong backward inhibition
    assert beliefs[1] < 0.9, f"Premise A should be inhibited, got {beliefs[1]}"
    assert beliefs[2] < 0.85, f"Premise B should be inhibited, got {beliefs[2]}"


def test_contradiction_stronger_than_deduction_inhibition():
    """Contradiction should inhibit premises MUCH more strongly than deduction.

    Jaynes: contradiction means P(A∧B) ≈ 0, which is a fundamentally different
    constraint from deduction's "A∧B → C with probability p".
    """
    fg_contra = FactorGraph()
    fg_contra.add_variable(1, 0.9)
    fg_contra.add_variable(2, 0.85)
    fg_contra.add_variable(3, 0.5)
    fg_contra.add_factor(
        edge_id=100, tail=[1, 2], head=[3], probability=0.8, edge_type="contradiction"
    )

    fg_deduct = FactorGraph()
    fg_deduct.add_variable(1, 0.9)
    fg_deduct.add_variable(2, 0.85)
    fg_deduct.add_variable(3, 0.5)
    fg_deduct.add_factor(edge_id=100, tail=[1, 2], head=[3], probability=0.8, edge_type="deduction")

    bp = BeliefPropagation(damping=1.0, max_iterations=50)
    beliefs_contra = bp.run(fg_contra)
    beliefs_deduct = bp.run(fg_deduct)

    # Contradiction should inhibit A more than deduction does
    contra_drop_a = 0.9 - beliefs_contra[1]
    deduct_drop_a = 0.9 - beliefs_deduct[1]
    assert contra_drop_a > deduct_drop_a * 2, (
        f"Contradiction should inhibit A much more: contra drop={contra_drop_a:.4f}, "
        f"deduct drop={deduct_drop_a:.4f}"
    )


def test_contradiction_weaker_evidence_yields_first():
    """Jaynes: the weaker premise should be inhibited more by contradiction.

    When A(0.9) and B(0.6) are contradictory, B should drop more because
    it has weaker prior support.
    """
    fg = FactorGraph()
    fg.add_variable(1, 0.9)  # A: strong
    fg.add_variable(2, 0.6)  # B: weak
    fg.add_variable(3, 0.5)  # conclusion
    fg.add_factor(edge_id=100, tail=[1, 2], head=[3], probability=0.9, edge_type="contradiction")

    bp = BeliefPropagation(damping=1.0, max_iterations=50)
    beliefs = bp.run(fg)

    drop_a = 0.9 - beliefs[1]
    drop_b = 0.6 - beliefs[2]
    assert drop_b > drop_a, (
        f"Weaker premise B should drop more: A drop={drop_a:.4f}, B drop={drop_b:.4f}"
    )


def test_contradiction_no_head_still_inhibits():
    """Contradiction with empty head should still penalize premises.

    Pure mutual exclusion constraint: A and B can't both be true.
    """
    fg = FactorGraph()
    fg.add_variable(1, 0.9)
    fg.add_variable(2, 0.8)
    fg.add_factor(edge_id=100, tail=[1, 2], head=[], probability=0.9, edge_type="contradiction")

    bp = BeliefPropagation(damping=1.0, max_iterations=50)
    beliefs = bp.run(fg)

    assert beliefs[1] < 0.9, f"A should be inhibited, got {beliefs[1]}"
    assert beliefs[2] < 0.8, f"B should be inhibited, got {beliefs[2]}"


# ---------------------------------------------------------------------------
# New tests: fixing bugs from old implementation
# ---------------------------------------------------------------------------


def test_multiple_factors_to_same_head():
    """Two factors pointing to the same head should combine, not overwrite."""
    fg = FactorGraph()
    fg.add_variable(1, 0.9)
    fg.add_variable(2, 0.8)
    fg.add_variable(3, 0.5)
    fg.add_factor(edge_id=100, tail=[1], head=[3], probability=0.8)
    fg.add_factor(edge_id=101, tail=[2], head=[3], probability=0.7)

    bp = BeliefPropagation(damping=1.0, max_iterations=50)
    beliefs = bp.run(fg)

    # With two supporting factors, belief should be higher than with just one
    fg_single = FactorGraph()
    fg_single.add_variable(1, 0.9)
    fg_single.add_variable(3, 0.5)
    fg_single.add_factor(edge_id=100, tail=[1], head=[3], probability=0.8)
    beliefs_single = bp.run(fg_single)

    assert beliefs[3] > beliefs_single[3], (
        f"Two factors should give higher belief than one: {beliefs[3]} vs {beliefs_single[3]}"
    )


def test_backward_message_through_deduction():
    """Low-belief head should weaken tail belief through backward messages."""
    fg = FactorGraph()
    fg.add_variable(1, 0.5)  # tail with uncertain prior
    fg.add_variable(2, 0.1)  # head with very low prior
    fg.add_factor(edge_id=100, tail=[1], head=[2], probability=0.9)

    bp = BeliefPropagation(damping=1.0, max_iterations=50)
    beliefs = bp.run(fg)

    # Backward message: low head belief should pull tail down from 0.5
    assert beliefs[1] < 0.5, f"Low head should weaken tail, got {beliefs[1]}"


def test_factor_ordering_invariance():
    """Result should be independent of factor list order."""
    fg1 = FactorGraph()
    fg1.add_variable(1, 0.9)
    fg1.add_variable(2, 0.8)
    fg1.add_variable(3, 0.5)
    fg1.add_factor(edge_id=100, tail=[1], head=[3], probability=0.8)
    fg1.add_factor(edge_id=101, tail=[2], head=[3], probability=0.7)

    fg2 = FactorGraph()
    fg2.add_variable(1, 0.9)
    fg2.add_variable(2, 0.8)
    fg2.add_variable(3, 0.5)
    # Reversed order
    fg2.add_factor(edge_id=101, tail=[2], head=[3], probability=0.7)
    fg2.add_factor(edge_id=100, tail=[1], head=[3], probability=0.8)

    bp = BeliefPropagation(damping=1.0, max_iterations=50)
    beliefs1 = bp.run(fg1)
    beliefs2 = bp.run(fg2)

    for vid in beliefs1:
        assert beliefs1[vid] == pytest.approx(beliefs2[vid], abs=1e-10), (
            f"Ordering should not matter for var {vid}: {beliefs1[vid]} vs {beliefs2[vid]}"
        )


def test_message_normalization_long_chain():
    """A 20-node chain should still produce meaningful beliefs (no decay to zero)."""
    fg = FactorGraph()
    n = 20
    fg.add_variable(1, 0.95)  # strong source
    for i in range(2, n + 1):
        fg.add_variable(i, 0.5)
    for i in range(1, n):
        fg.add_factor(edge_id=i, tail=[i], head=[i + 1], probability=0.9)

    bp = BeliefPropagation(damping=1.0, max_iterations=100, convergence_threshold=1e-8)
    beliefs = bp.run(fg)

    # All beliefs should be valid probabilities
    for vid, b in beliefs.items():
        assert 0.0 <= b <= 1.0, f"Node {vid} belief {b} out of range"

    # Last node should still have meaningful belief above uniform 0.5
    # (with normalized messages, signal propagates even through long chains)
    assert beliefs[n] > 0.5, f"End of 20-chain should be above 0.5, got {beliefs[n]}"


def test_retraction_with_backward_flow():
    """Retraction chain: A -[retract]-> B, B -[deduction]-> C.
    Strong A should reduce B, which in turn lowers C compared to no retraction.
    """
    fg = FactorGraph()
    fg.add_variable(1, 0.9)  # A: strong evidence
    fg.add_variable(2, 0.7)  # B: moderate prior
    fg.add_variable(3, 0.5)  # C: neutral
    fg.add_factor(edge_id=100, tail=[1], head=[2], probability=0.8, edge_type="retraction")
    fg.add_factor(edge_id=101, tail=[2], head=[3], probability=0.8, edge_type="deduction")

    bp = BeliefPropagation(damping=1.0, max_iterations=50)
    beliefs = bp.run(fg)

    # B should decrease from prior due to retraction
    assert beliefs[2] < 0.7, f"B should decrease from retraction, got {beliefs[2]}"

    # Compare: without retraction, C should be higher
    fg_no_retract = FactorGraph()
    fg_no_retract.add_variable(2, 0.7)
    fg_no_retract.add_variable(3, 0.5)
    fg_no_retract.add_factor(
        edge_id=101, tail=[2], head=[3], probability=0.8, edge_type="deduction"
    )
    beliefs_no_retract = bp.run(fg_no_retract)

    assert beliefs[3] < beliefs_no_retract[3], (
        f"C with retraction ({beliefs[3]}) should be lower than without ({beliefs_no_retract[3]})"
    )
