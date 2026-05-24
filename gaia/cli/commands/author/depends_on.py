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

from gaia.cli.commands.author._common import (
    build_sibling_imports,
    emit_syntax_error,
    normalize_file_option,
    parse_metadata,
    split_csv_refs,
    validate_identifier_flag,
)
from gaia.cli.commands.author._proposed_op import ProposedAuthorOp
from gaia.cli.commands.author._runner import run_author_op


def _render_depends_on_statement(
    *,
    binding_name: str | None,
    engine_label: str | None,
    conclusion: str,
    given: list[str],
    rationale: str | None,
    metadata: dict[str, Any] | None,
    background: list[str],
) -> str:
    """Render the proposed ``depends_on(...)`` statement."""
    args = [conclusion]
    given_repr = "[" + ", ".join(given) + "]"
    kwargs = [f"given={given_repr}"]
    if engine_label is not None:
        kwargs.append(f"label={engine_label!r}")
    if rationale:
        kwargs.append(f"rationale={rationale!r}")
    if background:
        kwargs.append(f"background=[{', '.join(background)}]")
    if metadata:
        kwargs.append(f"metadata={metadata!r}")
    rendered_args = ", ".join([*args, *kwargs])
    call = f"depends_on({rendered_args})"
    if binding_name is None:
        return call
    return f"{binding_name} = {call}"


def depends_on_command(
    label: str | None = typer.Option(
        None,
        "--label",
        help=(
            "Engine `label=` kwarg on the rendered depends_on(...) call. "
            "Distinct from --dsl-binding-name (the Python LHS)."
        ),
    ),
    dsl_binding_name: str | None = typer.Option(
        None,
        "--dsl-binding-name",
        help=(
            "Python LHS for the rendered statement (``<name> = "
            "depends_on(...)``). Omit to emit a bare expression."
        ),
    ),
    conclusion: str = typer.Option(..., "--conclusion", help="Identifier of the dependent Claim."),
    given: str = typer.Option(
        ...,
        "--given",
        help=(
            "Comma-separated dependency references: local Claim identifiers "
            "and/or pulled-claim QIDs (lkm:<package>::<label>)."
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
    export: bool = typer.Option(
        False,
        "--export/--no-export",
        help=(
            "Add --dsl-binding-name to __all__ on a successful write "
            "(default off for depends_on: scaffold actions are structural, "
            "not part of the package's public Knowledge surface)."
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
    r"""Append a ``depends_on(...)`` scaffold dependency.

    Example:
        gaia author depends-on --conclusion my_big_claim \
            --given my_small_claim_a,my_small_claim_b \
            --dsl-binding-name my_dependency
    """
    del json_

    metadata_dict, metadata_error = parse_metadata(metadata)
    if metadata_error:
        emit_syntax_error("depends_on", metadata_error, target=str(target), human=human)
        return

    if not validate_identifier_flag(
        conclusion, verb="depends_on", flag="--conclusion", target=str(target), human=human
    ):
        return
    given_refs, given_error = split_csv_refs(given)
    if given_error:
        emit_syntax_error(
            "depends_on",
            f"--given rejected: {given_error}",
            target=str(target),
            human=human,
            kind="prewrite.expr_unsafe",
        )
        return
    given_list = given_refs.rendered
    background_refs, background_error = split_csv_refs(background)
    if background_error:
        emit_syntax_error(
            "depends_on",
            f"--background rejected: {background_error}",
            target=str(target),
            human=human,
            kind="prewrite.expr_unsafe",
        )
        return
    background_list = background_refs.rendered
    if not given_list:
        emit_syntax_error(
            "depends_on",
            "--given must list at least one dependency identifier",
            target=str(target),
            human=human,
        )
        return

    generated_code = _render_depends_on_statement(
        binding_name=dsl_binding_name,
        engine_label=label,
        conclusion=conclusion,
        given=given_list,
        rationale=rationale,
        metadata=metadata_dict,
        background=background_list,
    )
    references = [conclusion, *given_refs.local, *background_refs.local]
    target_file = normalize_file_option(file)
    foreign_imports = tuple(
        (fi.module, fi.symbol, fi.alias)
        for fi in (*given_refs.foreign_imports, *background_refs.foreign_imports)
    )
    proposed_op = ProposedAuthorOp(
        verb="depends_on",
        kind="scaffold",
        label=dsl_binding_name,
        references=references,
        generated_code=generated_code,
        required_imports=("depends_on",),
        target_file=target_file,
        sibling_imports=build_sibling_imports(references, target_file=target_file),
        foreign_imports=foreign_imports,
        export=export,
    )
    run_author_op(
        proposed_op,
        target=target,
        human=human,
        check=check,
        interactive=interactive,
    )


__all__ = ["depends_on_command"]
