"""Tests for the lightweight GitHub output bundle in _github.py."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from gaia.cli.commands._github import generate_github_output

pytestmark = pytest.mark.pr_gate


def test_github_data_bundle_written_without_react_template(tmp_path: Path):
    """GitHub output writes data/assets directly and no longer ships a React app."""
    ir = {
        "package_name": "test_pkg",
        "namespace": "github",
        "knowledges": [
            {
                "id": "github:test_pkg::a",
                "label": "a",
                "type": "claim",
                "content": "A.",
                "module": "motivation",
            },
        ],
        "strategies": [],
        "operators": [],
        "ir_hash": "sha256:abc",
    }
    pkg_path = tmp_path / "test-pkg-gaia"
    pkg_path.mkdir()
    (pkg_path / "artifacts").mkdir()

    output_dir = generate_github_output(
        ir,
        pkg_path,
        beliefs_data=None,
        param_data=None,
        exported_ids={"github:test_pkg::a"},
    )

    docs_dir = output_dir / "docs"
    assert (docs_dir / "public" / "data" / "graph.json").exists()
    assert (docs_dir / "public" / "data" / "meta.json").exists()
    assert (docs_dir / "public" / "data" / "sections" / "motivation.md").exists()
    assert (docs_dir / "public" / "assets").is_dir()

    assert not (docs_dir / "package.json").exists()
    assert not (docs_dir / "src").exists()
    assert not (docs_dir / "index.html").exists()
    assert not (docs_dir / "vite.config.ts").exists()


def test_github_output_resets_stale_existing_bundle(tmp_path: Path):
    """Regenerating GitHub output removes stale files from prior React bundles."""
    ir = {
        "package_name": "test_pkg",
        "namespace": "github",
        "knowledges": [],
        "strategies": [],
        "operators": [],
        "ir_hash": "sha256:abc",
    }
    pkg_path = tmp_path / "test-pkg-gaia"
    stale_docs_dir = pkg_path / ".github-output" / "docs"
    stale_docs_dir.mkdir(parents=True)
    (stale_docs_dir / "package.json").write_text("{}")
    (stale_docs_dir / "src").mkdir()
    (stale_docs_dir / "src" / "App.tsx").write_text("export default function App() {}")

    output_dir = generate_github_output(
        ir,
        pkg_path,
        beliefs_data=None,
        param_data=None,
        exported_ids=set(),
    )

    assert not (output_dir / "docs" / "package.json").exists()
    assert not (output_dir / "docs" / "src").exists()
    assert (output_dir / "docs" / "public" / "data" / "graph.json").exists()


def test_meta_json_content(tmp_path: Path):
    """meta.json should include package_name and namespace from IR."""
    ir = {
        "package_name": "test_pkg",
        "namespace": "github",
        "knowledges": [],
        "strategies": [],
        "operators": [],
        "ir_hash": "sha256:abc",
    }
    pkg_path = tmp_path / "pkg"
    pkg_path.mkdir()

    output_dir = generate_github_output(
        ir,
        pkg_path,
        beliefs_data=None,
        param_data=None,
        exported_ids=set(),
        pkg_metadata={"name": "my-pkg-gaia", "description": "A test pkg."},
    )

    meta = json.loads((output_dir / "docs" / "public" / "data" / "meta.json").read_text())
    assert meta["package_name"] == "test_pkg"
    assert meta["namespace"] == "github"
    assert meta["name"] == "my-pkg-gaia"
    assert meta["description"] == "A test pkg."


def test_output_tree_does_not_include_pycache(tmp_path: Path):
    """Python bytecode caches should not leak into generated output."""
    ir = {
        "package_name": "pkg",
        "namespace": "github",
        "knowledges": [],
        "strategies": [],
        "operators": [],
    }
    pkg_path = tmp_path / "pkg"
    pkg_path.mkdir()

    output_dir = generate_github_output(
        ir, pkg_path, beliefs_data=None, param_data=None, exported_ids=set()
    )

    assert not list(output_dir.rglob("__pycache__"))
