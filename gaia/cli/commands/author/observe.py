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

The cli supports both the discrete-claim form with optional ``--given``
and the continuous form via ``--value`` / ``--error``. Both shapes go
through the same pre-write pipeline; the rendered statement diverges
only in which kwargs land on the call.

``--value`` / ``--error`` values are forwarded verbatim (``--value 203``
→ ``value=203``); the literal-or-identifier validator gates the flag
boundary, and the rendered snippet is Python source that the engine
evaluates at package-load time.

Prose mode for the observation slot via ``--observation-content
"<prose>"``: mints a fresh ``claim(prose)`` statement, uses the
cli-derived slug as the first positional arg of ``observe(...)``, and
prepends the auto-claim to the target file ahead of the
``observe(...)`` statement. Mutually exclusive with ``--conclusion``;
``--observation-label`` overrides the auto-derived slug (mirrors the
``--conclusion-label`` discipline on ``derive``). Only the
discrete-claim observation form supports prose mode; the continuous
form (``--value`` / ``--error``) targets an existing Distribution by
construction and so retains the identifier-only ``--conclusion``
shape.
"""

from __future__ import annotations

from typing import Any

import typer

from gaia.cli.commands.author._common import (
    PrewriteUnsafeError,
    build_sibling_imports,
    emit_syntax_error,
    normalize_file_option,
    parse_literal_or_identifier,
    parse_metadata,
    split_csv,
    split_csv_idents,
)
from gaia.cli.commands.author._proposed_op import ProposedAuthorOp
from gaia.cli.commands.author._prose import build_auto_claim_statement, slugify_label
from gaia.cli.commands.author._runner import run_author_op


def _validate_given_and_background(
    *,
    given: str | None,
    background: str | None,
    target: str,
    human: bool,
) -> tuple[list[str], list[str]] | None:
    """Run --given / --background through :func:`split_csv_idents`."""
    given_list, given_error = split_csv_idents(given)
    if given_error:
        emit_syntax_error(
            "observe",
            f"--given rejected: {given_error}",
            target=target,
            human=human,
            kind="prewrite.expr_unsafe",
        )
        return None
    background_list, background_error = split_csv_idents(background)
    if background_error:
        emit_syntax_error(
            "observe",
            f"--background rejected: {background_error}",
            target=target,
            human=human,
            kind="prewrite.expr_unsafe",
        )
        return None
    return given_list, background_list


def _check_continuous_mutex(
    *,
    value: str | None,
    error: str | None,
    given_list: list[str],
    target: str,
    human: bool,
) -> bool:
    """Continuous-form rules: --value forbids --given; --error needs --value.

    Returns ``True`` to proceed, ``False`` after emitting the
    rejection envelope.
    """
    if value is not None and given_list:
        emit_syntax_error(
            "observe",
            (
                "--value (continuous observe) is incompatible with --given "
                "(use a wrapper Claim instead)"
            ),
            target=target,
            human=human,
        )
        return False
    if error is not None and value is None:
        emit_syntax_error(
            "observe",
            "--error requires --value (continuous observation form)",
            target=target,
            human=human,
        )
        return False
    return True


def _validate_value_and_error(
    *,
    value: str | None,
    error: str | None,
    target: str,
    human: bool,
) -> tuple[str | None, str | None, list[str]] | None:
    """Run --value / --error through parse_literal_or_identifier.

    Returns ``(rendered_value, rendered_error, references_sink)`` on
    success or ``None`` after emitting the rejection envelope.
    """
    references_sink: list[str] = []
    rendered_value: str | None = None
    rendered_error: str | None = None
    if value is not None:
        try:
            _, rendered_value = parse_literal_or_identifier(value, references_sink=references_sink)
        except PrewriteUnsafeError as exc:
            emit_syntax_error(
                "observe",
                f"--value rejected: {exc}",
                target=target,
                human=human,
                kind="prewrite.expr_unsafe",
            )
            return None
    if error is not None:
        try:
            _, rendered_error = parse_literal_or_identifier(error, references_sink=references_sink)
        except PrewriteUnsafeError as exc:
            emit_syntax_error(
                "observe",
                f"--error rejected: {exc}",
                target=target,
                human=human,
                kind="prewrite.expr_unsafe",
            )
            return None
    return rendered_value, rendered_error, references_sink


def _check_observation_mode_mutex(
    *,
    conclusion: str | None,
    observation_content: str | None,
    observation_prose: str | None,
    observation_label: str | None,
    value: str | None,
    error: str | None,
    target: str,
    human: bool,
) -> bool:
    """Enforce the mode-shape rules for observe(...).

    Exactly one of ``--conclusion`` / ``--observation-content`` /
    ``--observation-prose`` must be set. ``--observation-label`` only
    applies with ``--observation-content``. Prose modes are incompatible
    with the continuous form (``--value`` / ``--error``).

    Returns ``True`` to proceed, ``False`` after emitting the rejection
    envelope.
    """
    obs_modes = [conclusion, observation_content, observation_prose]
    obs_modes_set = sum(1 for value_ in obs_modes if value_ is not None)
    if obs_modes_set == 0:
        emit_syntax_error(
            "observe",
            (
                "observe requires exactly one of --conclusion / "
                "--observation-content / --observation-prose"
            ),
            target=target,
            human=human,
        )
        return False
    if obs_modes_set > 1:
        emit_syntax_error(
            "observe",
            (
                "--conclusion, --observation-content, and --observation-prose "
                "are mutually exclusive — pick exactly one"
            ),
            target=target,
            human=human,
        )
        return False
    if observation_label is not None and observation_content is None:
        emit_syntax_error(
            "observe",
            "--observation-label only applies with --observation-content",
            target=target,
            human=human,
        )
        return False
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
            target=target,
            human=human,
        )
        return False
    return True


def _resolve_observation_mode(
    *,
    conclusion: str | None,
    observation_content: str | None,
    observation_prose: str | None,
    observation_label: str | None,
    dsl_binding_name: str | None,
    given_list: list[str],
    background_list: list[str],
) -> tuple[str, list[str], str, tuple[tuple[str, str], ...]]:
    """Resolve the observation-mode dispatch.

    Returns ``(conclusion_expr, references, observation_kind, prepended)``.
    The caller has already enforced mode mutex via
    :func:`_check_observation_mode_mutex`.
    """
    if observation_content is not None:
        if observation_label is not None:
            auto_label = observation_label
        else:
            reserved = {*given_list, *background_list}
            if dsl_binding_name is not None:
                reserved.add(dsl_binding_name)
            auto_label = slugify_label(observation_content, existing=reserved)
        prepended = ((auto_label, build_auto_claim_statement(auto_label, observation_content)),)
        return auto_label, [auto_label, *given_list, *background_list], "auto_mint", prepended
    if observation_prose is not None:
        # Inline-prose: emit ``observe('<prose>', ...)`` directly. The
        # engine's ``observe(conclusion: Claim | str, ...)`` polymorphism
        # wraps the prose into an anonymous Claim at runtime; no named
        # module-scope binding is introduced.
        return repr(observation_prose), [*given_list, *background_list], "inline_prose", ()
    assert conclusion is not None  # mutex check above
    return conclusion, [conclusion, *given_list, *background_list], "qid", ()


def _render_observe_statement(
    *,
    binding_name: str | None,
    engine_label: str | None,
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
    quoted string literal (``--observation-prose``).
    """
    args = [conclusion_expr]
    kwargs: list[str] = []
    if engine_label is not None:
        kwargs.append(f"label={engine_label!r}")
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
    rendered_args = ", ".join([*args, *kwargs])
    call = f"observe({rendered_args})"
    if binding_name is None:
        return call
    return f"{binding_name} = {call}"


def observe_command(
    label: str | None = typer.Option(
        None,
        "--label",
        help=(
            "Engine `label=` kwarg on the rendered observe(...) call. "
            "Distinct from --dsl-binding-name (the Python LHS)."
        ),
    ),
    dsl_binding_name: str | None = typer.Option(
        None,
        "--dsl-binding-name",
        help=(
            "Python LHS for the rendered statement (``<name> = "
            "observe(...)``). Omit to emit a bare expression."
        ),
    ),
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
    export: bool = typer.Option(
        True,
        "--export/--no-export",
        help=("Add --dsl-binding-name to __all__ on a successful write (default on for observe)."),
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
    r"""Append an ``observe(...)`` measurement event.

    Example:
        gaia author observe --conclusion my_distribution \
            --value 203 --error 5 \
            --dsl-binding-name temperature_obs --label temperature_obs
    """
    del json_

    # --- mutual-exclusion check on observation-mode ---------------------- #
    if not _check_observation_mode_mutex(
        conclusion=conclusion,
        observation_content=observation_content,
        observation_prose=observation_prose,
        observation_label=observation_label,
        value=value,
        error=error,
        target=str(target),
        human=human,
    ):
        return

    metadata_dict, metadata_error = parse_metadata(metadata)
    if metadata_error:
        emit_syntax_error("observe", metadata_error, target=str(target), human=human)
        return

    csv_pair = _validate_given_and_background(
        given=given, background=background, target=str(target), human=human
    )
    if csv_pair is None:
        return
    given_list, background_list = csv_pair
    # ``--source-refs`` is free-form annotation text — keep the
    # permissive splitter; repr() renders the strings safely into source.
    source_refs_list = split_csv(source_refs)

    # --value / --error are spliced directly into the rendered
    # observe() call. Validate as literal-or-identifier so the postwrite
    # import can't execute crafted argv.
    val_err_refs = _validate_value_and_error(
        value=value, error=error, target=str(target), human=human
    )
    if val_err_refs is None:
        return
    rendered_value, rendered_error, references_sink = val_err_refs

    # Mutual-exclusion sanity for continuous form.
    if not _check_continuous_mutex(
        value=value,
        error=error,
        given_list=given_list,
        target=str(target),
        human=human,
    ):
        return

    # --- resolve observation mode ---------------------------------------- #
    # ``conclusion_expr`` is the Python source spelling at the call site;
    # ``references`` lists the identifiers the pre-write (c) check must
    # resolve in module scope (inline-prose contributes none of its own).
    conclusion_expr, references, observation_kind, prepended = _resolve_observation_mode(
        conclusion=conclusion,
        observation_content=observation_content,
        observation_prose=observation_prose,
        observation_label=observation_label,
        dsl_binding_name=dsl_binding_name,
        given_list=given_list,
        background_list=background_list,
    )

    # Merge value/error bare-identifier references into the verb-level
    # reference list so prewrite resolves them (and Axis 2 inserts
    # cross-file imports when ``--file <sibling>`` lands the statement
    # in a non-init module).
    references = [*references, *references_sink]

    generated_code = _render_observe_statement(
        binding_name=dsl_binding_name,
        engine_label=label,
        conclusion_expr=conclusion_expr,
        value=rendered_value,
        error=rendered_error,
        given=given_list,
        source_refs=source_refs_list,
        rationale=rationale,
        metadata=metadata_dict,
        background=background_list,
    )
    target_file = normalize_file_option(file)
    proposed_op = ProposedAuthorOp(
        verb="observe",
        kind="reasoning",
        label=dsl_binding_name,
        references=references,
        generated_code=generated_code,
        required_imports=("observe",),
        target_file=target_file,
        sibling_imports=build_sibling_imports(references, target_file=target_file),
        prepended_statements=prepended,
        extra_payload={"observation_kind": observation_kind},
        export=export,
    )
    run_author_op(
        proposed_op,
        target=target,
        human=human,
        check=check,
        interactive=interactive,
    )


__all__ = ["observe_command"]
