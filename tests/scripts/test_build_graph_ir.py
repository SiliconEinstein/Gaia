"""Tests for scripts/pipeline/build_graph_ir.py — Typst v4 path with priors."""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[2] / "scripts" / "pipeline"))

from scripts.pipeline.build_graph_ir import build_package_graph_ir

FIXTURES_DIR = Path(__file__).parents[1] / "fixtures" / "ir"
TYPST_PKG = FIXTURES_DIR / "galileo_falling_bodies_v4"


@pytest.fixture(autouse=False)
def clean_typst_graph_ir():
    """Clean up graph_ir/ written to Typst fixture dir after test."""
    yield
    graph_dir = TYPST_PKG / "graph_ir"
    if graph_dir.exists():
        shutil.rmtree(graph_dir)


class TestBuildFromTypst:
    """Test the Typst package path (runs in-place due to relative imports)."""

    def test_builds_successfully(self, clean_typst_graph_ir):
        assert build_package_graph_ir(TYPST_PKG)

    def test_outputs_exist(self, clean_typst_graph_ir):
        build_package_graph_ir(TYPST_PKG)
        graph_dir = TYPST_PKG / "graph_ir"
        assert (graph_dir / "raw_graph.json").exists()
        assert (graph_dir / "local_canonical_graph.json").exists()
        assert (graph_dir / "canonicalization_log.json").exists()
        assert (graph_dir / "local_parameterization.json").exists()

    def test_raw_graph_has_nodes_and_factors(self, clean_typst_graph_ir):
        build_package_graph_ir(TYPST_PKG)
        raw = json.loads((TYPST_PKG / "graph_ir" / "raw_graph.json").read_text())
        assert len(raw["knowledge_nodes"]) > 0
        assert len(raw["factor_nodes"]) > 0
        assert raw["package"] == "galileo_falling_bodies"

    def test_local_parameterization_has_priors(self, clean_typst_graph_ir):
        build_package_graph_ir(TYPST_PKG)
        params = json.loads((TYPST_PKG / "graph_ir" / "local_parameterization.json").read_text())
        local_graph = json.loads(
            (TYPST_PKG / "graph_ir" / "local_canonical_graph.json").read_text()
        )
        for node in local_graph["knowledge_nodes"]:
            lcn_id = node["local_canonical_id"]
            assert lcn_id in params["node_priors"], f"Missing prior for {lcn_id}"


class TestDetection:
    """Test package type detection."""

    def test_skip_no_package(self, tmp_path):
        assert not build_package_graph_ir(tmp_path)
