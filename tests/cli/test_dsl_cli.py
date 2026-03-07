# tests/cli/test_dsl_cli.py
from pathlib import Path

from cli.commands.dsl import load_cmd, run_cmd

FIXTURE_DIR = Path(__file__).parents[1] / "fixtures" / "dsl_packages" / "galileo_falling_bodies"


def test_load_cmd(capsys):
    load_cmd(str(FIXTURE_DIR))
    captured = capsys.readouterr()
    assert "galileo_falling_bodies" in captured.out
    assert "5 modules" in captured.out


def test_run_cmd(capsys):
    run_cmd(str(FIXTURE_DIR))
    captured = capsys.readouterr()
    assert "galileo_falling_bodies" in captured.out
    assert "beliefs" in captured.out.lower() or "belief" in captured.out.lower()
