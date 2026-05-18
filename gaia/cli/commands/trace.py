"""Public `gaia trace` CLI sub-app.

Commands per ARM Trace v1：
  verify  — 仅 schema + hash chain 校验，秒级 fail-fast
  review  — 完整八段 review，stdout/json/markdown
  show    — 列事件流（tactic_log 风格）

Exit codes：
  0  clean / no errors
  1  tampered / errors found
  2  schema-broken / bad CLI args
"""

from __future__ import annotations

import typer

from gaia.engine.trace.hashing import compute_events_root, compute_manifest_hash, recompute_chain
from gaia.engine.trace.loader import load_trace
from gaia.engine.trace.render import render_json, render_markdown, render_text
from gaia.engine.trace.review import run_trace_review
from gaia.engine.trace.schema import Trace

trace_app = typer.Typer(
    name="trace",
    help=(
        "Gaia ARM Trace — verify and review execution traces "
        "(verify / review / show)."
    ),
    no_args_is_help=True,
)


# ---------------------------------------------------------------------------
# verify
# ---------------------------------------------------------------------------


@trace_app.command("verify")
def verify_command(
    trace_path: str = typer.Argument(..., help="Path to trace file (.json/.jsonl)."),
    quiet: bool = typer.Option(False, "--quiet", help="Suppress non-error output."),
) -> None:
    """Verify trace schema and hash chain.

    Fast schema + hash-chain check (seconds, fail-fast). Loads the trace,
    validates each event's prev_hash forms an unbroken chain from
    GENESIS, then checks the manifest's ``events_root`` and
    ``manifest_hash`` against recomputed values.

    Exit codes:
      * 0 — clean
      * 1 — hash chain / manifest mismatch (tampering)
      * 2 — schema error / unreadable file

    Example:

    .. code-block:: bash

        gaia trace verify path/to/trace.json
        gaia trace verify path/to/trace.jsonl --quiet
    """
    res = load_trace(trace_path)
    if res.issues:
        if not quiet:
            typer.echo(f"[schema] {len(res.issues)} issue(s):", err=True)
            for s in res.issues:
                typer.echo(f"  - {s.location}: {s.message}", err=True)
        raise typer.Exit(2)

    trace = res.trace
    assert trace is not None  # 没有 issues 就一定有 trace

    errors = _trace_verify_errors(trace, recompute_chain(trace.events))
    if errors:
        _raise_trace_verify_failure(errors, quiet=quiet)
    _emit_trace_verify_ok(trace, quiet=quiet)


# ---------------------------------------------------------------------------
# review
# ---------------------------------------------------------------------------


_SUPPORTED_REVIEW_MODES = {"trace", "publish"}


def _trace_chain_mismatches(trace: Trace, chain: list[str]) -> list[str]:
    """Return the first event prev-hash mismatch after genesis."""
    for i in range(1, len(trace.events)):
        if trace.events[i].prev_hash != chain[i - 1]:
            return [f"events[{i}] (seq={trace.events[i].seq}) prev_hash mismatch"]
    return []


def _trace_verify_errors(trace: Trace, chain: list[str]) -> list[str]:
    """Return hash-chain and manifest mismatches for a loaded trace."""
    expected_root = compute_events_root(trace.events)
    expected_manifest_hash = compute_manifest_hash(trace.manifest)
    errors: list[str] = []

    if trace.events:
        from gaia.engine.trace.hashing import GENESIS_PREV_HASH

        if trace.events[0].prev_hash != GENESIS_PREV_HASH:
            errors.append(f"events[0].prev_hash != GENESIS ({trace.events[0].prev_hash!r})")
        errors.extend(_trace_chain_mismatches(trace, chain))
    if trace.manifest.events_root != expected_root:
        errors.append("manifest.events_root mismatch")
    if trace.manifest.manifest_hash and trace.manifest.manifest_hash != expected_manifest_hash:
        errors.append("manifest.manifest_hash mismatch")
    return errors


def _emit_trace_verify_ok(trace: Trace, *, quiet: bool) -> None:
    """Print successful trace verification details."""
    if quiet:
        return
    typer.echo("[verify] OK")
    typer.echo(f"  events             : {len(trace.events)}")
    typer.echo(f"  events_root        : {compute_events_root(trace.events)}")
    typer.echo(f"  manifest_hash      : {trace.manifest.manifest_hash or '(none)'}")


def _raise_trace_verify_failure(errors: list[str], *, quiet: bool) -> None:
    """Print trace verification errors and exit with status 1."""
    if not quiet:
        typer.echo("[verify] FAIL", err=True)
        for error in errors:
            typer.echo(f"  - {error}", err=True)
    raise typer.Exit(1)


@trace_app.command("review")
def review_command(
    trace_path: str = typer.Argument(..., help="Path to trace file (.json/.jsonl)."),
    mode: str = typer.Option("trace", "--mode", help="Ranking mode: trace|publish."),
    package: str | None = typer.Option(
        None, "--package", help="Gaia package path used to resolve claim_ref review_ids."
    ),
    json_out: bool = typer.Option(False, "--json", help="Emit JSON report (deterministic)."),
    markdown_out: bool = typer.Option(False, "--markdown", help="Emit Markdown report."),
    snapshot_dir: str | None = typer.Option(
        None, "--snapshot-dir", help="Override snapshot output directory."
    ),
    strict: bool = typer.Option(
        False,
        "--strict",
        help="Exit non-zero whenever any error/warning diagnostic is present.",
    ),
) -> None:
    """Run the full ARM trace review (eight-section review).

    Performs the complete ARM trace review: schema + chain + decision
    soundness + tool-call validity + retry hygiene + claim_ref resolution
    + manifest coherence + ranking. ``--mode trace`` (default) emits the
    generic review; ``--mode publish`` adds publish-readiness gates.
    ``--package`` lets the reviewer resolve ``claim_ref`` review_ids against
    a Gaia package's review manifest.

    Exit codes:
      * 0 — clean (no error diagnostics; no warning blockers under --strict)
      * 1 — error-level diagnostic, or any warning under ``--strict``
      * 2 — invalid CLI argument combination

    Example:

    .. code-block:: bash

        gaia trace review path/to/trace.json
        gaia trace review path/to/trace.json --mode publish --strict
        gaia trace review path/to/trace.json --json > review.json
        gaia trace review path/to/trace.json --markdown > review.md
    """
    if mode not in _SUPPORTED_REVIEW_MODES:
        typer.echo(
            f"Error: invalid --mode {mode!r}; allowed: {sorted(_SUPPORTED_REVIEW_MODES)}",
            err=True,
        )
        raise typer.Exit(2)
    if json_out and markdown_out:
        typer.echo("Error: --json and --markdown are mutually exclusive.", err=True)
        raise typer.Exit(2)

    report = run_trace_review(
        trace_path,
        mode=mode,
        package_path=package,
        snapshot_dir=snapshot_dir,
    )

    if json_out:
        typer.echo(render_json(report))
    elif markdown_out:
        typer.echo(render_markdown(report))
    else:
        typer.echo(render_text(report))

    has_error = any(d.severity == "error" for d in report.diagnostics)
    has_warning = any(d.severity == "warning" for d in report.diagnostics)
    if has_error:
        raise typer.Exit(1)
    if strict and has_warning:
        raise typer.Exit(1)


# ---------------------------------------------------------------------------
# show
# ---------------------------------------------------------------------------


@trace_app.command("show")
def show_command(
    trace_path: str = typer.Argument(..., help="Path to trace file (.json/.jsonl)."),
    limit: int = typer.Option(50, "--limit", help="Max events to print (0 = all)."),
    kind: str | None = typer.Option(
        None, "--kind", help="Filter by event kind (decision/tool_call/...)."
    ),
    json_out: bool = typer.Option(False, "--json", help="Emit JSONL of selected events."),
) -> None:
    """Print the trace event stream (tactic_log style).

    Walks the events list in seq order and prints a compact one-line
    summary per event (kind, actor, ts, plus kind-specific detail). On
    schema violations the loadable events are still printed; schema
    issues go to stderr.

    ``--kind`` filters by event kind (``decision`` / ``tool_call`` /
    ``retry`` / etc.); ``--limit 0`` shows every event; ``--json``
    emits one JSON line per event for machine consumption.

    Example:

    .. code-block:: bash

        gaia trace show path/to/trace.json
        gaia trace show path/to/trace.json --kind tool_call --limit 0
        gaia trace show path/to/trace.json --json > events.jsonl
    """
    res = load_trace(trace_path)
    if res.issues and not res.trace:
        typer.echo("[show] schema errors prevent loading the trace:", err=True)
        for s in res.issues:
            typer.echo(f"  - {s.location}: {s.message}", err=True)
        raise typer.Exit(2)

    trace = res.trace
    assert trace is not None

    events = trace.events
    if kind:
        events = [e for e in events if e.kind == kind]
    if limit and limit > 0:
        events = events[:limit]

    if json_out:
        for e in events:
            typer.echo(e.model_dump_json())
        return

    # 简单 text 模式
    typer.echo(f"trace_id     : {trace.manifest.trace_id}")
    typer.echo(f"arm_id       : {trace.manifest.arm_id}")
    typer.echo(f"session_id   : {trace.manifest.session_id}")
    typer.echo(f"events shown : {len(events)} (of {len(trace.events)} total)")
    typer.echo("-" * 72)
    for e in events:
        marker = e.kind.ljust(18)
        actor = e.actor.ljust(8)
        suffix = ""
        if e.kind == "tool_call" and e.tool:
            suffix = f"  tool={e.tool}"
        elif e.kind == "decision" and e.reason:
            txt = (e.reason or "").splitlines()[0][:60]
            suffix = f"  reason={txt!r}"
        elif e.kind == "retry" and e.error:
            suffix = f"  err={e.error[:40]!r}"
        typer.echo(f"  seq={e.seq:<3} {marker} actor={actor} ts={e.ts.isoformat()}{suffix}")
