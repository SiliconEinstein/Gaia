"""``gaia author derive`` — append a ``derive(conclusion, given=[...])`` statement.

Maps to ``gaia.engine.lang.dsl.support.derive``:

.. code-block:: python

    derive(
        conclusion,
        *,
        given=(),
        background=None,
        rationale="",
        label=None,
    )

The verb supports three CLI shapes for ``conclusion``:

* ``--conclusion <identifier>`` — reference an already-declared Claim.
* ``--conclusion-content "<prose>"`` — cli auto-generates a fresh Claim
  bound to a slug derived from the prose, appends it to the target
  file, then uses the slug as ``conclusion``. ``--conclusion-label``
  overrides the auto-derived slug.
* ``--conclusion-prose "<prose>"`` — emits ``derive('<prose>', ...)``
  directly, leveraging the engine's ``conclusion: Claim | str``
  polymorphism. Skips the separate ``slug = claim(prose)`` declaration
  the auto-mint shape introduces; the prose flows to the DSL call site
  as a bare string literal. A named module-scope binding is still
  produced when ``--dsl-binding-name`` is supplied (the derive() result
  is the warrant Claim that downstream verbs reference).

The three shapes are mutually exclusive — pick exactly one. The
auto-mint shape uses the prose-mode helper infra in
:mod:`gaia.cli.commands.author._prose`; the inline-prose shape closes
the Galileo strict-reproducibility divergence around named Claim
bindings introduced by auto-mint.

Two ``label``-like surfaces (clean split):

* ``--label <engine-label>`` — passed through as the engine's ``label=``
  kwarg on the rendered ``derive(...)`` call. Does not affect the
  Python module-scope binding name.
* ``--dsl-binding-name <python-ident>`` — Python binding produced on the
  rendered statement (``<python-ident> = derive(...)``). When omitted,
  the rendered statement is a bare expression with no LHS binding (the
  engine's ``derive()`` result is held only by transitive Claim
  references inside the IR).
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
from gaia.cli.commands.author._proposed_op import ProposedAuthorOp
from gaia.cli.commands.author._prose import build_auto_claim_statement, slugify_label
from gaia.cli.commands.author._runner import run_author_op


def _parse_metadata(metadata_json: str | None) -> tuple[dict[str, Any] | None, str | None]:
    if metadata_json is None:
        return None, None
    try:
        parsed = json.loads(metadata_json)
    except json.JSONDecodeError as exc:
        return None, f"--metadata is not valid JSON: {exc}"
    if not isinstance(parsed, dict):
        return None, "--metadata must encode a JSON object (got non-object value)"
    return parsed, None


def _render_derive_statement(
    *,
    binding_name: str | None,
    engine_label: str | None,
    conclusion_expr: str,
    given: list[str],
    rationale: str | None,
    metadata: dict[str, Any] | None,
    background: list[str],
) -> str:
    """Render the proposed ``derive(...)`` statement.

    ``conclusion_expr`` is the *Python source* spelling that the call
    site uses for the conclusion argument: either a bare identifier
    (``--conclusion`` / ``--conclusion-content`` auto-mint slug) or a
    quoted string literal (``--conclusion-prose``). The caller is
    responsible for shaping the spelling before handing it in.

    ``binding_name`` is the Python module-scope identifier the rendered
    statement binds to (``<binding_name> = derive(...)``); ``None``
    renders a bare expression statement. ``engine_label`` is the
    ``derive()`` ``label=`` kwarg; ``None`` omits it.
    """
    given_repr = "[" + ", ".join(given) + "]" if given else "[]"
    args = [conclusion_expr]
    kwargs = [f"given={given_repr}"]
    if engine_label is not None:
        kwargs.append(f"label={engine_label!r}")
    if rationale:
        kwargs.append(f"rationale={rationale!r}")
    if background:
        bg_repr = "[" + ", ".join(background) + "]"
        kwargs.append(f"background={bg_repr}")
    if metadata:
        kwargs.append(f"metadata={metadata!r}")
    call = f"derive({', '.join(args)}, {', '.join(kwargs)})"
    if binding_name is None:
        return call
    return f"{binding_name} = {call}"


def derive_command(
    conclusion: str | None = typer.Option(
        None,
        "--conclusion",
        help="Identifier of the conclusion Claim (must already be declared).",
    ),
    conclusion_content: str | None = typer.Option(
        None,
        "--conclusion-content",
        help=(
            "Prose for an auto-generated conclusion Claim. Mutually exclusive with "
            "--conclusion and --conclusion-prose. Cli derives a snake-case slug for "
            "the label (override via --conclusion-label)."
        ),
    ),
    conclusion_label: str | None = typer.Option(
        None,
        "--conclusion-label",
        help=(
            "Optional explicit label for the auto-generated conclusion Claim "
            "(only meaningful with --conclusion-content)."
        ),
    ),
    conclusion_prose: str | None = typer.Option(
        None,
        "--conclusion-prose",
        help=(
            "Inline prose passed to the engine's ``derive(conclusion: Claim | str, "
            "...)`` polymorphism. Emits ``derive('<prose>', ...)`` directly with no "
            "named binding. Mutually exclusive with --conclusion and "
            "--conclusion-content."
        ),
    ),
    given: str = typer.Option(
        ...,
        "--given",
        help="Comma-separated identifiers of the premise Claim(s) the conclusion is derived from.",
    ),
    label: str | None = typer.Option(
        None,
        "--label",
        help=(
            "Engine `label=` kwarg passed through to the rendered derive(...) "
            "call. Distinct from --dsl-binding-name (the Python LHS). Omit "
            "both to render derive(...) without a label= kwarg and no LHS."
        ),
    ),
    dsl_binding_name: str | None = typer.Option(
        None,
        "--dsl-binding-name",
        help=(
            "Python module-scope identifier the rendered statement binds to "
            "(``<name> = derive(...)``). Omit to emit a bare expression "
            "statement (no LHS); the derive() result is then only reachable "
            "via transitive Claim references in the IR."
        ),
    ),
    target: str = typer.Option(
        ".", "--target", help="Path to the target Gaia package (default: cwd)."
    ),
    file: str | None = typer.Option(
        None,
        "--file",
        help=("Path under src/<import_name>/authored/. Default: authored/__init__.py."),
    ),
    rationale: str | None = typer.Option(
        None, "--rationale", help="Optional natural-language justification of the derivation."
    ),
    metadata: str | None = typer.Option(
        None, "--metadata", help="Optional JSON-encoded metadata dict."
    ),
    background: str | None = typer.Option(
        None,
        "--background",
        help="Comma-separated identifiers passed as the derive() background kwarg.",
    ),
    export: bool = typer.Option(
        True,
        "--export/--no-export",
        help=(
            "Append --dsl-binding-name to the target module's __all__ on a "
            "successful write (default on for derive: its result is a warrant "
            "Claim downstream verbs reference)."
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
        help="Prompt on pre-write warnings (human mode only).",
    ),
    json_: bool = typer.Option(
        True, "--json/--no-json", help="JSON-first output (default; redundant for clarity)."
    ),
) -> None:
    r"""Append a ``derive(conclusion, given=[...])`` support relation.

    Example:
        gaia author derive --conclusion-content "B follows from A." \
            --given my_claim_a \
            --dsl-binding-name my_derivation \
            --label my_derivation_path
    """
    del json_

    # --- mutual-exclusion check on conclusion-mode ----------------------- #
    conclusion_modes = [conclusion, conclusion_content, conclusion_prose]
    modes_set = sum(1 for value in conclusion_modes if value is not None)
    if modes_set == 0:
        emit_syntax_error(
            "derive",
            (
                "derive requires exactly one of --conclusion / --conclusion-content / "
                "--conclusion-prose"
            ),
            target=str(target),
            human=human,
        )
        return
    if modes_set > 1:
        emit_syntax_error(
            "derive",
            (
                "--conclusion, --conclusion-content, and --conclusion-prose are "
                "mutually exclusive — pick exactly one"
            ),
            target=str(target),
            human=human,
        )
        return
    if conclusion_label is not None and conclusion_content is None:
        emit_syntax_error(
            "derive",
            "--conclusion-label only applies with --conclusion-content",
            target=str(target),
            human=human,
        )
        return

    metadata_dict, metadata_error = _parse_metadata(metadata)
    if metadata_error:
        diag = Diagnostic(
            kind="prewrite.syntax",
            level="error",
            message=metadata_error,
            source="prewrite",
        )
        result = AuthorResult(
            verb="derive",
            status="error",
            code=exit_code_for_diagnostic(diag.kind),
            payload={"target": str(target)},
            diagnostics=[diag],
        )
        emit(result, human=human)
        return

    given_list, given_error = split_csv_idents(given)
    if given_error:
        emit_syntax_error(
            "derive",
            f"--given rejected: {given_error}",
            target=str(target),
            human=human,
            kind="prewrite.expr_unsafe",
        )
        return
    background_list, background_error = split_csv_idents(background)
    if background_error:
        emit_syntax_error(
            "derive",
            f"--background rejected: {background_error}",
            target=str(target),
            human=human,
            kind="prewrite.expr_unsafe",
        )
        return
    if not given_list:
        diag = Diagnostic(
            kind="prewrite.syntax",
            level="error",
            message="--given must list at least one premise identifier",
            source="prewrite",
        )
        result = AuthorResult(
            verb="derive",
            status="error",
            code=exit_code_for_diagnostic(diag.kind),
            payload={"target": str(target)},
            diagnostics=[diag],
        )
        emit(result, human=human)
        return

    # --- resolve conclusion mode ---------------------------------------- #
    # ``conclusion_expr`` is the Python source spelling that ends up at
    # the call site for the conclusion arg. ``references`` is the list
    # of identifier names that must resolve in module scope — the
    # inline-prose shape contributes no reference at all (the prose is
    # a bare string literal at the call site).
    prepended: tuple[tuple[str, str], ...] = ()
    references: list[str]
    conclusion_kind: str
    if conclusion_content is not None:
        # Auto-mint: derive a slug, prepend a ``slug = claim(prose)``
        # statement, use the slug as ``conclusion``. The slug must avoid
        # the caller-supplied identifiers; the prewrite (c) collision
        # check also runs against module symbols, so a slug collision
        # against an existing binding surfaces as the standard
        # ``prewrite.collision`` error.
        if conclusion_label is not None:
            auto_label = conclusion_label
        else:
            reserved = {*given_list, *background_list}
            if dsl_binding_name is not None:
                reserved.add(dsl_binding_name)
            auto_label = slugify_label(conclusion_content, existing=reserved)
        prepended = ((auto_label, build_auto_claim_statement(auto_label, conclusion_content)),)
        conclusion_expr = auto_label
        references = [auto_label, *given_list, *background_list]
        conclusion_kind = "auto_mint"
    elif conclusion_prose is not None:
        # Inline-prose: pass the prose through as a bare string
        # literal. The engine's ``derive(conclusion: Claim | str, ...)``
        # polymorphism wraps it into an anonymous Claim at runtime; no
        # auto-claim binding is prepended. References list omits the
        # prose entirely.
        conclusion_expr = repr(conclusion_prose)
        references = [*given_list, *background_list]
        conclusion_kind = "inline_prose"
    else:
        assert conclusion is not None  # mutex check above
        conclusion_expr = conclusion
        references = [conclusion, *given_list, *background_list]
        conclusion_kind = "qid"

    generated_code = _render_derive_statement(
        binding_name=dsl_binding_name,
        engine_label=label,
        conclusion_expr=conclusion_expr,
        given=given_list,
        rationale=rationale,
        metadata=metadata_dict,
        background=background_list,
    )
    target_file = normalize_file_option(file)
    proposed_op = ProposedAuthorOp(
        verb="derive",
        kind="reasoning",
        label=dsl_binding_name,
        references=references,
        generated_code=generated_code,
        required_imports=("derive",),
        target_file=target_file,
        sibling_imports=build_sibling_imports(references, target_file=target_file),
        prepended_statements=prepended,
        extra_payload={"conclusion_kind": conclusion_kind},
        export=export,
    )
    run_author_op(
        proposed_op,
        target=target,
        human=human,
        check=check,
        interactive=interactive,
    )


# Human-readable epilog appended to the rich-help output so authors see
# a one-line decision tree across the three --conclusion-* shapes
# before scanning each flag's individual help text.
_EPILOG_WHEN_TO_USE = """

When to use which --conclusion-* flag:

    --conclusion <label>           Reference an existing Claim by its
                                   label. Use when the conclusion was
                                   already authored with `gaia author
                                   claim` and you want to link to it.
    --conclusion-content "<prose>" Bind a fresh Claim inline. Gaia
                                   auto-derives a slug; override with
                                   --conclusion-label. Use when you
                                   want a named module-scope binding
                                   that later verbs can reference.
    --conclusion-prose   "<prose>" Pass prose directly as an anonymous
                                   string; no new Claim binding is
                                   created. Use when no later verb
                                   needs to reference this conclusion
                                   by name.

Pick exactly one — the three flags are mutually exclusive.
"""

derive_command.__doc__ = (derive_command.__doc__ or "") + _EPILOG_WHEN_TO_USE


__all__ = ["derive_command"]
