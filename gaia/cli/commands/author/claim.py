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

The cli supports both the prose-claim shape (positional ``content`` +
optional ``title`` / ``prior`` / ``metadata`` / ``references``) and the
predicate-claim shape via ``--formula "<formula-expr>"`` (alias
``--predicate``): the cli sandbox-validates the expression (whitelisted
formula primitives + Distribution factories + ``ClaimAtom`` per
:mod:`gaia.cli.commands.author._formula_sandbox`) and renders it
verbatim as the ``formula=`` kwarg. The naming reads as "predicate
mode" from the agent's point of view; the engine spelling is
``formula=`` (the predicate-logic surface inside ``claim()``).
"""

from __future__ import annotations

import json
from typing import Any

import typer

from gaia.cli.commands.author._common import (
    build_sibling_imports,
    emit_syntax_error,
    normalize_file_option,
    split_csv_idents,
)
from gaia.cli.commands.author._envelope import (
    AuthorResult,
    Diagnostic,
    emit,
    exit_code_for_diagnostic,
)
from gaia.cli.commands.author._formula_sandbox import (
    FormulaSandboxError,
    extract_engine_lang_names,
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


def _render_claim_statement(
    *,
    binding_name: str | None,
    content: str,
    title: str | None,
    prior: float | None,
    metadata: dict[str, Any] | None,
    background: list[str],
    predicate: str | None = None,
    label: str | None = None,
) -> str:
    """Produce the Python source for the proposed ``claim(...)`` statement.

    When ``predicate`` is set, the cli renders it as the ``formula=``
    kwarg — the DSL spelling of "predicate-logic claim". The expression
    has already been sandbox-validated by the caller.

    Only ``background`` populates the rendered ``background=`` kwarg.
    ``--references`` is formula-sandbox-only and is NOT rendered into
    the claim call: this matches the hand-authored mendel pattern of
    using formula-symbols without listing them as Knowledge-background.

    ``claim()`` does not take an engine ``label=`` kwarg (the engine
    signature has only ``**metadata``). When ``label`` is set the cli
    emits a follow-up ``<binding>.label = "<label>"`` assignment after
    the call so the Claim's mutable ``label`` attribute matches the
    hand-authored ``claim_obj.label = ...`` pattern in the example
    packages. The follow-up line requires ``binding_name`` — without an
    LHS there is nothing to mutate; the caller rejects that combination
    at the flag boundary.
    """
    args: list[str] = [repr(content)]
    if title is not None:
        args.append(f"title={title!r}")
    if prior is not None:
        args.append(f"prior={prior!r}")
    if predicate is not None:
        args.append(f"formula={predicate}")
    if background:
        rendered_bg = "[" + ", ".join(background) + "]"
        args.append(f"background={rendered_bg}")
    if metadata:
        # repr() on a dict produces valid-Python output for plain JSON
        # types (str / int / float / bool / None / list / dict).
        args.append(f"metadata={metadata!r}")
    call = f"claim({', '.join(args)})"
    if binding_name is None:
        return call
    rendered = f"{binding_name} = {call}"
    if label is not None:
        rendered += f"\n{binding_name}.label = {label!r}"
    return rendered


def claim_command(
    content: str = typer.Argument(..., help="Claim content (natural-language statement)."),
    dsl_binding_name: str | None = typer.Option(
        None,
        "--dsl-binding-name",
        help=(
            "Python module-scope identifier the rendered statement binds to "
            "(``<name> = claim(...)``). Omit to emit a bare expression "
            "statement. ``claim()`` does not take an engine ``label=`` "
            "kwarg, so this is the only label-like flag the verb exposes."
        ),
    ),
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
            "Optional direct prior in (0, 1), rendered as a prior= kwarg on the "
            "claim() call. Usually omit it: leaf-claim priors are normally "
            "recorded separately via `gaia author register-prior`, which keeps "
            "the belief value out of the claim definition and carries a source "
            "tag. Pass --prior only when a prior belongs inline on the claim "
            "itself."
        ),
    ),
    metadata: str | None = typer.Option(
        None, "--metadata", help="Optional JSON-encoded metadata dict."
    ),
    references: str | None = typer.Option(
        None,
        "--references",
        help=(
            "Comma-separated identifiers to whitelist inside the formula "
            "sandbox (no effect when --formula / --predicate is absent). "
            "References are NOT rendered into the claim's `background=` "
            "kwarg — use --background for that. Typical shape: "
            "`--references f2_total_count,f2_dominant_count "
            "--formula 'equals(f2_total_count, Constant(395, Nat))'`."
        ),
    ),
    background: str | None = typer.Option(
        None,
        "--background",
        help=(
            "Comma-separated Knowledge identifiers passed to the rendered "
            "claim's `background=[...]` kwarg. Pre-write resolves each "
            "identifier in module scope. Independent of --references "
            "(--references is sandbox-only and not rendered into the "
            "claim call)."
        ),
    ),
    predicate: str | None = typer.Option(
        None,
        "--predicate",
        help=(
            "Alias for --formula (predicate-mode shape). Backwards-compatible "
            "spelling; prefer --formula for new authoring."
        ),
    ),
    formula: str | None = typer.Option(
        None,
        "--formula",
        help=(
            "Predicate-logic expression rendered as the ``formula=`` kwarg. "
            "Validated by the formula sandbox (whitelist: land/lor/lnot/implies/"
            "iff/equals/forall/exists + ClaimAtom + Distribution factories + "
            "Variable/Constant + Nat/Real/Bool/Probability + references). "
            "Example: `--formula 'land(equals(my_var, Constant(395, Nat)), "
            "ClaimAtom(p))'`. Mutually exclusive with --predicate."
        ),
    ),
    label: str | None = typer.Option(
        None,
        "--label",
        help=(
            "Optional Claim label. ``claim()`` does not take an engine "
            "``label=`` kwarg, so the cli emits a follow-up "
            "``<binding>.label = '<label>'`` assignment line after the "
            "rendered ``claim(...)`` call — matching the hand-authored "
            "pattern in the example packages. Requires --dsl-binding-name "
            "(no LHS means nothing to mutate)."
        ),
    ),
    export: bool = typer.Option(
        True,
        "--export/--no-export",
        help=(
            "Add --dsl-binding-name to the target module's __all__ on a "
            "successful write (default on for claim: claims are referenceable "
            "Knowledge bindings other verbs cite by name)."
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
        help="Prompt on pre-write warnings (currently a no-op; reserved for future use).",
    ),
    json_: bool = typer.Option(
        True, "--json/--no-json", help="JSON-first output (default; redundant for clarity)."
    ),
) -> None:
    r"""Append a ``claim(...)`` Knowledge declaration.

    Example:
        gaia author claim "The reaction is fast." \
            --dsl-binding-name fast_reaction --prior 0.7
    """
    del json_  # JSON-vs-human is governed by `--human`; --json is a courtesy alias.

    if label is not None and dsl_binding_name is None:
        emit_syntax_error(
            "claim",
            "--label requires --dsl-binding-name (the follow-up "
            "`<binding>.label = ...` line needs an LHS to mutate)",
            target=str(target),
            human=human,
        )
        return

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

    ref_list, ref_error = split_csv_idents(references)
    if ref_error:
        emit_syntax_error(
            "claim",
            f"--references rejected: {ref_error}",
            target=str(target),
            human=human,
            kind="prewrite.expr_unsafe",
        )
        return
    background_list, background_error = split_csv_idents(background)
    if background_error:
        emit_syntax_error(
            "claim",
            f"--background rejected: {background_error}",
            target=str(target),
            human=human,
            kind="prewrite.expr_unsafe",
        )
        return

    # --- formula mode: sandbox-validate the formula expression ---------- #
    if predicate is not None and formula is not None:
        emit_syntax_error(
            "claim",
            "--predicate and --formula are aliases — pass only one",
            target=str(target),
            human=human,
        )
        return
    # Canonical name is --formula; --predicate stays as a
    # backwards-compatible alias. The render path treats them
    # interchangeably.
    formula_expr = formula if formula is not None else predicate
    if formula_expr is not None:
        # Permitted identifiers: the standing whitelist plus user-named
        # references (so ``ClaimAtom(some_ref)`` resolves when
        # ``some_ref`` is on the --references list). Background
        # identifiers are also permitted in the formula sandbox: a user
        # who lists a Knowledge claim in --background may still reference
        # it inside a ClaimAtom(...) inside the formula.
        extra = frozenset(ref_list) | frozenset(background_list)
        try:
            validate_formula_expr(formula_expr, extra_names=extra)
        except FormulaSandboxError as exc:
            arg_label = "--formula" if formula is not None else "--predicate"
            emit_syntax_error(
                "claim",
                f"{arg_label} rejected by sandbox: {exc}",
                target=str(target),
                human=human,
                kind="prewrite.expr_unsafe",
            )
            return

    generated_code = _render_claim_statement(
        binding_name=dsl_binding_name,
        content=content,
        title=title,
        prior=prior,
        metadata=metadata_dict,
        background=background_list,
        predicate=formula_expr,
        label=label,
    )
    # Pre-write resolves BOTH --references (formula-sandbox identifiers)
    # and --background (rendered kwarg identifiers) against module scope.
    # Both lists must point at already-bound names; the difference is
    # the rendered output (background appears in the claim's
    # ``background=``; references stay sandbox-only).
    op_references = list(dict.fromkeys((*ref_list, *background_list)))
    target_file = normalize_file_option(file)
    # Extend the required-imports tuple with any formula-primitive names
    # (``land`` / ``equals`` / ``Constant`` / ``Nat`` / ...) referenced
    # inside the validated formula expression. The G1 writer step then
    # inserts the missing names into the rendered ``from gaia.engine.lang
    # import (...)`` line so the postwrite check can import the module
    # cleanly without an explicit ``--imports`` flag at scaffold time.
    formula_imports = extract_engine_lang_names(formula_expr) if formula_expr is not None else ()
    required_imports = ("claim", *formula_imports)
    proposed_op = ProposedAuthorOp(
        verb="claim",
        kind="reasoning",
        label=dsl_binding_name,
        references=op_references,
        generated_code=generated_code,
        required_imports=required_imports,
        target_file=target_file,
        sibling_imports=build_sibling_imports(op_references, target_file=target_file),
        export=export,
    )
    run_author_op(
        proposed_op,
        target=target,
        human=human,
        check=check,
        interactive=interactive,
    )


__all__ = ["claim_command"]
