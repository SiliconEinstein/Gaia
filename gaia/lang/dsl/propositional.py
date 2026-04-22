"""Gaia Lang v6 propositional expression helpers."""

from __future__ import annotations

from gaia.lang.runtime.knowledge import Claim
from gaia.lang.runtime.nodes import Operator


def _claim_ref(claim: Claim) -> str:
    if claim.label:
        return f"[@{claim.label}]"
    return claim.content


def _expression_helper(content: str, helper_kind: str) -> Claim:
    return Claim(
        content,
        metadata={"generated": True, "helper_kind": helper_kind, "review": False},
    )


def _validate_claims(claims: tuple[Claim, ...], function_name: str) -> None:
    for claim in claims:
        if not isinstance(claim, Claim):
            raise TypeError(f"{function_name}() arguments must be Claim objects")


def not_(claim: Claim) -> Claim:
    """Construct the Boolean negation expression ``not claim``."""
    _validate_claims((claim,), "not_")
    helper = _expression_helper(f"not({_claim_ref(claim)})", "negation_result")
    Operator(operator="negation", variables=[claim], conclusion=helper)
    return helper


def and_(*claims: Claim) -> Claim:
    """Construct a Boolean conjunction expression over two or more Claims."""
    if len(claims) < 2:
        raise ValueError("and_() requires at least two claims")
    _validate_claims(claims, "and_")
    labels = ", ".join(_claim_ref(claim) for claim in claims)
    helper = _expression_helper(f"all_true({labels})", "conjunction_result")
    Operator(operator="conjunction", variables=list(claims), conclusion=helper)
    return helper


def or_(*claims: Claim) -> Claim:
    """Construct a Boolean disjunction expression over two or more Claims."""
    if len(claims) < 2:
        raise ValueError("or_() requires at least two claims")
    _validate_claims(claims, "or_")
    labels = ", ".join(_claim_ref(claim) for claim in claims)
    helper = _expression_helper(f"any_true({labels})", "disjunction_result")
    Operator(operator="disjunction", variables=list(claims), conclusion=helper)
    return helper
