"""Tests for React template copying and integration in _github.py."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from gaia.cli.commands._github import generate_github_output


def test_react_template_copied(tmp_path: Path):
    """React template files should be present in docs/ after generation."""
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

    # React template files should be present
    assert (docs_dir / "package.json").exists()
    assert (docs_dir / "src" / "App.tsx").exists()
    assert (docs_dir / "src" / "components" / "KnowledgeGraph.tsx").exists()
    assert (docs_dir / "index.html").exists()
    assert (docs_dir / "vite.config.ts").exists()
    assert (docs_dir / "tsconfig.json").exists()

    # Data files should be overlaid on top of template
    assert (docs_dir / "public" / "data" / "graph.json").exists()
    assert (docs_dir / "public" / "data" / "meta.json").exists()

    # node_modules and package-lock.json should NOT be copied
    assert not (docs_dir / "node_modules").exists()
    assert not (docs_dir / "package-lock.json").exists()


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


def test_template_does_not_include_pycache(tmp_path: Path):
    """__pycache__ directories should be excluded from the template copy."""
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
    docs_dir = output_dir / "docs"

    # Walk entire docs tree — no __pycache__ anywhere
    for p in docs_dir.rglob("__pycache__"):
        pytest.fail(f"__pycache__ found at {p}")


@pytest.mark.slow
def test_react_app_builds(tmp_path: Path):
    """The generated React app should build successfully with npm."""
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

    output_dir = generate_github_output(
        ir,
        pkg_path,
        beliefs_data=None,
        param_data=None,
        exported_ids={"github:test_pkg::a"},
    )

    docs_dir = output_dir / "docs"

    result = subprocess.run(
        ["npm", "install"],
        cwd=docs_dir,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, f"npm install failed: {result.stderr}"

    result = subprocess.run(
        ["npm", "run", "build"],
        cwd=docs_dir,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, f"npm build failed: {result.stderr}"

    assert (docs_dir / "dist" / "index.html").exists()
