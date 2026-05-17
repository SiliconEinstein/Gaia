"""``gaia author observe`` — append an ``observe(...)`` statement.

Maps to ``gaia.engine.lang.dsl.support.observe``:

.. code-block:: python

    observe(
        conclusion,
        *,
        value=...,
        error=None,
        given=(),
        background=None,
        source_refs=None,
        rationale="",
        label=None,
    )

The DSL recognises two authoring shapes:

1. **Discrete claim observation** — ``observe(my_claim)``. No-premise
   observation pins ``my_claim.prior`` to ``1 - CROMWELL_EPS``. Use
   ``--given`` to record a conditional observation that does not pin
   the conclusion.
2. **Continuous quantity observation** — ``observe(distribution,
   value=v, error=sigma)``. Records a measurement event for a
   :class:`Distribution`-typed quantity.

R2 ships the discrete-claim form with optional ``--given`` plus the
continuous form via ``--value`` / ``--error``. Both shapes go through
the same pre-write pipeline; the rendered statement diverges only in
which kwargs land on the call.

R2 does not parse ``--value`` / ``--error`` as expressions — they are
forwarded verbatim as numeric literals (``--value 203`` →
``value=203``). For Quantity-valued observations the user can pass a
Python expression with the right unit accessors via the same channel,
since the rendered snippet is Python source that the engine evaluates at
package-load time.
"""

from __future__ import annotations

from typing import Any

import typer

from gaia.cli.commands.author._common import emit_syntax_error, parse_metadata, split_csv
from gaia.cli.commands.author._proposed_op import ProposedAuthorOp
from gaia.cli.commands.author._runner import run_author_op


def _render_observe_statement(
    *,
    label: str,
    conclusion: str,
    value: str | None,
    error: str | None,
    given: list[str],
    source_refs: list[str],
    rationale: str | None,
    metadata: dict[str, Any] | None,
) -> str:
    """Render the proposed ``observe(...)`` statement."""
    args = [conclusion]
    kwargs: list[str] = [f"label={label!r}"]
    if value is not None:
        # Forward verbatim so callers can pass numeric literals or
        # Quantity expressions; lexically safe because pre-write parses
        # the resulting snippet as Python before write.
        kwargs.append(f"value={value}")
    if error is not None:
        kwargs.append(f"error={error}")
    if given:
        kwargs.append(f"given=[{', '.join(given)}]")
    if source_refs:
        kwargs.append(f"source_refs={source_refs!r}")
    if rationale:
        kwargs.append(f"rationale={rationale!r}")
    if metadata:
        kwargs.append(f"metadata={metadata!r}")
    return f"{label} = observe({', '.join(args)}, {', '.join(kwargs)})"


def observe_command(
    label: str = typer.Option(..., "--label", help="Identifier the observation Claim binds to."),
    conclusion: str = typer.Option(
        ...,
        "--conclusion",
        help="Identifier of the observed Claim or Distribution.",
    ),
    target: str = typer.Option(
        ".", "--target", help="Path to the target Gaia package (default: cwd)."
    ),
    value: str | None = typer.Option(
        None,
        "--value",
        help=(
            "Numeric value (continuous form). Forwarded verbatim — pass a literal "
            "(`--value 203`) or a Quantity expression (`--value '203 * ureg.K'`)."
        ),
    ),
    error: str | None = typer.Option(
        None,
        "--error",
        help="Observation error (continuous form): scalar sigma or Distribution.",
    ),
    given: str | None = typer.Option(
        None,
        "--given",
        help="Comma-separated premise identifiers for a conditional discrete observation.",
    ),
    source_refs: str | None = typer.Option(
        None,
        "--source-refs",
        help="Comma-separated source reference strings attached to the observation.",
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
    r"""Author an ``observe(...)`` measurement event.

    Examples:

    .. code-block:: bash

        # Discrete claim observation
        gaia author observe --conclusion stars_visible --label visible_obs

        # Continuous measurement
        gaia author observe --conclusion T_c --value 203 --error 5 \
            --label temperature_obs
    """
    del json_

    metadata_dict, metadata_error = parse_metadata(metadata)
    if metadata_error:
        emit_syntax_error("observe", metadata_error, target=str(target), human=human)
        return

    given_list = split_csv(given)
    source_refs_list = split_csv(source_refs)

    # Mutual-exclusion sanity: continuous form (with value) cannot accept --given.
    if value is not None and given_list:
        emit_syntax_error(
            "observe",
            (
                "--value (continuous observe) is incompatible with --given "
                "(use a wrapper Claim instead)"
            ),
            target=str(target),
            human=human,
        )
        return
    if error is not None and value is None:
        emit_syntax_error(
            "observe",
            "--error requires --value (continuous observation form)",
            target=str(target),
            human=human,
        )
        return

    generated_code = _render_observe_statement(
        label=label,
        conclusion=conclusion,
        value=value,
        error=error,
        given=given_list,
        source_refs=source_refs_list,
        rationale=rationale,
        metadata=metadata_dict,
    )
    references = [conclusion, *given_list]
    proposed_op = ProposedAuthorOp(
        verb="observe",
        kind="reasoning",
        label=label,
        references=references,
        generated_code=generated_code,
        required_imports=("observe",),
    )
    run_author_op(
        proposed_op,
        target=target,
        human=human,
        check=check,
        interactive=interactive,
    )


__all__ = ["observe_command"]
