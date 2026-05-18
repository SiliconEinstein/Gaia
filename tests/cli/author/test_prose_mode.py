"""Prose-mode tests for ``--<arg>-content`` and ``--conclusion-prose`` flags.

Uniform ``--<arg>-content``-suffix flags cover four call sites:

* ``derive --conclusion-content`` — mints a fresh auto-claim.
* ``claim --predicate`` — sandbox-validated formula.
* ``infer --hypothesis-content`` — the hypothesis is a fresh assertion
  for posterior-update.
* ``observe --observation-content`` — the observation is a fresh
  measurement statement.

All four reuse the same ``prepended_statements`` infra + helper
functions in :mod:`gaia.cli.commands.author._prose`.

``derive --conclusion-prose`` emits ``derive('<prose>', ...)`` inline
via the engine's ``conclusion: Claim | str`` polymorphism. Closes the
Galileo strict-reproducibility divergence around auto-mint bindings.
Three-way mutex with ``--conclusion`` (QID) and ``--conclusion-content``
(auto-mint). No named binding minted — prose is a bare string literal
at the call site.

These tests cover:

* ``derive --conclusion-content`` happy path: auto-generated claim
  appended to source before the derive statement, label derived from
  prose, payload exposes the auto-generated entry.
* ``--conclusion-label`` override: explicit label wins over slugified one.
* mutual exclusion with ``--conclusion``.
* ``claim --predicate`` happy path: renders ``formula=`` kwarg into the
  emitted statement.
* ``infer --hypothesis-content`` happy path + label override + mutex.
* ``observe --observation-content`` happy path + label override + mutex
  + prose/value compatibility rejection.
* ``derive --conclusion-prose`` happy path + no auto-mint + triple mutex
  + conclusion_kind payload tag + pre-write invariants under prose mode.
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


# --------------------------------------------------------------------------- #
# infer hypothesis prose                                                      #
# --------------------------------------------------------------------------- #


def test_infer_hypothesis_content_auto_generates_claim(
    gaia_package: FixturePackage,
) -> None:
    """``infer --hypothesis-content`` mints a fresh hypothesis claim."""
    result = runner.invoke(
        app,
        [
            "author",
            "infer",
            "--evidence",
            "observation",
            "--hypothesis-content",
            "A storm rolls in tonight.",
            "--p-e-given-h",
            "0.7",
            "--label",
            "storm_evidence",
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
    assert auto_label.startswith("a_storm_rolls_in")

    written = gaia_package.source_init.read_text()
    assert f"{auto_label} = claim('A storm rolls in tonight.')" in written
    # The infer call references the auto-label as hypothesis=...
    assert f"hypothesis={auto_label}" in written
    assert "storm_evidence = infer(observation" in written


def test_infer_hypothesis_label_override(gaia_package: FixturePackage) -> None:
    """``--hypothesis-label`` overrides the slug-derived label."""
    result = runner.invoke(
        app,
        [
            "author",
            "infer",
            "--evidence",
            "observation",
            "--hypothesis-content",
            "Whatever prose here.",
            "--hypothesis-label",
            "explicit_hyp",
            "--p-e-given-h",
            "0.7",
            "--label",
            "explicit_evidence",
            "--target",
            str(gaia_package.root),
            "--no-check",
        ],
    )
    assert result.exit_code == 0, result.output
    written = gaia_package.source_init.read_text()
    assert "explicit_hyp = claim('Whatever prose here.')" in written
    assert "hypothesis=explicit_hyp" in written


def test_infer_hypothesis_and_content_mutually_exclusive(
    gaia_package: FixturePackage,
) -> None:
    """Both --hypothesis and --hypothesis-content set → exit 2."""
    result = runner.invoke(
        app,
        [
            "author",
            "infer",
            "--evidence",
            "observation",
            "--hypothesis",
            "hypothesis",
            "--hypothesis-content",
            "Conflicting prose.",
            "--p-e-given-h",
            "0.7",
            "--label",
            "doomed",
            "--target",
            str(gaia_package.root),
            "--no-check",
        ],
    )
    assert result.exit_code == 2


def test_infer_requires_either_hypothesis_form(gaia_package: FixturePackage) -> None:
    """Neither --hypothesis nor --hypothesis-content set → exit 2."""
    result = runner.invoke(
        app,
        [
            "author",
            "infer",
            "--evidence",
            "observation",
            "--p-e-given-h",
            "0.7",
            "--label",
            "doomed",
            "--target",
            str(gaia_package.root),
            "--no-check",
        ],
    )
    assert result.exit_code == 2


def test_infer_hypothesis_label_without_content_rejected(
    gaia_package: FixturePackage,
) -> None:
    """``--hypothesis-label`` only makes sense with ``--hypothesis-content``."""
    result = runner.invoke(
        app,
        [
            "author",
            "infer",
            "--evidence",
            "observation",
            "--hypothesis",
            "hypothesis",
            "--hypothesis-label",
            "stray",
            "--p-e-given-h",
            "0.7",
            "--label",
            "doomed",
            "--target",
            str(gaia_package.root),
            "--no-check",
        ],
    )
    assert result.exit_code == 2


def test_infer_hypothesis_content_payload_has_auto_generated_entry(
    gaia_package: FixturePackage,
) -> None:
    """Envelope payload exposes the auto_generated entry list."""
    result = runner.invoke(
        app,
        [
            "author",
            "infer",
            "--evidence",
            "observation",
            "--hypothesis-content",
            "Fresh hypothesis.",
            "--p-e-given-h",
            "0.7",
            "--label",
            "fresh_evidence",
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
    entry = auto[0]
    assert "label" in entry
    assert "snippet" in entry
    assert "claim('Fresh hypothesis.')" in entry["snippet"]


# --------------------------------------------------------------------------- #
# observe observation prose                                                   #
# --------------------------------------------------------------------------- #


def test_observe_observation_content_auto_generates_claim(
    gaia_package: FixturePackage,
) -> None:
    """``observe --observation-content`` mints a fresh observation claim."""
    result = runner.invoke(
        app,
        [
            "author",
            "observe",
            "--observation-content",
            "Stars visible at zenith.",
            "--label",
            "vis_obs",
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
    assert auto_label.startswith("stars_visible")

    written = gaia_package.source_init.read_text()
    assert f"{auto_label} = claim('Stars visible at zenith.')" in written
    assert f"vis_obs = observe({auto_label}" in written


def test_observe_observation_label_override(gaia_package: FixturePackage) -> None:
    """``--observation-label`` overrides the slug-derived label."""
    result = runner.invoke(
        app,
        [
            "author",
            "observe",
            "--observation-content",
            "Some observation.",
            "--observation-label",
            "explicit_obs",
            "--label",
            "explicit_obs_event",
            "--target",
            str(gaia_package.root),
            "--no-check",
        ],
    )
    assert result.exit_code == 0, result.output
    written = gaia_package.source_init.read_text()
    assert "explicit_obs = claim('Some observation.')" in written
    assert "explicit_obs_event = observe(explicit_obs" in written


def test_observe_conclusion_and_content_mutually_exclusive(
    gaia_package: FixturePackage,
) -> None:
    """Both --conclusion and --observation-content set → exit 2."""
    result = runner.invoke(
        app,
        [
            "author",
            "observe",
            "--conclusion",
            "hypothesis",
            "--observation-content",
            "Conflicting prose.",
            "--label",
            "doomed",
            "--target",
            str(gaia_package.root),
            "--no-check",
        ],
    )
    assert result.exit_code == 2


def test_observe_requires_either_form(gaia_package: FixturePackage) -> None:
    """Neither --conclusion nor --observation-content set → exit 2."""
    result = runner.invoke(
        app,
        [
            "author",
            "observe",
            "--label",
            "lonely",
            "--target",
            str(gaia_package.root),
            "--no-check",
        ],
    )
    assert result.exit_code == 2


def test_observe_observation_label_without_content_rejected(
    gaia_package: FixturePackage,
) -> None:
    """``--observation-label`` only makes sense with ``--observation-content``."""
    result = runner.invoke(
        app,
        [
            "author",
            "observe",
            "--conclusion",
            "hypothesis",
            "--observation-label",
            "stray",
            "--label",
            "doomed",
            "--target",
            str(gaia_package.root),
            "--no-check",
        ],
    )
    assert result.exit_code == 2


def test_observe_observation_content_incompatible_with_value(
    gaia_package: FixturePackage,
) -> None:
    """Prose mode + --value (continuous form) is rejected.

    Continuous observation targets an existing Distribution, so the
    auto-mint pattern (which produces a Claim, not a Distribution)
    cannot apply.
    """
    result = runner.invoke(
        app,
        [
            "author",
            "observe",
            "--observation-content",
            "Continuous measurement.",
            "--value",
            "1.0",
            "--label",
            "bad_obs",
            "--target",
            str(gaia_package.root),
            "--no-check",
        ],
    )
    assert result.exit_code == 2


def test_observe_observation_content_with_given_conditional(
    gaia_package: FixturePackage,
) -> None:
    """Prose mode + --given builds a conditional discrete observation.

    Auto-mint happens first; the observation's --given list references
    the auto-claim plus any other premise identifiers.
    """
    result = runner.invoke(
        app,
        [
            "author",
            "observe",
            "--observation-content",
            "Visible with cloud cover.",
            "--given",
            "observation",
            "--label",
            "cond_vis",
            "--target",
            str(gaia_package.root),
            "--no-check",
        ],
    )
    assert result.exit_code == 0, result.output
    written = gaia_package.source_init.read_text()
    assert "given=[observation]" in written


def test_observe_observation_content_collision_against_seeded_resolves(
    gaia_package: FixturePackage,
) -> None:
    """Auto-derived slug collision against a seeded module symbol fails (c)."""
    existing = gaia_package.source_init.read_text()
    gaia_package.source_init.write_text(
        existing
        + "\nstars_visible_at_zenith = claim('preexisting')\n"
        + "__all__.append('stars_visible_at_zenith')\n"
    )
    result = runner.invoke(
        app,
        [
            "author",
            "observe",
            "--observation-content",
            "Stars visible at zenith.",
            "--label",
            "vis_obs",
            "--target",
            str(gaia_package.root),
            "--no-check",
        ],
    )
    assert result.exit_code == 3, result.output


# --------------------------------------------------------------------------- #
# derive conclusion-prose inline                                              #
# --------------------------------------------------------------------------- #


def test_derive_conclusion_prose_emits_inline_string_literal(
    gaia_package: FixturePackage,
) -> None:
    """``--conclusion-prose`` renders ``derive('<prose>', ...)`` directly.

    No auto-mint statement is prepended — the prose flows to the DSL
    call site as a bare string literal, leveraging the engine's
    ``conclusion: Claim | str`` polymorphism. This closes the Galileo
    strict-reproducibility divergence #1 (prose-mode auto-mint
    introducing named Claim bindings).
    """
    result = runner.invoke(
        app,
        [
            "author",
            "derive",
            "--conclusion-prose",
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
    assert envelope["status"] == "ok"
    payload = envelope["payload"]
    assert isinstance(payload, dict)
    assert payload.get("conclusion_kind") == "inline_prose"
    # No auto-generated entry — the inline shape mints nothing.
    assert "auto_generated" not in payload

    written = gaia_package.source_init.read_text()
    # No ``claim('Stars are visible tonight.')`` prepended.
    assert "claim('Stars are visible tonight.')" not in written
    # The derive call carries the prose as a bare string literal.
    assert (
        "visibility_warrant = derive('Stars are visible tonight.', "
        "given=[hypothesis], label='visibility_warrant')" in written
    )


def test_derive_conclusion_prose_payload_distinguishes_kind(
    gaia_package: FixturePackage,
) -> None:
    """The ``conclusion_kind`` payload tag distinguishes the three shapes."""
    # qid mode
    result_qid = runner.invoke(
        app,
        [
            "author",
            "derive",
            "--conclusion",
            "observation",
            "--given",
            "hypothesis",
            "--label",
            "qid_warrant",
            "--target",
            str(gaia_package.root),
            "--no-check",
        ],
    )
    assert result_qid.exit_code == 0, result_qid.output
    payload_qid = _parse(result_qid.output)["payload"]
    assert isinstance(payload_qid, dict)
    assert payload_qid.get("conclusion_kind") == "qid"

    # auto-mint mode
    result_auto = runner.invoke(
        app,
        [
            "author",
            "derive",
            "--conclusion-content",
            "An auto-mint prose conclusion.",
            "--given",
            "hypothesis",
            "--label",
            "auto_warrant",
            "--target",
            str(gaia_package.root),
            "--no-check",
        ],
    )
    assert result_auto.exit_code == 0, result_auto.output
    payload_auto = _parse(result_auto.output)["payload"]
    assert isinstance(payload_auto, dict)
    assert payload_auto.get("conclusion_kind") == "auto_mint"

    # inline-prose mode
    result_inline = runner.invoke(
        app,
        [
            "author",
            "derive",
            "--conclusion-prose",
            "An inline prose conclusion.",
            "--given",
            "hypothesis",
            "--label",
            "inline_warrant",
            "--target",
            str(gaia_package.root),
            "--no-check",
        ],
    )
    assert result_inline.exit_code == 0, result_inline.output
    payload_inline = _parse(result_inline.output)["payload"]
    assert isinstance(payload_inline, dict)
    assert payload_inline.get("conclusion_kind") == "inline_prose"


def test_derive_conclusion_prose_mutex_with_conclusion(
    gaia_package: FixturePackage,
) -> None:
    """``--conclusion`` and ``--conclusion-prose`` are mutually exclusive."""
    result = runner.invoke(
        app,
        [
            "author",
            "derive",
            "--conclusion",
            "observation",
            "--conclusion-prose",
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
    envelope = _parse(result.output)
    diags = envelope["diagnostics"]
    assert isinstance(diags, list)
    assert "mutually exclusive" in diags[0]["message"]


def test_derive_conclusion_prose_mutex_with_conclusion_content(
    gaia_package: FixturePackage,
) -> None:
    """``--conclusion-content`` and ``--conclusion-prose`` are mutually exclusive."""
    result = runner.invoke(
        app,
        [
            "author",
            "derive",
            "--conclusion-content",
            "Auto-mint prose.",
            "--conclusion-prose",
            "Inline prose.",
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
    envelope = _parse(result.output)
    diags = envelope["diagnostics"]
    assert isinstance(diags, list)
    assert "mutually exclusive" in diags[0]["message"]


def test_derive_conclusion_prose_triple_mutex(gaia_package: FixturePackage) -> None:
    """All three conclusion-mode flags set → triple-mutex error (exit 2)."""
    result = runner.invoke(
        app,
        [
            "author",
            "derive",
            "--conclusion",
            "observation",
            "--conclusion-content",
            "Auto prose.",
            "--conclusion-prose",
            "Inline prose.",
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


def test_derive_conclusion_prose_unresolved_premise_still_rejected(
    gaia_package: FixturePackage,
) -> None:
    """Inline-prose mode does NOT short-circuit (c)-reference validation.

    The prose itself is not a reference, but the ``--given`` premises
    must still resolve in module scope. A missing premise surfaces as
    ``prewrite.reference_unresolved`` (exit 3), same as in the other
    two conclusion modes.
    """
    result = runner.invoke(
        app,
        [
            "author",
            "derive",
            "--conclusion-prose",
            "Stars are visible tonight.",
            "--given",
            "ghost_premise",
            "--label",
            "visibility_warrant",
            "--target",
            str(gaia_package.root),
            "--no-check",
        ],
    )
    assert result.exit_code == 3
    envelope = _parse(result.output)
    diags = envelope["diagnostics"]
    assert isinstance(diags, list)
    assert diags[0]["kind"] == "prewrite.reference_unresolved"


def test_derive_conclusion_prose_label_collision_still_rejected(
    gaia_package: FixturePackage,
) -> None:
    """Inline-prose mode does NOT short-circuit (c)-collision validation.

    The verb's own label must remain a fresh module-scope symbol even
    when the conclusion is inline prose. A collision against a seeded
    binding surfaces as ``prewrite.collision`` (exit 3). Use a premise
    distinct from the colliding label so (d) self-loop doesn't fire
    first.
    """
    result = runner.invoke(
        app,
        [
            "author",
            "derive",
            "--conclusion-prose",
            "Stars are visible tonight.",
            "--given",
            "observation",
            "--label",
            "hypothesis",  # collides with seeded binding (but not in given)
            "--target",
            str(gaia_package.root),
            "--no-check",
        ],
    )
    assert result.exit_code == 3
    envelope = _parse(result.output)
    diags = envelope["diagnostics"]
    assert isinstance(diags, list)
    assert diags[0]["kind"] == "prewrite.collision"


def test_derive_conclusion_prose_compiles_clean_via_postwrite(
    gaia_package: FixturePackage,
) -> None:
    """Inline-prose derive survives the post-write ``gaia build check``.

    Verifies the engine's ``conclusion: Claim | str`` polymorphism
    actually compiles the prose-only conclusion at v0.5 — the
    architectural premise behind inline-prose mode. ``--check`` (default
    on) re-runs the full package compile after writing the statement.
    """
    result = runner.invoke(
        app,
        [
            "author",
            "derive",
            "--conclusion-prose",
            "Stars are visible tonight.",
            "--given",
            "hypothesis",
            "--label",
            "visibility_warrant",
            "--target",
            str(gaia_package.root),
        ],
    )
    assert result.exit_code == 0, result.output
    envelope = _parse(result.output)
    payload = envelope["payload"]
    assert isinstance(payload, dict)
    check = payload.get("check")
    assert isinstance(check, dict)
    # The fresh package starts with 2 seed claims; adding one derive
    # introduces 1 strategy + the conclusion Claim + the warrant Claim.
    assert check["strategy_count"] == 1


def test_derive_conclusion_prose_with_rationale_and_background(
    gaia_package: FixturePackage,
) -> None:
    """Inline-prose mode honours all the standard ``derive`` kwargs."""
    result = runner.invoke(
        app,
        [
            "author",
            "derive",
            "--conclusion-prose",
            "The composite falls faster than the heavy alone.",
            "--given",
            "hypothesis",
            "--background",
            "observation",
            "--rationale",
            "Greater weight implies greater natural speed.",
            "--label",
            "composite_faster",
            "--target",
            str(gaia_package.root),
            "--no-check",
        ],
    )
    assert result.exit_code == 0, result.output
    written = gaia_package.source_init.read_text()
    assert "composite_faster = derive(" in written
    assert "'The composite falls faster than the heavy alone.'" in written
    assert "given=[hypothesis]" in written
    assert "background=[observation]" in written
    assert "rationale='Greater weight implies greater natural speed.'" in written


def test_derive_requires_one_of_three_conclusion_modes(
    gaia_package: FixturePackage,
) -> None:
    """No conclusion-mode flag set → exit 2 with diagnostic naming all three."""
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
    envelope = _parse(result.output)
    diags = envelope["diagnostics"]
    assert isinstance(diags, list)
    msg = diags[0]["message"]
    assert "--conclusion" in msg
    assert "--conclusion-content" in msg
    assert "--conclusion-prose" in msg
