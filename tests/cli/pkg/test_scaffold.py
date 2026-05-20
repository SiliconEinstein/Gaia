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


def test_scaffold_check_skipped_by_default(tmp_path: Path) -> None:
    """Default scaffold skips post-write check (empty pkg cannot pass engine check).

    Wave 1 cleanup: the hypothesis placeholder is gone, so a freshly
    scaffolded package has no declarations — the engine treats that as
    an error. The flag default flipped to `--no-check`; users opt back
    in once author commands have added statements.
    """
    target = tmp_path / "skip-check-gaia"
    result = runner.invoke(app, ["pkg", "scaffold", "--target", str(target)])
    assert result.exit_code == 0, result.output
    envelope = _parse(result.output)
    payload = envelope["payload"]
    assert isinstance(payload, dict)
    # `--no-check` is the default → no check counts in payload.
    assert payload.get("check") == "skipped" or "check" not in payload


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
    # ``os-gaia`` would derive ``os`` as the import name, which collides
    # with the stdlib module; the scaffold refuses so the engine doesn't
    # surface a misleading "not a Gaia package" error downstream.
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
    """`--human` produces non-JSON output prefixed with the correct group.

    Pkg verbs render as ``gaia pkg <verb>``, not the old hardcoded
    ``gaia author <verb>``.
    """
    target = tmp_path / "human-gaia"
    result = runner.invoke(
        app,
        ["pkg", "scaffold", "--target", str(target), "--no-check", "--human"],
    )
    assert result.exit_code == 0, result.output
    assert "gaia pkg scaffold" in result.output


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
