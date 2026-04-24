"""Gaia Lang v6 Relate verbs: equal, contradict, exclusive."""

from __future__ import annotations

from gaia.lang.runtime.action import Contradict, Equal, Exclusive
from gaia.lang.runtime.knowledge import Claim, Knowledge


def _claim_ref(claim: Claim) -> str:
    if claim.label:
        return f"[@{claim.label}]"
    return claim.content


def equal(
    a: Claim,
    b: Claim,
    *,
    background: list[Knowledge] | None = None,
    rationale: str = "",
    label: str | None = None,
) -> Claim:
    """Declare two Claims equivalent. Returns an equivalence helper Claim."""
    helper = Claim(
        f"{_claim_ref(a)} and {_claim_ref(b)} are equivalent.",
        metadata={"generated": True, "helper_kind": "equivalence_result", "review": True},
    )
    action = Equal(
        label=label,
        rationale=rationale,
        background=list(background or []),
        a=a,
        b=b,
        helper=helper,
    )
    action.warrants.append(helper)
    return helper


def contradict(
    a: Claim,
    b: Claim,
    *,
    background: list[Knowledge] | None = None,
    rationale: str = "",
    label: str | None = None,
) -> Claim:
    """Declare two Claims contradictory. Returns a contradiction helper Claim."""
    helper = Claim(
        f"{_claim_ref(a)} and {_claim_ref(b)} contradict.",
        metadata={"generated": True, "helper_kind": "contradiction_result", "review": True},
    )
    action = Contradict(
        label=label,
        rationale=rationale,
        background=list(background or []),
        a=a,
        b=b,
        helper=helper,
    )
    action.warrants.append(helper)
    return helper


def exclusive(
    a: Claim,
    b: Claim,
    *,
    background: list[Knowledge] | None = None,
    rationale: str = "",
    label: str | None = None,
) -> Claim:
    """Declare two Claims as a closed binary partition. Returns an XOR helper Claim."""
    helper = Claim(
        f"exactly one of {_claim_ref(a)} and {_claim_ref(b)} is true.",
        metadata={"generated": True, "helper_kind": "complement_result", "review": True},
    )
    action = Exclusive(
        label=label,
        rationale=rationale,
        background=list(background or []),
        a=a,
        b=b,
        helper=helper,
    )
    action.warrants.append(helper)
    return helper
