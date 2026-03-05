# tests/libs/storage/test_vector_search.py
import pytest
import numpy as np
from libs.embedding import StubEmbeddingModel
from libs.storage.vector_search import create_vector_client
from libs.storage.config import StorageConfig
from tests.conftest import load_fixture_nodes

_embedding_model = StubEmbeddingModel()


@pytest.fixture
async def client(tmp_path):
    config = StorageConfig(lancedb_path=str(tmp_path / "lance_vec"))
    return create_vector_client(config)


def _random_embedding(dim: int = 1024) -> list[float]:
    vec = np.random.randn(dim).astype(np.float32)
    return (vec / np.linalg.norm(vec)).tolist()


async def test_insert_and_search(client):
    embs = [_random_embedding() for _ in range(5)]
    await client.insert_batch([1, 2, 3, 4, 5], embs)
    results = await client.search(embs[0], k=3)
    assert len(results) <= 3
    # First result should be exact match (closest to itself)
    assert results[0][0] == 1


async def test_search_empty(client):
    results = await client.search(_random_embedding(), k=5)
    assert results == []


async def test_search_batch(client):
    embs = [_random_embedding() for _ in range(5)]
    await client.insert_batch([1, 2, 3, 4, 5], embs)
    results = await client.search_batch([embs[0], embs[1]], k=2)
    assert len(results) == 2
    assert results[0][0][0] == 1  # first query matches node 1
    assert results[1][0][0] == 2  # second query matches node 2


# -- Fixture-data tests -------------------------------------------------------


@pytest.fixture
async def seeded_client(tmp_path):
    """Vector client pre-seeded with fixture node embeddings."""
    config = StorageConfig(lancedb_path=str(tmp_path / "lance_vec"))
    c = create_vector_client(config)
    nodes = load_fixture_nodes()
    texts = [n.content if isinstance(n.content, str) else str(n.content) for n in nodes]
    vectors = await _embedding_model.embed(texts)
    node_ids = [n.id for n in nodes]
    await c.insert_batch(node_ids, vectors)
    return c


async def test_search_finds_similar_fixture_nodes(seeded_client):
    """Search with a fixture node's embedding should return that node first."""
    nodes = load_fixture_nodes()
    query_text = nodes[0].content if isinstance(nodes[0].content, str) else str(nodes[0].content)
    query_vec = (await _embedding_model.embed([query_text]))[0]
    results = await seeded_client.search(query_vec, k=5)
    assert len(results) >= 1
    assert results[0][0] == nodes[0].id


async def test_search_batch_fixture_nodes(seeded_client):
    """Batch search with fixture embeddings returns correct matches."""
    nodes = load_fixture_nodes()
    texts = [
        nodes[0].content if isinstance(nodes[0].content, str) else str(nodes[0].content),
        nodes[1].content if isinstance(nodes[1].content, str) else str(nodes[1].content),
    ]
    vecs = await _embedding_model.embed(texts)
    results = await seeded_client.search_batch(vecs, k=3)
    assert len(results) == 2
    assert results[0][0][0] == nodes[0].id
    assert results[1][0][0] == nodes[1].id
