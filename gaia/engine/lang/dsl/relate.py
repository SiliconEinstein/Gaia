"""Gaia Lang v6 structural relation verbs: equal, contradict, exclusive."""

from __future__ import annotations

from gaia.engine.lang.runtime.action import (
    Contradict,
    Equal,
    Exclusive,
    attach_reasoning,
    validate_no_self_warrant,
)
from gaia.engine.lang.runtime.knowledge import Claim, Knowledge


def _claim_ref(claim: Claim) -> str:
    """Return a short reference to *claim* for use inside synthesized sentences.

    When the claim has a label we use the ``[@label]`` form; otherwise we
    fall back to the raw content string. A single trailing period is stripped
    so that splicing the reference into a larger sentence does not produce
    doubled-punctuation like ``"exactly one of God exists. and … is true."``.
    """
    if claim.label:
        return f"[@{claim.label}]"
    content = claim.content
    if content.endswith("."):
        content = content[:-1]
    return content


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
    validate_no_self_warrant(action, helper)
    attach_reasoning(helper, action)
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
    validate_no_self_warrant(action, helper)
    attach_reasoning(helper, action)
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
    validate_no_self_warrant(action, helper)
    attach_reasoning(helper, action)
    return helper
