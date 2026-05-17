"""CLI E2E tests for R7 G4 ``claim --formula`` (canonical name)."""

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


def test_claim_formula_basic_expression(gaia_package: FixturePackage) -> None:
    """`--formula 'land(ClaimAtom(a), ClaimAtom(b))'` renders as formula= kwarg."""
    result = runner.invoke(
        app,
        [
            "author",
            "claim",
            "Combined claim.",
            "--label",
            "combined",
            "--formula",
            "land(ClaimAtom(hypothesis), ClaimAtom(observation))",
            "--references",
            "hypothesis,observation",
            "--target",
            str(gaia_package.root),
            "--no-check",
        ],
    )
    assert result.exit_code == 0, result.output
    text = gaia_package.source_init.read_text()
    assert "formula=land(ClaimAtom(hypothesis), ClaimAtom(observation))" in text


def test_claim_formula_with_typed_terms(gaia_package: FixturePackage) -> None:
    """G4 sandbox extension allows Variable / Constant / Nat in formula."""
    # Seed a Variable in the package so the reference resolves.
    existing = gaia_package.source_init.read_text()
    gaia_package.source_init.write_text(existing + "\nmy_var = Variable(symbol='x', domain=Nat)\n")
    result = runner.invoke(
        app,
        [
            "author",
            "claim",
            "Variable bound to literal.",
            "--label",
            "var_binding",
            "--formula",
            "equals(my_var, Constant(395, Nat))",
            "--references",
            "my_var",
            "--target",
            str(gaia_package.root),
            "--no-check",
        ],
    )
    assert result.exit_code == 0, result.output
    text = gaia_package.source_init.read_text()
    assert "formula=equals(my_var, Constant(395, Nat))" in text


def test_claim_formula_rejects_attribute_access(gaia_package: FixturePackage) -> None:
    """Sandbox refuses attribute access in --formula."""
    result = runner.invoke(
        app,
        [
            "author",
            "claim",
            "Bad formula.",
            "--label",
            "x",
            "--formula",
            "os.system('rm -rf /')",
            "--target",
            str(gaia_package.root),
            "--no-check",
        ],
    )
    assert result.exit_code == 2
    envelope = _parse(result.output)
    diagnostics = envelope["diagnostics"]
    assert isinstance(diagnostics, list)
    assert diagnostics[0]["kind"] == "prewrite.expr_unsafe"


def test_claim_formula_alias_predicate(gaia_package: FixturePackage) -> None:
    """`--predicate` stays as a backwards-compatible alias for --formula."""
    result = runner.invoke(
        app,
        [
            "author",
            "claim",
            "Backward-compat claim.",
            "--label",
            "backcompat",
            "--predicate",
            "ClaimAtom(hypothesis)",
            "--references",
            "hypothesis",
            "--target",
            str(gaia_package.root),
            "--no-check",
        ],
    )
    assert result.exit_code == 0, result.output


def test_claim_formula_and_predicate_mutex(gaia_package: FixturePackage) -> None:
    """Passing both --formula and --predicate is a syntax error."""
    result = runner.invoke(
        app,
        [
            "author",
            "claim",
            "Conflicting flags.",
            "--label",
            "x",
            "--formula",
            "ClaimAtom(hypothesis)",
            "--predicate",
            "ClaimAtom(hypothesis)",
            "--target",
            str(gaia_package.root),
            "--no-check",
        ],
    )
    assert result.exit_code == 2
