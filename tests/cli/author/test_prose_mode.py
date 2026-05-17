"""R3 prose-mode tests for ``--<arg>-content`` flags.

R3·❓A=A — uniform ``--<arg>-content``-suffix flags. The R3 cut implements
two named call sites — ``derive --conclusion-content`` (mints an
auto-claim) and ``claim --predicate`` (sandbox-validated formula) — plus
the small helper infra in :mod:`gaia.cli.commands.author._prose` for
future verbs.

These tests cover:

* ``derive --conclusion-content`` happy path: auto-generated claim
  appended to source before the derive statement, label derived from
  prose, payload exposes the auto-generated entry.
* ``--conclusion-label`` override: explicit label wins over slugified one.
* mutual exclusion with ``--conclusion``.
* ``claim --predicate`` happy path: renders ``formula=`` kwarg into the
  emitted statement.
* :func:`slugify_label` corner cases.
"""

from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

from gaia.cli.commands.author._prose import build_auto_claim_statement, slugify_label
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
# slugify_label                                                               #
# --------------------------------------------------------------------------- #


def test_slugify_basic_prose() -> None:
    assert slugify_label("The reaction is fast.") == "the_reaction_is_fast"


def test_slugify_caps_to_max_words() -> None:
    assert slugify_label("One two three four five six", max_words=3) == "one_two_three"


def test_slugify_prepends_c_when_leading_digit() -> None:
    assert slugify_label("42 is the answer").startswith("c_42")


def test_slugify_falls_back_to_auto_claim_on_empty() -> None:
    assert slugify_label("...??!") == "auto_claim"


def test_slugify_collision_suffixes_with_underscore_count() -> None:
    assert slugify_label("foo bar", existing={"foo_bar"}) == "foo_bar_2"
    assert slugify_label("foo bar", existing={"foo_bar", "foo_bar_2"}) == "foo_bar_3"


def test_slugify_lowercases() -> None:
    assert slugify_label("Hello World") == "hello_world"


def test_build_auto_claim_statement_shape() -> None:
    stmt = build_auto_claim_statement("my_claim", "Some prose.")
    assert stmt.startswith("my_claim = claim(")
    assert "'Some prose.'" in stmt


# --------------------------------------------------------------------------- #
# derive --conclusion-content                                                 #
# --------------------------------------------------------------------------- #


def test_derive_conclusion_content_auto_generates_claim(
    gaia_package: FixturePackage,
) -> None:
    """``--conclusion-content`` mints a fresh claim with a derived label."""
    result = runner.invoke(
        app,
        [
            "author",
            "derive",
            "--conclusion-content",
            "Stars are visible tonight.",
            "--given",
            "hypothesis",
            "--label",
            "visibility_warrant",
            "--target",
            str(gaia_package.root),
            "--no-check",
        ],
    )
    assert result.exit_code == 0, result.output
    envelope = _parse(result.output)
    payload = envelope["payload"]
    assert isinstance(payload, dict)
    auto = payload.get("auto_generated")
    assert isinstance(auto, list)
    assert len(auto) == 1
    auto_label = auto[0]["label"]
    assert isinstance(auto_label, str)
    assert auto_label.startswith("stars_are_visible")

    written = gaia_package.source_init.read_text()
    # The auto-claim is appended before the derive statement.
    assert f"{auto_label} = claim('Stars are visible tonight.')" in written
    assert f"visibility_warrant = derive({auto_label}" in written


def test_derive_conclusion_label_override(gaia_package: FixturePackage) -> None:
    """``--conclusion-label`` overrides the slug-derived label."""
    result = runner.invoke(
        app,
        [
            "author",
            "derive",
            "--conclusion-content",
            "Whatever prose here.",
            "--conclusion-label",
            "explicit_label",
            "--given",
            "hypothesis",
            "--label",
            "warranted_explicit",
            "--target",
            str(gaia_package.root),
            "--no-check",
        ],
    )
    assert result.exit_code == 0, result.output
    written = gaia_package.source_init.read_text()
    assert "explicit_label = claim('Whatever prose here.')" in written
    assert "warranted_explicit = derive(explicit_label" in written


def test_derive_conclusion_and_conclusion_content_mutually_exclusive(
    gaia_package: FixturePackage,
) -> None:
    result = runner.invoke(
        app,
        [
            "author",
            "derive",
            "--conclusion",
            "observation",
            "--conclusion-content",
            "Conflicting prose.",
            "--given",
            "hypothesis",
            "--label",
            "doomed",
            "--target",
            str(gaia_package.root),
            "--no-check",
        ],
    )
    assert result.exit_code == 2


def test_derive_requires_either_conclusion_form(
    gaia_package: FixturePackage,
) -> None:
    """Neither --conclusion nor --conclusion-content → exit 2."""
    result = runner.invoke(
        app,
        [
            "author",
            "derive",
            "--given",
            "hypothesis",
            "--label",
            "doomed",
            "--target",
            str(gaia_package.root),
            "--no-check",
        ],
    )
    assert result.exit_code == 2


def test_derive_conclusion_label_without_content_rejected(
    gaia_package: FixturePackage,
) -> None:
    """``--conclusion-label`` only makes sense with ``--conclusion-content``."""
    result = runner.invoke(
        app,
        [
            "author",
            "derive",
            "--conclusion",
            "observation",
            "--conclusion-label",
            "stray",
            "--given",
            "hypothesis",
            "--label",
            "doomed",
            "--target",
            str(gaia_package.root),
            "--no-check",
        ],
    )
    assert result.exit_code == 2


def test_derive_conclusion_content_collision_against_seeded_label_resolves(
    gaia_package: FixturePackage,
) -> None:
    """Auto-derived slug should avoid colliding with a seeded module symbol.

    The slugifier itself does not consult module symbols (it only sees
    the user-supplied ``existing`` set). When the slug happens to hit a
    real module binding, the prewrite (c) collision check fires as a
    hard error — that's the safety net.
    """
    # Seed an extra binding that would collide with the natural slug.
    existing = gaia_package.source_init.read_text()
    gaia_package.source_init.write_text(
        existing
        + "\nstars_are_visible_tonight = claim('preexisting')\n"
        + "__all__.append('stars_are_visible_tonight')\n"
    )

    result = runner.invoke(
        app,
        [
            "author",
            "derive",
            "--conclusion-content",
            "Stars are visible tonight.",
            "--given",
            "hypothesis",
            "--label",
            "visibility_warrant",
            "--target",
            str(gaia_package.root),
            "--no-check",
        ],
    )
    # Slug collides with the seeded name → prewrite.collision exit 3.
    assert result.exit_code == 3, result.output


# --------------------------------------------------------------------------- #
# claim --predicate (predicate-form claim)                                    #
# --------------------------------------------------------------------------- #


def test_claim_predicate_renders_formula_kwarg(gaia_package: FixturePackage) -> None:
    """``--predicate`` emits ``formula=...`` in the rendered statement."""
    result = runner.invoke(
        app,
        [
            "author",
            "claim",
            "Compound claim",
            "--label",
            "compound_pred",
            "--references",
            "hypothesis,observation",
            "--predicate",
            "land(ClaimAtom(hypothesis), ClaimAtom(observation))",
            "--target",
            str(gaia_package.root),
            "--no-check",
        ],
    )
    assert result.exit_code == 0, result.output
    written = gaia_package.source_init.read_text()
    assert (
        "compound_pred = claim('Compound claim', "
        "formula=land(ClaimAtom(hypothesis), ClaimAtom(observation))" in written
    )


def test_claim_predicate_unresolved_reference_rejected(
    gaia_package: FixturePackage,
) -> None:
    """A predicate naming an unresolved Claim ref fails the sandbox + prewrite."""
    result = runner.invoke(
        app,
        [
            "author",
            "claim",
            "Compound claim",
            "--label",
            "ghost_pred",
            "--predicate",
            "ClaimAtom(ghost_claim)",
            "--target",
            str(gaia_package.root),
            "--no-check",
        ],
    )
    # ``ghost_claim`` is not in the sandbox extras (no --references), so
    # the sandbox rejects it first.
    assert result.exit_code == 2
    envelope = _parse(result.output)
    diags = envelope["diagnostics"]
    assert isinstance(diags, list)
    assert "ghost_claim" in diags[0]["message"]
