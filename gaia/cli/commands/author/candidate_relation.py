"""``gaia author candidate-relation`` — append ``candidate_relation(...)`` statement.

Maps to ``gaia.engine.lang.dsl.scaffold.candidate_relation`` (v0.5 variadic shape):

.. code-block:: python

    candidate_relation(
        *,
        claims,
        pattern=None,
        background=None,
        rationale="",
        label=None,
        metadata=None,
    )

Records a hypothesised relation without triggering formal semantics —
Scaffold tier, no warrants. ``pattern`` (if set) is one of
``equal`` / ``contradict`` / ``exclusive``; ``contradict`` requires
exactly two claims, the others are variadic. CLI hard-cuts to the v0.5
variadic shape per R0·❓-4=A; the legacy ``(a, b, *, proposed=...)``
form is not exposed.
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

_CANDIDATE_PATTERNS = frozenset({"equal", "contradict", "exclusive"})


def _render_candidate_relation_statement(
    *,
    label: str,
    claims: list[str],
    pattern: str | None,
    rationale: str | None,
    background: list[str],
    metadata: dict[str, Any] | None,
) -> str:
    """Render the proposed ``candidate_relation(...)`` statement."""
    claims_repr = "[" + ", ".join(claims) + "]"
    kwargs = [f"claims={claims_repr}", f"label={label!r}"]
    if pattern is not None:
        kwargs.append(f"pattern={pattern!r}")
    if rationale:
        kwargs.append(f"rationale={rationale!r}")
    if background:
        kwargs.append(f"background=[{', '.join(background)}]")
    if metadata:
        kwargs.append(f"metadata={metadata!r}")
    return f"{label} = candidate_relation({', '.join(kwargs)})"


def candidate_relation_command(
    label: str = typer.Option(..., "--label", help="Identifier the scaffold action takes."),
    claims: str = typer.Option(
        ...,
        "--claims",
        help="Comma-separated identifiers of at least two Claim(s).",
    ),
    target: str = typer.Option(
        ".", "--target", help="Path to the target Gaia package (default: cwd)."
    ),
    file: str | None = typer.Option(
        None,
        "--file",
        help=("Relative path under src/<import_name>/ to write into. Default: `__init__.py`."),
    ),
    pattern: str | None = typer.Option(
        None,
        "--pattern",
        help="Optional structural pattern (equal / contradict / exclusive).",
    ),
    rationale: str | None = typer.Option(
        None, "--rationale", help="Optional natural-language justification."
    ),
    background: str | None = typer.Option(
        None, "--background", help="Comma-separated background Knowledge identifiers."
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
    r"""Author a ``candidate_relation(...)`` scaffold-tier hypothesised relation.

    Example:

    .. code-block:: bash

        gaia author candidate-relation --claims a,b,c --pattern equal \
            --label maybe_equal --rationale "Pending materialization."
    """
    del json_

    if pattern is not None and pattern not in _CANDIDATE_PATTERNS:
        allowed = ", ".join(sorted(_CANDIDATE_PATTERNS))
        emit_syntax_error(
            "candidate_relation",
            f"--pattern must be one of: {allowed} (got {pattern!r})",
            target=str(target),
            human=human,
        )
        return

    metadata_dict, metadata_error = parse_metadata(metadata)
    if metadata_error:
        emit_syntax_error("candidate_relation", metadata_error, target=str(target), human=human)
        return

    claim_list = split_csv(claims)
    background_list = split_csv(background)
    if len(claim_list) < 2:
        emit_syntax_error(
            "candidate_relation",
            "--claims must list at least two identifiers",
            target=str(target),
            human=human,
        )
        return
    if pattern == "contradict" and len(claim_list) != 2:
        emit_syntax_error(
            "candidate_relation",
            '--pattern="contradict" requires exactly two --claims entries',
            target=str(target),
            human=human,
        )
        return

    generated_code = _render_candidate_relation_statement(
        label=label,
        claims=claim_list,
        pattern=pattern,
        rationale=rationale,
        background=background_list,
        metadata=metadata_dict,
    )
    references = [*claim_list, *background_list]
    proposed_op = ProposedAuthorOp(
        verb="candidate_relation",
        kind="scaffold",
        label=label,
        references=references,
        generated_code=generated_code,
        required_imports=("candidate_relation",),
        target_file=normalize_file_option(file),
    )
    run_author_op(
        proposed_op,
        target=target,
        human=human,
        check=check,
        interactive=interactive,
    )


__all__ = ["candidate_relation_command"]
