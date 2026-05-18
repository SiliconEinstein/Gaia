"""``gaia author materialize`` — append a ``materialize(scaffold, by=...)`` statement.

Maps to ``gaia.engine.lang.dsl.scaffold.materialize``:

.. code-block:: python

    materialize(
        scaffold,
        *,
        by,
        rationale="",
        label=None,
        metadata=None,
    )

Records a checked link from a scaffold action (``DependsOn`` /
``CandidateRelation``) to one or more formal graph records that
materialise it. The DSL enforces:

* The ``scaffold`` argument must be a registered ``Scaffold`` instance.
* Every ``by`` entry must belong to the same package and be either a
  :class:`GaiaGraph` instance, a :class:`Claim` (resolved to its
  producing graph record), or a string label that uniquely matches a
  graph record.
* At least one ``by`` record must reference one of the scaffold's core
  claims.
* If the scaffold carries a ``pattern`` (``equal`` / ``contradict`` /
  ``exclusive``), the materialising records' patterns must be
  consistent with it.

The ``materialize`` signature is keyword-only on ``by`` and identical in
shape to ``depends_on`` / ``candidate_relation`` (label / rationale /
metadata kwargs).

CLI surface: ``--scaffold <identifier>`` and ``--by <ident1,ident2,...>``;
the rendered ``by=`` kwarg becomes a Python list literal so identifier
references resolve at engine-import time.
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


def _render_materialize_statement(
    *,
    binding_name: str | None,
    engine_label: str | None,
    scaffold: str,
    by: list[str],
    rationale: str | None,
    metadata: dict[str, Any] | None,
) -> str:
    """Render the proposed ``materialize(...)`` statement."""
    by_repr = "[" + ", ".join(by) + "]"
    args = [scaffold]
    kwargs = [f"by={by_repr}"]
    if engine_label is not None:
        kwargs.append(f"label={engine_label!r}")
    if rationale:
        kwargs.append(f"rationale={rationale!r}")
    if metadata:
        kwargs.append(f"metadata={metadata!r}")
    rendered_args = ", ".join([*args, *kwargs])
    call = f"materialize({rendered_args})"
    if binding_name is None:
        return call
    return f"{binding_name} = {call}"


def materialize_command(
    label: str | None = typer.Option(
        None,
        "--label",
        help=(
            "Engine `label=` kwarg on the rendered materialize(...) call. "
            "Distinct from --dsl-binding-name (the Python LHS)."
        ),
    ),
    dsl_binding_name: str | None = typer.Option(
        None,
        "--dsl-binding-name",
        help=(
            "Python LHS for the rendered statement (``<name> = "
            "materialize(...)``). Omit to emit a bare expression."
        ),
    ),
    scaffold: str = typer.Option(
        ...,
        "--scaffold",
        help="Identifier of the registered Scaffold (DependsOn / CandidateRelation).",
    ),
    by: str = typer.Option(
        ...,
        "--by",
        help="Comma-separated identifiers of formal graph records that materialise the scaffold.",
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
    metadata: str | None = typer.Option(
        None, "--metadata", help="Optional JSON-encoded metadata dict."
    ),
    export: bool = typer.Option(
        False,
        "--export/--no-export",
        help=(
            "Add --dsl-binding-name to __all__ on a successful write "
            "(default off for materialize: the link is structural metadata, "
            "not part of the public Knowledge surface)."
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
    r"""Append a ``materialize(scaffold, by=...)`` scaffold-to-formal-record link.

    Example:
        gaia author materialize --scaffold my_maybe_equal \
            --by my_formal_equal --dsl-binding-name my_materialization
    """
    del json_

    metadata_dict, metadata_error = parse_metadata(metadata)
    if metadata_error:
        emit_syntax_error("materialize", metadata_error, target=str(target), human=human)
        return

    if not validate_identifier_flag(
        scaffold, verb="materialize", flag="--scaffold", target=str(target), human=human
    ):
        return
    by_list, by_error = split_csv_idents(by)
    if by_error:
        emit_syntax_error(
            "materialize",
            f"--by rejected: {by_error}",
            target=str(target),
            human=human,
            kind="prewrite.expr_unsafe",
        )
        return
    if not by_list:
        emit_syntax_error(
            "materialize",
            "--by must list at least one materialising record identifier",
            target=str(target),
            human=human,
        )
        return

    generated_code = _render_materialize_statement(
        binding_name=dsl_binding_name,
        engine_label=label,
        scaffold=scaffold,
        by=by_list,
        rationale=rationale,
        metadata=metadata_dict,
    )
    references = [scaffold, *by_list]
    target_file = normalize_file_option(file)
    proposed_op = ProposedAuthorOp(
        verb="materialize",
        kind="scaffold",
        label=dsl_binding_name,
        references=references,
        generated_code=generated_code,
        required_imports=("materialize",),
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


__all__ = ["materialize_command"]
