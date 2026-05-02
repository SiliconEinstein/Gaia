"""Focus resolution — look up TARGET against compiled IR and return binding."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class FocusBinding:
    raw: str | None
    resolved_id: str | None = None
    resolved_label: str | None = None
    kind: str = "freeform"

    def to_dict(self) -> dict:
        return {
            "raw": self.raw,
            "resolved_id": self.resolved_id,
            "resolved_label": self.resolved_label,
            "kind": self.kind,
        }


def resolve_focus_target(target: str | None, graph) -> FocusBinding:
    if target is None:
        return FocusBinding(raw=None, kind="none")
    t = str(target).strip()
    if not t:
        return FocusBinding(raw=None, kind="none")

    if graph is None:
        return FocusBinding(raw=t, kind="freeform")

    knowledges = getattr(graph, "knowledges", None) or []
    by_id: dict[str, object] = {}
    by_label: dict[str, object] = {}
    for k in knowledges:
        kid = getattr(k, "id", None)
        klabel = getattr(k, "label", None)
        if kid:
            by_id[kid] = k
        if klabel:
            by_label[klabel] = k

    hit = by_id.get(t) or by_label.get(t)
    if hit is None:
        return FocusBinding(raw=t, kind="freeform")

    ktype = getattr(hit, "type", None)
    kind = "claim"
    if str(ktype).endswith("question") or str(ktype) == "question":
        kind = "question"
    elif str(ktype).endswith("setting") or str(ktype) == "setting":
        kind = "setting"
    return FocusBinding(
        raw=t,
        resolved_id=getattr(hit, "id", None),
        resolved_label=getattr(hit, "label", None),
        kind=kind,
    )
