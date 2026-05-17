"""CLI E2E tests for R7 G8 — deprecated_ref narrowing to call positions.

R3-R6 walked every ast.Name in the proposed snippet, which flagged
``context = note(...)`` because ``context`` happens to match a
deprecated note alias. R7 narrows the scan to ``ast.Call`` ``node.func``
positions plus the reference-list (so `--given context` still warns).
"""

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


def test_g8_binding_named_context_no_warning(
    gaia_package: FixturePackage,
) -> None:
    """`gaia author note ... --label context` does NOT trip deprecated_ref.

    The label is a binding name; the deprecation is about *calling*
    ``context()`` as a DSL factory. Since note() is the call here (with
    the prose as content), the scan should not fire.
    """
    result = runner.invoke(
        app,
        [
            "author",
            "note",
            "A preamble note historically labeled `context`.",
            "--label",
            "context",
            "--target",
            str(gaia_package.root),
            "--no-check",
        ],
    )
    assert result.exit_code == 0, result.output
    envelope = _parse(result.output)
    diagnostics = envelope["diagnostics"]
    assert isinstance(diagnostics, list)
    # No deprecated_ref warning should fire for the binding name.
    for diag in diagnostics:
        assert isinstance(diag, dict)
        assert diag.get("kind") != "prewrite.deprecated_ref", diag


def test_g8_reference_still_warns(gaia_package: FixturePackage) -> None:
    """`--given context` (where context is a local binding) still warns.

    The reference-list scan is preserved post-G8 because the agent is
    *naming* the deprecated factory on the command line.
    """
    existing = gaia_package.source_init.read_text()
    gaia_package.source_init.write_text(existing + "\ncontext = note('legacy alias')\n")
    result = runner.invoke(
        app,
        [
            "author",
            "derive",
            "--conclusion",
            "observation",
            "--given",
            "context",
            "--label",
            "via_context",
            "--target",
            str(gaia_package.root),
            "--no-check",
        ],
    )
    assert result.exit_code == 0, result.output
    envelope = _parse(result.output)
    warnings = envelope["warnings"]
    assert isinstance(warnings, list)
    assert any(isinstance(w, str) and "context" in w for w in warnings)
