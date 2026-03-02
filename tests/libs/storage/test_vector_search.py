# tests/libs/storage/test_vector_search.py
import pytest
import numpy as np
from libs.storage.vector_search import create_vector_client
from libs.storage.config import StorageConfig


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
