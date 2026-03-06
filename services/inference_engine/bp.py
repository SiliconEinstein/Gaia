"""Loopy Belief Propagation for knowledge hypergraphs.

Implements a simplified BP algorithm where:
- Each variable (node) has a prior probability representing initial trust.
- Each factor (hyperedge) connects tail nodes to head nodes with a probability.
- Factor semantics: "if all tail nodes are true AND the edge probability holds,
  then head nodes are likely true."

The algorithm iterates, sending messages from factors to head variables,
until beliefs converge or the iteration budget is exhausted.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from services.inference_engine.factor_graph import FactorGraph

__all__ = ["BeliefPropagation"]


class BeliefPropagation:
    """Loopy Belief Propagation on a :class:`FactorGraph`.

    Parameters
    ----------
    damping:
        Controls how aggressively beliefs are updated each iteration.
        ``1.0`` means fully replace old belief; ``0.0`` means keep old belief.
    max_iterations:
        Upper bound on the number of message-passing sweeps.
    convergence_threshold:
        Stop early when the maximum absolute change in any belief
        falls below this value.
    """

    def __init__(
        self,
        damping: float = 0.5,
        max_iterations: int = 50,
        convergence_threshold: float = 1e-6,
    ) -> None:
        self._damping = damping
        self._max_iter = max_iterations
        self._threshold = convergence_threshold

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self, graph: FactorGraph) -> dict[int, float]:
        """Run loopy BP on *graph* and return posterior beliefs.

        Returns
        -------
        dict[int, float]
            Mapping from variable (node) id to its posterior belief in ``[0, 1]``.
        """
        if not graph.variables:
            return {}

        # Initialize beliefs to priors
        beliefs: dict[int, float] = dict(graph.variables)

        for _iteration in range(self._max_iter):
            old_beliefs = dict(beliefs)

            # For each factor, compute messages to head nodes
            for factor in graph.factors:
                tail_ids: list[int] = factor["tail"]
                head_ids: list[int] = factor["head"]
                prob: float = factor["probability"]
                edge_type: str = factor.get("edge_type", "deduction")

                # Factor message: product of tail beliefs * edge probability
                if tail_ids:
                    tail_belief = float(np.prod([beliefs.get(t, 1.0) for t in tail_ids]))
                else:
                    tail_belief = 1.0

                factor_msg = tail_belief * prob

                # Type-aware message transformation
                if edge_type == "retraction":
                    # Retraction: strong tail evidence *decreases* head belief
                    factor_msg = 1.0 - factor_msg
                elif edge_type == "contradiction":
                    # Contradiction: tail=[A,B] (conflicting premises), head=[C] (conclusion)
                    # Forward to head C: standard message (confirm the contradiction)
                    # factor_msg stays as tail_belief * prob — no inversion

                    # Backward to tail: inhibit premises using old_beliefs for stability
                    for t in tail_ids:
                        head_belief_avg = (
                            float(np.mean([old_beliefs.get(h, 1.0) for h in head_ids]))
                            if head_ids
                            else 0.0
                        )
                        contra_msg = 1.0 - head_belief_avg * prob
                        prior_t = graph.variables.get(t, 1.0)
                        new_t = prior_t * contra_msg
                        new_t = min(max(new_t, 0.0), 1.0)
                        beliefs[t] = self._damping * new_t + (1 - self._damping) * old_beliefs.get(
                            t, prior_t
                        )

                # Update head nodes: combine prior with incoming factor message
                for h in head_ids:
                    prior = graph.variables.get(h, 1.0)
                    # Weighted combination of prior and factor evidence
                    new_belief = prior * factor_msg
                    # Clamp to [0, 1]
                    new_belief = min(max(new_belief, 0.0), 1.0)
                    # Damping: blend new value with old belief
                    beliefs[h] = self._damping * new_belief + (1 - self._damping) * old_beliefs.get(
                        h, prior
                    )

            # Check convergence
            max_change = max(abs(beliefs[nid] - old_beliefs[nid]) for nid in beliefs)
            if max_change < self._threshold:
                break

        return beliefs
