"""CLI E2E tests for ``gaia author claim``."""

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


def test_claim_happy_path_writes_statement(gaia_package: FixturePackage) -> None:
    """A new claim binds to its label and the snippet lands in __init__.py."""
    result = runner.invoke(
        app,
        [
            "author",
            "claim",
            "Fresh new claim content.",
            "--dsl-binding-name",
            "freshie",
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
    assert payload["label"] == "freshie"
    assert payload["verb"] == "claim"

    written = gaia_package.source_init.read_text()
    assert "freshie = claim('Fresh new claim content.')" in written


def test_claim_with_prior_and_title(gaia_package: FixturePackage) -> None:
    """Prior + title kwargs render in the generated snippet."""
    result = runner.invoke(
        app,
        [
            "author",
            "claim",
            "Claim with prior.",
            "--dsl-binding-name",
            "with_prior",
            "--title",
            "Prior Claim",
            "--prior",
            "0.7",
            "--target",
            str(gaia_package.root),
            "--no-check",
        ],
    )
    assert result.exit_code == 0, result.output
    written = gaia_package.source_init.read_text()
    assert "with_prior = claim(" in written
    assert "title='Prior Claim'" in written
    assert "prior=0.7" in written


def test_claim_collision_with_seed_label(gaia_package: FixturePackage) -> None:
    """Reusing a seeded label trips the collision invariant (exit 3)."""
    result = runner.invoke(
        app,
        [
            "author",
            "claim",
            "Content.",
            "--dsl-binding-name",
            "hypothesis",  # already bound by the fixture
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


def test_claim_missing_target_exits_4(tmp_path) -> None:
    """A non-existent --target produces a system-IO error."""
    result = runner.invoke(
        app,
        [
            "author",
            "claim",
            "X.",
            "--dsl-binding-name",
            "foo",
            "--target",
            str(tmp_path / "missing"),
            "--no-check",
        ],
    )
    assert result.exit_code == 4
    envelope = _parse(result.output)
    diagnostics = envelope["diagnostics"]
    assert isinstance(diagnostics, list)
    assert diagnostics[0]["kind"] == "prewrite.target_missing"


def test_claim_bad_metadata_json_exits_2(gaia_package: FixturePackage) -> None:
    """Invalid --metadata JSON is a syntax error (exit 2)."""
    result = runner.invoke(
        app,
        [
            "author",
            "claim",
            "X.",
            "--dsl-binding-name",
            "ok",
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


def test_claim_check_runs_postwrite(gaia_package: FixturePackage) -> None:
    """Default --check runs post-write build check and reports counts."""
    result = runner.invoke(
        app,
        [
            "author",
            "claim",
            "Checked claim.",
            "--dsl-binding-name",
            "checked",
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
    # Fixture seeds 2 claims; we just added 1 more.
    assert check["knowledge_count"] >= 3


def test_claim_human_mode(gaia_package: FixturePackage) -> None:
    """`--human` produces non-JSON output mentioning the verb."""
    result = runner.invoke(
        app,
        [
            "author",
            "claim",
            "Human-readable claim.",
            "--dsl-binding-name",
            "humanish",
            "--target",
            str(gaia_package.root),
            "--no-check",
            "--human",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "gaia author claim" in result.output


def test_claim_background_flag_renders_kwarg(gaia_package: FixturePackage) -> None:
    """`--background a,b` populates `background=[a, b]` kwarg.

    ``--references`` (formula-sandbox only) and ``--background``
    (rendered claim kwarg) are independent flags. This test pins the
    explicit-background path: comma-separated identifiers in
    ``--background`` flow through pre-write reference resolution and
    emerge as ``background=[...]`` in the rendered claim.
    """
    result = runner.invoke(
        app,
        [
            "author",
            "claim",
            "Premise-bearing claim.",
            "--dsl-binding-name",
            "with_bg",
            "--background",
            "hypothesis,observation",
            "--target",
            str(gaia_package.root),
            "--no-check",
        ],
    )
    assert result.exit_code == 0, result.output
    written = gaia_package.source_init.read_text()
    assert "with_bg = claim(" in written
    assert "background=[hypothesis, observation]" in written


def test_claim_references_alone_skips_background_kwarg(
    gaia_package: FixturePackage,
) -> None:
    """`--references` alone does not render `background=`.

    Hand-authored mendel uses formula symbols (e.g. Variable identifiers)
    that should be sandbox-whitelisted without showing up in the claim's
    ``background=`` slot. The cli matches: ``--references X,Y --formula
    'equals(X, ...)'`` whitelists X/Y for the sandbox but does NOT emit
    ``background=[X, Y]``.
    """
    # Seed a Variable so the reference resolves.
    existing = gaia_package.source_init.read_text()
    gaia_package.source_init.write_text(existing + "\nmy_var = Variable(symbol='x', domain=Nat)\n")
    result = runner.invoke(
        app,
        [
            "author",
            "claim",
            "Formula claim with sandbox-only refs.",
            "--dsl-binding-name",
            "formula_only",
            "--references",
            "my_var",
            "--formula",
            "equals(my_var, Constant(395, Nat))",
            "--target",
            str(gaia_package.root),
            "--no-check",
        ],
    )
    assert result.exit_code == 0, result.output
    written = gaia_package.source_init.read_text()
    assert "formula_only = claim(" in written
    assert "formula=equals(my_var, Constant(395, Nat))" in written
    # The critical invariant: --references on its own does NOT render
    # a background= kwarg. Hand-authored matches this shape.
    formula_only_line = next(
        line for line in written.splitlines() if line.startswith("formula_only = claim(")
    )
    assert "background=" not in formula_only_line


def test_claim_references_and_background_combined(gaia_package: FixturePackage) -> None:
    """`--references` + `--background` are independent.

    Mixed usage: the formula can reference Variables (sandbox-only) while
    Knowledge-level premises pass through ``--background``. The rendered
    ``background=`` lists ONLY the ``--background`` identifiers, not the
    ``--references`` ones.
    """
    existing = gaia_package.source_init.read_text()
    gaia_package.source_init.write_text(existing + "\nmy_var = Variable(symbol='x', domain=Nat)\n")
    result = runner.invoke(
        app,
        [
            "author",
            "claim",
            "Mixed-mode claim.",
            "--dsl-binding-name",
            "mixed",
            "--references",
            "my_var",
            "--background",
            "hypothesis",
            "--formula",
            "equals(my_var, Constant(1, Nat))",
            "--target",
            str(gaia_package.root),
            "--no-check",
        ],
    )
    assert result.exit_code == 0, result.output
    written = gaia_package.source_init.read_text()
    mixed_line = next(line for line in written.splitlines() if line.startswith("mixed = claim("))
    assert "formula=equals(my_var, Constant(1, Nat))" in mixed_line
    # Background lists only the --background identifier, not the
    # sandbox-only --references identifier.
    assert "background=[hypothesis]" in mixed_line
    assert "my_var" not in mixed_line.split("background=[", 1)[1].split("]", 1)[0]
