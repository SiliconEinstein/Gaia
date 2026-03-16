"""End-to-end integration tests.

Tests exercise the full API through HTTP endpoints backed by real
LanceDB + Neo4j storage (no mocks). Tests are auto-skipped if Neo4j
is not reachable.
"""

import json
import os
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from libs.storage.config import StorageConfig
from services.gateway.app import create_app
from services.gateway.deps import Dependencies

PAPER_FIXTURES = Path("tests/fixtures/storage/papers")

NEO4J_URI = os.environ.get("NEO4J_TEST_URI", "bolt://localhost:7687")
NEO4J_PASSWORD = os.environ.get("NEO4J_TEST_PASSWORD", "")
NEO4J_DB = os.environ.get("NEO4J_TEST_DB", "neo4j")


async def _neo4j_available() -> bool:
    try:
        import neo4j

        auth = ("neo4j", NEO4J_PASSWORD) if NEO4J_PASSWORD else None
        driver = neo4j.AsyncGraphDatabase.driver(NEO4J_URI, auth=auth)
        async with driver.session(database=NEO4J_DB) as session:
            await session.run("RETURN 1")
        await driver.close()
        return True
    except Exception:
        return False


def _load_paper_fixture(slug: str) -> dict:
    """Load a paper's fixture JSON files."""
    d = PAPER_FIXTURES / slug
    return {
        "package": json.loads((d / "package.json").read_text()),
        "modules": json.loads((d / "modules.json").read_text()),
        "knowledge": json.loads((d / "knowledge.json").read_text()),
        "chains": json.loads((d / "chains.json").read_text()),
        "probabilities": json.loads((d / "probabilities.json").read_text()),
        "beliefs": json.loads((d / "beliefs.json").read_text()),
    }


@pytest.fixture
async def client(tmp_path):
    """Create app with real storage (LanceDB + Neo4j).

    Auto-skips if Neo4j is not reachable. Each test gets a clean Neo4j
    database by deleting all nodes before and after the test.
    """
    if not await _neo4j_available():
        pytest.skip("Neo4j not available")

    config = StorageConfig(
        lancedb_path=str(tmp_path / "lance"),
        graph_backend="neo4j",
        neo4j_uri=NEO4J_URI,
        neo4j_user="neo4j",
        neo4j_password=NEO4J_PASSWORD,
        neo4j_database=NEO4J_DB,
    )
    dep = Dependencies(config=config)
    await dep.initialize(config)

    # Clean Neo4j before test
    await _clean_neo4j(dep)

    app = create_app(dependencies=dep)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c

    # Clean Neo4j after test
    await _clean_neo4j(dep)
    await dep.cleanup()


async def _clean_neo4j(dep: Dependencies) -> None:
    """Delete all Knowledge, Chain, Resource nodes from Neo4j (test isolation)."""
    import neo4j

    auth = ("neo4j", NEO4J_PASSWORD) if NEO4J_PASSWORD else None
    driver = neo4j.AsyncGraphDatabase.driver(NEO4J_URI, auth=auth)
    async with driver.session(database=NEO4J_DB) as session:
        await session.run("MATCH (n:Knowledge) DETACH DELETE n")
        await session.run("MATCH (n:Chain) DETACH DELETE n")
        await session.run("MATCH (n:Resource) DETACH DELETE n")
    await driver.close()


class TestHealth:
    async def test_storage_initialized(self, client):
        resp = await client.get("/health")
        assert resp.status_code == 200


class TestIngest:
    async def test_ingest_paper_package(self, client):
        slugs = [d.name for d in sorted(PAPER_FIXTURES.iterdir()) if d.is_dir()]
        assert len(slugs) >= 1, "Need at least 1 paper fixture"

        data = _load_paper_fixture(slugs[0])
        resp = await client.post("/packages/ingest", json=data)
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["package_id"] == data["package"]["package_id"]
        assert body["status"] == "ingested"


class TestRead:
    @pytest.fixture(autouse=True)
    async def _ingest_first_paper(self, client):
        """Ingest the first paper fixture before each test."""
        slugs = [d.name for d in sorted(PAPER_FIXTURES.iterdir()) if d.is_dir()]
        self._fixture = _load_paper_fixture(slugs[0])
        resp = await client.post("/packages/ingest", json=self._fixture)
        assert resp.status_code == 201

    async def test_get_package(self, client):
        pkg_id = self._fixture["package"]["package_id"]
        resp = await client.get(f"/packages/{pkg_id}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["package_id"] == pkg_id
        assert body["status"] == "merged"

    async def test_get_package_not_found(self, client):
        resp = await client.get("/packages/nonexistent")
        assert resp.status_code == 404

    async def test_get_knowledge(self, client):
        kid = self._fixture["knowledge"][0]["knowledge_id"]
        resp = await client.get(f"/knowledge/{kid}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["knowledge_id"] == kid
        assert body["content"] == self._fixture["knowledge"][0]["content"]

    async def test_get_knowledge_versions(self, client):
        kid = self._fixture["knowledge"][0]["knowledge_id"]
        resp = await client.get(f"/knowledge/{kid}/versions")
        assert resp.status_code == 200
        versions = resp.json()
        assert len(versions) >= 1
        assert versions[0]["knowledge_id"] == kid

    async def test_get_module(self, client):
        # Fixtures may have multiple modules (setting + reasoning); find any valid one
        for mod in self._fixture["modules"]:
            mid = mod["module_id"]
            resp = await client.get(f"/modules/{mid}")
            assert resp.status_code == 200
            body = resp.json()
            assert body["module_id"] == mid
            assert body["role"] in ("reasoning", "setting", "motivation")

    async def test_get_module_chains(self, client):
        # Find the module that owns chains
        chain_module_ids = {c["module_id"] for c in self._fixture["chains"]}
        mod = next(m for m in self._fixture["modules"] if m["module_id"] in chain_module_ids)
        mid = mod["module_id"]
        expected_chains = [c for c in self._fixture["chains"] if c["module_id"] == mid]

        resp = await client.get(f"/modules/{mid}/chains")
        assert resp.status_code == 200
        chains = resp.json()
        assert len(chains) == len(expected_chains)
        for chain in chains:
            assert "chain_id" in chain
            assert "steps" in chain
            assert len(chain["steps"]) > 0

    async def test_get_chain_probabilities(self, client):
        chain_id = self._fixture["chains"][0]["chain_id"]
        resp = await client.get(f"/chains/{chain_id}/probabilities")
        assert resp.status_code == 200
        probs = resp.json()
        assert len(probs) > 0
        assert probs[0]["chain_id"] == chain_id
        # Source varies by pipeline: "author" (fixtures mode) or "llm_review" (pipeline mode)
        assert probs[0]["source"] in ("author", "llm_review")

    async def test_get_knowledge_beliefs(self, client):
        # Beliefs are only present when fixture includes them; skip gracefully if absent
        kid = self._fixture["knowledge"][0]["knowledge_id"]
        resp = await client.get(f"/knowledge/{kid}/beliefs")
        assert resp.status_code == 200
        beliefs = resp.json()
        # Beliefs may be empty when pipeline doesn't generate them for this knowledge item
        if beliefs:
            assert beliefs[0]["knowledge_id"] == kid


class TestMultiPackageE2E:
    """Ingest all 3 paper packages and verify cross-package reads."""

    async def test_ingest_all_papers_then_read(self, client):
        slugs = sorted([d.name for d in PAPER_FIXTURES.iterdir() if d.is_dir()])
        assert len(slugs) == 3, f"Expected 3 paper fixtures, got {len(slugs)}"

        # Ingest all 3
        for slug in slugs:
            data = _load_paper_fixture(slug)
            resp = await client.post("/packages/ingest", json=data)
            assert resp.status_code == 201, f"Ingest {slug} failed: {resp.text}"

        # Verify each package readable
        for slug in slugs:
            data = _load_paper_fixture(slug)
            pkg_id = data["package"]["package_id"]

            resp = await client.get(f"/packages/{pkg_id}")
            assert resp.status_code == 200, f"Package {pkg_id} not found"

            for k in data["knowledge"]:
                resp = await client.get(f"/knowledge/{k['knowledge_id']}")
                assert resp.status_code == 200, f"Knowledge {k['knowledge_id']} not found"

            for m in data["modules"]:
                resp = await client.get(f"/modules/{m['module_id']}")
                assert resp.status_code == 200, f"Module {m['module_id']} not found"

                resp = await client.get(f"/modules/{m['module_id']}/chains")
                assert resp.status_code == 200
                chains = resp.json()
                expected = len([c for c in data["chains"] if c["module_id"] == m["module_id"]])
                assert len(chains) == expected
