"""gaia starmap-replay v4 — IR-tick replay with pinned graphviz layout.

Reads the two JSONL logs an ``lkm-to-gaia`` run leaves under a package's
``artifacts/lkm-discovery/`` directory and renders a single self-contained
HTML file that plays back the IR-side construction of the package.

v4 contract (vs v3):

* **Tick axis is per-``gaia_action``, not per-event.** Each entry of
  ``event.gaia_actions`` whose ``action`` lands an IR change
  (``claim``/``support``/``deduction``/``contradiction``/``equivalence``/
  ``prior``) is one IR-tick. Events with no IR-relevant actions still
  appear on the timeline as informational markers (``round_open``,
  ``stage_transition``, retrievals, etc.) but contribute zero ticks.

* **Pinned canonical layout.** The frontend gets a ``final_layout`` table
  baked from ``dot -Tjson0`` against the same DOT source ``gaia starmap
  --format dot`` produces. Nodes are placed at their pinned coordinates
  on first appearance; cluster boxes match ``_dot.py`` styling. This
  command degrades gracefully when graphviz is missing or the package
  has no compiled IR — replay still renders, with no pinned layout
  (frontend falls back to a centred no-op).

* **Per-round belief snapshots.** For each ``round_id`` seen in the
  growth-log stream, a truncated IR (only knowledges introduced by
  end-of-round R) is run through ``InferenceEngine`` and the resulting
  beliefs are baked as ``round_beliefs``. The frontend animates each
  claim node's belief number across round boundaries.

The frontend half lives in ``viz/src/starmap-replay.ts`` (entry) and
``viz/src/replay/*.ts``. The build pipeline (``cd viz && npm run
build:replay``) inlines bundle + CSS into a single template HTML which
is shipped at ``gaia/cli/starmap_replay_assets/template.html``; this
command injects the timeline JSON into that template at the
``<!--__TIMELINE_DATA__-->`` placeholder and writes the result.
"""

from __future__ import annotations

from typing import Any


import json
from pathlib import Path

import typer

from gaia.cli._packages import (
    GaiaCliError,
    apply_package_priors,
    compile_loaded_package_artifact,
    ensure_package_env,
    load_gaia_package,
)
from gaia.cli.commands._dot import to_dot
from gaia.cli.commands._graph_json import generate_graph_json
from gaia.cli.commands._render_priors import param_data_from_ir_metadata
from gaia.cli.commands._replay_build import (
    annotate_layout_with_kinds,
    annotate_ticks_with_survival,
    bridge_event_symbols_to_layout,
    collect_round_order,
    compute_dot_layout,
    compute_round_beliefs,
    rekey_layout_to_lkm_ids,
    split_into_ir_ticks,
    topo_reorder_ticks,
)

TIMELINE_PLACEHOLDER = "<!--__TIMELINE_DATA__-->"
DEFAULT_OUT_RELATIVE = ".gaia/starmap-replay.html"
ARTIFACTS_SUBDIR = "artifacts/lkm-discovery"
RETRIEVAL_LOG_NAME = "retrieval_log.jsonl"
GROWTH_LOG_NAME = "graph_growth_log.jsonl"
SCHEMA_VERSION = "1"


def _load_template() -> str:
    """Read the shipped placeholder HTML template."""
    import gaia.cli.starmap_replay_assets as assets_pkg

    template_path = Path(assets_pkg.__file__).parent / "template.html"
    return template_path.read_text(encoding="utf-8")


def _render_html(template: str, timeline_json: str) -> str:
    """Inject the timeline JSON payload into *template* at the placeholder."""
    if TIMELINE_PLACEHOLDER not in template:
        raise RuntimeError(
            f"Error: starmap-replay template is missing the {TIMELINE_PLACEHOLDER!r} placeholder."
        )
    injection = f"<script>window.TIMELINE_DATA = {timeline_json};</script>"
    return template.replace(TIMELINE_PLACEHOLDER, injection, 1)


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    """Read newline-delimited JSON. Skip blank lines, raise on parse errors."""
    events: list[dict[str, Any]] = []
    for lineno, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw.strip()
        if not line:
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise typer.BadParameter(f"{path}: line {lineno} is not valid JSON: {exc}") from exc
    return events


def _is_replayable(event: dict[str, Any]) -> bool:
    """Drop retry / failure events — replay ignores transient retries."""
    if event.get("retry_of_event_id"):
        return False
    if event.get("decision") == "retry":
        return False
    # response_code != 0 implies a failed retrieval — also skip.
    if "response_code" in event and event.get("response_code") not in (None, 0):
        return False
    return True


def _validate_schema(events: list[dict[str, Any]], source: str) -> list[str]:
    """Return a list of warning strings for events with non-"1" schema_version."""
    warnings: list[str] = []
    for event in events:
        if event.get("schema_version") != SCHEMA_VERSION:
            warnings.append(
                f"{source}: event {event.get('event_id', '<no id>')} "
                f"has schema_version={event.get('schema_version')!r} "
                f"(expected {SCHEMA_VERSION!r})"
            )
    return warnings


def merge_events(
    retrieval_events: list[dict[str, Any]], growth_events: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Merge two streams into one timeline.

    Sort key is ``(timestamp_utc, actor_id, seq)``. ISO-8601 timestamps with a
    fixed millisecond format and trailing ``Z`` sort lexicographically. The
    sort is stable — events with identical keys retain their input order, so
    we tag each with ``event_kind`` (``retrieval`` / ``growth``) before
    merging to disambiguate downstream.
    """
    tagged: list[dict[str, Any]] = []
    for event in retrieval_events:
        # Note: we mutate via a shallow copy so the caller's list stays intact.
        e = dict(event)
        e.setdefault("event_kind", "retrieval")
        tagged.append(e)
    for event in growth_events:
        e = dict(event)
        e.setdefault("event_kind", "growth")
        tagged.append(e)

    tagged.sort(
        key=lambda e: (
            e.get("timestamp_utc", ""),
            e.get("actor_id", ""),
            e.get("seq", 0),
        )
    )
    return tagged


def _try_load_ir_artifacts(
    pkg_dir: Path,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None, list[str]]:
    """Best-effort load of compiled IR + DOT layout for a package.

    Returns ``(ir, layout, warnings)``. Either of ``ir``/``layout`` may
    be ``None`` when:

    * the package has no ``.gaia/ir.json`` (e.g. the unit-test fixture),
    * graphviz ``dot`` isn't on ``PATH``,
    * compilation fails for any reason.

    Replay still renders in those cases — without round beliefs / pinned
    layout, but with the timeline + tick + structured-detail features
    intact.
    """
    warnings: list[str] = []

    # Try compiling the package fresh — that gives us the canonical IR
    # used by `gaia starmap` / `gaia infer`. If compilation fails (no
    # pyproject.toml, missing src/, etc.), fall back to the on-disk
    # ``.gaia/ir.json`` if present.
    ir: dict[str, Any] | None = None
    try:
        ensure_package_env(pkg_dir)
        loaded = load_gaia_package(str(pkg_dir))
        apply_package_priors(loaded)
        compiled = compile_loaded_package_artifact(loaded)
        ir = compiled.to_json()
    except (GaiaCliError, Exception) as exc:  # noqa: BLE001 - we degrade
        warnings.append(f"compilation skipped: {exc}")
        ir_json_path = pkg_dir / ".gaia" / "ir.json"
        if ir_json_path.is_file():
            try:
                ir = json.loads(ir_json_path.read_text(encoding="utf-8"))
                warnings.append(f"using stored IR at {ir_json_path}")
            except json.JSONDecodeError as parse_err:
                warnings.append(f"stored IR is invalid JSON: {parse_err}")
                ir = None
        else:
            ir = None

    # Pinned layout requires a working IR + graphviz. Skip silently on
    # failure (warnings surface to the CLI caller).
    layout: dict[str, Any] | None = None
    if ir is not None:
        try:
            param_data = param_data_from_ir_metadata(ir)
            exported_ids = {k["id"] for k in ir.get("knowledges", []) if k.get("exported")}
            graph_json = generate_graph_json(
                ir,
                beliefs_data=None,
                param_data=param_data,
                exported_ids=exported_ids,
            )
            dot_source = to_dot(graph_json)
            layout = compute_dot_layout(dot_source)
            # Re-key knowledge layout entries to raw lkm_ids so the
            # frontend (which admits nodes by event-side id) can find
            # their pinned coordinates. See rekey_layout_to_lkm_ids docs.
            layout, rekey_warns = rekey_layout_to_lkm_ids(layout, ir)
            warnings.extend(rekey_warns)
            # Decorate every layout entry with kind + styling info pulled
            # from the IR so the replay frontend can render strategies as
            # ellipses and operators as hexagons (red for contradictions)
            # at their pinned positions on first admission. Without this
            # the canvas can't tell strat_<i> from oper_<i> from a normal
            # claim and silently degrades to claim-only rendering.
            annotate_layout_with_kinds(layout, ir)
        except FileNotFoundError as exc:
            warnings.append(f"pinned layout skipped: {exc}")
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"pinned layout failed: {exc}")

    return ir, layout, warnings


def build_timeline_payload(
    retrieval_events: list[dict[str, Any]],
    growth_events: list[dict[str, Any]],
    *,
    package_name: str | None = None,
    pkg_dir: Path | None = None,
) -> dict[str, Any]:
    """Construct the JSON payload the frontend reads from ``window.TIMELINE_DATA``.

    Pulled out as a function so unit tests can call it on synthetic
    inputs without touching the filesystem.
    """
    replayable_retrievals = [e for e in retrieval_events if _is_replayable(e)]
    replayable_growths = [e for e in growth_events if _is_replayable(e)]
    merged = merge_events(replayable_retrievals, replayable_growths)
    ticks = split_into_ir_ticks(merged)

    final_layout: dict[str, Any] | None = None
    round_beliefs: dict[str, dict[str, float]] = {}
    rounds_in_order: list[str] = collect_round_order(merged)
    build_warnings: list[str] = []

    ir_for_survival: dict[str, Any] | None = None
    layout_for_survival: dict[str, Any] | None = None
    if pkg_dir is not None:
        ir, layout, warns = _try_load_ir_artifacts(pkg_dir)
        build_warnings.extend(warns)
        if layout is not None and ir is not None:
            # Bridge event-side strategy / operator symbols (gfac_*,
            # human-readable contradiction ids) to their strat_<i> /
            # oper_<i> pinned positions so they don't pile up at the
            # canvas centre.
            layout, bridge_warns = bridge_event_symbols_to_layout(layout, ir, merged)
            build_warnings.extend(bridge_warns)
        if layout is not None:
            final_layout = layout
            layout_for_survival = layout
        if ir is not None:
            round_beliefs = compute_round_beliefs(ir, merged)
            ir_for_survival = ir

    # Mark each IR-tick with whether its action survives into the final
    # compiled IR. Orphan ticks (action symbols that the agent admitted
    # mid-run but later merged/repaired away) get `survives_to_final=False`
    # so the frontend skips them on the canvas — keeping the hard
    # invariant that the replay's final state equals the static SVG.
    ticks, survival_warnings = annotate_ticks_with_survival(
        ticks, merged, layout_for_survival, ir_for_survival
    )
    build_warnings.extend(survival_warnings)

    # Topologically reorder surviving ticks so a strategy / operator
    # tick fires only after all its referenced claims are admitted. This
    # turns the IR-tick axis from a chronological-event axis into a
    # logical-dependency axis: the lkm-to-gaia agent occasionally admits
    # a contradiction operator before all of its variable claims are on
    # canvas (later revising which claims it references). Replayed in
    # chronological order, that produces transient frames where a
    # hexagon's edges fan into not-yet-drawn nodes. The reorder uses
    # original tick_index as a tiebreaker so chronology is preserved
    # whenever no dependency forces a swap.
    ticks, topo_warnings = topo_reorder_ticks(ticks, merged, layout_for_survival, ir_for_survival)
    build_warnings.extend(topo_warnings)

    return {
        "schema_version": SCHEMA_VERSION,
        "package_name": package_name,
        "retrieval_count": len(replayable_retrievals),
        "growth_count": len(replayable_growths),
        "events": merged,
        "ticks": ticks,
        "rounds": rounds_in_order,
        "round_beliefs": round_beliefs,
        "final_layout": final_layout,
        "build_warnings": build_warnings,
    }


def starmap_replay_command(
    path: str = typer.Argument(".", help="Path to knowledge package directory"),
    out: str = typer.Option(
        None,
        "--out",
        help=(
            "Output file. Defaults to '.gaia/starmap-replay.html' relative to "
            "the package directory; absolute paths are honored as-is."
        ),
    ),
) -> None:
    """Emit an HTML replay of a package's lkm-discovery run.

    Reads ``<package>/artifacts/lkm-discovery/retrieval_log.jsonl`` and
    ``<package>/artifacts/lkm-discovery/graph_growth_log.jsonl`` (the two
    JSONL logs an ``lkm-to-gaia`` orchestrator + worker pair leave behind),
    merges them on ``(timestamp_utc, actor_id, seq)``, drops retry /
    failure events, splits each event into per-``gaia_action`` IR-ticks,
    and writes a single self-contained HTML page that plays back the run
    on a pinned canonical layout. Round-by-round beliefs are computed by
    re-running BP on the compiled IR truncated to each round's
    cumulative knowledge set.

    Examples:

      # Default — write .gaia/starmap-replay.html into the package:
      gaia starmap-replay path/to/pkg

      # Custom output path:
      gaia starmap-replay path/to/pkg --out figures/replay.html
    """
    pkg_dir = Path(path).resolve()
    if not pkg_dir.is_dir():
        typer.echo(f"Error: {pkg_dir} is not a directory.", err=True)
        raise typer.Exit(1)

    artifacts_dir = pkg_dir / ARTIFACTS_SUBDIR
    retrieval_log = artifacts_dir / RETRIEVAL_LOG_NAME
    growth_log = artifacts_dir / GROWTH_LOG_NAME

    missing = [p for p in (retrieval_log, growth_log) if not p.is_file()]
    if missing:
        for p in missing:
            typer.echo(f"Error: missing timeline log: {p}", err=True)
        typer.echo(
            "Run the lkm-to-gaia discovery pipeline first; both logs must "
            f"exist under {artifacts_dir}.",
            err=True,
        )
        raise typer.Exit(1)

    retrieval_events = _read_jsonl(retrieval_log)
    growth_events = _read_jsonl(growth_log)

    for warning in _validate_schema(retrieval_events, str(retrieval_log)):
        typer.echo(f"Warning: {warning}")
    for warning in _validate_schema(growth_events, str(growth_log)):
        typer.echo(f"Warning: {warning}")

    payload = build_timeline_payload(
        retrieval_events,
        growth_events,
        package_name=pkg_dir.name,
        pkg_dir=pkg_dir,
    )
    for warning in payload.get("build_warnings", []):
        typer.echo(f"Note: {warning}")

    timeline_json = json.dumps(payload, ensure_ascii=False)

    try:
        template = _load_template()
        content = _render_html(template, timeline_json)
    except RuntimeError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1)
    except FileNotFoundError as exc:
        typer.echo(
            "Error: starmap-replay template asset not found. The viz/ bundle "
            f"may not have been shipped: {exc}",
            err=True,
        )
        raise typer.Exit(1)

    out_path = Path(out) if out is not None else Path(DEFAULT_OUT_RELATIVE)
    if not out_path.is_absolute():
        out_path = pkg_dir / out_path
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(content, encoding="utf-8")

    tick_count = len(payload["ticks"])
    rounds_count = len(payload["rounds"])
    typer.echo(
        f"Wrote starmap replay to {out_path} "
        f"({payload['retrieval_count']} retrievals, "
        f"{payload['growth_count']} growth events, "
        f"{len(payload['events'])} total, "
        f"{tick_count} IR-ticks, "
        f"{rounds_count} rounds)"
    )
