"""``gaia bayes likelihood`` — append a ``bayes.likelihood(...)`` statement.

Maps to ``gaia.engine.bayes.dsl.likelihood.likelihood``:

.. code-block:: python

    bayes.likelihood(
        data: Claim | list[Claim],
        *,
        model: Claim,
        against: Claim | list[Claim] = (),
        background=None,
        rationale="",
        label=None,
        exclusivity="pairwise_contradiction",
        metadata=None,
    )

Cli surface:

* ``--data <csv>`` — comma-separated identifier list of observation
  Claims (one or more).
* ``--model <ident>`` — identifier of the primary bayes.model helper Claim.
* ``--against <csv>`` — comma-separated identifier list of alternative
  model Claims (zero or more).
* ``--exclusivity <mode>`` — one of ``none`` /
  ``pairwise_contradiction`` / ``exhaustive_pairwise_complement``;
  default ``pairwise_contradiction`` matches the engine default.
"""

from __future__ import annotations

from typing import Any

import typer

from gaia.cli.commands.author._common import (
    emit_syntax_error,
    normalize_file_option,
    parse_metadata,
    split_csv,
)
from gaia.cli.commands.author._proposed_op import ProposedAuthorOp
from gaia.cli.commands.author._runner import run_author_op

_EXCLUSIVITY_VALUES = frozenset(
    {"none", "pairwise_contradiction", "exhaustive_pairwise_complement"}
)


def _render_likelihood_statement(
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
    """Render the proposed ``bayes.likelihood(...)`` statement."""
    # Data is a single Claim or a list of Claims; render as bare
    # identifier when single, as ``[...]`` when multiple.
    data_arg = data[0] if len(data) == 1 else "[" + ", ".join(data) + "]"
    args = [data_arg]
    kwargs = [f"model={model}"]
    if against:
        kwargs.append(f"against=[{', '.join(against)}]")
    if background:
        kwargs.append(f"background=[{', '.join(background)}]")
    if rationale:
        kwargs.append(f"rationale={rationale!r}")
    if exclusivity != "pairwise_contradiction":
        # Only emit when non-default to keep the rendered call concise.
        kwargs.append(f"exclusivity={exclusivity!r}")
    kwargs.append(f"label={label!r}")
    if metadata:
        kwargs.append(f"metadata={metadata!r}")
    return f"{label} = bayes.likelihood({', '.join(args)}, {', '.join(kwargs)})"


def likelihood_command(
    label: str = typer.Option(
        ..., "--label", help="Identifier the likelihood helper Claim binds to."
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
        help="Comma-separated identifier(s) of alternative model Claim(s).",
    ),
    exclusivity: str = typer.Option(
        "pairwise_contradiction",
        "--exclusivity",
        help=(
            "Structural-action mode: 'none' / 'pairwise_contradiction' (default) / "
            "'exhaustive_pairwise_complement'."
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
    r"""Author a ``bayes.likelihood(data, model=..., against=...)`` statement.

    Example:

    .. code-block:: bash

        gaia bayes likelihood \
            --data f2_count_observation \
            --model mendel_count_model \
            --against diffuse_count_model \
            --exclusivity none \
            --rationale "Compare Mendel vs diffuse on F2 counts." \
            --label mendel_count_likelihood
    """
    del json_

    if exclusivity not in _EXCLUSIVITY_VALUES:
        allowed = ", ".join(sorted(_EXCLUSIVITY_VALUES))
        emit_syntax_error(
            "bayes.likelihood",
            f"--exclusivity must be one of: {allowed} (got {exclusivity!r})",
            target=str(target),
            human=human,
        )
        return

    metadata_dict, metadata_error = parse_metadata(metadata)
    if metadata_error:
        emit_syntax_error("bayes.likelihood", metadata_error, target=str(target), human=human)
        return

    data_list = split_csv(data)
    if not data_list:
        emit_syntax_error(
            "bayes.likelihood",
            "--data must list at least one observation identifier",
            target=str(target),
            human=human,
        )
        return
    against_list = split_csv(against)
    background_list = split_csv(background)

    generated_code = _render_likelihood_statement(
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
    proposed_op = ProposedAuthorOp(
        verb="bayes.likelihood",
        kind="reasoning",
        label=label,
        references=references,
        generated_code=generated_code,
        required_imports=("bayes",),
        target_file=normalize_file_option(file),
    )
    run_author_op(
        proposed_op,
        target=target,
        human=human,
        check=check,
        interactive=interactive,
    )


__all__ = ["likelihood_command"]
