"""V2 storage end-to-end integration tests.

Tests exercise the full v2 API through HTTP endpoints backed by real
LanceDB + Neo4j storage (no mocks). Tests are auto-skipped if Neo4j
is not reachable.
"""

import json
import os
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from libs.storage import StorageConfig as V1StorageConfig
from libs.storage_v2.config import StorageConfig as V2StorageConfig
from services.gateway.app import create_app
from services.gateway.deps import Dependencies

PAPER_FIXTURES = Path("tests/fixtures/storage_v2/papers")

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
    """Load a paper's v2 fixture JSON files."""
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
async def v2_client(tmp_path):
    """Create app with real v2 storage (LanceDB + Neo4j).

    Auto-skips if Neo4j is not reachable. Each test gets a clean Neo4j
    database by deleting all v2 nodes before and after the test.
    """
    if not await _neo4j_available():
        pytest.skip("Neo4j not available")

    v1_config = V1StorageConfig(lancedb_path=str(tmp_path / "lance_v1"))
    v2_config = V2StorageConfig(
        lancedb_path=str(tmp_path / "lance_v2"),
        graph_backend="neo4j",
        neo4j_uri=NEO4J_URI,
        neo4j_user="neo4j",
        neo4j_password=NEO4J_PASSWORD,
        neo4j_database=NEO4J_DB,
    )
    dep = Dependencies(config=v1_config, v2_config=v2_config)
    dep.initialize(v1_config)
    # v1 graph not needed for v2 tests
    dep.storage.graph = None
    # Initialize v2 storage (async)
    await dep.initialize_v2()

    # Clean Neo4j before test
    await _clean_neo4j_v2(dep)

    app = create_app(dependencies=dep)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    # Clean Neo4j after test
    await _clean_neo4j_v2(dep)
    await dep.cleanup()


async def _clean_neo4j_v2(dep: Dependencies) -> None:
    """Delete all Knowledge, Chain, Resource nodes from Neo4j (test isolation)."""
    import neo4j

    auth = ("neo4j", NEO4J_PASSWORD) if NEO4J_PASSWORD else None
    driver = neo4j.AsyncGraphDatabase.driver(NEO4J_URI, auth=auth)
    async with driver.session(database=NEO4J_DB) as session:
        await session.run("MATCH (n:Knowledge) DETACH DELETE n")
        await session.run("MATCH (n:Chain) DETACH DELETE n")
        await session.run("MATCH (n:Resource) DETACH DELETE n")
    await driver.close()


class TestV2Health:
    async def test_v2_storage_initialized(self, v2_client):
        resp = await v2_client.get("/health")
        assert resp.status_code == 200


class TestV2Ingest:
    async def test_ingest_paper_package(self, v2_client):
        slugs = [d.name for d in sorted(PAPER_FIXTURES.iterdir()) if d.is_dir()]
        assert len(slugs) >= 1, "Need at least 1 paper fixture"

        data = _load_paper_fixture(slugs[0])
        resp = await v2_client.post("/v2/packages/ingest", json=data)
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["package_id"] == data["package"]["package_id"]
        assert body["status"] == "ingested"


class TestV2Read:
    @pytest.fixture(autouse=True)
    async def _ingest_first_paper(self, v2_client):
        """Ingest the first paper fixture before each test."""
        slugs = [d.name for d in sorted(PAPER_FIXTURES.iterdir()) if d.is_dir()]
        self._fixture = _load_paper_fixture(slugs[0])
        resp = await v2_client.post("/v2/packages/ingest", json=self._fixture)
        assert resp.status_code == 201

    async def test_get_package(self, v2_client):
        pkg_id = self._fixture["package"]["package_id"]
        resp = await v2_client.get(f"/v2/packages/{pkg_id}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["package_id"] == pkg_id
        assert body["status"] == "merged"

    async def test_get_package_not_found(self, v2_client):
        resp = await v2_client.get("/v2/packages/nonexistent")
        assert resp.status_code == 404

    async def test_get_knowledge(self, v2_client):
        kid = self._fixture["knowledge"][0]["knowledge_id"]
        resp = await v2_client.get(f"/v2/knowledge/{kid}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["knowledge_id"] == kid
        assert body["content"] == self._fixture["knowledge"][0]["content"]

    async def test_get_knowledge_versions(self, v2_client):
        kid = self._fixture["knowledge"][0]["knowledge_id"]
        resp = await v2_client.get(f"/v2/knowledge/{kid}/versions")
        assert resp.status_code == 200
        versions = resp.json()
        assert len(versions) >= 1
        assert versions[0]["knowledge_id"] == kid

    async def test_get_module(self, v2_client):
        mid = self._fixture["modules"][0]["module_id"]
        resp = await v2_client.get(f"/v2/modules/{mid}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["module_id"] == mid
        assert body["role"] == "reasoning"

    async def test_get_module_chains(self, v2_client):
        mid = self._fixture["modules"][0]["module_id"]
        resp = await v2_client.get(f"/v2/modules/{mid}/chains")
        assert resp.status_code == 200
        chains = resp.json()
        assert len(chains) == len(self._fixture["chains"])
        for chain in chains:
            assert "chain_id" in chain
            assert "steps" in chain
            assert len(chain["steps"]) > 0

    async def test_get_chain_probabilities(self, v2_client):
        chain_id = self._fixture["chains"][0]["chain_id"]
        resp = await v2_client.get(f"/v2/chains/{chain_id}/probabilities")
        assert resp.status_code == 200
        probs = resp.json()
        assert len(probs) > 0
        assert probs[0]["chain_id"] == chain_id
        assert probs[0]["source"] == "author"

    async def test_get_knowledge_beliefs(self, v2_client):
        kid = self._fixture["knowledge"][0]["knowledge_id"]
        resp = await v2_client.get(f"/v2/knowledge/{kid}/beliefs")
        assert resp.status_code == 200
        beliefs = resp.json()
        assert len(beliefs) >= 1
        assert beliefs[0]["knowledge_id"] == kid


class TestV2MultiPackageE2E:
    """Ingest all 3 paper packages and verify cross-package reads."""

    async def test_ingest_all_papers_then_read(self, v2_client):
        slugs = sorted([d.name for d in PAPER_FIXTURES.iterdir() if d.is_dir()])
        assert len(slugs) == 3, f"Expected 3 paper fixtures, got {len(slugs)}"

        # Ingest all 3
        for slug in slugs:
            data = _load_paper_fixture(slug)
            resp = await v2_client.post("/v2/packages/ingest", json=data)
            assert resp.status_code == 201, f"Ingest {slug} failed: {resp.text}"

        # Verify each package readable
        for slug in slugs:
            data = _load_paper_fixture(slug)
            pkg_id = data["package"]["package_id"]

            resp = await v2_client.get(f"/v2/packages/{pkg_id}")
            assert resp.status_code == 200, f"Package {pkg_id} not found"

            for k in data["knowledge"]:
                resp = await v2_client.get(f"/v2/knowledge/{k['knowledge_id']}")
                assert resp.status_code == 200, f"Knowledge {k['knowledge_id']} not found"

            for m in data["modules"]:
                resp = await v2_client.get(f"/v2/modules/{m['module_id']}")
                assert resp.status_code == 200, f"Module {m['module_id']} not found"

                resp = await v2_client.get(f"/v2/modules/{m['module_id']}/chains")
                assert resp.status_code == 200
                chains = resp.json()
                expected = len([c for c in data["chains"] if c["module_id"] == m["module_id"]])
                assert len(chains) == expected


class TestV2ServerCommitReviewMerge:
    """Server-side v2 commit/review/merge pipeline — NOT YET IMPLEMENTED.

    These tests document the expected API surface for server-side v2 operations.
    See docs/plans/2026-03-12-server-v2-commit-review-merge.md for design.
    """

    @pytest.mark.xfail(reason="Server-side v2 commit not implemented", strict=True)
    async def test_submit_v2_commit(self, v2_client):
        resp = await v2_client.post(
            "/v2/commits",
            json={
                "operations": [
                    {
                        "type": "add_knowledge",
                        "knowledge": {
                            "knowledge_id": "test/k1",
                            "version": 1,
                            "type": "claim",
                            "content": "Test claim",
                            "prior": 0.5,
                            "source_package_id": "test",
                            "source_module_id": "test.mod",
                            "created_at": "2026-03-12T00:00:00Z",
                        },
                    }
                ]
            },
        )
        assert resp.status_code == 201

    @pytest.mark.xfail(reason="Server-side v2 review not implemented", strict=True)
    async def test_submit_v2_review(self, v2_client):
        resp = await v2_client.post("/v2/commits/test-commit/review")
        assert resp.status_code == 202

    @pytest.mark.xfail(reason="Server-side v2 merge not implemented", strict=True)
    async def test_merge_v2_commit(self, v2_client):
        resp = await v2_client.post("/v2/commits/test-commit/merge")
        assert resp.status_code == 200

    @pytest.mark.xfail(reason="Server-side v2 BM25 search not implemented", strict=True)
    async def test_v2_bm25_search(self, v2_client):
        resp = await v2_client.post(
            "/v2/search/knowledge",
            json={"text": "superconductivity", "top_k": 10},
        )
        assert resp.status_code == 200

    @pytest.mark.xfail(reason="Server-side v2 vector search not implemented", strict=True)
    async def test_v2_vector_search(self, v2_client):
        resp = await v2_client.post(
            "/v2/search/vector",
            json={"embedding": [0.1] * 512, "top_k": 10},
        )
        assert resp.status_code == 200

    @pytest.mark.xfail(reason="Server-side v2 topology search not implemented", strict=True)
    async def test_v2_topology_search(self, v2_client):
        resp = await v2_client.post(
            "/v2/search/topology",
            json={"seed_ids": ["test/k1"], "hops": 2},
        )
        assert resp.status_code == 200
