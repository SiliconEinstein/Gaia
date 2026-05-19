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
exactly two claims, the others are variadic. CLI exposes only the v0.5
variadic shape; the legacy ``(a, b, *, proposed=...)`` form is not
surfaced.
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
)
from gaia.cli.commands.author._proposed_op import ProposedAuthorOp
from gaia.cli.commands.author._runner import run_author_op

_CANDIDATE_PATTERNS = frozenset({"equal", "contradict", "exclusive"})


def _render_candidate_relation_statement(
    *,
    binding_name: str | None,
    engine_label: str | None,
    claims: list[str],
    pattern: str | None,
    rationale: str | None,
    background: list[str],
    metadata: dict[str, Any] | None,
) -> str:
    """Render the proposed ``candidate_relation(...)`` statement."""
    claims_repr = "[" + ", ".join(claims) + "]"
    kwargs = [f"claims={claims_repr}"]
    if engine_label is not None:
        kwargs.append(f"label={engine_label!r}")
    if pattern is not None:
        kwargs.append(f"pattern={pattern!r}")
    if rationale:
        kwargs.append(f"rationale={rationale!r}")
    if background:
        kwargs.append(f"background=[{', '.join(background)}]")
    if metadata:
        kwargs.append(f"metadata={metadata!r}")
    call = f"candidate_relation({', '.join(kwargs)})"
    if binding_name is None:
        return call
    return f"{binding_name} = {call}"


def candidate_relation_command(
    label: str | None = typer.Option(
        None,
        "--label",
        help=(
            "Engine `label=` kwarg on the rendered candidate_relation(...) "
            "call. Distinct from --dsl-binding-name (the Python LHS)."
        ),
    ),
    dsl_binding_name: str | None = typer.Option(
        None,
        "--dsl-binding-name",
        help=(
            "Python LHS for the rendered statement (``<name> = "
            "candidate_relation(...)``). Omit to emit a bare expression."
        ),
    ),
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
    export: bool = typer.Option(
        False,
        "--export/--no-export",
        help=(
            "Add --dsl-binding-name to __all__ on a successful write "
            "(default off for candidate_relation: scaffold-tier output is "
            "structural, not part of the public Knowledge surface)."
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
    r"""Append a ``candidate_relation(...)`` scaffold-tier hypothesised relation.

    Example:
        gaia author candidate-relation \
            --claims my_claim_a,my_claim_b,my_claim_c \
            --pattern equal --dsl-binding-name my_maybe_equal
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

    claim_list, claim_error = split_csv_idents(claims)
    if claim_error:
        emit_syntax_error(
            "candidate_relation",
            f"--claims rejected: {claim_error}",
            target=str(target),
            human=human,
            kind="prewrite.expr_unsafe",
        )
        return
    background_list, background_error = split_csv_idents(background)
    if background_error:
        emit_syntax_error(
            "candidate_relation",
            f"--background rejected: {background_error}",
            target=str(target),
            human=human,
            kind="prewrite.expr_unsafe",
        )
        return
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
        binding_name=dsl_binding_name,
        engine_label=label,
        claims=claim_list,
        pattern=pattern,
        rationale=rationale,
        background=background_list,
        metadata=metadata_dict,
    )
    references = [*claim_list, *background_list]
    target_file = normalize_file_option(file)
    proposed_op = ProposedAuthorOp(
        verb="candidate_relation",
        kind="scaffold",
        label=dsl_binding_name,
        references=references,
        generated_code=generated_code,
        required_imports=("candidate_relation",),
        target_file=target_file,
        sibling_imports=build_sibling_imports(references, target_file=target_file),
        export=export,
    )
    run_author_op(
        proposed_op,
        target=target,
        human=human,
        check=check,
        interactive=interactive,
    )


__all__ = ["candidate_relation_command"]
