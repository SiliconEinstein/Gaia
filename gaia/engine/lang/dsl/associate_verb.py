"""Gaia Lang v6 Associate verb."""

from __future__ import annotations

from typing import Any

from gaia.engine.lang.dsl._lift import _lift_to_claim
from gaia.engine.lang.runtime.action import (
    Associate as AssociateAction,
)
from gaia.engine.lang.runtime.action import attach_reasoning, validate_no_self_warrant
from gaia.engine.lang.runtime.knowledge import Claim, Knowledge

_ASSOCIATE_PATTERNS = frozenset({"equal", "contradict", "exclusive"})


def _claim_ref(claim: Claim) -> str:
    if claim.label:
        return f"[@{claim.label}]"
    return claim.content


def associate(
    a: Any,
    b: Any,
    *,
    p_a_given_b: float,
    p_b_given_a: float,
    pattern: str | None = None,
    background: list[Knowledge] | None = None,
    rationale: str = "",
    label: str | None = None,
) -> Claim:
    """Declare a symmetric probabilistic association. Returns an association helper Claim.

    ``a`` and ``b`` may be any Boolean-valued expression (``Claim``,
    ``ClaimAtom``, Formula node, or ``BoolExpr``); non-``Claim`` inputs are
    lifted to helper Claims at the verb boundary per RFC #703.
    """
    a = _lift_to_claim(a, verb="associate", position="first argument")
    b = _lift_to_claim(b, verb="associate", position="second argument")
    _validate_pattern(pattern, p_a_given_b=p_a_given_b, p_b_given_a=p_b_given_a)

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
                "pattern": pattern,
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
        pattern=pattern,
        helper=helper,
    )
    validate_no_self_warrant(action, helper)
    attach_reasoning(helper, action)
    return helper


def _validate_pattern(
    pattern: str | None,
    *,
    p_a_given_b: float,
    p_b_given_a: float,
) -> None:
    if pattern is None:
        return
    if pattern not in _ASSOCIATE_PATTERNS:
        allowed = ", ".join(sorted(_ASSOCIATE_PATTERNS))
        raise ValueError(f"associate pattern must be one of: {allowed}")
    if pattern == "equal" and not (p_a_given_b > 0.5 and p_b_given_a > 0.5):
        raise ValueError(
            "associate(pattern='equal') requires p_a_given_b > 0.5 and p_b_given_a > "
            "0.5. If the conditional is not informative, drop the pattern argument."
        )
    if pattern in {"contradict", "exclusive"} and not (p_a_given_b < 0.5 and p_b_given_a < 0.5):
        raise ValueError(
            f"associate(pattern='{pattern}') requires p_a_given_b < 0.5 and p_b_given_a "
            "< 0.5. If the conditional is not informative, drop the pattern argument."
        )
