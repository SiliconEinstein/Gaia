"""``gaia author associate`` — append an ``associate(a, b, ...)`` statement.

Maps to ``gaia.engine.lang.dsl.associate_verb.associate``:

.. code-block:: python

    associate(
        a,
        b,
        *,
        p_a_given_b,
        p_b_given_a,
        pattern=None,
        background=None,
        rationale="",
        label=None,
    )

Symmetric probabilistic association between two Claims. Returns a helper
Claim. ``pattern`` (if set) is one of ``equal`` / ``contradict`` /
``exclusive`` and the DSL enforces consistency with the two conditional
probabilities (e.g. ``pattern="equal"`` requires both > 0.5).
"""

from __future__ import annotations

from typing import Any

import typer

from gaia.cli.commands.author._common import (
    build_sibling_imports,
    emit_syntax_error,
    normalize_file_option,
    parse_metadata,
    validate_identifier_flag,
)
from gaia.cli.commands.author._proposed_op import ProposedAuthorOp
from gaia.cli.commands.author._runner import run_author_op

_ASSOCIATE_PATTERNS = frozenset({"equal", "contradict", "exclusive"})


def _render_associate_statement(
    *,
    binding_name: str | None,
    engine_label: str | None,
    a: str,
    b: str,
    p_a_given_b: float,
    p_b_given_a: float,
    pattern: str | None,
    rationale: str | None,
    metadata: dict[str, Any] | None,
) -> str:
    """Render the proposed ``associate(...)`` statement."""
    args = [a, b]
    kwargs = [
        f"p_a_given_b={p_a_given_b!r}",
        f"p_b_given_a={p_b_given_a!r}",
    ]
    if engine_label is not None:
        kwargs.append(f"label={engine_label!r}")
    if pattern is not None:
        kwargs.append(f"pattern={pattern!r}")
    if rationale:
        kwargs.append(f"rationale={rationale!r}")
    if metadata:
        kwargs.append(f"metadata={metadata!r}")
    rendered_args = ", ".join([*args, *kwargs])
    call = f"associate({rendered_args})"
    if binding_name is None:
        return call
    return f"{binding_name} = {call}"


def associate_command(
    label: str | None = typer.Option(
        None,
        "--label",
        help=(
            "Engine `label=` kwarg on the rendered associate(...) call. "
            "Distinct from --dsl-binding-name (the Python LHS)."
        ),
    ),
    dsl_binding_name: str | None = typer.Option(
        None,
        "--dsl-binding-name",
        help=(
            "Python LHS for the rendered statement (``<name> = "
            "associate(...)``). Omit to emit a bare expression."
        ),
    ),
    a: str = typer.Option(..., "--a", help="Identifier of the first Claim."),
    b: str = typer.Option(..., "--b", help="Identifier of the second Claim."),
    p_a_given_b: float = typer.Option(..., "--p-a-given-b", help="P(a | b) — required."),
    p_b_given_a: float = typer.Option(..., "--p-b-given-a", help="P(b | a) — required."),
    target: str = typer.Option(
        ".", "--target", help="Path to the target Gaia package (default: cwd)."
    ),
    file: str | None = typer.Option(
        None,
        "--file",
        help=("Relative path under src/<import_name>/ to write into. Default: `__init__.py`."),
    ),
    pattern: str | None = typer.Option(
        None,
        "--pattern",
        help="Optional structural pattern (equal / contradict / exclusive).",
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
            "(default on for associate)."
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
    r"""Append an ``associate(...)`` probabilistic-association statement.

    Example:

        gaia author associate --a my_claim_a --b my_claim_b \
            --p-a-given-b 0.9 --p-b-given-a 0.6 \
            --dsl-binding-name my_association
    """
    del json_

    if pattern is not None and pattern not in _ASSOCIATE_PATTERNS:
        allowed = ", ".join(sorted(_ASSOCIATE_PATTERNS))
        emit_syntax_error(
            "associate",
            f"--pattern must be one of: {allowed} (got {pattern!r})",
            target=str(target),
            human=human,
        )
        return

    metadata_dict, metadata_error = parse_metadata(metadata)
    if metadata_error:
        emit_syntax_error("associate", metadata_error, target=str(target), human=human)
        return

    if not validate_identifier_flag(
        a, verb="associate", flag="--a", target=str(target), human=human
    ):
        return
    if not validate_identifier_flag(
        b, verb="associate", flag="--b", target=str(target), human=human
    ):
        return

    generated_code = _render_associate_statement(
        binding_name=dsl_binding_name,
        engine_label=label,
        a=a,
        b=b,
        p_a_given_b=p_a_given_b,
        p_b_given_a=p_b_given_a,
        pattern=pattern,
        rationale=rationale,
        metadata=metadata_dict,
    )
    target_file = normalize_file_option(file)
    references = [a, b]
    proposed_op = ProposedAuthorOp(
        verb="associate",
        kind="reasoning",
        label=dsl_binding_name,
        references=references,
        generated_code=generated_code,
        required_imports=("associate",),
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


__all__ = ["associate_command"]
