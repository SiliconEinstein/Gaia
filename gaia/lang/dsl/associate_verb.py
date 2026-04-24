"""Gaia Lang v6 Associate verb."""

from __future__ import annotations

from gaia.lang.runtime.action import Associate as AssociateAction
from gaia.lang.runtime.knowledge import Claim, Knowledge


def _claim_ref(claim: Claim) -> str:
    if claim.label:
        return f"[@{claim.label}]"
    return claim.content


def associate(
    a: Claim,
    b: Claim,
    *,
    p_a_given_b: float,
    p_b_given_a: float,
    prior_a: float | None = None,
    prior_b: float | None = None,
    background: list[Knowledge] | None = None,
    rationale: str = "",
    label: str | None = None,
) -> Claim:
    """Declare a symmetric probabilistic association. Returns an association helper Claim."""
    if not isinstance(a, Claim):
        raise TypeError("associate() a must be a Claim")
    if not isinstance(b, Claim):
        raise TypeError("associate() b must be a Claim")

    helper = Claim(
        f"{_claim_ref(a)} and {_claim_ref(b)} are statistically associated.",
        metadata={
            "generated": True,
            "helper_kind": "association",
            "review": True,
            "relation": {
                "type": "associate",
                "a": a,
                "b": b,
                "p_a_given_b": p_a_given_b,
                "p_b_given_a": p_b_given_a,
                "prior_a": prior_a,
                "prior_b": prior_b,
            },
        },
    )
    action = AssociateAction(
        label=label,
        rationale=rationale,
        background=list(background or []),
        a=a,
        b=b,
        p_a_given_b=p_a_given_b,
        p_b_given_a=p_b_given_a,
        prior_a=prior_a,
        prior_b=prior_b,
        helper=helper,
    )
    action.warrants.append(helper)
    return helper
