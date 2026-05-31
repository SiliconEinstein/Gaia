"""Direct tests for the 4-invariant pre-write check.

The CLI verb tests exercise pre-write end-to-end; this file tests the
``prewrite_check`` API directly so each invariant has a per-failure-mode
unit test independent of any one verb's CLI shape.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from gaia.cli.commands.author._prewrite import prewrite_check
from gaia.cli.commands.author._proposed_op import ProposedAuthorOp

from .conftest import FixturePackage

pytestmark = pytest.mark.pr_gate


def _claim_op(label: str = "fresh_label", references: list[str] | None = None) -> ProposedAuthorOp:
    return ProposedAuthorOp(
        verb="claim",
        kind="reasoning",
        label=label,
        references=references or [],
        generated_code=f"{label} = claim('Test content.')",
    )


def test_prewrite_passes_on_valid_package(gaia_package: FixturePackage) -> None:
    """Invariant (a)/(b)/(c)/(d) all pass for a fresh non-colliding op."""
    result = prewrite_check(gaia_package.root, _claim_op())
    assert result.ok
    assert result.exit_code == 0
    assert result.diagnostics == []
    assert result.import_name == gaia_package.import_name
    assert result.project_name == gaia_package.project_name


def test_prewrite_target_missing(tmp_path: Path) -> None:
    """Invariant (a): non-existent target."""
    nonexistent = tmp_path / "does-not-exist"
    result = prewrite_check(nonexistent, _claim_op())
    assert not result.ok
    assert result.exit_code == 4  # EXIT_SYSTEM_IO
    assert result.diagnostics[0].kind == "prewrite.target_missing"


def test_prewrite_target_not_gaia_package(not_a_gaia_package: Path) -> None:
    """Invariant (a): pyproject without [tool.gaia].type."""
    result = prewrite_check(not_a_gaia_package, _claim_op())
    assert not result.ok
    assert result.exit_code == 4
    assert result.diagnostics[0].kind == "prewrite.target_not_gaia_package"


def test_prewrite_target_invalid_toml(tmp_path: Path) -> None:
    """Invariant (a): pyproject.toml that fails to parse.

    The kind was split from the overloaded ``prewrite.target_invalid``
    into ``prewrite.target_bad_toml`` so downstream dispatch can
    distinguish bad-TOML from missing-pyproject / missing-source-root /
    missing-init.py.
    """
    root = tmp_path / "broken-gaia"
    root.mkdir()
    (root / "pyproject.toml").write_text("this is not = valid toml [[")
    result = prewrite_check(root, _claim_op())
    assert not result.ok
    assert result.diagnostics[0].kind == "prewrite.target_bad_toml"


def test_prewrite_syntax_failure(gaia_package: FixturePackage) -> None:
    """Invariant (b): proposed code does not parse."""
    bad_op = ProposedAuthorOp(
        verb="claim",
        kind="reasoning",
        label="bad",
        generated_code="bad = claim(",  # unterminated call
    )
    result = prewrite_check(gaia_package.root, bad_op)
    assert not result.ok
    assert result.exit_code == 2  # EXIT_INPUT_SYNTAX
    assert result.diagnostics[0].kind == "prewrite.syntax"


def test_prewrite_label_collision(gaia_package: FixturePackage) -> None:
    """Invariant (c): label collides with an already-bound module symbol."""
    op = _claim_op(label="hypothesis")  # seeded by the fixture's __init__.py
    result = prewrite_check(gaia_package.root, op)
    assert not result.ok
    assert result.exit_code == 3  # EXIT_COLLISION_OR_REF
    assert result.diagnostics[0].kind == "prewrite.collision"


def test_prewrite_invalid_label_identifier(gaia_package: FixturePackage) -> None:
    """Invariant (b/c): invalid Python identifier surfaces as a syntax error.

    The generated snippet ``"123_not_valid = claim(...)"`` fails the
    pre-write syntax invariant (b) before invariant (c) gets to run its
    isidentifier() check — both invariants would catch this, but
    fail-fast order means (b) fires first. We assert that the error is
    one of the two expected kinds so the test stays robust if the order
    later flips.
    """
    op = _claim_op(label="123_not_valid")
    result = prewrite_check(gaia_package.root, op)
    assert not result.ok
    assert result.diagnostics[0].kind in {"prewrite.syntax", "prewrite.collision"}


def test_prewrite_invalid_label_dunder_via_synth_snippet(gaia_package: FixturePackage) -> None:
    """Invariant (c): identifier starts with __ — caught by collision check.

    Crafted to hit invariant (c) without snagging on invariant (b): the
    snippet uses a valid Python identifier so (b) passes; the label
    starts with __ so isidentifier passes but our policy rejects it.
    """
    op = ProposedAuthorOp(
        verb="claim",
        kind="reasoning",
        label="__dunder",
        references=[],
        generated_code="__dunder = claim('Content.')",
    )
    result = prewrite_check(gaia_package.root, op)
    assert not result.ok
    assert result.diagnostics[0].kind == "prewrite.collision"


def test_prewrite_reference_unresolved(gaia_package: FixturePackage) -> None:
    """Invariant (c): reference does not resolve in module scope."""
    op = _claim_op(references=["nonexistent_label"])
    result = prewrite_check(gaia_package.root, op)
    assert not result.ok
    assert result.exit_code == 3
    assert result.diagnostics[0].kind == "prewrite.reference_unresolved"


def test_prewrite_reference_resolved_via_seed(gaia_package: FixturePackage) -> None:
    """Invariant (c): pre-existing seeded labels resolve cleanly."""
    op = _claim_op(label="derived", references=list(gaia_package.seed_labels))
    result = prewrite_check(gaia_package.root, op)
    assert result.ok, [d.message for d in result.diagnostics]


def test_prewrite_self_loop(gaia_package: FixturePackage) -> None:
    """Invariant (d): label references itself.

    The pipeline runs (d) before (c) precisely so a self-loop fires as
    ``prewrite.self_loop`` (exit 1) rather than being masked by (c)'s
    collision check. See ``prewrite_check`` docstring for the
    rationale.
    """
    op = _claim_op(label="hypothesis", references=["hypothesis"])
    result = prewrite_check(gaia_package.root, op)
    assert not result.ok
    assert result.exit_code == 1  # EXIT_PREWRITE_STRUCTURAL
    assert result.diagnostics[0].kind == "prewrite.self_loop"


def test_prewrite_failfast_orders_first_error() -> None:
    """When multiple invariants would fail, target-validity fires first."""
    # Both invariants fail: target missing AND syntax invalid. Order means
    # target-validity wins; pre-write returns one diagnostic, not two.
    op = ProposedAuthorOp(
        verb="claim",
        kind="reasoning",
        label="foo",
        generated_code="!syntactically invalid",
    )
    result = prewrite_check(Path("/no/such/path"), op)
    assert not result.ok
    assert len(result.diagnostics) == 1
    assert result.diagnostics[0].kind == "prewrite.target_missing"


def test_prewrite_is_side_effect_free_on_a_fresh_package(tmp_path: Path) -> None:
    """Prewrite must not materialize ``authored/`` or touch the root __init__.

    Regression for the side-effecting ``ensure_authored_submodule`` call
    that used to run during the read-only prewrite check. A package with
    no ``authored/`` submodule should come out byte-identical after a
    prewrite — materialization is the writer's job, not prewrite's.
    """
    project_name = "fresh-gaia"
    import_name = "fresh"
    root = tmp_path / project_name
    src = root / "src" / import_name
    src.mkdir(parents=True)
    (root / "pyproject.toml").write_text(
        '[project]\nname = "fresh-gaia"\nversion = "0.1.0"\n\n'
        '[tool.gaia]\ntype = "knowledge-package"\n'
    )
    root_init = src / "__init__.py"
    root_init.write_text("from gaia.engine.lang import claim\n\n__all__: list[str] = []\n")
    before = root_init.read_text()

    result = prewrite_check(root, _claim_op())
    assert result.ok, [d.message for d in result.diagnostics]

    # No authored/ created, root __init__ untouched.
    assert not (src / "authored").exists()
    assert root_init.read_text() == before


def test_prewrite_root_only_symbols_excludes_imports(tmp_path: Path) -> None:
    """Import-bound root names are NOT cross-module-injected.

    A root ``from gaia.engine.lang import register_prior`` binds
    ``register_prior`` at module scope, but it is an imported name (engine
    names are handled by the writer's required_imports). It must not land
    in ``root_only_symbols``, otherwise the runner would emit a spurious
    ``from <pkg> import register_prior`` re-import. A *DSL* binding
    (assignment) in the root still counts.
    """
    project_name = "imp-gaia"
    import_name = "imp"
    root = tmp_path / project_name
    src = root / "src" / import_name
    src.mkdir(parents=True)
    (root / "pyproject.toml").write_text(
        '[project]\nname = "imp-gaia"\nversion = "0.1.0"\n\n'
        '[tool.gaia]\ntype = "knowledge-package"\n'
    )
    root_init = src / "__init__.py"
    # An imported engine name + a hand-authored DSL binding at root scope.
    root_init.write_text(
        "from gaia.engine.lang import claim, register_prior\n\n"
        "root_claim = claim('Hand-authored root claim.')\n\n"
        '__all__ = ["root_claim"]\n'
    )

    result = prewrite_check(root, _claim_op())
    assert result.ok, [d.message for d in result.diagnostics]
    # The imported name must NOT be a cross-module-injection candidate.
    assert "register_prior" not in result.root_only_symbols
    assert "claim" not in result.root_only_symbols
    # The hand-authored DSL binding still is.
    assert "root_claim" in result.root_only_symbols
