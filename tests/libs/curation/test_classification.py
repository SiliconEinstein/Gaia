"""Tests for curation classification module."""

from libs.curation.classification import classify_clusters
from libs.curation.models import ClusterGroup, SimilarityPair
from libs.global_graph.models import GlobalCanonicalNode

# ── Test fixtures ──

_NODES = {
    "gcn_a": GlobalCanonicalNode(
        global_canonical_id="gcn_a",
        knowledge_type="claim",
        representative_content="The Earth orbits the Sun",
    ),
    "gcn_b": GlobalCanonicalNode(
        global_canonical_id="gcn_b",
        knowledge_type="claim",
        representative_content="The Earth orbits the Sun",  # identical = duplicate
    ),
    "gcn_c": GlobalCanonicalNode(
        global_canonical_id="gcn_c",
        knowledge_type="claim",
        representative_content="Our planet revolves around the star at the center of the solar system",
    ),
}


def test_classify_high_similarity_as_merge():
    """Pair with very high similarity → merge suggestion."""
    clusters = [
        ClusterGroup(
            cluster_id="c1",
            node_ids=["gcn_a", "gcn_b"],
            pairs=[
                SimilarityPair(
                    node_a_id="gcn_a",
                    node_b_id="gcn_b",
                    similarity_score=0.99,
                    method="embedding",
                )
            ],
        )
    ]
    suggestions = classify_clusters(clusters, _NODES)
    assert len(suggestions) == 1
    assert suggestions[0].operation == "merge"
    assert suggestions[0].confidence > 0.95


def test_classify_medium_similarity_as_equivalence():
    """Pair with medium-high similarity → equivalence suggestion."""
    clusters = [
        ClusterGroup(
            cluster_id="c2",
            node_ids=["gcn_a", "gcn_c"],
            pairs=[
                SimilarityPair(
                    node_a_id="gcn_a",
                    node_b_id="gcn_c",
                    similarity_score=0.88,
                    method="embedding",
                )
            ],
        )
    ]
    suggestions = classify_clusters(clusters, _NODES)
    assert len(suggestions) == 1
    assert suggestions[0].operation == "create_equivalence"


def test_classify_empty_clusters():
    """No clusters produce no suggestions."""
    assert classify_clusters([], {}) == []


def test_classify_multi_node_cluster():
    """Cluster with 3 nodes produces pairwise suggestions."""
    clusters = [
        ClusterGroup(
            cluster_id="c3",
            node_ids=["gcn_a", "gcn_b", "gcn_c"],
            pairs=[
                SimilarityPair(
                    node_a_id="gcn_a",
                    node_b_id="gcn_b",
                    similarity_score=0.99,
                    method="embedding",
                ),
                SimilarityPair(
                    node_a_id="gcn_a",
                    node_b_id="gcn_c",
                    similarity_score=0.85,
                    method="embedding",
                ),
            ],
        )
    ]
    suggestions = classify_clusters(clusters, _NODES)
    # Should produce suggestions for each pair
    assert len(suggestions) == 2
    ops = {s.operation for s in suggestions}
    assert "merge" in ops
    assert "create_equivalence" in ops
