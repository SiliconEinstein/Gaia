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
"""

from __future__ import annotations

from typing import Any

import typer

from gaia.cli.commands.author._common import emit_syntax_error, parse_metadata, split_csv
from gaia.cli.commands.author._proposed_op import ProposedAuthorOp
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
    hypothesis: str = typer.Option(..., "--hypothesis", help="Identifier of the hypothesis Claim."),
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

    Example:

    .. code-block:: bash

        gaia author infer --evidence sky_red --hypothesis storm_tonight \
            --p-e-given-h 0.7 --p-e-given-not-h 0.2 --label sky_evidence
    """
    del json_

    metadata_dict, metadata_error = parse_metadata(metadata)
    if metadata_error:
        emit_syntax_error("infer", metadata_error, target=str(target), human=human)
        return

    given_list = split_csv(given)
    generated_code = _render_infer_statement(
        label=label,
        evidence=evidence,
        hypothesis=hypothesis,
        p_e_given_h=p_e_given_h,
        p_e_given_not_h=p_e_given_not_h,
        given=given_list,
        rationale=rationale,
        metadata=metadata_dict,
    )
    references = [evidence, hypothesis, *given_list]
    proposed_op = ProposedAuthorOp(
        verb="infer",
        kind="reasoning",
        label=label,
        references=references,
        generated_code=generated_code,
        required_imports=("infer",),
    )
    run_author_op(
        proposed_op,
        target=target,
        human=human,
        check=check,
        interactive=interactive,
    )


__all__ = ["infer_command"]
