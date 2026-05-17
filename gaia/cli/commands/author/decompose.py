"""``gaia author decompose`` — append a ``decompose(whole, parts=..., formula=...)`` statement.

Maps to ``gaia.engine.lang.dsl.decompose.decompose``:

.. code-block:: python

    decompose(
        whole,
        *,
        parts,
        formula,
        background=None,
        rationale="",
        label=None,
        metadata=None,
    )

The ``formula`` argument is the tricky part — the DSL expects a
:class:`Formula` AST node (``Land`` / ``Lor`` / ``Iff`` / ``Implies`` /
``ClaimAtom`` / ...), not a string. Building one from CLI flags
needs a small mini-DSL; we ship two surfaces:

1. **``--formula-template <kind>``** — pre-baked common shapes built
   from ``--parts`` automatically. Supported kinds:

   * ``atom`` — single-part ``ClaimAtom(<part_0>)``.
   * ``and`` — ``land(ClaimAtom(<p_0>), ClaimAtom(<p_1>), ...)``.
   * ``or`` — ``lor(ClaimAtom(<p_0>), ClaimAtom(<p_1>), ...)``.

2. **``--formula-expr <python>``** — raw Python expression evaluated at
   author time with the ``land`` / ``lor`` / ``lnot`` / ``iff`` /
   ``implies`` / ``ClaimAtom`` helpers in scope plus every part name as
   a local binding. For decompositions whose formula doesn't fit a
   pre-baked template (mixed implication, nested ``iff``, etc.).

Mutually exclusive: exactly one of ``--formula-template`` / ``--formula-expr``
must be set. The pre-write syntax check parses the rendered statement
to catch obvious malformations before the writer touches the file.
"""

from __future__ import annotations

from typing import Any

import typer

from gaia.cli.commands.author._common import emit_syntax_error, parse_metadata, split_csv
from gaia.cli.commands.author._proposed_op import ProposedAuthorOp
from gaia.cli.commands.author._runner import run_author_op

_FORMULA_TEMPLATES = frozenset({"atom", "and", "or"})


def _render_formula_from_template(template: str, parts: list[str]) -> tuple[str | None, str | None]:
    """Render the formula source from a (template, parts) pair.

    Returns ``(formula_source, error)``. On success ``formula_source`` is
    a Python expression that evaluates to a Formula at write time; on
    failure ``error`` carries a human-readable explanation.
    """
    if template not in _FORMULA_TEMPLATES:
        allowed = ", ".join(sorted(_FORMULA_TEMPLATES))
        return None, f"--formula-template must be one of: {allowed} (got {template!r})"
    if template == "atom":
        if len(parts) != 1:
            return None, "--formula-template=atom requires exactly one --parts entry"
        return f"ClaimAtom({parts[0]})", None
    if len(parts) < 2:
        return None, f"--formula-template={template} requires at least two --parts entries"
    atoms = ", ".join(f"ClaimAtom({p})" for p in parts)
    if template == "and":
        return f"land({atoms})", None
    return f"lor({atoms})", None  # template == "or"


def _render_decompose_statement(
    *,
    label: str,
    whole: str,
    parts: list[str],
    formula_src: str,
    rationale: str | None,
    metadata: dict[str, Any] | None,
) -> str:
    """Render the proposed ``decompose(...)`` statement."""
    parts_repr = "[" + ", ".join(parts) + "]"
    args = [whole]
    kwargs = [f"parts={parts_repr}", f"formula={formula_src}", f"label={label!r}"]
    if rationale:
        kwargs.append(f"rationale={rationale!r}")
    if metadata:
        kwargs.append(f"metadata={metadata!r}")
    return f"{label} = decompose({', '.join(args)}, {', '.join(kwargs)})"


def decompose_command(
    label: str = typer.Option(..., "--label", help="Identifier the decomposition action takes."),
    whole: str = typer.Option(
        ..., "--whole", help="Identifier of the composite Claim being decomposed."
    ),
    parts: str = typer.Option(
        ..., "--parts", help="Comma-separated identifiers of atomic Claim parts."
    ),
    target: str = typer.Option(
        ".", "--target", help="Path to the target Gaia package (default: cwd)."
    ),
    formula_template: str | None = typer.Option(
        None,
        "--formula-template",
        help=(
            "Pre-baked formula shape over --parts: atom (single-part), "
            "and (conjunction), or (disjunction)."
        ),
    ),
    formula_expr: str | None = typer.Option(
        None,
        "--formula-expr",
        help=(
            "Raw Python expression for the formula, evaluated at author time with "
            "land/lor/lnot/iff/implies/ClaimAtom plus part names in scope."
        ),
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
    r"""Author a ``decompose(whole, parts=..., formula=...)`` decomposition.

    Example:

    .. code-block:: bash

        gaia author decompose --whole composite --parts atom_a,atom_b \
            --formula-template and --label split_composite
    """
    del json_

    if formula_template is None and formula_expr is None:
        emit_syntax_error(
            "decompose",
            "decompose requires exactly one of --formula-template / --formula-expr",
            target=str(target),
            human=human,
        )
        return
    if formula_template is not None and formula_expr is not None:
        emit_syntax_error(
            "decompose",
            "--formula-template and --formula-expr are mutually exclusive",
            target=str(target),
            human=human,
        )
        return

    metadata_dict, metadata_error = parse_metadata(metadata)
    if metadata_error:
        emit_syntax_error("decompose", metadata_error, target=str(target), human=human)
        return

    part_list = split_csv(parts)
    if not part_list:
        emit_syntax_error(
            "decompose",
            "--parts must list at least one identifier",
            target=str(target),
            human=human,
        )
        return

    if formula_template is not None:
        formula_src, template_error = _render_formula_from_template(formula_template, part_list)
        if template_error:
            emit_syntax_error("decompose", template_error, target=str(target), human=human)
            return
        assert formula_src is not None
    else:
        assert formula_expr is not None
        formula_src = formula_expr

    generated_code = _render_decompose_statement(
        label=label,
        whole=whole,
        parts=part_list,
        formula_src=formula_src,
        rationale=rationale,
        metadata=metadata_dict,
    )
    references = [whole, *part_list]
    proposed_op = ProposedAuthorOp(
        verb="decompose",
        kind="reasoning",
        label=label,
        references=references,
        generated_code=generated_code,
        required_imports=("decompose", "ClaimAtom", "land", "lor"),
    )
    run_author_op(
        proposed_op,
        target=target,
        human=human,
        check=check,
        interactive=interactive,
    )


__all__ = ["decompose_command"]
