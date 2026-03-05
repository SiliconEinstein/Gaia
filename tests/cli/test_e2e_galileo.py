"""End-to-end test: recreate Galileo tied balls via CLI."""

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
