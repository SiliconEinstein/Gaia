"""Regression tests for the v0.5 Galileo example package."""

from __future__ import annotations

import shutil
import json
from pathlib import Path

from typer.testing import CliRunner

from gaia.cli.main import app


runner = CliRunner()


def _copy_galileo_example(tmp_path: Path) -> Path:
    repo_root = Path(__file__).resolve().parents[1]
    source = repo_root / "examples" / "galileo-v0-5-gaia"
    package = tmp_path / "galileo-v0-5-gaia"
    shutil.copytree(source, package, ignore=shutil.ignore_patterns(".gaia", "__pycache__"))
    return package


def test_vacuum_setup_stays_background_not_independent_claim(tmp_path: Path):
    package = _copy_galileo_example(tmp_path)

    result = runner.invoke(app, ["compile", str(package)])
    assert result.exit_code == 0, result.output

    ir = (package / ".gaia" / "ir.json").read_text()
    assert "vacuum_has_no_medium" not in ir
    assert "In vacuum, there is no resisting medium." not in ir
    assert "vacuum_setup" in ir

    compiled = json.loads(ir)
    strategy = next(
        s
        for s in compiled["strategies"]
        if s["conclusion"] == "example:galileo_v0_5::vacuum_equal_fall_prediction"
    )
    assert strategy["premises"] == ["example:galileo_v0_5::medium_model"]
    assert strategy["background"] == ["example:galileo_v0_5::vacuum_setup"]
