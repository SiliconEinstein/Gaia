"""CLI E2E tests for inline-prose on observe + infer."""

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


# --------------------------------------------------------------------------- #
# observe --observation-prose                                                 #
# --------------------------------------------------------------------------- #


def test_observe_prose_emits_inline_string_literal(
    gaia_package: FixturePackage,
) -> None:
    """`--observation-prose` emits `observe('<prose>', ...)` directly."""
    result = runner.invoke(
        app,
        [
            "author",
            "observe",
            "--observation-prose",
            "The sky is red tonight.",
            "--dsl-binding-name",
            "sky_obs",
            "--target",
            str(gaia_package.root),
            "--no-check",
        ],
    )
    assert result.exit_code == 0, result.output
    envelope = _parse(result.output)
    payload = envelope["payload"]
    assert isinstance(payload, dict)
    assert payload["observation_kind"] == "inline_prose"
    written = gaia_package.source_init.read_text()
    assert "sky_obs = observe('The sky is red tonight.'" in written


def test_observe_prose_mutex_with_conclusion(gaia_package: FixturePackage) -> None:
    """Can't pass both --conclusion and --observation-prose."""
    result = runner.invoke(
        app,
        [
            "author",
            "observe",
            "--conclusion",
            "observation",
            "--observation-prose",
            "Different prose.",
            "--dsl-binding-name",
            "x",
            "--target",
            str(gaia_package.root),
            "--no-check",
        ],
    )
    assert result.exit_code == 2


def test_observe_prose_mutex_with_observation_content(
    gaia_package: FixturePackage,
) -> None:
    """Can't pass both --observation-content and --observation-prose."""
    result = runner.invoke(
        app,
        [
            "author",
            "observe",
            "--observation-content",
            "First version.",
            "--observation-prose",
            "Second version.",
            "--dsl-binding-name",
            "x",
            "--target",
            str(gaia_package.root),
            "--no-check",
        ],
    )
    assert result.exit_code == 2


# --------------------------------------------------------------------------- #
# infer --hypothesis-prose                                                    #
# --------------------------------------------------------------------------- #


def test_infer_prose_wraps_with_claim_at_call_site(
    gaia_package: FixturePackage,
) -> None:
    """`--hypothesis-prose` wraps the prose with claim() inline."""
    result = runner.invoke(
        app,
        [
            "author",
            "infer",
            "--evidence",
            "observation",
            "--hypothesis-prose",
            "The hypothesis is true.",
            "--p-e-given-h",
            "0.8",
            "--dsl-binding-name",
            "evidence_via_prose",
            "--target",
            str(gaia_package.root),
            "--no-check",
        ],
    )
    assert result.exit_code == 0, result.output
    envelope = _parse(result.output)
    payload = envelope["payload"]
    assert isinstance(payload, dict)
    assert payload["hypothesis_kind"] == "inline_prose"
    written = gaia_package.source_init.read_text()
    assert "hypothesis=claim('The hypothesis is true.')" in written


def test_infer_prose_mutex_with_hypothesis(gaia_package: FixturePackage) -> None:
    """--hypothesis and --hypothesis-prose are mutually exclusive."""
    result = runner.invoke(
        app,
        [
            "author",
            "infer",
            "--evidence",
            "observation",
            "--hypothesis",
            "hypothesis",
            "--hypothesis-prose",
            "Conflicting prose.",
            "--p-e-given-h",
            "0.5",
            "--dsl-binding-name",
            "x",
            "--target",
            str(gaia_package.root),
            "--no-check",
        ],
    )
    assert result.exit_code == 2


def test_infer_prose_mutex_with_content(gaia_package: FixturePackage) -> None:
    """--hypothesis-content and --hypothesis-prose are mutually exclusive."""
    result = runner.invoke(
        app,
        [
            "author",
            "infer",
            "--evidence",
            "observation",
            "--hypothesis-content",
            "First.",
            "--hypothesis-prose",
            "Second.",
            "--p-e-given-h",
            "0.5",
            "--dsl-binding-name",
            "x",
            "--target",
            str(gaia_package.root),
            "--no-check",
        ],
    )
    assert result.exit_code == 2
