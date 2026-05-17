"""``gaia bayes model`` — append a ``bayes.model(...)`` predictive-model statement.

Maps to ``gaia.engine.bayes.dsl.model.model``:

.. code-block:: python

    bayes.model(
        hypothesis: Claim,
        *,
        observable: Variable,
        distribution: Distribution,
        background=None,
        rationale="",
        label=None,
        metadata=None,
    )

Cli surface:

* ``--hypothesis <ident>`` — identifier of the hypothesis Claim.
* ``--observable <ident>`` — identifier of the Variable being predicted.
* ``--distribution <ident>`` — identifier of the Distribution binding
  (created via ``bayes binomial`` / ``bayes normal`` / etc.).
* ``--background <csv>`` — optional comma-separated background Knowledge
  identifiers (forwarded to ``background=[...]``).
* ``--rationale <str>`` — optional natural-language justification.
* ``--label <ident>`` — identifier the helper Claim binds to.
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


def _render_model_statement(
    *,
    label: str,
    hypothesis: str,
    observable: str,
    distribution: str,
    background: list[str],
    rationale: str | None,
    metadata: dict[str, Any] | None,
) -> str:
    """Render the proposed ``bayes.model(...)`` statement."""
    args = [hypothesis]
    kwargs = [f"observable={observable}", f"distribution={distribution}"]
    if background:
        kwargs.append(f"background=[{', '.join(background)}]")
    if rationale:
        kwargs.append(f"rationale={rationale!r}")
    kwargs.append(f"label={label!r}")
    if metadata:
        kwargs.append(f"metadata={metadata!r}")
    return f"{label} = bayes.model({', '.join(args)}, {', '.join(kwargs)})"


def model_command(
    label: str = typer.Option(
        ..., "--label", help="Identifier the predictive-model helper Claim binds to."
    ),
    hypothesis: str = typer.Option(
        ...,
        "--hypothesis",
        help="Identifier of the hypothesis Claim being modelled.",
    ),
    observable: str = typer.Option(
        ...,
        "--observable",
        help="Identifier of the Variable the model predicts.",
    ),
    distribution: str = typer.Option(
        ...,
        "--distribution",
        help=(
            "Identifier of the Distribution binding (e.g. one created via "
            "`bayes binomial` / `bayes normal` / ...)."
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
    r"""Author a ``bayes.model(hypothesis, observable=..., distribution=...)`` statement.

    Example:

    .. code-block:: bash

        gaia bayes model \
            --hypothesis mendelian_segregation_model \
            --observable f2_dominant_count \
            --distribution mendel_binomial \
            --background monohybrid_cross_setup,dominance_background \
            --rationale "Mendel predicts Binomial(N, 3/4) for F2 dominant counts." \
            --label mendel_count_model
    """
    del json_

    metadata_dict, metadata_error = parse_metadata(metadata)
    if metadata_error:
        emit_syntax_error("bayes.model", metadata_error, target=str(target), human=human)
        return

    background_list = split_csv(background)
    generated_code = _render_model_statement(
        label=label,
        hypothesis=hypothesis,
        observable=observable,
        distribution=distribution,
        background=background_list,
        rationale=rationale,
        metadata=metadata_dict,
    )
    references = [hypothesis, observable, distribution, *background_list]
    proposed_op = ProposedAuthorOp(
        verb="bayes.model",
        kind="reasoning",
        label=label,
        references=references,
        generated_code=generated_code,
        # ``bayes`` must be importable in the target file. The scaffold
        # template seeds ``from gaia.engine import bayes``; the
        # pre-write reference check accepts the dotted-call form because
        # ``bayes`` itself is the bound name in module scope.
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


__all__ = ["model_command"]
