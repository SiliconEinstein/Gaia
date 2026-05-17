"""CLI E2E tests for ``gaia author decompose``."""

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


def _seed_extra_atoms(gaia_package: FixturePackage) -> None:
    """Add two atomic claims plus a composite so decompose has real parts."""
    existing = gaia_package.source_init.read_text()
    gaia_package.source_init.write_text(
        existing
        + "\natom_a = claim('Atom A.')\n"
        + "atom_b = claim('Atom B.')\n"
        + "composite = claim('Composite.')\n"
    )


def test_decompose_happy_path_template_and(gaia_package: FixturePackage) -> None:
    """--formula-template=and renders a ``land(ClaimAtom(...), ...)`` formula."""
    _seed_extra_atoms(gaia_package)
    result = runner.invoke(
        app,
        [
            "author",
            "decompose",
            "--whole",
            "composite",
            "--parts",
            "atom_a,atom_b",
            "--formula-template",
            "and",
            "--label",
            "split_composite",
            "--target",
            str(gaia_package.root),
            "--no-check",
        ],
    )
    assert result.exit_code == 0, result.output
    written = gaia_package.source_init.read_text()
    assert "split_composite = decompose(composite" in written
    assert "parts=[atom_a, atom_b]" in written
    assert "formula=land(ClaimAtom(atom_a), ClaimAtom(atom_b))" in written


def test_decompose_template_atom_single_part(gaia_package: FixturePackage) -> None:
    """--formula-template=atom requires exactly one --parts entry."""
    _seed_extra_atoms(gaia_package)
    result = runner.invoke(
        app,
        [
            "author",
            "decompose",
            "--whole",
            "composite",
            "--parts",
            "atom_a",
            "--formula-template",
            "atom",
            "--label",
            "single_split",
            "--target",
            str(gaia_package.root),
            "--no-check",
        ],
    )
    assert result.exit_code == 0, result.output
    written = gaia_package.source_init.read_text()
    assert "formula=ClaimAtom(atom_a)" in written


def test_decompose_formula_expr_raw(gaia_package: FixturePackage) -> None:
    """--formula-expr forwards a raw Python expression verbatim."""
    _seed_extra_atoms(gaia_package)
    result = runner.invoke(
        app,
        [
            "author",
            "decompose",
            "--whole",
            "composite",
            "--parts",
            "atom_a,atom_b",
            "--formula-expr",
            "iff(ClaimAtom(atom_a), ClaimAtom(atom_b))",
            "--label",
            "raw_split",
            "--target",
            str(gaia_package.root),
            "--no-check",
        ],
    )
    assert result.exit_code == 0, result.output
    written = gaia_package.source_init.read_text()
    assert "formula=iff(ClaimAtom(atom_a), ClaimAtom(atom_b))" in written


def test_decompose_requires_one_formula_source(gaia_package: FixturePackage) -> None:
    """Neither --formula-template nor --formula-expr → syntax error (exit 2)."""
    _seed_extra_atoms(gaia_package)
    result = runner.invoke(
        app,
        [
            "author",
            "decompose",
            "--whole",
            "composite",
            "--parts",
            "atom_a,atom_b",
            "--label",
            "missing_formula",
            "--target",
            str(gaia_package.root),
            "--no-check",
        ],
    )
    assert result.exit_code == 2


def test_decompose_template_and_expr_mutually_exclusive(gaia_package: FixturePackage) -> None:
    _seed_extra_atoms(gaia_package)
    result = runner.invoke(
        app,
        [
            "author",
            "decompose",
            "--whole",
            "composite",
            "--parts",
            "atom_a,atom_b",
            "--formula-template",
            "and",
            "--formula-expr",
            "ClaimAtom(atom_a)",
            "--label",
            "both_formula",
            "--target",
            str(gaia_package.root),
            "--no-check",
        ],
    )
    assert result.exit_code == 2


def test_decompose_unknown_template_exits_2(gaia_package: FixturePackage) -> None:
    _seed_extra_atoms(gaia_package)
    result = runner.invoke(
        app,
        [
            "author",
            "decompose",
            "--whole",
            "composite",
            "--parts",
            "atom_a,atom_b",
            "--formula-template",
            "xor",  # not in the allowed set
            "--label",
            "bad_template",
            "--target",
            str(gaia_package.root),
            "--no-check",
        ],
    )
    assert result.exit_code == 2


def test_decompose_unresolved_whole_exits_3(gaia_package: FixturePackage) -> None:
    _seed_extra_atoms(gaia_package)
    result = runner.invoke(
        app,
        [
            "author",
            "decompose",
            "--whole",
            "ghost_composite",
            "--parts",
            "atom_a,atom_b",
            "--formula-template",
            "and",
            "--label",
            "ghost_split",
            "--target",
            str(gaia_package.root),
            "--no-check",
        ],
    )
    assert result.exit_code == 3


def test_decompose_human_mode(gaia_package: FixturePackage) -> None:
    _seed_extra_atoms(gaia_package)
    result = runner.invoke(
        app,
        [
            "author",
            "decompose",
            "--whole",
            "composite",
            "--parts",
            "atom_a,atom_b",
            "--formula-template",
            "and",
            "--label",
            "human_split",
            "--target",
            str(gaia_package.root),
            "--no-check",
            "--human",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "gaia author decompose" in result.output
