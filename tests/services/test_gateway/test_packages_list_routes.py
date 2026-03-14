"""Tests for v2 list API routes."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from libs.storage.models import Package, Module, Knowledge, Chain
from services.gateway.app import create_app
from services.gateway.deps import deps


class MockStorage:
    async def list_packages(self, page: int = 1, page_size: int = 20):
        pkg = Package(
            package_id="pkg1", name="pkg1", version="1.0.0",
            description="test", modules=[], exports=[],
            submitter="test", submitted_at="2026-01-01T00:00:00Z", status="merged",
        )
        return [pkg], 1

    async def list_knowledge_paged(self, page: int = 1, page_size: int = 20, type_filter: str | None = None):
        from libs.storage.models import Knowledge
        k = Knowledge(
            knowledge_id="k1", version=1, type="claim", content="test content",
            prior=0.5, keywords=[], source_package_id="pkg1",
            source_package_version="1.0.0", source_module_id="pkg1.mod1",
        )
        return [k], 1

    async def list_modules(self, package_id: str | None = None):
        m = Module(
            module_id="pkg1.mod1", package_id="pkg1", package_version="1.0.0",
            name="mod1", role="reasoning", imports=[], chain_ids=[], export_ids=[],
        )
        return [m]

    async def list_chains_paged(self, page: int = 1, page_size: int = 20, module_id: str | None = None):
        return [], 0

    async def get_chain(self, chain_id: str):
        return None

    async def get_graph_data(self, package_id: str | None = None):
        return {"nodes": [], "edges": []}


@pytest.fixture()
def client():
    deps.storage = MockStorage()
    app = create_app()
    c = TestClient(app)
    yield c
    deps.storage = None


def test_list_packages(client):
    r = client.get("/packages")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 1
    assert body["items"][0]["package_id"] == "pkg1"
    assert body["page"] == 1
    assert body["size"] == 20


def test_list_packages_pagination(client):
    r = client.get("/packages?page=2&page_size=5")
    assert r.status_code == 200
    body = r.json()
    assert body["page"] == 2
    assert body["size"] == 5
