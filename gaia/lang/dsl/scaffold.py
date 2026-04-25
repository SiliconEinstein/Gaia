"""Gaia Lang v6 scaffold verbs."""

from __future__ import annotations

from typing import Any

from gaia.lang.runtime.action import DependsOn
from gaia.lang.runtime.knowledge import Claim, Knowledge


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
    conclusion.supports.append(action)
    return conclusion
