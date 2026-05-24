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


def _write_pulled_package(pkg_root, *, import_name: str, label: str, content: str) -> None:
    """Materialize a minimal pulled (lkm-namespaced) package under .gaia/lkm_packages/.

    Mirrors what ``gaia pkg add --lkm-paper`` lays down: a ``-gaia`` dist under
    ``.gaia/lkm_packages/<dist>/src/<import_name>/`` whose ``[tool.gaia].namespace``
    is ``lkm`` and whose claim is exported. The package depends only on
    ``gaia-lang``, so adding its ``src/`` to the path is enough to import it.
    """
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


def test_derive_given_accepts_pulled_claim_qid(gaia_package: FixturePackage) -> None:
    """`--given` accepts a pulled-claim QID, emits the aliased import + reference."""
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
            "derive",
            "--conclusion-prose",
            "B follows from the pulled premise.",
            "--given",
            "lkm:paper_a::conclusion_1",
            "--target",
            str(gaia_package.root),
            "--check",
        ],
    )
    assert result.exit_code == 0, result.output
    envelope = _parse(result.output)
    assert envelope["status"] == "ok"
    written = gaia_package.source_init.read_text()
    # Aliased import resolves the pulled claim; the alias is the in-DSL reference.
    assert "from paper_a import conclusion_1 as paper_a__conclusion_1" in written
    assert "given=[paper_a__conclusion_1]" in written


def test_derive_given_rejects_non_identifier_non_qid(gaia_package: FixturePackage) -> None:
    """A token that is neither a bare identifier nor a QID is still refused."""
    result = runner.invoke(
        app,
        [
            "author",
            "derive",
            "--conclusion",
            "observation",
            "--given",
            "__import__('os')",
            "--target",
            str(gaia_package.root),
            "--no-check",
        ],
    )
    assert result.exit_code != 0
    envelope = _parse(result.output)
    assert envelope["status"] == "error"
    assert any("--given rejected" in d["message"] for d in envelope["diagnostics"])
