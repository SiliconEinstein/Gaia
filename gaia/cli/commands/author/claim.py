"""``gaia author claim`` — append a ``claim(...)`` statement to a Gaia package.

The CLI surface maps to ``gaia.engine.lang.dsl.knowledge.claim``:

.. code-block:: python

    claim(
        content,
        proposition=None,           # BoolExpr (predicate claim) — positional
        *,
        title=None,
        format="markdown",
        background=None,
        parameters=None,
        provenance=None,
        prior=None,
        formula=None,
        ...
    )

R1 covered the prose-claim shape (positional ``content`` + optional
``title`` / ``prior`` / ``metadata`` / ``references``). R3 adds the
predicate-claim shape via ``--predicate "<formula-expr>"``: the cli
sandbox-validates the expression (whitelisted formula primitives +
Distribution factories + ``ClaimAtom`` per
:mod:`gaia.cli.commands.author._formula_sandbox`) and renders it
verbatim as the ``formula=`` kwarg. The naming reads as "predicate
mode" from the agent's point of view; the engine spelling is
``formula=`` (the predicate-logic surface inside ``claim()``).
"""

from __future__ import annotations

import json
from typing import Any

import typer

from gaia.cli.commands.author._common import emit_syntax_error, normalize_file_option
from gaia.cli.commands.author._envelope import (
    AuthorResult,
    Diagnostic,
    emit,
    exit_code_for_diagnostic,
)
from gaia.cli.commands.author._formula_sandbox import (
    FormulaSandboxError,
    validate_formula_expr,
)
from gaia.cli.commands.author._proposed_op import ProposedAuthorOp
from gaia.cli.commands.author._runner import run_author_op


def _format_metadata_kwargs(metadata_json: str | None) -> tuple[dict[str, Any] | None, str | None]:
    """Parse ``--metadata`` JSON (or None) into a Python dict. Returns (dict, error)."""
    if metadata_json is None:
        return None, None
    try:
        parsed = json.loads(metadata_json)
    except json.JSONDecodeError as exc:
        return None, f"--metadata is not valid JSON: {exc}"
    if not isinstance(parsed, dict):
        return None, "--metadata must encode a JSON object (got non-object value)"
    return parsed, None


def _split_csv(value: str | None) -> list[str]:
    """Split a comma-separated CLI option into a clean list of identifiers."""
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def _render_claim_statement(
    *,
    label: str,
    content: str,
    title: str | None,
    prior: float | None,
    metadata: dict[str, Any] | None,
    references: list[str],
    predicate: str | None = None,
) -> str:
    """Produce the Python source for the proposed ``claim(...)`` statement.

    When ``predicate`` is set, the cli renders it as the ``formula=``
    kwarg — the DSL spelling of "predicate-logic claim". The expression
    has already been sandbox-validated by the caller.
    """
    args: list[str] = [repr(content)]
    if title is not None:
        args.append(f"title={title!r}")
    if prior is not None:
        args.append(f"prior={prior!r}")
    if predicate is not None:
        args.append(f"formula={predicate}")
    if references:
        # claim() takes background=[...] for premise context; the CLI's
        # ``--references`` flag is the agent-facing name (same value).
        rendered_refs = "[" + ", ".join(references) + "]"
        args.append(f"background={rendered_refs}")
    if metadata:
        # repr() on a dict produces valid-Python output for plain JSON
        # types (str / int / float / bool / None / list / dict).
        args.append(f"metadata={metadata!r}")
    return f"{label} = claim({', '.join(args)})"


def claim_command(
    content: str = typer.Argument(..., help="Claim content (natural-language statement)."),
    label: str = typer.Option(..., "--label", help="Identifier the statement binds to."),
    target: str = typer.Option(
        ".", "--target", help="Path to the target Gaia package (default: cwd)."
    ),
    file: str | None = typer.Option(
        None,
        "--file",
        help=(
            "Relative path under src/<import_name>/ to write into (e.g. "
            "`priors.py`). Default: `__init__.py`. The file must already "
            "exist; use `gaia pkg add-module` to scaffold a fresh sibling."
        ),
    ),
    title: str | None = typer.Option(None, "--title", help="Optional short title for the claim."),
    prior: float | None = typer.Option(
        None,
        "--prior",
        help=(
            "Optional inline prior in (0, 1); routed through register_prior "
            "with source 'claim_inline'."
        ),
    ),
    metadata: str | None = typer.Option(
        None, "--metadata", help="Optional JSON-encoded metadata dict."
    ),
    references: str | None = typer.Option(
        None,
        "--references",
        help="Comma-separated background references (must resolve in target package).",
    ),
    predicate: str | None = typer.Option(
        None,
        "--predicate",
        help=(
            "Predicate-logic expression rendered as the ``formula=`` kwarg. "
            "Validated by the formula sandbox (whitelist: land/lor/lnot/implies/"
            "iff/equals/forall/exists + ClaimAtom + Distribution factories + "
            "references). Example: `--predicate 'land(ClaimAtom(a), ClaimAtom(b))'`."
        ),
    ),
    check: bool = typer.Option(
        True,
        "--check/--no-check",
        help="Run post-write `gaia build check` after a successful write (default on).",
    ),
    human: bool = typer.Option(
        False,
        "--human",
        help="Render the envelope in human-readable form instead of JSON.",
    ),
    interactive: bool = typer.Option(
        False,
        "--interactive",
        help="Prompt on pre-write warnings (no-op in R1; reserved for R2).",
    ),
    json_: bool = typer.Option(
        True, "--json/--no-json", help="JSON-first output (default; redundant for clarity)."
    ),
) -> None:
    """Author a ``claim(...)`` statement.

    Example:

    .. code-block:: bash

        gaia author claim "The reaction is fast." --label fast_reaction --prior 0.7
    """
    del json_  # JSON-vs-human is governed by `--human`; --json is a courtesy alias.

    metadata_dict, metadata_error = _format_metadata_kwargs(metadata)
    if metadata_error:
        diag = Diagnostic(
            kind="prewrite.syntax",
            level="error",
            message=metadata_error,
            source="prewrite",
        )
        result = AuthorResult(
            verb="claim",
            status="error",
            code=exit_code_for_diagnostic(diag.kind),
            payload={"target": str(target)},
            diagnostics=[diag],
        )
        emit(result, human=human)
        return

    ref_list = _split_csv(references)

    # --- R3 predicate mode: sandbox-validate the formula expression ----- #
    if predicate is not None:
        # Permitted identifiers: the standing whitelist plus user-named
        # references (so ``ClaimAtom(some_ref)`` resolves when
        # ``some_ref`` is on the --references list).
        extra = frozenset(ref_list)
        try:
            validate_formula_expr(predicate, extra_names=extra)
        except FormulaSandboxError as exc:
            emit_syntax_error(
                "claim",
                f"--predicate rejected by sandbox: {exc}",
                target=str(target),
                human=human,
                kind="prewrite.expr_unsafe",
            )
            return

    generated_code = _render_claim_statement(
        label=label,
        content=content,
        title=title,
        prior=prior,
        metadata=metadata_dict,
        references=ref_list,
        predicate=predicate,
    )
    proposed_op = ProposedAuthorOp(
        verb="claim",
        kind="reasoning",
        label=label,
        references=ref_list,
        generated_code=generated_code,
        required_imports=("claim",),
        target_file=normalize_file_option(file),
    )
    run_author_op(
        proposed_op,
        target=target,
        human=human,
        check=check,
        interactive=interactive,
    )


__all__ = ["claim_command"]
