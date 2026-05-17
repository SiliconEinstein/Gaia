"""CLI E2E tests for R7 G5 `--background` on equal/contradict/exclusive/observe."""

from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

from gaia.cli.main import app

from .conftest import FixturePackage

pytestmark = pytest.mark.pr_gate

runner = CliRunner()


def _parse(output: str) -> dict[str, object]:
    for line in reversed(output.strip().splitlines()):
        stripped = line.strip()
        if stripped.startswith("{"):
            return json.loads(stripped)
    raise AssertionError(f"no JSON envelope in output: {output!r}")


def _seed_extra_background(gaia_package: FixturePackage) -> None:
    """Add a `setup_note` binding for background reference tests."""
    existing = gaia_package.source_init.read_text()
    gaia_package.source_init.write_text(existing + "\nsetup_note = note('Background setup.')\n")


def test_equal_background_renders(gaia_package: FixturePackage) -> None:
    _seed_extra_background(gaia_package)
    result = runner.invoke(
        app,
        [
            "author",
            "equal",
            "--a",
            "hypothesis",
            "--b",
            "observation",
            "--label",
            "with_bg",
            "--background",
            "setup_note",
            "--target",
            str(gaia_package.root),
            "--no-check",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "background=[setup_note]" in gaia_package.source_init.read_text()


def test_contradict_background_renders(gaia_package: FixturePackage) -> None:
    _seed_extra_background(gaia_package)
    result = runner.invoke(
        app,
        [
            "author",
            "contradict",
            "--a",
            "hypothesis",
            "--b",
            "observation",
            "--label",
            "contra_bg",
            "--background",
            "setup_note",
            "--target",
            str(gaia_package.root),
            "--no-check",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "background=[setup_note]" in gaia_package.source_init.read_text()


def test_exclusive_background_renders(gaia_package: FixturePackage) -> None:
    _seed_extra_background(gaia_package)
    result = runner.invoke(
        app,
        [
            "author",
            "exclusive",
            "--a",
            "hypothesis",
            "--b",
            "observation",
            "--label",
            "exclu_bg",
            "--background",
            "setup_note",
            "--target",
            str(gaia_package.root),
            "--no-check",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "background=[setup_note]" in gaia_package.source_init.read_text()


def test_observe_background_renders(gaia_package: FixturePackage) -> None:
    _seed_extra_background(gaia_package)
    result = runner.invoke(
        app,
        [
            "author",
            "observe",
            "--conclusion",
            "observation",
            "--label",
            "obs_bg",
            "--background",
            "setup_note",
            "--target",
            str(gaia_package.root),
            "--no-check",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "background=[setup_note]" in gaia_package.source_init.read_text()


def test_equal_background_unresolved_reference_exits_3(
    gaia_package: FixturePackage,
) -> None:
    """A non-existent background entry trips reference resolution."""
    result = runner.invoke(
        app,
        [
            "author",
            "equal",
            "--a",
            "hypothesis",
            "--b",
            "observation",
            "--label",
            "bad_bg",
            "--background",
            "no_such_note",
            "--target",
            str(gaia_package.root),
            "--no-check",
        ],
    )
    assert result.exit_code == 3
    envelope = _parse(result.output)
    diagnostics = envelope["diagnostics"]
    assert isinstance(diagnostics, list)
    assert diagnostics[0]["kind"] == "prewrite.reference_unresolved"
