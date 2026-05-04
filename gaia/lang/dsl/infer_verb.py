"""Gaia Lang v6 Infer verb."""

from __future__ import annotations

import warnings

from gaia.lang.runtime.action import Infer as InferAction
from gaia.lang.runtime.knowledge import Claim, Knowledge


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


def infer(
    evidence_or_legacy=None,
    *args,
    hypothesis: Claim | None = None,
    evidence: Claim | str | None = None,
    given: Claim | tuple[Claim, ...] | list[Claim] | None = (),
    background: list[Knowledge] | None = None,
    p_e_given_h: float | Claim | None = None,
    p_e_given_not_h: float | Claim | None = 0.5,
    prior_hypothesis: float | None = None,
    prior_evidence: float | None = None,
    rationale: str = "",
    label: str | None = None,
    **legacy_kwargs,
) -> Claim:
    """Bayesian inference. Returns the evidence Claim.

    The canonical v6 shape is ``infer(evidence, hypothesis=..., ...)``. The old
    v5 ``infer([premises], conclusion, ...)`` form is preserved as a deprecated
    compatibility path.
    """
    if isinstance(evidence_or_legacy, (list, tuple)):
        from gaia.lang.dsl.strategies import infer as legacy_infer

        warnings.warn(
            "infer([premises], conclusion, ...) is deprecated; use "
            "infer(evidence, hypothesis=..., p_e_given_h=..., "
            "p_e_given_not_h=...) instead",
            DeprecationWarning,
            stacklevel=2,
        )
        return legacy_infer(evidence_or_legacy, *args, **legacy_kwargs)

    if args:
        raise TypeError("v6 infer() accepts only one positional evidence argument")
    if legacy_kwargs:
        unexpected = next(iter(legacy_kwargs))
        raise TypeError(f"infer() got an unexpected keyword argument: '{unexpected}'")
    if evidence_or_legacy is not None:
        if evidence is not None:
            raise TypeError("infer() got evidence both positionally and by keyword")
        evidence = evidence_or_legacy

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

    relation = {
        "type": "infer",
        "hypothesis": hypothesis,
        "evidence": evidence,
        "p_e_given_h": p_e_given_h,
        "p_e_given_not_h": p_e_given_not_h,
        "prior_hypothesis": prior_hypothesis,
        "prior_evidence": prior_evidence,
    }
    if given_tuple:
        relation["given"] = given_tuple
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
        prior_hypothesis=prior_hypothesis,
        prior_evidence=prior_evidence,
        helper=helper,
    )
    action.warrants.append(helper)
    evidence.supports.append(action)
    return evidence
