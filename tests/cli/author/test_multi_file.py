"""CLI E2E tests for R7 G1 multi-file `--file` routing.

Covers:

* ``--file <relative>`` directs the writer to a sibling Python module.
* Non-existent target file is rejected with ``prewrite.target_invalid``.
* Absolute paths / ``..`` traversals are rejected.
* ``register-prior --file priors.py`` auto-inserts the cross-file
  ``from <pkg> import <claim>`` line when missing.
* ``gaia pkg add-module`` scaffolds a sibling module.
"""

from __future__ import annotations

import json
from pathlib import Path

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


def test_add_module_creates_sibling_file(gaia_package: FixturePackage) -> None:
    """`gaia pkg add-module` lays down `src/<pkg>/<name>.py` with __all__."""
    result = runner.invoke(
        app,
        [
            "pkg",
            "add-module",
            "--name",
            "priors",
            "--target",
            str(gaia_package.root),
        ],
    )
    assert result.exit_code == 0, result.output
    envelope = _parse(result.output)
    assert envelope["status"] == "ok"
    sibling = Path(gaia_package.root) / "src" / gaia_package.import_name / "priors.py"
    assert sibling.exists()
    text = sibling.read_text()
    assert "__all__" in text


def test_add_module_with_imports_seeds_dsl(gaia_package: FixturePackage) -> None:
    """`--imports register_prior` seeds the DSL import in the new file."""
    result = runner.invoke(
        app,
        [
            "pkg",
            "add-module",
            "--name",
            "priors",
            "--imports",
            "register_prior",
            "--target",
            str(gaia_package.root),
        ],
    )
    assert result.exit_code == 0, result.output
    sibling = Path(gaia_package.root) / "src" / gaia_package.import_name / "priors.py"
    text = sibling.read_text()
    assert "from gaia.engine.lang import register_prior" in text


def test_add_module_refuses_existing_file(gaia_package: FixturePackage) -> None:
    """Re-running add-module on the same name is a collision error."""
    runner.invoke(
        app,
        ["pkg", "add-module", "--name", "priors", "--target", str(gaia_package.root)],
    )
    result = runner.invoke(
        app,
        ["pkg", "add-module", "--name", "priors", "--target", str(gaia_package.root)],
    )
    assert result.exit_code != 0
    envelope = _parse(result.output)
    diagnostics = envelope["diagnostics"]
    assert isinstance(diagnostics, list)
    assert diagnostics[0]["kind"] == "prewrite.collision"


def test_add_module_rejects_invalid_name(gaia_package: FixturePackage) -> None:
    """Non-identifier names are rejected with exit code 2."""
    result = runner.invoke(
        app,
        [
            "pkg",
            "add-module",
            "--name",
            "1bad",
            "--target",
            str(gaia_package.root),
        ],
    )
    assert result.exit_code == 2


def test_author_file_routes_to_sibling(gaia_package: FixturePackage) -> None:
    """`gaia author claim --file priors.py` appends to priors.py."""
    # First create the sibling file.
    runner.invoke(
        app,
        ["pkg", "add-module", "--name", "priors", "--target", str(gaia_package.root)],
    )
    result = runner.invoke(
        app,
        [
            "author",
            "claim",
            "Test claim landing in priors.",
            "--label",
            "prior_test_claim",
            "--file",
            "priors.py",
            "--target",
            str(gaia_package.root),
            "--no-check",
        ],
    )
    assert result.exit_code == 0, result.output
    envelope = _parse(result.output)
    payload = envelope["payload"]
    assert isinstance(payload, dict)
    written_to = payload["written_to"]
    assert isinstance(written_to, str)
    assert written_to.endswith("priors.py")
    sibling = Path(gaia_package.root) / "src" / gaia_package.import_name / "priors.py"
    assert "prior_test_claim = claim(" in sibling.read_text()
    # __init__.py should NOT have the binding.
    assert "prior_test_claim" not in gaia_package.source_init.read_text()


def test_author_file_rejects_nonexistent_sibling(gaia_package: FixturePackage) -> None:
    """Routing to a non-existent file fails with target_invalid."""
    result = runner.invoke(
        app,
        [
            "author",
            "claim",
            "Will not land.",
            "--label",
            "wont_land",
            "--file",
            "ghost.py",
            "--target",
            str(gaia_package.root),
            "--no-check",
        ],
    )
    assert result.exit_code != 0
    envelope = _parse(result.output)
    diagnostics = envelope["diagnostics"]
    assert isinstance(diagnostics, list)
    assert diagnostics[0]["kind"] == "prewrite.target_invalid"


def test_author_file_rejects_absolute_path(gaia_package: FixturePackage) -> None:
    """Absolute paths are rejected with target_invalid."""
    result = runner.invoke(
        app,
        [
            "author",
            "claim",
            "Will not land.",
            "--label",
            "absurd",
            "--file",
            "/etc/passwd",
            "--target",
            str(gaia_package.root),
            "--no-check",
        ],
    )
    assert result.exit_code != 0
    envelope = _parse(result.output)
    diagnostics = envelope["diagnostics"]
    assert isinstance(diagnostics, list)
    assert diagnostics[0]["kind"] == "prewrite.target_invalid"


def test_author_file_rejects_dot_dot_traversal(gaia_package: FixturePackage) -> None:
    """`..` parts are rejected."""
    result = runner.invoke(
        app,
        [
            "author",
            "claim",
            "Will not land.",
            "--label",
            "absurd",
            "--file",
            "../../etc/passwd.py",
            "--target",
            str(gaia_package.root),
            "--no-check",
        ],
    )
    assert result.exit_code != 0


def test_register_prior_to_priors_py_adds_sibling_import(
    gaia_package: FixturePackage,
) -> None:
    """`register-prior --file priors.py` auto-inserts the cross-file import."""
    runner.invoke(
        app,
        ["pkg", "add-module", "--name", "priors", "--target", str(gaia_package.root)],
    )
    result = runner.invoke(
        app,
        [
            "author",
            "register-prior",
            "--claim",
            "hypothesis",
            "--value",
            "0.9",
            "--justification",
            "Test prior.",
            "--file",
            "priors.py",
            "--target",
            str(gaia_package.root),
            "--no-check",
        ],
    )
    assert result.exit_code == 0, result.output
    sibling = Path(gaia_package.root) / "src" / gaia_package.import_name / "priors.py"
    text = sibling.read_text()
    assert f"from {gaia_package.import_name} import hypothesis" in text
    assert "register_prior(hypothesis, 0.9" in text
