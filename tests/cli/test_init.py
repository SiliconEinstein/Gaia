"""Tests for gaia init command."""

from typer.testing import CliRunner

from cli.main import app

runner = CliRunner()


def test_init_creates_typst_toml(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["init", "my_package"])
    assert result.exit_code == 0
    pkg_dir = tmp_path / "my_package"
    assert pkg_dir.exists()
    toml_file = pkg_dir / "typst.toml"
    assert toml_file.exists()
    content = toml_file.read_text()
    assert "my_package" in content


def test_init_creates_lib_typ(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["init", "my_package"])
    assert result.exit_code == 0
    lib_file = tmp_path / "my_package" / "lib.typ"
    assert lib_file.exists()


def test_init_creates_motivation_module(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["init", "my_package"])
    assert result.exit_code == 0
    mod_file = tmp_path / "my_package" / "motivation.typ"
    assert mod_file.exists()
    content = mod_file.read_text()
    assert "main_question" in content


def test_init_refuses_existing_directory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "existing_pkg").mkdir()
    result = runner.invoke(app, ["init", "existing_pkg"])
    assert result.exit_code != 0
