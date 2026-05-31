"""CLI E2E tests for ``gaia author question``."""

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


def test_question_happy_path(gaia_package: FixturePackage) -> None:
    """A question binds to its label and lands in __init__.py."""
    result = runner.invoke(
        app,
        [
            "author",
            "question",
            "Does X cause Y?",
            "--dsl-binding-name",
            "rq",
            "--target",
            str(gaia_package.root),
            "--no-check",
        ],
    )
    assert result.exit_code == 0, result.output
    envelope = _parse(result.output)
    assert envelope["status"] == "ok"
    written = gaia_package.source_init.read_text()
    assert "rq = question('Does X cause Y?')" in written


def test_question_with_targets(gaia_package: FixturePackage) -> None:
    """--targets renders as a list of identifier references."""
    result = runner.invoke(
        app,
        [
            "author",
            "question",
            "Why?",
            "--dsl-binding-name",
            "why_rq",
            "--targets",
            "hypothesis,observation",
            "--target",
            str(gaia_package.root),
            "--no-check",
        ],
    )
    assert result.exit_code == 0, result.output
    written = gaia_package.source_init.read_text()
    assert "targets=[hypothesis, observation]" in written


def test_question_unresolved_target_exits_3(gaia_package: FixturePackage) -> None:
    """--targets includes a name that doesn't resolve in module scope."""
    result = runner.invoke(
        app,
        [
            "author",
            "question",
            "What?",
            "--dsl-binding-name",
            "what_rq",
            "--targets",
            "nonexistent_claim",
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


def test_question_postwrite_check(gaia_package: FixturePackage) -> None:
    """Default --check loads the package."""
    result = runner.invoke(
        app,
        [
            "author",
            "question",
            "Checked?",
            "--dsl-binding-name",
            "checked_rq",
            "--target",
            str(gaia_package.root),
        ],
    )
    assert result.exit_code == 0, result.output


def test_question_human_mode(gaia_package: FixturePackage) -> None:
    result = runner.invoke(
        app,
        [
            "author",
            "question",
            "Human-readable?",
            "--dsl-binding-name",
            "human_rq",
            "--target",
            str(gaia_package.root),
            "--no-check",
            "--human",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "gaia author question" in result.output
