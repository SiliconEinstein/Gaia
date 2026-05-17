"""``gaia author equal`` — append an ``equal(a, b, ...)`` statement.

Maps to ``gaia.engine.lang.dsl.relate.equal``:

.. code-block:: python

    equal(a, b, *, background=None, rationale="", label=None)

R1 binds the helper Claim returned by ``equal`` to a CLI-provided
``--label`` (the underlying DSL function makes ``label`` optional, but
the agent-facing CLI requires it so the produced binding is
referenceable in subsequent author commands).
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


def _render_equal_statement(
    *,
    label: str,
    a: str,
    b: str,
    rationale: str | None,
    metadata: dict[str, Any] | None,
) -> str:
    """Render the proposed ``equal(...)`` statement."""
    args = [a, b]
    kwargs: list[str] = [f"label={label!r}"]
    if rationale:
        kwargs.append(f"rationale={rationale!r}")
    if metadata:
        kwargs.append(f"metadata={metadata!r}")
    return f"{label} = equal({', '.join(args)}, {', '.join(kwargs)})"


def equal_command(
    label: str = typer.Option(..., "--label", help="Identifier the helper Claim binds to."),
    a: str = typer.Option(..., "--a", help="Identifier of the first Claim."),
    b: str = typer.Option(..., "--b", help="Identifier of the second Claim."),
    target: str = typer.Option(
        ".", "--target", help="Path to the target Gaia package (default: cwd)."
    ),
    rationale: str | None = typer.Option(
        None, "--rationale", help="Optional natural-language justification."
    ),
    metadata: str | None = typer.Option(
        None, "--metadata", help="Optional JSON-encoded metadata dict."
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
    r"""Author an ``equal(a, b, ...)`` structural relation.

    Example:

    .. code-block:: bash

        gaia author equal --a heliocentric --b copernican_model \
            --label same_theory --rationale "Re-statement, not new content."
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
            verb="equal",
            status="error",
            code=exit_code_for_diagnostic(diag.kind),
            payload={"target": str(target)},
            diagnostics=[diag],
        )
        emit(result, human=human)
        return

    generated_code = _render_equal_statement(
        label=label,
        a=a,
        b=b,
        rationale=rationale,
        metadata=metadata_dict,
    )
    proposed_op = ProposedAuthorOp(
        verb="equal",
        kind="reasoning",
        label=label,
        references=[a, b],
        generated_code=generated_code,
        required_imports=("equal",),
    )
    run_author_op(
        proposed_op,
        target=target,
        human=human,
        check=check,
        interactive=interactive,
    )


__all__ = ["equal_command"]
