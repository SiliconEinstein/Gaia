"""gaia inquiry — public CLI sub-app.

Public commands per spec §G3:  focus, review.
Additional ProofState-extension subcommands (Round A1) exposed under
  inquiry obligation / hypothesis / reject / tactics
to support Lean-like reasoning process tracking, all implemented via state.json
only — no mutation of .py source / IR / priors / beliefs.
"""

from __future__ import annotations

import json
from pathlib import Path

import typer

from gaia.engine.inquiry.focus import resolve_focus_target
from gaia.engine.inquiry.review import (
    publish_blockers,
    render_markdown,
    render_text,
    resolve_graph,
    run_review,
)
from gaia.engine.inquiry.state import (
    VALID_OBLIGATION_KINDS,
    SyntheticHypothesis,
    SyntheticObligation,
    SyntheticRejection,
    append_tactic_event,
    load_state,
    mint_qid,
    pop_focus_frame,
    push_focus_frame,
    save_state,
)

inquiry_app = typer.Typer(
    name="inquiry",
    help=(
        "Gaia Inquiry — semantic review loop "
        "(focus / review / reject / obligation / hypothesis / tactics)."
    ),
    no_args_is_help=True,
)

obligation_app = typer.Typer(
    name="obligation", help="Manage synthetic obligations.", no_args_is_help=True
)
hypothesis_app = typer.Typer(
    name="hypothesis", help="Manage working hypotheses.", no_args_is_help=True
)
tactics_app = typer.Typer(
    name="tactics", help="Inspect the inquiry tactic log.", no_args_is_help=True
)

inquiry_app.add_typer(obligation_app, name="obligation")
inquiry_app.add_typer(hypothesis_app, name="hypothesis")
inquiry_app.add_typer(tactics_app, name="tactics")


# ---------------------------------------------------------------------------
# focus
# ---------------------------------------------------------------------------


@inquiry_app.command("focus")
def focus_command(
    target: str | None = typer.Argument(None, help="Focus target."),
    clear: bool = typer.Option(False, "--clear", help="Clear current focus."),
    push: bool = typer.Option(False, "--push", help="Push current focus and set new."),
    pop: bool = typer.Option(False, "--pop", help="Pop saved focus off the stack."),
    show_stack: bool = typer.Option(False, "--stack", help="Print focus stack."),
    path: str = typer.Option(".", "--path", help="Package path."),
) -> None:
    """Inspect or update the current inquiry focus.

    The inquiry focus is a state.json-only pointer to the claim, strategy,
    or freeform topic the agent is currently working on. ``focus`` is
    inspect-or-set: no args reads the current focus; a bare ``TARGET``
    sets it. The focus stack supports push/pop semantics so the agent
    can dive into a sub-claim and resume.

    Example:

    .. code-block:: bash

        # Read current focus:
        gaia inquiry focus

        # Set focus to a claim label:
        gaia inquiry focus my_claim_label

        # Push current focus and switch to a new one:
        gaia inquiry focus other_claim --push

        # Pop back to the prior focus:
        gaia inquiry focus --pop

        # Inspect the focus stack:
        gaia inquiry focus --stack

        # Clear the focus entirely:
        gaia inquiry focus --clear
    """
    flags_set = sum([bool(clear), bool(push), bool(pop), bool(show_stack)])
    if flags_set > 1:
        typer.echo("Error: --clear/--push/--pop/--stack are mutually exclusive.", err=True)
        raise typer.Exit(2)

    state = load_state(path)
    graph = resolve_graph(path)

    if clear:
        push_focus_frame(state)  # preserve history — not required but cheap
        state.focus_stack.pop()  # we actually don't want the frame on clear
        state.focus = None
        state.focus_kind = None
        state.focus_resolved_id = None
        save_state(path, state)
        append_tactic_event(path, "focus_clear", {})
        typer.echo("focus cleared")
        return

    if show_stack:
        typer.echo(f"current: {state.focus or '(none)'}")
        if not state.focus_stack:
            typer.echo("stack: (empty)")
            return
        typer.echo("stack (top → bottom):")
        for frame in reversed(state.focus_stack):
            raw = frame.get("focus") or "(none)"
            kind = frame.get("focus_kind") or "none"
            typer.echo(f"  - {raw}  [{kind}]")
        return

    if pop:
        if not state.focus_stack:
            typer.echo("Error: focus stack is empty.", err=True)
            raise typer.Exit(1)
        old = pop_focus_frame(state)
        save_state(path, state)
        append_tactic_event(
            path,
            "focus_pop",
            {"old": (old or {}).get("focus"), "restored": state.focus},
        )
        typer.echo(f"popped: {(old or {}).get('focus')} → {state.focus or '(none)'}")
        return

    if push:
        if not target:
            typer.echo("Error: --push requires a TARGET.", err=True)
            raise typer.Exit(2)
        push_focus_frame(state)
        binding = resolve_focus_target(target, graph)
        state.focus = binding.raw
        state.focus_kind = binding.kind
        state.focus_resolved_id = binding.resolved_id
        save_state(path, state)
        append_tactic_event(path, "focus_push", {"target": target})
        typer.echo(f"focus pushed: {target}")
        return

    if target is None:
        if state.focus is None:
            typer.echo("focus: (none)")
        else:
            kind = state.focus_kind or "freeform"
            rid = state.focus_resolved_id
            suffix = f"; id={rid}" if rid else ""
            typer.echo(f"focus: {state.focus}  [{kind}{suffix}]")
        return

    binding = resolve_focus_target(target, graph)
    state.focus = binding.raw
    state.focus_kind = binding.kind
    state.focus_resolved_id = binding.resolved_id
    save_state(path, state)
    append_tactic_event(path, "focus_set", {"target": target, "kind": binding.kind})
    typer.echo(f"focus set: {binding.raw}  [{binding.kind}]")


# ---------------------------------------------------------------------------
# obligation
# ---------------------------------------------------------------------------


@obligation_app.command("add")
def obligation_add(
    target_qid: str = typer.Argument(..., help="QID the obligation is about."),
    content: str = typer.Option(..., "-c", "--content", help="What must be shown."),
    kind: str = typer.Option("other", "--kind", help="Diagnostic kind."),
    path: str = typer.Option(".", "--path", help="Package path."),
) -> None:
    """Add a synthetic obligation for an inquiry target.

    Records a "what must be shown" note against a target QID — a
    ProofState-style obligation visible in the inquiry review report.
    Pure state.json mutation; no IR / priors / beliefs change.

    ``--kind`` selects the diagnostic kind; allowed values are
    ``focus_weakness`` / ``other`` (default) / ``prior_hole`` /
    ``structural_hole`` / ``support_weak`` (see ``VALID_OBLIGATION_KINDS``
    in :mod:`gaia.engine.inquiry.state`).

    Example:

    .. code-block:: bash

        gaia inquiry obligation add my_claim \\
            -c "Show the prior is justified by the cited evidence." \\
            --kind prior_hole
    """
    if kind not in VALID_OBLIGATION_KINDS:
        typer.echo(
            f"Error: invalid --kind {kind!r}; allowed: {sorted(VALID_OBLIGATION_KINDS)}",
            err=True,
        )
        raise typer.Exit(2)

    state = load_state(path)
    qid = mint_qid("oblig")
    state.synthetic_obligations.append(
        SyntheticObligation(qid=qid, target_qid=target_qid, content=content, diagnostic_kind=kind)
    )
    save_state(path, state)
    append_tactic_event(
        path,
        "obligation_add",
        {"qid": qid, "target_qid": target_qid, "kind": kind},
    )
    typer.echo(f"obligation added {qid}")


@obligation_app.command("list")
def obligation_list(
    json_out: bool = typer.Option(False, "--json"),
    path: str = typer.Option(".", "--path"),
) -> None:
    """List open synthetic obligations.

    Prints every open obligation (kind, qid, target_qid, content) in
    state.json. ``--json`` emits the same rows as a JSON array for
    machine consumption.

    Example:

    .. code-block:: bash

        gaia inquiry obligation list
        gaia inquiry obligation list --json
    """
    state = load_state(path)
    rows = [
        {
            "qid": o.qid,
            "target_qid": o.target_qid,
            "content": o.content,
            "diagnostic_kind": o.diagnostic_kind,
            "created_at": o.created_at,
        }
        for o in state.synthetic_obligations
    ]
    if json_out:
        typer.echo(json.dumps(rows, ensure_ascii=False, indent=2))
        return
    if not rows:
        typer.echo("(no open obligations)")
        return
    for r in rows:
        typer.echo(f"- [{r['diagnostic_kind']}] {r['qid']} → {r['target_qid']}: {r['content']}")


@obligation_app.command("close")
def obligation_close(
    qid: str = typer.Argument(...),
    path: str = typer.Option(".", "--path"),
) -> None:
    """Close a synthetic obligation by QID.

    Removes the obligation with the given QID from state.json; logs a
    ``obligation_close`` tactic event. Exits non-zero when no obligation
    matches the QID. QIDs are printed by ``gaia inquiry obligation
    list``.

    Example:

    .. code-block:: bash

        gaia inquiry obligation close oblig_a1b2c3d4
    """
    state = load_state(path)
    before = len(state.synthetic_obligations)
    state.synthetic_obligations = [o for o in state.synthetic_obligations if o.qid != qid]
    if len(state.synthetic_obligations) == before:
        typer.echo(f"Error: no obligation with qid {qid!r}.", err=True)
        raise typer.Exit(1)
    save_state(path, state)
    append_tactic_event(path, "obligation_close", {"qid": qid})
    typer.echo(f"obligation closed {qid}")


# ---------------------------------------------------------------------------
# hypothesis
# ---------------------------------------------------------------------------


@hypothesis_app.command("add")
def hypothesis_add(
    content: str = typer.Argument(..., help="Hypothesis content."),
    scope: str | None = typer.Option(None, "--scope", help="Scope QID."),
    path: str = typer.Option(".", "--path"),
) -> None:
    """Add a working hypothesis to inquiry state.

    Records a tentative hypothesis the agent wants to track during
    inquiry without committing it to the DSL / IR. Pure state.json
    mutation. ``--scope`` optionally pins the hypothesis to a specific
    target QID so the inquiry review report can group it with related
    claims.

    Example:

    .. code-block:: bash

        gaia inquiry hypothesis add "The prior is robust to ±10% perturbation."
        gaia inquiry hypothesis add "Bayes factor > 10 under diffuse alt." \\
            --scope my_claim_id
    """
    state = load_state(path)
    qid = mint_qid("hyp")
    state.synthetic_hypotheses.append(
        SyntheticHypothesis(qid=qid, content=content, scope_qid=scope)
    )
    save_state(path, state)
    append_tactic_event(path, "hypothesis_add", {"qid": qid, "scope": scope})
    typer.echo(f"hypothesis added {qid}")


@hypothesis_app.command("list")
def hypothesis_list(
    json_out: bool = typer.Option(False, "--json"),
    path: str = typer.Option(".", "--path"),
) -> None:
    """List working hypotheses from inquiry state.

    Prints every recorded hypothesis (qid, scope_qid, content) from
    state.json. ``--json`` emits a JSON array for machine consumption.

    Example:

    .. code-block:: bash

        gaia inquiry hypothesis list
        gaia inquiry hypothesis list --json
    """
    state = load_state(path)
    rows = [
        {
            "qid": h.qid,
            "content": h.content,
            "scope_qid": h.scope_qid,
            "created_at": h.created_at,
        }
        for h in state.synthetic_hypotheses
    ]
    if json_out:
        typer.echo(json.dumps(rows, ensure_ascii=False, indent=2))
        return
    if not rows:
        typer.echo("(no hypotheses)")
        return
    for r in rows:
        scope = f" @ {r['scope_qid']}" if r["scope_qid"] else ""
        typer.echo(f"- {r['qid']}{scope}: {r['content']}")


@hypothesis_app.command("remove")
def hypothesis_remove(
    qid: str = typer.Argument(...),
    path: str = typer.Option(".", "--path"),
) -> None:
    """Remove a working hypothesis by QID.

    Drops the hypothesis with the given QID from state.json. QIDs are
    printed by ``gaia inquiry hypothesis list``.

    Example:

    .. code-block:: bash

        gaia inquiry hypothesis remove hyp_a1b2c3d4
    """
    state = load_state(path)
    before = len(state.synthetic_hypotheses)
    state.synthetic_hypotheses = [h for h in state.synthetic_hypotheses if h.qid != qid]
    if len(state.synthetic_hypotheses) == before:
        typer.echo(f"Error: no hypothesis with qid {qid!r}.", err=True)
        raise typer.Exit(1)
    save_state(path, state)
    append_tactic_event(path, "hypothesis_remove", {"qid": qid})
    typer.echo(f"hypothesis removed {qid}")


# ---------------------------------------------------------------------------
# reject
# ---------------------------------------------------------------------------


@inquiry_app.command("reject")
def reject_command(
    strategy: str = typer.Argument(..., help="Target strategy label/id."),
    content: str = typer.Option(..., "-c", "--content", help="Reason."),
    path: str = typer.Option(".", "--path"),
) -> None:
    """Record a synthetic rejection for a strategy.

    Annotates a strategy with a free-text rejection note (e.g. "the
    cited evidence does not actually support this", "argument is
    circular"). Pure state.json mutation; the strategy stays in the IR.
    Useful as a self-review affordance: a rejected strategy can later be
    revisited or removed from the DSL source.

    Example:

    .. code-block:: bash

        gaia inquiry reject my_strategy_label \\
            -c "Premise A is not yet established."
    """
    state = load_state(path)
    qid = mint_qid("rej")
    state.synthetic_rejections.append(
        SyntheticRejection(qid=qid, target_strategy=strategy, content=content)
    )
    save_state(path, state)
    append_tactic_event(path, "reject", {"qid": qid, "strategy": strategy})
    typer.echo(f"strategy rejected {qid} ({strategy})")


# ---------------------------------------------------------------------------
# tactics log
# ---------------------------------------------------------------------------


@tactics_app.command("log")
def tactics_log(
    json_out: bool = typer.Option(False, "--json"),
    path: str = typer.Option(".", "--path"),
) -> None:
    """Print the inquiry tactic event log.

    Renders the append-only audit log of every inquiry state mutation
    (focus / obligation / hypothesis / reject / review events) in
    chronological order. ``--json`` emits one JSON record per entry for
    machine consumption.

    Example:

    .. code-block:: bash

        gaia inquiry tactics log
        gaia inquiry tactics log --json
    """
    from gaia.engine.inquiry.state import read_tactic_log

    rows = read_tactic_log(path)
    if json_out:
        typer.echo(json.dumps(rows, ensure_ascii=False, indent=2))
        return
    if not rows:
        typer.echo("(no tactic log entries)")
        return
    for rec in rows:
        ts = rec.get("timestamp", "")
        ev = rec.get("event", "")
        payload = rec.get("payload", {})
        typer.echo(f"{ts}  {ev}  {json.dumps(payload, ensure_ascii=False)}")


# ---------------------------------------------------------------------------
# review
# ---------------------------------------------------------------------------


@inquiry_app.command("review")
def review_command(
    path: str = typer.Argument(".", help="Package path."),
    focus_: str | None = typer.Option(None, "--focus"),
    mode: str = typer.Option("auto", "--mode"),
    no_infer: bool = typer.Option(False, "--no-infer"),
    depth: int = typer.Option(0, "--depth"),
    since: str | None = typer.Option(None, "--since"),
    json_out: bool = typer.Option(False, "--json"),
    markdown_out: bool = typer.Option(False, "--markdown"),
    strict: bool = typer.Option(False, "--strict"),
) -> None:
    """Run the local semantic inquiry review.

    Executes the semantic inquiry loop on the package: graph-health
    diagnostics, focus-relevance analysis, optional inference, and
    publish-readiness blockers. Writes a timestamped review artifact
    under ``.gaia/inquiry/reviews/``.

    ``--mode`` selects the review profile:

    * ``auto`` (default) — pick a profile based on the package state
    * ``formalize`` — emphasise scaffolded / unformalised claims
    * ``explore`` — bias towards weak / orphaned claims
    * ``verify`` — emphasise prior coherence + Bayes diagnostics
    * ``publish`` — full publish-readiness gates (combine with ``--strict``)

    ``--no-infer`` skips the BP inference step (faster but misses
    belief-derived diagnostics); ``--depth N`` controls dependency
    inference depth as in ``gaia run infer``.

    Example:

    .. code-block:: bash

        gaia inquiry review .
        gaia inquiry review . --mode publish --strict
        gaia inquiry review . --no-infer --json
        gaia inquiry review . --focus my_claim_label --markdown > review.md
    """
    if mode not in {"auto", "formalize", "explore", "verify", "publish"}:
        typer.echo(f"Error: invalid --mode {mode!r}.", err=True)
        raise typer.Exit(2)
    if json_out and markdown_out:
        typer.echo("Error: --json and --markdown are mutually exclusive.", err=True)
        raise typer.Exit(2)

    report = run_review(
        path,
        focus_override=focus_,
        mode=mode,
        no_infer=no_infer,
        depth=depth,
        since=since,
        strict=strict,
    )
    append_tactic_event(
        Path(path),
        "review",
        {"review_id": report.review_id, "mode": mode, "no_infer": no_infer},
    )

    if json_out:
        typer.echo(json.dumps(report.to_json_dict(), ensure_ascii=False, indent=2))
    elif markdown_out:
        typer.echo(render_markdown(report))
    else:
        typer.echo(render_text(report))

    if report.graph_health.get("errors"):
        raise typer.Exit(1)
    if strict and mode == "publish":
        blockers = publish_blockers(report)
        if blockers:
            for b in blockers:
                typer.echo(f"[publish-strict] {b}", err=True)
            raise typer.Exit(1)
    elif strict and report.graph_health.get("warnings"):
        raise typer.Exit(1)
