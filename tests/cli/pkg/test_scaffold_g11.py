"""CLI E2E tests for R7 G11 scaffold defaults + new flags."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from gaia.cli.main import app

pytestmark = pytest.mark.pr_gate

runner = CliRunner()


def _parse(output: str) -> dict[str, object]:
    for line in reversed(output.strip().splitlines()):
        stripped = line.strip()
        if stripped.startswith("{"):
            return json.loads(stripped)
    raise AssertionError(f"no JSON envelope in output: {output!r}")


def test_scaffold_default_requires_python_312(tmp_path: Path) -> None:
    """G11 — pyproject template uses requires-python = '>=3.12'."""
    target = tmp_path / "default-gaia"
    result = runner.invoke(app, ["pkg", "scaffold", "--target", str(target), "--no-check"])
    assert result.exit_code == 0, result.output
    pyproject = (target / "pyproject.toml").read_text()
    assert 'requires-python = ">=3.12"' in pyproject


def test_scaffold_default_has_allow_holes(tmp_path: Path) -> None:
    """G11 — pyproject ships [tool.gaia.quality] allow_holes = true."""
    target = tmp_path / "holes-gaia"
    result = runner.invoke(app, ["pkg", "scaffold", "--target", str(target), "--no-check"])
    assert result.exit_code == 0, result.output
    pyproject = (target / "pyproject.toml").read_text()
    assert "[tool.gaia.quality]" in pyproject
    assert "allow_holes = true" in pyproject


def test_scaffold_default_omits_uuid(tmp_path: Path) -> None:
    """G11 — default no uuid in pyproject."""
    target = tmp_path / "no-uuid-gaia"
    result = runner.invoke(app, ["pkg", "scaffold", "--target", str(target), "--no-check"])
    assert result.exit_code == 0, result.output
    pyproject = (target / "pyproject.toml").read_text()
    assert "uuid =" not in pyproject
    envelope = _parse(result.output)
    payload = envelope["payload"]
    assert isinstance(payload, dict)
    assert payload["uuid"] is None


def test_scaffold_with_uuid_flag_emits_uuid(tmp_path: Path) -> None:
    """`--with-uuid` opts in to a generated uuid."""
    target = tmp_path / "with-uuid-gaia"
    result = runner.invoke(
        app,
        ["pkg", "scaffold", "--target", str(target), "--with-uuid", "--no-check"],
    )
    assert result.exit_code == 0, result.output
    pyproject = (target / "pyproject.toml").read_text()
    assert "uuid =" in pyproject
    envelope = _parse(result.output)
    payload = envelope["payload"]
    assert isinstance(payload, dict)
    assert payload["uuid"] is not None


def test_scaffold_default_imports_bayes_and_typed_terms(tmp_path: Path) -> None:
    """G11 — default __init__.py includes bayes + Variable/Constant/domain primitives."""
    target = tmp_path / "fullimport-gaia"
    result = runner.invoke(app, ["pkg", "scaffold", "--target", str(target), "--no-check"])
    assert result.exit_code == 0, result.output
    init_py = (target / "src" / "fullimport" / "__init__.py").read_text()
    assert "from gaia.engine import bayes" in init_py
    for symbol in ("Variable", "Constant", "Nat", "Real", "Bool", "Probability"):
        assert symbol in init_py


def test_scaffold_minimal_imports_uses_sparse_template(tmp_path: Path) -> None:
    """`--minimal-imports` ships only `from gaia.engine.lang import claim`."""
    target = tmp_path / "minimal-gaia"
    result = runner.invoke(
        app,
        ["pkg", "scaffold", "--target", str(target), "--minimal-imports", "--no-check"],
    )
    assert result.exit_code == 0, result.output
    init_py = (target / "src" / "minimal" / "__init__.py").read_text()
    assert "from gaia.engine.lang import claim" in init_py
    assert "ClaimAtom" not in init_py
    assert "bayes" not in init_py
