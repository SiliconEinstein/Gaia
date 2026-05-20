"""Spec §8 text renderer + §9.1 JSON serializer for ReviewReport."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from gaia.engine.inquiry.focus import FocusBinding
from gaia.engine.inquiry.proof_state import ProofContext

if TYPE_CHECKING:
    from gaia.engine.inquiry.review import ReviewReport


def _append_text_focus(lines: list[str], report: ReviewReport) -> None:
    """Append text focus section."""
    lines.append("## Focus")
    focus = report.focus
    if focus.resolved_id:
        lines.append(f"  {focus.resolved_label} ({focus.kind}, id={focus.resolved_id})")
    elif focus.raw:
        lines.append(f"  (freeform) {focus.raw}")
    else:
        lines.append("  (no focus set)")
    lines.append(f"  mode: {report.mode}")
    lines.append("")


def _append_text_compile(lines: list[str], report: ReviewReport) -> None:
    """Append text compile section."""
    lines.append("## Compile")
    lines.append(f"  status: {report.compile_status}")
    if report.ir_hash:
        lines.append(f"  ir_hash: {report.ir_hash}")
    for key, value in report.counts.items():
        lines.append(f"  {key}: {value}")
    lines.append("")


def _append_text_semantic_diff(lines: list[str], report: ReviewReport) -> None:
    """Append text semantic-diff section."""
    lines.append("## Semantic diff")
    diff = report.semantic_diff
    if diff.baseline_review_id is None:
        lines.append("  (no baseline review — run `gaia inquiry review` again to diff)")
    elif diff.is_empty:
        lines.append(f"  baseline: {diff.baseline_review_id}")
        lines.append("  (no semantic changes)")
    else:
        lines.append(f"  baseline: {diff.baseline_review_id}")
        _append_text_diff_counts(lines, diff)
        _append_text_diff_details(lines, diff)
    lines.append("")


def _append_text_diff_counts(lines: list[str], diff: Any) -> None:
    """Append text diff count rows."""
    for tag, items in (
        ("claims", diff.added_claims),
        ("questions", diff.added_questions),
        ("settings", diff.added_settings),
        ("strategies", diff.added_strategies),
        ("operators", diff.added_operators),
    ):
        if items:
            lines.append(f"  + {len(items)} {tag}")
    for tag, items in (
        ("claims", diff.removed_claims),
        ("questions", diff.removed_questions),
        ("settings", diff.removed_settings),
        ("strategies", diff.removed_strategies),
        ("operators", diff.removed_operators),
    ):
        if items:
            lines.append(f"  - {len(items)} {tag}")
    for tag, items in (
        ("changed claims", diff.changed_claims),
        ("changed strategies", diff.changed_strategies),
        ("changed operators", diff.changed_operators),
    ):
        if items:
            lines.append(f"  ~ {len(items)} {tag}")


def _append_text_diff_details(lines: list[str], diff: Any) -> None:
    """Append text changed-prior/export details."""
    if diff.changed_priors:
        lines.append("  changed priors:")
        for delta in diff.changed_priors:
            lines.append(f"    - {delta.label}: {delta.before} → {delta.after}")
    if diff.changed_exports:
        lines.append("  changed exports:")
        for delta in diff.changed_exports:
            lines.append(f"    - {delta.label}: {delta.before} → {delta.after}")


def _append_text_graph_health(lines: list[str], report: ReviewReport) -> None:
    """Append text graph-health section."""
    lines.append("## Graph health")
    graph_health = report.graph_health
    lines.append(f"  warnings: {len(graph_health['warnings'])}")
    lines.append(f"  errors: {len(graph_health['errors'])}")
    lines.append(f"  orphaned claims: {len(graph_health['orphaned_claims'])}")
    lines.append(f"  background-only claims: {len(graph_health['background_only_claims'])}")
    lines.append(f"  independent claims missing priors: {len(graph_health['prior_holes'])}")
    lines.append(f"  possible duplicate claims: {len(graph_health['possible_duplicates'])}")
    for msg in graph_health["errors"]:
        lines.append(f"  ! {msg}")
    for msg in graph_health["warnings"]:
        lines.append(f"  · {msg}")
    lines.append("")


def _append_text_inquiry_tree(lines: list[str], report: ReviewReport) -> None:
    """Append text inquiry-tree section."""
    lines.append("## Inquiry tree")
    inquiry_tree = report.inquiry_tree
    lines.append(f"  goals: {inquiry_tree['goals']}")
    lines.append(f"  accepted warrants: {inquiry_tree['accepted_warrants']}")
    lines.append(f"  unreviewed warrants: {inquiry_tree['unreviewed_warrants']}")
    lines.append(f"  blocked paths: {inquiry_tree['blocked_paths']}")
    lines.append(f"  structural holes: {len(inquiry_tree['structural_holes'])}")
    lines.append("")


def _append_text_prior_holes(lines: list[str], report: ReviewReport) -> None:
    """Append text prior-hole section."""
    lines.append("## Prior holes")
    if not report.prior_holes:
        lines.append("  (all independent claims have priors set)")
    else:
        for hole in report.prior_holes:
            lines.append(f"  - {hole['label']}")
            preview = hole.get("content", "")
            if preview:
                lines.append(f"    content: {preview}")
            lines.append(f"    prior:   {hole['prior']}")
    lines.append("")


def _append_text_belief_report(lines: list[str], report: ReviewReport) -> None:
    """Append text belief-report section."""
    lines.append("## Belief report")
    belief_report = report.belief_report
    if not belief_report["ran_inference"]:
        lines.append("  (inference skipped)")
    else:
        _append_text_focus_belief(lines, belief_report)
        lines.append(f"  total claims with beliefs: {len(belief_report['beliefs'])}")
        _append_text_belief_deltas(lines, belief_report)
    lines.append("")


def _append_text_focus_belief(lines: list[str], belief_report: dict[str, Any]) -> None:
    """Append text focus belief row when present."""
    if not belief_report.get("focus"):
        return
    focus = belief_report["focus"]
    if focus.get("delta") is not None:
        lines.append(
            f"  focus {focus['label']}: {focus['before']} → {focus['after']} "
            f"(Δ={focus['delta']:+.3f})"
        )
    else:
        lines.append(f"  focus {focus['label']}: {focus['after']:.3f}")


def _append_text_belief_deltas(lines: list[str], belief_report: dict[str, Any]) -> None:
    """Append largest belief increases/decreases."""
    if belief_report.get("largest_increases"):
        lines.append("  largest increases:")
        for item in belief_report["largest_increases"]:
            lines.append(f"    - {item['label']}: {item['before']} → {item['after']}")
    if belief_report.get("largest_decreases"):
        lines.append("  largest decreases:")
        for item in belief_report["largest_decreases"]:
            lines.append(f"    - {item['label']}: {item['before']} → {item['after']}")


def _append_text_proof_state(lines: list[str], report: ReviewReport) -> None:
    """Append text proof-state section when populated."""
    proof_context = report.proof_context
    if proof_context is None:
        return
    if not (proof_context.obligations or proof_context.hypotheses or proof_context.rejections):
        return
    lines.append("## Proof state")
    lines.append(f"  obligations ({len(proof_context.obligations)}):")
    for obligation in proof_context.obligations:
        lines.append(f"    - [{obligation.diagnostic_kind}] {obligation.content}")
    if proof_context.hypotheses:
        lines.append(f"  hypotheses ({len(proof_context.hypotheses)}):")
        for hypothesis in proof_context.hypotheses:
            lines.append(f"    - {hypothesis.content}")
    if proof_context.rejections:
        lines.append(f"  rejections ({len(proof_context.rejections)}):")
        for rejection in proof_context.rejections:
            lines.append(f"    - {rejection.target_strategy}: {rejection.content}")
    lines.append("")


def _append_text_next_edits(lines: list[str], report: ReviewReport) -> None:
    """Append text next-edits section."""
    lines.append("## Next edits")
    if not report.next_edits:
        lines.append("  (no suggested edits)")
    else:
        for index, edit in enumerate(report.next_edits, 1):
            lines.append(f"  {index}. {edit}")


def render_text(report: ReviewReport) -> str:
    """Render a review report as the spec §8 plain-text layout."""
    lines: list[str] = []
    lines.append("Gaia Inquiry Review")
    lines.append("─" * 20)
    lines.append("")

    _append_text_focus(lines, report)
    _append_text_compile(lines, report)
    _append_text_semantic_diff(lines, report)
    _append_text_graph_health(lines, report)
    _append_text_inquiry_tree(lines, report)
    _append_text_prior_holes(lines, report)
    _append_text_belief_report(lines, report)
    _append_text_proof_state(lines, report)
    _append_text_next_edits(lines, report)

    return "\n".join(lines)


def to_json_dict(report: ReviewReport) -> dict[str, Any]:
    """Serialize a review report to the spec §9.1 JSON dictionary shape."""
    return {
        "review_id": report.review_id,
        "created_at": report.created_at,
        "path": report.path,
        "focus": _focus_to_dict(report.focus),
        "mode": report.mode,
        "compile": {
            "status": report.compile_status,
            "ir_hash": report.ir_hash,
            "counts": dict(report.counts),
        },
        "semantic_diff": report.semantic_diff.to_dict(),
        "graph_health": report.graph_health,
        "inquiry_tree": report.inquiry_tree,
        "prior_holes": list(report.prior_holes),
        "belief_report": report.belief_report,
        "diagnostics": [d.to_dict() for d in report.diagnostics],
        "next_edits": list(report.next_edits),
        "next_edits_structured": [e.to_dict() for e in report.next_edits_structured],
        "proof_context": _proof_context_to_dict(report.proof_context),
    }


def _focus_to_dict(f: FocusBinding) -> dict[str, Any]:
    return {
        "raw": f.raw,
        "resolved_id": f.resolved_id,
        "resolved_label": f.resolved_label,
        "kind": f.kind,
    }


def _proof_context_to_dict(pc: ProofContext | None) -> dict[str, Any]:
    if pc is None:
        return {"obligations": [], "hypotheses": [], "rejections": []}
    return {
        "obligations": [vars(o) for o in pc.obligations],
        "hypotheses": [vars(h) for h in pc.hypotheses],
        "rejections": [vars(r) for r in pc.rejections],
    }


def _append_markdown_header(md: list[str], report: ReviewReport) -> None:
    """Append Markdown document header and metadata."""
    md.append("# Gaia Inquiry Review")
    md.append("")
    md.append(f"- **review_id**: `{report.review_id}`")
    md.append(f"- **created_at**: `{report.created_at}`")
    md.append(f"- **path**: `{report.path}`")
    md.append("")


def _append_markdown_focus(md: list[str], report: ReviewReport) -> None:
    """Append Markdown focus section."""
    md.append("## Focus")
    focus = report.focus
    if focus.resolved_id:
        md.append(
            f"- **target**: `{focus.resolved_label}` (`{focus.kind}`, id=`{focus.resolved_id}`)"
        )
    elif focus.raw:
        md.append(f"- **freeform**: `{focus.raw}`")
    else:
        md.append("- _no focus set_")
    md.append(f"- **mode**: `{report.mode}`")
    md.append("")


def _append_markdown_compile(md: list[str], report: ReviewReport) -> None:
    """Append Markdown compile section."""
    md.append("## Compile")
    md.append(f"- status: `{report.compile_status}`")
    if report.ir_hash:
        md.append(f"- ir_hash: `{report.ir_hash}`")
    for key, value in report.counts.items():
        md.append(f"- {key}: {value}")
    md.append("")


def _append_markdown_semantic_diff(md: list[str], report: ReviewReport) -> None:
    """Append Markdown semantic-diff section."""
    md.append("## Semantic diff")
    diff = report.semantic_diff
    if diff.baseline_review_id is None:
        md.append("_no baseline review yet_")
    elif diff.is_empty:
        md.append(f"baseline: `{diff.baseline_review_id}` — no semantic changes")
    else:
        md.append(f"baseline: `{diff.baseline_review_id}`")
        md.append("")
        _append_markdown_diff_items(md, diff)
        _append_markdown_delta_items(md, diff)
    md.append("")


def _append_markdown_diff_items(md: list[str], diff: Any) -> None:
    """Append Markdown added/removed ID lists."""
    for heading, items in (
        ("Added claims", diff.added_claims),
        ("Removed claims", diff.removed_claims),
        ("Added questions", diff.added_questions),
        ("Removed questions", diff.removed_questions),
        ("Added settings", diff.added_settings),
        ("Removed settings", diff.removed_settings),
        ("Added strategies", diff.added_strategies),
        ("Removed strategies", diff.removed_strategies),
        ("Added operators", diff.added_operators),
        ("Removed operators", diff.removed_operators),
    ):
        if items:
            md.append(f"**{heading}** ({len(items)})")
            for item in items:
                md.append(f"- `{item}`")
            md.append("")


def _append_markdown_delta_items(md: list[str], diff: Any) -> None:
    """Append Markdown changed-field delta lists."""
    for heading, deltas in (
        ("Changed claims", diff.changed_claims),
        ("Changed strategies", diff.changed_strategies),
        ("Changed operators", diff.changed_operators),
        ("Changed priors", diff.changed_priors),
        ("Changed exports", diff.changed_exports),
    ):
        if deltas:
            md.append(f"**{heading}** ({len(deltas)})")
            for delta in deltas:
                md.append(f"- `{delta.label}` _{delta.field}_: `{delta.before}` → `{delta.after}`")
            md.append("")


def _append_markdown_graph_health(md: list[str], report: ReviewReport) -> None:
    """Append Markdown graph-health section."""
    md.append("## Graph health")
    graph_health = report.graph_health
    md.append(f"- warnings: {len(graph_health['warnings'])}")
    md.append(f"- errors: {len(graph_health['errors'])}")
    md.append(f"- orphaned claims: {len(graph_health['orphaned_claims'])}")
    md.append(f"- background-only claims: {len(graph_health['background_only_claims'])}")
    md.append(f"- prior holes: {len(graph_health['prior_holes'])}")
    md.append(f"- possible duplicates: {len(graph_health['possible_duplicates'])}")
    _append_markdown_messages(md, "Errors", graph_health["errors"])
    _append_markdown_messages(md, "Warnings", graph_health["warnings"])
    md.append("")


def _append_markdown_messages(md: list[str], heading: str, messages: list[str]) -> None:
    """Append a titled Markdown message list when non-empty."""
    if not messages:
        return
    md.append("")
    md.append(f"**{heading}**")
    for message in messages:
        md.append(f"- {message}")


def _append_markdown_inquiry_tree(md: list[str], report: ReviewReport) -> None:
    """Append Markdown inquiry-tree section."""
    md.append("## Inquiry tree")
    inquiry_tree = report.inquiry_tree
    md.append(f"- goals: {inquiry_tree['goals']}")
    md.append(f"- accepted warrants: {inquiry_tree['accepted_warrants']}")
    md.append(f"- unreviewed warrants: {inquiry_tree['unreviewed_warrants']}")
    md.append(f"- blocked paths: {inquiry_tree['blocked_paths']}")
    md.append(f"- structural holes: {len(inquiry_tree['structural_holes'])}")
    md.append("")


def _append_markdown_prior_holes(md: list[str], report: ReviewReport) -> None:
    """Append Markdown prior-hole section."""
    md.append("## Prior holes")
    if not report.prior_holes:
        md.append("_all independent claims have priors set_")
    else:
        for hole in report.prior_holes:
            md.append(f"- **{hole['label']}**")
            preview = hole.get("content", "")
            if preview:
                md.append(f"  - content: {preview}")
            md.append(f"  - prior: `{hole['prior']}`")
    md.append("")


def _append_markdown_belief_report(md: list[str], report: ReviewReport) -> None:
    """Append Markdown belief-report section."""
    md.append("## Belief report")
    belief_report = report.belief_report
    if not belief_report["ran_inference"]:
        md.append("_inference skipped_")
    else:
        _append_markdown_focus_belief(md, belief_report)
        md.append(f"- claims with beliefs: {len(belief_report['beliefs'])}")
        _append_markdown_belief_deltas(md, belief_report)
    md.append("")


def _append_markdown_focus_belief(md: list[str], belief_report: dict[str, Any]) -> None:
    """Append Markdown focus belief row when present."""
    if not belief_report.get("focus"):
        return
    focus = belief_report["focus"]
    if focus.get("delta") is not None:
        md.append(
            f"- focus **{focus['label']}**: {focus['before']} → {focus['after']} "
            f"(Δ={focus['delta']:+.3f})"
        )
    else:
        md.append(f"- focus **{focus['label']}**: {focus['after']:.3f}")


def _append_markdown_belief_deltas(md: list[str], belief_report: dict[str, Any]) -> None:
    """Append largest Markdown belief increases/decreases."""
    for heading, key in (
        ("Largest increases", "largest_increases"),
        ("Largest decreases", "largest_decreases"),
    ):
        if belief_report.get(key):
            md.append("")
            md.append(f"**{heading}**")
            for item in belief_report[key]:
                md.append(f"- `{item['label']}`: {item['before']} → {item['after']}")


def _append_markdown_proof_state(md: list[str], report: ReviewReport) -> None:
    """Append Markdown proof-state section when populated."""
    proof_context = report.proof_context
    if proof_context is None:
        return
    if not (proof_context.obligations or proof_context.hypotheses or proof_context.rejections):
        return
    md.append("## Proof state")
    _append_markdown_proof_items(
        md,
        f"**Obligations** ({len(proof_context.obligations)})",
        [f"_[{item.diagnostic_kind}]_ {item.content}" for item in proof_context.obligations],
    )
    _append_markdown_proof_items(
        md,
        f"**Hypotheses** ({len(proof_context.hypotheses)})",
        [item.content for item in proof_context.hypotheses],
    )
    _append_markdown_proof_items(
        md,
        f"**Rejections** ({len(proof_context.rejections)})",
        [f"`{item.target_strategy}`: {item.content}" for item in proof_context.rejections],
    )
    md.append("")


def _append_markdown_proof_items(md: list[str], heading: str, items: list[str]) -> None:
    """Append a proof subsection when non-empty."""
    if not items:
        return
    if md and md[-1] != "## Proof state":
        md.append("")
    md.append(heading)
    for item in items:
        md.append(f"- {item}")


def _append_markdown_next_edits(md: list[str], report: ReviewReport) -> None:
    """Append Markdown next-edits section."""
    md.append("## Next edits")
    if not report.next_edits_structured and not report.next_edits:
        md.append("_no suggested edits_")
        return
    for index, edit in enumerate(report.next_edits_structured, 1):
        anchor = ""
        if edit.source_anchor is not None:
            source_anchor = edit.source_anchor
            anchor = f" — `{source_anchor.file}:{source_anchor.line}`"
        md.append(f"{index}. _[{edit.kind}/{edit.severity}]_ {edit.text}{anchor}")
    if not report.next_edits_structured:
        for index, edit_text in enumerate(report.next_edits, 1):
            md.append(f"{index}. {edit_text}")


def render_markdown(report: ReviewReport) -> str:
    """Spec §17.2 Markdown renderer.

    Mirrors the eight-section text layout but uses Markdown headings, bullet
    lists, and fenced code blocks for IDs/source anchors. The section names
    match render_text exactly so agents can diff outputs.
    """
    md: list[str] = []
    _append_markdown_header(md, report)
    _append_markdown_focus(md, report)
    _append_markdown_compile(md, report)
    _append_markdown_semantic_diff(md, report)
    _append_markdown_graph_health(md, report)
    _append_markdown_inquiry_tree(md, report)
    _append_markdown_prior_holes(md, report)
    _append_markdown_belief_report(md, report)
    _append_markdown_proof_state(md, report)
    _append_markdown_next_edits(md, report)

    return "\n".join(md)


def render_json(report: ReviewReport) -> str:
    """Render a review report as pretty JSON without ASCII escaping."""
    return json.dumps(to_json_dict(report), ensure_ascii=False, indent=2)
