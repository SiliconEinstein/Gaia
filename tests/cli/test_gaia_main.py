"""Tests for the Gaia CLI entry point."""

from typer.testing import CliRunner

from cli.main import app

runner = CliRunner()


def test_help_shows_all_commands():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    for cmd in ["build", "publish", "init", "search", "clean"]:
        assert cmd in result.output


def test_build_stub():
    result = runner.invoke(app, ["build", "--help"])
    assert result.exit_code == 0


def test_init_stub():
    result = runner.invoke(app, ["init", "--help"])
    assert result.exit_code == 0


def test_clean_stub():
    result = runner.invoke(app, ["clean", "--help"])
    assert result.exit_code == 0


def test_search_stub():
    result = runner.invoke(app, ["search", "--help"])
    assert result.exit_code == 0


def test_publish_stub():
    result = runner.invoke(app, ["publish", "--help"])
    assert result.exit_code == 0
