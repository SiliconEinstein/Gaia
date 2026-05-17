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
* ``--conclusion-content "<prose>"`` — let ``derive`` mint a fresh Claim
  from a string. Mutually exclusive with the above; pre-write would
  catch the resolution failure either way, but rejecting at flag-parse
  time gives a friendlier error.

R1 ships ``--conclusion`` (identifier mode) only. The free-form prose
mode is R2: it requires the writer to bind the auto-generated label
back into the source, which conflicts with R1's simple "append a single
statement" writer. The CLI surface stays compatible — R2 just adds the
second option.
"""

from __future__ import annotations

import json
from typing import Any

import typer

from gaia.cli.commands.author._envelope import (
    AuthorResult,
    Diagnostic,
    emit,
    exit_code_for_diagnostic,
)
from gaia.cli.commands.author._proposed_op import ProposedAuthorOp
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
    conclusion: str = typer.Option(
        ...,
        "--conclusion",
        help="Identifier of the conclusion Claim (must already be declared).",
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
        help="Prompt on pre-write warnings (no-op in R1; reserved for R2).",
    ),
    json_: bool = typer.Option(
        True, "--json/--no-json", help="JSON-first output (default; redundant for clarity)."
    ),
) -> None:
    r"""Author a ``derive(conclusion, given=[...])`` support relation.

    Example:

    .. code-block:: bash

        gaia author derive --conclusion stars_visible \
            --given clear_night,observer_present \
            --label visibility_warrant
    """
    del json_

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

    generated_code = _render_derive_statement(
        label=label,
        conclusion=conclusion,
        given=given_list,
        rationale=rationale,
        metadata=metadata_dict,
        background=background_list,
    )
    references = [conclusion, *given_list, *background_list]
    proposed_op = ProposedAuthorOp(
        verb="derive",
        kind="reasoning",
        label=label,
        references=references,
        generated_code=generated_code,
        required_imports=("derive",),
    )
    run_author_op(
        proposed_op,
        target=target,
        human=human,
        check=check,
        interactive=interactive,
    )


__all__ = ["derive_command"]
