"""``gaia author depends-on`` — append a ``depends_on(conclusion, given=...)`` statement.

Maps to ``gaia.engine.lang.dsl.scaffold.depends_on``:

.. code-block:: python

    depends_on(
        conclusion,
        *,
        given,
        background=None,
        rationale="",
        label=None,
        metadata=None,
    )

Scaffold-tier verb (no warrants, just records the dependency edge).
Returns the :class:`DependsOn` action; the CLI binds it under the
``--label`` identifier so subsequent statements (e.g. ``materialize``)
can reference it.
"""

from __future__ import annotations

from typing import Any

import typer

from gaia.cli.commands.author._common import emit_syntax_error, parse_metadata, split_csv
from gaia.cli.commands.author._proposed_op import ProposedAuthorOp
from gaia.cli.commands.author._runner import run_author_op


def _render_depends_on_statement(
    *,
    label: str,
    conclusion: str,
    given: list[str],
    rationale: str | None,
    metadata: dict[str, Any] | None,
    background: list[str],
) -> str:
    """Render the proposed ``depends_on(...)`` statement."""
    args = [conclusion]
    given_repr = "[" + ", ".join(given) + "]"
    kwargs = [f"given={given_repr}", f"label={label!r}"]
    if rationale:
        kwargs.append(f"rationale={rationale!r}")
    if background:
        kwargs.append(f"background=[{', '.join(background)}]")
    if metadata:
        kwargs.append(f"metadata={metadata!r}")
    return f"{label} = depends_on({', '.join(args)}, {', '.join(kwargs)})"


def depends_on_command(
    label: str = typer.Option(..., "--label", help="Identifier the scaffold action takes."),
    conclusion: str = typer.Option(..., "--conclusion", help="Identifier of the dependent Claim."),
    given: str = typer.Option(
        ...,
        "--given",
        help="Comma-separated identifiers of dependency Claim(s).",
    ),
    target: str = typer.Option(
        ".", "--target", help="Path to the target Gaia package (default: cwd)."
    ),
    rationale: str | None = typer.Option(
        None, "--rationale", help="Optional natural-language justification."
    ),
    background: str | None = typer.Option(
        None,
        "--background",
        help="Comma-separated background Knowledge identifiers.",
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
    r"""Author a ``depends_on(...)`` scaffold dependency.

    Example:

    .. code-block:: bash

        gaia author depends-on --conclusion big_claim --given small_claim_a,small_claim_b \
            --label big_depends_on_smalls
    """
    del json_

    metadata_dict, metadata_error = parse_metadata(metadata)
    if metadata_error:
        emit_syntax_error("depends_on", metadata_error, target=str(target), human=human)
        return

    given_list = split_csv(given)
    background_list = split_csv(background)
    if not given_list:
        emit_syntax_error(
            "depends_on",
            "--given must list at least one dependency identifier",
            target=str(target),
            human=human,
        )
        return

    generated_code = _render_depends_on_statement(
        label=label,
        conclusion=conclusion,
        given=given_list,
        rationale=rationale,
        metadata=metadata_dict,
        background=background_list,
    )
    references = [conclusion, *given_list, *background_list]
    proposed_op = ProposedAuthorOp(
        verb="depends_on",
        kind="scaffold",
        label=label,
        references=references,
        generated_code=generated_code,
        required_imports=("depends_on",),
    )
    run_author_op(
        proposed_op,
        target=target,
        human=human,
        check=check,
        interactive=interactive,
    )


__all__ = ["depends_on_command"]
