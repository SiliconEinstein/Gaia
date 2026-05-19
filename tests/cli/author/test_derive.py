"""CLI E2E tests for ``gaia author derive``."""

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


def test_derive_happy_path_writes_statement(gaia_package: FixturePackage) -> None:
    """`derive` references a seeded conclusion + premise and writes the call."""
    result = runner.invoke(
        app,
        [
            "author",
            "derive",
            "--conclusion",
            "observation",
            "--given",
            "hypothesis",
            "--dsl-binding-name",
            "warranted",
            "--target",
            str(gaia_package.root),
            "--no-check",
        ],
    )
    assert result.exit_code == 0, result.output
    envelope = _parse(result.output)
    assert envelope["status"] == "ok"
    assert envelope["verb"] == "derive"
    written = gaia_package.source_init.read_text()
    assert "warranted = derive(observation, given=[hypothesis])" in written


def test_derive_with_rationale_and_multiple_given(gaia_package: FixturePackage) -> None:
    """Multi-premise derive renders a list of given identifiers."""
    result = runner.invoke(
        app,
        [
            "author",
            "derive",
            "--conclusion",
            "observation",
            "--given",
            "hypothesis,observation",
            "--dsl-binding-name",
            "doubly_warranted",
            "--rationale",
            "Both premises imply the conclusion.",
            "--target",
            str(gaia_package.root),
            "--no-check",
        ],
    )
    assert result.exit_code == 0, result.output
    written = gaia_package.source_init.read_text()
    assert "given=[hypothesis, observation]" in written
    assert "rationale='Both premises imply the conclusion.'" in written


def test_derive_missing_given_exits_2(gaia_package: FixturePackage) -> None:
    """Empty --given is a syntax error (exit 2)."""
    result = runner.invoke(
        app,
        [
            "author",
            "derive",
            "--conclusion",
            "observation",
            "--given",
            "",
            "--dsl-binding-name",
            "x",
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


def test_derive_unresolved_premise_exits_3(gaia_package: FixturePackage) -> None:
    """Unknown identifier in --given is a reference error."""
    result = runner.invoke(
        app,
        [
            "author",
            "derive",
            "--conclusion",
            "observation",
            "--given",
            "ghost_premise",
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


def test_derive_self_loop_exits_1(gaia_package: FixturePackage) -> None:
    """Label that appears in the verb's reference list trips self-loop (exit 1).

    ``derive`` includes the ``--conclusion`` identifier in the
    ``references`` list (since the conclusion must already be declared
    for the warrant to be well-formed). Setting ``--label`` equal to
    ``--conclusion`` therefore creates a self-loop the structural check
    catches first, ahead of any collision / reference checks.
    """
    result = runner.invoke(
        app,
        [
            "author",
            "derive",
            "--conclusion",
            "observation",
            "--given",
            "hypothesis",
            "--dsl-binding-name",
            "observation",  # conclusion's identifier == label
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


def test_derive_postwrite_check_succeeds(gaia_package: FixturePackage) -> None:
    """Default --check runs post-write and reports counts."""
    result = runner.invoke(
        app,
        [
            "author",
            "derive",
            "--conclusion",
            "observation",
            "--given",
            "hypothesis",
            "--dsl-binding-name",
            "checked_derive",
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


def test_derive_human_mode(gaia_package: FixturePackage) -> None:
    result = runner.invoke(
        app,
        [
            "author",
            "derive",
            "--conclusion",
            "observation",
            "--given",
            "hypothesis",
            "--dsl-binding-name",
            "human_derive",
            "--target",
            str(gaia_package.root),
            "--no-check",
            "--human",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "gaia author derive" in result.output
