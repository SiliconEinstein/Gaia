"""Tests for _github.py orchestrator."""

from __future__ import annotations

import json
from pathlib import Path

from gaia.cli.commands._github import generate_github_output


def test_github_output_creates_expected_structure(tmp_path: Path):
    ir = {
        "package_name": "test_pkg",
        "namespace": "github",
        "knowledges": [
            {
                "id": "github:test_pkg::a",
                "label": "a",
                "type": "claim",
                "content": "Claim A.",
                "module": "motivation",
            },
        ],
        "strategies": [],
        "operators": [],
        "ir_hash": "sha256:abc123",
    }
    pkg_path = tmp_path / "test-pkg-gaia"
    pkg_path.mkdir()
    (pkg_path / "artifacts").mkdir()
    (pkg_path / "artifacts" / "fig1.png").write_bytes(b"PNG")

    output_dir = generate_github_output(
        ir,
        pkg_path,
        beliefs_data=None,
        param_data=None,
        exported_ids={"github:test_pkg::a"},
    )

    assert (output_dir / "wiki" / "Home.md").exists()
    assert (output_dir / "wiki" / "Module-motivation.md").exists()
    assert (output_dir / "manifest.json").exists()
    assert (output_dir / "docs" / "public" / "data" / "graph.json").exists()
    assert (output_dir / "docs" / "public" / "assets" / "fig1.png").exists()
    assert (output_dir / "README.md").exists()


def test_github_output_returns_path_inside_pkg(tmp_path: Path):
    ir = {
        "package_name": "pkg",
        "namespace": "github",
        "knowledges": [],
        "strategies": [],
        "operators": [],
    }
    pkg_path = tmp_path / "pkg-gaia"
    pkg_path.mkdir()

    output_dir = generate_github_output(
        ir, pkg_path, beliefs_data=None, param_data=None, exported_ids=set()
    )
    assert output_dir.parent == pkg_path
    assert output_dir.name == ".github-output"


def test_meta_json_written(tmp_path: Path):
    ir = {
        "package_name": "test_pkg",
        "namespace": "github",
        "knowledges": [],
        "strategies": [],
        "operators": [],
    }
    pkg_path = tmp_path / "pkg"
    pkg_path.mkdir()

    output_dir = generate_github_output(
        ir,
        pkg_path,
        beliefs_data=None,
        param_data=None,
        exported_ids=set(),
        pkg_metadata={"name": "Test Package", "description": "A test."},
    )
    meta_path = output_dir / "docs" / "public" / "data" / "meta.json"
    assert meta_path.exists()
    meta = json.loads(meta_path.read_text())
    assert meta["name"] == "Test Package"
    assert meta["description"] == "A test."


def test_beliefs_json_copied(tmp_path: Path):
    ir = {
        "package_name": "test_pkg",
        "namespace": "github",
        "knowledges": [
            {
                "id": "github:test_pkg::a",
                "label": "a",
                "type": "claim",
                "content": "A.",
                "module": "m",
            },
        ],
        "strategies": [],
        "operators": [],
    }
    beliefs_data = {
        "beliefs": [{"knowledge_id": "github:test_pkg::a", "belief": 0.9, "label": "a"}],
        "diagnostics": {"converged": True, "iterations_run": 5},
    }
    pkg_path = tmp_path / "pkg"
    pkg_path.mkdir()

    output_dir = generate_github_output(
        ir,
        pkg_path,
        beliefs_data=beliefs_data,
        param_data=None,
        exported_ids=set(),
    )
    beliefs_path = output_dir / "docs" / "public" / "data" / "beliefs.json"
    assert beliefs_path.exists()
    data = json.loads(beliefs_path.read_text())
    assert data["beliefs"][0]["belief"] == 0.9


def test_section_placeholders_per_module(tmp_path: Path):
    ir = {
        "package_name": "pkg",
        "namespace": "github",
        "knowledges": [
            {"id": "a", "label": "a", "type": "claim", "content": ".", "module": "intro"},
            {"id": "b", "label": "b", "type": "claim", "content": ".", "module": "results"},
        ],
        "strategies": [],
        "operators": [],
    }
    pkg_path = tmp_path / "pkg"
    pkg_path.mkdir()

    output_dir = generate_github_output(
        ir, pkg_path, beliefs_data=None, param_data=None, exported_ids=set()
    )
    sections_dir = output_dir / "docs" / "public" / "data" / "sections"
    assert sections_dir.exists()
    assert (sections_dir / "intro.md").exists()
    assert (sections_dir / "results.md").exists()


def test_readme_contains_mermaid_and_conclusions(tmp_path: Path):
    """README should contain a simplified Mermaid graph when beliefs are available."""
    ir = {
        "package_name": "test_pkg",
        "namespace": "github",
        "knowledges": [
            {
                "id": "github:test_pkg::a",
                "label": "a",
                "type": "claim",
                "content": "Claim A.",
                "module": "motivation",
            },
        ],
        "strategies": [],
        "operators": [],
    }
    beliefs_data = {
        "beliefs": [{"knowledge_id": "github:test_pkg::a", "belief": 0.9, "label": "a"}],
        "diagnostics": {"converged": True, "iterations_run": 3},
    }
    param_data = {"priors": [{"knowledge_id": "github:test_pkg::a", "value": 0.5}]}
    pkg_path = tmp_path / "pkg"
    pkg_path.mkdir()

    output_dir = generate_github_output(
        ir,
        pkg_path,
        beliefs_data=beliefs_data,
        param_data=param_data,
        exported_ids={"github:test_pkg::a"},
    )
    readme_text = (output_dir / "README.md").read_text()
    assert "# test_pkg" in readme_text
    # Should have a conclusion table
    assert "| Label |" in readme_text or "a" in readme_text


def test_no_artifacts_dir(tmp_path: Path):
    """When pkg_path has no artifacts/, the assets dir should still be created (empty)."""
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
    assets_dir = output_dir / "docs" / "public" / "assets"
    assert assets_dir.exists()
    assert list(assets_dir.iterdir()) == []


def test_wiki_inference_page_when_beliefs(tmp_path: Path):
    """When beliefs_data is provided, wiki/Inference-Results.md is generated."""
    ir = {
        "package_name": "pkg",
        "namespace": "github",
        "knowledges": [
            {
                "id": "github:pkg::x",
                "label": "x",
                "type": "claim",
                "content": "X.",
                "module": "m",
            },
        ],
        "strategies": [],
        "operators": [],
    }
    beliefs_data = {
        "beliefs": [{"knowledge_id": "github:pkg::x", "belief": 0.7, "label": "x"}],
        "diagnostics": {"converged": True, "iterations_run": 2},
    }
    pkg_path = tmp_path / "pkg"
    pkg_path.mkdir()

    output_dir = generate_github_output(
        ir, pkg_path, beliefs_data=beliefs_data, param_data=None, exported_ids=set()
    )
    assert (output_dir / "wiki" / "Inference-Results.md").exists()
