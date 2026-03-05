"""Tests for gaia stats and contradictions commands."""

from typer.testing import CliRunner
from cli.main import app

runner = CliRunner()


def test_stats_output(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner.invoke(app, ["init"])
    runner.invoke(app, ["claim", "A", "--type", "axiom"])
    runner.invoke(app, ["claim", "B", "--type", "axiom"])
    runner.invoke(app, ["claim", "C", "--premise", "1,2", "--type", "deduction", "--why", "test"])
    result = runner.invoke(app, ["stats"])
    assert result.exit_code == 0
    assert "3" in result.output
    assert "axiom" in result.output
    assert "deduction" in result.output


def test_contradictions_found(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner.invoke(app, ["init"])
    runner.invoke(app, ["claim", "A导致X", "--type", "deduction"])
    runner.invoke(app, ["claim", "A导致非X", "--type", "deduction"])
    runner.invoke(app, ["claim", "矛盾", "--premise", "1,2", "--type", "contradiction"])
    result = runner.invoke(app, ["contradictions"])
    assert result.exit_code == 0
    assert "矛盾" in result.output


def test_contradictions_none(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner.invoke(app, ["init"])
    runner.invoke(app, ["claim", "A", "--type", "axiom"])
    result = runner.invoke(app, ["contradictions"])
    assert result.exit_code == 0
    assert "No contradictions" in result.output
