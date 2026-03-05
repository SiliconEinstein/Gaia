"""End-to-end test: recreate Galileo tied balls via CLI."""

from unittest.mock import AsyncMock, patch

from typer.testing import CliRunner
from cli.main import app

runner = CliRunner()


def test_galileo_full_workflow(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner.invoke(app, ["init", "galileo_tied_balls"])
    monkeypatch.chdir(tmp_path / "galileo_tied_balls")

    # Aristotle's observations
    runner.invoke(app, ["claim", "石头比树叶落得快", "--type", "observation"])
    runner.invoke(app, ["claim", "铁比木头落得快", "--type", "observation"])
    runner.invoke(app, ["claim", "v ∝ W 定律", "--premise", "1,2", "--why", "归纳观察", "--type", "theory"])

    # Tied balls thought experiment
    runner.invoke(app, ["claim", "绑球设定", "--type", "axiom"])
    runner.invoke(app, ["claim", "推导A: HL更慢", "--premise", "3,4", "--why", "轻球拖拽重球", "--type", "deduction"])
    runner.invoke(app, ["claim", "推导B: HL更快", "--premise", "3,4", "--why", "总重量更大", "--type", "deduction"])
    runner.invoke(app, ["claim", "矛盾: 不可能既快又慢", "--premise", "5,6", "--type", "contradiction"])

    # Build and verify
    result = runner.invoke(app, ["build"])
    assert result.exit_code == 0

    # Contradictions should be found
    result = runner.invoke(app, ["contradictions"])
    assert "矛盾" in result.output

    # Stats
    result = runner.invoke(app, ["stats"])
    assert "7" in result.output  # 7 claims


def test_galileo_with_review(tmp_path, monkeypatch):
    """Full workflow: init -> claim -> build -> review -> build (with scores)."""
    monkeypatch.chdir(tmp_path)
    runner.invoke(app, ["init", "galileo"])
    monkeypatch.chdir(tmp_path / "galileo")

    runner.invoke(app, ["claim", "v ∝ W", "--type", "theory"])
    runner.invoke(app, ["claim", "绑球设定", "--type", "axiom"])
    runner.invoke(
        app,
        ["claim", "HL更慢", "--premise", "1,2", "--why", "轻球拖拽", "--type", "deduction"],
    )
    runner.invoke(
        app,
        ["claim", "HL更快", "--premise", "1,2", "--why", "总重更大", "--type", "deduction"],
    )
    runner.invoke(app, ["claim", "矛盾", "--premise", "3,4", "--type", "contradiction"])

    # Build without review
    result = runner.invoke(app, ["build"])
    assert result.exit_code == 0

    # Mock review
    mock_review = (
        'score: 0.95\n'
        'justification: "valid"\n'
        'confirmed_premises: [1, 2]\n'
        'downgraded_premises: []\n'
        'upgraded_context: []\n'
        'irrelevant: []\n'
        'suggested_premise: []\n'
        'suggested_context: []'
    )
    with patch(
        "cli.commands.review._call_llm", new_callable=AsyncMock, return_value=mock_review
    ):
        result = runner.invoke(app, ["review"])
    assert result.exit_code == 0

    # Build again with review scores
    result = runner.invoke(app, ["build"])
    assert result.exit_code == 0
