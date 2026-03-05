"""Tests for gaia init command."""

from typer.testing import CliRunner
from cli.main import app

runner = CliRunner()


def test_init_creates_package(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["init", "galileo_tied_balls"])
    assert result.exit_code == 0
    pkg_dir = tmp_path / "galileo_tied_balls"
    assert (pkg_dir / "gaia.toml").exists()
    assert (pkg_dir / "claims").is_dir()


def test_init_in_current_dir(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["init"])
    assert result.exit_code == 0
    assert (tmp_path / "gaia.toml").exists()
    assert (tmp_path / "claims").is_dir()


def test_init_already_exists(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner.invoke(app, ["init"])
    result = runner.invoke(app, ["init"])
    assert result.exit_code != 0
