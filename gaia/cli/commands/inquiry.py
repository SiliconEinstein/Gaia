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
from typing import Optional

import typer

from gaia.inquiry.review import (
    publish_blockers,
    render_markdown,
    render_text,
    resolve_graph,
    run_review,
)
from gaia.inquiry.focus import resolve_focus_target
from gaia.inquiry.state import (
    VALID_OBLIGATION_KINDS,
    SyntheticHypothesis,
    SyntheticObligation,
    SyntheticRejection,
    append_tactic_event,
    load_state,
    mint_qid,
    pop_focus_frame,
    push_focus_frame,
    read_tactic_log,
    save_state,
)

OUTPUT_FORMATS = {"text", "json", "markdown"}
LIST_FORMATS = {"text", "json"}
OBLIGATION_TYPE_ALIASES = {
    "prior": "prior_hole",
    "structure": "structural_hole",
    "structural": "structural_hole",
    "support": "support_weak",
    "focus": "focus_weakness",
    "other": "other",
}

inquiry_app = typer.Typer(
    name="inquiry",
    help="Gaia Inquiry — semantic review loop.",
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
inquiry_app.add_typer(obligation_app, name="todo")
inquiry_app.add_typer(hypothesis_app, name="hypothesis")
inquiry_app.add_typer(tactics_app, name="tactics")


def _resolve_output_format(
    output_format: str,
    *,
    json_out: bool = False,
    markdown_out: bool = False,
) -> str:
    if output_format not in OUTPUT_FORMATS:
        typer.echo(f"Error: invalid --format {output_format!r}.", err=True)
        raise typer.Exit(2)
    if json_out and markdown_out:
        typer.echo("Error: --json and --markdown are mutually exclusive.", err=True)
        raise typer.Exit(2)
    if output_format != "text" and (json_out or markdown_out):
        typer.echo("Error: --format cannot be combined with --json/--markdown.", err=True)
        raise typer.Exit(2)
    if json_out:
        return "json"
    if markdown_out:
        return "markdown"
    return output_format


def _resolve_list_format(output_format: str, *, json_out: bool = False) -> str:
    if output_format not in LIST_FORMATS:
        typer.echo(f"Error: invalid --format {output_format!r}.", err=True)
        raise typer.Exit(2)
    if output_format != "text" and json_out:
        typer.echo("Error: --format cannot be combined with --json.", err=True)
        raise typer.Exit(2)
    return "json" if json_out else output_format


def _normalize_obligation_kind(kind: str, type_: str | None) -> str:
    if type_ is not None:
        if kind != "other":
            typer.echo("Error: --type cannot be combined with --kind.", err=True)
            raise typer.Exit(2)
        kind = type_
    normalized = OBLIGATION_TYPE_ALIASES.get(kind, kind)
    if normalized not in VALID_OBLIGATION_KINDS:
        allowed = sorted(set(VALID_OBLIGATION_KINDS) | set(OBLIGATION_TYPE_ALIASES))
        typer.echo(f"Error: invalid obligation type {kind!r}; allowed: {allowed}", err=True)
        raise typer.Exit(2)
    return normalized


def _resolve_target_id(target: str, path: str) -> str:
    graph = resolve_graph(path)
    binding = resolve_focus_target(target, graph)
    return binding.resolved_id or target


def _print_tactic_log(path: str, output_format: str, *, json_out: bool = False) -> None:
    fmt = _resolve_list_format(output_format, json_out=json_out)
    rows = read_tactic_log(path)
    if fmt == "json":
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
# focus
# ---------------------------------------------------------------------------


@inquiry_app.command("focus")
def focus_command(
    target: Optional[str] = typer.Argument(None, help="Focus target."),
    clear: bool = typer.Option(False, "--clear", help="Clear current focus."),
    push: bool = typer.Option(False, "--push", help="Push current focus and set new."),
    pop: bool = typer.Option(False, "--pop", help="Pop saved focus off the stack."),
    show_stack: bool = typer.Option(False, "--stack", help="Print focus stack."),
    path: str = typer.Option(".", "--path", help="Package path."),
) -> None:
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
    target_qid: str = typer.Argument(..., help="Target label/id/QID the obligation is about."),
    content: str = typer.Option(..., "-c", "--content", help="What must be shown."),
    kind: str = typer.Option("other", "--kind", help="Diagnostic kind."),
    type_: Optional[str] = typer.Option(None, "--type", help="Friendly obligation type."),
    path: str = typer.Option(".", "--path", help="Package path."),
) -> None:
    normalized_kind = _normalize_obligation_kind(kind, type_)
    resolved_target = _resolve_target_id(target_qid, path)

    state = load_state(path)
    qid = mint_qid("oblig")
    state.synthetic_obligations.append(
        SyntheticObligation(
            qid=qid,
            target_qid=resolved_target,
            content=content,
            diagnostic_kind=normalized_kind,
        )
    )
    save_state(path, state)
    append_tactic_event(
        path,
        "obligation_add",
        {"qid": qid, "target_qid": resolved_target, "kind": normalized_kind},
    )
    typer.echo(f"obligation added {qid}")


@obligation_app.command("list")
def obligation_list(
    json_out: bool = typer.Option(False, "--json"),
    output_format: str = typer.Option("text", "--format", help="Output format: text or json."),
    path: str = typer.Option(".", "--path"),
) -> None:
    fmt = _resolve_list_format(output_format, json_out=json_out)
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
    if fmt == "json":
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
    scope: Optional[str] = typer.Option(None, "--scope", help="Scope QID."),
    path: str = typer.Option(".", "--path"),
) -> None:
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
    output_format: str = typer.Option("text", "--format", help="Output format: text or json."),
    path: str = typer.Option(".", "--path"),
) -> None:
    _print_tactic_log(path, output_format, json_out=json_out)


@inquiry_app.command("log")
def log_command(
    json_out: bool = typer.Option(False, "--json"),
    output_format: str = typer.Option("text", "--format", help="Output format: text or json."),
    path: str = typer.Option(".", "--path"),
) -> None:
    _print_tactic_log(path, output_format, json_out=json_out)


# ---------------------------------------------------------------------------
# review
# ---------------------------------------------------------------------------


@inquiry_app.command("review")
def review_command(
    path: str = typer.Argument(".", help="Package path."),
    focus_: Optional[str] = typer.Option(None, "--focus"),
    mode: str = typer.Option("auto", "--mode"),
    no_infer: bool = typer.Option(False, "--no-infer"),
    depth: int = typer.Option(0, "--depth"),
    since: Optional[str] = typer.Option(None, "--since"),
    output_format: str = typer.Option(
        "text", "--format", help="Output format: text, json, or markdown."
    ),
    json_out: bool = typer.Option(False, "--json"),
    markdown_out: bool = typer.Option(False, "--markdown"),
    strict: bool = typer.Option(False, "--strict"),
) -> None:
    if mode not in {"auto", "formalize", "explore", "verify", "publish"}:
        typer.echo(f"Error: invalid --mode {mode!r}.", err=True)
        raise typer.Exit(2)
    fmt = _resolve_output_format(output_format, json_out=json_out, markdown_out=markdown_out)
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

    if fmt == "json":
        typer.echo(json.dumps(report.to_json_dict(), ensure_ascii=False, indent=2))
    elif fmt == "markdown":
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


@inquiry_app.command("gate")
def gate_command(
    path: str = typer.Argument(".", help="Package path."),
    profile: str = typer.Option("publish", "--profile", help="Gate profile."),
    focus_: Optional[str] = typer.Option(None, "--focus"),
    no_infer: bool = typer.Option(False, "--no-infer"),
    depth: int = typer.Option(0, "--depth"),
    since: Optional[str] = typer.Option(None, "--since"),
    output_format: str = typer.Option("text", "--format", help="Output format: text or json."),
    json_out: bool = typer.Option(False, "--json"),
) -> None:
    fmt = _resolve_list_format(output_format, json_out=json_out)
    if profile != "publish":
        typer.echo("Error: only --profile publish is currently supported.", err=True)
        raise typer.Exit(2)

    report = run_review(
        path,
        focus_override=focus_,
        mode="publish",
        no_infer=no_infer,
        depth=depth,
        since=since,
        strict=True,
    )
    blockers = publish_blockers(report)
    append_tactic_event(
        Path(path),
        "gate",
        {"review_id": report.review_id, "profile": profile, "passed": not blockers},
    )

    if fmt == "json":
        typer.echo(
            json.dumps(
                {
                    "profile": profile,
                    "passed": not blockers,
                    "blockers": blockers,
                    "review_id": report.review_id,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    elif blockers:
        for blocker in blockers:
            typer.echo(f"[publish-gate] {blocker}")
    else:
        typer.echo("publish gate passed")

    if report.graph_health.get("errors") or blockers:
        raise typer.Exit(1)
