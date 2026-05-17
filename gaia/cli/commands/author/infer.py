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

R4·❓A=A — prose mode for the hypothesis slot. ``--hypothesis-content
"<prose>"`` mints a fresh ``claim(prose)`` statement, uses the
cli-derived slug as the ``hypothesis=`` kwarg, and prepends the
auto-claim to the target file ahead of the ``infer(...)`` statement.
Mutually exclusive with ``--hypothesis``; ``--hypothesis-label``
overrides the auto-derived slug (mirrors R3's ``--conclusion-label``
discipline). This is a semantically-honest fit because the hypothesis
in an ``infer()`` call is a fresh assertion being introduced for
posterior-update — the prose maps cleanly onto a new Claim.

R4 prose mode scope is bounded to ``--hypothesis-content`` only (not
``--evidence-content``); evidence usually references prior claims, so
the auto-mint pattern doesn't fit. R5+ may revisit if authoring
patterns demand it.
"""

from __future__ import annotations

from typing import Any

import typer

from gaia.cli.commands.author._common import emit_syntax_error, parse_metadata, split_csv
from gaia.cli.commands.author._proposed_op import ProposedAuthorOp
from gaia.cli.commands.author._prose import build_auto_claim_statement, slugify_label
from gaia.cli.commands.author._runner import run_author_op


def _render_infer_statement(
    *,
    label: str,
    evidence: str,
    hypothesis: str,
    p_e_given_h: float,
    p_e_given_not_h: float | None,
    given: list[str],
    rationale: str | None,
    metadata: dict[str, Any] | None,
) -> str:
    """Render the proposed ``infer(...)`` statement."""
    args = [evidence]
    kwargs = [f"hypothesis={hypothesis}", f"p_e_given_h={p_e_given_h!r}"]
    if p_e_given_not_h is not None:
        kwargs.append(f"p_e_given_not_h={p_e_given_not_h!r}")
    if given:
        kwargs.append(f"given=[{', '.join(given)}]")
    kwargs.append(f"label={label!r}")
    if rationale:
        kwargs.append(f"rationale={rationale!r}")
    if metadata:
        kwargs.append(f"metadata={metadata!r}")
    return f"{label} = infer({', '.join(args)}, {', '.join(kwargs)})"


def infer_command(
    label: str = typer.Option(
        ..., "--label", help="Identifier the evidence Claim takes after `infer()` returns it."
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
    rationale: str | None = typer.Option(
        None, "--rationale", help="Optional natural-language justification."
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
    r"""Author an ``infer(...)`` Bayesian-inference statement.

    Examples:

    .. code-block:: bash

        # Reference an existing hypothesis Claim
        gaia author infer --evidence sky_red --hypothesis storm_tonight \
            --p-e-given-h 0.7 --p-e-given-not-h 0.2 --label sky_evidence

        # Mint a fresh hypothesis from prose (R4 prose mode)
        gaia author infer --evidence sky_red \
            --hypothesis-content "A storm rolls in tonight." \
            --p-e-given-h 0.7 --label sky_evidence
    """
    del json_

    # --- mutual-exclusion check on hypothesis-mode ----------------------- #
    if hypothesis is None and hypothesis_content is None:
        emit_syntax_error(
            "infer",
            "infer requires exactly one of --hypothesis / --hypothesis-content",
            target=str(target),
            human=human,
        )
        return
    if hypothesis is not None and hypothesis_content is not None:
        emit_syntax_error(
            "infer",
            "--hypothesis and --hypothesis-content are mutually exclusive",
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

    given_list = split_csv(given)

    # --- prose mode: mint a fresh hypothesis claim ------------------------ #
    prepended: tuple[tuple[str, str], ...] = ()
    if hypothesis_content is not None:
        if hypothesis_label is not None:
            auto_label = hypothesis_label
        else:
            reserved = {label, evidence, *given_list}
            auto_label = slugify_label(hypothesis_content, existing=reserved)
        prepended = ((auto_label, build_auto_claim_statement(auto_label, hypothesis_content)),)
        resolved_hypothesis = auto_label
    else:
        assert hypothesis is not None  # mutex check above
        resolved_hypothesis = hypothesis

    generated_code = _render_infer_statement(
        label=label,
        evidence=evidence,
        hypothesis=resolved_hypothesis,
        p_e_given_h=p_e_given_h,
        p_e_given_not_h=p_e_given_not_h,
        given=given_list,
        rationale=rationale,
        metadata=metadata_dict,
    )
    references = [evidence, resolved_hypothesis, *given_list]
    proposed_op = ProposedAuthorOp(
        verb="infer",
        kind="reasoning",
        label=label,
        references=references,
        generated_code=generated_code,
        required_imports=("infer",),
        prepended_statements=prepended,
    )
    run_author_op(
        proposed_op,
        target=target,
        human=human,
        check=check,
        interactive=interactive,
    )


__all__ = ["infer_command"]
