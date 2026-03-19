"""Tests for curation clustering module."""

from libs.curation.clustering import cluster_similar_nodes, _build_clusters_from_pairs
from libs.curation.models import SimilarityPair
from libs.embedding import StubEmbeddingModel
from libs.global_graph.models import GlobalCanonicalNode


# ── Unit test: cluster building from pairs ──


def test_build_clusters_single_pair():
    """Two nodes above threshold form one cluster."""
    pairs = [
        SimilarityPair(
            node_a_id="gcn_a", node_b_id="gcn_b", similarity_score=0.96, method="embedding"
        )
    ]
    clusters = _build_clusters_from_pairs(pairs)
    assert len(clusters) == 1
    assert set(clusters[0].node_ids) == {"gcn_a", "gcn_b"}


def test_build_clusters_transitive():
    """A-B and B-C should merge into one cluster {A, B, C}."""
    pairs = [
        SimilarityPair(
            node_a_id="gcn_a", node_b_id="gcn_b", similarity_score=0.95, method="embedding"
        ),
        SimilarityPair(
            node_a_id="gcn_b", node_b_id="gcn_c", similarity_score=0.93, method="embedding"
        ),
    ]
    clusters = _build_clusters_from_pairs(pairs)
    assert len(clusters) == 1
    assert set(clusters[0].node_ids) == {"gcn_a", "gcn_b", "gcn_c"}


def test_build_clusters_disjoint():
    """Two disjoint pairs form two clusters."""
    pairs = [
        SimilarityPair(
            node_a_id="gcn_a", node_b_id="gcn_b", similarity_score=0.96, method="embedding"
        ),
        SimilarityPair(
            node_a_id="gcn_c", node_b_id="gcn_d", similarity_score=0.95, method="embedding"
        ),
    ]
    clusters = _build_clusters_from_pairs(pairs)
    assert len(clusters) == 2


def test_build_clusters_empty():
    """No pairs produce no clusters."""
    clusters = _build_clusters_from_pairs([])
    assert clusters == []


# ── Integration test: full clustering with embedding ──


async def test_cluster_similar_nodes_finds_similar():
    """Nodes with identical content should cluster together."""
    nodes = [
        GlobalCanonicalNode(
            global_canonical_id="gcn_a",
            knowledge_type="claim",
            representative_content="The Earth orbits the Sun",
        ),
        GlobalCanonicalNode(
            global_canonical_id="gcn_b",
            knowledge_type="claim",
            representative_content="The Earth orbits the Sun",  # identical
        ),
        GlobalCanonicalNode(
            global_canonical_id="gcn_c",
            knowledge_type="claim",
            representative_content="Water boils at 100 degrees Celsius",  # different
        ),
    ]
    embedding_model = StubEmbeddingModel(dim=64)
    clusters = await cluster_similar_nodes(nodes, embedding_model=embedding_model, threshold=0.90)
    # The two identical texts should cluster; the different one should not
    matching = [c for c in clusters if "gcn_a" in c.node_ids]
    assert len(matching) == 1
    assert "gcn_b" in matching[0].node_ids


async def test_cluster_similar_nodes_empty():
    """Empty input returns no clusters."""
    clusters = await cluster_similar_nodes([], threshold=0.90)
    assert clusters == []


async def test_cluster_similar_nodes_single_node():
    """Single node cannot form a cluster."""
    nodes = [
        GlobalCanonicalNode(
            global_canonical_id="gcn_a",
            knowledge_type="claim",
            representative_content="Solo node",
        ),
    ]
    clusters = await cluster_similar_nodes(nodes, threshold=0.90)
    assert clusters == []
