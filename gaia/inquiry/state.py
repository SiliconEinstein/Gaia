"""Inquiry state — Lean-ProofState-style reasoning process state.

This module owns the only mutable artifact of gaia.inquiry: .gaia/inquiry/state.json
plus an append-only tactic log at .gaia/inquiry/tactics.jsonl.

Per spec §2 Non-Goals, none of this touches .py source / IR / priors / beliefs.
The dataclasses here mirror a Lean proof state:
  - focus + focus_stack  ≈ goal stack
  - synthetic_obligations ≈ unresolved goals that the agent wants to track
                            separately from IR-level question()
  - synthetic_hypotheses  ≈ local context / working assumptions (≈ setting())
  - synthetic_rejections  ≈ closed strategy branches
  - tactic log            ≈ append-only audit of inquiry commands
"""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

STATE_SCHEMA_VERSION = 2

VALID_MODES = {"auto", "formalize", "explore", "verify", "publish"}

VALID_OBLIGATION_KINDS = {
    "prior_hole",
    "structural_hole",
    "support_weak",
    "focus_weakness",
    "other",
}


def _utcnow() -> str:
    return datetime.now(tz=timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def mint_qid(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


@dataclass
class SyntheticObligation:
    qid: str
    target_qid: str
    content: str
    diagnostic_kind: str = "other"
    anchor: dict[str, Any] = field(default_factory=dict)
    created_at: str | None = None

    def __post_init__(self) -> None:
        if self.created_at is None:
            self.created_at = _utcnow()
        if self.diagnostic_kind not in VALID_OBLIGATION_KINDS:
            raise ValueError(
                f"invalid obligation kind {self.diagnostic_kind!r}; "
                f"allowed: {sorted(VALID_OBLIGATION_KINDS)}"
            )


@dataclass
class SyntheticHypothesis:
    qid: str
    content: str
    scope_qid: str | None = None
    created_at: str | None = None

    def __post_init__(self) -> None:
        if self.created_at is None:
            self.created_at = _utcnow()


@dataclass
class SyntheticRejection:
    qid: str
    target_strategy: str
    content: str
    created_at: str | None = None

    def __post_init__(self) -> None:
        if self.created_at is None:
            self.created_at = _utcnow()


@dataclass
class InquiryState:
    version: int = STATE_SCHEMA_VERSION
    focus: str | None = None
    focus_kind: str | None = None
    focus_resolved_id: str | None = None
    mode: str = "auto"
    last_review_id: str | None = None
    baseline_review_id: str | None = None
    focus_stack: list[dict[str, Any]] = field(default_factory=list)
    synthetic_obligations: list[SyntheticObligation] = field(default_factory=list)
    synthetic_hypotheses: list[SyntheticHypothesis] = field(default_factory=list)
    synthetic_rejections: list[SyntheticRejection] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "focus": self.focus,
            "focus_kind": self.focus_kind,
            "focus_resolved_id": self.focus_resolved_id,
            "mode": self.mode,
            "last_review_id": self.last_review_id,
            "baseline_review_id": self.baseline_review_id,
            "focus_stack": list(self.focus_stack),
            "synthetic_obligations": [asdict(o) for o in self.synthetic_obligations],
            "synthetic_hypotheses": [asdict(h) for h in self.synthetic_hypotheses],
            "synthetic_rejections": [asdict(r) for r in self.synthetic_rejections],
        }


def inquiry_dir(pkg_path: str | Path) -> Path:
    d = Path(pkg_path).resolve() / ".gaia" / "inquiry"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _state_path(pkg_path: str | Path) -> Path:
    return inquiry_dir(pkg_path) / "state.json"


def _tactics_path(pkg_path: str | Path) -> Path:
    return inquiry_dir(pkg_path) / "tactics.jsonl"


def load_state(pkg_path: str | Path) -> InquiryState:
    p = _state_path(pkg_path)
    if not p.exists():
        return InquiryState()
    raw = json.loads(p.read_text(encoding="utf-8"))
    version = int(raw.get("version", 1))
    if version > STATE_SCHEMA_VERSION:
        raise ValueError(
            f"state.json version {version} is newer than supported {STATE_SCHEMA_VERSION}"
        )
    mode = raw.get("mode", "auto")
    if mode not in VALID_MODES:
        raise ValueError(f"invalid mode {mode!r}; allowed: {sorted(VALID_MODES)}")
    obligations = [SyntheticObligation(**o) for o in raw.get("synthetic_obligations", [])]
    hypotheses = [SyntheticHypothesis(**h) for h in raw.get("synthetic_hypotheses", [])]
    rejections = [SyntheticRejection(**r) for r in raw.get("synthetic_rejections", [])]
    return InquiryState(
        version=STATE_SCHEMA_VERSION,
        focus=raw.get("focus"),
        focus_kind=raw.get("focus_kind"),
        focus_resolved_id=raw.get("focus_resolved_id"),
        mode=mode,
        last_review_id=raw.get("last_review_id"),
        baseline_review_id=raw.get("baseline_review_id"),
        focus_stack=list(raw.get("focus_stack", [])),
        synthetic_obligations=obligations,
        synthetic_hypotheses=hypotheses,
        synthetic_rejections=rejections,
    )


def save_state(pkg_path: str | Path, state: InquiryState) -> None:
    p = _state_path(pkg_path)
    payload = state.to_dict()
    p.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def append_tactic_event(
    pkg_path: str | Path, event: str, payload: dict[str, Any] | None = None
) -> None:
    rec = {
        "timestamp": _utcnow(),
        "event": event,
        "payload": payload or {},
    }
    p = _tactics_path(pkg_path)
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def read_tactic_log(pkg_path: str | Path) -> list[dict[str, Any]]:
    p = _tactics_path(pkg_path)
    if not p.exists():
        return []
    out: list[dict[str, Any]] = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        out.append(json.loads(line))
    return out


def push_focus_frame(state: InquiryState) -> None:
    """Push current focus onto focus_stack. Caller sets the new focus after."""
    frame = {
        "focus": state.focus,
        "focus_kind": state.focus_kind,
        "focus_resolved_id": state.focus_resolved_id,
    }
    state.focus_stack.append(frame)


def pop_focus_frame(state: InquiryState) -> dict[str, Any] | None:
    """Pop the top frame and restore it. Returns old current frame for logging."""
    if not state.focus_stack:
        return None
    old = {
        "focus": state.focus,
        "focus_kind": state.focus_kind,
        "focus_resolved_id": state.focus_resolved_id,
    }
    restored = state.focus_stack.pop()
    state.focus = restored.get("focus")
    state.focus_kind = restored.get("focus_kind")
    state.focus_resolved_id = restored.get("focus_resolved_id")
    return old
