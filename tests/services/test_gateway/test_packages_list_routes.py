"""Tests for v2 list API routes."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from libs.storage.models import Chain, ChainStep, Knowledge, KnowledgeRef, Module, Package
from services.gateway.app import create_app
from services.gateway.deps import deps


class MockStorage:
    async def list_packages(self, page: int = 1, page_size: int = 20):
        pkg = Package(
            package_id="pkg1",
            name="pkg1",
            version="1.0.0",
            description="test",
            modules=[],
            exports=[],
            submitter="test",
            submitted_at="2026-01-01T00:00:00Z",
            status="merged",
        )
        return [pkg], 1

    async def list_knowledge_paged(
        self, page: int = 1, page_size: int = 20, type_filter: str | None = None
    ):
        from datetime import datetime

        k = Knowledge(
            knowledge_id="k1",
            version=1,
            type="claim",
            content="test content",
            prior=0.5,
            keywords=[],
            source_package_id="pkg1",
            source_package_version="1.0.0",
            source_module_id="pkg1.mod1",
            created_at=datetime(2026, 1, 1),
        )
        if type_filter and type_filter != "claim":
            return [], 0
        return [k], 1

    async def list_modules(self, package_id: str | None = None):
        m = Module(
            module_id="pkg1.mod1",
            package_id="pkg1",
            package_version="1.0.0",
            name="mod1",
            role="reasoning",
            imports=[],
            chain_ids=[],
            export_ids=[],
        )
        return [m]

    async def list_chains_paged(
        self, page: int = 1, page_size: int = 20, module_id: str | None = None
    ):
        return [], 0

    async def get_chain(self, chain_id: str):
        if chain_id == "chain1":
            return Chain(
                chain_id="chain1",
                package_id="pkg1",
                package_version="1.0.0",
                module_id="pkg1.mod1",
                type="deduction",
                steps=[
                    ChainStep(
                        step_index=0,
                        premises=[KnowledgeRef(knowledge_id="k1", version=1)],
                        reasoning="k1 implies k2",
                        conclusion=KnowledgeRef(knowledge_id="k2", version=1),
                    )
                ],
            )
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


def test_list_knowledge(client):
    r = client.get("/knowledge")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 1
    assert body["items"][0]["knowledge_id"] == "k1"


def test_list_knowledge_type_filter(client):
    r = client.get("/knowledge?type_filter=claim")
    assert r.status_code == 200
    assert r.json()["total"] == 1


def test_list_knowledge_type_filter_no_match(client):
    r = client.get("/knowledge?type_filter=setting")
    assert r.status_code == 200
    assert "items" in r.json()


def test_list_modules(client):
    r = client.get("/modules")
    assert r.status_code == 200
    body = r.json()
    assert len(body) == 1
    assert body[0]["module_id"] == "pkg1.mod1"


def test_list_modules_filtered(client):
    r = client.get("/modules?package_id=pkg1")
    assert r.status_code == 200


def test_list_chains(client):
    r = client.get("/chains")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 0
    assert body["items"] == []


def test_get_chain_found(client):
    r = client.get("/chains/chain1")
    assert r.status_code == 200
    body = r.json()
    assert body["chain_id"] == "chain1"
    assert body["type"] == "deduction"
    assert len(body["steps"]) == 1


def test_get_chain_not_found(client):
    r = client.get("/chains/nonexistent.chain")
    assert r.status_code == 404


def test_get_graph(client):
    r = client.get("/graph")
    assert r.status_code == 200
    body = r.json()
    assert "nodes" in body
    assert "edges" in body


def test_get_graph_filtered(client):
    r = client.get("/graph?package_id=pkg1")
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body["nodes"], list)
    assert isinstance(body["edges"], list)
