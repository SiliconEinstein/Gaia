"""Factor graph representation for belief propagation on hypergraphs."""

from __future__ import annotations

import logging

from libs.models import HyperEdge, Node

logger = logging.getLogger(__name__)

# Cromwell's rule (Jaynes): never assign P=0 or P=1 to any probability.
# All priors and edge probabilities are clamped to [EPS, 1-EPS].
CROMWELL_EPS = 1e-3


def _cromwell_clamp(value: float) -> float:
    """Clamp a probability to (ε, 1-ε) per Cromwell's rule."""
    return max(CROMWELL_EPS, min(1.0 - CROMWELL_EPS, value))


class FactorGraph:
    """Factor graph for belief propagation on hypergraph.

    A factor graph is a bipartite graph between variable nodes and factor nodes.
    Each Node in the hypergraph becomes a variable with its prior belief, and
    each HyperEdge becomes a factor connecting its premise and conclusion
    variables with an associated probability.

    **Cromwell's rule** is enforced at construction: priors and edge
    probabilities are clamped to ``[ε, 1-ε]`` (ε = 1e-3). This prevents
    degenerate all-zero potentials in BP and ensures no proposition is
    treated as absolutely certain or impossible. The clamped values are
    what you see in ``variables`` and ``factors``.
    """

    def __init__(self) -> None:
        self.variables: dict[int, float] = {}  # node_id -> prior
        self.factors: list[dict] = []  # [{edge_id, premises, conclusions, probability}]

    def add_variable(self, node_id: int, prior: float) -> None:
        """Add a variable node with its prior belief.

        Cromwell's rule: *prior* is clamped to ``[ε, 1-ε]``.
        """
        clamped = _cromwell_clamp(prior)
        if clamped != prior:
            logger.debug("Cromwell clamp: variable %d prior %.4g -> %.4g", node_id, prior, clamped)
        self.variables[node_id] = clamped

    def add_factor(
        self,
        edge_id: int,
        premises: list[int],
        conclusions: list[int],
        probability: float,
        edge_type: str = "deduction",
    ) -> None:
        """Add a factor (hyperedge) connecting variables.

        Cromwell's rule: *probability* is clamped to ``[ε, 1-ε]``.
        """
        clamped = _cromwell_clamp(probability)
        if clamped != probability:
            logger.debug(
                "Cromwell clamp: factor %d probability %.4g -> %.4g",
                edge_id,
                probability,
                clamped,
            )
        self.factors.append(
            {
                "edge_id": edge_id,
                "premises": premises,
                "conclusions": conclusions,
                "probability": clamped,
                "edge_type": edge_type,
            }
        )

    @classmethod
    def from_subgraph(cls, nodes: list[Node], edges: list[HyperEdge]) -> FactorGraph:
        """Build a factor graph from Node and HyperEdge lists.

        - Each Node becomes a variable with its prior.
        - Each HyperEdge becomes a factor with its probability (default 1.0
          if None).
        """
        graph = cls()
        for node in nodes:
            graph.add_variable(node.id, node.prior)
        for edge in edges:
            prob = edge.probability if edge.probability is not None else 1.0
            graph.add_factor(edge.id, edge.premises, edge.conclusions, prob, edge_type=edge.type)
        return graph

    def get_var_factors(self) -> dict[int, list[int]]:
        """Build reverse index: variable id -> list of factor indices involving it."""
        var_factors: dict[int, list[int]] = {vid: [] for vid in self.variables}
        for fi, f in enumerate(self.factors):
            for vid in f["premises"] + f["conclusions"]:
                if vid in var_factors:
                    var_factors[vid].append(fi)
        return var_factors

    def get_variable_ids(self) -> list[int]:
        """Get all variable (node) IDs."""
        return list(self.variables.keys())
