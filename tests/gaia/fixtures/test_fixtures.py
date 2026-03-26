"""Smoke tests for graph and parameterization fixtures."""

from tests.gaia.fixtures.graphs import (
    make_einstein_equivalence,
    make_galileo_falling_bodies,
    make_minimal_claim_pair,
    make_newton_gravity,
)
from tests.gaia.fixtures.parameterizations import make_default_local_params

from gaia.libs.models import KnowledgeType, LocalCanonicalGraph


class TestGalileoFallingBodies:
    def test_produces_valid_graph(self) -> None:
        g = make_galileo_falling_bodies()
        assert isinstance(g, LocalCanonicalGraph)

    def test_node_counts(self) -> None:
        g = make_galileo_falling_bodies()
        settings = [n for n in g.knowledge_nodes if n.type == KnowledgeType.SETTING]
        claims = [n for n in g.knowledge_nodes if n.type == KnowledgeType.CLAIM]
        assert len(g.knowledge_nodes) == 5
        assert len(settings) == 1  # tied_balls_setup is a thought experiment setting
        assert len(claims) == 4  # aristotle, composite_slower, composite_faster, vacuum

    def test_factor_count(self) -> None:
        g = make_galileo_falling_bodies()
        assert len(g.factor_nodes) == 4


class TestNewtonGravity:
    def test_produces_valid_graph(self) -> None:
        g = make_newton_gravity()
        assert isinstance(g, LocalCanonicalGraph)

    def test_node_counts(self) -> None:
        g = make_newton_gravity()
        claims = [n for n in g.knowledge_nodes if n.type == KnowledgeType.CLAIM]
        assert len(g.knowledge_nodes) == 5
        assert len(claims) == 5

    def test_factor_count(self) -> None:
        g = make_newton_gravity()
        assert len(g.factor_nodes) == 2


class TestEinsteinEquivalence:
    def test_produces_valid_graph(self) -> None:
        g = make_einstein_equivalence()
        assert isinstance(g, LocalCanonicalGraph)

    def test_node_counts(self) -> None:
        g = make_einstein_equivalence()
        claims = [n for n in g.knowledge_nodes if n.type == KnowledgeType.CLAIM]
        assert len(g.knowledge_nodes) == 5
        assert len(claims) == 5

    def test_factor_count(self) -> None:
        g = make_einstein_equivalence()
        assert len(g.factor_nodes) == 3


class TestMinimalClaimPair:
    def test_produces_valid_graph(self) -> None:
        g = make_minimal_claim_pair()
        assert isinstance(g, LocalCanonicalGraph)

    def test_node_and_factor_counts(self) -> None:
        g = make_minimal_claim_pair()
        assert len(g.knowledge_nodes) == 2
        assert len(g.factor_nodes) == 1


class TestCrossPackageMatch:
    def test_galileo_vacuum_matches_newton_galileo_vacuum(self) -> None:
        """Identical content produces the same lcn_ ID across packages."""
        galileo = make_galileo_falling_bodies()
        newton = make_newton_gravity()

        galileo_vacuum = next(
            n
            for n in galileo.knowledge_nodes
            if n.content is not None and "vacuum" in n.content.lower()
        )
        newton_galileo_vacuum = next(
            n
            for n in newton.knowledge_nodes
            if n.content is not None and "vacuum" in n.content.lower()
        )

        assert galileo_vacuum.id == newton_galileo_vacuum.id
        assert galileo_vacuum.id is not None
        assert galileo_vacuum.id.startswith("lcn_")


class TestDefaultLocalParams:
    def test_produces_valid_parameterization(self) -> None:
        g = make_galileo_falling_bodies()
        params = make_default_local_params(g)
        assert params.graph_hash == g.graph_hash

    def test_key_counts_galileo(self) -> None:
        g = make_galileo_falling_bodies()
        params = make_default_local_params(g)
        # Only CLAIM nodes get priors (4 claims in galileo)
        assert len(params.node_priors) == 4
        assert len(params.factor_parameters) == 4

    def test_key_counts_newton(self) -> None:
        g = make_newton_gravity()
        params = make_default_local_params(g)
        assert len(params.node_priors) == 5
        assert len(params.factor_parameters) == 2

    def test_custom_values(self) -> None:
        g = make_minimal_claim_pair()
        params = make_default_local_params(g, prior=0.7, factor_prob=0.9)
        for v in params.node_priors.values():
            assert v == 0.7
        for v in params.factor_parameters.values():
            assert v == 0.9
