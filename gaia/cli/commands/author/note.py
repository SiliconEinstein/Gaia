"""``gaia author note`` — append a ``note(...)`` statement.

Maps to ``gaia.engine.lang.dsl.knowledge.note``:

.. code-block:: python

    note(content, *, title=None, format="markdown", **metadata)

``note`` declares non-probabilistic contextual material — the agent uses
it for background text that does not participate in belief propagation
but contextualises a downstream claim or derivation.
"""

from __future__ import annotations

from typing import Any

import typer

from gaia.cli.commands.author._common import (
    emit_syntax_error,
    normalize_file_option,
    parse_metadata,
)
from gaia.cli.commands.author._proposed_op import ProposedAuthorOp
from gaia.cli.commands.author._runner import run_author_op


def _render_note_statement(
    *,
    binding_name: str | None,
    content: str,
    title: str | None,
    metadata: dict[str, Any] | None,
) -> str:
    """Render the proposed ``note(...)`` statement.

    ``note()`` does not take an engine ``label=`` kwarg (the engine
    signature has only ``**metadata``); only the Python LHS is settable.
    """
    args = [repr(content)]
    if title is not None:
        args.append(f"title={title!r}")
    if metadata:
        # note() takes **metadata, so we flatten the dict literally as kwargs.
        # repr() on a dict produces valid-Python output for plain JSON types.
        args.append(f"metadata={metadata!r}")
    call = f"note({', '.join(args)})"
    if binding_name is None:
        return call
    return f"{binding_name} = {call}"


def note_command(
    content: str = typer.Argument(..., help="Note content (natural-language background)."),
    dsl_binding_name: str | None = typer.Option(
        None,
        "--dsl-binding-name",
        help=(
            "Python module-scope identifier the rendered statement binds to "
            "(``<name> = note(...)``). Omit to emit a bare expression. "
            "``note()`` does not take an engine ``label=`` kwarg, so this "
            "is the only label-like flag the verb exposes."
        ),
    ),
    target: str = typer.Option(
        ".", "--target", help="Path to the target Gaia package (default: cwd)."
    ),
    file: str | None = typer.Option(
        None,
        "--file",
        help=("Relative path under src/<import_name>/ to write into. Default: `__init__.py`."),
    ),
    title: str | None = typer.Option(None, "--title", help="Optional short title for the note."),
    metadata: str | None = typer.Option(
        None, "--metadata", help="Optional JSON-encoded metadata dict."
    ),
    export: bool = typer.Option(
        False,
        "--export/--no-export",
        help=(
            "Add --dsl-binding-name to the target module's __all__ on a "
            "successful write (default off for note: notes are contextual "
            "background, not part of the package's public Knowledge surface)."
        ),
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
    r"""Append a ``note(...)`` background statement.

    Example:

        gaia author note "Earlier work established the setup." \
            --dsl-binding-name background_setup --title "Setup background"
    """
    del json_

    metadata_dict, metadata_error = parse_metadata(metadata)
    if metadata_error:
        emit_syntax_error("note", metadata_error, target=str(target), human=human)
        return

    generated_code = _render_note_statement(
        binding_name=dsl_binding_name,
        content=content,
        title=title,
        metadata=metadata_dict,
    )
    proposed_op = ProposedAuthorOp(
        verb="note",
        kind="reasoning",
        label=dsl_binding_name,
        references=[],
        generated_code=generated_code,
        required_imports=("note",),
        target_file=normalize_file_option(file),
        export=export,
    )
    run_author_op(
        proposed_op,
        target=target,
        human=human,
        check=check,
        interactive=interactive,
    )


__all__ = ["note_command"]
