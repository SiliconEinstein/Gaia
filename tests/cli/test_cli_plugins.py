"""Tests for root CLI plugin discovery."""

from __future__ import annotations

import typer
from pytest import MonkeyPatch
from typer.testing import CliRunner

import gaia.cli.main as cli_main
from gaia.cli.main import add_missing_research_hint, load_cli_plugins

runner = CliRunner()


class FakeEntryPoint:
    """Small importlib.metadata.EntryPoint stand-in for tests."""

    def __init__(
        self,
        plugin: object = None,
        *,
        name: str = "gaia-research",
        load_error: Exception | None = None,
    ) -> None:
        self.name = name
        self._plugin = plugin
        self._load_error = load_error

    def load(self) -> object:
        if self._load_error is not None:
            raise self._load_error
        return self._plugin


class FakeSelectableEntryPoints(list[FakeEntryPoint]):
    """Small importlib.metadata entry-points collection stand-in."""

    def select(self, *, group: str) -> list[FakeEntryPoint]:
        assert group == "gaia.cli_plugins"
        return list(self)


def _root_app() -> typer.Typer:
    app = typer.Typer(no_args_is_help=True)

    @app.command(name="core")
    def core_command() -> None:
        typer.echo("core command")

    @app.command(name="status")
    def status_command() -> None:
        typer.echo("status command")

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


def test_load_cli_plugins_uses_metadata_discovery(monkeypatch: MonkeyPatch) -> None:
    app = _root_app()

    def register(root_app: typer.Typer) -> None:
        @root_app.command(name="research")
        def research_command() -> None:
            typer.echo("discovered research plugin")

    monkeypatch.setattr(
        cli_main.metadata,
        "entry_points",
        lambda: FakeSelectableEntryPoints([FakeEntryPoint(register)]),
    )

    loaded = load_cli_plugins(app)

    assert loaded == ["gaia-research"]
    result = runner.invoke(app, ["research"])
    assert result.exit_code == 0, result.output
    assert "discovered research plugin" in result.output


def test_load_cli_plugins_skips_broken_entry_points() -> None:
    app = _root_app()

    def register(root_app: typer.Typer) -> None:
        @root_app.command(name="research")
        def research_command() -> None:
            typer.echo("healthy plugin")

    loaded = load_cli_plugins(
        app,
        entry_points=[
            FakeEntryPoint(name="broken", load_error=RuntimeError("missing optional dep")),
            FakeEntryPoint(register),
        ],
    )

    assert loaded == ["gaia-research"]
    result = runner.invoke(app, ["core"])
    assert result.exit_code == 0, result.output
    assert "core command" in result.output


def test_load_cli_plugins_rolls_back_registration_failure() -> None:
    app = _root_app()

    def broken_register(root_app: typer.Typer) -> None:
        @root_app.command(name="temporary")
        def temporary_command() -> None:
            typer.echo("partial registration")

        raise RuntimeError("registration failed")

    loaded = load_cli_plugins(app, entry_points=[FakeEntryPoint(broken_register)])

    assert loaded == []
    help_result = runner.invoke(app, ["--help"])
    assert help_result.exit_code == 0, help_result.output
    assert "temporary" not in help_result.output


def test_load_cli_plugins_rejects_top_level_name_conflicts() -> None:
    app = _root_app()

    def register(root_app: typer.Typer) -> None:
        @root_app.command(name="core")
        def plugin_core_command() -> None:
            typer.echo("plugin shadow")

    loaded = load_cli_plugins(app, entry_points=[FakeEntryPoint(register)])

    assert loaded == []
    result = runner.invoke(app, ["core"])
    assert result.exit_code == 0, result.output
    assert "core command" in result.output
    assert "plugin shadow" not in result.output


def test_missing_research_hint_points_to_external_package() -> None:
    app = _root_app()
    add_missing_research_hint(app)

    result = runner.invoke(app, ["research"])

    assert result.exit_code == 4, result.output
    assert "gaia-research" in result.output
    assert "pip install" in result.output


def test_missing_research_hint_help_points_to_external_package() -> None:
    app = _root_app()
    add_missing_research_hint(app)

    result = runner.invoke(app, ["research", "--help"])

    assert result.exit_code == 0, result.output
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
