"""Tests for gaia init command."""


import yaml
from typer.testing import CliRunner

from cli.main import app

runner = CliRunner()


def test_init_creates_package_yaml(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["init", "my_package"])
    assert result.exit_code == 0
    pkg_dir = tmp_path / "my_package"
    assert pkg_dir.exists()
    pkg_yaml = pkg_dir / "package.yaml"
    assert pkg_yaml.exists()
    data = yaml.safe_load(pkg_yaml.read_text())
    assert data["name"] == "my_package"
    assert data["version"] == "0.1.0"
    assert "modules" in data
    assert "motivation" in data["modules"]


def test_init_creates_motivation_module(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["init", "my_package"])
    assert result.exit_code == 0
    mod_file = tmp_path / "my_package" / "motivation.yaml"
    assert mod_file.exists()
    data = yaml.safe_load(mod_file.read_text())
    assert data["type"] == "motivation_module"
    assert data["name"] == "motivation"
    assert len(data["declarations"]) >= 1


def test_init_refuses_existing_directory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "existing_pkg").mkdir()
    result = runner.invoke(app, ["init", "existing_pkg"])
    assert result.exit_code != 0
