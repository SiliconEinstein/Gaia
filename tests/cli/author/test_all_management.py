"""CLI E2E tests for ``__all__`` auto-management."""

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


def test_default_author_write_does_not_export(gaia_package: FixturePackage) -> None:
    """Author verbs leave __all__ untouched unless --export is explicit."""
    result = runner.invoke(
        app,
        [
            "author",
            "claim",
            "A new internal claim.",
            "--dsl-binding-name",
            "internal_claim",
            "--target",
            str(gaia_package.root),
            "--no-check",
        ],
    )
    assert result.exit_code == 0, result.output
    envelope = _parse(result.output)
    payload = envelope["payload"]
    assert isinstance(payload, dict)
    assert not payload.get("all_managed", False)

    text = gaia_package.source_init.read_text()
    assert "internal_claim = claim('A new internal claim.')" in text
    all_start = text.find("__all__")
    all_block = text[all_start : text.find("]", all_start) + 1]
    assert "'internal_claim'" not in all_block


def test_explicit_export_grows_all_block_alphabetically(gaia_package: FixturePackage) -> None:
    """Explicit --export inserts new labels into __all__ in alphabetical order."""
    # Fixture seeds __all__ = ["hypothesis", "observation"].
    result = runner.invoke(
        app,
        [
            "author",
            "claim",
            "A new claim that adds itself to __all__.",
            "--dsl-binding-name",
            "added_claim",
            "--export",
            "--target",
            str(gaia_package.root),
            "--no-check",
        ],
    )
    assert result.exit_code == 0, result.output
    envelope = _parse(result.output)
    payload = envelope["payload"]
    assert isinstance(payload, dict)
    assert payload.get("all_managed") is True
    text = gaia_package.source_init.read_text()
    # added_claim should sort to first position alphabetically (a < h < o)
    assert "'added_claim'" in text
    # Verify ordering inside __all__: scan the literal.
    all_start = text.find("__all__")
    assert all_start >= 0
    all_block = text[all_start : text.find("]", all_start) + 1]
    pos_added = all_block.find("'added_claim'")
    pos_hypothesis = all_block.find("'hypothesis'")
    pos_observation = all_block.find("'observation'")
    assert pos_added < pos_hypothesis < pos_observation


def test_all_skipped_when_no_all_block(gaia_package: FixturePackage) -> None:
    """A package without `__all__` is left as-is (no synthesis)."""
    # Strip __all__ from the fixture.
    text = gaia_package.source_init.read_text()
    cut = text.find("__all__")
    gaia_package.source_init.write_text(text[:cut].rstrip() + "\n")

    result = runner.invoke(
        app,
        [
            "author",
            "claim",
            "Claim without an exports list.",
            "--dsl-binding-name",
            "no_all_claim",
            "--target",
            str(gaia_package.root),
            "--no-check",
        ],
    )
    assert result.exit_code == 0, result.output
    envelope = _parse(result.output)
    payload = envelope["payload"]
    assert isinstance(payload, dict)
    # No __all__ in source → cli did not manage it.
    assert not payload.get("all_managed", False)
    new_text = gaia_package.source_init.read_text()
    assert "no_all_claim" in new_text
    # __all__ stays absent — no synthesis. (Compare on top-level
    # assignment, since the prose may otherwise mention it.)
    assert "__all__ = " not in new_text


def test_all_idempotent_when_label_already_present(
    gaia_package: FixturePackage,
) -> None:
    """If label already in __all__, the literal is left untouched (idempotent)."""
    # Seed __all__ with an extra entry but also bind it locally so the
    # pre-write collision check fires the way it would for a real
    # already-bound symbol.
    text = gaia_package.source_init.read_text()
    gaia_package.source_init.write_text(
        text.replace(
            '__all__ = ["hypothesis", "observation"]',
            '__all__ = ["existing_claim", "hypothesis", "observation"]\n'
            "existing_claim = claim('Pre-existing claim.')",
        )
    )
    # The label already exists → pre-write should refuse (collision).
    result = runner.invoke(
        app,
        [
            "author",
            "claim",
            "Trying to redeclare existing_claim.",
            "--dsl-binding-name",
            "existing_claim",
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
