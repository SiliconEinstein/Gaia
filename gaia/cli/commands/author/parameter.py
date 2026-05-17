"""``gaia author parameter`` — append a ``parameter(variable, value, ...)`` statement.

Maps to ``gaia.engine.lang.dsl.sugar.parameter``:

.. code-block:: python

    parameter(
        variable,
        value,
        *,
        content=None,
        describe=None,
        title=None,
        format="markdown",
        background=None,
        provenance=None,
        prior=None,
        label=None,
        metadata=None,
    )

``parameter`` declares that a primitive :class:`Variable` takes a
concrete value. The author binds the variable separately (usually via
``Variable(...)`` in DSL source) and references it by identifier here.
The verb auto-generates an ``equals(variable, value)`` formula behind
the scenes; the CLI surface just forwards the ``variable`` identifier
and ``value`` literal.

R2 forwards ``--value`` verbatim — pass a numeric literal
(``--value 0.5``), a string (``--value "'fast'"``), or a Quantity
expression. Pre-write parses the rendered statement as Python before
write, so obvious malformations still surface as a syntax error.
"""

from __future__ import annotations

from typing import Any

import typer

from gaia.cli.commands.author._common import emit_syntax_error, parse_metadata
from gaia.cli.commands.author._proposed_op import ProposedAuthorOp
from gaia.cli.commands.author._runner import run_author_op


def _render_parameter_statement(
    *,
    label: str,
    variable: str,
    value: str,
    content: str | None,
    title: str | None,
    prior: float | None,
    rationale: str | None,
    metadata: dict[str, Any] | None,
) -> str:
    """Render the proposed ``parameter(...)`` statement."""
    args = [variable, value]
    kwargs = [f"label={label!r}"]
    if content is not None:
        kwargs.append(f"content={content!r}")
    if title is not None:
        kwargs.append(f"title={title!r}")
    if prior is not None:
        kwargs.append(f"prior={prior!r}")
    if rationale is not None:
        # ``parameter`` doesn't define a top-level ``rationale`` kwarg;
        # route it via metadata so the call still parses.
        metadata = dict(metadata or {})
        metadata.setdefault("rationale", rationale)
    if metadata:
        kwargs.append(f"metadata={metadata!r}")
    return f"{label} = parameter({', '.join(args)}, {', '.join(kwargs)})"


def parameter_command(
    label: str = typer.Option(..., "--label", help="Identifier the parameter Claim binds to."),
    variable: str = typer.Option(..., "--variable", help="Identifier of the bound Variable."),
    value: str = typer.Option(
        ...,
        "--value",
        help="Variable value (literal). Forwarded verbatim — pass `0.5` or `'fast'` etc.",
    ),
    target: str = typer.Option(
        ".", "--target", help="Path to the target Gaia package (default: cwd)."
    ),
    content: str | None = typer.Option(
        None, "--content", help="Optional Claim content text (defaults to auto-generated)."
    ),
    title: str | None = typer.Option(
        None, "--title", help="Optional short title for the parameter Claim."
    ),
    prior: float | None = typer.Option(None, "--prior", help="Optional inline prior in (0, 1)."),
    rationale: str | None = typer.Option(
        None,
        "--rationale",
        help="Optional natural-language justification (routed through metadata).",
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
    r"""Author a ``parameter(...)`` Variable-to-value binding.

    Example:

    .. code-block:: bash

        gaia author parameter --variable theta --value 0.5 \
            --label theta_default --prior 0.5
    """
    del json_

    metadata_dict, metadata_error = parse_metadata(metadata)
    if metadata_error:
        emit_syntax_error("parameter", metadata_error, target=str(target), human=human)
        return

    generated_code = _render_parameter_statement(
        label=label,
        variable=variable,
        value=value,
        content=content,
        title=title,
        prior=prior,
        rationale=rationale,
        metadata=metadata_dict,
    )
    proposed_op = ProposedAuthorOp(
        verb="parameter",
        kind="reasoning",
        label=label,
        references=[variable],
        generated_code=generated_code,
        required_imports=("parameter",),
    )
    run_author_op(
        proposed_op,
        target=target,
        human=human,
        check=check,
        interactive=interactive,
    )


__all__ = ["parameter_command"]
