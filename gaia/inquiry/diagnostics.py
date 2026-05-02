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
    "blocked_warrant_path",
    "focus_unsupported",
    "large_belief_drop",
    "overstrong_strategy_without_provenance",
    "claim_with_evidence_but_no_focus_connection",
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
            f'Set a prior in priors.py: set_prior("{entry.label}", <value>, justification="...").'
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
                f'Update priors.py: set_prior("{entry.label}", {entry.prior}, justification="...").'
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


# ---------------------------------------------------------------------------
# Spec §15.2 — remaining diagnostic emitters
#   blocked_warrant_path / focus_unsupported / large_belief_drop /
#   overstrong_strategy_without_provenance /
#   claim_with_evidence_but_no_focus_connection
# ---------------------------------------------------------------------------


def detect_blocked_warrant_path(
    graph,
    kb: KnowledgeBreakdown,
    anchors: dict | None = None,
) -> list[Diagnostic]:
    """A strategy whose premises include unresolved prior holes.

    Walks every strategy and reports it as a blocked warrant path when one or
    more of its premises is a claim listed in ``kb.holes`` (independent claims
    without a recorded prior). Severity is *warning*: the warrant cannot
    propagate confidence until the upstream priors are filled.
    """
    out: list[Diagnostic] = []
    if graph is None:
        return out
    hole_ids = {h.cid for h in kb.holes}
    if not hole_ids:
        return out
    for s in getattr(graph, "strategies", []) or []:
        sid = getattr(s, "id", "") or ""
        label = sid.split("::")[-1] if sid else ""
        premises = list(getattr(s, "premises", None) or [])
        blocking = sorted(p for p in premises if p in hole_ids)
        if not blocking:
            continue
        d = Diagnostic(
            severity="warning",
            kind="blocked_warrant_path",
            target=sid or label,
            label=label,
            message=(f"Strategy `{label}` has unresolved prior holes in its premises: {blocking}."),
            suggested_edit=(
                f"Set priors in priors.py for {blocking} to unblock the warrant "
                f"path leading to `{label}`."
            ),
            data={"blocking_premises": blocking, "strategy": sid},
        )
        out.append(_attach_anchor(d, anchors))
    return out


def detect_focus_unsupported(
    graph,
    focus: FocusBinding | None,
    anchors: dict | None = None,
) -> list[Diagnostic]:
    """Focus claim is not referenced anywhere in the graph.

    A focus is considered supported if it appears as a strategy's conclusion,
    premise, or background, or as an operator's conclusion or variable. When
    no such reference exists, the inquiry tree has no path leading to or from
    the focus, and the agent cannot reason toward it.
    """
    if graph is None or focus is None:
        return []
    fid = focus.resolved_id
    if not fid:
        return []
    for s in getattr(graph, "strategies", []) or []:
        if getattr(s, "conclusion", None) == fid:
            return []
        if fid in (getattr(s, "premises", None) or []):
            return []
        if fid in (getattr(s, "background", None) or []):
            return []
    for o in getattr(graph, "operators", []) or []:
        if getattr(o, "conclusion", None) == fid:
            return []
        if fid in (getattr(o, "variables", None) or []):
            return []
    label = fid.split("::")[-1] if fid else ""
    d = Diagnostic(
        severity="warning",
        kind="focus_unsupported",
        target=fid,
        label=label,
        message=(
            f"Focus `{label}` is not referenced by any strategy or operator; "
            "the inquiry tree has no edges touching it."
        ),
        suggested_edit=(
            f"Add a strategy that concludes `{label}` (or include `{label}` "
            "as a premise/background) so it is wired into the inquiry tree."
        ),
    )
    return [_attach_anchor(d, anchors)]


def detect_large_belief_drop(
    belief_report: dict,
    threshold: float = 0.3,
) -> list[Diagnostic]:
    """Posterior dropped meaningfully relative to the baseline snapshot.

    Reads ``belief_report['largest_decreases']`` (populated only when a
    baseline snapshot was found and inference ran) and emits one diagnostic
    per claim whose ``delta <= -threshold``. Default threshold is conservative
    (0.3) to avoid noise from small numerical fluctuations.
    """
    out: list[Diagnostic] = []
    if not isinstance(belief_report, dict):
        return out
    decreases = belief_report.get("largest_decreases") or []
    for entry in decreases:
        delta = entry.get("delta")
        try:
            d_val = float(delta)
        except (TypeError, ValueError):
            continue
        if d_val > -threshold:
            continue
        label = entry.get("label", "") or ""
        before = entry.get("before")
        after = entry.get("after")
        out.append(
            Diagnostic(
                severity="warning",
                kind="large_belief_drop",
                target=label,
                label=label,
                message=(f"Belief for `{label}` dropped {d_val:+.3f} (from {before} to {after})."),
                suggested_edit=(
                    f"Investigate which evidence or strategy change pushed "
                    f"`{label}` down by {-d_val:.2f}; revise the supporting "
                    "structure or update the baseline if intentional."
                ),
                data={
                    "before": before,
                    "after": after,
                    "delta": d_val,
                    "threshold": threshold,
                },
            )
        )
    return out


def detect_overstrong_strategy_without_provenance(
    graph,
    strength_threshold: float = 0.8,
    anchors: dict | None = None,
) -> list[Diagnostic]:
    """Strategy has neither ``provenance`` nor ``justification`` metadata.

    A strategy must record a non-empty ``provenance`` or ``justification``
    field; otherwise its warrant is unsourced. When the strategy declares a
    ``strength`` (or ``confidence``) at or above ``strength_threshold``,
    severity is *warning* — the agent is leaning on an unjustified strong
    claim. Otherwise severity is *info*.
    """
    out: list[Diagnostic] = []
    if graph is None:
        return out

    def _nonempty(v) -> bool:
        if v is None:
            return False
        if isinstance(v, str):
            return bool(v.strip())
        return True

    for s in getattr(graph, "strategies", []) or []:
        sid = getattr(s, "id", "") or ""
        label = sid.split("::")[-1] if sid else ""
        meta = dict(getattr(s, "metadata", None) or {})
        if _nonempty(meta.get("provenance")) or _nonempty(meta.get("justification")):
            continue

        raw_strength = meta.get("strength", meta.get("confidence"))
        try:
            strength_val = float(raw_strength) if raw_strength is not None else None
        except (TypeError, ValueError):
            strength_val = None

        if strength_val is not None and strength_val >= strength_threshold:
            severity: Severity = "warning"
            message = (
                f"Strategy `{label}` declares strength {strength_val:.2f} "
                "but has no `provenance` or `justification` recorded."
            )
        else:
            severity = "info"
            message = (
                f"Strategy `{label}` has no `provenance` or `justification` "
                "recorded in its metadata."
            )
        data: dict = {"strength_threshold": strength_threshold}
        if strength_val is not None:
            data["strength"] = strength_val
        d = Diagnostic(
            severity=severity,
            kind="overstrong_strategy_without_provenance",
            target=sid or label,
            label=label,
            message=message,
            suggested_edit=(
                f"Update `{label}`.metadata with a non-empty "
                '"provenance" or "justification" field describing why this '
                "warrant is taken to hold."
            ),
            data=data,
        )
        out.append(_attach_anchor(d, anchors))
    return out


def detect_claim_with_evidence_but_no_focus_connection(
    graph,
    focus: FocusBinding | None,
    anchors: dict | None = None,
) -> list[Diagnostic]:
    """Claim cited as background but disconnected from the focus.

    Builds an undirected adjacency over all strategy / operator co-occurrences
    and BFS from the focus claim. A claim that appears only in some strategy's
    ``background`` (i.e. cited as evidence but never as premise or conclusion)
    yet is in a different connected component from the focus is reported.
    Severity is *info* — it is rarely fatal but signals a stranded reference.
    """
    if graph is None or focus is None:
        return []
    fid = focus.resolved_id
    if not fid:
        return []

    from collections import defaultdict, deque

    adj: dict[str, set[str]] = defaultdict(set)

    def _link_clique(nodes: list[str]) -> None:
        nodes = [n for n in nodes if n]
        for i, a in enumerate(nodes):
            for b in nodes[i + 1 :]:
                adj[a].add(b)
                adj[b].add(a)

    for s in getattr(graph, "strategies", []) or []:
        clique: list[str] = []
        if getattr(s, "conclusion", None):
            clique.append(s.conclusion)
        clique.extend(getattr(s, "premises", None) or [])
        clique.extend(getattr(s, "background", None) or [])
        _link_clique(clique)
    for o in getattr(graph, "operators", []) or []:
        clique = []
        if getattr(o, "conclusion", None):
            clique.append(o.conclusion)
        clique.extend(getattr(o, "variables", None) or [])
        _link_clique(clique)

    visited: set[str] = {fid}
    q: deque = deque([fid])
    while q:
        cur = q.popleft()
        for nb in adj.get(cur, ()):
            if nb not in visited:
                visited.add(nb)
                q.append(nb)

    in_core: set[str] = set()
    in_bg: set[str] = set()
    for s in getattr(graph, "strategies", []) or []:
        if getattr(s, "conclusion", None):
            in_core.add(s.conclusion)
        for p in getattr(s, "premises", None) or []:
            in_core.add(p)
        for b in getattr(s, "background", None) or []:
            in_bg.add(b)
    bg_only = in_bg - in_core

    out: list[Diagnostic] = []
    focus_label = fid.split("::")[-1] if fid else ""
    for k in getattr(graph, "knowledges", []) or []:
        kid = getattr(k, "id", "")
        if kid not in bg_only or kid in visited:
            continue
        label = getattr(k, "label", "") or (kid.split("::")[-1] if kid else "")
        d = Diagnostic(
            severity="info",
            kind="claim_with_evidence_but_no_focus_connection",
            target=kid,
            label=label,
            message=(
                f"Claim `{label}` is cited as background evidence but is in a "
                f"different connected component than focus `{focus_label}`."
            ),
            suggested_edit=(
                f"Either connect `{label}` into a strategy that touches the "
                f"focus subgraph, or remove the dangling background reference."
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
