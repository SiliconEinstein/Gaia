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

The cli forwards ``--value`` verbatim — pass a numeric literal
(``--value 0.5``), a string (``--value "'fast'"``), or a Quantity
expression. The flag boundary gates the value through
:func:`parse_literal_or_identifier`; pre-write also parses the rendered
statement as Python before write, so obvious malformations surface as
a syntax error.
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
)
from gaia.cli.commands.author._proposed_op import ProposedAuthorOp
from gaia.cli.commands.author._runner import run_author_op


def _render_parameter_statement(
    *,
    binding_name: str | None,
    engine_label: str | None,
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
    kwargs: list[str] = []
    if engine_label is not None:
        kwargs.append(f"label={engine_label!r}")
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
    rendered_args = ", ".join([*args, *kwargs])
    call = f"parameter({rendered_args})"
    if binding_name is None:
        return call
    return f"{binding_name} = {call}"


def parameter_command(
    label: str | None = typer.Option(
        None,
        "--label",
        help=(
            "Engine `label=` kwarg on the rendered parameter(...) call. "
            "Distinct from --dsl-binding-name (the Python LHS)."
        ),
    ),
    dsl_binding_name: str | None = typer.Option(
        None,
        "--dsl-binding-name",
        help=(
            "Python LHS for the rendered statement (``<name> = "
            "parameter(...)``). Omit to emit a bare expression."
        ),
    ),
    variable: str = typer.Option(..., "--variable", help="Identifier of the bound Variable."),
    value: str = typer.Option(
        ...,
        "--value",
        help="Variable value (literal). Forwarded verbatim — pass `0.5` or `'fast'` etc.",
    ),
    target: str = typer.Option(
        ".", "--target", help="Path to the target Gaia package (default: cwd)."
    ),
    file: str | None = typer.Option(
        None,
        "--file",
        help=("Relative path under src/<import_name>/ to write into. Default: `__init__.py`."),
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
    export: bool = typer.Option(
        True,
        "--export/--no-export",
        help=(
            "Add --dsl-binding-name to __all__ on a successful write "
            "(default on for parameter)."
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
    r"""Append a ``parameter(...)`` Variable-to-value binding.

    Example:

        gaia author parameter --variable my_theta --value 0.5 \
            --dsl-binding-name my_theta_default --prior 0.5
    """
    del json_

    metadata_dict, metadata_error = parse_metadata(metadata)
    if metadata_error:
        emit_syntax_error("parameter", metadata_error, target=str(target), human=human)
        return

    # --value must be a literal or a bare identifier; the rendered
    # statement splices it directly into the parameter() call and the
    # postwrite import would otherwise execute arbitrary Python. The
    # validator pushes a bare identifier into references so prewrite
    # verifies module-scope resolution.
    references: list[str] = [variable]
    try:
        _, rendered_value = parse_literal_or_identifier(value, references_sink=references)
    except PrewriteUnsafeError as exc:
        emit_syntax_error(
            "parameter",
            f"--value rejected: {exc}",
            target=str(target),
            human=human,
            kind="prewrite.expr_unsafe",
        )
        return

    generated_code = _render_parameter_statement(
        binding_name=dsl_binding_name,
        engine_label=label,
        variable=variable,
        value=rendered_value,
        content=content,
        title=title,
        prior=prior,
        rationale=rationale,
        metadata=metadata_dict,
    )
    target_file = normalize_file_option(file)
    proposed_op = ProposedAuthorOp(
        verb="parameter",
        kind="reasoning",
        label=dsl_binding_name,
        references=references,
        generated_code=generated_code,
        required_imports=("parameter",),
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


__all__ = ["parameter_command"]
