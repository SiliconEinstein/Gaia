"""Smoke tests for graph and parameterization fixtures."""

from tests.gaia.fixtures.graphs import (
    INVERSE_SQUARE_CONTENT,
    VACUUM_PREDICTION_CONTENT,
    make_einstein_equivalence,
    make_galileo_falling_bodies,
    make_minimal_claim_pair,
    make_newton_gravity,
)
from tests.gaia.fixtures.parameterizations import make_default_local_params

from gaia.models import KnowledgeType, LocalCanonicalGraph


class TestGalileoFallingBodies:
    def test_produces_valid_graph(self) -> None:
        g, p = make_galileo_falling_bodies()
        assert isinstance(g, LocalCanonicalGraph)
        assert p.graph_hash == g.graph_hash

    def test_node_counts(self) -> None:
        g, _ = make_galileo_falling_bodies()
        settings = [n for n in g.knowledge_nodes if n.type == KnowledgeType.SETTING]
        claims = [n for n in g.knowledge_nodes if n.type == KnowledgeType.CLAIM]
        assert len(g.knowledge_nodes) == 10
        assert len(settings) == 1  # tied_balls_setup
        assert len(claims) == 9

    def test_factor_count(self) -> None:
        g, _ = make_galileo_falling_bodies()
        assert len(g.factor_nodes) == 7

    def test_priors_cover_all_claims(self) -> None:
        g, p = make_galileo_falling_bodies()
        claim_ids = {n.id for n in g.knowledge_nodes if n.type == KnowledgeType.CLAIM}
        assert set(p.node_priors.keys()) == claim_ids

    def test_factor_params_cover_all_factors(self) -> None:
        g, p = make_galileo_falling_bodies()
        factor_ids = {f.factor_id for f in g.factor_nodes}
        assert set(p.factor_parameters.keys()) == factor_ids


class TestNewtonGravity:
    def test_produces_valid_graph(self) -> None:
        g, p = make_newton_gravity()
        assert isinstance(g, LocalCanonicalGraph)
        assert p.graph_hash == g.graph_hash

    def test_node_counts(self) -> None:
        g, _ = make_newton_gravity()
        claims = [n for n in g.knowledge_nodes if n.type == KnowledgeType.CLAIM]
        assert len(g.knowledge_nodes) == 5
        assert len(claims) == 5

    def test_factor_count(self) -> None:
        g, _ = make_newton_gravity()
        assert len(g.factor_nodes) == 3

    def test_priors_cover_all_claims(self) -> None:
        g, p = make_newton_gravity()
        claim_ids = {n.id for n in g.knowledge_nodes if n.type == KnowledgeType.CLAIM}
        assert set(p.node_priors.keys()) == claim_ids


class TestEinsteinEquivalence:
    def test_produces_valid_graph(self) -> None:
        g, p = make_einstein_equivalence()
        assert isinstance(g, LocalCanonicalGraph)
        assert p.graph_hash == g.graph_hash

    def test_node_counts(self) -> None:
        g, _ = make_einstein_equivalence()
        claims = [n for n in g.knowledge_nodes if n.type == KnowledgeType.CLAIM]
        assert len(g.knowledge_nodes) == 7
        assert len(claims) == 7

    def test_factor_count(self) -> None:
        g, _ = make_einstein_equivalence()
        assert len(g.factor_nodes) == 5

    def test_priors_cover_all_claims(self) -> None:
        g, p = make_einstein_equivalence()
        claim_ids = {n.id for n in g.knowledge_nodes if n.type == KnowledgeType.CLAIM}
        assert set(p.node_priors.keys()) == claim_ids


class TestMinimalClaimPair:
    def test_produces_valid_graph(self) -> None:
        g = make_minimal_claim_pair()
        assert isinstance(g, LocalCanonicalGraph)

    def test_node_and_factor_counts(self) -> None:
        g = make_minimal_claim_pair()
        assert len(g.knowledge_nodes) == 2
        assert len(g.factor_nodes) == 1


class TestCrossPackageMatch:
    def test_newton_mass_cancellation_different_id_from_galileo_vacuum(self) -> None:
        """Newton's mass_cancellation and Galileo's vacuum_prediction are
        semantically equivalent but worded differently → different lcn_ IDs.
        This is the equivalent_candidate scenario for canonicalization."""
        galileo, _ = make_galileo_falling_bodies()
        newton, _ = make_newton_gravity()

        galileo_vacuum = next(
            n for n in galileo.knowledge_nodes if n.content == VACUUM_PREDICTION_CONTENT
        )
        newton_mass_cancel = next(
            n for n in newton.knowledge_nodes if "All objects fall" in (n.content or "")
        )

        # Different wording → different content-addressed IDs
        assert galileo_vacuum.id != newton_mass_cancel.id
        # But both are claims about the same physical truth
        assert galileo_vacuum.id.startswith("lcn_")
        assert newton_mass_cancel.id.startswith("lcn_")

    def test_newton_inverse_square_matches_einstein_newton_gravity(self) -> None:
        """Identical inverse-square content matches across newton and einstein."""
        newton, _ = make_newton_gravity()
        einstein, _ = make_einstein_equivalence()

        newton_isq = next(n for n in newton.knowledge_nodes if n.content == INVERSE_SQUARE_CONTENT)
        einstein_ng = next(
            n for n in einstein.knowledge_nodes if n.content == INVERSE_SQUARE_CONTENT
        )

        assert newton_isq.id == einstein_ng.id
        assert newton_isq.id is not None
        assert newton_isq.id.startswith("lcn_")


class TestDefaultLocalParams:
    def test_produces_valid_parameterization(self) -> None:
        g = make_minimal_claim_pair()
        params = make_default_local_params(g)
        assert params.graph_hash == g.graph_hash

    def test_key_counts_minimal(self) -> None:
        g = make_minimal_claim_pair()
        params = make_default_local_params(g)
        assert len(params.node_priors) == 2
        assert len(params.factor_parameters) == 1

    def test_custom_values(self) -> None:
        g = make_minimal_claim_pair()
        params = make_default_local_params(g, prior=0.7, factor_prob=0.9)
        for v in params.node_priors.values():
            assert v == 0.7
        for v in params.factor_parameters.values():
            assert v == 0.9
