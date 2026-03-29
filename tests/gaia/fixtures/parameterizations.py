"""Parameterization fixtures for testing."""

from gaia.core.local_params import LocalParameterization
from gaia.models import KnowledgeType, LocalCanonicalGraph


def make_default_local_params(
    graph: LocalCanonicalGraph, prior: float = 0.5, factor_prob: float = 0.8
) -> LocalParameterization:
    """Create default LocalParameterization for a graph."""
    node_priors = {n.id: prior for n in graph.knowledge_nodes if n.type == KnowledgeType.CLAIM}
    factor_params = {f.factor_id: factor_prob for f in graph.factor_nodes}
    return LocalParameterization(
        graph_hash=graph.graph_hash,
        node_priors=node_priors,
        factor_parameters=factor_params,
    )
