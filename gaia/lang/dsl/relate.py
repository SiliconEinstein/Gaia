"""Gaia Lang v6 Relate verbs: equal, contradict."""

from __future__ import annotations

from gaia.lang.runtime.action import Contradict, Equal
from gaia.lang.runtime.knowledge import Claim


def _claim_ref(claim: Claim) -> str:
    if claim.label:
        return f"[@{claim.label}]"
    return claim.content


def equal(a: Claim, b: Claim, *, rationale: str = "", label: str | None = None) -> Claim:
    """Declare two Claims equivalent. Returns an equivalence helper Claim."""
    helper = Claim(
        f"{_claim_ref(a)} and {_claim_ref(b)} are equivalent.",
        metadata={"generated": True, "helper_kind": "equivalence_result", "review": True},
    )
    action = Equal(label=label, rationale=rationale, a=a, b=b, helper=helper)
    action.warrants.append(helper)
    return helper


def contradict(a: Claim, b: Claim, *, rationale: str = "", label: str | None = None) -> Claim:
    """Declare two Claims contradictory. Returns a contradiction helper Claim."""
    helper = Claim(
        f"{_claim_ref(a)} and {_claim_ref(b)} contradict.",
        metadata={"generated": True, "helper_kind": "contradiction_result", "review": True},
    )
    action = Contradict(label=label, rationale=rationale, a=a, b=b, helper=helper)
    action.warrants.append(helper)
    return helper
