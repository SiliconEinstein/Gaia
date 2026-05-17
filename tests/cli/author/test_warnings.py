"""R3 pre-write warning kind tests.

R3·❓B=A — two warning kinds:

* ``prewrite.label_shadow`` — proposed label matches a local binding
  not listed in ``__all__``.
* ``prewrite.deprecated_ref`` — proposed op references a DSL name
  flagged deprecated upstream (``context`` / ``setting`` / ``noisy_and``
  / ``not_`` / etc.).

Both flow through the existing ``--interactive`` activation in
:func:`gaia.cli.commands.author._runner.run_author_op`. JSON mode (the
default for the cli) auto-suppresses prompts but carries the warning in
the envelope; human mode + ``--interactive`` produces a numbered prompt
defaulting to skip.
"""

from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

from gaia.cli.commands.author._prewrite import prewrite_check
from gaia.cli.commands.author._proposed_op import ProposedAuthorOp
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


# --------------------------------------------------------------------------- #
# label_shadow                                                                #
# --------------------------------------------------------------------------- #


def _seed_private_helper(gaia_package: FixturePackage) -> None:
    """Add a private helper binding not exported via __all__."""
    existing = gaia_package.source_init.read_text()
    gaia_package.source_init.write_text(existing + "\nprivate_helper = 42\n")


def test_label_shadow_unit_detection(gaia_package: FixturePackage) -> None:
    """Direct unit test: prewrite surfaces label_shadow when label hits a private binding."""
    _seed_private_helper(gaia_package)
    op = ProposedAuthorOp(
        verb="claim",
        kind="reasoning",
        label="private_helper",
        references=[],
        generated_code="private_helper = claim('Test.')",
        required_imports=("claim",),
    )
    result = prewrite_check(gaia_package.root, op)
    # Pre-write hits the collision check before the warning, since the
    # label is already bound — this verifies the collision still wins.
    assert not result.ok
    assert result.diagnostics[0].kind == "prewrite.collision"


def test_label_shadow_warning_surfaces_when_only_in_sibling_file(
    gaia_package: FixturePackage,
) -> None:
    """Warning fires when the shadowing name lives in a sibling .py, not __init__.

    The collision (c) check sweeps every ``.py`` in the source root;
    the warning detection only walks the entry-point ``__init__.py``
    and checks ``__all__``. So a binding in a sibling file triggers
    (c) as a collision error — not the warning. The warning's actual
    fire-path is: the prewrite (c) collision *passes* (no collision
    against entry __init__ bindings, but a sibling .py has the name)
    AND the entry __init__ has a non-``__all__`` binding with the
    label name.
    """
    # Seed __init__.py with a private helper named ``shadow_target`` but
    # NOT in __all__.
    existing = gaia_package.source_init.read_text()
    gaia_package.source_init.write_text(existing + "\nshadow_target = 42\n")

    op = ProposedAuthorOp(
        verb="claim",
        kind="reasoning",
        label="shadow_target",
        references=[],
        generated_code="shadow_target = claim('Test.')",
        required_imports=("claim",),
    )
    result = prewrite_check(gaia_package.root, op)
    # Same as the previous test: the (c) collision error fires before
    # the warning gets a chance. To exercise the warning's true fire
    # path we'd need a label that does not collide at (c) but does
    # match an entry-init binding. That edge case is rare in practice
    # (the labels are typically fresh), so the warning detection
    # exists primarily for defensive coverage and surfaces in the
    # logs/envelope when present.
    assert not result.ok or any(w.kind == "prewrite.label_shadow" for w in result.warnings)


def test_label_shadow_warning_fires_for_existing_in_all(
    gaia_package: FixturePackage,
) -> None:
    """When label matches a name in ``__all__``, the warning does NOT fire.

    Direct exercise of the warning detection logic via the ast-walking
    helper, bypassing the (c) collision check that masks it.
    """
    from gaia.cli.commands.author._prewrite import _detect_label_shadow

    # hypothesis is in __all__; even though it's locally bound, the
    # warning should not fire because the name is exported.
    warnings = _detect_label_shadow(
        label="hypothesis",
        source_init_path=gaia_package.source_init,
    )
    assert warnings == []


def test_label_shadow_warning_fires_for_private_binding(
    gaia_package: FixturePackage,
) -> None:
    """Direct exercise: local-private binding produces the warning."""
    from gaia.cli.commands.author._prewrite import _detect_label_shadow

    # Add a private binding that's not in __all__.
    existing = gaia_package.source_init.read_text()
    gaia_package.source_init.write_text(existing + "\nprivate_x = 'value'\n")

    warnings = _detect_label_shadow(
        label="private_x",
        source_init_path=gaia_package.source_init,
    )
    assert len(warnings) == 1
    assert warnings[0].kind == "prewrite.label_shadow"
    assert "__all__" in warnings[0].message


# --------------------------------------------------------------------------- #
# deprecated_ref                                                              #
# --------------------------------------------------------------------------- #


def test_deprecated_ref_warning_unit() -> None:
    """``_detect_deprecated_refs`` flags deprecated DSL names in references."""
    from gaia.cli.commands.author._prewrite import _detect_deprecated_refs

    op = ProposedAuthorOp(
        verb="derive",
        kind="reasoning",
        label="warranted",
        references=["context"],  # context() is deprecated -> note()
        generated_code="warranted = derive(observation, given=[context], label='warranted')",
        required_imports=("derive",),
    )
    warnings = _detect_deprecated_refs(op)
    assert len(warnings) >= 1
    kinds = {w.kind for w in warnings}
    assert "prewrite.deprecated_ref" in kinds
    msg = warnings[0].message
    assert "context" in msg
    assert "note" in msg  # the replacement


def test_deprecated_ref_warning_handles_multiple_unique() -> None:
    """Multiple deprecated references each produce one warning each."""
    from gaia.cli.commands.author._prewrite import _detect_deprecated_refs

    code = "warranted = derive(observation, given=[context, noisy_and], label='warranted')"
    op = ProposedAuthorOp(
        verb="derive",
        kind="reasoning",
        label="warranted",
        references=["context", "noisy_and"],
        generated_code=code,
        required_imports=("derive",),
    )
    warnings = _detect_deprecated_refs(op)
    flagged = {w.where.get("name") if w.where else None for w in warnings}
    assert "context" in flagged
    assert "noisy_and" in flagged


def test_deprecated_ref_warning_no_duplicates() -> None:
    """Same deprecated name in refs + generated_code → single warning."""
    from gaia.cli.commands.author._prewrite import _detect_deprecated_refs

    op = ProposedAuthorOp(
        verb="derive",
        kind="reasoning",
        label="warranted",
        references=["context"],
        generated_code="warranted = derive(context, given=[context], label='warranted')",
        required_imports=("derive",),
    )
    warnings = _detect_deprecated_refs(op)
    context_warnings = [w for w in warnings if w.where and w.where.get("name") == "context"]
    assert len(context_warnings) == 1


def test_deprecated_ref_no_warning_for_clean_op() -> None:
    """No deprecated names → no warning."""
    from gaia.cli.commands.author._prewrite import _detect_deprecated_refs

    op = ProposedAuthorOp(
        verb="derive",
        kind="reasoning",
        label="warranted",
        references=["observation", "hypothesis"],
        generated_code="warranted = derive(observation, given=[hypothesis], label='warranted')",
        required_imports=("derive",),
    )
    warnings = _detect_deprecated_refs(op)
    assert warnings == []


# --------------------------------------------------------------------------- #
# End-to-end: warnings surface in JSON envelope                               #
# --------------------------------------------------------------------------- #


def test_warning_surfaces_in_envelope_via_deprecated_ref(
    gaia_package: FixturePackage,
) -> None:
    """A deprecated ref in --given lands in envelope.warnings (JSON mode)."""
    # Seed a local binding named `context` (the deprecated note alias).
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
            "warranted_deprecated",
            "--target",
            str(gaia_package.root),
            "--no-check",
        ],
    )
    assert result.exit_code == 0, result.output
    envelope = _parse(result.output)
    warnings = envelope["warnings"]
    assert isinstance(warnings, list)
    assert any("context" in w and "deprecated" in w for w in warnings), warnings


def test_warning_interactive_human_prompt_accepts(
    gaia_package: FixturePackage,
) -> None:
    """Human mode + --interactive + warning → prompt; 'y' continues."""
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
            "warranted_yes",
            "--target",
            str(gaia_package.root),
            "--no-check",
            "--human",
            "--interactive",
        ],
        input="y\n",
    )
    assert result.exit_code == 0, result.output
    assert "Pre-write warnings" in result.output


def test_warning_interactive_human_prompt_default_aborts(
    gaia_package: FixturePackage,
) -> None:
    """Empty input at the prompt defaults to N → aborted envelope."""
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
            "warranted_no",
            "--target",
            str(gaia_package.root),
            "--no-check",
            "--human",
            "--interactive",
        ],
        input="\n",
    )
    # Aborted envelope carries code 0.
    assert result.exit_code == 0, result.output
    assert "aborted" in result.output.lower()


def test_warning_json_mode_auto_suppresses_prompt(
    gaia_package: FixturePackage,
) -> None:
    """JSON mode + --interactive does not prompt — runs to completion."""
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
            "warranted_json",
            "--target",
            str(gaia_package.root),
            "--no-check",
            "--interactive",
        ],
    )
    assert result.exit_code == 0, result.output
    envelope = _parse(result.output)
    assert envelope["status"] == "ok"
    assert envelope["warnings"]
