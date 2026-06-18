"""CLI tests for the external ``gaia research`` handoff."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
import typer
from typer.testing import CliRunner

from gaia.cli.main import app, load_cli_plugins

pytestmark = pytest.mark.pr_gate

runner = CliRunner()


class FakeEntryPoint:
    """Small importlib metadata entry point stand-in."""

    name = "research"

    def __init__(self, plugin: object) -> None:
        self._plugin = plugin

    def load(self) -> object:
        return self._plugin


def test_research_group_is_hidden_when_external_plugin_is_missing() -> None:
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0, result.output
    assert "research" not in result.output


def test_research_command_points_to_external_package_when_plugin_is_missing() -> None:
    result = runner.invoke(app, ["research"])

    assert result.exit_code == 4, result.output
    assert "gaia-research" in result.output
    assert "pip install" in result.output


def test_research_subcommands_do_not_fall_back_to_core_workflow() -> None:
    result = runner.invoke(app, ["research", "run", ".", "--topic", "aspirin"])

    assert result.exit_code != 0
    assert "gaia-research" in result.output
    assert "Start a UI-observable research run" not in result.output


def test_root_cli_does_not_import_core_research_workflow() -> None:
    code = """
import json
import sys

import gaia.cli.main

module_names = [
    "gaia.cli.commands.research",
    "gaia.cli.commands.research_orchestrator",
    "gaia.engine.research",
    "gaia.lkm_explorer",
]
print(json.dumps({
    name: name in sys.modules
    for name in module_names
}, sort_keys=True))
"""
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    result = subprocess.run(
        [sys.executable, "-I", "-c", code],
        check=True,
        capture_output=True,
        env=env,
        text=True,
    )

    assert json.loads(result.stdout) == {
        "gaia.cli.commands.research": False,
        "gaia.cli.commands.research_orchestrator": False,
        "gaia.engine.research": False,
        "gaia.lkm_explorer": False,
    }


def test_core_research_workflow_paths_are_removed() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    removed_paths = [
        "gaia/cli/commands/research.py",
        "gaia/cli/commands/research_orchestrator.py",
        "gaia/engine/research",
        "gaia/lkm_explorer",
        "gaia/_skills/gaia-research-loop",
        "gaia/_skills/gaia-evidence-subgraph",
        "gaia/_skills/gaia-scholarly-synthesis",
        "tests/gaia/test_research_report.py",
        "tests/lkm_explorer",
    ]

    for relative in removed_paths:
        assert not (repo_root / relative).exists(), relative


def test_external_research_plugin_can_register_run_surface() -> None:
    snapshot = (list(app.registered_commands), list(app.registered_groups))

    def register(root_app: typer.Typer) -> None:
        research_app = typer.Typer(no_args_is_help=True)

        @research_app.command("run")
        def run_command(pkg: str, topic: str = "") -> None:
            typer.echo(f"external run: {pkg} {topic}")

        root_app.add_typer(research_app, name="research")

    try:
        loaded = load_cli_plugins(app, entry_points=[FakeEntryPoint(register)])

        assert loaded == ["research"]
        result = runner.invoke(app, ["research", "run", ".", "--topic", "aspirin"])
        assert result.exit_code == 0, result.output
        assert "external run: . aspirin" in result.output
    finally:
        commands, groups = snapshot
        app.registered_commands[:] = commands
        app.registered_groups[:] = groups
