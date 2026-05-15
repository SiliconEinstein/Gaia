"""Gaia Lang v6 scaffold verbs."""

from __future__ import annotations

from typing import Any

from gaia.engine.lang.runtime.action import CandidateRelation, DependsOn
from gaia.engine.lang.runtime.knowledge import Claim, Knowledge

_CANDIDATE_RELATION_KINDS = frozenset(
    {
        "equal",
        "contradict",
        "exclusive",
        "associate",
        "tension",
    }
)


def _as_claim_tuple(given: Claim | tuple[Claim, ...] | list[Claim]) -> tuple[Claim, ...]:
    if isinstance(given, Knowledge):
        return (given,)
    return tuple(given)


def depends_on(
    conclusion: Claim,
    *,
    given: Claim | tuple[Claim, ...] | list[Claim],
    background: list[Knowledge] | None = None,
    rationale: str = "",
    label: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> Claim:
    """Record unformalized load-bearing dependencies for a Claim."""
    if not isinstance(conclusion, Claim):
        raise TypeError("depends_on conclusion must be a Claim")
    given_tuple = _as_claim_tuple(given)
    if not given_tuple:
        raise ValueError("depends_on requires at least one given Claim")
    if any(not isinstance(item, Claim) for item in given_tuple):
        raise TypeError("depends_on given entries must be Claims")
    action = DependsOn(
        label=label,
        rationale=rationale,
        background=list(background or []),
        metadata=dict(metadata or {}),
        conclusion=conclusion,
        given=given_tuple,
    )
    conclusion.from_actions.append(action)
    return conclusion


def candidate_relation(
    a: Claim,
    b: Claim,
    *,
    proposed: str,
    background: list[Knowledge] | None = None,
    rationale: str = "",
    label: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> CandidateRelation:
    """Record a hypothesized binary relation without triggering formal semantics."""
    if not isinstance(a, Claim):
        raise TypeError("candidate_relation a must be a Claim")
    if not isinstance(b, Claim):
        raise TypeError("candidate_relation b must be a Claim")
    if proposed not in _CANDIDATE_RELATION_KINDS:
        allowed = ", ".join(sorted(_CANDIDATE_RELATION_KINDS))
        raise ValueError(f"candidate_relation proposed must be one of: {allowed}")
    return CandidateRelation(
        label=label,
        rationale=rationale,
        background=list(background or []),
        metadata=dict(metadata or {}),
        a=a,
        b=b,
        proposed=proposed,
    )


def tension(
    a: Claim,
    b: Claim,
    *,
    background: list[Knowledge] | None = None,
    rationale: str = "",
    label: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> CandidateRelation:
    """Record a hypothesized scientific tension between two Claims."""
    return candidate_relation(
        a,
        b,
        proposed="tension",
        background=background,
        rationale=rationale,
        label=label,
        metadata=metadata,
    )
