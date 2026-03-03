import pytest
from fastapi.testclient import TestClient
from services.gateway.app import create_app
from services.gateway.deps import Dependencies
from libs.storage import StorageConfig
from libs.models import Node


@pytest.fixture
def client(tmp_path):
    config = StorageConfig(lancedb_path=str(tmp_path / "lance"))
    dep = Dependencies(config)
    dep.initialize(config)
    app = create_app(dependencies=dep)
    return TestClient(app), dep


async def _seed_data(dep):
    import numpy as np

    nodes = [
        Node(id=1, type="paper-extract", content="YH10 superconductivity at high pressure"),
        Node(id=2, type="paper-extract", content="LaH10 experiment under pressure"),
    ]
    await dep.storage.lance.save_nodes(nodes)
    # Add vectors
    embs = [np.random.randn(1024).astype(np.float32).tolist() for _ in range(2)]
    await dep.storage.vector.insert_batch([1, 2], embs)


def test_search_nodes(client):
    c, dep = client
    import asyncio
    import numpy as np

    asyncio.get_event_loop().run_until_complete(_seed_data(dep))
    embedding = np.random.randn(1024).astype(np.float32).tolist()
    resp = c.post(
        "/search/nodes",
        json={
            "query": "superconductivity",
            "embedding": embedding,
            "k": 10,
            "paths": ["vector", "bm25"],
        },
    )
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_search_nodes_empty():
    """Search with no data should return empty list."""
    import tempfile
    import numpy as np

    with tempfile.TemporaryDirectory() as tmp:
        config = StorageConfig(lancedb_path=tmp + "/lance")
        dep = Dependencies(config)
        dep.initialize(config)
        app = create_app(dependencies=dep)
        c = TestClient(app)
        embedding = np.random.randn(1024).astype(np.float32).tolist()
        resp = c.post(
            "/search/nodes",
            json={
                "query": "test",
                "embedding": embedding,
                "k": 10,
                "paths": ["bm25"],
            },
        )
        assert resp.status_code == 200
