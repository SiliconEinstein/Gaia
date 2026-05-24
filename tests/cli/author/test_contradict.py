"""CLI E2E tests for ``gaia author contradict``."""

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


def test_contradict_happy_path(gaia_package: FixturePackage) -> None:
    """Contradict references seeded labels and writes a `contradict(...)` call."""
    result = runner.invoke(
        app,
        [
            "author",
            "contradict",
            "--a",
            "hypothesis",
            "--b",
            "observation",
            "--dsl-binding-name",
            "they_contradict",
            "--target",
            str(gaia_package.root),
            "--no-check",
        ],
    )
    assert result.exit_code == 0, result.output
    written = gaia_package.source_init.read_text()
    assert "they_contradict = contradict(hypothesis, observation)" in written


def test_contradict_unresolved_exits_3(gaia_package: FixturePackage) -> None:
    result = runner.invoke(
        app,
        [
            "author",
            "contradict",
            "--a",
            "hypothesis",
            "--b",
            "ghost",
            "--dsl-binding-name",
            "c",
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


def test_contradict_self_loop_exits_1(gaia_package: FixturePackage) -> None:
    """label==a or label==b is a self-loop (exit 1)."""
    result = runner.invoke(
        app,
        [
            "author",
            "contradict",
            "--a",
            "hypothesis",
            "--b",
            "observation",
            "--dsl-binding-name",
            "hypothesis",
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


def test_contradict_postwrite_check(gaia_package: FixturePackage) -> None:
    result = runner.invoke(
        app,
        [
            "author",
            "contradict",
            "--a",
            "hypothesis",
            "--b",
            "observation",
            "--dsl-binding-name",
            "checked_contradict",
            "--target",
            str(gaia_package.root),
        ],
    )
    assert result.exit_code == 0, result.output


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


def test_contradict_accepts_pulled_claim_qid(gaia_package: FixturePackage) -> None:
    """`--a` / `--b` accept a pulled-claim QID; the alias becomes the in-DSL reference."""
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
            "contradict",
            "--a",
            "lkm:paper_a::conclusion_1",
            "--b",
            "observation",
            "--dsl-binding-name",
            "they_contradict",
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
    assert "they_contradict = contradict(paper_a__conclusion_1, observation)" in written


def test_contradict_rejects_non_identifier_non_qid(gaia_package: FixturePackage) -> None:
    """A token that is neither a bare identifier nor a QID is still refused."""
    result = runner.invoke(
        app,
        [
            "author",
            "contradict",
            "--a",
            "__import__('os')",
            "--b",
            "observation",
            "--target",
            str(gaia_package.root),
            "--no-check",
        ],
    )
    assert result.exit_code != 0
    envelope = _parse(result.output)
    assert envelope["status"] == "error"
    assert any("--a rejected" in d["message"] for d in envelope["diagnostics"])


def test_contradict_human_mode(gaia_package: FixturePackage) -> None:
    result = runner.invoke(
        app,
        [
            "author",
            "contradict",
            "--a",
            "hypothesis",
            "--b",
            "observation",
            "--dsl-binding-name",
            "human_contra",
            "--target",
            str(gaia_package.root),
            "--no-check",
            "--human",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "gaia author contradict" in result.output
