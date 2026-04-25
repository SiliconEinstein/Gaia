"""Spec §15 — Diagnostic layer over Gaia's existing detectors.

Inquiry does NOT run its own graph analysis. It translates the outputs of
``gaia.ir.validator.validate_local_graph`` and
``gaia.cli.commands.check_core.analyze_knowledge_breakdown`` into a uniform
``Diagnostic`` stream, which drives the `graph_health`, `prior_holes`, and
`next_edits` sections of the review report.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Literal

from gaia.cli.commands.check_core import (
    HoleEntry,
    KnowledgeBreakdown,
    find_possible_duplicate_claims,
)
from gaia.inquiry.anchor import SourceAnchor
from gaia.inquiry.focus import FocusBinding

Severity = Literal["error", "warning", "info"]
DiagnosticKind = Literal[
    "compile_error",
    "validation_error",
    "validation_warning",
    "prior_hole",
    "orphaned_claim",
    "background_only_claim",
    "possible_duplicate_claim",
    "focus_weakness",
    "structural_hole",
    "support_weak",
    "belief_regression",
    "stale_artifact",
    "focus_low_posterior",
    "prior_without_justification",
    "unreviewed_warrant",
    "rejected_warrant",
]


@dataclass
class Diagnostic:
    """Spec §15 Diagnostic record. Uniform across all detection sources."""

    severity: Severity
    kind: DiagnosticKind
    target: str
    label: str
    message: str
    suggested_edit: str = ""
    data: dict = field(default_factory=dict)
    source_anchor: SourceAnchor | None = None

    def to_dict(self) -> dict:
        d = asdict(self)
        if not d["data"]:
            d.pop("data")
        if d.get("source_anchor") is None:
            d.pop("source_anchor", None)
        return d


@dataclass
class NextEdit:
    """Spec §8.8 / Round A2 — 结构化编辑建议。

    ``text`` 是渲染给人看的 imperative 一行; ``source_anchor`` 在可定位时指向
    需要修改的源位置。其余字段复制自产生该 edit 的 Diagnostic。
    """

    text: str
    kind: str
    severity: Severity
    target: str
    label: str
    source_anchor: SourceAnchor | None = None

    def to_dict(self) -> dict:
        d = {
            "text": self.text,
            "kind": self.kind,
            "severity": self.severity,
            "target": self.target,
            "label": self.label,
        }
        if self.source_anchor is not None:
            d["source_anchor"] = self.source_anchor.to_dict()
        return d


def from_validation(warnings: list[str], errors: list[str]) -> list[Diagnostic]:
    """Lift strings from ``ValidationResult`` into ``Diagnostic`` records."""
    out: list[Diagnostic] = []
    for msg in errors:
        out.append(
            Diagnostic(
                severity="error",
                kind="validation_error",
                target="graph",
                label="graph",
                message=msg,
            )
        )
    for msg in warnings:
        out.append(
            Diagnostic(
                severity="warning",
                kind="validation_warning",
                target="graph",
                label="graph",
                message=msg,
            )
        )
    return out


def _attach_anchor(d: Diagnostic, anchors: dict[str, SourceAnchor] | None) -> Diagnostic:
    if anchors and d.label in anchors:
        d.source_anchor = anchors[d.label]
    return d


def from_knowledge_breakdown(
    kb: KnowledgeBreakdown,
    ir: dict,
    focus: FocusBinding | None,
    anchors: dict[str, SourceAnchor] | None = None,
) -> list[Diagnostic]:
    """Emit diagnostics for prior holes, orphans, background-only, duplicates."""
    out: list[Diagnostic] = []
    for entry in kb.holes:
        out.append(_attach_anchor(_prior_hole_diag(entry), anchors))
    for label in kb.orphaned:
        out.append(
            _attach_anchor(
                Diagnostic(
                    severity="warning",
                    kind="orphaned_claim",
                    target=label,
                    label=label,
                    message="Claim is not referenced by any strategy or operator.",
                    suggested_edit=f"Either connect `{label}` to a strategy/operator, or remove it.",
                ),
                anchors,
            )
        )
    for label in kb.background_only:
        out.append(
            _attach_anchor(
                Diagnostic(
                    severity="info",
                    kind="background_only_claim",
                    target=label,
                    label=label,
                    message="Claim appears only in strategy background; not part of the BP graph.",
                    suggested_edit=(
                        f"If `{label}` should affect beliefs, move it to premises; "
                        "otherwise leave as background."
                    ),
                ),
                anchors,
            )
        )
    for a, b in find_possible_duplicate_claims(ir):
        out.append(
            Diagnostic(
                severity="warning",
                kind="possible_duplicate_claim",
                target=f"{a}|{b}",
                label=f"{a} / {b}",
                message=f"Claims `{a}` and `{b}` have identical content.",
                suggested_edit=f"Merge `{a}` and `{b}`, or differentiate their content.",
            )
        )
    return out


def _prior_hole_diag(entry: HoleEntry) -> Diagnostic:
    preview = (entry.content[:72] + "...") if len(entry.content) > 75 else entry.content
    return Diagnostic(
        severity="warning",
        kind="prior_hole",
        target=entry.cid,
        label=entry.label,
        message=f"Independent claim `{entry.label}` has no prior set (defaults to 0.5).",
        suggested_edit=(
            f'Set a prior in priors.py: set_prior("{entry.label}", <value>, '
            'justification="...").'
        ),
        data={"content": preview},
    )


# ---------------------------------------------------------------------------
# Batch B emitters — additional diagnostic sources beyond validator/breakdown.
# ---------------------------------------------------------------------------


def detect_stale_artifact(
    pkg_path,
    current_ir_hash: str | None,
) -> list[Diagnostic]:
    """Compare in-memory ir_hash with on-disk .gaia/ir_hash file.

    If the file exists and differs, the package state on disk was produced by
    an earlier IR — typically because the agent edited Python after the last
    review/build. Always non-fatal (warning).
    """
    from pathlib import Path as _P

    out: list[Diagnostic] = []
    if current_ir_hash is None:
        return out
    f = _P(pkg_path) / ".gaia" / "ir_hash"
    if not f.exists():
        return out
    try:
        recorded = f.read_text(encoding="utf-8").strip()
    except OSError:
        return out
    if not recorded or recorded == current_ir_hash:
        return out
    out.append(
        Diagnostic(
            severity="warning",
            kind="stale_artifact",
            target=".gaia/ir_hash",
            label=".gaia/ir_hash",
            message=(
                f"On-disk ir_hash ({recorded[:12]}...) does not match the freshly "
                f"compiled graph ({current_ir_hash[:12]}...)."
            ),
            suggested_edit=(
                "Re-run `gaia build` (or the package equivalent) to refresh "
                "cached artifacts; otherwise downstream tools may read stale state."
            ),
            data={"recorded": recorded, "current": current_ir_hash},
        )
    )
    return out


def detect_focus_low_posterior(
    belief_report: dict,
    threshold: float = 0.3,
) -> list[Diagnostic]:
    """Emit when the focus claim's posterior is below ``threshold``.

    Spec §15: low posterior on the focus signals that the supporting evidence
    is currently insufficient. Threshold is conservative (0.3) to avoid noise.
    """
    out: list[Diagnostic] = []
    foc = belief_report.get("focus") if isinstance(belief_report, dict) else None
    if not foc:
        return out
    after = foc.get("after")
    if after is None:
        return out
    try:
        val = float(after)
    except (TypeError, ValueError):
        return out
    if val >= threshold:
        return out
    label = foc.get("label", "")
    target = foc.get("knowledge_id", label)
    out.append(
        Diagnostic(
            severity="warning",
            kind="focus_low_posterior",
            target=target,
            label=label,
            message=(
                f"Focus `{label}` posterior is {val:.3f}, below {threshold:.2f}; "
                "evidence supporting it is currently weak."
            ),
            suggested_edit=(
                f"Add a supporting strategy or premise for `{label}`, "
                "or revise the claim if the evidence does not back it."
            ),
            data={"posterior": val, "threshold": threshold},
        )
    )
    return out


def detect_prior_without_justification(
    kb,
    anchors: dict | None = None,
) -> list[Diagnostic]:
    """For every covered (non-hole) prior, require a non-empty justification.

    Reads from ``KnowledgeBreakdown.covered`` — entries with prior set but
    empty ``prior_justification``. Severity is *info*: not blocking, but the
    publish gate may surface it.
    """
    out: list[Diagnostic] = []
    for entry in kb.covered:
        just = (entry.prior_justification or "").strip()
        if just:
            continue
        d = Diagnostic(
            severity="info",
            kind="prior_without_justification",
            target=entry.cid,
            label=entry.label,
            message=(
                f"Claim `{entry.label}` has prior={entry.prior} but no "
                "`prior_justification` recorded."
            ),
            suggested_edit=(
                f'Update priors.py: set_prior("{entry.label}", {entry.prior}, '
                'justification="...").'
            ),
            data={"prior": entry.prior},
        )
        out.append(_attach_anchor(d, anchors))
    return out


def detect_warrant_status(
    graph,
    rejected_strategy_targets: set[str] | None = None,
    anchors: dict | None = None,
) -> list[Diagnostic]:
    """Walk graph.strategies and emit unreviewed/rejected warrants.

    A strategy is *rejected* if its label or id appears in
    ``rejected_strategy_targets`` (sourced from InquiryState.synthetic_rejections).
    Otherwise it is *unreviewed* unless its metadata carries a non-empty
    ``judgment`` key.
    """
    out: list[Diagnostic] = []
    if graph is None:
        return out
    rejected = rejected_strategy_targets or set()
    for s in getattr(graph, "strategies", []) or []:
        sid = getattr(s, "id", "") or ""
        label = sid.split("::")[-1] if sid else getattr(s, "label", "") or ""
        meta = dict(getattr(s, "metadata", None) or {})
        if sid in rejected or label in rejected:
            d = Diagnostic(
                severity="info",
                kind="rejected_warrant",
                target=sid or label,
                label=label,
                message=f"Strategy `{label}` is recorded as rejected.",
                suggested_edit=(
                    f"Either remove `{label}` from the package or replace it "
                    "with a revised strategy."
                ),
            )
            out.append(_attach_anchor(d, anchors))
            continue
        judgment = (meta.get("judgment") or "").strip()
        if not judgment:
            d = Diagnostic(
                severity="info",
                kind="unreviewed_warrant",
                target=sid or label,
                label=label,
                message=f"Strategy `{label}` has no review judgment yet.",
                suggested_edit=(
                    f"Run a review pass on `{label}` and record a judgment "
                    'in its metadata (e.g. metadata={"judgment": "accepted"}).'
                ),
            )
            out.append(_attach_anchor(d, anchors))
    return out


_PRIO = {"error": 0, "warning": 1, "info": 2}


def format_diagnostics_as_next_edits(diags: list[Diagnostic]) -> list[str]:
    """Spec §8 `Next edits` — 文本形式 (向后兼容 Step 2 的 str 列表)。

    若 diagnostic 带 ``source_anchor``, 追加 ``(file:line)`` 到末尾,
    便于人眼直接定位源行。
    """
    seen: set[str] = set()
    ordered: list[str] = []
    for d in sorted(diags, key=lambda d: _PRIO.get(d.severity, 9)):
        edit = d.suggested_edit.strip()
        if not edit or edit in seen:
            continue
        seen.add(edit)
        if d.source_anchor is not None:
            ordered.append(f"{edit} ({d.source_anchor.file}:{d.source_anchor.line})")
        else:
            ordered.append(edit)
    return ordered


def format_diagnostics_as_structured_edits(diags: list[Diagnostic]) -> list[NextEdit]:
    """Round A2 — structured NextEdit 列表, 与文本版 dedup 语义一致。"""
    seen: set[str] = set()
    out: list[NextEdit] = []
    for d in sorted(diags, key=lambda d: _PRIO.get(d.severity, 9)):
        edit = d.suggested_edit.strip()
        if not edit or edit in seen:
            continue
        seen.add(edit)
        out.append(
            NextEdit(
                text=edit,
                kind=d.kind,
                severity=d.severity,
                target=d.target,
                label=d.label,
                source_anchor=d.source_anchor,
            )
        )
    return out
