"""ProofContext — merged view of IR question()/setting() and synthetic state."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from gaia.inquiry.state import (
    InquiryState,
)


@dataclass
class ObligationView:
    qid: str
    target_qid: str | None
    content: str
    diagnostic_kind: str
    origin: str  # "ir" | "synthetic"
    anchor: dict[str, Any] = field(default_factory=dict)


@dataclass
class HypothesisView:
    qid: str
    content: str
    scope_qid: str | None
    origin: str  # "ir" | "synthetic"


@dataclass
class RejectionView:
    qid: str
    target_strategy: str
    content: str


@dataclass
class ProofContext:
    obligations: list[ObligationView] = field(default_factory=list)
    hypotheses: list[HypothesisView] = field(default_factory=list)
    rejections: list[RejectionView] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "obligations": [asdict(o) for o in self.obligations],
            "hypotheses": [asdict(h) for h in self.hypotheses],
            "rejections": [asdict(r) for r in self.rejections],
        }


def build_proof_context(graph, state: InquiryState) -> ProofContext:
    ctx = ProofContext()

    # IR side — question() becomes obligation view, setting() becomes hypothesis view.
    if graph is not None:
        for k in getattr(graph, "knowledges", []) or []:
            ktype = str(getattr(k, "type", ""))
            qid = getattr(k, "id", None) or getattr(k, "label", None) or ""
            content = getattr(k, "content", "") or ""
            if ktype.endswith("question") or ktype == "question":
                ctx.obligations.append(
                    ObligationView(
                        qid=qid,
                        target_qid=None,
                        content=content,
                        diagnostic_kind="other",
                        origin="ir",
                    )
                )
            elif ktype.endswith("setting") or ktype == "setting":
                ctx.hypotheses.append(
                    HypothesisView(
                        qid=qid,
                        content=content,
                        scope_qid=None,
                        origin="ir",
                    )
                )

    # Synthetic state.
    for o in state.synthetic_obligations:
        ctx.obligations.append(
            ObligationView(
                qid=o.qid,
                target_qid=o.target_qid,
                content=o.content,
                diagnostic_kind=o.diagnostic_kind,
                origin="synthetic",
                anchor=dict(o.anchor),
            )
        )
    for h in state.synthetic_hypotheses:
        ctx.hypotheses.append(
            HypothesisView(
                qid=h.qid,
                content=h.content,
                scope_qid=h.scope_qid,
                origin="synthetic",
            )
        )
    for r in state.synthetic_rejections:
        ctx.rejections.append(
            RejectionView(
                qid=r.qid,
                target_strategy=r.target_strategy,
                content=r.content,
            )
        )
    return ctx
