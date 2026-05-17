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

The verb supports two CLI shapes for ``conclusion``:

* ``--conclusion <identifier>`` — reference an already-declared Claim.
* ``--conclusion-content "<prose>"`` — cli auto-generates a fresh Claim
  bound to a slug derived from the prose, appends it to the target
  file, then uses the slug as ``conclusion``. Mutually exclusive with
  the above. ``--conclusion-label`` overrides the auto-derived slug.

R3 ships both shapes via the prose-mode helper infra in
:mod:`gaia.cli.commands.author._prose`; the R1·R2 ``--conclusion``
mode is unchanged.
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
    conclusion: str,
    given: list[str],
    rationale: str | None,
    metadata: dict[str, Any] | None,
    background: list[str],
) -> str:
    """Render the proposed ``derive(...)`` statement."""
    given_repr = "[" + ", ".join(given) + "]" if given else "[]"
    args = [conclusion]
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
            "--conclusion. Cli derives a snake-case slug for the label (override via "
            "--conclusion-label)."
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
    """
    del json_

    # --- mutual-exclusion check on conclusion-mode ----------------------- #
    if conclusion is None and conclusion_content is None:
        emit_syntax_error(
            "derive",
            "derive requires exactly one of --conclusion / --conclusion-content",
            target=str(target),
            human=human,
        )
        return
    if conclusion is not None and conclusion_content is not None:
        emit_syntax_error(
            "derive",
            "--conclusion and --conclusion-content are mutually exclusive",
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

    # --- prose mode: mint a fresh conclusion claim ----------------------- #
    prepended: tuple[tuple[str, str], ...] = ()
    if conclusion_content is not None:
        # The cli-derived slug must avoid the verb's own label and the
        # caller-supplied identifiers; the prewrite (c) check also runs
        # against module symbols, so a collision against existing
        # bindings will surface as the standard ``prewrite.collision``
        # error rather than silently colliding.
        if conclusion_label is not None:
            auto_label = conclusion_label
        else:
            reserved = {label, *given_list, *background_list}
            auto_label = slugify_label(conclusion_content, existing=reserved)
        prepended = ((auto_label, build_auto_claim_statement(auto_label, conclusion_content)),)
        resolved_conclusion = auto_label
    else:
        assert conclusion is not None  # mutex check above
        resolved_conclusion = conclusion

    generated_code = _render_derive_statement(
        label=label,
        conclusion=resolved_conclusion,
        given=given_list,
        rationale=rationale,
        metadata=metadata_dict,
        background=background_list,
    )
    references = [resolved_conclusion, *given_list, *background_list]
    proposed_op = ProposedAuthorOp(
        verb="derive",
        kind="reasoning",
        label=label,
        references=references,
        generated_code=generated_code,
        required_imports=("derive",),
        prepended_statements=prepended,
    )
    run_author_op(
        proposed_op,
        target=target,
        human=human,
        check=check,
        interactive=interactive,
    )


__all__ = ["derive_command"]
