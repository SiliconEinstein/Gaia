"""Spec §8 text renderer + §9.1 JSON serializer for ReviewReport."""

from __future__ import annotations

import json
from typing import Any

from gaia.inquiry.focus import FocusBinding
from gaia.inquiry.proof_state import ProofContext


def render_text(report: "ReviewReport") -> str:  # noqa: F821 - forward ref from review.py
    lines: list[str] = []
    lines.append("Gaia Inquiry Review")
    lines.append("─" * 20)
    lines.append("")

    lines.append("## Focus")
    f = report.focus
    if f.resolved_id:
        lines.append(f"  {f.resolved_label} ({f.kind}, id={f.resolved_id})")
    elif f.raw:
        lines.append(f"  (freeform) {f.raw}")
    else:
        lines.append("  (no focus set)")
    lines.append(f"  mode: {report.mode}")
    lines.append("")

    lines.append("## Compile")
    lines.append(f"  status: {report.compile_status}")
    if report.ir_hash:
        lines.append(f"  ir_hash: {report.ir_hash}")
    for k, v in report.counts.items():
        lines.append(f"  {k}: {v}")
    lines.append("")

    lines.append("## Semantic diff")
    d = report.semantic_diff
    if d.baseline_review_id is None:
        lines.append("  (no baseline review — run `gaia inquiry review` again to diff)")
    elif d.is_empty:
        lines.append(f"  baseline: {d.baseline_review_id}")
        lines.append("  (no semantic changes)")
    else:
        lines.append(f"  baseline: {d.baseline_review_id}")
        # §14.2 — print every non-empty category with consistent +/- prefixes.
        for tag, items in (
            ("claims", d.added_claims),
            ("questions", d.added_questions),
            ("settings", d.added_settings),
            ("strategies", d.added_strategies),
            ("operators", d.added_operators),
        ):
            if items:
                lines.append(f"  + {len(items)} {tag}")
        for tag, items in (
            ("claims", d.removed_claims),
            ("questions", d.removed_questions),
            ("settings", d.removed_settings),
            ("strategies", d.removed_strategies),
            ("operators", d.removed_operators),
        ):
            if items:
                lines.append(f"  - {len(items)} {tag}")
        if d.changed_claims:
            lines.append(f"  ~ {len(d.changed_claims)} changed claims")
        if d.changed_strategies:
            lines.append(f"  ~ {len(d.changed_strategies)} changed strategies")
        if d.changed_operators:
            lines.append(f"  ~ {len(d.changed_operators)} changed operators")
        if d.changed_priors:
            lines.append("  changed priors:")
            for delta in d.changed_priors:
                lines.append(f"    - {delta.label}: {delta.before} → {delta.after}")
        if d.changed_exports:
            lines.append("  changed exports:")
            for delta in d.changed_exports:
                lines.append(f"    - {delta.label}: {delta.before} → {delta.after}")
    lines.append("")

    lines.append("## Graph health")
    gh = report.graph_health
    lines.append(f"  warnings: {len(gh['warnings'])}")
    lines.append(f"  errors: {len(gh['errors'])}")
    lines.append(f"  orphaned claims: {len(gh['orphaned_claims'])}")
    lines.append(f"  background-only claims: {len(gh['background_only_claims'])}")
    lines.append(f"  independent claims missing priors: {len(gh['prior_holes'])}")
    lines.append(f"  possible duplicate claims: {len(gh['possible_duplicates'])}")
    for msg in gh["errors"]:
        lines.append(f"  ! {msg}")
    for msg in gh["warnings"]:
        lines.append(f"  · {msg}")
    lines.append("")

    lines.append("## Inquiry tree")
    it = report.inquiry_tree
    lines.append(f"  goals: {it['goals']}")
    lines.append(f"  accepted warrants: {it['accepted_warrants']}")
    lines.append(f"  unreviewed warrants: {it['unreviewed_warrants']}")
    lines.append(f"  blocked paths: {it['blocked_paths']}")
    lines.append(f"  structural holes: {len(it['structural_holes'])}")
    lines.append("")

    lines.append("## Prior holes")
    if not report.prior_holes:
        lines.append("  (all independent claims have priors set)")
    else:
        for h in report.prior_holes:
            lines.append(f"  - {h['label']}")
            preview = h.get("content", "")
            if preview:
                lines.append(f"    content: {preview}")
            lines.append(f"    prior:   {h['prior']}")
    lines.append("")

    lines.append("## Belief report")
    br = report.belief_report
    if not br["ran_inference"]:
        lines.append("  (inference skipped)")
    else:
        if br.get("focus"):
            foc = br["focus"]
            if foc.get("delta") is not None:
                lines.append(
                    f"  focus {foc['label']}: {foc['before']} → {foc['after']} "
                    f"(Δ={foc['delta']:+.3f})"
                )
            else:
                lines.append(f"  focus {foc['label']}: {foc['after']:.3f}")
        lines.append(f"  total claims with beliefs: {len(br['beliefs'])}")
        if br.get("largest_increases"):
            lines.append("  largest increases:")
            for item in br["largest_increases"]:
                lines.append(f"    - {item['label']}: {item['before']} → {item['after']}")
        if br.get("largest_decreases"):
            lines.append("  largest decreases:")
            for item in br["largest_decreases"]:
                lines.append(f"    - {item['label']}: {item['before']} → {item['after']}")
    lines.append("")

    if report.proof_context is not None and (
        report.proof_context.obligations
        or report.proof_context.hypotheses
        or report.proof_context.rejections
    ):
        pc = report.proof_context
        lines.append("## Proof state")
        lines.append(f"  obligations ({len(pc.obligations)}):")
        for ob in pc.obligations:
            lines.append(f"    - [{ob.diagnostic_kind}] {ob.content}")
        if pc.hypotheses:
            lines.append(f"  hypotheses ({len(pc.hypotheses)}):")
            for hp in pc.hypotheses:
                lines.append(f"    - {hp.content}")
        if pc.rejections:
            lines.append(f"  rejections ({len(pc.rejections)}):")
            for rj in pc.rejections:
                lines.append(f"    - {rj.target_strategy}: {rj.content}")
        lines.append("")

    lines.append("## Next edits")
    if not report.next_edits:
        lines.append("  (no suggested edits)")
    else:
        for i, edit in enumerate(report.next_edits, 1):
            lines.append(f"  {i}. {edit}")

    return "\n".join(lines)


def to_json_dict(report: "ReviewReport") -> dict[str, Any]:  # noqa: F821
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


def render_markdown(report) -> str:
    """Spec §17.2 Markdown renderer.

    Mirrors the eight-section text layout but uses Markdown headings, bullet
    lists, and fenced code blocks for IDs/source anchors. The section names
    match render_text exactly so agents can diff outputs.
    """
    md: list[str] = []
    md.append("# Gaia Inquiry Review")
    md.append("")
    md.append(f"- **review_id**: `{report.review_id}`")
    md.append(f"- **created_at**: `{report.created_at}`")
    md.append(f"- **path**: `{report.path}`")
    md.append("")

    md.append("## Focus")
    f = report.focus
    if f.resolved_id:
        md.append(f"- **target**: `{f.resolved_label}` (`{f.kind}`, id=`{f.resolved_id}`)")
    elif f.raw:
        md.append(f"- **freeform**: `{f.raw}`")
    else:
        md.append("- _no focus set_")
    md.append(f"- **mode**: `{report.mode}`")
    md.append("")

    md.append("## Compile")
    md.append(f"- status: `{report.compile_status}`")
    if report.ir_hash:
        md.append(f"- ir_hash: `{report.ir_hash}`")
    for k, v in report.counts.items():
        md.append(f"- {k}: {v}")
    md.append("")

    md.append("## Semantic diff")
    d = report.semantic_diff
    if d.baseline_review_id is None:
        md.append("_no baseline review yet_")
    elif d.is_empty:
        md.append(f"baseline: `{d.baseline_review_id}` — no semantic changes")
    else:
        md.append(f"baseline: `{d.baseline_review_id}`")
        md.append("")
        for heading, items in (
            ("Added claims", d.added_claims),
            ("Removed claims", d.removed_claims),
            ("Added questions", d.added_questions),
            ("Removed questions", d.removed_questions),
            ("Added settings", d.added_settings),
            ("Removed settings", d.removed_settings),
            ("Added strategies", d.added_strategies),
            ("Removed strategies", d.removed_strategies),
            ("Added operators", d.added_operators),
            ("Removed operators", d.removed_operators),
        ):
            if items:
                md.append(f"**{heading}** ({len(items)})")
                for x in items:
                    md.append(f"- `{x}`")
                md.append("")
        for heading, deltas in (
            ("Changed claims", d.changed_claims),
            ("Changed strategies", d.changed_strategies),
            ("Changed operators", d.changed_operators),
            ("Changed priors", d.changed_priors),
            ("Changed exports", d.changed_exports),
        ):
            if deltas:
                md.append(f"**{heading}** ({len(deltas)})")
                for delta in deltas:
                    md.append(
                        f"- `{delta.label}` _{delta.field}_: `{delta.before}` → `{delta.after}`"
                    )
                md.append("")
    md.append("")

    md.append("## Graph health")
    gh = report.graph_health
    md.append(f"- warnings: {len(gh['warnings'])}")
    md.append(f"- errors: {len(gh['errors'])}")
    md.append(f"- orphaned claims: {len(gh['orphaned_claims'])}")
    md.append(f"- background-only claims: {len(gh['background_only_claims'])}")
    md.append(f"- prior holes: {len(gh['prior_holes'])}")
    md.append(f"- possible duplicates: {len(gh['possible_duplicates'])}")
    if gh["errors"]:
        md.append("")
        md.append("**Errors**")
        for msg in gh["errors"]:
            md.append(f"- {msg}")
    if gh["warnings"]:
        md.append("")
        md.append("**Warnings**")
        for msg in gh["warnings"]:
            md.append(f"- {msg}")
    md.append("")

    md.append("## Inquiry tree")
    it = report.inquiry_tree
    md.append(f"- goals: {it['goals']}")
    md.append(f"- accepted warrants: {it['accepted_warrants']}")
    md.append(f"- unreviewed warrants: {it['unreviewed_warrants']}")
    md.append(f"- blocked paths: {it['blocked_paths']}")
    md.append(f"- structural holes: {len(it['structural_holes'])}")
    md.append("")

    md.append("## Prior holes")
    if not report.prior_holes:
        md.append("_all independent claims have priors set_")
    else:
        for h in report.prior_holes:
            md.append(f"- **{h['label']}**")
            preview = h.get("content", "")
            if preview:
                md.append(f"  - content: {preview}")
            md.append(f"  - prior: `{h['prior']}`")
    md.append("")

    md.append("## Belief report")
    br = report.belief_report
    if not br["ran_inference"]:
        md.append("_inference skipped_")
    else:
        if br.get("focus"):
            foc = br["focus"]
            if foc.get("delta") is not None:
                md.append(
                    f"- focus **{foc['label']}**: {foc['before']} → {foc['after']} "
                    f"(Δ={foc['delta']:+.3f})"
                )
            else:
                md.append(f"- focus **{foc['label']}**: {foc['after']:.3f}")
        md.append(f"- claims with beliefs: {len(br['beliefs'])}")
        if br.get("largest_increases"):
            md.append("")
            md.append("**Largest increases**")
            for item in br["largest_increases"]:
                md.append(f"- `{item['label']}`: {item['before']} → {item['after']}")
        if br.get("largest_decreases"):
            md.append("")
            md.append("**Largest decreases**")
            for item in br["largest_decreases"]:
                md.append(f"- `{item['label']}`: {item['before']} → {item['after']}")
    md.append("")

    if report.proof_context is not None and (
        report.proof_context.obligations
        or report.proof_context.hypotheses
        or report.proof_context.rejections
    ):
        pc = report.proof_context
        md.append("## Proof state")
        if pc.obligations:
            md.append(f"**Obligations** ({len(pc.obligations)})")
            for ob in pc.obligations:
                md.append(f"- _[{ob.diagnostic_kind}]_ {ob.content}")
        if pc.hypotheses:
            md.append("")
            md.append(f"**Hypotheses** ({len(pc.hypotheses)})")
            for hp in pc.hypotheses:
                md.append(f"- {hp.content}")
        if pc.rejections:
            md.append("")
            md.append(f"**Rejections** ({len(pc.rejections)})")
            for rj in pc.rejections:
                md.append(f"- `{rj.target_strategy}`: {rj.content}")
        md.append("")

    md.append("## Next edits")
    if not report.next_edits_structured and not report.next_edits:
        md.append("_no suggested edits_")
    else:
        items = report.next_edits_structured or [None for _ in report.next_edits]
        for i, edit in enumerate(report.next_edits_structured, 1):
            anchor = ""
            if edit.source_anchor is not None:
                a = edit.source_anchor
                anchor = f" — `{a.file}:{a.line}`"
            md.append(f"{i}. _[{edit.kind}/{edit.severity}]_ {edit.text}{anchor}")
        if not report.next_edits_structured:
            for i, edit in enumerate(report.next_edits, 1):
                md.append(f"{i}. {edit}")

    return "\n".join(md)


def render_json(report) -> str:
    return json.dumps(to_json_dict(report), ensure_ascii=False, indent=2)
