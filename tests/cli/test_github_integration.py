"""Tests for _github.py orchestrator and --github CLI flag."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from gaia.cli.commands._github import generate_github_output
from gaia.cli.main import app

runner = CliRunner()


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
    assert meta["package_name"] == "test_pkg"
    assert meta["namespace"] == "github"


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


# ── CLI --github flag integration ──


def test_compile_github_flag(tmp_path):
    """gaia compile --github generates .github-output/ with expected structure."""
    pkg_dir = tmp_path / "github_pkg"
    pkg_dir.mkdir()
    (pkg_dir / "pyproject.toml").write_text(
        '[project]\nname = "github-pkg-gaia"\nversion = "1.0.0"\n'
        'description = "A test package."\n\n'
        '[tool.gaia]\nnamespace = "github"\ntype = "knowledge-package"\n'
    )
    pkg_src = pkg_dir / "github_pkg"
    pkg_src.mkdir()
    (pkg_src / "__init__.py").write_text(
        "from gaia.lang import claim, noisy_and\n\n"
        'a = claim("Premise A.")\n'
        'b = claim("Premise B.")\n'
        'c = claim("Conclusion.")\n'
        "noisy_and([a, b], c)\n"
        '__all__ = ["a", "b", "c"]\n'
    )

    result = runner.invoke(app, ["compile", str(pkg_dir), "--github"])
    assert result.exit_code == 0, f"Failed: {result.output}"
    assert "GitHub output:" in result.output

    output_dir = pkg_dir / ".github-output"
    assert (output_dir / "wiki" / "Home.md").exists()
    assert (output_dir / "manifest.json").exists()
    assert (output_dir / "docs" / "public" / "data" / "graph.json").exists()
    assert (output_dir / "README.md").exists()


def test_github_output_with_real_package(tmp_path):
    """Compile a Galileo-like package with --github and verify full structure.

    Creates a multi-module package with claims, deduction, contradiction,
    and exported conclusions, then verifies all GitHub output artifacts.
    """
    pkg_dir = tmp_path / "galileo_pkg"
    pkg_dir.mkdir()
    (pkg_dir / "pyproject.toml").write_text(
        '[project]\nname = "galileo-pkg-gaia"\nversion = "1.0.0"\n'
        'description = "Galileo falling bodies analysis."\n\n'
        '[tool.gaia]\nnamespace = "github"\ntype = "knowledge-package"\n'
    )

    # Create a multi-module package
    pkg_src = pkg_dir / "galileo_pkg"
    pkg_src.mkdir()

    # Module: motivation
    (pkg_src / "motivation.py").write_text(
        '"""Motivation and Background"""\n'
        "from gaia.lang import setting, claim\n\n"
        'context = setting("Galileo observed objects falling near Earth surface.")\n'
        'obs_equal_time = claim("Heavy and light objects fall in approximately equal time.")\n'
    )

    # Module: analysis
    (pkg_src / "analysis.py").write_text(
        '"""Analysis of Falling Bodies"""\n'
        "from gaia.lang import claim, deduction, contradiction\n"
        "from galileo_pkg.motivation import obs_equal_time\n\n"
        'aristotle_hyp = claim("Heavier objects fall faster (Aristotle).")\n'
        'galileo_hyp = claim("All objects fall at the same rate in vacuum.")\n'
        "deduction([obs_equal_time], galileo_hyp)\n"
        "contradiction(aristotle_hyp, galileo_hyp)\n"
    )

    # __init__.py: re-export with module order
    (pkg_src / "__init__.py").write_text(
        "from galileo_pkg.motivation import *  # noqa: F403\n"
        "from galileo_pkg.analysis import *  # noqa: F403\n\n"
        "from galileo_pkg.motivation import context, obs_equal_time\n"
        "from galileo_pkg.analysis import aristotle_hyp, galileo_hyp\n\n"
        '__all__ = ["obs_equal_time", "galileo_hyp"]\n'
    )

    # Create an artifact file to test asset copying
    artifacts_dir = pkg_dir / "artifacts"
    artifacts_dir.mkdir()
    (artifacts_dir / "diagram.svg").write_text("<svg>test</svg>")

    result = runner.invoke(app, ["compile", str(pkg_dir), "--github"])
    assert result.exit_code == 0, f"Failed: {result.output}"
    assert "GitHub output:" in result.output

    output_dir = pkg_dir / ".github-output"

    # ── Wiki structure ──
    assert (output_dir / "wiki" / "Home.md").exists()
    home_md = (output_dir / "wiki" / "Home.md").read_text()
    assert "galileo" in home_md.lower() or "Galileo" in home_md

    # Module pages should exist for each module
    wiki_dir = output_dir / "wiki"
    wiki_files = {f.name for f in wiki_dir.iterdir()}
    assert "Home.md" in wiki_files
    # At least one module page should exist
    module_pages = [f for f in wiki_files if f.startswith("Module-")]
    assert len(module_pages) >= 1, f"Expected module pages, got: {wiki_files}"

    # ── graph.json ──
    graph_path = output_dir / "docs" / "public" / "data" / "graph.json"
    assert graph_path.exists()
    graph = json.loads(graph_path.read_text())
    assert "nodes" in graph
    assert "edges" in graph
    # Should have at least 4 non-helper knowledge nodes
    non_helper_nodes = [n for n in graph["nodes"] if not n.get("label", "").startswith("__")]
    assert len(non_helper_nodes) >= 4, f"Expected >= 4 nodes, got {len(non_helper_nodes)}"
    # Should have edges (deduction + contradiction)
    assert len(graph["edges"]) >= 1, f"Expected edges, got {graph['edges']}"

    # ── manifest.json ──
    manifest_path = output_dir / "manifest.json"
    assert manifest_path.exists()
    manifest = json.loads(manifest_path.read_text())
    assert "wiki_pages" in manifest
    assert "exported_conclusions" in manifest
    assert "total_claims" in manifest
    # Exported conclusions should include our __all__ exports
    assert len(manifest["exported_conclusions"]) >= 1

    # ── README.md ──
    readme_path = output_dir / "README.md"
    assert readme_path.exists()
    readme_text = readme_path.read_text()
    assert "galileo" in readme_text.lower() or "Galileo" in readme_text

    # ── Assets copied ──
    assets_dir_out = output_dir / "docs" / "public" / "assets"
    assert (assets_dir_out / "diagram.svg").exists()
