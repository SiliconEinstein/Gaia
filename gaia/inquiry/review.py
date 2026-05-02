"""gaia inquiry review — orchestrator.

This module is intentionally thin: it composes Gaia's existing compile,
validate, classify, hole-analysis, and inference layers into the eight-section
report defined by spec §8/§9. No detection logic lives here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from gaia.cli._packages import (
    GaiaCliError,
    apply_package_priors,
    collect_foreign_node_priors,
    compile_loaded_package_artifact,
    ensure_package_env,
    load_gaia_package,
)
from gaia.cli.commands.check_core import (
    KnowledgeBreakdown,
    analyze_knowledge_breakdown,
    find_possible_duplicate_claims,
)
from gaia.ir.validator import validate_local_graph

from gaia.inquiry.anchor import find_anchors
from gaia.inquiry.diagnostics import (
    Diagnostic,
    NextEdit,
    detect_blocked_warrant_path,
    detect_claim_with_evidence_but_no_focus_connection,
    detect_focus_low_posterior,
    detect_focus_unsupported,
    detect_large_belief_drop,
    detect_overstrong_strategy_without_provenance,
    detect_prior_without_justification,
    detect_stale_artifact,
    detect_warrant_status,
    format_diagnostics_as_structured_edits,
    from_knowledge_breakdown,
    from_validation,
)
from gaia.inquiry.diff import SemanticDiff, compute_semantic_diff, empty_diff
from gaia.inquiry.focus import FocusBinding, resolve_focus_target
from gaia.inquiry.proof_state import ProofContext, build_proof_context
from gaia.inquiry.ranking import rank_diagnostics, rank_next_edits
from gaia.inquiry.render import render_markdown as _render_markdown
from gaia.inquiry.render import render_text as _render_text
from gaia.inquiry.render import to_json_dict as _to_json_dict
from gaia.inquiry.snapshot import (
    load_snapshot,
    mint_review_id,
    resolve_baseline,
    save_snapshot,
)
from gaia.inquiry.state import load_state, save_state


def _utcnow_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


# --------------------------------------------------------------------------- #
# Report dataclass — passive container, all fields filled by run_review.      #
# --------------------------------------------------------------------------- #


@dataclass
class ReviewReport:
    review_id: str
    created_at: str
    path: str
    focus: FocusBinding
    mode: str

    # §8.2 Compile
    compile_status: str
    ir_hash: str | None
    counts: dict[str, int]

    # §8.3 Semantic diff
    semantic_diff: SemanticDiff = field(default_factory=empty_diff)

    # §8.4 Graph health (sourced from validate_local_graph + check_core)
    graph_health: dict[str, Any] = field(default_factory=dict)

    # §8.5 Inquiry tree
    inquiry_tree: dict[str, Any] = field(default_factory=dict)

    # §8.6 Prior holes — list of {label, cid, content, prior}
    prior_holes: list[dict[str, Any]] = field(default_factory=list)

    # §8.7 Belief report
    belief_report: dict[str, Any] = field(default_factory=dict)

    # §15 Diagnostic stream — drives §8.8 next_edits.
    diagnostics: list[Diagnostic] = field(default_factory=list)
    next_edits: list[str] = field(default_factory=list)
    next_edits_structured: list[NextEdit] = field(default_factory=list)

    # ProofState (Round A1 extension)
    proof_context: ProofContext | None = None

    def to_json_dict(self) -> dict[str, Any]:
        return _to_json_dict(self)


# --------------------------------------------------------------------------- #
# Public helpers                                                              #
# --------------------------------------------------------------------------- #


def resolve_graph(path: str | Path):
    """Compile a package and return its LocalCanonicalGraph (or None on failure)."""
    try:
        ensure_package_env(Path(path).resolve())
        loaded = load_gaia_package(str(path))
        apply_package_priors(loaded)
        compiled = compile_loaded_package_artifact(loaded)
    except GaiaCliError:
        return None
    except Exception:
        return None
    return compiled.graph


def render_text(report: ReviewReport) -> str:
    """Spec §8 eight-section text renderer."""
    return _render_text(report)


def render_markdown(report: ReviewReport) -> str:
    """Spec §17.2 Markdown renderer."""
    return _render_markdown(report)


# --------------------------------------------------------------------------- #
# Orchestrator                                                                #
# --------------------------------------------------------------------------- #


def run_review(
    path: str | Path,
    *,
    focus_override: str | None = None,
    mode: str = "auto",
    no_infer: bool = False,
    depth: int = 0,
    since: str | None = None,
    strict: bool = False,
) -> ReviewReport:
    pkg_path = Path(path).resolve()
    state = load_state(pkg_path)
    focus_raw = focus_override if focus_override is not None else state.focus

    warnings: list[str] = []
    errors: list[str] = []
    graph = None
    compile_status = "error"
    ir_hash: str | None = None
    counts = {"knowledge": 0, "strategies": 0, "operators": 0}

    # Step 1: compile via Gaia.
    try:
        ensure_package_env(pkg_path)
        loaded = load_gaia_package(str(pkg_path))
        apply_package_priors(loaded)
        compiled = compile_loaded_package_artifact(loaded)
        graph = compiled.graph
        compile_status = "ok"
    except GaiaCliError as exc:
        errors.append(f"compile: {exc}")
    except Exception as exc:  # surfaced as report error, not raised
        errors.append(f"compile: {exc}")

    if graph is not None:
        counts["knowledge"] = len(getattr(graph, "knowledges", []) or [])
        counts["strategies"] = len(getattr(graph, "strategies", []) or [])
        counts["operators"] = len(getattr(graph, "operators", []) or [])
        ir_hash = getattr(graph, "ir_hash", None)

        # Step 2: validate via Gaia.
        validation = validate_local_graph(graph)
        warnings.extend(validation.warnings)
        errors.extend(validation.errors)

    focus = resolve_focus_target(focus_raw, graph)

    # Step 3: knowledge breakdown via check_core (single source of truth).
    ir_dict = _graph_to_ir_dict(graph)
    if ir_dict is not None:
        kb = analyze_knowledge_breakdown(ir_dict)
    else:
        kb = KnowledgeBreakdown()

    graph_health = _build_graph_health(kb, ir_dict, warnings, errors)
    prior_holes = _build_prior_holes(kb)
    inquiry_tree = _build_inquiry_tree(kb, graph)

    # Step 4: semantic diff against baseline snapshot.
    baseline_id = resolve_baseline(pkg_path, since, state.last_review_id)
    baseline_snap = load_snapshot(pkg_path, baseline_id) if baseline_id else None
    semantic_diff = compute_semantic_diff(ir_dict, baseline_snap)

    # Step 5: inference via gaia.bp; enrich with baseline belief deltas.
    belief_report = _build_belief_report(graph, pkg_path, no_infer, errors, focus)
    if belief_report["ran_inference"] and baseline_snap is not None:
        _annotate_belief_deltas(belief_report, baseline_snap)

    # Step 6: diagnostics — translate validator + breakdown into one stream.
    anchors = find_anchors(pkg_path)
    diagnostics: list[Diagnostic] = []
    diagnostics.extend(from_validation(warnings, errors))
    if ir_dict is not None:
        diagnostics.extend(from_knowledge_breakdown(kb, ir_dict, focus, anchors))
        diagnostics.extend(detect_prior_without_justification(kb, anchors))
    diagnostics.extend(detect_stale_artifact(pkg_path, ir_hash))
    diagnostics.extend(detect_focus_low_posterior(belief_report))
    rejected_targets = {r.target_strategy for r in getattr(state, "synthetic_rejections", []) or []}
    diagnostics.extend(detect_warrant_status(graph, rejected_targets, anchors))
    if graph is not None:
        if ir_dict is not None:
            diagnostics.extend(detect_blocked_warrant_path(graph, kb, anchors))
        diagnostics.extend(detect_focus_unsupported(graph, focus, anchors))
        diagnostics.extend(detect_overstrong_strategy_without_provenance(graph, anchors=anchors))
        diagnostics.extend(
            detect_claim_with_evidence_but_no_focus_connection(graph, focus, anchors)
        )
    diagnostics.extend(detect_large_belief_drop(belief_report))
    diagnostics = rank_diagnostics(diagnostics, mode)
    next_edits_structured = rank_next_edits(
        format_diagnostics_as_structured_edits(diagnostics), mode
    )
    next_edits = [
        f"{e.text} ({e.source_anchor.file}:{e.source_anchor.line})"
        if e.source_anchor is not None
        else e.text
        for e in next_edits_structured
    ]

    # Step 7: ProofContext (Round A1).
    proof_ctx = build_proof_context(graph, state)

    review_id = mint_review_id(ir_hash, mode)
    created_at = _utcnow_iso()
    report = ReviewReport(
        review_id=review_id,
        created_at=created_at,
        path=str(pkg_path),
        focus=focus,
        mode=mode,
        compile_status=compile_status,
        ir_hash=ir_hash,
        counts=counts,
        semantic_diff=semantic_diff,
        graph_health=graph_health,
        inquiry_tree=inquiry_tree,
        prior_holes=prior_holes,
        belief_report=belief_report,
        diagnostics=diagnostics,
        next_edits=next_edits,
        next_edits_structured=next_edits_structured,
        proof_context=proof_ctx,
    )

    # Persist snapshot for future diffs.
    save_snapshot(
        pkg_path,
        review_id=review_id,
        created_at=created_at,
        ir_hash=ir_hash,
        ir_dict=ir_dict,
        beliefs=belief_report.get("beliefs", []),
    )

    state.last_review_id = review_id
    if state.baseline_review_id is None:
        state.baseline_review_id = review_id
    state.mode = mode
    save_state(pkg_path, state)

    return report


def _annotate_belief_deltas(belief_report: dict, baseline_snap: dict) -> None:
    """Compute per-claim belief deltas vs baseline; fill focus/largest_*."""
    base_by_id = {b["knowledge_id"]: b["belief"] for b in baseline_snap.get("beliefs", [])}
    deltas: list[tuple[str, str, float, float, float]] = []
    for entry in belief_report["beliefs"]:
        kid = entry["knowledge_id"]
        if kid not in base_by_id:
            continue
        before = base_by_id[kid]
        after = entry["belief"]
        try:
            delta = float(after) - float(before)
        except (TypeError, ValueError):
            continue
        deltas.append((kid, entry["label"], before, after, delta))

    if belief_report.get("focus"):
        foc = belief_report["focus"]
        for kid, _label, before, after, delta in deltas:
            if kid == foc.get("knowledge_id"):
                foc["before"] = before
                foc["after"] = after
                foc["delta"] = delta
                break

    deltas.sort(key=lambda t: t[4], reverse=True)
    belief_report["largest_increases"] = [
        {"label": lbl, "before": b, "after": a, "delta": d}
        for _kid, lbl, b, a, d in deltas[:3]
        if d > 0
    ]
    belief_report["largest_decreases"] = [
        {"label": lbl, "before": b, "after": a, "delta": d}
        for _kid, lbl, b, a, d in sorted(deltas, key=lambda t: t[4])[:3]
        if d < 0
    ]


# --------------------------------------------------------------------------- #
# Section assemblers — pure, no detection logic.                              #
# --------------------------------------------------------------------------- #


def _graph_to_ir_dict(graph) -> dict | None:
    """Convert a LocalCanonicalGraph to the dict shape consumed by check_core.

    check_core was written against the JSON IR shape. The compiled graph holds
    the same data on dataclasses; this adapter is the only translation layer.
    """
    if graph is None:
        return None
    knowledges = []
    for k in getattr(graph, "knowledges", []) or []:
        knowledges.append(
            {
                "id": getattr(k, "id", ""),
                "label": getattr(k, "label", ""),
                "type": _normalize_type(getattr(k, "type", "")),
                "content": getattr(k, "content", "") or "",
                "metadata": dict(getattr(k, "metadata", {}) or {}),
                "exported": bool(getattr(k, "exported", False)),
            }
        )
    strategies = []
    for s in getattr(graph, "strategies", []) or []:
        strategies.append(
            {
                "id": getattr(s, "id", ""),
                "conclusion": getattr(s, "conclusion", None),
                "premises": list(getattr(s, "premises", []) or []),
                "background": list(getattr(s, "background", []) or []),
            }
        )
    operators = []
    for o in getattr(graph, "operators", []) or []:
        operators.append(
            {
                "id": getattr(o, "id", ""),
                "conclusion": getattr(o, "conclusion", None),
                "variables": list(getattr(o, "variables", []) or []),
            }
        )
    return {"knowledges": knowledges, "strategies": strategies, "operators": operators}


def _normalize_type(t: Any) -> str:
    s = str(t)
    if "." in s:
        s = s.rsplit(".", 1)[-1]
    return s.lower()


def _build_graph_health(
    kb: KnowledgeBreakdown,
    ir_dict: dict | None,
    warnings: list[str],
    errors: list[str],
) -> dict[str, Any]:
    duplicates = find_possible_duplicate_claims(ir_dict) if ir_dict else []
    return {
        "warnings": list(warnings),
        "errors": list(errors),
        "orphaned_claims": list(kb.orphaned),
        "background_only_claims": list(kb.background_only),
        "prior_holes": [h.label for h in kb.holes],
        "possible_duplicates": [{"a": a, "b": b} for a, b in duplicates],
    }


def _build_prior_holes(kb: KnowledgeBreakdown) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for h in kb.holes:
        preview = (h.content[:72] + "...") if len(h.content) > 75 else h.content
        out.append(
            {
                "label": h.label,
                "cid": h.cid,
                "content": preview,
                "prior": "NOT SET (defaults to 0.5)",
            }
        )
    return out


def _build_inquiry_tree(kb: KnowledgeBreakdown, graph) -> dict[str, Any]:
    n_strategies = len(getattr(graph, "strategies", []) or []) if graph else 0
    hole_ids = {h.cid for h in kb.holes}
    blocked_paths = 0
    if graph is not None and hole_ids:
        for s in getattr(graph, "strategies", []) or []:
            premises = list(getattr(s, "premises", None) or [])
            if any(p in hole_ids for p in premises):
                blocked_paths += 1
    return {
        "goals": len(kb.questions),
        "accepted_warrants": 0,
        "unreviewed_warrants": n_strategies,
        "blocked_paths": blocked_paths,
        "structural_holes": list(kb.orphaned),
    }


def _build_belief_report(
    graph,
    pkg_path: Path,
    no_infer: bool,
    errors: list[str],
    focus: FocusBinding,
) -> dict[str, Any]:
    out: dict[str, Any] = {
        "ran_inference": False,
        "beliefs": [],
        "focus": None,
        "largest_increases": [],
        "largest_decreases": [],
    }
    if graph is None or no_infer:
        return out
    if errors:
        return out
    try:
        from gaia.bp import lower_local_graph
        from gaia.bp.engine import InferenceEngine

        foreign = collect_foreign_node_priors(graph, pkg_path)
        fg = lower_local_graph(graph, node_priors=foreign or None)
        fg_errs = fg.validate()
        if fg_errs:
            errors.extend(fg_errs)
            return out
        engine = InferenceEngine()
        result = engine.run(fg)
    except Exception as exc:  # pragma: no cover
        errors.append(f"infer: {exc}")
        return out

    out["ran_inference"] = True
    kbyid = {k.id: k for k in graph.knowledges}
    for kid, belief in sorted(result.bp_result.beliefs.items()):
        if kid in kbyid:
            out["beliefs"].append(
                {"knowledge_id": kid, "label": kbyid[kid].label, "belief": belief}
            )

    if focus.resolved_id:
        for entry in out["beliefs"]:
            if entry["knowledge_id"] == focus.resolved_id:
                out["focus"] = {
                    "knowledge_id": focus.resolved_id,
                    "label": entry["label"],
                    "before": None,
                    "after": entry["belief"],
                    "delta": None,
                }
                break

    return out


def publish_blockers(report: ReviewReport) -> list[str]:
    """Spec §12 publish-readiness — return non-empty list iff strict mode should fail.

    The publish gate fails if *any* of these hold:
    - graph_health.errors is non-empty
    - graph_health.warnings is non-empty
    - any prior_hole, unreviewed_warrant, prior_without_justification, or
      stale_artifact diagnostic remains
    """
    blockers: list[str] = []
    health = report.graph_health or {}
    for e in health.get("errors", []) or []:
        blockers.append(f"graph error: {e}")
    for w in health.get("warnings", []) or []:
        blockers.append(f"graph warning: {w}")
    blocking_kinds = {
        "prior_hole",
        "unreviewed_warrant",
        "prior_without_justification",
        "stale_artifact",
        "blocked_warrant_path",
        "focus_unsupported",
        "overstrong_strategy_without_provenance",
    }
    for d in report.diagnostics:
        if d.kind in blocking_kinds:
            blockers.append(f"{d.kind}: {d.label} — {d.message}")
    return blockers
