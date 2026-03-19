"""Tests for gaia build command."""

import shutil
from pathlib import Path

import pytest
from typer.testing import CliRunner

from cli.main import app

runner = CliRunner()

TYPST_FIXTURE = "tests/fixtures/gaia_language_packages/galileo_falling_bodies_typst"


def test_build_invalid_path():
    result = runner.invoke(app, ["build", "/nonexistent/path"])
    assert result.exit_code != 0


def test_build_requires_typst_toml(tmp_path):
    """gaia build should fail if no typst.toml is found."""
    (tmp_path / "dummy.yaml").write_text("name: test")
    result = runner.invoke(app, ["build", str(tmp_path)])
    assert result.exit_code != 0
    assert "typst.toml" in result.output.lower()


# ---------------------------------------------------------------------------
# Typst build tests
# ---------------------------------------------------------------------------


@pytest.fixture()
def typst_fixture():
    """Use real fixture path so relative #import paths resolve; clean up .gaia after."""
    pkg = Path(TYPST_FIXTURE)
    yield pkg
    gaia_dir = pkg / ".gaia"
    if gaia_dir.exists():
        shutil.rmtree(gaia_dir)


def test_build_typst_package_default_format(typst_fixture):
    """gaia build on a Typst package should produce package.md (default --format md)."""
    result = runner.invoke(app, ["build", str(typst_fixture)])
    assert result.exit_code == 0, result.output
    md_path = typst_fixture / ".gaia" / "build" / "package.md"
    assert md_path.exists()
    content = md_path.read_text()
    assert "tied_balls" in content or "contradiction" in content
    assert "Build complete." in result.output


def test_build_typst_package_json_format(typst_fixture):
    """gaia build --format json should produce graph.json."""
    result = runner.invoke(app, ["build", str(typst_fixture), "--format", "json"])
    assert result.exit_code == 0, result.output
    json_path = typst_fixture / ".gaia" / "build" / "graph.json"
    assert json_path.exists()
    # Should NOT produce package.md when format=json
    md_path = typst_fixture / ".gaia" / "build" / "package.md"
    assert not md_path.exists()
    assert "Build complete." in result.output


def test_build_typst_package_all_format(typst_fixture):
    """gaia build --format all should produce both package.md and graph.json."""
    result = runner.invoke(app, ["build", str(typst_fixture), "--format", "all"])
    assert result.exit_code == 0, result.output
    build_dir = typst_fixture / ".gaia" / "build"
    assert (build_dir / "package.md").exists()
    assert (build_dir / "graph.json").exists()
    assert "Build complete." in result.output
