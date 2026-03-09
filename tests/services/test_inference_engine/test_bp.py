"""Tests for the sum-product loopy BeliefPropagation algorithm."""

from __future__ import annotations

import pytest

from libs.inference.bp import (
    BeliefPropagation,
    InconsistentGraphError,
    _evaluate_potential,
    _normalize,
)
from libs.inference.factor_graph import FactorGraph


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _simple_chain() -> FactorGraph:
    """A -> B with probability 0.8"""
    fg = FactorGraph()
    fg.add_variable(1, 0.9)  # A: high prior
    fg.add_variable(2, 0.5)  # B: neutral prior
    fg.add_factor(edge_id=100, premises=[1], conclusions=[2], probability=0.8)
    return fg


def _two_step_chain() -> FactorGraph:
    """A -> B -> C"""
    fg = FactorGraph()
    fg.add_variable(1, 0.9)
    fg.add_variable(2, 0.5)
    fg.add_variable(3, 0.5)
    fg.add_factor(edge_id=100, premises=[1], conclusions=[2], probability=0.8)
    fg.add_factor(edge_id=101, premises=[2], conclusions=[3], probability=0.7)
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
    # B's belief should be pulled up significantly from 0.5 by A's high prior + edge prob 0.8
    # Converged value is ~0.745
    assert beliefs[2] > 0.7, f"B should be well above 0.5, got {beliefs[2]}"
    # A's belief should decrease from 0.9 due to backward messages from B's weaker prior
    assert beliefs[1] < 0.9, f"A should be pulled down from 0.9, got {beliefs[1]}"


def test_chain_propagation():
    fg = _two_step_chain()
    bp = BeliefPropagation(damping=1.0, max_iterations=50)
    beliefs = bp.run(fg)
    # Source node with high prior should have highest belief
    assert beliefs[1] >= beliefs[3], f"Source should >= end: {beliefs[1]} vs {beliefs[3]}"
    # Evidence should attenuate: A > C > 0.5
    assert beliefs[3] > 0.55, f"End of chain should be above 0.55, got {beliefs[3]}"
    # Middle node B should also be above 0.5 (receives evidence from A)
    assert beliefs[2] > 0.55, f"Middle node should be above 0.55, got {beliefs[2]}"


def test_convergence():
    """BP should converge to stable beliefs within max_iterations."""
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
    # Re-run should produce identical results (idempotent convergence)
    beliefs2 = bp.run(fg)
    for vid in beliefs:
        assert beliefs[vid] == pytest.approx(beliefs2[vid], abs=1e-10), (
            f"Re-run should give same result for var {vid}"
        )
    # All beliefs should be meaningfully above 0.5 (chain of supportive edges)
    for vid, b in beliefs.items():
        assert b > 0.7, f"Node {vid} should be > 0.7, got {b}"


def test_low_probability_edge():
    fg = FactorGraph()
    fg.add_variable(1, 0.9)
    fg.add_variable(2, 0.5)
    fg.add_factor(edge_id=100, premises=[1], conclusions=[2], probability=0.1)
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
    fg.add_factor(edge_id=100, premises=[1, 2], conclusions=[3], probability=0.9)
    bp = BeliefPropagation(damping=1.0, max_iterations=50)
    beliefs = bp.run(fg)
    # Conclusion should be pulled up significantly from 0.5 by strong premises
    # Converged value is ~0.725
    assert beliefs[3] > 0.65, f"Conclusion should be well above 0.5, got {beliefs[3]}"
    # Premises should be pulled down slightly from their priors (backward messages)
    assert beliefs[1] < 0.9, f"Premise 1 should decrease from 0.9, got {beliefs[1]}"
    assert beliefs[2] < 0.8, f"Premise 2 should decrease from 0.8, got {beliefs[2]}"


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
    fg.add_factor(
        edge_id=100, premises=[1], conclusions=[2], probability=0.8, edge_type="retraction"
    )
    bp = BeliefPropagation(damping=1.0, max_iterations=50)
    beliefs = bp.run(fg)
    # Retraction: strong tail + high prob → head should decrease from prior
    assert beliefs[2] < 0.7, f"Retraction should reduce head belief, got {beliefs[2]}"


def test_contradiction_head_stays_at_prior():
    """Contradiction head is non-participating: belief should stay at prior."""
    fg = FactorGraph()
    fg.add_variable(1, 0.9)  # premise A
    fg.add_variable(2, 0.85)  # premise B
    fg.add_variable(3, 0.5)  # conclusion C — neutral prior
    fg.add_factor(
        edge_id=100, premises=[1, 2], conclusions=[3], probability=0.8, edge_type="contradiction"
    )
    bp = BeliefPropagation(damping=1.0, max_iterations=50)
    beliefs = bp.run(fg)
    # Head is non-participating: potential is independent of head value,
    # so f2v messages are uniform and head stays at prior.
    assert beliefs[3] == pytest.approx(0.5, abs=0.01), (
        f"Contradiction head should stay at prior 0.5, got {beliefs[3]}"
    )


def test_contradiction_inhibits_premises():
    """Contradiction tail nodes should decrease from priors (Jaynes backward inhibition)."""
    fg = FactorGraph()
    fg.add_variable(1, 0.9)  # premise A
    fg.add_variable(2, 0.85)  # premise B
    fg.add_variable(3, 0.5)  # conclusion C
    fg.add_factor(
        edge_id=100, premises=[1, 2], conclusions=[3], probability=0.8, edge_type="contradiction"
    )
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
        edge_id=100, premises=[1, 2], conclusions=[3], probability=0.8, edge_type="contradiction"
    )

    fg_deduct = FactorGraph()
    fg_deduct.add_variable(1, 0.9)
    fg_deduct.add_variable(2, 0.85)
    fg_deduct.add_variable(3, 0.5)
    fg_deduct.add_factor(
        edge_id=100, premises=[1, 2], conclusions=[3], probability=0.8, edge_type="deduction"
    )

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
    fg.add_factor(
        edge_id=100, premises=[1, 2], conclusions=[3], probability=0.9, edge_type="contradiction"
    )

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
    fg.add_factor(
        edge_id=100, premises=[1, 2], conclusions=[], probability=0.9, edge_type="contradiction"
    )

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
    fg.add_factor(edge_id=100, premises=[1], conclusions=[3], probability=0.8)
    fg.add_factor(edge_id=101, premises=[2], conclusions=[3], probability=0.7)

    bp = BeliefPropagation(damping=1.0, max_iterations=50)
    beliefs = bp.run(fg)

    # With two supporting factors, belief should be higher than with just one
    fg_single = FactorGraph()
    fg_single.add_variable(1, 0.9)
    fg_single.add_variable(3, 0.5)
    fg_single.add_factor(edge_id=100, premises=[1], conclusions=[3], probability=0.8)
    beliefs_single = bp.run(fg_single)

    assert beliefs[3] > beliefs_single[3], (
        f"Two factors should give higher belief than one: {beliefs[3]} vs {beliefs_single[3]}"
    )


def test_backward_message_through_deduction():
    """Low-belief head should weaken tail belief through backward messages."""
    fg = FactorGraph()
    fg.add_variable(1, 0.5)  # tail with uncertain prior
    fg.add_variable(2, 0.1)  # head with very low prior
    fg.add_factor(edge_id=100, premises=[1], conclusions=[2], probability=0.9)

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
    fg1.add_factor(edge_id=100, premises=[1], conclusions=[3], probability=0.8)
    fg1.add_factor(edge_id=101, premises=[2], conclusions=[3], probability=0.7)

    fg2 = FactorGraph()
    fg2.add_variable(1, 0.9)
    fg2.add_variable(2, 0.8)
    fg2.add_variable(3, 0.5)
    # Reversed order
    fg2.add_factor(edge_id=101, premises=[2], conclusions=[3], probability=0.7)
    fg2.add_factor(edge_id=100, premises=[1], conclusions=[3], probability=0.8)

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
        fg.add_factor(edge_id=i, premises=[i], conclusions=[i + 1], probability=0.9)

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
    fg.add_factor(
        edge_id=100, premises=[1], conclusions=[2], probability=0.8, edge_type="retraction"
    )
    fg.add_factor(
        edge_id=101, premises=[2], conclusions=[3], probability=0.8, edge_type="deduction"
    )

    bp = BeliefPropagation(damping=1.0, max_iterations=50)
    beliefs = bp.run(fg)

    # B should decrease from prior due to retraction
    assert beliefs[2] < 0.7, f"B should decrease from retraction, got {beliefs[2]}"

    # Compare: without retraction, C should be higher
    fg_no_retract = FactorGraph()
    fg_no_retract.add_variable(2, 0.7)
    fg_no_retract.add_variable(3, 0.5)
    fg_no_retract.add_factor(
        edge_id=101, premises=[2], conclusions=[3], probability=0.8, edge_type="deduction"
    )
    beliefs_no_retract = bp.run(fg_no_retract)

    assert beliefs[3] < beliefs_no_retract[3], (
        f"C with retraction ({beliefs[3]}) should be lower than without ({beliefs_no_retract[3]})"
    )


# ---------------------------------------------------------------------------
# Direct unit tests for _evaluate_potential
# ---------------------------------------------------------------------------


class TestEvaluatePotential:
    """Direct tests for the factor potential function — the mathematical core of BP."""

    def test_not_all_tails_true_returns_one(self):
        """When any tail is 0, the factor is unconstrained (potential = 1)."""
        result = _evaluate_potential(
            "deduction",
            premise_ids=[1, 2],
            conclusion_ids=[3],
            assignment={1: 1, 2: 0, 3: 1},
            prob=0.8,
        )
        assert result == 1.0

    def test_deduction_head_true(self):
        """Deduction: all tails true, head=1 → potential = p."""
        result = _evaluate_potential(
            "deduction",
            premise_ids=[1],
            conclusion_ids=[2],
            assignment={1: 1, 2: 1},
            prob=0.8,
        )
        assert result == pytest.approx(0.8)

    def test_deduction_head_false(self):
        """Deduction: all tails true, head=0 → potential = 1-p."""
        result = _evaluate_potential(
            "deduction",
            premise_ids=[1],
            conclusion_ids=[2],
            assignment={1: 1, 2: 0},
            prob=0.8,
        )
        assert result == pytest.approx(0.2)

    def test_retraction_head_true(self):
        """Retraction: all tails true, head=1 → potential = 1-p (inverted)."""
        result = _evaluate_potential(
            "retraction",
            premise_ids=[1],
            conclusion_ids=[2],
            assignment={1: 1, 2: 1},
            prob=0.8,
        )
        assert result == pytest.approx(0.2)

    def test_retraction_head_false(self):
        """Retraction: all tails true, head=0 → potential = p."""
        result = _evaluate_potential(
            "retraction",
            premise_ids=[1],
            conclusion_ids=[2],
            assignment={1: 1, 2: 0},
            prob=0.8,
        )
        assert result == pytest.approx(0.8)

    def test_contradiction_no_head(self):
        """Contradiction with no head: all tails true → penalty = 1-p."""
        result = _evaluate_potential(
            "contradiction",
            premise_ids=[1, 2],
            conclusion_ids=[],
            assignment={1: 1, 2: 1},
            prob=0.9,
        )
        assert result == pytest.approx(0.1)

    def test_contradiction_with_head_ignores_head_value(self):
        """Contradiction potential is independent of head value (head non-participating)."""
        pot_h1 = _evaluate_potential(
            "contradiction",
            premise_ids=[1],
            conclusion_ids=[2],
            assignment={1: 1, 2: 1},
            prob=0.8,
        )
        pot_h0 = _evaluate_potential(
            "contradiction",
            premise_ids=[1],
            conclusion_ids=[2],
            assignment={1: 1, 2: 0},
            prob=0.8,
        )
        # Both should equal penalty = 1-0.8 = 0.2, regardless of head value
        assert pot_h1 == pytest.approx(0.2)
        assert pot_h0 == pytest.approx(0.2)

    def test_induction_same_as_deduction(self):
        """Induction uses the same potential as deduction."""
        for h_val in (0, 1):
            deduct = _evaluate_potential(
                "deduction",
                [1],
                [2],
                {1: 1, 2: h_val},
                0.7,
            )
            induct = _evaluate_potential(
                "induction",
                [1],
                [2],
                {1: 1, 2: h_val},
                0.7,
            )
            assert deduct == pytest.approx(induct)

    def test_unknown_edge_type_defaults_to_deduction(self):
        """Unknown edge types (paper-extract, abstraction, etc.) use deduction potential."""
        for edge_type in ("paper-extract", "abstraction", "unknown-type"):
            result = _evaluate_potential(
                edge_type,
                [1],
                [2],
                {1: 1, 2: 1},
                0.75,
            )
            assert result == pytest.approx(0.75)

    def test_multi_head_deduction(self):
        """Multiple heads: potential is product of per-head potentials."""
        result = _evaluate_potential(
            "deduction",
            premise_ids=[1],
            conclusion_ids=[2, 3],
            assignment={1: 1, 2: 1, 3: 0},
            prob=0.8,
        )
        # head 2 = 1 → 0.8, head 3 = 0 → 0.2, product = 0.16
        assert result == pytest.approx(0.16)

    def test_multi_tail_one_false(self):
        """With multiple tails, if any is false, potential = 1 regardless of edge type."""
        for edge_type in ("deduction", "retraction", "contradiction"):
            result = _evaluate_potential(
                edge_type,
                premise_ids=[1, 2, 3],
                conclusion_ids=[4],
                assignment={1: 1, 2: 1, 3: 0, 4: 1},
                prob=0.9,
            )
            assert result == 1.0, f"{edge_type}: should be 1.0 when tail is false"

    def test_prob_zero_deduction(self):
        """probability=0: head=1 gets 0, head=0 gets 1 (raw potential, no clamping)."""
        assert _evaluate_potential("deduction", [1], [2], {1: 1, 2: 1}, 0.0) == pytest.approx(0.0)
        assert _evaluate_potential("deduction", [1], [2], {1: 1, 2: 0}, 0.0) == pytest.approx(1.0)

    def test_prob_one_deduction(self):
        """probability=1: deterministic — head=1 gets 1, head=0 gets 0."""
        assert _evaluate_potential("deduction", [1], [2], {1: 1, 2: 1}, 1.0) == pytest.approx(1.0)
        assert _evaluate_potential("deduction", [1], [2], {1: 1, 2: 0}, 1.0) == pytest.approx(0.0)

    def test_prob_zero_contradiction(self):
        """probability=0 contradiction: penalty = 1 (no inhibition)."""
        result = _evaluate_potential(
            "contradiction",
            [1, 2],
            [],
            {1: 1, 2: 1},
            0.0,
        )
        assert result == pytest.approx(1.0)

    def test_prob_one_contradiction(self):
        """probability=1 contradiction: penalty = 0 (maximum inhibition)."""
        result = _evaluate_potential(
            "contradiction",
            [1, 2],
            [],
            {1: 1, 2: 1},
            1.0,
        )
        assert result == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# Cyclic graph tests (loopy BP's core use case)
# ---------------------------------------------------------------------------


def test_cycle_two_nodes():
    """A→B→A cycle should converge to valid beliefs."""
    fg = FactorGraph()
    fg.add_variable(1, 0.9)
    fg.add_variable(2, 0.5)
    fg.add_factor(edge_id=100, premises=[1], conclusions=[2], probability=0.8)
    fg.add_factor(edge_id=101, premises=[2], conclusions=[1], probability=0.7)

    bp = BeliefPropagation(damping=0.5, max_iterations=100)
    beliefs = bp.run(fg)

    for vid, b in beliefs.items():
        assert 0.0 <= b <= 1.0, f"Node {vid} belief {b} out of range"
    # Mutual reinforcement: both should be above 0.5
    assert beliefs[1] > 0.5
    assert beliefs[2] > 0.5


def test_cycle_three_nodes():
    """A→B→C→A triangle should converge to valid beliefs."""
    fg = FactorGraph()
    fg.add_variable(1, 0.8)
    fg.add_variable(2, 0.5)
    fg.add_variable(3, 0.5)
    fg.add_factor(edge_id=100, premises=[1], conclusions=[2], probability=0.8)
    fg.add_factor(edge_id=101, premises=[2], conclusions=[3], probability=0.7)
    fg.add_factor(edge_id=102, premises=[3], conclusions=[1], probability=0.6)

    bp = BeliefPropagation(damping=0.5, max_iterations=100)
    beliefs = bp.run(fg)

    for vid, b in beliefs.items():
        assert 0.0 <= b <= 1.0, f"Node {vid} belief {b} out of range"


def test_cycle_with_contradiction():
    """Contradiction in a cycle: A→B with deduction, A+B→C with contradiction.
    The contradiction should inhibit premises even in a cyclic structure."""
    fg = FactorGraph()
    fg.add_variable(1, 0.9)
    fg.add_variable(2, 0.8)
    fg.add_variable(3, 0.5)
    fg.add_factor(edge_id=100, premises=[1], conclusions=[2], probability=0.8)
    fg.add_factor(
        edge_id=101, premises=[1, 2], conclusions=[3], probability=0.8, edge_type="contradiction"
    )

    bp = BeliefPropagation(damping=0.5, max_iterations=100)
    beliefs = bp.run(fg)

    for vid, b in beliefs.items():
        assert 0.0 <= b <= 1.0, f"Node {vid} belief {b} out of range"
    # Contradiction should inhibit at least one premise
    assert beliefs[1] < 0.9 or beliefs[2] < 0.8


# ---------------------------------------------------------------------------
# Boundary value tests
# ---------------------------------------------------------------------------


def test_prior_zero():
    """A node with prior=0.0 should stay near zero even with supporting evidence."""
    fg = FactorGraph()
    fg.add_variable(1, 0.9)  # strong tail
    fg.add_variable(2, 0.0)  # prior = 0 (known false)
    fg.add_factor(edge_id=100, premises=[1], conclusions=[2], probability=0.9)

    bp = BeliefPropagation(damping=1.0, max_iterations=50)
    beliefs = bp.run(fg)

    assert 0.0 <= beliefs[2] <= 1.0
    # Prior=0 is very strong evidence of falsehood; belief should stay low
    assert beliefs[2] < 0.3, f"Prior=0 node should resist, got {beliefs[2]}"


def test_prior_one():
    """A node with prior=1.0 should stay near one even with opposing evidence."""
    fg = FactorGraph()
    fg.add_variable(1, 0.9)
    fg.add_variable(2, 1.0)  # prior = 1 (known true)
    fg.add_factor(
        edge_id=100, premises=[1], conclusions=[2], probability=0.9, edge_type="retraction"
    )

    bp = BeliefPropagation(damping=1.0, max_iterations=50)
    beliefs = bp.run(fg)

    assert 0.0 <= beliefs[2] <= 1.0
    # Prior=1 is very strong evidence; retraction should have limited effect
    assert beliefs[2] > 0.7, f"Prior=1 node should resist retraction, got {beliefs[2]}"


def test_probability_zero_edge():
    """An edge with probability=0 should not propagate any evidence."""
    fg = FactorGraph()
    fg.add_variable(1, 0.9)
    fg.add_variable(2, 0.5)
    fg.add_factor(edge_id=100, premises=[1], conclusions=[2], probability=0.0)

    bp = BeliefPropagation(damping=1.0, max_iterations=50)
    beliefs = bp.run(fg)

    assert 0.0 <= beliefs[2] <= 1.0
    # prob=0 means "if tail true, head is definitely false"
    # This should push head BELOW 0.5
    assert beliefs[2] < 0.5, f"prob=0 edge should push head below 0.5, got {beliefs[2]}"


def test_probability_one_edge():
    """An edge with probability=1.0 is a deterministic implication."""
    fg = FactorGraph()
    fg.add_variable(1, 0.9)
    fg.add_variable(2, 0.5)
    fg.add_factor(edge_id=100, premises=[1], conclusions=[2], probability=1.0)

    bp = BeliefPropagation(damping=1.0, max_iterations=50)
    beliefs = bp.run(fg)

    assert 0.0 <= beliefs[2] <= 1.0
    # Deterministic: head belief should be very close to tail belief
    assert beliefs[2] > 0.8, f"prob=1 edge should strongly propagate, got {beliefs[2]}"


def test_all_priors_zero():
    """All nodes with prior=0 are Cromwell-clamped; should produce valid beliefs."""
    fg = FactorGraph()
    fg.add_variable(1, 0.0)
    fg.add_variable(2, 0.0)
    fg.add_factor(edge_id=100, premises=[1], conclusions=[2], probability=0.8)

    bp = BeliefPropagation(damping=1.0, max_iterations=50)
    beliefs = bp.run(fg)

    for vid, b in beliefs.items():
        assert 0.0 <= b <= 1.0, f"Node {vid} belief {b} out of range"


def test_zero_partition_raises():
    """_normalize raises InconsistentGraphError on [0, 0] input."""
    import numpy as np

    with pytest.raises(InconsistentGraphError, match="Zero partition"):
        _normalize(np.array([0.0, 0.0]))


def test_damping_zero_preserves_priors():
    """With damping=0, messages never update, so beliefs should equal priors."""
    fg = FactorGraph()
    fg.add_variable(1, 0.9)
    fg.add_variable(2, 0.3)
    fg.add_variable(3, 0.7)
    fg.add_factor(edge_id=100, premises=[1], conclusions=[2], probability=0.8)
    fg.add_factor(edge_id=101, premises=[2], conclusions=[3], probability=0.9)

    bp = BeliefPropagation(damping=0.0, max_iterations=50)
    beliefs = bp.run(fg)

    # damping=0 means msg = 0*new + 1*old = old (uniform forever)
    # Beliefs = prior * uniform^n = prior (normalized)
    assert beliefs[1] == pytest.approx(0.9, abs=1e-10)
    assert beliefs[2] == pytest.approx(0.3, abs=1e-10)
    assert beliefs[3] == pytest.approx(0.7, abs=1e-10)


@pytest.mark.parametrize(
    "edge_type, prior_head, prob, expect_above_prior",
    [
        ("deduction", 0.5, 0.8, True),  # deduction pulls head UP
        ("retraction", 0.7, 0.8, False),  # retraction pulls head DOWN
        ("induction", 0.5, 0.8, True),  # induction = deduction semantics
    ],
)
def test_edge_type_direction(edge_type, prior_head, prob, expect_above_prior):
    """Parametrized test: edge type determines direction of belief change."""
    fg = FactorGraph()
    fg.add_variable(1, 0.9)  # strong tail
    fg.add_variable(2, prior_head)
    fg.add_factor(edge_id=100, premises=[1], conclusions=[2], probability=prob, edge_type=edge_type)

    bp = BeliefPropagation(damping=1.0, max_iterations=50)
    beliefs = bp.run(fg)

    if expect_above_prior:
        assert beliefs[2] > prior_head, (
            f"{edge_type}: expected head above {prior_head}, got {beliefs[2]}"
        )
    else:
        assert beliefs[2] < prior_head, (
            f"{edge_type}: expected head below {prior_head}, got {beliefs[2]}"
        )
