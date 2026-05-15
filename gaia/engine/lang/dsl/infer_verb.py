"""Gaia Lang v6 Infer verb."""

from __future__ import annotations

import warnings
from typing import Any, cast

from gaia.engine.lang.runtime.action import Infer as InferAction
from gaia.engine.lang.runtime.knowledge import Claim, Knowledge
from gaia.engine.lang.runtime.nodes import Strategy


def _claim_ref(claim: Claim) -> str:
    # infer() returns the evidence Claim, so callers may relabel it after the
    # action is created. Keep helper display text independent of mutable labels;
    # structured references live in relation metadata.
    return claim.content


def _as_given_tuple(given: Claim | tuple[Claim, ...] | list[Claim] | None) -> tuple[Claim, ...]:
    if given is None:
        return ()
    if isinstance(given, Knowledge):
        return (given,)
    return tuple(given)


def _legacy_infer(
    premises: list[Knowledge] | tuple[Knowledge, ...],
    args: tuple[Any, ...],
    legacy_kwargs: dict[str, Any],
) -> Strategy:
    from gaia.engine.lang.dsl.strategies import infer as legacy_infer

    warnings.warn(
        "infer([premises], conclusion, ...) is deprecated; use "
        "infer(evidence, hypothesis=..., p_e_given_h=..., "
        "p_e_given_not_h=...) instead",
        DeprecationWarning,
        stacklevel=2,
    )
    return legacy_infer(list(premises), *args, **legacy_kwargs)


def _resolve_evidence(evidence: Claim | str | None) -> Claim | str | None:
    if isinstance(evidence, (list, tuple)):
        raise TypeError("legacy infer form must be handled before evidence resolution")
    return evidence


def _validate_infer_claims(
    *,
    hypothesis: Claim | None,
    evidence: Claim | str | None,
    p_e_given_h: float | Claim | None,
    given: Claim | tuple[Claim, ...] | list[Claim] | None,
) -> tuple[Claim, Claim, tuple[Claim, ...]]:
    if hypothesis is None:
        raise TypeError("infer() missing required keyword argument: 'hypothesis'")
    if evidence is None:
        raise TypeError("infer() missing required keyword argument: 'evidence'")
    if p_e_given_h is None:
        raise TypeError("infer() missing required keyword argument: 'p_e_given_h'")
    if isinstance(evidence, str):
        evidence = Claim(evidence)
    if not isinstance(evidence, Claim):
        raise TypeError("infer() evidence must be a Claim or string")
    if not isinstance(hypothesis, Claim):
        raise TypeError("infer() hypothesis must be a Claim")
    given_tuple = _as_given_tuple(given)
    if any(not isinstance(item, Claim) for item in given_tuple):
        raise TypeError("infer() given entries must be Claims")
    return evidence, hypothesis, given_tuple


def _infer_relation(
    *,
    hypothesis: Claim,
    evidence: Claim,
    given_tuple: tuple[Claim, ...],
    p_e_given_h: float | Claim | None,
    p_e_given_not_h: float | Claim | None,
) -> dict[str, Any]:
    relation: dict[str, Any] = {
        "type": "infer",
        "hypothesis": hypothesis,
        "evidence": evidence,
        "p_e_given_h": p_e_given_h,
        "p_e_given_not_h": p_e_given_not_h,
    }
    if given_tuple:
        relation["given"] = given_tuple
    return relation


def infer(
    evidence: Claim | str | None = None,
    *args: Any,
    hypothesis: Claim | None = None,
    given: Claim | tuple[Claim, ...] | list[Claim] | None = (),
    background: list[Knowledge] | None = None,
    p_e_given_h: float | Claim | None = None,
    p_e_given_not_h: float | Claim | None = 0.5,
    rationale: str = "",
    label: str | None = None,
    **legacy_kwargs: Any,
) -> Claim | Strategy:
    """Bayesian inference. Returns the evidence Claim.

    The canonical v6 shape is ``infer(evidence, hypothesis=..., ...)``. The old
    v5 ``infer([premises], conclusion, ...)`` form is preserved as a deprecated
    compatibility path.
    """
    legacy_evidence = cast(Any, evidence)
    if isinstance(legacy_evidence, (list, tuple)):
        return _legacy_infer(legacy_evidence, args, legacy_kwargs)

    if args:
        raise TypeError("v6 infer() accepts only one positional evidence argument")
    if legacy_kwargs:
        unexpected = next(iter(legacy_kwargs))
        raise TypeError(f"infer() got an unexpected keyword argument: '{unexpected}'")
    evidence = _resolve_evidence(evidence)
    evidence, hypothesis, given_tuple = _validate_infer_claims(
        hypothesis=hypothesis,
        evidence=evidence,
        p_e_given_h=p_e_given_h,
        given=given,
    )
    assert p_e_given_h is not None
    relation = _infer_relation(
        hypothesis=hypothesis,
        evidence=evidence,
        given_tuple=given_tuple,
        p_e_given_h=p_e_given_h,
        p_e_given_not_h=p_e_given_not_h,
    )
    helper = Claim(
        f"{_claim_ref(evidence)} statistically supports {_claim_ref(hypothesis)}.",
        metadata={
            "generated": True,
            "helper_kind": "likelihood",
            "review": True,
            "relation": relation,
        },
    )
    action = InferAction(
        label=label,
        rationale=rationale,
        background=list(background or []),
        hypothesis=hypothesis,
        evidence=evidence,
        given=given_tuple,
        p_e_given_h=p_e_given_h,
        p_e_given_not_h=p_e_given_not_h,
        helper=helper,
    )
    action.warrants.append(helper)
    evidence.from_actions.append(action)
    return evidence
