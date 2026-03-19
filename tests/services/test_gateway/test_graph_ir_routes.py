"""Tests for graph IR routes."""

from fastapi.testclient import TestClient

from services.gateway.app import create_app
from services.gateway.deps import Dependencies


def _client():
    deps = Dependencies()
    deps.storage = None  # routes don't use storage
    app = create_app(dependencies=deps)
    return TestClient(app, raise_server_exceptions=False)


class TestGlobalGraphRoute:
    def test_get_global_graph(self):
        client = _client()
        resp = client.get("/graph-ir/global")
        assert resp.status_code == 200
        data = resp.json()
        assert "knowledge_nodes" in data
        assert "factor_nodes" in data
        assert "bindings" in data

    def test_get_global_graph_has_nodes(self):
        client = _client()
        data = client.get("/graph-ir/global").json()
        assert len(data["knowledge_nodes"]) > 0
        assert len(data["bindings"]) > 0


class TestPackageGraphRoutes:
    def test_list_packages(self):
        client = _client()
        resp = client.get("/graph-ir")
        assert resp.status_code == 200
        packages = resp.json()
        assert isinstance(packages, list)
        slugs = {p["slug"] for p in packages}
        assert "galileo_falling_bodies" in slugs

    def test_get_raw_graph(self):
        client = _client()
        resp = client.get("/graph-ir/galileo_falling_bodies/raw")
        assert resp.status_code == 200
        data = resp.json()
        assert "knowledge_nodes" in data
        assert "factor_nodes" in data

    def test_get_local_graph(self):
        client = _client()
        resp = client.get("/graph-ir/galileo_falling_bodies/local")
        assert resp.status_code == 200

    def test_get_parameterization(self):
        client = _client()
        resp = client.get("/graph-ir/galileo_falling_bodies/parameterization")
        assert resp.status_code == 200
        data = resp.json()
        assert "node_priors" in data

    def test_get_beliefs(self):
        client = _client()
        resp = client.get("/graph-ir/galileo_falling_bodies/beliefs")
        assert resp.status_code == 200
        data = resp.json()
        assert "node_beliefs" in data

    def test_404_missing_package(self):
        client = _client()
        assert client.get("/graph-ir/nonexistent/raw").status_code == 404
        assert client.get("/graph-ir/nonexistent/local").status_code == 404
        assert client.get("/graph-ir/nonexistent/parameterization").status_code == 404
        assert client.get("/graph-ir/nonexistent/beliefs").status_code == 404
