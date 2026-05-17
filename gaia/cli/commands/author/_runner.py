"""Shared verb dispatch for ``gaia author <verb>``.

Each per-verb module (:mod:`.claim`, :mod:`.equal`, :mod:`.derive`)
constructs a :class:`ProposedAuthorOp` from its parsed flags and calls
:func:`run_author_op` to execute the uniform pipeline:

    1. pre-write check    (always; fail-fast; no flag)
    2. write              (only if pre-write OK)
    3. post-write check   (only if pre-write OK; gated by --check/--no-check)
    4. emit envelope      (JSON or human; exits with semantic code)

The runner owns the JSON envelope and exit-code semantics so individual
verbs only have to know their argument-to-snippet mapping.
"""

from __future__ import annotations

from pathlib import Path

from gaia.cli.commands.author._envelope import (
    EXIT_OK,
    EXIT_PREWRITE_STRUCTURAL,
    AuthorResult,
    Diagnostic,
    emit,
    system_error,
)
from gaia.cli.commands.author._postwrite import postwrite_check
from gaia.cli.commands.author._prewrite import prewrite_check
from gaia.cli.commands.author._proposed_op import ProposedAuthorOp
from gaia.cli.commands.author._writer import append_statement


def run_author_op(
    proposed_op: ProposedAuthorOp,
    *,
    target: str | Path,
    human: bool,
    check: bool,
    interactive: bool,
) -> None:
    """Execute the canonical pre-write → write → post-write → emit cycle.

    Args:
        proposed_op: The verb-specific operation the per-verb command
            built from its parsed flags. Must already carry a populated
            ``generated_code`` snippet.
        target: Path to the target Gaia package root.
        human: When ``True``, emit the human-readable rendering instead
            of JSON.
        check: When ``True``, run the post-write ``gaia build check`` step
            after a successful write. Short-circuited if pre-write fails.
        interactive: When ``True``, surface pre-write warnings as
            interactive prompts. R1 implements no warnings yet (the four
            invariants are error-only), so this flag is reserved for R2;
            its presence in the signature locks the surface so R2's
            additions don't require a CLI-flag breaking change.
    """
    del interactive  # R1: no pre-write warnings emit prompts yet; reserved.

    target_path = Path(target).resolve()

    # ---- step 1: pre-write ---------------------------------------------- #

    try:
        pre = prewrite_check(target_path, proposed_op)
    except (OSError, PermissionError) as exc:
        emit(
            system_error(proposed_op.verb, f"system error reading target: {exc}"),
            human=human,
        )
        return  # unreachable — emit raises typer.Exit
    if not pre.ok:
        result = AuthorResult(
            verb=proposed_op.verb,
            status="error",
            code=pre.exit_code,
            payload={"target": str(target_path)},
            diagnostics=pre.diagnostics,
        )
        emit(result, human=human)
        return

    assert pre.source_init_path is not None  # invariant after a successful prewrite

    # ---- step 2: write -------------------------------------------------- #

    try:
        write_result = append_statement(pre.source_init_path, proposed_op.generated_code)
    except (OSError, PermissionError) as exc:
        emit(
            system_error(
                proposed_op.verb,
                f"failed to write to {pre.source_init_path}: {exc}",
                kind="prewrite.target_invalid",
            ),
            human=human,
        )
        return

    payload: dict[str, object] = {
        "target": str(target_path),
        "written_to": str(write_result.path),
        "label": proposed_op.label,
        "verb": proposed_op.verb,
        "snippet": write_result.appended,
    }

    # ---- step 3: post-write --------------------------------------------- #

    post_warnings: list[Diagnostic] = []
    if check:
        post = postwrite_check(target_path)
        post_warnings.extend(post.warnings)
        if not post.ok:
            result = AuthorResult(
                verb=proposed_op.verb,
                status="error",
                code=EXIT_PREWRITE_STRUCTURAL,
                payload=payload,
                warnings=[w.message for w in post.warnings],
                diagnostics=post.diagnostics,
            )
            emit(result, human=human)
            return
        payload["check"] = {
            "knowledge_count": post.knowledge_count,
            "strategy_count": post.strategy_count,
            "operator_count": post.operator_count,
        }
    else:
        payload["check"] = "skipped"

    # ---- step 4: emit ok ------------------------------------------------ #

    result = AuthorResult(
        verb=proposed_op.verb,
        status="ok",
        code=EXIT_OK,
        payload=payload,
        warnings=[w.message for w in post_warnings],
        diagnostics=list(post_warnings),
    )
    emit(result, human=human)


__all__ = ["run_author_op"]
