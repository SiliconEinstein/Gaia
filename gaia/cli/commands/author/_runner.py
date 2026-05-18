"""Shared verb dispatch for ``gaia author <verb>``.

Each per-verb module (:mod:`.claim`, :mod:`.equal`, :mod:`.derive`, ...)
constructs a :class:`ProposedAuthorOp` from its parsed flags and calls
:func:`run_author_op` to execute the uniform pipeline:

    1. pre-write check    (always; fail-fast; no flag)
    2. write              (only if pre-write OK)
    3. post-write check   (only if pre-write OK; gated by --check/--no-check)
    4. emit envelope      (JSON or human; exits with semantic code)

The runner owns the JSON envelope and exit-code semantics so individual
verbs only have to know their argument-to-snippet mapping.

R2 wires the ``--interactive`` flag uniformly: any pre-write warning
surfaces a numbered prompt, default-skip semantics. In JSON mode (the
default) the prompts are auto-suppressed and the run proceeds, since the
agent consumer does not have stdin to drive prompts. See the
``_maybe_consume_warnings`` helper for the activation logic.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

import typer

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


def _maybe_consume_warnings(
    verb: str,
    warnings: list[Diagnostic],
    *,
    interactive: bool,
    human: bool,
) -> tuple[bool, AuthorResult | None]:
    """Apply ``--interactive`` activation against ``warnings``.

    Returns ``(proceed, optional_abort_result)``:

    * ``(True, None)`` — proceed to write. Default when there are no
      warnings, when ``--interactive`` is not set, or when the caller
      accepted the prompt.
    * ``(False, result)`` — abort. The caller should ``emit(result, ...)``
      and stop. Used when the user said no at the prompt.

    Activation rules (CD-pick, ratified):

    * JSON mode (``human=False``) auto-suppresses prompts even when
      ``--interactive`` is set — agents do not drive stdin. Warnings still
      flow into the envelope; the run continues.
    * ``--interactive`` + ``human`` mode + at least one warning →
      numbered prompt, default ``N``.

    The abort envelope uses ``status="aborted"`` with a ``user.aborted``
    diagnostic so an agent that parses an abort log can tell user-driven
    aborts apart from pre-write errors.
    """
    if not warnings or not interactive:
        return True, None
    if not human:
        # JSON consumers can't drive a prompt; warnings already appear in
        # the envelope.warnings array. Proceed silently.
        return True, None

    typer.echo("Pre-write warnings:")
    for idx, warning in enumerate(warnings, start=1):
        typer.echo(f"  {idx}) {warning.kind}: {warning.message}")
    answer = typer.prompt("Continue? [y/N]", default="N", show_default=False).strip().lower()
    if answer in {"y", "yes"}:
        return True, None
    aborted = AuthorResult(
        verb=verb,
        status="aborted",
        code=EXIT_OK,
        warnings=[w.message for w in warnings],
        diagnostics=[
            Diagnostic(
                kind="user.aborted",
                level="warning",
                message="user declined to proceed past pre-write warnings",
                source="prewrite",
            ),
            *warnings,
        ],
    )
    return False, aborted


@dataclass
class _WriteOutcome:
    """Result of the write-phase helper."""

    write_result_path: Path
    written_segments: list[str]
    sibling_added_total: list[str]
    all_warning_messages: list[str]
    all_managed: bool


def _execute_writes(
    proposed_op: ProposedAuthorOp,
    *,
    pre_source_init: Path,
    write_target: Path,
    pre_import_name: str | None,
) -> _WriteOutcome:
    """Run the prepended + main writes. Raises OSError/PermissionError on IO fail.

    R10 Axis 2 §C.2 — prepended statements now land in the **same file**
    as the main statement (``write_target``), not unconditionally in
    ``__init__.py`` via ``pre_source_init``. The previous behaviour
    half-mutated a package when ``--file <sibling>`` was passed: the
    auto-mint claim went into ``__init__.py`` while the consuming
    derive/observe/infer statement landed in the sibling, leaving the
    sibling with an unresolved reference and ``__init__.py`` with an
    orphan binding. Routing prepended writes to ``write_target`` keeps
    them next to their consumer.
    """
    del pre_source_init  # retained as a kwarg for API symmetry / future use
    written_segments: list[str] = []
    all_warning_messages: list[str] = []
    for _prep_label, prep_code in proposed_op.prepended_statements:
        prep_write = append_statement(write_target, prep_code, new_label=_prep_label)
        written_segments.append(prep_write.appended)
        if prep_write.all_warning:
            all_warning_messages.append(prep_write.all_warning)
    write_result = append_statement(
        write_target,
        proposed_op.generated_code,
        new_label=proposed_op.label,
        sibling_imports=proposed_op.sibling_imports,
        import_package_name=pre_import_name,
    )
    written_segments.append(write_result.appended)
    if write_result.all_warning:
        all_warning_messages.append(write_result.all_warning)
    return _WriteOutcome(
        write_result_path=write_result.path,
        written_segments=written_segments,
        sibling_added_total=list(write_result.sibling_imports_added),
        all_warning_messages=all_warning_messages,
        all_managed=write_result.all_managed,
    )


def _build_payload(
    proposed_op: ProposedAuthorOp,
    target_path: Path,
    outcome: _WriteOutcome,
) -> dict[str, object]:
    """Assemble the canonical envelope payload from the write outcome."""
    payload: dict[str, object] = {
        "target": str(target_path),
        "written_to": str(outcome.write_result_path),
        "label": proposed_op.label,
        "verb": proposed_op.verb,
        "snippet": "".join(outcome.written_segments),
    }
    if proposed_op.prepended_statements:
        payload["auto_generated"] = [
            {"label": label, "snippet": snip}
            for (label, _code), snip in zip(
                proposed_op.prepended_statements,
                outcome.written_segments[:-1],
                strict=True,
            )
        ]
    if outcome.sibling_added_total:
        payload["sibling_imports_added"] = outcome.sibling_added_total
    if outcome.all_managed:
        payload["all_managed"] = True
    if proposed_op.extra_payload:
        payload.update(proposed_op.extra_payload)
    return payload


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
            interactive prompts (human mode only — JSON mode auto-
            suppresses). See :func:`_maybe_consume_warnings`.
    """
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
        emit(
            AuthorResult(
                verb=proposed_op.verb,
                status="error",
                code=pre.exit_code,
                payload={"target": str(target_path)},
                diagnostics=pre.diagnostics,
            ),
            human=human,
        )
        return

    assert pre.source_init_path is not None  # invariant after a successful prewrite
    write_target = pre.write_target_path or pre.source_init_path

    proceed, abort_result = _maybe_consume_warnings(
        proposed_op.verb,
        pre.warnings,
        interactive=interactive,
        human=human,
    )
    if not proceed:
        assert abort_result is not None
        emit(abort_result, human=human)
        return
    sys.stdout.flush()  # keep prompt output and JSON output disjoint

    # ---- step 2: write -------------------------------------------------- #

    try:
        outcome = _execute_writes(
            proposed_op,
            pre_source_init=pre.source_init_path,
            write_target=write_target,
            pre_import_name=pre.import_name,
        )
    except (OSError, PermissionError) as exc:
        emit(
            system_error(
                proposed_op.verb,
                f"failed to write to {write_target}: {exc}",
                kind="prewrite.target_invalid",
            ),
            human=human,
        )
        return

    payload = _build_payload(proposed_op, target_path, outcome)

    # Carry pre-write warnings through into the final envelope so JSON
    # consumers see them even when --interactive auto-suppresses prompts.
    prewrite_warnings = list(pre.warnings)
    for warning_msg in outcome.all_warning_messages:
        prewrite_warnings.append(
            Diagnostic(
                kind="postwrite.all_dynamic",
                level="warning",
                message=warning_msg,
                source="postwrite",
            )
        )

    # ---- step 3: post-write --------------------------------------------- #

    post_warnings: list[Diagnostic] = []
    if check:
        post = postwrite_check(target_path)
        post_warnings.extend(post.warnings)
        if not post.ok:
            combined_warnings = prewrite_warnings + post.warnings
            emit(
                AuthorResult(
                    verb=proposed_op.verb,
                    status="error",
                    code=EXIT_PREWRITE_STRUCTURAL,
                    payload=payload,
                    warnings=[w.message for w in combined_warnings],
                    diagnostics=post.diagnostics,
                ),
                human=human,
            )
            return
        payload["check"] = {
            "knowledge_count": post.knowledge_count,
            "strategy_count": post.strategy_count,
            "operator_count": post.operator_count,
        }
    else:
        payload["check"] = "skipped"

    # ---- step 4: emit ok ------------------------------------------------ #

    final_warnings = prewrite_warnings + post_warnings
    emit(
        AuthorResult(
            verb=proposed_op.verb,
            status="ok",
            code=EXIT_OK,
            payload=payload,
            warnings=[w.message for w in final_warnings],
            diagnostics=list(final_warnings),
        ),
        human=human,
    )


__all__ = ["run_author_op"]
