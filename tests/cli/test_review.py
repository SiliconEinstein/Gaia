"""Tests for gaia review command."""

from unittest.mock import patch, AsyncMock
from typer.testing import CliRunner
from cli.main import app

runner = CliRunner()

MOCK_REVIEW = """score: 0.92
justification: "valid"
confirmed_premises: [1]
downgraded_premises: []
upgraded_context: []
irrelevant: []
suggested_premise: []
suggested_context: []"""


def test_review_single_claim(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner.invoke(app, ["init"])
    runner.invoke(app, ["claim", "公理A", "--type", "axiom"])
    runner.invoke(app, ["claim", "结论B", "--premise", "1", "--why", "推导", "--type", "deduction"])

    with patch("cli.commands.review._call_llm", new_callable=AsyncMock, return_value=MOCK_REVIEW):
        result = runner.invoke(app, ["review", "2"])
    assert result.exit_code == 0
    assert "0.92" in result.output


def test_review_all_claims(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner.invoke(app, ["init"])
    runner.invoke(app, ["claim", "公理A", "--type", "axiom"])
    runner.invoke(app, ["claim", "结论B", "--premise", "1", "--why", "推导", "--type", "deduction"])

    with patch("cli.commands.review._call_llm", new_callable=AsyncMock, return_value=MOCK_REVIEW):
        result = runner.invoke(app, ["review"])
    assert result.exit_code == 0
    assert "Score" in result.output or "score" in result.output


def test_review_saves_results(tmp_path, monkeypatch):
    """Review results should be persisted locally."""
    monkeypatch.chdir(tmp_path)
    runner.invoke(app, ["init"])
    runner.invoke(app, ["claim", "公理A", "--type", "axiom"])
    runner.invoke(app, ["claim", "结论B", "--premise", "1", "--why", "推导", "--type", "deduction"])

    with patch("cli.commands.review._call_llm", new_callable=AsyncMock, return_value=MOCK_REVIEW):
        runner.invoke(app, ["review", "2"])

    review_dir = tmp_path / ".gaia" / "reviews"
    assert review_dir.exists()
    review_files = list(review_dir.glob("*.yaml"))
    assert len(review_files) >= 1
