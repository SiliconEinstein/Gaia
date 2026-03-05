"""Tests for gaia show command."""

from typer.testing import CliRunner
from cli.main import app

runner = CliRunner()


def test_show_existing_claim(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner.invoke(app, ["init"])
    runner.invoke(app, ["claim", "测试命题", "--type", "axiom"])
    result = runner.invoke(app, ["show", "1"])
    assert result.exit_code == 0
    assert "测试命题" in result.output
    assert "axiom" in result.output


def test_show_nonexistent_claim(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner.invoke(app, ["init"])
    result = runner.invoke(app, ["show", "999"])
    assert result.exit_code != 0
