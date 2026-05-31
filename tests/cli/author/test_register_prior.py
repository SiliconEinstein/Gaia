"""CLI E2E tests for ``gaia author register-prior``."""

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


def test_register_prior_happy_path(gaia_package: FixturePackage) -> None:
    """register_prior writes a bare expression statement (no LHS)."""
    result = runner.invoke(
        app,
        [
            "author",
            "register-prior",
            "--claim",
            "hypothesis",
            "--value",
            "0.7",
            "--justification",
            "Prior from expert.",
            "--target",
            str(gaia_package.root),
            "--no-check",
        ],
    )
    assert result.exit_code == 0, result.output
    envelope = _parse(result.output)
    assert envelope["status"] == "ok"
    payload = envelope["payload"]
    assert isinstance(payload, dict)
    # No label binding — register_prior() returns None.
    assert payload["label"] is None

    written = gaia_package.source_init.read_text()
    assert "register_prior(hypothesis, value=0.7" in written
    assert "justification='Prior from expert.'" in written
    # Default source_id is omitted from the rendered call when caller
    # didn't explicitly pass --source-id. Engine fills in the default
    # at load time.
    assert "source_id=" not in written


def test_register_prior_custom_source_id(gaia_package: FixturePackage) -> None:
    """--source-id renders the named source."""
    result = runner.invoke(
        app,
        [
            "author",
            "register-prior",
            "--claim",
            "hypothesis",
            "--value",
            "0.55",
            "--justification",
            "Calibration result.",
            "--source-id",
            "calibration_2026q2",
            "--target",
            str(gaia_package.root),
            "--no-check",
        ],
    )
    assert result.exit_code == 0, result.output
    written = gaia_package.source_init.read_text()
    assert "source_id='calibration_2026q2'" in written


def test_register_prior_explicit_default_source_id_still_emits(
    gaia_package: FixturePackage,
) -> None:
    """Explicit ``--source-id user_priors`` still renders the kwarg.

    Omission of ``source_id=`` is driven by *absence* of the
    ``--source-id`` flag, not by value comparison. A user who explicitly
    types ``--source-id user_priors`` gets the kwarg rendered (no silent
    drop based on value matching the engine default).
    """
    result = runner.invoke(
        app,
        [
            "author",
            "register-prior",
            "--claim",
            "hypothesis",
            "--value",
            "0.5",
            "--justification",
            "Explicit default.",
            "--source-id",
            "user_priors",
            "--target",
            str(gaia_package.root),
            "--no-check",
        ],
    )
    assert result.exit_code == 0, result.output
    written = gaia_package.source_init.read_text()
    assert "source_id='user_priors'" in written


def test_register_prior_empty_justification_exits_2(gaia_package: FixturePackage) -> None:
    """Empty --justification is rejected (matches engine behavior)."""
    result = runner.invoke(
        app,
        [
            "author",
            "register-prior",
            "--claim",
            "hypothesis",
            "--value",
            "0.5",
            "--justification",
            "   ",
            "--target",
            str(gaia_package.root),
            "--no-check",
        ],
    )
    assert result.exit_code == 2


def test_register_prior_unresolved_claim_exits_3(gaia_package: FixturePackage) -> None:
    result = runner.invoke(
        app,
        [
            "author",
            "register-prior",
            "--claim",
            "ghost_claim",
            "--value",
            "0.5",
            "--justification",
            "Ghostly.",
            "--target",
            str(gaia_package.root),
            "--no-check",
        ],
    )
    assert result.exit_code == 3


def test_register_prior_statement_label_comment(gaia_package: FixturePackage) -> None:
    """--statement-label renders a trailing # comment."""
    result = runner.invoke(
        app,
        [
            "author",
            "register-prior",
            "--claim",
            "hypothesis",
            "--value",
            "0.5",
            "--justification",
            "Neutral.",
            "--statement-label",
            "prior_for_hypothesis",
            "--target",
            str(gaia_package.root),
            "--no-check",
        ],
    )
    assert result.exit_code == 0, result.output
    written = gaia_package.source_init.read_text()
    assert "# prior_for_hypothesis" in written


def test_register_prior_human_mode(gaia_package: FixturePackage) -> None:
    result = runner.invoke(
        app,
        [
            "author",
            "register-prior",
            "--claim",
            "hypothesis",
            "--value",
            "0.5",
            "--justification",
            "Neutral.",
            "--target",
            str(gaia_package.root),
            "--no-check",
            "--human",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "gaia author register_prior" in result.output
