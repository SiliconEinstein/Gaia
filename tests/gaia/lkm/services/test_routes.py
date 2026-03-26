"""Tests for FastAPI service routes — ingest, knowledge, inference."""

import pytest
from httpx import ASGITransport, AsyncClient

from gaia.libs.embedding import StubEmbeddingModel
from gaia.libs.storage.config import StorageConfig
from gaia.libs.storage.manager import StorageManager
from gaia.lkm.services.app import create_app
from gaia.lkm.services import deps as deps_module
from gaia.lkm.services.deps import Dependencies
from tests.gaia.fixtures.graphs import make_galileo_falling_bodies


@pytest.fixture
async def client(tmp_path):
    config = StorageConfig(lancedb_path=str(tmp_path / "test.lance"))
    storage = StorageManager(config)
    await storage.initialize()
    embedding = StubEmbeddingModel(dim=64)
    dependencies = Dependencies(storage=storage, embedding=embedding)
    # Set deps globally so routes can access them (ASGITransport doesn't
    # trigger lifespan by default).
    deps_module.deps = dependencies
    app = create_app(dependencies=dependencies)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    deps_module.deps = None


async def test_health(client: AsyncClient):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


async def test_ingest_package(client: AsyncClient):
    graph, params = make_galileo_falling_bodies()
    payload = {
        "package_id": "galileo_falling_bodies",
        "version": "1.0",
        "local_graph": graph.model_dump(mode="json"),
        "local_params": params.model_dump(mode="json"),
    }
    resp = await client.post("/api/packages/ingest", json=payload)
    assert resp.status_code == 200
    body = resp.json()
    assert body["package_id"] == "galileo_falling_bodies"
    assert body["version"] == "1.0"
    assert body["new_global_nodes"] > 0
    assert body["bindings"] > 0
    assert body["global_factors"] > 0


async def test_get_knowledge_not_found(client: AsyncClient):
    resp = await client.get("/api/knowledge/nonexistent")
    assert resp.status_code == 404


async def test_get_knowledge_after_ingest(client: AsyncClient):
    graph, params = make_galileo_falling_bodies()
    payload = {
        "package_id": "galileo_falling_bodies",
        "version": "1.0",
        "local_graph": graph.model_dump(mode="json"),
        "local_params": params.model_dump(mode="json"),
    }
    await client.post("/api/packages/ingest", json=payload)

    # The first knowledge node should be retrievable by its local canonical ID
    first_node_id = graph.knowledge_nodes[0].id
    resp = await client.get(f"/api/knowledge/{first_node_id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == first_node_id


async def test_trigger_bp_after_ingest(client: AsyncClient):
    graph, params = make_galileo_falling_bodies()
    payload = {
        "package_id": "galileo_falling_bodies",
        "version": "1.0",
        "local_graph": graph.model_dump(mode="json"),
        "local_params": params.model_dump(mode="json"),
    }
    await client.post("/api/packages/ingest", json=payload)

    resp = await client.post("/api/inference/run", json={"resolution_policy": "latest"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["converged"] is not None
    assert "beliefs" in body
    assert "bp_run_id" in body
