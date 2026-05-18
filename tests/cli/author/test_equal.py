"""CLI E2E tests for ``gaia author equal``."""

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


def test_equal_happy_path_writes_statement(gaia_package: FixturePackage) -> None:
    """Equal references seeded labels and writes an `equal(...)` call."""
    result = runner.invoke(
        app,
        [
            "author",
            "equal",
            "--a",
            "hypothesis",
            "--b",
            "observation",
            "--dsl-binding-name",
            "are_equal",
            "--target",
            str(gaia_package.root),
            "--no-check",
        ],
    )
    assert result.exit_code == 0, result.output
    envelope = _parse(result.output)
    assert envelope["status"] == "ok"
    assert envelope["verb"] == "equal"
    written = gaia_package.source_init.read_text()
    assert "are_equal = equal(hypothesis, observation)" in written


def test_equal_with_rationale_and_metadata(gaia_package: FixturePackage) -> None:
    """Optional rationale and metadata kwargs render correctly."""
    result = runner.invoke(
        app,
        [
            "author",
            "equal",
            "--a",
            "hypothesis",
            "--b",
            "observation",
            "--dsl-binding-name",
            "are_equal",
            "--rationale",
            "Stated in two ways.",
            "--metadata",
            '{"source": "manual"}',
            "--target",
            str(gaia_package.root),
            "--no-check",
        ],
    )
    assert result.exit_code == 0, result.output
    written = gaia_package.source_init.read_text()
    assert "rationale='Stated in two ways.'" in written
    assert "metadata=" in written
    assert "'source': 'manual'" in written


def test_equal_unresolved_reference_exits_3(gaia_package: FixturePackage) -> None:
    """Referencing a non-existent label fails with exit code 3."""
    result = runner.invoke(
        app,
        [
            "author",
            "equal",
            "--a",
            "hypothesis",
            "--b",
            "nonexistent",
            "--dsl-binding-name",
            "x",
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


def test_equal_collision_with_seed(gaia_package: FixturePackage) -> None:
    """Re-using a seeded label (not in references list) is a collision (exit 3).

    Both seeded labels (``hypothesis`` / ``observation``) are used in
    ``--a`` / ``--b``, so re-using either as ``--label`` trips
    self-loop, not collision. We seed a separate symbol via the
    fixture's __init__.py — but to keep the fixture minimal we extend
    __init__.py with an extra binding via a sub-fixture instead.
    """
    # Add an extra non-reference symbol to the package so we can collide on it
    # without being part of the references list.
    existing = gaia_package.source_init.read_text()
    gaia_package.source_init.write_text(
        existing
        + "\nextra_symbol = claim('Extra symbol for collision testing.')\n"
        + '__all__ = ["hypothesis", "observation", "extra_symbol"]\n'
    )
    result = runner.invoke(
        app,
        [
            "author",
            "equal",
            "--a",
            "hypothesis",
            "--b",
            "observation",
            "--dsl-binding-name",
            "extra_symbol",  # collides, not in --a / --b
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


def test_equal_self_loop_exits_1(gaia_package: FixturePackage) -> None:
    """Setting --label equal to one of --a / --b is a self-loop (exit 1).

    ``equal`` puts both ``a`` and ``b`` into the references list. The
    structural check runs ahead of reference resolution so the self-loop
    fires as ``prewrite.self_loop`` (exit 1), not as
    ``prewrite.reference_unresolved`` or ``prewrite.collision``.
    """
    result = runner.invoke(
        app,
        [
            "author",
            "equal",
            "--a",
            "hypothesis",
            "--b",
            "observation",
            "--dsl-binding-name",
            "hypothesis",  # collision with --a → self-loop wins
            "--target",
            str(gaia_package.root),
            "--no-check",
        ],
    )
    assert result.exit_code == 1
    envelope = _parse(result.output)
    diagnostics = envelope["diagnostics"]
    assert isinstance(diagnostics, list)
    assert diagnostics[0]["kind"] == "prewrite.self_loop"


def test_equal_postwrite_check_succeeds(gaia_package: FixturePackage) -> None:
    """Default --check runs post-write and reports knowledge counts."""
    result = runner.invoke(
        app,
        [
            "author",
            "equal",
            "--a",
            "hypothesis",
            "--b",
            "observation",
            "--dsl-binding-name",
            "checked_equal",
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
    assert check["knowledge_count"] >= 2


def test_equal_human_mode(gaia_package: FixturePackage) -> None:
    result = runner.invoke(
        app,
        [
            "author",
            "equal",
            "--a",
            "hypothesis",
            "--b",
            "observation",
            "--dsl-binding-name",
            "human_equal",
            "--target",
            str(gaia_package.root),
            "--no-check",
            "--human",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "gaia author equal" in result.output
