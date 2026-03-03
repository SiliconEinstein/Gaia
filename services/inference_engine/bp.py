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

                # Factor message: product of tail beliefs * edge probability
                if tail_ids:
                    tail_belief = float(np.prod([beliefs.get(t, 1.0) for t in tail_ids]))
                else:
                    tail_belief = 1.0

                factor_msg = tail_belief * prob

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
