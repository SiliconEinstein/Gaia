"""Tests for gaia build command."""

from typer.testing import CliRunner
from cli.main import app

runner = CliRunner()


def test_build_valid_package(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner.invoke(app, ["init"])
    runner.invoke(app, ["claim", "前提A", "--type", "axiom"])
    runner.invoke(app, ["claim", "结论B", "--premise", "1", "--why", "推导", "--type", "deduction"])
    result = runner.invoke(app, ["build"])
    assert result.exit_code == 0
    assert "✓" in result.output


def test_build_invalid_premise_ref(tmp_path, monkeypatch):
    """Build should fail if premise references nonexistent claim."""
    monkeypatch.chdir(tmp_path)
    runner.invoke(app, ["init"])
    runner.invoke(
        app, ["claim", "结论B", "--premise", "999", "--why", "推导", "--type", "deduction"]
    )
    result = runner.invoke(app, ["build"])
    assert result.exit_code != 0 or "error" in result.output.lower()


def test_build_runs_bp(tmp_path, monkeypatch):
    """Build should run BP and show belief values."""
    monkeypatch.chdir(tmp_path)
    runner.invoke(app, ["init"])
    runner.invoke(app, ["claim", "公理A", "--type", "axiom"])
    runner.invoke(app, ["claim", "公理B", "--type", "axiom"])
    runner.invoke(
        app, ["claim", "推论C", "--premise", "1,2", "--why", "A+B推C", "--type", "deduction"]
    )
    result = runner.invoke(app, ["build"])
    assert result.exit_code == 0
    assert "BP" in result.output or "belief" in result.output.lower()


def test_build_generates_lockfile(tmp_path, monkeypatch):
    """Build should generate gaia.lock."""
    monkeypatch.chdir(tmp_path)
    runner.invoke(app, ["init"])
    runner.invoke(app, ["claim", "本地命题", "--type", "axiom"])
    runner.invoke(app, ["build"])
    lock_path = tmp_path / "gaia.lock"
    assert lock_path.exists()


def test_build_no_claims(tmp_path, monkeypatch):
    """Build with no claims should fail."""
    monkeypatch.chdir(tmp_path)
    runner.invoke(app, ["init"])
    result = runner.invoke(app, ["build"])
    assert result.exit_code != 0
