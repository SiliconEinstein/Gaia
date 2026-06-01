"""``gaia author infer`` — append an ``infer(evidence, hypothesis=..., ...)`` statement.

Maps to ``gaia.engine.lang.dsl.infer_verb.infer`` (canonical v6 shape):

.. code-block:: python

    infer(
        evidence,
        *,
        hypothesis,
        p_e_given_h,
        p_e_given_not_h=0.5,
        given=(),
        background=None,
        rationale="",
        label=None,
    )

Returns the evidence Claim (relabelled by ``--label``). The verb declares
that ``evidence`` statistically supports ``hypothesis`` with the supplied
conditional likelihoods. ``p_e_given_h`` is required; ``p_e_given_not_h``
defaults to 0.5 in the DSL (we surface it but allow omission).

The legacy v5 list-of-premises shape (``infer([premises], conclusion)``)
is not exposed through the CLI — agents authoring fresh content should
use the v6 form.

Prose mode for the hypothesis slot. ``--hypothesis-content "<prose>"``
mints a fresh ``claim(prose)`` statement, uses the cli-derived slug as
the ``hypothesis=`` kwarg, and prepends the auto-claim to the target
file ahead of the ``infer(...)`` statement. Mutually exclusive with
``--hypothesis``; ``--hypothesis-label`` overrides the auto-derived
slug (mirrors the ``--conclusion-label`` discipline on ``derive``).
This is a semantically-honest fit because the hypothesis in an
``infer()`` call is a fresh assertion being introduced for posterior
update — the prose maps cleanly onto a new Claim.

Prose mode scope is bounded to ``--hypothesis-content`` only (not
``--evidence-content``); evidence usually references prior claims, so
the auto-mint pattern doesn't fit.
"""

from __future__ import annotations

from typing import Any

import typer

from gaia.cli.commands.author._common import (
    build_sibling_imports,
    emit_syntax_error,
    normalize_file_option,
    parse_metadata,
    split_csv_idents,
)
from gaia.cli.commands.author._proposed_op import ProposedAuthorOp
from gaia.cli.commands.author._prose import build_auto_claim_statement, slugify_label
from gaia.cli.commands.author._runner import run_author_op


def _render_infer_statement(
    *,
    binding_name: str | None,
    engine_label: str | None,
    evidence: str,
    hypothesis_expr: str,
    p_e_given_h: float,
    p_e_given_not_h: float | None,
    given: list[str],
    rationale: str | None,
    metadata: dict[str, Any] | None,
    background: list[str],
) -> str:
    """Render the proposed ``infer(...)`` statement.

    ``hypothesis_expr`` is the Python source spelling at the call site:
    either a bare identifier (``--hypothesis`` / ``--hypothesis-content``
    auto-mint slug) or an inline ``claim('<prose>')`` call expression
    (``--hypothesis-prose``).
    """
    args = [evidence]
    kwargs = [f"hypothesis={hypothesis_expr}", f"p_e_given_h={p_e_given_h!r}"]
    if p_e_given_not_h is not None:
        kwargs.append(f"p_e_given_not_h={p_e_given_not_h!r}")
    if given:
        kwargs.append(f"given=[{', '.join(given)}]")
    if background:
        kwargs.append(f"background=[{', '.join(background)}]")
    if engine_label is not None:
        kwargs.append(f"label={engine_label!r}")
    if rationale:
        kwargs.append(f"rationale={rationale!r}")
    if metadata:
        kwargs.append(f"metadata={metadata!r}")
    rendered_args = ", ".join([*args, *kwargs])
    call = f"infer({rendered_args})"
    if binding_name is None:
        return call
    return f"{binding_name} = {call}"


def infer_command(
    label: str | None = typer.Option(
        None,
        "--label",
        help=(
            "Engine `label=` kwarg on the rendered infer(...) call. "
            "Distinct from --dsl-binding-name (the Python LHS)."
        ),
    ),
    dsl_binding_name: str | None = typer.Option(
        None,
        "--dsl-binding-name",
        help=(
            "Python LHS for the rendered statement (``<name> = "
            "infer(...)``). Omit to emit a bare expression."
        ),
    ),
    evidence: str = typer.Option(..., "--evidence", help="Identifier of the evidence Claim."),
    hypothesis: str | None = typer.Option(
        None,
        "--hypothesis",
        help=(
            "Identifier of the hypothesis Claim (must already be declared). "
            "Mutually exclusive with --hypothesis-content."
        ),
    ),
    hypothesis_content: str | None = typer.Option(
        None,
        "--hypothesis-content",
        help=(
            "Prose for an auto-generated hypothesis Claim. Mutually exclusive with "
            "--hypothesis. Cli derives a snake-case slug for the label "
            "(override via --hypothesis-label)."
        ),
    ),
    hypothesis_prose: str | None = typer.Option(
        None,
        "--hypothesis-prose",
        help=(
            "Inline prose wrapped into an anonymous claim() at the call site. "
            "Emits ``infer(evidence, hypothesis=claim('<prose>'), ...)`` with "
            "no named binding. Mutually exclusive with --hypothesis and "
            "--hypothesis-content. (The engine's ``infer()`` hypothesis kwarg "
            "is strictly Claim-typed, so the cli wraps the prose at the call "
            "site rather than passing a bare string.)"
        ),
    ),
    hypothesis_label: str | None = typer.Option(
        None,
        "--hypothesis-label",
        help=(
            "Optional explicit label for the auto-generated hypothesis Claim "
            "(only meaningful with --hypothesis-content)."
        ),
    ),
    p_e_given_h: float = typer.Option(
        ...,
        "--p-e-given-h",
        help="P(evidence | hypothesis) — required likelihood under the hypothesis.",
    ),
    target: str = typer.Option(
        ".", "--target", help="Path to the target Gaia package (default: cwd)."
    ),
    file: str | None = typer.Option(
        None,
        "--file",
        help=("Relative path under src/<import_name>/ to write into. Default: `__init__.py`."),
    ),
    p_e_given_not_h: float | None = typer.Option(
        None,
        "--p-e-given-not-h",
        help="P(evidence | NOT hypothesis) — defaults to 0.5 in the DSL when omitted.",
    ),
    given: str | None = typer.Option(
        None,
        "--given",
        help="Comma-separated identifiers of conditioning Claim(s).",
    ),
    background: str | None = typer.Option(
        None,
        "--background",
        help="Comma-separated identifiers passed as the infer() background kwarg.",
    ),
    rationale: str | None = typer.Option(
        None, "--rationale", help="Optional natural-language justification."
    ),
    metadata: str | None = typer.Option(
        None, "--metadata", help="Optional JSON-encoded metadata dict."
    ),
    export: bool = typer.Option(
        False,
        "--export/--no-export",
        help=(
            "Add --dsl-binding-name to __all__ on a successful write. Default off: "
            "exports are the package's curated public Knowledge surface."
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
    r"""Append an ``infer(...)`` Bayesian-inference statement.

    Example:
        gaia author infer --evidence my_evidence \
            --hypothesis my_hypothesis --p-e-given-h 0.7 \
            --dsl-binding-name my_inference --label my_inference
    """
    del json_

    # --- mutual-exclusion check on hypothesis-mode ----------------------- #
    hyp_modes = [hypothesis, hypothesis_content, hypothesis_prose]
    hyp_modes_set = sum(1 for value_ in hyp_modes if value_ is not None)
    if hyp_modes_set == 0:
        emit_syntax_error(
            "infer",
            (
                "infer requires exactly one of --hypothesis / --hypothesis-content "
                "/ --hypothesis-prose"
            ),
            target=str(target),
            human=human,
        )
        return
    if hyp_modes_set > 1:
        emit_syntax_error(
            "infer",
            (
                "--hypothesis, --hypothesis-content, and --hypothesis-prose are "
                "mutually exclusive — pick exactly one"
            ),
            target=str(target),
            human=human,
        )
        return
    if hypothesis_label is not None and hypothesis_content is None:
        emit_syntax_error(
            "infer",
            "--hypothesis-label only applies with --hypothesis-content",
            target=str(target),
            human=human,
        )
        return

    metadata_dict, metadata_error = parse_metadata(metadata)
    if metadata_error:
        emit_syntax_error("infer", metadata_error, target=str(target), human=human)
        return

    given_list, given_error = split_csv_idents(given)
    if given_error:
        emit_syntax_error(
            "infer",
            f"--given rejected: {given_error}",
            target=str(target),
            human=human,
            kind="prewrite.expr_unsafe",
        )
        return
    background_list, background_error = split_csv_idents(background)
    if background_error:
        emit_syntax_error(
            "infer",
            f"--background rejected: {background_error}",
            target=str(target),
            human=human,
            kind="prewrite.expr_unsafe",
        )
        return

    # --- resolve hypothesis mode ---------------------------------------- #
    prepended: tuple[tuple[str, str], ...] = ()
    references: list[str]
    hypothesis_kind: str
    if hypothesis_content is not None:
        if hypothesis_label is not None:
            auto_label = hypothesis_label
        else:
            reserved = {evidence, *given_list, *background_list}
            if dsl_binding_name is not None:
                reserved.add(dsl_binding_name)
            auto_label = slugify_label(hypothesis_content, existing=reserved)
        prepended = ((auto_label, build_auto_claim_statement(auto_label, hypothesis_content)),)
        hypothesis_expr = auto_label
        references = [evidence, auto_label, *given_list, *background_list]
        hypothesis_kind = "auto_mint"
    elif hypothesis_prose is not None:
        # Inline-prose: wrap the prose with claim() at the call
        # site. The engine's infer() hypothesis kwarg is strictly Claim-
        # typed (no ``Claim | str`` polymorphism unlike derive/observe).
        # No named binding is introduced; references list omits the prose.
        hypothesis_expr = f"claim({hypothesis_prose!r})"
        references = [evidence, *given_list, *background_list]
        hypothesis_kind = "inline_prose"
    else:
        assert hypothesis is not None  # mutex check above
        hypothesis_expr = hypothesis
        references = [evidence, hypothesis, *given_list, *background_list]
        hypothesis_kind = "qid"

    generated_code = _render_infer_statement(
        binding_name=dsl_binding_name,
        engine_label=label,
        evidence=evidence,
        hypothesis_expr=hypothesis_expr,
        p_e_given_h=p_e_given_h,
        p_e_given_not_h=p_e_given_not_h,
        given=given_list,
        rationale=rationale,
        metadata=metadata_dict,
        background=background_list,
    )
    required_imports: tuple[str, ...] = ("infer",)
    if hypothesis_prose is not None:
        # Inline-prose wraps the prose with ``claim(...)`` at the call
        # site, so the target file needs ``claim`` importable.
        required_imports = ("infer", "claim")
    target_file = normalize_file_option(file)
    proposed_op = ProposedAuthorOp(
        verb="infer",
        kind="reasoning",
        label=dsl_binding_name,
        references=references,
        generated_code=generated_code,
        required_imports=required_imports,
        target_file=target_file,
        sibling_imports=build_sibling_imports(references, target_file=target_file),
        prepended_statements=prepended,
        extra_payload={"hypothesis_kind": hypothesis_kind},
        export=export,
    )
    run_author_op(
        proposed_op,
        target=target,
        human=human,
        check=check,
        interactive=interactive,
    )


__all__ = ["infer_command"]
