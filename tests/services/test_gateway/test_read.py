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


async def _seed_node(dep, node_id=1, content="test node"):
    node = Node(id=node_id, type="paper-extract", content=content)
    await dep.storage.lance.save_nodes([node])


def test_get_node(client):
    c, dep = client
    import asyncio

    asyncio.get_event_loop().run_until_complete(_seed_node(dep))
    resp = c.get("/nodes/1")
    assert resp.status_code == 200
    assert resp.json()["id"] == 1


def test_get_node_not_found(client):
    c, dep = client
    resp = c.get("/nodes/999")
    assert resp.status_code == 404


def test_get_hyperedge_no_graph(client):
    c, dep = client
    # graph is None in local mode
    if dep.storage.graph is None:
        resp = c.get("/hyperedges/1")
        assert resp.status_code == 503
