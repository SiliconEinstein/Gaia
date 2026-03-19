"""Tests for shared find_similar function."""

from libs.curation.similarity import find_similar
from libs.embedding import StubEmbeddingModel
from libs.global_graph.models import GlobalCanonicalNode


def _make_nodes():
    return [
        GlobalCanonicalNode(
            global_canonical_id="gcn_a",
            knowledge_type="claim",
            representative_content="The Earth orbits the Sun",
        ),
        GlobalCanonicalNode(
            global_canonical_id="gcn_b",
            knowledge_type="claim",
            representative_content="Water boils at 100 degrees Celsius",
        ),
        GlobalCanonicalNode(
            global_canonical_id="gcn_c",
            knowledge_type="claim",
            representative_content="The Earth orbits the Sun",  # identical to gcn_a
        ),
    ]


async def test_find_similar_returns_matches_above_threshold():
    """Nodes with identical content should be returned as similar."""
    nodes = _make_nodes()
    query = nodes[0]
    candidates = nodes[1:]
    embedding_model = StubEmbeddingModel(dim=64)

    results = await find_similar(query, candidates, threshold=0.90, embedding_model=embedding_model)
    # gcn_c has identical content to query, should match
    matched_ids = {r[0] for r in results}
    assert "gcn_c" in matched_ids


async def test_find_similar_empty_candidates():
    """No candidates returns empty list."""
    node = GlobalCanonicalNode(
        global_canonical_id="gcn_a",
        knowledge_type="claim",
        representative_content="Test",
    )
    results = await find_similar(node, [], threshold=0.90)
    assert results == []


async def test_find_similar_type_mismatch_excluded():
    """Candidates with different knowledge_type are excluded."""
    query = GlobalCanonicalNode(
        global_canonical_id="gcn_q",
        knowledge_type="claim",
        representative_content="Same content",
    )
    candidate = GlobalCanonicalNode(
        global_canonical_id="gcn_c",
        knowledge_type="question",
        representative_content="Same content",
    )
    results = await find_similar(query, [candidate], threshold=0.50)
    assert results == []


async def test_find_similar_tfidf_fallback():
    """Works without embedding model using TF-IDF."""
    nodes = _make_nodes()
    results = await find_similar(nodes[0], [nodes[2]], threshold=0.50, embedding_model=None)
    # Identical text should match even with TF-IDF
    assert len(results) >= 1
