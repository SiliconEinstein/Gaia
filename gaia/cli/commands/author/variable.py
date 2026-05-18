"""``gaia author variable`` — append a ``Variable(symbol, domain, value)`` statement.

Exposes the engine's :class:`gaia.engine.lang.runtime.variable.Variable`
class through a structured cli verb so an agent can declare typed terms
for use in formulas, parameter() calls, and bayes.model() observables
without hand-editing source.

Maps to ``gaia.engine.lang.runtime.variable.Variable``:

.. code-block:: python

    Variable(symbol="<s>", domain=<Nat|Real|Bool|Probability|Domain>,
             value=<scalar|None>, content=<optional str>)

The cli surface accepts the four primitive domain names plus an
identifier-only path for user-declared Domains (validated by pre-write's
identifier resolution invariant). ``--value`` is forwarded verbatim so
callers can pass numeric literals, booleans, or even simple
expressions; pre-write parses the rendered statement as Python before
write to catch obvious malformations.
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

_PRIMITIVE_DOMAINS = frozenset({"Nat", "Real", "Bool", "Probability"})


def _render_variable_statement(
    *,
    binding_name: str | None,
    symbol: str,
    domain: str,
    value: str | None,
    content: str | None,
    metadata: dict[str, Any] | None,
    const: bool,
) -> str:
    """Render the proposed ``Variable(...)`` (or ``Constant(...)``) statement.

    The DSL re-exports both ``Variable`` and ``Constant`` from
    ``gaia.engine.lang``; the difference is binding semantics —
    ``Variable`` carries an optional bound value; ``Constant`` is a
    frozen literal expression term that only appears inside formulas.
    The cli renders one or the other based on the ``--const`` flag.

    Neither ``Variable`` nor ``Constant`` takes an engine ``label=``
    kwarg, so only the Python LHS is settable.
    """
    if const:
        # Constant(value, primitive) — frozen literal term, no symbol /
        # binding semantics. ``--symbol`` is ignored for const mode.
        call = f"Constant({value}, {domain})"
    else:
        kwargs = [f"symbol={symbol!r}", f"domain={domain}"]
        if value is not None:
            kwargs.append(f"value={value}")
        if content is not None:
            kwargs.append(f"content={content!r}")
        if metadata:
            kwargs.append(f"metadata={metadata!r}")
        call = f"Variable({', '.join(kwargs)})"
    if binding_name is None:
        return call
    return f"{binding_name} = {call}"


def variable_command(
    dsl_binding_name: str | None = typer.Option(
        None,
        "--dsl-binding-name",
        help=(
            "Python LHS for the rendered Variable/Constant declaration "
            "(``<name> = Variable(...)``). Omit to emit a bare expression. "
            "Variable / Constant do not take an engine ``label=`` kwarg, "
            "so this is the only label-like flag the verb exposes."
        ),
    ),
    symbol: str | None = typer.Option(
        None,
        "--symbol",
        help=(
            "Symbol used in formulas (e.g. `k_dominant`). Required unless "
            "--const is passed (Constant has no symbol)."
        ),
    ),
    domain: str = typer.Option(
        ...,
        "--domain",
        help=(
            "Primitive type or user-declared Domain identifier. Built-in "
            "primitives: Nat / Real / Bool / Probability. A non-primitive "
            "name is treated as a user-declared Domain reference (pre-write "
            "verifies it resolves in module scope)."
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
    value: str | None = typer.Option(
        None,
        "--value",
        help=(
            "Bound value: numeric literal (`--value 395`), boolean / None "
            "(`--value True`), or a bare Python identifier "
            "(`--value DOMINANT_COUNT`) resolved against the package's "
            "module scope so authors can reference imported constants "
            "(e.g. from a sibling `probabilities.py`). Required for "
            "Constant; arbitrary Python expressions are refused at the "
            "flag boundary."
        ),
    ),
    content: str | None = typer.Option(
        None,
        "--content",
        help=(
            "Optional Variable.content override (defaults to auto-generated "
            "`'Variable <symbol>: <domain> = <value>'`)."
        ),
    ),
    metadata: str | None = typer.Option(
        None, "--metadata", help="Optional JSON-encoded metadata dict."
    ),
    const: bool = typer.Option(
        False,
        "--const",
        help=(
            "Emit Constant(value, primitive) instead of Variable(...). "
            "Constant is a frozen literal term used inside formulas; it "
            "does not carry a symbol or bind a runtime value."
        ),
    ),
    export: bool = typer.Option(
        False,
        "--export/--no-export",
        help=(
            "Add --dsl-binding-name to __all__ on a successful write "
            "(default off for variable: typed-term declarations are "
            "internal scaffolding, not part of the public Knowledge surface)."
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
    r"""Append a ``Variable(...)`` or ``Constant(...)`` typed-term declaration.

    Example:
        gaia author variable --symbol my_n --domain Nat --value 395 \
            --dsl-binding-name my_count
    """
    del json_

    if const:
        # Constant requires --value and --domain only; --symbol is invalid
        # since Constant has no symbol slot.
        if value is None:
            emit_syntax_error(
                "variable",
                "--const requires --value",
                target=str(target),
                human=human,
            )
            return
        if symbol is not None:
            emit_syntax_error(
                "variable",
                "--const is incompatible with --symbol (Constant has no symbol slot)",
                target=str(target),
                human=human,
            )
            return
    else:
        if symbol is None:
            emit_syntax_error(
                "variable",
                "--symbol is required (use --const for a Constant literal)",
                target=str(target),
                human=human,
            )
            return

    metadata_dict, metadata_error = parse_metadata(metadata)
    if metadata_error:
        emit_syntax_error("variable", metadata_error, target=str(target), human=human)
        return

    # References: the domain identifier always resolves either against
    # the standing whitelist of primitives or against a module-scope
    # Domain binding. We push the domain into pre-write's reference list
    # only when it's NOT a primitive — pre-write's symbol scan can't see
    # the built-in primitives that come from ``gaia.engine.lang``.
    references: list[str] = []
    if domain not in _PRIMITIVE_DOMAINS:
        references.append(domain)

    # Every ``--value`` must be a literal or a bare identifier. Anything
    # else (calls, dotted lookups, dunder names) is rejected at the
    # flag boundary so the splice-into-generated-source RCE vector is
    # closed. The validator pushes a bare identifier into ``references``
    # so prewrite invariant (c) verifies it resolves in module scope.
    rendered_value: str | None = None
    if value is not None:
        # Primitive domain names appear as literals/idents — keep them
        # out of the references list since the engine surfaces them as
        # built-in symbols, not module-scope bindings.
        try:
            _, rendered_value = parse_literal_or_identifier(
                value,
                references_sink=references,
            )
        except PrewriteUnsafeError as exc:
            emit_syntax_error(
                "variable",
                f"--value rejected: {exc}",
                target=str(target),
                human=human,
                kind="prewrite.expr_unsafe",
            )
            return
        # Strip primitive-domain false-positives back out of references.
        if rendered_value in _PRIMITIVE_DOMAINS and rendered_value in references:
            references.remove(rendered_value)

    generated_code = _render_variable_statement(
        binding_name=dsl_binding_name,
        symbol=symbol or "",
        domain=domain,
        value=rendered_value,
        content=content,
        metadata=metadata_dict,
        const=const,
    )

    required_imports: tuple[str, ...] = ("Constant",) if const else ("Variable",)
    if domain in _PRIMITIVE_DOMAINS:
        required_imports = (*required_imports, domain)

    target_file = normalize_file_option(file)
    proposed_op = ProposedAuthorOp(
        verb="variable",
        kind="reasoning",
        label=dsl_binding_name,
        references=references,
        generated_code=generated_code,
        required_imports=required_imports,
        target_file=target_file,
        sibling_imports=build_sibling_imports(references, target_file=target_file),
        extra_payload={"variable_kind": "const" if const else "variable"},
        export=export,
    )
    run_author_op(
        proposed_op,
        target=target,
        human=human,
        check=check,
        interactive=interactive,
    )


__all__ = ["variable_command"]
