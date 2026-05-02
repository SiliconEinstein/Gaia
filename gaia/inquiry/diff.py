"""Spec §14 semantic diff — compare current IR against a previous review snapshot.

Implements all 16 categories listed in §14.2:

    added/removed/changed_claims
    added/removed_questions
    added/removed_settings
    added/removed/changed_strategies
    added/removed/changed_operators
    changed_priors
    changed_exports

Identity matching uses stable IR ids (§14.3); labels are kept only for human-
readable display. The diff is report-only — it cannot be applied (Non-Goals §2).
"""

from __future__ import annotations

from dataclasses import dataclass, field


# --------------------------------------------------------------------------- #
# Delta record                                                                #
# --------------------------------------------------------------------------- #


@dataclass
class ClaimDelta:
    """Per-field change record for a knowledge / strategy / operator / prior."""

    label: str
    field: str  # see SemanticDiff field comments for the allowed values
    before: str
    after: str

    def to_dict(self) -> dict:
        return {
            "label": self.label,
            "field": self.field,
            "before": self.before,
            "after": self.after,
        }


# --------------------------------------------------------------------------- #
# SemanticDiff (spec §9.1, §14.2)                                             #
# --------------------------------------------------------------------------- #


@dataclass
class SemanticDiff:
    """Spec §9.1 semantic_diff object — covers all 16 §14.2 categories."""

    baseline_review_id: str | None = None

    # Knowledge — type=claim
    added_claims: list[str] = field(default_factory=list)
    removed_claims: list[str] = field(default_factory=list)
    changed_claims: list[ClaimDelta] = field(default_factory=list)

    # Knowledge — type=question (Non-Goals §2: questions are read-only DSL primitives,
    # they appear only in added/removed because their identity is structural).
    added_questions: list[str] = field(default_factory=list)
    removed_questions: list[str] = field(default_factory=list)

    # Knowledge — type=setting
    added_settings: list[str] = field(default_factory=list)
    removed_settings: list[str] = field(default_factory=list)

    # Strategies (= warrants)
    added_strategies: list[str] = field(default_factory=list)
    removed_strategies: list[str] = field(default_factory=list)
    changed_strategies: list[ClaimDelta] = field(default_factory=list)

    # Operators
    added_operators: list[str] = field(default_factory=list)
    removed_operators: list[str] = field(default_factory=list)
    changed_operators: list[ClaimDelta] = field(default_factory=list)

    # Cross-cutting deltas
    changed_priors: list[ClaimDelta] = field(default_factory=list)
    changed_exports: list[ClaimDelta] = field(default_factory=list)

    @property
    def is_empty(self) -> bool:
        return not any(
            (
                self.added_claims,
                self.removed_claims,
                self.changed_claims,
                self.added_questions,
                self.removed_questions,
                self.added_settings,
                self.removed_settings,
                self.added_strategies,
                self.removed_strategies,
                self.changed_strategies,
                self.added_operators,
                self.removed_operators,
                self.changed_operators,
                self.changed_priors,
                self.changed_exports,
            )
        )

    def to_dict(self) -> dict:
        return {
            "baseline_review_id": self.baseline_review_id,
            "added_claims": list(self.added_claims),
            "removed_claims": list(self.removed_claims),
            "changed_claims": [d.to_dict() for d in self.changed_claims],
            "added_questions": list(self.added_questions),
            "removed_questions": list(self.removed_questions),
            "added_settings": list(self.added_settings),
            "removed_settings": list(self.removed_settings),
            "added_strategies": list(self.added_strategies),
            "removed_strategies": list(self.removed_strategies),
            "changed_strategies": [d.to_dict() for d in self.changed_strategies],
            "added_operators": list(self.added_operators),
            "removed_operators": list(self.removed_operators),
            "changed_operators": [d.to_dict() for d in self.changed_operators],
            "changed_priors": [d.to_dict() for d in self.changed_priors],
            "changed_exports": [d.to_dict() for d in self.changed_exports],
        }


def empty_diff() -> SemanticDiff:
    return SemanticDiff()


# --------------------------------------------------------------------------- #
# Helpers — IR introspection                                                  #
# --------------------------------------------------------------------------- #


def _knowledges_by_type_id(ir: dict, kind: str) -> dict[str, dict]:
    return {k["id"]: k for k in ir.get("knowledges", []) or [] if k.get("type") == kind}


def _strategies_by_id(ir: dict) -> dict[str, dict]:
    return {s["id"]: s for s in ir.get("strategies", []) or []}


def _operators_by_id(ir: dict) -> dict[str, dict]:
    return {o["id"]: o for o in ir.get("operators", []) or []}


def _label(item: dict) -> str:
    return item.get("label") or item.get("id", "").split("::")[-1]


def _prior(k: dict):
    meta = k.get("metadata") or {}
    return meta.get("prior")


def _exported(k: dict) -> bool:
    if "exported" in k:
        return bool(k["exported"])
    meta = k.get("metadata") or {}
    return bool(meta.get("exported", False))


def _fmt(v) -> str:
    return "∅" if v is None else str(v)


# --------------------------------------------------------------------------- #
# Computation                                                                 #
# --------------------------------------------------------------------------- #


def compute_semantic_diff(
    current_ir: dict | None,
    baseline_snapshot: dict | None,
) -> SemanticDiff:
    """Return all 16 §14.2 category deltas between two snapshots."""
    if baseline_snapshot is None or current_ir is None:
        d = SemanticDiff()
        if baseline_snapshot is not None:
            d.baseline_review_id = baseline_snapshot.get("review_id")
        return d

    diff = SemanticDiff(baseline_review_id=baseline_snapshot.get("review_id"))
    base_ir = baseline_snapshot.get("ir") or {}

    _diff_claims(diff, current_ir, base_ir)
    _diff_questions(diff, current_ir, base_ir)
    _diff_settings(diff, current_ir, base_ir)
    _diff_strategies(diff, current_ir, base_ir)
    _diff_operators(diff, current_ir, base_ir)
    return diff


# --------------------------------------------------------------------------- #
# Per-category routines                                                       #
# --------------------------------------------------------------------------- #


def _diff_claims(diff: SemanticDiff, cur: dict, base: dict) -> None:
    """added/removed/changed_claims + changed_priors + changed_exports."""
    cur_c = _knowledges_by_type_id(cur, "claim")
    base_c = _knowledges_by_type_id(base, "claim")

    for cid in sorted(cur_c.keys() - base_c.keys()):
        diff.added_claims.append(_label(cur_c[cid]))
    for cid in sorted(base_c.keys() - cur_c.keys()):
        diff.removed_claims.append(_label(base_c[cid]))

    for cid in sorted(cur_c.keys() & base_c.keys()):
        a, b = base_c[cid], cur_c[cid]
        label = _label(b)

        if (a.get("content") or "") != (b.get("content") or ""):
            diff.changed_claims.append(
                ClaimDelta(label, "content", a.get("content") or "", b.get("content") or "")
            )
        if (a.get("label") or "") != (b.get("label") or ""):
            diff.changed_claims.append(
                ClaimDelta(label, "label", a.get("label") or "", b.get("label") or "")
            )

        pa, pb = _prior(a), _prior(b)
        if pa != pb:
            diff.changed_priors.append(ClaimDelta(label, "prior", _fmt(pa), _fmt(pb)))

        ea, eb = _exported(a), _exported(b)
        if ea != eb:
            diff.changed_exports.append(ClaimDelta(label, "exported", _fmt(ea), _fmt(eb)))


def _diff_questions(diff: SemanticDiff, cur: dict, base: dict) -> None:
    cur_q = _knowledges_by_type_id(cur, "question")
    base_q = _knowledges_by_type_id(base, "question")
    for qid in sorted(cur_q.keys() - base_q.keys()):
        diff.added_questions.append(_label(cur_q[qid]))
    for qid in sorted(base_q.keys() - cur_q.keys()):
        diff.removed_questions.append(_label(base_q[qid]))


def _diff_settings(diff: SemanticDiff, cur: dict, base: dict) -> None:
    cur_s = _knowledges_by_type_id(cur, "setting")
    base_s = _knowledges_by_type_id(base, "setting")
    for sid in sorted(cur_s.keys() - base_s.keys()):
        diff.added_settings.append(_label(cur_s[sid]))
    for sid in sorted(base_s.keys() - cur_s.keys()):
        diff.removed_settings.append(_label(base_s[sid]))


def _diff_strategies(diff: SemanticDiff, cur: dict, base: dict) -> None:
    cur_st = _strategies_by_id(cur)
    base_st = _strategies_by_id(base)
    for sid in sorted(cur_st.keys() - base_st.keys()):
        diff.added_strategies.append(sid.split("::")[-1])
    for sid in sorted(base_st.keys() - cur_st.keys()):
        diff.removed_strategies.append(sid.split("::")[-1])
    for sid in sorted(cur_st.keys() & base_st.keys()):
        a, b = base_st[sid], cur_st[sid]
        label = sid.split("::")[-1]
        if a.get("conclusion") != b.get("conclusion"):
            diff.changed_strategies.append(
                ClaimDelta(
                    label, "conclusion", _fmt(a.get("conclusion")), _fmt(b.get("conclusion"))
                )
            )
        if list(a.get("premises") or []) != list(b.get("premises") or []):
            diff.changed_strategies.append(
                ClaimDelta(
                    label,
                    "premises",
                    ",".join(a.get("premises") or []),
                    ",".join(b.get("premises") or []),
                )
            )


def _diff_operators(diff: SemanticDiff, cur: dict, base: dict) -> None:
    cur_op = _operators_by_id(cur)
    base_op = _operators_by_id(base)
    for oid in sorted(cur_op.keys() - base_op.keys()):
        diff.added_operators.append(oid.split("::")[-1])
    for oid in sorted(base_op.keys() - cur_op.keys()):
        diff.removed_operators.append(oid.split("::")[-1])
    for oid in sorted(cur_op.keys() & base_op.keys()):
        a, b = base_op[oid], cur_op[oid]
        label = oid.split("::")[-1]
        if a.get("conclusion") != b.get("conclusion"):
            diff.changed_operators.append(
                ClaimDelta(
                    label, "conclusion", _fmt(a.get("conclusion")), _fmt(b.get("conclusion"))
                )
            )
        va, vb = list(a.get("variables") or []), list(b.get("variables") or [])
        if va != vb:
            diff.changed_operators.append(
                ClaimDelta(label, "variables", ",".join(va), ",".join(vb))
            )
