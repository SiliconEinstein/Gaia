"""Tests for gaia show command."""

from typer.testing import CliRunner

from cli.main import app

runner = CliRunner()

FIXTURE_PATH = "tests/fixtures/gaia_language_packages/galileo_falling_bodies"


def test_show_claim_details():
    result = runner.invoke(app, ["show", "heavier_falls_faster", "--path", FIXTURE_PATH])
    assert result.exit_code == 0
    assert "heavier_falls_faster" in result.output
    assert "claim" in result.output.lower()
    assert "0.7" in result.output


def test_show_connected_chains():
    """heavier_falls_faster should appear in multiple chains."""
    result = runner.invoke(app, ["show", "heavier_falls_faster", "--path", FIXTURE_PATH])
    assert result.exit_code == 0
    assert "chain" in result.output.lower()


def test_show_unknown_declaration():
    result = runner.invoke(app, ["show", "nonexistent_claim", "--path", FIXTURE_PATH])
    assert result.exit_code != 0


def test_show_setting():
    result = runner.invoke(app, ["show", "thought_experiment_env", "--path", FIXTURE_PATH])
    assert result.exit_code == 0
    assert "setting" in result.output.lower()
