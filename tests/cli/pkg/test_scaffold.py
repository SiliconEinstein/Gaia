"""CLI E2E tests for ``gaia pkg scaffold``."""

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
        line = line.strip()
        if line.startswith("{"):
            return json.loads(line)
    raise AssertionError(f"no JSON envelope in output: {output!r}")


def test_scaffold_happy_path_empty_dir(tmp_path: Path) -> None:
    """Scaffold lays down pyproject + src/<import>/__init__.py + .gaia/."""
    target = tmp_path / "my-domain-gaia"
    result = runner.invoke(
        app,
        ["pkg", "scaffold", "--target", str(target), "--no-check"],
    )
    assert result.exit_code == 0, result.output
    envelope = _parse(result.output)
    assert envelope["status"] == "ok"
    assert envelope["verb"] == "scaffold"

    payload = envelope["payload"]
    assert isinstance(payload, dict)
    assert payload["pkg_name"] == "my-domain-gaia"
    assert payload["import_name"] == "my_domain"
    assert (target / "pyproject.toml").exists()
    assert (target / "src" / "my_domain" / "__init__.py").exists()
    assert (target / ".gaia").exists()


def test_scaffold_postwrite_check(tmp_path: Path) -> None:
    """Default --check loads the freshly-scaffolded package."""
    target = tmp_path / "checked-gaia"
    result = runner.invoke(app, ["pkg", "scaffold", "--target", str(target)])
    assert result.exit_code == 0, result.output
    envelope = _parse(result.output)
    payload = envelope["payload"]
    assert isinstance(payload, dict)
    check = payload["check"]
    assert isinstance(check, dict)
    assert check["knowledge_count"] == 1  # the template's hypothesis claim


def test_scaffold_refuses_non_empty_dir(tmp_path: Path) -> None:
    """A pre-existing non-empty target is rejected (exit 2 — collision)."""
    target = tmp_path / "existing-gaia"
    target.mkdir()
    (target / "pyproject.toml").write_text("[project]\nname = 'existing-gaia'\n")
    result = runner.invoke(app, ["pkg", "scaffold", "--target", str(target), "--no-check"])
    assert result.exit_code == 2
    envelope = _parse(result.output)
    diagnostics = envelope["diagnostics"]
    assert isinstance(diagnostics, list)
    assert diagnostics[0]["kind"] == "prewrite.collision"


def test_scaffold_rejects_invalid_name(tmp_path: Path) -> None:
    """Name not ending with -gaia is rejected (exit 4)."""
    target = tmp_path / "bad-name"
    result = runner.invoke(app, ["pkg", "scaffold", "--target", str(target), "--no-check"])
    assert result.exit_code == 4
    envelope = _parse(result.output)
    diagnostics = envelope["diagnostics"]
    assert isinstance(diagnostics, list)
    assert diagnostics[0]["kind"] == "prewrite.target_not_gaia_package"


def test_scaffold_rejects_stdlib_import_name_collision(tmp_path: Path) -> None:
    """A package name that derives a stdlib import_name is rejected (exit 4)."""
    target = tmp_path / "os-gaia"
    result = runner.invoke(
        app,
        ["pkg", "scaffold", "--target", str(target), "--no-check"],
    )
    # S7 / audit §E.7 — ``os-gaia`` would derive ``os`` as the import
    # name, which collides with the stdlib module; the scaffold refuses
    # so the engine doesn't surface a misleading "not a Gaia package"
    # error downstream.
    assert result.exit_code == 4
    envelope = _parse(result.output)
    diagnostics = envelope["diagnostics"]
    assert isinstance(diagnostics, list)
    assert diagnostics[0]["kind"] == "prewrite.target_invalid"
    message = diagnostics[0]["message"]
    assert isinstance(message, str)
    assert "stdlib" in message


def test_scaffold_explicit_name_and_namespace(tmp_path: Path) -> None:
    """--name and --namespace override the directory-derived defaults."""
    target = tmp_path / "default-derived"
    result = runner.invoke(
        app,
        [
            "pkg",
            "scaffold",
            "--target",
            str(target),
            "--name",
            "alt-domain-gaia",
            "--namespace",
            "domain.alt",
            "--no-check",
        ],
    )
    assert result.exit_code == 0, result.output
    envelope = _parse(result.output)
    payload = envelope["payload"]
    assert isinstance(payload, dict)
    assert payload["pkg_name"] == "alt-domain-gaia"
    assert payload["namespace"] == "domain.alt"


def test_scaffold_human_mode(tmp_path: Path) -> None:
    """`--human` produces non-JSON output."""
    target = tmp_path / "human-gaia"
    result = runner.invoke(
        app,
        ["pkg", "scaffold", "--target", str(target), "--no-check", "--human"],
    )
    assert result.exit_code == 0, result.output
    assert "gaia author scaffold" in result.output


def test_scaffold_envelope_shape(tmp_path: Path) -> None:
    """Envelope carries every required key with the right types."""
    target = tmp_path / "shape-gaia"
    result = runner.invoke(app, ["pkg", "scaffold", "--target", str(target), "--no-check"])
    assert result.exit_code == 0, result.output
    envelope = _parse(result.output)
    assert set(envelope.keys()) == {
        "status",
        "code",
        "verb",
        "payload",
        "warnings",
        "diagnostics",
    }
    assert envelope["status"] == "ok"
    assert envelope["code"] == 0
    payload = envelope["payload"]
    assert isinstance(payload, dict)
    assert set(payload).issuperset(
        {"pkg_path", "pkg_name", "import_name", "namespace", "uuid", "files_created"}
    )
