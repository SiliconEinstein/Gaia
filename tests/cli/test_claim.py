"""Tests for gaia claim command."""

import yaml
from typer.testing import CliRunner
from cli.main import app

runner = CliRunner()


def test_claim_basic(tmp_path, monkeypatch):
    """Add a simple claim with no premises."""
    monkeypatch.chdir(tmp_path)
    runner.invoke(app, ["init"])
    result = runner.invoke(
        app,
        [
            "claim",
            "石头比树叶落得快",
            "--type",
            "observation",
        ],
    )
    assert result.exit_code == 0
    assert "Created claim" in result.output

    # Verify YAML file was created
    claim_files = list((tmp_path / "claims").glob("*.yaml"))
    assert len(claim_files) == 1
    with open(claim_files[0]) as f:
        data = yaml.safe_load(f)
    assert data["claims"][0]["content"] == "石头比树叶落得快"
    assert data["claims"][0]["type"] == "observation"


def test_claim_with_premise(tmp_path, monkeypatch):
    """Add a claim with premise references."""
    monkeypatch.chdir(tmp_path)
    runner.invoke(app, ["init"])
    # First claim
    runner.invoke(app, ["claim", "前提A", "--type", "axiom"])
    # Second claim referencing first
    result = runner.invoke(
        app,
        [
            "claim",
            "结论B",
            "--premise",
            "1",
            "--why",
            "从A推导出B",
            "--type",
            "deduction",
        ],
    )
    assert result.exit_code == 0
    assert "Created claim" in result.output


def test_claim_increments_id(tmp_path, monkeypatch):
    """Each claim should get a unique incrementing ID."""
    monkeypatch.chdir(tmp_path)
    runner.invoke(app, ["init"])
    runner.invoke(app, ["claim", "A", "--type", "axiom"])
    runner.invoke(app, ["claim", "B", "--type", "axiom"])
    runner.invoke(app, ["claim", "C", "--type", "axiom"])

    from cli.package import load_all_claims

    claims = load_all_claims(tmp_path)
    ids = [c["id"] for c in claims]
    assert ids == [1, 2, 3]
