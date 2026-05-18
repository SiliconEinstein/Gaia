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

from gaia.cli.commands.author._common import (
    PrewriteUnsafeError,
    build_sibling_imports,
    emit_syntax_error,
    normalize_file_option,
    parse_literal_or_identifier,
    parse_metadata,
    split_csv_idents,
)
from gaia.cli.commands.author._proposed_op import ProposedAuthorOp
from gaia.cli.commands.author._runner import run_author_op


def _render_compute_statement(
    *,
    binding_name: str | None,
    engine_label: str | None,
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
    if engine_label is not None:
        kwargs.append(f"label={engine_label!r}")
    if rationale:
        kwargs.append(f"rationale={rationale!r}")
    if metadata:
        kwargs.append(f"metadata={metadata!r}")
    rendered_args = ", ".join([*args, *kwargs])
    call = f"compute({rendered_args})"
    if binding_name is None:
        return call
    return f"{binding_name} = {call}"


def compute_command(
    label: str | None = typer.Option(
        None,
        "--label",
        help=(
            "Engine `label=` kwarg on the rendered compute(...) call. "
            "Distinct from --dsl-binding-name (the Python LHS)."
        ),
    ),
    dsl_binding_name: str | None = typer.Option(
        None,
        "--dsl-binding-name",
        help=(
            "Python LHS for the rendered statement (``<name> = "
            "compute(...)``). Omit to emit a bare expression."
        ),
    ),
    conclusion_type: str = typer.Option(
        ...,
        "--conclusion-type",
        help="Identifier of the Claim subclass the computation produces (e.g. `Probability`).",
    ),
    target: str = typer.Option(
        ".", "--target", help="Path to the target Gaia package (default: cwd)."
    ),
    file: str | None = typer.Option(
        None,
        "--file",
        help=("Relative path under src/<import_name>/ to write into. Default: `__init__.py`."),
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
    export: bool = typer.Option(
        True,
        "--export/--no-export",
        help=(
            "Add --dsl-binding-name to __all__ on a successful write "
            "(default on for compute)."
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
    r"""Append a ``compute(...)`` deterministic-computation statement.

    Example:
        gaia author compute --conclusion-type Probability \
            --fn my_compute_prob --given my_hypothesis_x \
            --dsl-binding-name my_result --label my_result
    """
    del json_

    metadata_dict, metadata_error = parse_metadata(metadata)
    if metadata_error:
        emit_syntax_error("compute", metadata_error, target=str(target), human=human)
        return

    given_list, given_error = split_csv_idents(given)
    if given_error:
        emit_syntax_error(
            "compute",
            f"--given rejected: {given_error}",
            target=str(target),
            human=human,
            kind="prewrite.expr_unsafe",
        )
        return

    # --conclusion-type and --fn both splice into the rendered
    # compute() call. The references list only catches malformed
    # values incidentally (string-membership test against module
    # symbols); add explicit identifier-shape gates here.
    references: list[str] = []
    try:
        _, rendered_conclusion = parse_literal_or_identifier(
            conclusion_type,
            references_sink=references,
        )
    except PrewriteUnsafeError as exc:
        emit_syntax_error(
            "compute",
            f"--conclusion-type rejected: {exc}",
            target=str(target),
            human=human,
            kind="prewrite.expr_unsafe",
        )
        return
    rendered_fn: str | None = None
    if fn is not None:
        try:
            _, rendered_fn = parse_literal_or_identifier(fn, references_sink=references)
        except PrewriteUnsafeError as exc:
            emit_syntax_error(
                "compute",
                f"--fn rejected: {exc}",
                target=str(target),
                human=human,
                kind="prewrite.expr_unsafe",
            )
            return

    generated_code = _render_compute_statement(
        binding_name=dsl_binding_name,
        engine_label=label,
        conclusion_type=rendered_conclusion,
        fn=rendered_fn,
        given=given_list,
        rationale=rationale,
        metadata=metadata_dict,
    )
    references = [*references, *given_list]
    target_file = normalize_file_option(file)
    proposed_op = ProposedAuthorOp(
        verb="compute",
        kind="reasoning",
        label=dsl_binding_name,
        references=references,
        generated_code=generated_code,
        required_imports=("compute",),
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


__all__ = ["compute_command"]
