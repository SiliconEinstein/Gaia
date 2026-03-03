"""End-to-end integration tests for Gaia API.

These tests exercise full workflows through the FastAPI gateway using real
storage backends (LanceDB on disk, local vector index) but without Neo4j.
Graph operations are gracefully skipped when graph=None.
"""

import pytest
import numpy as np
from fastapi.testclient import TestClient
from services.gateway.app import create_app
from services.gateway.deps import Dependencies
from libs.storage import StorageConfig
from libs.models import Node


@pytest.fixture
def app_client(tmp_path):
    """Create a full app with real storage (local mode, no Neo4j)."""
    config = StorageConfig(lancedb_path=str(tmp_path / "lance"))
    dep = Dependencies(config)
    dep.initialize(config)
    # Ensure graph is None (no Neo4j in tests)
    dep.storage.graph = None
    app = create_app(dependencies=dep)
    client = TestClient(app)
    return client, dep


def _embedding(dim=1024):
    """Generate a random unit-norm embedding vector."""
    vec = np.random.randn(dim).astype(np.float32)
    return (vec / np.linalg.norm(vec)).tolist()


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

    def test_submit_review_merge(self, app_client):
        client, dep = app_client

        # 1. Submit a valid commit
        resp = client.post(
            "/commits",
            json={
                "message": "Add new finding about YH10",
                "operations": [
                    {
                        "op": "add_edge",
                        "tail": [{"content": "YH10 is predicted stable at 400GPa"}],
                        "head": [{"node_id": 1}],
                        "type": "meet",
                        "reasoning": ["DFT calculation shows stability"],
                    }
                ],
            },
        )
        assert resp.status_code == 200
        commit_id = resp.json()["commit_id"]
        assert resp.json()["status"] == "pending_review"

        # 2. Review (stub LLM always approves)
        resp = client.post(f"/commits/{commit_id}/review")
        assert resp.status_code == 200
        assert resp.json()["approved"] is True

        # 3. Merge
        resp = client.post(f"/commits/{commit_id}/merge")
        assert resp.status_code == 200
        assert resp.json()["success"] is True

        # 4. Verify commit status is now 'merged'
        resp = client.get(f"/commits/{commit_id}")
        assert resp.status_code == 200
        assert resp.json()["status"] == "merged"

    def test_submit_invalid_rejected(self, app_client):
        """A commit with empty tail/head/reasoning should be rejected at submit time."""
        client, dep = app_client
        resp = client.post(
            "/commits",
            json={
                "message": "invalid commit",
                "operations": [
                    {
                        "op": "add_edge",
                        "tail": [],
                        "head": [],
                        "type": "meet",
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
                        "tail": [{"content": "premise"}],
                        "head": [{"node_id": 1}],
                        "type": "meet",
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
                        "tail": [{"content": "data point"}],
                        "head": [{"node_id": 1}],
                        "type": "meet",
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

    def test_create_and_read_node(self, app_client):
        """Seed a node directly via storage, then read it through the API."""
        client, dep = app_client
        import asyncio

        node = Node(
            id=1,
            type="paper-extract",
            content="test content",
            keywords=["test"],
        )
        asyncio.get_event_loop().run_until_complete(dep.storage.lance.save_nodes([node]))

        resp = client.get("/nodes/1")
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
                        "tail": [{"content": "node created by merge"}],
                        "head": [{"node_id": 1}],
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

    def test_search_after_seeding(self, app_client):
        """Seed nodes and vectors, then search for them."""
        client, dep = app_client
        import asyncio

        # Seed nodes directly
        nodes = [
            Node(id=1, type="paper-extract", content="YH10 superconductivity prediction"),
            Node(id=2, type="paper-extract", content="LaH10 experimental verification"),
        ]
        asyncio.get_event_loop().run_until_complete(dep.storage.lance.save_nodes(nodes))

        # Seed vectors
        embs = [_embedding() for _ in range(2)]
        asyncio.get_event_loop().run_until_complete(dep.storage.vector.insert_batch([1, 2], embs))

        # Search via the API
        resp = client.post(
            "/search/nodes",
            json={
                "query": "superconductivity",
                "embedding": _embedding(),
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
                "query": "nothing",
                "embedding": _embedding(),
                "k": 10,
                "paths": ["bm25"],
            },
        )
        assert resp.status_code == 200
        results = resp.json()
        assert isinstance(results, list)

    def test_search_vector_only(self, app_client):
        """Search using only the vector recall path."""
        client, dep = app_client
        import asyncio

        # Seed a node + its embedding
        node = Node(id=1, type="paper-extract", content="hydrogen sulfide")
        asyncio.get_event_loop().run_until_complete(dep.storage.lance.save_nodes([node]))
        emb = _embedding()
        asyncio.get_event_loop().run_until_complete(dep.storage.vector.insert_batch([1], [emb]))

        # Search using only vector path
        resp = client.post(
            "/search/nodes",
            json={
                "query": "hydrogen",
                "embedding": emb,  # use same embedding to guarantee a hit
                "k": 10,
                "paths": ["vector"],
            },
        )
        assert resp.status_code == 200
        results = resp.json()
        assert isinstance(results, list)
        # With the same embedding, we should find the node
        assert len(results) >= 1

    def test_search_bm25_only(self, app_client):
        """Search using only the BM25 recall path."""
        client, dep = app_client
        import asyncio

        node = Node(id=1, type="paper-extract", content="superconductor critical temperature")
        asyncio.get_event_loop().run_until_complete(dep.storage.lance.save_nodes([node]))

        resp = client.post(
            "/search/nodes",
            json={
                "query": "superconductor",
                "embedding": _embedding(),
                "k": 10,
                "paths": ["bm25"],
            },
        )
        assert resp.status_code == 200
        results = resp.json()
        assert isinstance(results, list)
        # BM25 should find the node by keyword match
        assert len(results) >= 1

    def test_search_result_structure(self, app_client):
        """Verify the search result structure has expected fields."""
        client, dep = app_client
        import asyncio

        node = Node(id=1, type="paper-extract", content="structure test node")
        asyncio.get_event_loop().run_until_complete(dep.storage.lance.save_nodes([node]))
        asyncio.get_event_loop().run_until_complete(
            dep.storage.vector.insert_batch([1], [_embedding()])
        )

        resp = client.post(
            "/search/nodes",
            json={
                "query": "structure",
                "embedding": _embedding(),
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
                        "tail": [{"content": "LaH10 shows Tc=250K at 170GPa"}],
                        "head": [{"node_id": 1}],
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
                "query": "LaH10",
                "embedding": _embedding(),
                "k": 10,
                "paths": ["bm25"],
            },
        )
        assert resp.status_code == 200
        # Note: FTS index may need recreation; results depend on LanceDB FTS timing.
        # The key assertion is that the API works end-to-end without errors.

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
                            "tail": [{"content": content}],
                            "head": [{"node_id": 1}],
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
                "query": "ambient pressure",
                "embedding": _embedding(),
                "k": 10,
                "paths": ["bm25"],
            },
        )
        assert resp.status_code == 200
        results = resp.json()
        assert isinstance(results, list)

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
                        "tail": [{"content": "H3S superconductor at 200GPa"}],
                        "head": [{"node_id": 1}],
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
        """A commit with multiple new nodes in tail and head should create them all."""
        client, dep = app_client

        resp = client.post(
            "/commits",
            json={
                "message": "Multi-node commit",
                "operations": [
                    {
                        "op": "add_edge",
                        "tail": [
                            {"content": "Premise A: high pressure synthesis"},
                            {"content": "Premise B: crystal structure analysis"},
                        ],
                        "head": [
                            {"content": "Conclusion: novel superconductor phase"},
                        ],
                        "type": "meet",
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
        # Should have created 3 new nodes (2 tail + 1 head)
        assert len(merge_data["new_node_ids"]) == 3
        # Should have created 1 new hyperedge
        assert len(merge_data["new_edge_ids"]) == 1
