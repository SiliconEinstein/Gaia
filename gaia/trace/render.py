"""Render trace review reports as text, Markdown, or JSON.

设计原则：
- 与 ``gaia.inquiry.render`` 一致的章节顺序（§1 → §8）与命名约定
- 任何字段缺失走优雅降级，不抛异常（吸取 dz-fusion 教训：渲染层不允许 crash）
- ``render_json`` 等价于 ``json.dumps(report.to_json_dict(), sort_keys=True, indent=2)``
  ——决定性回归测试可以 byte-equal（除 ``created_at`` 字段）
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from gaia.trace.review import TraceReviewReport


# ============ Text ============


def render_text(report: "TraceReviewReport") -> str:
    """Render a trace review report as the plain-text CLI view."""
    out: list[str] = []
    out.append("=" * 72)
    out.append(f"ARM Trace Review  —  {report.trace_review_id}")
    out.append("=" * 72)
    out.append(f"path        : {report.path}")
    out.append(f"created_at  : {report.created_at}")
    out.append(f"mode        : {report.mode}")
    out.append("")

    out.append("§2 Manifest")
    out.append("-" * 72)
    out.append(f"  status        : {report.manifest_status}")
    out.append(f"  manifest_hash : {report.manifest_hash or '(none)'}")
    out.append("  counts        :")
    for k in sorted(report.counts):
        out.append(f"    {k:<22} : {report.counts[k]}")
    out.append("")

    out.append("§3 Hash Chain")
    out.append("-" * 72)
    hc = report.hash_chain or {}
    out.append(f"  ok            : {bool(hc.get('ok'))}")
    out.append(f"  broken_at_seq : {hc.get('broken_at_seq')}")
    out.append(f"  recomputed_root : {hc.get('recomputed_root', '')[:32]}...")
    if hc.get("declared_root") and hc.get("declared_root") != hc.get("recomputed_root"):
        out.append(f"  declared_root   : {hc['declared_root'][:32]}... (mismatch)")
    out.append("")

    out.append("§4 Causal Health")
    out.append("-" * 72)
    for k, v in (report.causal_health or {}).items():
        out.append(f"  {k:<22} : {v}")
    out.append("")

    out.append("§5 Reference Validity")
    out.append("-" * 72)
    if not report.reference_validity:
        out.append("  (no claim_refs in trace)")
    else:
        for r in report.reference_validity:
            mark = "✓" if r.get("resolved") else "✗"
            out.append(
                f"  {mark} seq={r['seq']:<3} {r['relation']:<12} "
                f"claim={r['claim_id']!r} review_id={r['review_id']!r}"
            )
    out.append("")

    out.append("§6 Tampering Signals")
    out.append("-" * 72)
    if not report.tampering:
        out.append("  (clean)")
    else:
        for t in report.tampering:
            out.append(f"  [{t['severity']}] {t['kind']} @ {t['target']}: {t['message']}")
    out.append("")

    out.append("§7 Execution Stats")
    out.append("-" * 72)
    es = report.execution_stats or {}
    out.append(f"  actors           : {es.get('actors')}")
    out.append(f"  kind_distribution: {es.get('kind_distribution')}")
    out.append(f"  retry_count      : {es.get('retry_count')}")
    out.append(f"  time_span_secs   : {es.get('time_span_seconds')}")
    out.append("")

    out.append("§8 Diagnostics + Next Edits")
    out.append("-" * 72)
    if not report.diagnostics:
        out.append("  (no diagnostics — trace passes all checks)")
    else:
        for d in report.diagnostics:
            out.append(f"  [{d.severity}] {d.kind} @ {d.target} :: {d.message}")
    out.append("")
    if report.next_edits:
        out.append("Suggested next edits:")
        for i, e in enumerate(report.next_edits, 1):
            out.append(f"  {i}. {e}")
    out.append("")
    return "\n".join(out)


# ============ Markdown ============


def render_markdown(report: "TraceReviewReport") -> str:
    """Render a trace review report as Markdown."""
    out: list[str] = []
    out.append(f"# ARM Trace Review — `{report.trace_review_id}`")
    out.append("")
    out.append(f"- **path**: `{report.path}`")
    out.append(f"- **created_at**: {report.created_at}")
    out.append(f"- **mode**: `{report.mode}`")
    out.append("")

    out.append("## §2 Manifest")
    out.append(f"- status: `{report.manifest_status}`")
    out.append(f"- manifest_hash: `{report.manifest_hash or '(none)'}`")
    out.append("- counts:")
    for k in sorted(report.counts):
        out.append(f"  - `{k}`: {report.counts[k]}")
    out.append("")

    out.append("## §3 Hash Chain")
    hc = report.hash_chain or {}
    out.append(f"- ok: `{bool(hc.get('ok'))}`")
    out.append(f"- broken_at_seq: `{hc.get('broken_at_seq')}`")
    out.append(f"- recomputed_root: `{hc.get('recomputed_root', '')}`")
    out.append("")

    out.append("## §4 Causal Health")
    for k, v in (report.causal_health or {}).items():
        out.append(f"- **{k}**: `{v}`")
    out.append("")

    out.append("## §5 Reference Validity")
    if not report.reference_validity:
        out.append("_no claim_refs in trace_")
    else:
        out.append("| seq | relation | claim_id | review_id | resolved |")
        out.append("|---|---|---|---|---|")
        for r in report.reference_validity:
            out.append(
                f"| {r['seq']} | {r['relation']} | `{r['claim_id']}` | "
                f"`{r['review_id']}` | {'✓' if r.get('resolved') else '✗'} |"
            )
    out.append("")

    out.append("## §6 Tampering Signals")
    if not report.tampering:
        out.append("_clean_")
    else:
        for t in report.tampering:
            out.append(f"- **[{t['severity']}] {t['kind']}** @ `{t['target']}` — {t['message']}")
    out.append("")

    out.append("## §7 Execution Stats")
    es = report.execution_stats or {}
    out.append(f"- actors: `{es.get('actors')}`")
    out.append(f"- kind_distribution: `{es.get('kind_distribution')}`")
    out.append(f"- retry_count: `{es.get('retry_count')}`")
    out.append(f"- time_span_seconds: `{es.get('time_span_seconds')}`")
    out.append("")

    out.append("## §8 Diagnostics + Next Edits")
    if not report.diagnostics:
        out.append("_no diagnostics — trace passes all checks_")
    else:
        for d in report.diagnostics:
            out.append(f"- **[{d.severity}] {d.kind}** @ `{d.target}` — {d.message}")
    if report.next_edits:
        out.append("")
        out.append("**Suggested next edits:**")
        for i, e in enumerate(report.next_edits, 1):
            out.append(f"{i}. {e}")
    out.append("")
    return "\n".join(out)


# ============ JSON ============


def to_json_dict(report: "TraceReviewReport") -> dict[str, Any]:
    """Return the JSON-compatible mapping for a trace review report."""
    return report.to_json_dict()


def render_json(report: "TraceReviewReport") -> str:
    """Render deterministic JSON with stable key ordering."""
    return json.dumps(
        report.to_json_dict(),
        ensure_ascii=False,
        sort_keys=True,
        indent=2,
    )
