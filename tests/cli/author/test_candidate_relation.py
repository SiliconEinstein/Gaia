"""CLI E2E tests for ``gaia author candidate-relation``."""

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


def test_candidate_relation_happy_path(gaia_package: FixturePackage) -> None:
    result = runner.invoke(
        app,
        [
            "author",
            "candidate-relation",
            "--claims",
            "hypothesis,observation",
            "--pattern",
            "equal",
            "--dsl-binding-name",
            "maybe_equal",
            "--target",
            str(gaia_package.root),
            "--no-check",
        ],
    )
    assert result.exit_code == 0, result.output
    written = gaia_package.source_init.read_text()
    assert "maybe_equal = candidate_relation(" in written
    assert "claims=[hypothesis, observation]" in written
    assert "pattern='equal'" in written


def test_candidate_relation_without_pattern(gaia_package: FixturePackage) -> None:
    """Pattern is optional."""
    result = runner.invoke(
        app,
        [
            "author",
            "candidate-relation",
            "--claims",
            "hypothesis,observation",
            "--dsl-binding-name",
            "patternless",
            "--target",
            str(gaia_package.root),
            "--no-check",
        ],
    )
    assert result.exit_code == 0, result.output
    written = gaia_package.source_init.read_text()
    assert "pattern=" not in written.split("patternless = candidate_relation")[1].split("\n")[0]


def test_candidate_relation_requires_two_claims(gaia_package: FixturePackage) -> None:
    result = runner.invoke(
        app,
        [
            "author",
            "candidate-relation",
            "--claims",
            "hypothesis",
            "--dsl-binding-name",
            "too_few",
            "--target",
            str(gaia_package.root),
            "--no-check",
        ],
    )
    assert result.exit_code == 2


def test_candidate_relation_contradict_requires_two(gaia_package: FixturePackage) -> None:
    """pattern=contradict requires exactly 2 claims."""
    # Seed a third claim to test the rejection.
    existing = gaia_package.source_init.read_text()
    gaia_package.source_init.write_text(existing + "\nthird = claim('Third.')\n")
    result = runner.invoke(
        app,
        [
            "author",
            "candidate-relation",
            "--claims",
            "hypothesis,observation,third",
            "--pattern",
            "contradict",
            "--dsl-binding-name",
            "three_way_contra",
            "--target",
            str(gaia_package.root),
            "--no-check",
        ],
    )
    assert result.exit_code == 2


def test_candidate_relation_bad_pattern_exits_2(gaia_package: FixturePackage) -> None:
    result = runner.invoke(
        app,
        [
            "author",
            "candidate-relation",
            "--claims",
            "hypothesis,observation",
            "--pattern",
            "xor",
            "--dsl-binding-name",
            "bad_pat",
            "--target",
            str(gaia_package.root),
            "--no-check",
        ],
    )
    assert result.exit_code == 2


def test_candidate_relation_unresolved_exits_3(gaia_package: FixturePackage) -> None:
    result = runner.invoke(
        app,
        [
            "author",
            "candidate-relation",
            "--claims",
            "hypothesis,ghost",
            "--dsl-binding-name",
            "unresolved",
            "--target",
            str(gaia_package.root),
            "--no-check",
        ],
    )
    assert result.exit_code == 3


def _write_pulled_package(pkg_root, *, import_name: str, label: str, content: str) -> None:
    """Materialize a minimal pulled (lkm-namespaced) package under .gaia/lkm_packages/."""
    dist = f"{import_name.replace('_', '-')}-gaia"
    root = pkg_root / ".gaia" / "lkm_packages" / dist
    src = root / "src" / import_name
    src.mkdir(parents=True)
    (root / "pyproject.toml").write_text(
        f'[project]\nname = "{dist}"\nversion = "0.1.0"\n\n'
        '[tool.gaia]\ntype = "knowledge-package"\nnamespace = "lkm"\n'
    )
    (src / "__init__.py").write_text(
        "from gaia.engine.lang import claim\n\n"
        f"{label} = claim({content!r})\n"
        f'__all__ = ["{label}"]\n'
    )


def test_candidate_relation_accepts_pulled_claim_qid(gaia_package: FixturePackage) -> None:
    """`--claims` accepts a pulled-claim QID; the alias becomes the in-DSL reference."""
    _write_pulled_package(
        gaia_package.root,
        import_name="paper_a",
        label="conclusion_1",
        content="Pulled paper A conclusion.",
    )
    result = runner.invoke(
        app,
        [
            "author",
            "candidate-relation",
            "--claims",
            "lkm:paper_a::conclusion_1,observation",
            "--dsl-binding-name",
            "maybe_related",
            "--target",
            str(gaia_package.root),
            "--check",
        ],
    )
    assert result.exit_code == 0, result.output
    envelope = _parse(result.output)
    assert envelope["status"] == "ok"
    written = gaia_package.source_init.read_text()
    assert "from paper_a import conclusion_1 as paper_a__conclusion_1" in written
    assert "claims=[paper_a__conclusion_1, observation]" in written


def test_candidate_relation_human_mode(gaia_package: FixturePackage) -> None:
    result = runner.invoke(
        app,
        [
            "author",
            "candidate-relation",
            "--claims",
            "hypothesis,observation",
            "--dsl-binding-name",
            "human_cr",
            "--target",
            str(gaia_package.root),
            "--no-check",
            "--human",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "gaia author candidate_relation" in result.output
