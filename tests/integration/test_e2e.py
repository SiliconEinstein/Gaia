"""End-to-end integration tests for Gaia API.

These tests exercise full workflows through the FastAPI gateway using real
storage backends (LanceDB on disk, local vector index) but without Neo4j.
Graph operations are gracefully skipped when graph=None.
"""

import asyncio

import pytest
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient
from services.gateway.app import create_app
from services.gateway.deps import Dependencies
from libs.storage import StorageConfig
from libs.embedding import StubEmbeddingModel
from libs.models import Node

_stub_emb = StubEmbeddingModel()


@pytest.fixture
def app_client(tmp_path):
    """Create a full app with real storage (local mode, no Neo4j)."""
    config = StorageConfig(lancedb_path=str(tmp_path / "lance"))
    dep = Dependencies(config)
    dep.initialize(config)
    # Ensure graph is None (no Neo4j in tests)
    dep.storage.graph = None
    # Force stub embedding so tests don't depend on .env / real API
    dep.search_engine._embedding_model = _stub_emb
    app = create_app(dependencies=dep)
    client = TestClient(app)
    return client, dep


@pytest.fixture
async def async_app_client(tmp_path):
    """Create an async app client for tests that need background task completion."""
    config = StorageConfig(lancedb_path=str(tmp_path / "lance"))
    dep = Dependencies(config)
    dep.initialize(config)
    dep.storage.graph = None
    # Force stub embedding so tests don't depend on .env / real API
    dep.search_engine._embedding_model = _stub_emb
    app = create_app(dependencies=dep)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client, dep


async def _embed(text: str) -> list[float]:
    """Generate a deterministic embedding for test seeding."""
    return (await _stub_emb.embed([text]))[0]


class TestHealthCheck:
    """Verify the /health endpoint returns correct status."""

    def test_health(self, app_client):
        client, dep = app_client
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "version" in data


class TestCommitWorkflow:
    """Full submit -> review -> merge -> verify workflow."""

    async def test_submit_review_merge(self, async_app_client):
        client, dep = async_app_client

        # 1. Submit a valid commit
        resp = await client.post(
            "/commits",
            json={
                "message": "Add new finding about YH10",
                "operations": [
                    {
                        "op": "add_edge",
                        "premises": [{"content": "YH10 is predicted stable at 400GPa"}],
                        "conclusions": [{"node_id": 1}],
                        "type": "induction",
                        "reasoning": ["DFT calculation shows stability"],
                    }
                ],
            },
        )
        assert resp.status_code == 200
        commit_id = resp.json()["commit_id"]
        assert resp.json()["status"] == "pending_review"

        # 2. Review (async — submit then wait for completion)
        resp = await client.post(f"/commits/{commit_id}/review")
        assert resp.status_code == 200
        assert "job_id" in resp.json()

        # Wait for review job to complete
        for _ in range(50):
            resp = await client.get(f"/commits/{commit_id}/review")
            if resp.json()["status"] in ("completed", "failed"):
                break
            await asyncio.sleep(0.02)

        # 3. Merge
        resp = await client.post(f"/commits/{commit_id}/merge")
        assert resp.status_code == 200
        assert resp.json()["success"] is True

        # 4. Verify commit status is now 'merged'
        resp = await client.get(f"/commits/{commit_id}")
        assert resp.status_code == 200
        assert resp.json()["status"] == "merged"

    def test_submit_invalid_rejected(self, app_client):
        """A commit with empty premises/conclusions/reasoning should be rejected at submit time."""
        client, dep = app_client
        resp = client.post(
            "/commits",
            json={
                "message": "invalid commit",
                "operations": [
                    {
                        "op": "add_edge",
                        "premises": [],
                        "conclusions": [],
                        "type": "induction",
                        "reasoning": [],
                    }
                ],
            },
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "rejected"

    def test_force_merge_skips_review(self, app_client):
        """Force merge should succeed without a prior review step."""
        client, dep = app_client
        resp = client.post(
            "/commits",
            json={
                "message": "force merge test",
                "operations": [
                    {
                        "op": "add_edge",
                        "premises": [{"content": "premise"}],
                        "conclusions": [{"node_id": 1}],
                        "type": "induction",
                        "reasoning": ["reasoning"],
                    }
                ],
            },
        )
        assert resp.status_code == 200
        commit_id = resp.json()["commit_id"]

        # Skip review, force merge directly
        resp = client.post(f"/commits/{commit_id}/merge", json={"force": True})
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    def test_merge_without_review_fails(self, app_client):
        """Non-force merge without review should fail gracefully."""
        client, dep = app_client
        resp = client.post(
            "/commits",
            json={
                "message": "no review merge",
                "operations": [
                    {
                        "op": "add_edge",
                        "premises": [{"content": "data point"}],
                        "conclusions": [{"node_id": 1}],
                        "type": "induction",
                        "reasoning": ["evidence"],
                    }
                ],
            },
        )
        commit_id = resp.json()["commit_id"]

        # Attempt merge without review
        resp = client.post(f"/commits/{commit_id}/merge")
        assert resp.status_code == 200
        assert resp.json()["success"] is False

    def test_commit_not_found(self, app_client):
        """Requesting a non-existent commit should return 404."""
        client, dep = app_client
        resp = client.get("/commits/nonexistent-id")
        assert resp.status_code == 404

    def test_review_not_found(self, app_client):
        """Reviewing a non-existent commit should return 404."""
        client, dep = app_client
        resp = client.post("/commits/nonexistent-id/review")
        assert resp.status_code == 404

    def test_merge_not_found(self, app_client):
        """Merging a non-existent commit should return 404."""
        client, dep = app_client
        resp = client.post("/commits/nonexistent-id/merge")
        assert resp.status_code == 404


class TestNodeOperations:
    """Test node CRUD through the API."""

    async def test_create_and_read_node(self, async_app_client):
        """Seed a node directly via storage, then read it through the API."""
        client, dep = async_app_client

        node = Node(
            id=1,
            type="paper-extract",
            content="test content",
            keywords=["test"],
        )
        await dep.storage.lance.save_nodes([node])

        resp = await client.get("/nodes/1")
        assert resp.status_code == 200
        data = resp.json()
        assert data["content"] == "test content"
        assert data["type"] == "paper-extract"

    def test_node_not_found(self, app_client):
        """Requesting a non-existent node should return 404."""
        client, dep = app_client
        resp = client.get("/nodes/99999")
        assert resp.status_code == 404

    def test_hyperedge_without_graph_returns_503(self, app_client):
        """Hyperedge endpoint returns 503 when graph store is unavailable."""
        client, dep = app_client
        resp = client.get("/hyperedges/1")
        assert resp.status_code == 503

    def test_subgraph_without_graph_returns_503(self, app_client):
        """Subgraph endpoint returns 503 when graph store is unavailable."""
        client, dep = app_client
        resp = client.get("/nodes/1/subgraph")
        assert resp.status_code == 503

    def test_read_node_created_by_merge(self, app_client):
        """Submit, merge, then read the newly created node via /nodes/{id}."""
        client, dep = app_client

        # Submit and force-merge a commit that creates a new node
        resp = client.post(
            "/commits",
            json={
                "message": "add node via merge",
                "operations": [
                    {
                        "op": "add_edge",
                        "premises": [{"content": "node created by merge"}],
                        "conclusions": [{"node_id": 1}],
                        "type": "paper-extract",
                        "reasoning": ["test reasoning"],
                    }
                ],
            },
        )
        commit_id = resp.json()["commit_id"]
        merge_resp = client.post(f"/commits/{commit_id}/merge", json={"force": True})
        merge_data = merge_resp.json()
        assert merge_data["success"] is True

        # The merge should have created at least one new node
        new_node_ids = merge_data["new_node_ids"]
        assert len(new_node_ids) >= 1

        # Read the node through the API
        node_id = new_node_ids[0]
        resp = client.get(f"/nodes/{node_id}")
        assert resp.status_code == 200
        assert resp.json()["content"] == "node created by merge"


class TestSearchWorkflow:
    """Test search through the API."""

    async def test_search_after_seeding(self, async_app_client):
        """Seed nodes and vectors, then search for them."""
        client, dep = async_app_client

        # Seed nodes directly
        nodes = [
            Node(id=1, type="paper-extract", content="YH10 superconductivity prediction"),
            Node(id=2, type="paper-extract", content="LaH10 experimental verification"),
        ]
        await dep.storage.lance.save_nodes(nodes)

        # Seed vectors using the same stub model the search engine uses
        embs = await _stub_emb.embed([n.content for n in nodes])
        await dep.storage.vector.insert_batch([1, 2], embs)

        # Search via the API
        resp = await client.post(
            "/search/nodes",
            json={
                "text": "superconductivity",
                "k": 10,
                "paths": ["vector", "bm25"],
            },
        )
        assert resp.status_code == 200
        results = resp.json()
        assert isinstance(results, list)

    def test_search_empty_database(self, app_client):
        """Search on an empty database should return 200 with empty or minimal results."""
        client, dep = app_client
        resp = client.post(
            "/search/nodes",
            json={
                "text": "nothing",
                "k": 10,
                "paths": ["bm25"],
            },
        )
        assert resp.status_code == 200
        results = resp.json()
        assert isinstance(results, list)

    async def test_search_vector_only(self, async_app_client):
        """Search using only the vector recall path."""
        client, dep = async_app_client

        # Seed a node + its embedding using the stub model
        node = Node(id=1, type="paper-extract", content="hydrogen sulfide")
        await dep.storage.lance.save_nodes([node])
        emb = await _embed("hydrogen sulfide")
        await dep.storage.vector.insert_batch([1], [emb])

        # Search using only vector path — "hydrogen sulfide" query will produce
        # the same embedding as the seeded vector, guaranteeing a hit
        resp = await client.post(
            "/search/nodes",
            json={
                "text": "hydrogen sulfide",
                "k": 10,
                "paths": ["vector"],
            },
        )
        assert resp.status_code == 200
        results = resp.json()
        assert isinstance(results, list)
        # With the same text, we should find the node
        assert len(results) >= 1

    async def test_search_bm25_only(self, async_app_client):
        """Search using only the BM25 recall path."""
        client, dep = async_app_client

        node = Node(id=1, type="paper-extract", content="superconductor critical temperature")
        await dep.storage.lance.save_nodes([node])

        resp = await client.post(
            "/search/nodes",
            json={
                "text": "superconductor",
                "k": 10,
                "paths": ["bm25"],
            },
        )
        assert resp.status_code == 200
        results = resp.json()
        assert isinstance(results, list)
        # BM25 should find the node by keyword match
        assert len(results) >= 1

    async def test_search_result_structure(self, async_app_client):
        """Verify the search result structure has expected fields."""
        client, dep = async_app_client

        node = Node(id=1, type="paper-extract", content="structure test node")
        await dep.storage.lance.save_nodes([node])
        emb = await _embed("structure test node")
        await dep.storage.vector.insert_batch([1], [emb])

        resp = await client.post(
            "/search/nodes",
            json={
                "text": "structure",
                "k": 10,
                "paths": ["bm25"],
            },
        )
        assert resp.status_code == 200
        results = resp.json()
        if len(results) > 0:
            result = results[0]
            assert "node" in result
            assert "score" in result
            assert "sources" in result
            assert isinstance(result["sources"], list)
            assert "id" in result["node"]
            assert "content" in result["node"]


class TestFullPipeline:
    """Test the complete pipeline: submit -> merge -> search finds new data."""

    def test_submit_merge_then_search(self, app_client):
        """End-to-end: create data via commit, then find it via search."""
        client, dep = app_client

        # 1. Submit and force-merge a new edge with a new node
        resp = client.post(
            "/commits",
            json={
                "message": "Add superconductor finding",
                "operations": [
                    {
                        "op": "add_edge",
                        "premises": [{"content": "LaH10 shows Tc=250K at 170GPa"}],
                        "conclusions": [{"node_id": 1}],
                        "type": "paper-extract",
                        "reasoning": ["experimental observation"],
                    }
                ],
            },
        )
        assert resp.status_code == 200
        commit_id = resp.json()["commit_id"]
        assert resp.json()["status"] == "pending_review"

        merge_resp = client.post(f"/commits/{commit_id}/merge", json={"force": True})
        assert merge_resp.status_code == 200
        assert merge_resp.json()["success"] is True

        # 2. The new node should now be searchable via BM25
        resp = client.post(
            "/search/nodes",
            json={
                "text": "LaH10",
                "k": 10,
                "paths": ["bm25"],
            },
        )
        assert resp.status_code == 200
        results = resp.json()
        assert len(results) > 0, "Should find the newly merged LaH10 node via BM25"
        found_contents = [str(r["node"]["content"]).lower() for r in results]
        assert any("lah10" in c for c in found_contents), (
            f"LaH10 node not found in results: {found_contents}"
        )

    def test_multiple_commits_then_search(self, app_client):
        """Multiple commits followed by a search aggregating all data."""
        client, dep = app_client

        # Submit and merge two separate commits
        for content in [
            "MgB2 has Tc=39K at ambient pressure",
            "YBCO has Tc=93K at ambient pressure",
        ]:
            resp = client.post(
                "/commits",
                json={
                    "message": f"Add finding: {content[:30]}",
                    "operations": [
                        {
                            "op": "add_edge",
                            "premises": [{"content": content}],
                            "conclusions": [{"node_id": 1}],
                            "type": "paper-extract",
                            "reasoning": ["literature review"],
                        }
                    ],
                },
            )
            commit_id = resp.json()["commit_id"]
            client.post(f"/commits/{commit_id}/merge", json={"force": True})

        # Search for superconductor content
        resp = client.post(
            "/search/nodes",
            json={
                "text": "ambient pressure",
                "k": 10,
                "paths": ["bm25"],
            },
        )
        assert resp.status_code == 200
        results = resp.json()
        assert isinstance(results, list)
        assert len(results) > 0, "Should find nodes about ambient pressure"

    def test_submit_merge_verify_node_persisted(self, app_client):
        """Verify that a merged commit actually creates a readable node."""
        client, dep = app_client

        resp = client.post(
            "/commits",
            json={
                "message": "Persist test",
                "operations": [
                    {
                        "op": "add_edge",
                        "premises": [{"content": "H3S superconductor at 200GPa"}],
                        "conclusions": [{"node_id": 1}],
                        "type": "paper-extract",
                        "reasoning": ["experiment"],
                    }
                ],
            },
        )
        commit_id = resp.json()["commit_id"]
        merge_resp = client.post(f"/commits/{commit_id}/merge", json={"force": True})
        merge_data = merge_resp.json()
        assert merge_data["success"] is True

        # Read back each new node
        for nid in merge_data["new_node_ids"]:
            resp = client.get(f"/nodes/{nid}")
            assert resp.status_code == 200
            assert resp.json()["id"] == nid

    def test_commit_with_multiple_new_nodes(self, app_client):
        """A commit with multiple new nodes in premises and conclusions should create them all."""
        client, dep = app_client

        resp = client.post(
            "/commits",
            json={
                "message": "Multi-node commit",
                "operations": [
                    {
                        "op": "add_edge",
                        "premises": [
                            {"content": "Premise A: high pressure synthesis"},
                            {"content": "Premise B: crystal structure analysis"},
                        ],
                        "conclusions": [
                            {"content": "Conclusion: novel superconductor phase"},
                        ],
                        "type": "induction",
                        "reasoning": ["combined analysis of A and B"],
                    }
                ],
            },
        )
        assert resp.status_code == 200
        commit_id = resp.json()["commit_id"]

        merge_resp = client.post(f"/commits/{commit_id}/merge", json={"force": True})
        merge_data = merge_resp.json()
        assert merge_data["success"] is True
        # Should have created 3 new nodes (2 premises + 1 conclusion)
        assert len(merge_data["new_node_ids"]) == 3
        # Should have created 1 new hyperedge
        assert len(merge_data["new_edge_ids"]) == 1


class TestAsyncReviewPipeline:
    """Test the async review pipeline features added in Plan B."""

    async def test_review_result_contains_detailed_fields(self, async_app_client):
        """The review result should contain DetailedReviewResult fields."""
        client, dep = async_app_client

        # Submit commit
        resp = await client.post(
            "/commits",
            json={
                "message": "Test detailed review",
                "operations": [
                    {
                        "op": "add_edge",
                        "premises": [{"content": "New proposition for review"}],
                        "conclusions": [{"node_id": 1}],
                        "type": "induction",
                        "reasoning": ["test reasoning"],
                    }
                ],
            },
        )
        assert resp.status_code == 200
        commit_id = resp.json()["commit_id"]

        # Submit review
        resp = await client.post(f"/commits/{commit_id}/review")
        assert resp.status_code == 200
        assert "job_id" in resp.json()

        # Wait for completion
        for _ in range(50):
            resp = await client.get(f"/commits/{commit_id}/review")
            if resp.json()["status"] in ("completed", "failed"):
                break
            await asyncio.sleep(0.02)
        assert resp.json()["status"] == "completed"

        # Get result — should have DetailedReviewResult fields
        resp = await client.get(f"/commits/{commit_id}/review/result")
        assert resp.status_code == 200
        data = resp.json()
        assert "overall_verdict" in data
        assert "operations" in data
        assert data["overall_verdict"] == "pass"

    async def test_review_cancel(self, async_app_client):
        """Should be able to cancel a review job."""
        client, dep = async_app_client

        resp = await client.post(
            "/commits",
            json={
                "message": "Test cancel",
                "operations": [
                    {
                        "op": "add_edge",
                        "premises": [{"content": "Cancel me"}],
                        "conclusions": [{"node_id": 1}],
                        "type": "induction",
                        "reasoning": ["r"],
                    }
                ],
            },
        )
        assert resp.status_code == 200
        commit_id = resp.json()["commit_id"]

        # Submit review
        resp = await client.post(f"/commits/{commit_id}/review")
        assert resp.status_code == 200

        # Cancel
        resp = await client.delete(f"/commits/{commit_id}/review")
        assert resp.status_code == 200

    async def test_review_status_not_found(self, async_app_client):
        """GET /commits/{id}/review should 404 if no review submitted."""
        client, dep = async_app_client

        resp = await client.post(
            "/commits",
            json={
                "message": "No review",
                "operations": [
                    {
                        "op": "add_edge",
                        "premises": [{"content": "p"}],
                        "conclusions": [{"node_id": 1}],
                        "type": "induction",
                        "reasoning": ["r"],
                    }
                ],
            },
        )
        assert resp.status_code == 200
        commit_id = resp.json()["commit_id"]

        resp = await client.get(f"/commits/{commit_id}/review")
        assert resp.status_code == 404

    async def test_search_text_only_no_embedding(self, async_app_client):
        """Search with text only (BM25 path) should work without explicit embeddings."""
        client, dep = async_app_client

        # Submit and force-merge to seed data
        resp = await client.post(
            "/commits",
            json={
                "message": "Seed for text search",
                "operations": [
                    {
                        "op": "add_edge",
                        "premises": [{"content": "Graphene has high thermal conductivity"}],
                        "conclusions": [{"node_id": 1}],
                        "type": "paper-extract",
                        "reasoning": ["measurement result"],
                    }
                ],
            },
        )
        assert resp.status_code == 200
        commit_id = resp.json()["commit_id"]
        merge_resp = await client.post(f"/commits/{commit_id}/merge", json={"force": True})
        assert merge_resp.json()["success"] is True

        # Search using only text (BM25), no embedding provided
        resp = await client.post(
            "/search/nodes",
            json={
                "text": "graphene thermal",
                "k": 10,
                "paths": ["bm25"],
            },
        )
        assert resp.status_code == 200
        results = resp.json()
        assert isinstance(results, list)
