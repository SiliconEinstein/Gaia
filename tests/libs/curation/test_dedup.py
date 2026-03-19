"""Tests for content hash deduplication."""

from libs.curation.dedup import deduplicate_by_hash, _content_hash
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
        representative_content="The Earth orbits the Sun",  # identical
    ),
    "gcn_c": GlobalCanonicalNode(
        global_canonical_id="gcn_c",
        knowledge_type="claim",
        representative_content="Our planet revolves around the star at the center",
    ),
    "gcn_d": GlobalCanonicalNode(
        global_canonical_id="gcn_d",
        knowledge_type="claim",
        representative_content="  The Earth orbits the Sun  ",  # whitespace variant
    ),
}


def test_content_hash_normalization():
    """Hash normalizes whitespace and case."""
    assert _content_hash("The Earth orbits the Sun") == _content_hash("the earth orbits the sun")
    assert _content_hash("  hello  ") == _content_hash("hello")
    assert _content_hash("ABC") != _content_hash("DEF")


def test_dedup_finds_exact_duplicates():
    """Nodes with identical content produce a merge suggestion."""
    nodes = {"gcn_a": _NODES["gcn_a"], "gcn_b": _NODES["gcn_b"]}
    suggestions = deduplicate_by_hash(nodes)
    assert len(suggestions) == 1
    assert suggestions[0].operation == "merge"
    assert suggestions[0].confidence == 1.0
    assert set(suggestions[0].target_ids) == {"gcn_a", "gcn_b"}
    assert suggestions[0].evidence["method"] == "content_hash"


def test_dedup_normalizes_whitespace():
    """Whitespace-only differences are treated as duplicates."""
    nodes = {"gcn_a": _NODES["gcn_a"], "gcn_d": _NODES["gcn_d"]}
    suggestions = deduplicate_by_hash(nodes)
    assert len(suggestions) == 1
    assert set(suggestions[0].target_ids) == {"gcn_a", "gcn_d"}


def test_dedup_no_duplicates():
    """Unique content produces no suggestions."""
    nodes = {"gcn_a": _NODES["gcn_a"], "gcn_c": _NODES["gcn_c"]}
    suggestions = deduplicate_by_hash(nodes)
    assert len(suggestions) == 0


def test_dedup_empty_input():
    """Empty node map produces no suggestions."""
    assert deduplicate_by_hash({}) == []


def test_dedup_three_way_duplicate():
    """Three nodes with same content produce one merge suggestion with all three."""
    nodes = {"gcn_a": _NODES["gcn_a"], "gcn_b": _NODES["gcn_b"], "gcn_d": _NODES["gcn_d"]}
    suggestions = deduplicate_by_hash(nodes)
    assert len(suggestions) == 1
    assert len(suggestions[0].target_ids) == 3


def test_dedup_deterministic_order():
    """Target IDs are sorted for determinism."""
    nodes = {"gcn_b": _NODES["gcn_b"], "gcn_a": _NODES["gcn_a"]}
    suggestions = deduplicate_by_hash(nodes)
    assert suggestions[0].target_ids == ["gcn_a", "gcn_b"]


def test_dedup_mixed_duplicates_and_unique():
    """Only duplicate groups appear in suggestions, unique nodes are ignored."""
    suggestions = deduplicate_by_hash(_NODES)
    # gcn_a, gcn_b, gcn_d are duplicates (after normalization); gcn_c is unique
    assert len(suggestions) == 1
    assert "gcn_c" not in suggestions[0].target_ids
