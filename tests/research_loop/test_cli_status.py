from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from gaia.research_loop.cli import app


def test_status_initializes_empty_loop(tmp_path: Path) -> None:
    runner = CliRunner()

    result = runner.invoke(app, ["status", str(tmp_path), "--json"])

    assert result.exit_code == 0
    assert '"phase": "idle"' in result.stdout
    assert (tmp_path / ".gaia" / "research_loop" / "state.json").exists()


def test_status_human_output_names_next_command(tmp_path: Path) -> None:
    runner = CliRunner()

    result = runner.invoke(app, ["status", str(tmp_path)])

    assert result.exit_code == 0
    assert "Research loop: idle" in result.stdout
    assert "Next: gaia-research-loop next" in result.stdout
