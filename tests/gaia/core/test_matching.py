"""Tests for gaia.core.matching — similarity matching engine."""

import pytest

from gaia.core.matching import compute_similarity, find_best_match
from gaia.libs.embedding import StubEmbeddingModel
from gaia.models import KnowledgeNode, KnowledgeType, Parameter, SourceRef


def _node(
    content: str,
    type_: KnowledgeType = KnowledgeType.CLAIM,
    parameters: list[Parameter] | None = None,
) -> KnowledgeNode:
    """Helper to build a KnowledgeNode with minimal boilerplate."""
    return KnowledgeNode(
        type=type_,
        content=content,
        parameters=parameters or [],
        source_refs=[SourceRef(package="test-pkg", version="0.1.0")],
    )


@pytest.fixture
def embedding_model():
    return StubEmbeddingModel(dim=64)


# ---------------------------------------------------------------------------
# find_best_match — embedding path
# ---------------------------------------------------------------------------


async def test_identical_content_matches(embedding_model):
    """Identical content → score > threshold → match returned."""
    query = _node("Water boils at 100 degrees Celsius at sea level.")
    candidate = _node("Water boils at 100 degrees Celsius at sea level.")

    result = await find_best_match(
        query, [candidate], embedding_model=embedding_model, threshold=0.90
    )

    assert result is not None
    matched, score = result
    assert matched.id == candidate.id
    assert score >= 0.99  # identical text → cosine ≈ 1.0


async def test_different_type_never_matches(embedding_model):
    """Claim vs setting with identical content → None (type filter)."""
    query = _node("Water boils at 100 degrees Celsius.", type_=KnowledgeType.CLAIM)
    candidate = _node("Water boils at 100 degrees Celsius.", type_=KnowledgeType.SETTING)

    result = await find_best_match(
        query, [candidate], embedding_model=embedding_model, threshold=0.50
    )

    assert result is None


async def test_no_candidates_returns_none(embedding_model):
    """Empty candidate list → None."""
    query = _node("Some proposition.")
    result = await find_best_match(query, [], embedding_model=embedding_model)
    assert result is None


async def test_below_threshold_returns_none(embedding_model):
    """Very different content → below threshold → None."""
    query = _node("Quantum entanglement violates Bell inequalities.")
    candidate = _node("The recipe for chocolate cake requires flour and sugar.")

    result = await find_best_match(
        query, [candidate], embedding_model=embedding_model, threshold=0.99
    )

    assert result is None


async def test_template_parameter_mismatch(embedding_model):
    """Templates with different parameter structure → None or low score."""
    query = _node(
        "X reacts with Y to produce Z",
        type_=KnowledgeType.TEMPLATE,
        parameters=[
            Parameter(name="X", type="substance"),
            Parameter(name="Y", type="substance"),
            Parameter(name="Z", type="substance"),
        ],
    )
    candidate = _node(
        "X reacts with Y to produce Z",
        type_=KnowledgeType.TEMPLATE,
        parameters=[
            Parameter(name="X", type="substance"),
            Parameter(name="Y", type="substance"),
            # missing Z — different parameter structure
        ],
    )

    result = await find_best_match(
        query, [candidate], embedding_model=embedding_model, threshold=0.90
    )

    assert result is None


# ---------------------------------------------------------------------------
# find_best_match — TF-IDF fallback (no embedding model)
# ---------------------------------------------------------------------------


async def test_tfidf_fallback():
    """No embedding model, similar text → positive match."""
    query = _node("Water boils at 100 degrees Celsius at sea level.")
    candidate = _node("Water boils at 100 degrees Celsius at sea level.")

    result = await find_best_match(query, [candidate], embedding_model=None, threshold=0.90)

    assert result is not None
    matched, score = result
    assert matched.id == candidate.id
    assert score >= 0.99


async def test_tfidf_dissimilar():
    """Very different TF-IDF texts → low score → None."""
    query = _node("Quantum entanglement violates Bell inequalities in physics experiments.")
    candidate = _node("The recipe for chocolate cake requires flour sugar and eggs for baking.")

    result = await find_best_match(query, [candidate], embedding_model=None, threshold=0.90)

    assert result is None


# ---------------------------------------------------------------------------
# find_best_match — returns best among multiple candidates
# ---------------------------------------------------------------------------


async def test_returns_best_match(embedding_model):
    """Multiple candidates → returns the one with highest similarity."""
    query = _node("Water boils at 100 degrees Celsius at sea level.")
    best_candidate = _node("Water boils at 100 degrees Celsius at sea level.")
    other_candidate = _node("Ice melts at zero degrees Celsius at standard pressure.")

    result = await find_best_match(
        query,
        [other_candidate, best_candidate],
        embedding_model=embedding_model,
        threshold=0.50,
    )

    assert result is not None
    matched, score = result
    assert matched.id == best_candidate.id


# ---------------------------------------------------------------------------
# compute_similarity — unit tests
# ---------------------------------------------------------------------------


def test_compute_similarity_identical():
    """Identical texts → score = 1.0."""
    score = compute_similarity("hello world", "hello world")
    assert score == pytest.approx(1.0)


def test_compute_similarity_disjoint():
    """Completely different texts → score = 0.0."""
    score = compute_similarity("alpha beta gamma", "delta epsilon zeta")
    assert score == pytest.approx(0.0)


def test_compute_similarity_partial():
    """Partially overlapping texts → 0 < score < 1."""
    score = compute_similarity(
        "water boils at one hundred degrees",
        "water freezes at zero degrees",
    )
    assert 0.0 < score < 1.0
