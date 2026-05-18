"""CLI E2E tests for ``gaia author note``."""

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
        line = line.strip()
        if line.startswith("{"):
            return json.loads(line)
    raise AssertionError(f"no JSON envelope in output: {output!r}")


def test_note_happy_path(gaia_package: FixturePackage) -> None:
    """A note binds to its label and lands in __init__.py."""
    result = runner.invoke(
        app,
        [
            "author",
            "note",
            "Background context for this domain.",
            "--dsl-binding-name",
            "bg_note",
            "--target",
            str(gaia_package.root),
            "--no-check",
        ],
    )
    assert result.exit_code == 0, result.output
    envelope = _parse(result.output)
    assert envelope["status"] == "ok"
    assert envelope["verb"] == "note"
    written = gaia_package.source_init.read_text()
    assert "bg_note = note('Background context for this domain.')" in written


def test_note_with_title_and_metadata(gaia_package: FixturePackage) -> None:
    """Optional title + metadata kwargs render in the snippet."""
    result = runner.invoke(
        app,
        [
            "author",
            "note",
            "Detailed.",
            "--dsl-binding-name",
            "detailed_note",
            "--title",
            "Detail",
            "--metadata",
            '{"source": "manual"}',
            "--target",
            str(gaia_package.root),
            "--no-check",
        ],
    )
    assert result.exit_code == 0, result.output
    written = gaia_package.source_init.read_text()
    assert "title='Detail'" in written
    assert "'source': 'manual'" in written


def test_note_collision_exits_3(gaia_package: FixturePackage) -> None:
    """Re-using a seeded label trips the collision invariant (exit 3)."""
    result = runner.invoke(
        app,
        [
            "author",
            "note",
            "X.",
            "--dsl-binding-name",
            "hypothesis",
            "--target",
            str(gaia_package.root),
            "--no-check",
        ],
    )
    assert result.exit_code == 3
    envelope = _parse(result.output)
    diagnostics = envelope["diagnostics"]
    assert isinstance(diagnostics, list)
    assert diagnostics[0]["kind"] == "prewrite.collision"


def test_note_bad_metadata_exits_2(gaia_package: FixturePackage) -> None:
    """Invalid --metadata JSON surfaces as a syntax error (exit 2)."""
    result = runner.invoke(
        app,
        [
            "author",
            "note",
            "X.",
            "--dsl-binding-name",
            "bad_note",
            "--metadata",
            "not json",
            "--target",
            str(gaia_package.root),
            "--no-check",
        ],
    )
    assert result.exit_code == 2
    envelope = _parse(result.output)
    diagnostics = envelope["diagnostics"]
    assert isinstance(diagnostics, list)
    assert diagnostics[0]["kind"] == "prewrite.syntax"


def test_note_postwrite_check(gaia_package: FixturePackage) -> None:
    """Default --check runs post-write integration."""
    result = runner.invoke(
        app,
        [
            "author",
            "note",
            "Checked note.",
            "--dsl-binding-name",
            "checked_note",
            "--target",
            str(gaia_package.root),
        ],
    )
    assert result.exit_code == 0, result.output
    envelope = _parse(result.output)
    payload = envelope["payload"]
    assert isinstance(payload, dict)
    check = payload["check"]
    assert isinstance(check, dict)
    assert check["knowledge_count"] >= 3  # 2 seeded + 1 new note


def test_note_human_mode(gaia_package: FixturePackage) -> None:
    result = runner.invoke(
        app,
        [
            "author",
            "note",
            "Human note.",
            "--dsl-binding-name",
            "human_note",
            "--target",
            str(gaia_package.root),
            "--no-check",
            "--human",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "gaia author note" in result.output
