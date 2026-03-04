import pytest
from fastapi.testclient import TestClient
from services.gateway.app import create_app
from services.gateway.deps import Dependencies
from libs.storage import StorageConfig


@pytest.fixture
def client(tmp_path):
    config = StorageConfig(lancedb_path=str(tmp_path / "lance"))
    dep = Dependencies(config)
    dep.initialize(config)
    # Disable Neo4j graph store so merge tests don't require a running Neo4j
    dep.storage.graph = None
    app = create_app(dependencies=dep)
    return TestClient(app)


def _valid_commit_payload():
    return {
        "message": "test commit",
        "operations": [
            {
                "op": "add_edge",
                "tail": [{"content": "premise A"}],
                "head": [{"node_id": 42}],
                "type": "induction",
                "reasoning": ["deduction from A"],
            }
        ],
    }


def test_submit_commit(client):
    resp = client.post("/commits", json=_valid_commit_payload())
    assert resp.status_code == 200
    data = resp.json()
    assert "commit_id" in data
    assert data["status"] == "pending_review"


def test_get_commit(client):
    # Submit first
    resp = client.post("/commits", json=_valid_commit_payload())
    commit_id = resp.json()["commit_id"]
    # Get
    resp = client.get(f"/commits/{commit_id}")
    assert resp.status_code == 200
    assert resp.json()["commit_id"] == commit_id


def test_get_commit_not_found(client):
    resp = client.get("/commits/nonexistent")
    assert resp.status_code == 404


def test_review_commit(client):
    resp = client.post("/commits", json=_valid_commit_payload())
    commit_id = resp.json()["commit_id"]
    resp = client.post(f"/commits/{commit_id}/review")
    assert resp.status_code == 200
    assert resp.json()["approved"] is True


def test_merge_commit(client):
    resp = client.post("/commits", json=_valid_commit_payload())
    commit_id = resp.json()["commit_id"]
    # Review first
    client.post(f"/commits/{commit_id}/review")
    # Merge
    resp = client.post(f"/commits/{commit_id}/merge")
    assert resp.status_code == 200
    assert resp.json()["success"] is True


def test_merge_without_review_fails(client):
    resp = client.post("/commits", json=_valid_commit_payload())
    commit_id = resp.json()["commit_id"]
    resp = client.post(f"/commits/{commit_id}/merge")
    assert resp.status_code == 200
    assert resp.json()["success"] is False


def test_merge_force(client):
    resp = client.post("/commits", json=_valid_commit_payload())
    commit_id = resp.json()["commit_id"]
    resp = client.post(f"/commits/{commit_id}/merge", json={"force": True})
    assert resp.status_code == 200
    assert resp.json()["success"] is True


def test_review_not_found(client):
    resp = client.post("/commits/nonexistent/review")
    assert resp.status_code == 404


def test_merge_not_found(client):
    resp = client.post("/commits/nonexistent/merge")
    assert resp.status_code == 404
