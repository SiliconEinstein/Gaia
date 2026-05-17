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
    emit_syntax_error,
    normalize_file_option,
    parse_metadata,
)
from gaia.cli.commands.author._proposed_op import ProposedAuthorOp
from gaia.cli.commands.author._runner import run_author_op


def _render_register_prior_statement(
    *,
    claim_ref: str,
    value: float,
    justification: str,
    source_id: str,
    metadata: dict[str, Any] | None,
    comment_label: str | None,
) -> str:
    """Render the proposed ``register_prior(...)`` statement.

    The statement is a bare call (no LHS) since ``register_prior``
    returns ``None``. ``comment_label`` is optionally rendered as a
    trailing ``# label`` comment so a reader can scan the source.
    """
    args = [claim_ref, repr(value)]
    kwargs = [f"justification={justification!r}", f"source_id={source_id!r}"]
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
    value: float = typer.Option(
        ..., "--value", help="Prior probability in (CROMWELL_EPS, 1 - CROMWELL_EPS)."
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
            "Relative path under src/<import_name>/ to write into (e.g. "
            "`priors.py` to match the hand-authored pattern). Default: "
            "`__init__.py`. When writing to a sibling file, the cli will "
            "auto-insert `from <import_name> import <claim>` if missing."
        ),
    ),
    source_id: str = typer.Option(
        "user_priors",
        "--source-id",
        help="Source identifier (defaults to 'user_priors'; engines use namespaced ids).",
    ),
    statement_label: str | None = typer.Option(
        None,
        "--statement-label",
        help="Optional trailing-comment label so tooling can scan the source line.",
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
    r"""Author a ``register_prior(...)`` prior-registration statement.

    Example:

    .. code-block:: bash

        gaia author register-prior --claim hypothesis_x --value 0.7 \
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

    generated_code = _render_register_prior_statement(
        claim_ref=claim,
        value=value,
        justification=justification,
        source_id=source_id,
        metadata=metadata_dict,
        comment_label=statement_label,
    )
    # R7 G1: register_prior may now target a sibling file (e.g. priors.py)
    # so it matches the hand-authored pattern where prior records live
    # alongside __init__.py rather than inside it. When writing to a
    # sibling, the referenced ``claim`` identifier must be imported from
    # the package — declare a sibling_imports entry so the writer adds
    # ``from <import_name> import <claim>`` if missing.
    sibling_imports: tuple[tuple[str, str], ...] = ()
    target_file = normalize_file_option(file)
    if target_file and target_file != "__init__.py":
        sibling_imports = ((claim, ""),)  # package name filled in by writer

    proposed_op = ProposedAuthorOp(
        verb="register_prior",
        kind="reasoning",
        # No LHS binding — the call returns None and mutates the claim
        # in place. Pre-write skips the label-collision invariant when
        # label is None (see _prewrite._validate_label_collision).
        label=None,
        references=[claim],
        generated_code=generated_code,
        required_imports=("register_prior",),
        target_file=target_file,
        sibling_imports=sibling_imports,
    )
    run_author_op(
        proposed_op,
        target=target,
        human=human,
        check=check,
        interactive=interactive,
    )


__all__ = ["register_prior_command"]
