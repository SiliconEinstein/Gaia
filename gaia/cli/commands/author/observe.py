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

R4·❓A=A — prose mode for the observation slot. ``--observation-content
"<prose>"`` mints a fresh ``claim(prose)`` statement, uses the
cli-derived slug as the first positional arg of ``observe(...)``, and
prepends the auto-claim to the target file ahead of the
``observe(...)`` statement. Mutually exclusive with ``--conclusion``;
``--observation-label`` overrides the auto-derived slug (mirrors R3's
``--conclusion-label`` discipline). Semantically honest because a
discrete observation is a fresh measurement statement being introduced
into the package — the prose maps cleanly onto a new Claim. Only the
discrete-claim observation form supports prose mode; the continuous
form (``--value`` / ``--error``) targets an existing Distribution by
construction and so retains the identifier-only ``--conclusion``
shape.
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
from gaia.cli.commands.author._prose import build_auto_claim_statement, slugify_label
from gaia.cli.commands.author._runner import run_author_op


def _render_observe_statement(
    *,
    label: str,
    conclusion_expr: str,
    value: str | None,
    error: str | None,
    given: list[str],
    source_refs: list[str],
    rationale: str | None,
    metadata: dict[str, Any] | None,
    background: list[str],
) -> str:
    """Render the proposed ``observe(...)`` statement.

    ``conclusion_expr`` is the Python source spelling at the call site:
    either a bare identifier (``--conclusion`` / auto-mint slug) or a
    quoted string literal (R7 G6 ``--observation-prose``).
    """
    args = [conclusion_expr]
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
    if background:
        kwargs.append(f"background=[{', '.join(background)}]")
    if source_refs:
        kwargs.append(f"source_refs={source_refs!r}")
    if rationale:
        kwargs.append(f"rationale={rationale!r}")
    if metadata:
        kwargs.append(f"metadata={metadata!r}")
    return f"{label} = observe({', '.join(args)}, {', '.join(kwargs)})"


def observe_command(
    label: str = typer.Option(..., "--label", help="Identifier the observation Claim binds to."),
    conclusion: str | None = typer.Option(
        None,
        "--conclusion",
        help=(
            "Identifier of the observed Claim or Distribution (must already be "
            "declared). Mutually exclusive with --observation-content."
        ),
    ),
    observation_content: str | None = typer.Option(
        None,
        "--observation-content",
        help=(
            "Prose for an auto-generated observation Claim. Mutually exclusive with "
            "--conclusion. Cli derives a snake-case slug for the label (override "
            "via --observation-label). Only valid for discrete observations; the "
            "continuous form (--value / --error) targets a Distribution and so "
            "must use --conclusion."
        ),
    ),
    observation_prose: str | None = typer.Option(
        None,
        "--observation-prose",
        help=(
            "Inline prose passed through the engine's "
            "``observe(conclusion: Claim | str, ...)`` polymorphism. Emits "
            "``observe('<prose>', ...)`` directly with no named binding. "
            "Mutually exclusive with --conclusion and --observation-content."
        ),
    ),
    observation_label: str | None = typer.Option(
        None,
        "--observation-label",
        help=(
            "Optional explicit label for the auto-generated observation Claim "
            "(only meaningful with --observation-content)."
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
    background: str | None = typer.Option(
        None,
        "--background",
        help="Comma-separated identifiers passed as the observe() background kwarg.",
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

        # Mint a fresh observation from prose (R4 prose mode)
        gaia author observe --observation-content "Stars visible in zenith." \
            --label visible_obs
    """
    del json_

    # --- mutual-exclusion check on observation-mode ---------------------- #
    obs_modes = [conclusion, observation_content, observation_prose]
    obs_modes_set = sum(1 for value_ in obs_modes if value_ is not None)
    if obs_modes_set == 0:
        emit_syntax_error(
            "observe",
            (
                "observe requires exactly one of --conclusion / "
                "--observation-content / --observation-prose"
            ),
            target=str(target),
            human=human,
        )
        return
    if obs_modes_set > 1:
        emit_syntax_error(
            "observe",
            (
                "--conclusion, --observation-content, and --observation-prose "
                "are mutually exclusive — pick exactly one"
            ),
            target=str(target),
            human=human,
        )
        return
    if observation_label is not None and observation_content is None:
        emit_syntax_error(
            "observe",
            "--observation-label only applies with --observation-content",
            target=str(target),
            human=human,
        )
        return
    # The continuous form needs a Distribution-typed identifier as the
    # observation target, so prose mode (which generates a Claim, not a
    # Distribution) is incompatible with --value / --error.
    if (observation_content is not None or observation_prose is not None) and (
        value is not None or error is not None
    ):
        emit_syntax_error(
            "observe",
            (
                "prose mode (--observation-content / --observation-prose) is "
                "incompatible with --value / --error (continuous form targets "
                "an existing Distribution; use --conclusion <dist_label>)"
            ),
            target=str(target),
            human=human,
        )
        return

    metadata_dict, metadata_error = parse_metadata(metadata)
    if metadata_error:
        emit_syntax_error("observe", metadata_error, target=str(target), human=human)
        return

    given_list = split_csv(given)
    background_list = split_csv(background)
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

    # --- resolve observation mode ---------------------------------------- #
    # ``conclusion_expr`` is the Python source spelling at the call site;
    # ``references`` lists the identifiers the pre-write (c) check must
    # resolve in module scope (inline-prose contributes none of its own).
    prepended: tuple[tuple[str, str], ...] = ()
    references: list[str]
    observation_kind: str
    if observation_content is not None:
        if observation_label is not None:
            auto_label = observation_label
        else:
            reserved = {label, *given_list, *background_list}
            auto_label = slugify_label(observation_content, existing=reserved)
        prepended = ((auto_label, build_auto_claim_statement(auto_label, observation_content)),)
        conclusion_expr = auto_label
        references = [auto_label, *given_list, *background_list]
        observation_kind = "auto_mint"
    elif observation_prose is not None:
        # R7 G6 inline-prose: emit ``observe('<prose>', ...)`` directly.
        # The engine's ``observe(conclusion: Claim | str, ...)``
        # polymorphism wraps the prose into an anonymous Claim at
        # runtime; no named module-scope binding is introduced.
        conclusion_expr = repr(observation_prose)
        references = [*given_list, *background_list]
        observation_kind = "inline_prose"
    else:
        assert conclusion is not None  # mutex check above
        conclusion_expr = conclusion
        references = [conclusion, *given_list, *background_list]
        observation_kind = "qid"

    generated_code = _render_observe_statement(
        label=label,
        conclusion_expr=conclusion_expr,
        value=value,
        error=error,
        given=given_list,
        source_refs=source_refs_list,
        rationale=rationale,
        metadata=metadata_dict,
        background=background_list,
    )
    proposed_op = ProposedAuthorOp(
        verb="observe",
        kind="reasoning",
        label=label,
        references=references,
        generated_code=generated_code,
        required_imports=("observe",),
        target_file=normalize_file_option(file),
        prepended_statements=prepended,
        extra_payload={"observation_kind": observation_kind},
    )
    run_author_op(
        proposed_op,
        target=target,
        human=human,
        check=check,
        interactive=interactive,
    )


__all__ = ["observe_command"]
