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

**Audit (R2 task item)**: The ``materialize`` signature is the v0.5
newcomer — added in the +35-commit reconcile between R0's audit point
(``841269b4``) and R1's worktree base (``bd59456f``). The signature is
keyword-only on ``by`` and identical in shape to ``depends_on`` /
``candidate_relation`` (label / rationale / metadata kwargs). No quirks;
it folds into the standard Scaffold cli pattern.

CLI surface: ``--scaffold <identifier>`` and ``--by <ident1,ident2,...>``;
the rendered ``by=`` kwarg becomes a Python list literal so identifier
references resolve at engine-import time.
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


def _render_materialize_statement(
    *,
    label: str,
    scaffold: str,
    by: list[str],
    rationale: str | None,
    metadata: dict[str, Any] | None,
) -> str:
    """Render the proposed ``materialize(...)`` statement."""
    by_repr = "[" + ", ".join(by) + "]"
    args = [scaffold]
    kwargs = [f"by={by_repr}", f"label={label!r}"]
    if rationale:
        kwargs.append(f"rationale={rationale!r}")
    if metadata:
        kwargs.append(f"metadata={metadata!r}")
    return f"{label} = materialize({', '.join(args)}, {', '.join(kwargs)})"


def materialize_command(
    label: str = typer.Option(
        ..., "--label", help="Identifier the MaterializationLink action takes."
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
    r"""Author a ``materialize(scaffold, by=...)`` scaffold-to-formal-record link.

    Example:

    .. code-block:: bash

        gaia author materialize --scaffold maybe_equal --by formal_equal \
            --label maybe_equal_materialized --rationale "Pattern matched."
    """
    del json_

    metadata_dict, metadata_error = parse_metadata(metadata)
    if metadata_error:
        emit_syntax_error("materialize", metadata_error, target=str(target), human=human)
        return

    by_list = split_csv(by)
    if not by_list:
        emit_syntax_error(
            "materialize",
            "--by must list at least one materialising record identifier",
            target=str(target),
            human=human,
        )
        return

    generated_code = _render_materialize_statement(
        label=label,
        scaffold=scaffold,
        by=by_list,
        rationale=rationale,
        metadata=metadata_dict,
    )
    references = [scaffold, *by_list]
    proposed_op = ProposedAuthorOp(
        verb="materialize",
        kind="scaffold",
        label=label,
        references=references,
        generated_code=generated_code,
        required_imports=("materialize",),
        target_file=normalize_file_option(file),
    )
    run_author_op(
        proposed_op,
        target=target,
        human=human,
        check=check,
        interactive=interactive,
    )


__all__ = ["materialize_command"]
