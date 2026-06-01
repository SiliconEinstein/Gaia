"""End-to-end integration chains for the cli surface.

Regression guards covering the cross-verb authoring paths:

* ``pkg scaffold`` → ``pkg add-module`` → ``author claim --file <sib>``
  → ``gaia build check`` clean (sibling-imports + role policy).
* ``bayes binomial --n <unsafe>`` rejected by the
  :func:`parse_literal_or_identifier` gate; clean input round-trips.
* Cross-module reference: ``--file <sib>`` referencing an identifier
  bound in ``__init__.py``; the writer auto-inserts the import.
* Priors policy: ``author claim --file priors.py`` exits 3 with
  ``prewrite.target_role_forbidden`` before write.

These tests run with ``--check`` (default) so the postwrite path is
fully exercised. They are pr_gate-marked so they run on every PR.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from gaia.cli.main import app

pytestmark = pytest.mark.pr_gate

runner = CliRunner()


def _parse_envelope(output: str) -> dict[str, object]:
    """Pull the last JSON line out of cli stdout."""
    for line in reversed(output.strip().splitlines()):
        line = line.strip()
        if line.startswith("{"):
            return json.loads(line)
    raise AssertionError(f"no JSON envelope in output: {output!r}")


def _scaffold(tmp_path: Path, *, name: str = "chain-gaia") -> Path:
    """Run ``pkg scaffold`` and return the target package root.

    Wave 1 cleanup: the scaffold template no longer pre-seeds a
    ``hypothesis`` placeholder claim, so there is nothing to strip here.
    """
    target = tmp_path / name
    result = runner.invoke(
        app,
        [
            "pkg",
            "scaffold",
            "--target",
            str(target),
            "--name",
            name,
            "--namespace",
            "example",
            "--no-check",
        ],
    )
    assert result.exit_code == 0, result.output
    return target


def test_chain_scaffold_add_module_author_check_clean(tmp_path: Path) -> None:
    """Pkg scaffold → add-module --name extra → author claim --file extra.py → check ok."""
    target = _scaffold(tmp_path)

    add_result = runner.invoke(
        app,
        [
            "pkg",
            "add-module",
            "--name",
            "extra",
            "--imports",
            "claim",
            "--target",
            str(target),
        ],
    )
    assert add_result.exit_code == 0, add_result.output

    author_result = runner.invoke(
        app,
        [
            "author",
            "claim",
            "Sibling claim.",
            "--dsl-binding-name",
            "sibling_claim",
            "--file",
            "extra.py",
            "--target",
            str(target),
        ],
    )
    assert author_result.exit_code == 0, author_result.output
    envelope = _parse_envelope(author_result.output)
    payload = envelope["payload"]
    assert isinstance(payload, dict)
    # The postwrite check should report the new Knowledge node.
    check = payload.get("check")
    assert isinstance(check, dict), check
    assert check["knowledge_count"] == 1
    # Sibling file (in authored/) should have the binding; the package-root
    # __init__.py never receives CLI-authored writes.
    extras_path = target / "src" / "chain" / "authored" / "extra.py"
    init_path = target / "src" / "chain" / "__init__.py"
    assert "sibling_claim = claim(" in extras_path.read_text()
    assert "sibling_claim" not in init_path.read_text()


def test_chain_bayes_binomial_unsafe_n_rejected(tmp_path: Path) -> None:
    """Bayes binomial --n with an unsafe expression exits 2 (prewrite.expr_unsafe)."""
    target = _scaffold(tmp_path)
    result = runner.invoke(
        app,
        [
            "bayes",
            "binomial",
            "--label",
            "doomed",
            "--n",
            "(__import__('os').system('id') or 5)",
            "--p",
            "0.5",
            "--target",
            str(target),
        ],
    )
    assert result.exit_code == 2, result.output
    envelope = _parse_envelope(result.output)
    diagnostics = envelope["diagnostics"]
    assert isinstance(diagnostics, list)
    assert diagnostics[0]["kind"] == "prewrite.expr_unsafe"


def test_chain_bayes_binomial_clean_inputs_round_trip(tmp_path: Path) -> None:
    """Bayes binomial with literal n/p produces a valid rendered binding.

    Distribution-only packages are rejected by the engine (no Knowledge
    declarations) — so we seed a single claim first to satisfy the
    engine's package-validity rule, then assert the Binomial binding
    appears in source.
    """
    target = _scaffold(tmp_path)
    seed_result = runner.invoke(
        app,
        [
            "author",
            "claim",
            "Seed claim for bayes chain.",
            "--dsl-binding-name",
            "seed_claim",
            "--target",
            str(target),
        ],
    )
    assert seed_result.exit_code == 0, seed_result.output
    result = runner.invoke(
        app,
        [
            "bayes",
            "binomial",
            "--label",
            "fair_coin",
            "--n",
            "100",
            "--p",
            "0.5",
            "--target",
            str(target),
        ],
    )
    assert result.exit_code == 0, result.output
    envelope = _parse_envelope(result.output)
    payload = envelope["payload"]
    assert isinstance(payload, dict)
    check = payload.get("check")
    assert isinstance(check, dict), check
    # CLI-authored statements land in the authored/ submodule.
    init_path = target / "src" / "chain" / "authored" / "__init__.py"
    assert "fair_coin = Binomial('fair_coin', n=100, p=0.5)" in init_path.read_text()


def test_chain_cross_module_reference_with_check(tmp_path: Path) -> None:
    """A sibling --file references a __init__.py binding; writer auto-imports."""
    target = _scaffold(tmp_path)

    # Declare a claim in __init__.py.
    base_result = runner.invoke(
        app,
        [
            "author",
            "claim",
            "Base observation.",
            "--dsl-binding-name",
            "base_obs",
            "--target",
            str(target),
        ],
    )
    assert base_result.exit_code == 0, base_result.output

    # Scaffold a sibling and derive from base_obs in it.
    add_result = runner.invoke(
        app,
        [
            "pkg",
            "add-module",
            "--name",
            "evidence",
            "--imports",
            "derive",
            "--target",
            str(target),
        ],
    )
    assert add_result.exit_code == 0, add_result.output
    derive_result = runner.invoke(
        app,
        [
            "author",
            "derive",
            "--conclusion-prose",
            "Derived from the base observation.",
            "--given",
            "base_obs",
            "--dsl-binding-name",
            "follow_warrant",
            "--file",
            "evidence.py",
            "--target",
            str(target),
        ],
    )
    assert derive_result.exit_code == 0, derive_result.output

    # Both the base claim and the sibling live in the authored/ submodule;
    # base_obs is imported through the package root, so the auto-inserted
    # ``from chain import base_obs`` resolves at load time.
    evidence_path = target / "src" / "chain" / "authored" / "evidence.py"
    text = evidence_path.read_text()
    assert "from chain import base_obs" in text
    assert "follow_warrant = derive(" in text


def test_chain_priors_policy_rejects_claim(tmp_path: Path) -> None:
    """Author claim --file priors.py exits 3 with prewrite.target_role_forbidden."""
    target = _scaffold(tmp_path)

    # Scaffold priors.py first so the file exists (else target_invalid
    # would mask the role-forbidden rejection).
    runner.invoke(
        app,
        ["pkg", "add-module", "--name", "priors", "--target", str(target)],
    )

    # Capture the package shape BEFORE the rejected command. Prewrite is
    # side-effect-free: a rejected author command must leave every file
    # byte-identical (no authored/ materialization, no root import block
    # mutation, no append to priors.py).
    src = target / "src" / "chain"
    init_path = src / "__init__.py"
    priors_path = src / "authored" / "priors.py"
    before = {path: path.read_text() for path in sorted(src.rglob("*.py"))}

    result = runner.invoke(
        app,
        [
            "author",
            "claim",
            "Forbidden in priors.",
            "--dsl-binding-name",
            "forbidden_claim",
            "--file",
            "priors.py",
            "--target",
            str(target),
        ],
    )
    assert result.exit_code == 3, result.output
    envelope = _parse_envelope(result.output)
    diagnostics = envelope["diagnostics"]
    assert isinstance(diagnostics, list)
    assert diagnostics[0]["kind"] == "prewrite.target_role_forbidden"
    # The rejected claim must NOT have been appended to priors.py.
    assert "forbidden_claim" not in priors_path.read_text()
    # The whole package shape is unchanged after the rejection: same set of
    # files, each byte-identical (covers the root __init__.py import block and
    # any authored/ contents — prewrite mutates nothing on rejection).
    after = {path: path.read_text() for path in sorted(src.rglob("*.py"))}
    assert after == before
    assert "forbidden_claim" not in init_path.read_text()
