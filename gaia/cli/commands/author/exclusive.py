"""``gaia author exclusive`` — append an ``exclusive(a, b, ...)`` statement.

Maps to ``gaia.engine.lang.dsl.relate.exclusive``:

.. code-block:: python

    exclusive(a, b, *, background=None, rationale="", label=None)

Declares two Claims as a closed binary partition (exactly one is true).
Returns an XOR helper Claim. Surface is identical to ``equal`` /
``contradict``.
"""

from __future__ import annotations

from typing import Any

import typer

from gaia.cli.commands.author._common import (
    build_sibling_imports,
    emit_syntax_error,
    normalize_file_option,
    parse_metadata,
    split_csv_idents,
    validate_identifier_flag,
)
from gaia.cli.commands.author._proposed_op import ProposedAuthorOp
from gaia.cli.commands.author._runner import run_author_op


def _render_exclusive_statement(
    *,
    label: str,
    a: str,
    b: str,
    rationale: str | None,
    metadata: dict[str, Any] | None,
    background: list[str],
) -> str:
    """Render the proposed ``exclusive(...)`` statement."""
    args = [a, b]
    kwargs: list[str] = [f"label={label!r}"]
    if rationale:
        kwargs.append(f"rationale={rationale!r}")
    if background:
        kwargs.append(f"background=[{', '.join(background)}]")
    if metadata:
        kwargs.append(f"metadata={metadata!r}")
    return f"{label} = exclusive({', '.join(args)}, {', '.join(kwargs)})"


def exclusive_command(
    label: str = typer.Option(..., "--label", help="Identifier the helper Claim binds to."),
    a: str = typer.Option(..., "--a", help="Identifier of the first Claim."),
    b: str = typer.Option(..., "--b", help="Identifier of the second Claim."),
    target: str = typer.Option(
        ".", "--target", help="Path to the target Gaia package (default: cwd)."
    ),
    file: str | None = typer.Option(
        None,
        "--file",
        help=("Relative path under src/<import_name>/ to write into. Default: `__init__.py`."),
    ),
    rationale: str | None = typer.Option(
        None, "--rationale", help="Optional natural-language justification."
    ),
    background: str | None = typer.Option(
        None,
        "--background",
        help="Comma-separated identifiers passed as the exclusive() background kwarg.",
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
        False, "--human", help="Render the envelope in human-readable form instead of JSON."
    ),
    interactive: bool = typer.Option(
        False, "--interactive", help="Prompt on pre-write warnings (human mode only)."
    ),
    json_: bool = typer.Option(
        True, "--json/--no-json", help="JSON-first output (default; redundant for clarity)."
    ),
) -> None:
    r"""Author an ``exclusive(a, b, ...)`` closed-partition statement.

    Example:

    .. code-block:: bash

        gaia author exclusive --a coin_heads --b coin_tails \
            --label coin_outcome --rationale "Exactly one of heads/tails per flip."
    """
    del json_

    metadata_dict, metadata_error = parse_metadata(metadata)
    if metadata_error:
        emit_syntax_error("exclusive", metadata_error, target=str(target), human=human)
        return

    if not validate_identifier_flag(
        a, verb="exclusive", flag="--a", target=str(target), human=human
    ):
        return
    if not validate_identifier_flag(
        b, verb="exclusive", flag="--b", target=str(target), human=human
    ):
        return

    background_list, background_error = split_csv_idents(background)
    if background_error:
        emit_syntax_error(
            "exclusive",
            f"--background rejected: {background_error}",
            target=str(target),
            human=human,
            kind="prewrite.expr_unsafe",
        )
        return
    generated_code = _render_exclusive_statement(
        label=label,
        a=a,
        b=b,
        rationale=rationale,
        metadata=metadata_dict,
        background=background_list,
    )
    target_file = normalize_file_option(file)
    references = [a, b, *background_list]
    proposed_op = ProposedAuthorOp(
        verb="exclusive",
        kind="reasoning",
        label=label,
        references=references,
        generated_code=generated_code,
        required_imports=("exclusive",),
        target_file=target_file,
        sibling_imports=build_sibling_imports(references, target_file=target_file),
    )
    run_author_op(
        proposed_op,
        target=target,
        human=human,
        check=check,
        interactive=interactive,
    )


__all__ = ["exclusive_command"]
