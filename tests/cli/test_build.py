"""Tests for gaia build command."""


import yaml
from typer.testing import CliRunner

from cli.main import app

runner = CliRunner()

FIXTURE_PATH = "tests/fixtures/dsl_packages/galileo_falling_bodies"


def test_build_creates_gaia_dir(tmp_path):
    """gaia build should create .gaia/build/ directory."""
    import shutil

    pkg_dir = tmp_path / "galileo"
    shutil.copytree(FIXTURE_PATH, pkg_dir)
    result = runner.invoke(app, ["build", str(pkg_dir)])
    assert result.exit_code == 0
    assert (pkg_dir / ".gaia" / "build").exists()


def test_build_creates_elaborated_yaml(tmp_path):
    """gaia build should write elaborated.yaml with package data and prompts."""
    import shutil

    pkg_dir = tmp_path / "galileo"
    shutil.copytree(FIXTURE_PATH, pkg_dir)
    result = runner.invoke(app, ["build", str(pkg_dir)])
    assert result.exit_code == 0
    elab_file = pkg_dir / ".gaia" / "build" / "elaborated.yaml"
    assert elab_file.exists()
    data = yaml.safe_load(elab_file.read_text())
    assert data["package"]["name"] == "galileo_falling_bodies"
    assert "modules" in data["package"]
    assert "prompts" in data
    assert len(data["prompts"]) >= 11


def test_build_output_contains_module_count(tmp_path):
    """gaia build should print summary."""
    import shutil

    pkg_dir = tmp_path / "galileo"
    shutil.copytree(FIXTURE_PATH, pkg_dir)
    result = runner.invoke(app, ["build", str(pkg_dir)])
    assert result.exit_code == 0
    assert "galileo_falling_bodies" in result.output
    assert "5 modules" in result.output


def test_build_elaborated_yaml_has_chain_contexts(tmp_path):
    """elaborated.yaml should include chain_contexts dict."""
    import shutil

    pkg_dir = tmp_path / "galileo"
    shutil.copytree(FIXTURE_PATH, pkg_dir)
    runner.invoke(app, ["build", str(pkg_dir)])
    elab_file = pkg_dir / ".gaia" / "build" / "elaborated.yaml"
    data = yaml.safe_load(elab_file.read_text())
    assert "chain_contexts" in data
    assert "drag_prediction_chain" in data["chain_contexts"]
    assert data["chain_contexts"]["contradiction_chain"]["edge_type"] == "contradiction"


def test_build_invalid_path():
    result = runner.invoke(app, ["build", "/nonexistent/path"])
    assert result.exit_code != 0
