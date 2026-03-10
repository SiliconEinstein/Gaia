# tests/cli/test_lang_cli.py
from pathlib import Path

import pytest

from cli.commands.lang import execute_cmd, inspect_cmd, load_cmd, run_cmd, validate_cmd

FIXTURE_DIR = (
    Path(__file__).parents[1] / "fixtures" / "gaia_language_packages" / "galileo_falling_bodies"
)


async def test_load_cmd(capsys):
    await load_cmd(str(FIXTURE_DIR))
    captured = capsys.readouterr()
    assert "galileo_falling_bodies" in captured.out
    assert "5 modules" in captured.out


async def test_run_cmd(capsys):
    await run_cmd(str(FIXTURE_DIR))
    captured = capsys.readouterr()
    assert "galileo_falling_bodies" in captured.out
    assert "Variables: 14" in captured.out
    assert "Factors: 11" in captured.out
    assert "Beliefs after BP:" in captured.out
    # Check at least one specific belief line with prior -> belief format
    assert "heavier_falls_faster: prior=0.7" in captured.out
    assert "vacuum_prediction: prior=0.5" in captured.out
    assert "tied_balls_contradiction: prior=0.6" in captured.out


async def test_execute_cmd(capsys):
    await execute_cmd(str(FIXTURE_DIR))
    captured = capsys.readouterr()
    assert "galileo_falling_bodies" in captured.out
    assert "Executed with 5 modules" in captured.out


async def test_inspect_cmd(capsys):
    await inspect_cmd(str(FIXTURE_DIR))
    captured = capsys.readouterr()
    assert "Factor Graph:" in captured.out
    assert "Variables: 14" in captured.out
    assert "Factors: 11" in captured.out
    assert "contradiction_chain.step_2" in captured.out
    assert "tied_balls_contradiction.constraint" in captured.out


async def test_validate_cmd(capsys):
    await validate_cmd(str(FIXTURE_DIR))
    captured = capsys.readouterr()
    assert "Package is valid" in captured.out
    assert "All references resolved" in captured.out


async def test_validate_cmd_invalid_path(capsys):
    await validate_cmd("/nonexistent/path")
    captured = capsys.readouterr()
    assert "Validation failed" in captured.out


# ── Inline / error path tests ─────────────────────────────────


async def test_load_cmd_invalid_path():
    """load_cmd with a nonexistent path raises FileNotFoundError."""
    with pytest.raises(FileNotFoundError):
        await load_cmd("/nonexistent/lang/package/path")


async def test_run_cmd_invalid_path():
    """run_cmd with a nonexistent path raises FileNotFoundError."""
    with pytest.raises(FileNotFoundError):
        await run_cmd("/nonexistent/lang/package/path")


async def test_execute_cmd_invalid_path():
    """execute_cmd with a nonexistent path raises FileNotFoundError."""
    with pytest.raises(FileNotFoundError):
        await execute_cmd("/nonexistent/lang/package/path")


async def test_inspect_cmd_invalid_path():
    """inspect_cmd with a nonexistent path raises FileNotFoundError."""
    with pytest.raises(FileNotFoundError):
        await inspect_cmd("/nonexistent/lang/package/path")
