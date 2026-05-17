"""``gaia author question`` — append a ``question(...)`` statement.

Maps to ``gaia.engine.lang.dsl.knowledge.question``:

.. code-block:: python

    question(content, *, title=None, format="markdown", **metadata)

``question`` declares a research question. It does not carry a prior
and does not participate in belief propagation; it marks an open inquiry
that downstream tooling can render or surface.
"""

from __future__ import annotations

from typing import Any

import typer

from gaia.cli.commands.author._common import (
    emit_syntax_error,
    normalize_file_option,
    parse_metadata,
    split_csv,
)
from gaia.cli.commands.author._proposed_op import ProposedAuthorOp
from gaia.cli.commands.author._runner import run_author_op


def _render_question_statement(
    *,
    label: str,
    content: str,
    title: str | None,
    targets: list[str],
    metadata: dict[str, Any] | None,
) -> str:
    """Render the proposed ``question(...)`` statement."""
    args = [repr(content)]
    if title is not None:
        args.append(f"title={title!r}")
    if targets:
        # ``question`` accepts a ``targets`` kwarg routed through **metadata
        # in the DSL; rendered as a Python list of identifier references.
        rendered_targets = "[" + ", ".join(targets) + "]"
        args.append(f"targets={rendered_targets}")
    if metadata:
        args.append(f"metadata={metadata!r}")
    return f"{label} = question({', '.join(args)})"


def question_command(
    content: str = typer.Argument(
        ..., help="Question content (natural-language research question)."
    ),
    label: str = typer.Option(..., "--label", help="Identifier the question binds to."),
    target: str = typer.Option(
        ".", "--target", help="Path to the target Gaia package (default: cwd)."
    ),
    file: str | None = typer.Option(
        None,
        "--file",
        help=("Relative path under src/<import_name>/ to write into. Default: `__init__.py`."),
    ),
    title: str | None = typer.Option(
        None, "--title", help="Optional short title for the question."
    ),
    targets: str | None = typer.Option(
        None,
        "--targets",
        help=(
            "Comma-separated identifiers of claims the question targets (must resolve in package)."
        ),
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
    r"""Author a ``question(...)`` research-question statement.

    Example:

    .. code-block:: bash

        gaia author question "Does X cause Y?" --label rq_x_causes_y \
            --targets hypothesis_x,hypothesis_y
    """
    del json_

    metadata_dict, metadata_error = parse_metadata(metadata)
    if metadata_error:
        emit_syntax_error("question", metadata_error, target=str(target), human=human)
        return

    target_list = split_csv(targets)
    generated_code = _render_question_statement(
        label=label,
        content=content,
        title=title,
        targets=target_list,
        metadata=metadata_dict,
    )
    proposed_op = ProposedAuthorOp(
        verb="question",
        kind="reasoning",
        label=label,
        references=target_list,
        generated_code=generated_code,
        required_imports=("question",),
        target_file=normalize_file_option(file),
    )
    run_author_op(
        proposed_op,
        target=target,
        human=human,
        check=check,
        interactive=interactive,
    )


__all__ = ["question_command"]
