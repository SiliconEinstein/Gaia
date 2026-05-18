"""``gaia author contradict`` — append a ``contradict(a, b, ...)`` statement.

Maps to ``gaia.engine.lang.dsl.relate.contradict``:

.. code-block:: python

    contradict(a, b, *, background=None, rationale="", label=None)

Returns a contradiction helper Claim. Same shape as ``equal`` — both
binary Claim references, both produce a helper.
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


def _render_contradict_statement(
    *,
    binding_name: str | None,
    engine_label: str | None,
    a: str,
    b: str,
    rationale: str | None,
    metadata: dict[str, Any] | None,
    background: list[str],
) -> str:
    """Render the proposed ``contradict(...)`` statement."""
    args = [a, b]
    kwargs: list[str] = []
    if engine_label is not None:
        kwargs.append(f"label={engine_label!r}")
    if rationale:
        kwargs.append(f"rationale={rationale!r}")
    if background:
        kwargs.append(f"background=[{', '.join(background)}]")
    if metadata:
        kwargs.append(f"metadata={metadata!r}")
    rendered_args = ", ".join([*args, *kwargs])
    call = f"contradict({rendered_args})"
    if binding_name is None:
        return call
    return f"{binding_name} = {call}"


def contradict_command(
    label: str | None = typer.Option(
        None,
        "--label",
        help=(
            "Engine `label=` kwarg on the rendered contradict(...) call. "
            "Distinct from --dsl-binding-name (the Python LHS)."
        ),
    ),
    dsl_binding_name: str | None = typer.Option(
        None,
        "--dsl-binding-name",
        help=(
            "Python LHS for the rendered statement (``<name> = "
            "contradict(...)``). Omit to emit a bare expression."
        ),
    ),
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
        help="Comma-separated identifiers passed as the contradict() background kwarg.",
    ),
    metadata: str | None = typer.Option(
        None, "--metadata", help="Optional JSON-encoded metadata dict."
    ),
    export: bool = typer.Option(
        True,
        "--export/--no-export",
        help=(
            "Add --dsl-binding-name to __all__ on a successful write "
            "(default on for contradict)."
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
    r"""Append a ``contradict(a, b, ...)`` structural relation.

    Example:
        gaia author contradict --a my_claim_a --b my_claim_b \
            --dsl-binding-name my_contradiction --label my_contradiction
    """
    del json_

    metadata_dict, metadata_error = parse_metadata(metadata)
    if metadata_error:
        emit_syntax_error("contradict", metadata_error, target=str(target), human=human)
        return

    if not validate_identifier_flag(
        a, verb="contradict", flag="--a", target=str(target), human=human
    ):
        return
    if not validate_identifier_flag(
        b, verb="contradict", flag="--b", target=str(target), human=human
    ):
        return

    background_list, background_error = split_csv_idents(background)
    if background_error:
        emit_syntax_error(
            "contradict",
            f"--background rejected: {background_error}",
            target=str(target),
            human=human,
            kind="prewrite.expr_unsafe",
        )
        return
    generated_code = _render_contradict_statement(
        binding_name=dsl_binding_name,
        engine_label=label,
        a=a,
        b=b,
        rationale=rationale,
        metadata=metadata_dict,
        background=background_list,
    )
    target_file = normalize_file_option(file)
    references = [a, b, *background_list]
    proposed_op = ProposedAuthorOp(
        verb="contradict",
        kind="reasoning",
        label=dsl_binding_name,
        references=references,
        generated_code=generated_code,
        required_imports=("contradict",),
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


__all__ = ["contradict_command"]
