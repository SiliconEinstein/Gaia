"""``gaia author derive`` — append a ``derive(conclusion, given=[...])`` statement.

Maps to ``gaia.engine.lang.dsl.support.derive``:

.. code-block:: python

    derive(
        conclusion,
        *,
        given=(),
        background=None,
        rationale="",
        label=None,
    )

The verb supports three CLI shapes for ``conclusion``:

* ``--conclusion <identifier>`` — reference an already-declared Claim.
* ``--conclusion-content "<prose>"`` — cli auto-generates a fresh Claim
  bound to a slug derived from the prose, appends it to the target
  file, then uses the slug as ``conclusion``. ``--conclusion-label``
  overrides the auto-derived slug.
* ``--conclusion-prose "<prose>"`` — emits ``derive('<prose>', ...)``
  directly, leveraging the engine's ``conclusion: Claim | str``
  polymorphism. No named Claim binding is minted; the prose flows to
  the DSL call site as a bare string literal.

The three shapes are mutually exclusive — pick exactly one. ``R3`` ships
the auto-mint shape via the prose-mode helper infra in
:mod:`gaia.cli.commands.author._prose`; ``R6`` adds the inline-prose
shape that closes the Galileo strict-reproducibility divergence #1
(prose-mode auto-mint introducing named Claim bindings).
"""

from __future__ import annotations

import json
from typing import Any

import typer

from gaia.cli.commands.author._common import emit_syntax_error
from gaia.cli.commands.author._envelope import (
    AuthorResult,
    Diagnostic,
    emit,
    exit_code_for_diagnostic,
)
from gaia.cli.commands.author._proposed_op import ProposedAuthorOp
from gaia.cli.commands.author._prose import build_auto_claim_statement, slugify_label
from gaia.cli.commands.author._runner import run_author_op


def _parse_metadata(metadata_json: str | None) -> tuple[dict[str, Any] | None, str | None]:
    if metadata_json is None:
        return None, None
    try:
        parsed = json.loads(metadata_json)
    except json.JSONDecodeError as exc:
        return None, f"--metadata is not valid JSON: {exc}"
    if not isinstance(parsed, dict):
        return None, "--metadata must encode a JSON object (got non-object value)"
    return parsed, None


def _split_csv(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def _render_derive_statement(
    *,
    label: str,
    conclusion_expr: str,
    given: list[str],
    rationale: str | None,
    metadata: dict[str, Any] | None,
    background: list[str],
) -> str:
    """Render the proposed ``derive(...)`` statement.

    ``conclusion_expr`` is the *Python source* spelling that the call
    site uses for the conclusion argument: either a bare identifier
    (``--conclusion`` / ``--conclusion-content`` auto-mint slug) or a
    quoted string literal (``--conclusion-prose``). The caller is
    responsible for shaping the spelling before handing it in.
    """
    given_repr = "[" + ", ".join(given) + "]" if given else "[]"
    args = [conclusion_expr]
    kwargs = [f"given={given_repr}", f"label={label!r}"]
    if rationale:
        kwargs.append(f"rationale={rationale!r}")
    if background:
        bg_repr = "[" + ", ".join(background) + "]"
        kwargs.append(f"background={bg_repr}")
    if metadata:
        kwargs.append(f"metadata={metadata!r}")
    return f"{label} = derive({', '.join(args)}, {', '.join(kwargs)})"


def derive_command(
    conclusion: str | None = typer.Option(
        None,
        "--conclusion",
        help="Identifier of the conclusion Claim (must already be declared).",
    ),
    conclusion_content: str | None = typer.Option(
        None,
        "--conclusion-content",
        help=(
            "Prose for an auto-generated conclusion Claim. Mutually exclusive with "
            "--conclusion and --conclusion-prose. Cli derives a snake-case slug for "
            "the label (override via --conclusion-label)."
        ),
    ),
    conclusion_label: str | None = typer.Option(
        None,
        "--conclusion-label",
        help=(
            "Optional explicit label for the auto-generated conclusion Claim "
            "(only meaningful with --conclusion-content)."
        ),
    ),
    conclusion_prose: str | None = typer.Option(
        None,
        "--conclusion-prose",
        help=(
            "Inline prose passed to the engine's ``derive(conclusion: Claim | str, "
            "...)`` polymorphism. Emits ``derive('<prose>', ...)`` directly with no "
            "named binding. Mutually exclusive with --conclusion and "
            "--conclusion-content."
        ),
    ),
    given: str = typer.Option(
        ...,
        "--given",
        help="Comma-separated identifiers of the premise Claim(s) the conclusion is derived from.",
    ),
    label: str = typer.Option(..., "--label", help="Identifier the produced binding takes."),
    target: str = typer.Option(
        ".", "--target", help="Path to the target Gaia package (default: cwd)."
    ),
    rationale: str | None = typer.Option(
        None, "--rationale", help="Optional natural-language justification of the derivation."
    ),
    metadata: str | None = typer.Option(
        None, "--metadata", help="Optional JSON-encoded metadata dict."
    ),
    background: str | None = typer.Option(
        None,
        "--background",
        help="Comma-separated identifiers passed as the derive() background kwarg.",
    ),
    check: bool = typer.Option(
        True,
        "--check/--no-check",
        help="Run post-write `gaia build check` after a successful write (default on).",
    ),
    human: bool = typer.Option(
        False,
        "--human",
        help="Render the envelope in human-readable form instead of JSON.",
    ),
    interactive: bool = typer.Option(
        False,
        "--interactive",
        help="Prompt on pre-write warnings (human mode only).",
    ),
    json_: bool = typer.Option(
        True, "--json/--no-json", help="JSON-first output (default; redundant for clarity)."
    ),
) -> None:
    r"""Author a ``derive(conclusion, given=[...])`` support relation.

    Examples:

    .. code-block:: bash

        # Reference an existing conclusion
        gaia author derive --conclusion stars_visible \
            --given clear_night,observer_present \
            --label visibility_warrant

        # Mint a fresh conclusion from prose (R3 prose mode)
        gaia author derive --conclusion-content "Stars are visible tonight." \
            --given clear_night,observer_present \
            --label visibility_warrant

        # Emit prose inline via the engine's Claim|str polymorphism (R6)
        gaia author derive --conclusion-prose "Stars are visible tonight." \
            --given clear_night,observer_present \
            --label visibility_warrant
    """
    del json_

    # --- mutual-exclusion check on conclusion-mode ----------------------- #
    conclusion_modes = [conclusion, conclusion_content, conclusion_prose]
    modes_set = sum(1 for value in conclusion_modes if value is not None)
    if modes_set == 0:
        emit_syntax_error(
            "derive",
            (
                "derive requires exactly one of --conclusion / --conclusion-content / "
                "--conclusion-prose"
            ),
            target=str(target),
            human=human,
        )
        return
    if modes_set > 1:
        emit_syntax_error(
            "derive",
            (
                "--conclusion, --conclusion-content, and --conclusion-prose are "
                "mutually exclusive — pick exactly one"
            ),
            target=str(target),
            human=human,
        )
        return
    if conclusion_label is not None and conclusion_content is None:
        emit_syntax_error(
            "derive",
            "--conclusion-label only applies with --conclusion-content",
            target=str(target),
            human=human,
        )
        return

    metadata_dict, metadata_error = _parse_metadata(metadata)
    if metadata_error:
        diag = Diagnostic(
            kind="prewrite.syntax",
            level="error",
            message=metadata_error,
            source="prewrite",
        )
        result = AuthorResult(
            verb="derive",
            status="error",
            code=exit_code_for_diagnostic(diag.kind),
            payload={"target": str(target)},
            diagnostics=[diag],
        )
        emit(result, human=human)
        return

    given_list = _split_csv(given)
    background_list = _split_csv(background)
    if not given_list:
        diag = Diagnostic(
            kind="prewrite.syntax",
            level="error",
            message="--given must list at least one premise identifier",
            source="prewrite",
        )
        result = AuthorResult(
            verb="derive",
            status="error",
            code=exit_code_for_diagnostic(diag.kind),
            payload={"target": str(target)},
            diagnostics=[diag],
        )
        emit(result, human=human)
        return

    # --- resolve conclusion mode ---------------------------------------- #
    # ``conclusion_expr`` is the Python source spelling that ends up at
    # the call site for the conclusion arg. ``references`` is the list
    # of identifier names that must resolve in module scope — the
    # inline-prose shape contributes no reference at all (the prose is
    # a bare string literal at the call site).
    prepended: tuple[tuple[str, str], ...] = ()
    references: list[str]
    conclusion_kind: str
    if conclusion_content is not None:
        # R3 auto-mint: derive a slug, prepend a ``slug = claim(prose)``
        # statement, use the slug as ``conclusion``. The slug must avoid
        # the verb's own label and the caller-supplied identifiers; the
        # prewrite (c) collision check also runs against module symbols,
        # so a slug collision against an existing binding surfaces as
        # the standard ``prewrite.collision`` error.
        if conclusion_label is not None:
            auto_label = conclusion_label
        else:
            reserved = {label, *given_list, *background_list}
            auto_label = slugify_label(conclusion_content, existing=reserved)
        prepended = ((auto_label, build_auto_claim_statement(auto_label, conclusion_content)),)
        conclusion_expr = auto_label
        references = [auto_label, *given_list, *background_list]
        conclusion_kind = "auto_mint"
    elif conclusion_prose is not None:
        # R6 inline-prose: pass the prose through as a bare string
        # literal. The engine's ``derive(conclusion: Claim | str, ...)``
        # polymorphism wraps it into an anonymous Claim at runtime; no
        # named module-scope binding is introduced. References list
        # omits the prose entirely.
        conclusion_expr = repr(conclusion_prose)
        references = [*given_list, *background_list]
        conclusion_kind = "inline_prose"
    else:
        assert conclusion is not None  # mutex check above
        conclusion_expr = conclusion
        references = [conclusion, *given_list, *background_list]
        conclusion_kind = "qid"

    generated_code = _render_derive_statement(
        label=label,
        conclusion_expr=conclusion_expr,
        given=given_list,
        rationale=rationale,
        metadata=metadata_dict,
        background=background_list,
    )
    proposed_op = ProposedAuthorOp(
        verb="derive",
        kind="reasoning",
        label=label,
        references=references,
        generated_code=generated_code,
        required_imports=("derive",),
        prepended_statements=prepended,
        extra_payload={"conclusion_kind": conclusion_kind},
    )
    run_author_op(
        proposed_op,
        target=target,
        human=human,
        check=check,
        interactive=interactive,
    )


__all__ = ["derive_command"]
