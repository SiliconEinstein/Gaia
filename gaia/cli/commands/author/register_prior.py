"""``gaia author register-prior`` — append a ``register_prior(...)`` statement.

Maps to ``gaia.engine.lang.dsl.register_prior.register_prior``:

.. code-block:: python

    register_prior(
        claim,
        value,
        *,
        justification,
        source_id="user_priors",
        created_at=None,
    )

This is the canonical (and after v0.5, the only) way to attach a prior
to a Claim. The function returns ``None`` and mutates the claim in
place; the produced statement has no LHS binding, which means the
``proposed_op.label`` field stays ``None`` for this verb. The CLI keeps
a ``--statement-label`` flag for an *optional* line-level comment label
that the author tooling can pin against, but the default is to emit a
bare expression statement.
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
    validate_identifier_flag,
)
from gaia.cli.commands.author._proposed_op import ProposedAuthorOp
from gaia.cli.commands.author._runner import run_author_op

_ENGINE_DEFAULT_SOURCE_ID = "user_priors"
"""Mirrors :data:`gaia.engine.lang.dsl.register_prior.DEFAULT_SOURCE_ID`.

When the cli would render ``source_id='user_priors'``, omit the kwarg
instead so the rendered statement matches the hand-authored pattern of
relying on the engine's default. Pinned locally so a CLI parse-time
check stays side-effect free (no engine import needed just to compare
a default).
"""


def _render_register_prior_statement(
    *,
    claim_ref: str,
    value: str,
    justification: str,
    source_id: str,
    emit_source_id: bool,
    metadata: dict[str, Any] | None,
    comment_label: str | None,
) -> str:
    """Render the proposed ``register_prior(...)`` statement.

    The statement is a bare call (no LHS) since ``register_prior``
    returns ``None``. ``comment_label`` is optionally rendered as a
    trailing ``# label`` comment so a reader can scan the source.

    ``value`` is the *Python source spelling* the caller wants at the
    rendered call site — either a numeric literal (``'0.5'``,
    ``'1.0 - PRIOR_MENDELIAN_MODEL'`` is **not** accepted at the
    flag boundary; only bare identifiers like ``'PRIOR_MENDELIAN_MODEL'``
    are) or a bare identifier resolved against module scope. The cli
    forwards it verbatim into ``value=<spelling>`` — matches the
    hand-authored pattern in the example packages where mendel uses
    ``value=PRIOR_MENDELIAN_MODEL`` rather than a numeric literal.

    ``emit_source_id`` toggles whether the ``source_id=`` kwarg appears
    in the rendered call. ``False`` is reserved for the case where the
    caller did not explicitly pass ``--source-id`` AND the value matches
    the engine default (:data:`_ENGINE_DEFAULT_SOURCE_ID`), matching the
    hand-authored mendel pattern of omitting the kwarg when redundant.
    """
    args = [claim_ref]
    kwargs = [f"value={value}", f"justification={justification!r}"]
    if emit_source_id:
        kwargs.append(f"source_id={source_id!r}")
    if metadata:
        kwargs.append(f"metadata={metadata!r}")
    statement = f"register_prior({', '.join(args)}, {', '.join(kwargs)})"
    if comment_label:
        statement += f"  # {comment_label}"
    return statement


def register_prior_command(
    claim: str = typer.Option(
        ..., "--claim", help="Identifier of the Claim to attach the prior to."
    ),
    value: str = typer.Option(
        ...,
        "--value",
        help=(
            "Prior probability in (CROMWELL_EPS, 1 - CROMWELL_EPS). Accepts "
            "either a numeric literal (`--value 0.5`) or a bare Python "
            "identifier (`--value PRIOR_MENDELIAN_MODEL`) resolved against "
            "the module scope so callers can reference imported constants "
            "(e.g. from a sibling `probabilities.py`). Arbitrary Python "
            "expressions are refused at the flag boundary."
        ),
    ),
    justification: str = typer.Option(
        ...,
        "--justification",
        help="Required non-empty rationale string (engines reject empty values).",
    ),
    target: str = typer.Option(
        ".", "--target", help="Path to the target Gaia package (default: cwd)."
    ),
    file: str | None = typer.Option(
        None,
        "--file",
        help=(
            "Relative path under src/<import_name>/authored/ to write into (e.g. "
            "`priors.py` to match the hand-authored pattern). Default: "
            "authored/__init__.py. When writing to a sibling file, the cli will "
            "auto-insert `from <import_name> import <claim>` if missing."
        ),
    ),
    source_id: str | None = typer.Option(
        None,
        "--source-id",
        help=(
            "Source identifier. Defaults to the engine's `user_priors`; "
            "when omitted on the cli, the rendered call omits the "
            "`source_id=` kwarg so the engine default applies (matches "
            "the hand-authored omit-when-default pattern). Engines use "
            "namespaced ids (e.g. `continuous_inference`, `reviewer_alice`)."
        ),
    ),
    statement_label: str | None = typer.Option(
        None,
        "--statement-label",
        help="Optional trailing-comment label so tooling can scan the source line.",
    ),
    metadata: str | None = typer.Option(
        None, "--metadata", help="Optional JSON-encoded metadata dict."
    ),
    export: bool = typer.Option(
        False,
        "--export/--no-export",
        help=(
            "Add the statement's binding to __all__ on a successful write "
            "(default off for register_prior: the call has no LHS binding, "
            "so this flag is reserved for surface uniformity)."
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
    r"""Append a ``register_prior(...)`` prior-registration statement.

    Example:
        gaia author register-prior --claim my_hypothesis --value 0.7 \
            --justification "Prior elicited from domain expert."
    """
    del json_

    metadata_dict, metadata_error = parse_metadata(metadata)
    if metadata_error:
        emit_syntax_error("register_prior", metadata_error, target=str(target), human=human)
        return

    if not justification.strip():
        emit_syntax_error(
            "register_prior",
            "--justification must be a non-empty string",
            target=str(target),
            human=human,
        )
        return

    if not validate_identifier_flag(
        claim, verb="register_prior", flag="--claim", target=str(target), human=human
    ):
        return

    # Parse --value: either a numeric literal or a bare identifier.
    # Identifier values are pushed onto the references list so pre-write
    # invariant (c) verifies they resolve in module scope.
    extra_value_refs: list[str] = []
    try:
        _, rendered_value = parse_literal_or_identifier(
            value,
            references_sink=extra_value_refs,
        )
    except PrewriteUnsafeError as exc:
        emit_syntax_error(
            "register_prior",
            f"--value rejected: {exc}",
            target=str(target),
            human=human,
            kind="prewrite.expr_unsafe",
        )
        return

    # Emit ``source_id=`` only when the caller passed ``--source-id``
    # explicitly (any value, including ``user_priors`` if that was the
    # explicit choice). When omitted on the cli, render without the
    # kwarg so the engine default applies and the rendered statement
    # matches the hand-authored omit-when-default pattern.
    emit_source_id = source_id is not None
    effective_source_id = source_id if source_id is not None else _ENGINE_DEFAULT_SOURCE_ID
    generated_code = _render_register_prior_statement(
        claim_ref=claim,
        value=rendered_value,
        justification=justification,
        source_id=effective_source_id,
        emit_source_id=emit_source_id,
        metadata=metadata_dict,
        comment_label=statement_label,
    )
    # register_prior may target a sibling file (e.g. priors.py); the
    # shared ``build_sibling_imports`` helper wires the cross-file
    # import. Tuple is empty when target_file is None or ``__init__.py``
    # (the helper short-circuits) so the default-file behaviour is
    # unchanged.
    target_file = normalize_file_option(file)
    references = [claim, *extra_value_refs]
    proposed_op = ProposedAuthorOp(
        verb="register_prior",
        kind="reasoning",
        # No LHS binding — the call returns None and mutates the claim
        # in place. Pre-write skips the label-collision invariant when
        # label is None (see _prewrite._validate_label_collision).
        label=None,
        references=references,
        generated_code=generated_code,
        required_imports=("register_prior",),
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


__all__ = ["register_prior_command"]
