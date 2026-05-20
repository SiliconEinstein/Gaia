"""``gaia bayes compare`` — append a ``bayes.compare(...)`` statement.

Maps to ``gaia.engine.bayes.dsl.compare.compare``:

.. code-block:: python

    bayes.compare(
        data: Claim | list[Claim],
        *,
        models: list[Claim],
        background=None,
        rationale="",
        label=None,
        exclusivity="exhaustive_pairwise_complement",
        metadata=None,
    )

Cli surface:

* ``--data <csv>`` — comma-separated identifier list of observation
  Claims (one or more).
* ``--model <ident>`` — identifier of the primary bayes.model helper Claim.
* ``--against <csv>`` — comma-separated identifier list of alternative
  model Claims (one or more; ``compare`` requires at least two models).
* ``--exclusivity <mode>`` — one of ``pairwise_contradiction`` /
  ``exhaustive_pairwise_complement``; default matches the engine default.
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
    validate_identifier_flag,
)
from gaia.cli.commands.author._proposed_op import ProposedAuthorOp
from gaia.cli.commands.author._runner import run_author_op

_EXCLUSIVITY_VALUES = frozenset({"pairwise_contradiction", "exhaustive_pairwise_complement"})


def _render_compare_statement(
    *,
    label: str,
    data: list[str],
    model: str,
    against: list[str],
    background: list[str],
    rationale: str | None,
    exclusivity: str,
    metadata: dict[str, Any] | None,
) -> str:
    """Render the proposed ``bayes.compare(...)`` statement."""
    # Data is a single Claim or a list of Claims; render as bare
    # identifier when single, as ``[...]`` when multiple.
    data_arg = data[0] if len(data) == 1 else "[" + ", ".join(data) + "]"
    args = [data_arg]
    models = [model, *against]
    kwargs = [f"models=[{', '.join(models)}]"]
    if background:
        kwargs.append(f"background=[{', '.join(background)}]")
    if rationale:
        kwargs.append(f"rationale={rationale!r}")
    if exclusivity != "exhaustive_pairwise_complement":
        # Only emit when non-default to keep the rendered call concise.
        kwargs.append(f"exclusivity={exclusivity!r}")
    kwargs.append(f"label={label!r}")
    if metadata:
        kwargs.append(f"metadata={metadata!r}")
    return f"{label} = bayes.compare({', '.join(args)}, {', '.join(kwargs)})"


def compare_command(
    label: str = typer.Option(
        ..., "--label", help="Identifier the comparison helper Claim binds to."
    ),
    data: str = typer.Option(
        ...,
        "--data",
        help="Comma-separated identifier(s) of observation Claim(s).",
    ),
    model: str = typer.Option(
        ...,
        "--model",
        help="Identifier of the primary bayes.model helper Claim.",
    ),
    against: str | None = typer.Option(
        None,
        "--against",
        help="Comma-separated identifier(s) of alternative model Claim(s); at least one required.",
    ),
    exclusivity: str = typer.Option(
        "exhaustive_pairwise_complement",
        "--exclusivity",
        help=(
            "Structural constraint between the compared hypotheses. "
            "exhaustive_pairwise_complement (default): the hypotheses "
            "partition the outcome space — exactly one must be true; "
            "posterior mass flows pairwise as in standard Bayesian "
            "model selection (suitable when the listed models are "
            "collectively exhaustive). "
            "pairwise_contradiction: the hypotheses are mutually "
            "exclusive but not exhaustive — at most one is true; an "
            "'all hypotheses false' joint state is permitted (use "
            "when you believe all listed models may be wrong)."
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
    background: str | None = typer.Option(
        None,
        "--background",
        help="Comma-separated identifiers passed as the background kwarg.",
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
    r"""Author a ``bayes.compare(data, models=[model, ...])`` statement.

    ``bayes compare`` is the quantitative culmination of a qualitative
    authoring graph (claims, observations, derivations, exclusive
    operators). For a self-contained two-prior posterior comparison
    without a qualitative argument, libraries like PyMC or
    scipy.stats may be a lighter fit.

    Example:

    .. code-block:: bash

        gaia bayes compare \
            --data f2_count_observation \
            --model mendel_count_model \
            --against diffuse_count_model \
            --rationale "Compare Mendel vs diffuse on F2 counts." \
            --label mendel_count_likelihood
    """
    del json_

    if exclusivity not in _EXCLUSIVITY_VALUES:
        allowed = ", ".join(sorted(_EXCLUSIVITY_VALUES))
        emit_syntax_error(
            "bayes.compare",
            f"--exclusivity must be one of: {allowed} (got {exclusivity!r})",
            target=str(target),
            human=human,
        )
        return

    metadata_dict, metadata_error = parse_metadata(metadata)
    if metadata_error:
        emit_syntax_error("bayes.compare", metadata_error, target=str(target), human=human)
        return

    if not validate_identifier_flag(
        model, verb="bayes.compare", flag="--model", target=str(target), human=human
    ):
        return
    data_list, data_error = split_csv_idents(data)
    if data_error:
        emit_syntax_error(
            "bayes.compare",
            f"--data rejected: {data_error}",
            target=str(target),
            human=human,
            kind="prewrite.expr_unsafe",
        )
        return
    if not data_list:
        emit_syntax_error(
            "bayes.compare",
            "--data must list at least one observation identifier",
            target=str(target),
            human=human,
        )
        return
    against_list, against_error = split_csv_idents(against)
    if against_error:
        emit_syntax_error(
            "bayes.compare",
            f"--against rejected: {against_error}",
            target=str(target),
            human=human,
            kind="prewrite.expr_unsafe",
        )
        return
    if not against_list:
        emit_syntax_error(
            "bayes.compare",
            "--against must list at least one alternative model",
            target=str(target),
            human=human,
        )
        return
    background_list, background_error = split_csv_idents(background)
    if background_error:
        emit_syntax_error(
            "bayes.compare",
            f"--background rejected: {background_error}",
            target=str(target),
            human=human,
            kind="prewrite.expr_unsafe",
        )
        return

    generated_code = _render_compare_statement(
        label=label,
        data=data_list,
        model=model,
        against=against_list,
        background=background_list,
        rationale=rationale,
        exclusivity=exclusivity,
        metadata=metadata_dict,
    )
    references = [*data_list, model, *against_list, *background_list]
    target_file = normalize_file_option(file)
    proposed_op = ProposedAuthorOp(
        verb="bayes.compare",
        kind="reasoning",
        label=label,
        references=references,
        generated_code=generated_code,
        required_imports=("bayes",),
        target_file=target_file,
        sibling_imports=build_sibling_imports(references, target_file=target_file),
    )
    run_author_op(
        proposed_op,
        target=target,
        human=human,
        check=check,
        interactive=interactive,
    )


__all__ = ["compare_command"]
