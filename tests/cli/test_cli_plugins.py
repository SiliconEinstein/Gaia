"""Tests for root CLI plugin discovery."""

from __future__ import annotations

import typer
from typer.testing import CliRunner

from gaia.cli.main import add_missing_research_hint, load_cli_plugins

runner = CliRunner()


class FakeEntryPoint:
    """Small importlib.metadata.EntryPoint stand-in for tests."""

    name = "gaia-research"

    def __init__(self, plugin: object) -> None:
        self._plugin = plugin

    def load(self) -> object:
        return self._plugin


def _root_app() -> typer.Typer:
    app = typer.Typer(no_args_is_help=True)

    @app.command(name="core")
    def core_command() -> None:
        typer.echo("core command")

    return app


def test_load_cli_plugins_registers_callable_entry_point() -> None:
    app = _root_app()

    def register(root_app: typer.Typer) -> None:
        @root_app.command(name="research")
        def research_command() -> None:
            typer.echo("external research plugin")

    loaded = load_cli_plugins(app, entry_points=[FakeEntryPoint(register)])

    assert loaded == ["gaia-research"]
    result = runner.invoke(app, ["research"])
    assert result.exit_code == 0, result.output
    assert "external research plugin" in result.output


def test_missing_research_hint_points_to_external_package() -> None:
    app = _root_app()
    add_missing_research_hint(app)

    result = runner.invoke(app, ["research"])

    assert result.exit_code == 4, result.output
    assert "gaia-research" in result.output
    assert "pip install" in result.output


def test_missing_research_hint_stays_out_of_root_help() -> None:
    app = _root_app()
    add_missing_research_hint(app)

    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0, result.output
    assert "research" not in result.output


def test_missing_research_hint_does_not_override_plugin_command() -> None:
    app = _root_app()

    @app.command(name="research")
    def research_command() -> None:
        typer.echo("plugin wins")

    add_missing_research_hint(app)

    result = runner.invoke(app, ["research"])
    assert result.exit_code == 0, result.output
    assert "plugin wins" in result.output
