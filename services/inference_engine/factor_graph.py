"""Factor graph representation for belief propagation on hypergraphs."""

from __future__ import annotations

from libs.models import HyperEdge, Node


class FactorGraph:
    """Factor graph for belief propagation on hypergraph.

    A factor graph is a bipartite graph between variable nodes and factor nodes.
    Each Node in the hypergraph becomes a variable with its prior belief, and
    each HyperEdge becomes a factor connecting its tail and head variables with
    an associated probability.
    """

    def __init__(self) -> None:
        self.variables: dict[int, float] = {}  # node_id -> prior
        self.factors: list[dict] = []  # [{edge_id, tail, head, probability}]

    def add_variable(self, node_id: int, prior: float) -> None:
        """Add a variable node with its prior belief."""
        self.variables[node_id] = prior

    def add_factor(
        self,
        edge_id: int,
        tail: list[int],
        head: list[int],
        probability: float,
    ) -> None:
        """Add a factor (hyperedge) connecting variables."""
        self.factors.append(
            {
                "edge_id": edge_id,
                "tail": tail,
                "head": head,
                "probability": probability,
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
            graph.add_factor(edge.id, edge.tail, edge.head, prob)
        return graph

    def get_neighbors(self, node_id: int) -> list[int]:
        """Get factor indices that involve this node."""
        return [
            i for i, f in enumerate(self.factors) if node_id in f["tail"] or node_id in f["head"]
        ]

    def get_variable_ids(self) -> list[int]:
        """Get all variable (node) IDs."""
        return list(self.variables.keys())
