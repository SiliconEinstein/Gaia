"""Conflict discovery via BP signals (Level 1) and sensitivity analysis (Level 2).

Level 1: Find nodes with belief oscillation (direction changes) in BP diagnostics.
Level 2: Clamp probe nodes to true, re-run BP, find nodes with significant belief drops.
"""

from __future__ import annotations

from libs.inference.bp import BPDiagnostics, BeliefPropagation
from libs.inference.factor_graph import FactorGraph

from .models import ConflictCandidate


def detect_conflicts_level1(
    diag: BPDiagnostics,
    min_direction_changes: int = 2,
    belief_range: tuple[float, float] = (0.3, 0.7),
) -> list[ConflictCandidate]:
    """Level 1: Identify candidate conflict regions from BP oscillation signals.

    Finds nodes whose belief oscillated (changed direction) frequently during BP
    and whose final belief is in the uncertain range (0.3-0.7).

    Args:
        diag: Diagnostics from run_with_diagnostics().
        min_direction_changes: Minimum number of direction changes to flag.
        belief_range: Belief value range to consider "uncertain".

    Returns:
        ConflictCandidate pairs from oscillating nodes.
    """
    if not diag.belief_history:
        return []

    # Find oscillating nodes
    oscillating_ids: list[int] = []
    for vid, changes in diag.direction_changes.items():
        if changes < min_direction_changes:
            continue
        # Check if final belief is in uncertain range
        history = diag.belief_history.get(vid, [])
        if history:
            final = history[-1]
            if belief_range[0] <= final <= belief_range[1]:
                oscillating_ids.append(vid)

    # Pair oscillating nodes (they are likely in conflict with each other)
    candidates: list[ConflictCandidate] = []
    for i in range(len(oscillating_ids)):
        for j in range(i + 1, len(oscillating_ids)):
            a, b = oscillating_ids[i], oscillating_ids[j]
            strength = (diag.direction_changes.get(a, 0) + diag.direction_changes.get(b, 0)) / (
                2 * max(diag.iterations_run, 1)
            )
            candidates.append(
                ConflictCandidate(
                    node_a_id=str(a),
                    node_b_id=str(b),
                    signal_type="oscillation",
                    strength=min(strength, 1.0),
                    detail={
                        "a_direction_changes": diag.direction_changes.get(a, 0),
                        "b_direction_changes": diag.direction_changes.get(b, 0),
                        "a_final_belief": diag.belief_history[a][-1],
                        "b_final_belief": diag.belief_history[b][-1],
                    },
                )
            )

    return candidates


def detect_conflicts_level2(
    graph: FactorGraph,
    probe_node_ids: list[int],
    baseline_beliefs: dict[int, float],
    bp: BeliefPropagation,
    min_drop: float = 0.1,
) -> list[ConflictCandidate]:
    """Level 2: Sensitivity analysis — clamp probes to true, find antagonistic nodes.

    For each probe node, create a modified graph with the probe clamped to true
    (prior = 0.999), run BP, and find nodes whose belief dropped significantly
    compared to the baseline.

    Args:
        graph: The original factor graph.
        probe_node_ids: Node IDs to test (typically from Level 1 candidates).
        baseline_beliefs: Beliefs from a normal BP run.
        bp: BeliefPropagation instance to use.
        min_drop: Minimum belief drop to flag as antagonistic.

    Returns:
        ConflictCandidate pairs (probe, antagonist).
    """
    if not probe_node_ids:
        return []

    candidates: list[ConflictCandidate] = []

    for probe_id in probe_node_ids:
        if probe_id not in graph.variables:
            continue

        # Build clamped graph: same structure, probe prior → 0.999
        clamped = FactorGraph()
        for vid, prior in graph.variables.items():
            clamped.add_variable(vid, 0.999 if vid == probe_id else prior)
        for factor in graph.factors:
            clamped.add_factor(
                factor["edge_id"],
                factor["premises"],
                factor["conclusions"],
                factor["probability"],
                factor.get("edge_type", "deduction"),
                factor.get("gate_var"),
            )

        # Run BP on clamped graph
        clamped_beliefs = bp.run(clamped)

        # Find nodes with significant belief drop
        for vid, clamped_belief in clamped_beliefs.items():
            if vid == probe_id:
                continue
            baseline = baseline_beliefs.get(vid, 0.5)
            drop = baseline - clamped_belief
            if drop >= min_drop:
                candidates.append(
                    ConflictCandidate(
                        node_a_id=str(probe_id),
                        node_b_id=str(vid),
                        signal_type="sensitivity",
                        strength=min(drop, 1.0),
                        detail={
                            "probe_id": probe_id,
                            "baseline_belief": baseline,
                            "clamped_belief": clamped_belief,
                            "belief_drop": drop,
                        },
                    )
                )

    return candidates
