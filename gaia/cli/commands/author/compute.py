"""``gaia author compute`` — append a ``compute(...)`` statement.

Maps to ``gaia.engine.lang.dsl.support.compute`` in its imperative form:

.. code-block:: python

    compute(
        conclusion_type,
        *,
        fn=None,
        given=(),
        background=None,
        rationale="",
        label=None,
    )

The decorator form (``@compute``) is a Python-source-level concern —
it requires writing a function body, which the CLI shouldn't synthesise.
The imperative form maps cleanly to flags: ``--conclusion-type`` is the
identifier of a Claim subclass, ``--fn`` is the identifier of a callable
that produces the result, and ``--given`` is the comma-separated
identifier list of premise Claims.
"""

from __future__ import annotations

from typing import Any

import typer

from gaia.cli.commands.author._common import emit_syntax_error, parse_metadata, split_csv
from gaia.cli.commands.author._proposed_op import ProposedAuthorOp
from gaia.cli.commands.author._runner import run_author_op


def _render_compute_statement(
    *,
    label: str,
    conclusion_type: str,
    fn: str | None,
    given: list[str],
    rationale: str | None,
    metadata: dict[str, Any] | None,
) -> str:
    """Render the proposed ``compute(...)`` statement."""
    args = [conclusion_type]
    kwargs: list[str] = []
    if fn is not None:
        kwargs.append(f"fn={fn}")
    if given:
        kwargs.append(f"given=[{', '.join(given)}]")
    kwargs.append(f"label={label!r}")
    if rationale:
        kwargs.append(f"rationale={rationale!r}")
    if metadata:
        kwargs.append(f"metadata={metadata!r}")
    return f"{label} = compute({', '.join(args)}, {', '.join(kwargs)})"


def compute_command(
    label: str = typer.Option(..., "--label", help="Identifier the produced Claim binds to."),
    conclusion_type: str = typer.Option(
        ...,
        "--conclusion-type",
        help="Identifier of the Claim subclass the computation produces (e.g. `Probability`).",
    ),
    target: str = typer.Option(
        ".", "--target", help="Path to the target Gaia package (default: cwd)."
    ),
    fn: str | None = typer.Option(
        None,
        "--fn",
        help="Identifier of a callable producing the result (e.g. `compute_probability`).",
    ),
    given: str | None = typer.Option(
        None,
        "--given",
        help="Comma-separated identifiers of premise Claim(s).",
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
        False, "--human", help="Render the envelope in human-readable form instead of JSON."
    ),
    interactive: bool = typer.Option(
        False, "--interactive", help="Prompt on pre-write warnings (human mode only)."
    ),
    json_: bool = typer.Option(
        True, "--json/--no-json", help="JSON-first output (default; redundant for clarity)."
    ),
) -> None:
    r"""Author a ``compute(...)`` deterministic-computation statement.

    Example:

    .. code-block:: bash

        gaia author compute --label result --conclusion-type Probability \
            --fn compute_prob --given hypothesis_x,hypothesis_y
    """
    del json_

    metadata_dict, metadata_error = parse_metadata(metadata)
    if metadata_error:
        emit_syntax_error("compute", metadata_error, target=str(target), human=human)
        return

    given_list = split_csv(given)
    generated_code = _render_compute_statement(
        label=label,
        conclusion_type=conclusion_type,
        fn=fn,
        given=given_list,
        rationale=rationale,
        metadata=metadata_dict,
    )
    references: list[str] = [conclusion_type, *given_list]
    if fn is not None:
        references.append(fn)
    proposed_op = ProposedAuthorOp(
        verb="compute",
        kind="reasoning",
        label=label,
        references=references,
        generated_code=generated_code,
        required_imports=("compute",),
    )
    run_author_op(
        proposed_op,
        target=target,
        human=human,
        check=check,
        interactive=interactive,
    )


__all__ = ["compute_command"]
