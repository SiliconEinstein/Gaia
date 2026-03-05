"""Tests for gaia search command."""

from typer.testing import CliRunner
from cli.main import app

runner = CliRunner()


def test_search_finds_claim(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner.invoke(app, ["init"])
    runner.invoke(app, ["claim", "石头比树叶落得快", "--type", "observation"])
    runner.invoke(app, ["claim", "铁比木头落得快", "--type", "observation"])
    runner.invoke(app, ["claim", "万有引力", "--type", "theory"])
    result = runner.invoke(app, ["search", "石头"])
    assert result.exit_code == 0
    assert "石头" in result.output


def test_search_no_claims(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner.invoke(app, ["init"])
    result = runner.invoke(app, ["search", "anything"])
    assert result.exit_code == 0
    assert "No claims" in result.output
