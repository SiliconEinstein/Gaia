"""CLI E2E tests for scaffold defaults + flags."""

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
    """Pyproject template uses requires-python = '>=3.12'."""
    target = tmp_path / "default-gaia"
    result = runner.invoke(app, ["pkg", "scaffold", "--target", str(target), "--no-check"])
    assert result.exit_code == 0, result.output
    pyproject = (target / "pyproject.toml").read_text()
    assert 'requires-python = ">=3.12"' in pyproject


def test_scaffold_default_has_allow_holes(tmp_path: Path) -> None:
    """Pyproject ships [tool.gaia.quality] allow_holes = true."""
    target = tmp_path / "holes-gaia"
    result = runner.invoke(app, ["pkg", "scaffold", "--target", str(target), "--no-check"])
    assert result.exit_code == 0, result.output
    pyproject = (target / "pyproject.toml").read_text()
    assert "[tool.gaia.quality]" in pyproject
    assert "allow_holes = true" in pyproject


def test_scaffold_default_omits_uuid(tmp_path: Path) -> None:
    """Default has no uuid in pyproject."""
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


def test_scaffold_default_uses_minimal_import(tmp_path: Path) -> None:
    """Default __init__.py imports only `claim` and ships empty __all__.

    The placeholder ``hypothesis = claim(...)`` demo statement was removed —
    fresh packages start empty, and author commands populate __all__ as
    statements are added. Wave 2 will make the import dynamic.
    """
    target = tmp_path / "minimal-gaia"
    result = runner.invoke(app, ["pkg", "scaffold", "--target", str(target), "--no-check"])
    assert result.exit_code == 0, result.output
    init_py = (target / "src" / "minimal" / "__init__.py").read_text()
    assert "from gaia.engine.lang import claim" in init_py
    assert "__all__: list[str] = []" in init_py
    # No placeholder demo statement, no wide-import preamble.
    assert "hypothesis = claim(" not in init_py
    assert "from gaia.engine import bayes" not in init_py
    assert "ClaimAtom" not in init_py


def test_scaffold_with_docstring_writes_module_docstring(tmp_path: Path) -> None:
    """`--docstring` writes a triple-quoted module docstring at line 1."""
    target = tmp_path / "docstring-gaia"
    result = runner.invoke(
        app,
        [
            "pkg",
            "scaffold",
            "--target",
            str(target),
            "--docstring",
            "My package docstring.",
            "--no-check",
        ],
    )
    assert result.exit_code == 0, result.output
    init_py = (target / "src" / "docstring" / "__init__.py").read_text()
    assert init_py.startswith('"""My package docstring."""\n')
    envelope = _parse(result.output)
    payload = envelope["payload"]
    assert isinstance(payload, dict)
    assert payload["docstring"] == "My package docstring."


def test_scaffold_without_docstring_writes_no_docstring(tmp_path: Path) -> None:
    """No `--docstring` flag means no module docstring at all."""
    target = tmp_path / "nodoc-gaia"
    result = runner.invoke(app, ["pkg", "scaffold", "--target", str(target), "--no-check"])
    assert result.exit_code == 0, result.output
    init_py = (target / "src" / "nodoc" / "__init__.py").read_text()
    assert not init_py.lstrip().startswith('"""')


def test_scaffold_pyproject_omits_authors(tmp_path: Path) -> None:
    """Scaffold's pyproject.toml never includes `[project] authors`."""
    target = tmp_path / "noauth-gaia"
    result = runner.invoke(app, ["pkg", "scaffold", "--target", str(target), "--no-check"])
    assert result.exit_code == 0, result.output
    pyproject = (target / "pyproject.toml").read_text()
    assert "authors" not in pyproject
