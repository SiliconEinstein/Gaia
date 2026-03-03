import pytest
from fastapi.testclient import TestClient
from services.gateway.app import create_app
from services.gateway.deps import Dependencies


@pytest.fixture
def client(tmp_path):
    from libs.storage import StorageConfig

    config = StorageConfig(lancedb_path=str(tmp_path / "lance"))
    deps = Dependencies(config)
    deps.initialize(config)
    app = create_app(dependencies=deps)
    return TestClient(app)


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "version" in data


def test_app_has_title():
    deps = Dependencies()
    app = create_app(dependencies=deps)
    assert app.title == "Gaia"
