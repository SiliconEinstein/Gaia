"""Gaia Lang v6 Action class hierarchy."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable

    from gaia.lang.runtime.knowledge import Claim, Knowledge


@dataclass
class Action:
    """Base reasoning action. Parallel to Knowledge, not a Knowledge subclass."""

    label: str | None = None
    rationale: str = ""
    background: list[Knowledge] = field(default_factory=list)
    warrants: list[Claim] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        from gaia.lang.runtime.knowledge import _current_package

        pkg = _current_package.get()
        if pkg is None:
            from gaia.lang.runtime.package import infer_package_from_callstack

            pkg = infer_package_from_callstack()
        if pkg is not None:
            pkg._register_action(self)


@dataclass
class Support(Action):
    """Directional reasoning: given -> conclusion."""

    conclusion: Claim | None = None
    given: tuple[Claim, ...] = ()


@dataclass
class Derive(Support):
    """Logical derivation."""


@dataclass
class Observe(Support):
    """Empirical observation or measurement."""


@dataclass
class Compute(Support):
    """Deterministic code execution."""

    fn: Callable[..., Any] | None = None
    code_hash: str | None = None


@dataclass
class Scaffold(Action):
    """Formalization workflow record. Does not enter IR/BP as a warrant."""


@dataclass
class DependsOn(Scaffold):
    """Marks unformalized dependencies for a conclusion."""

    conclusion: Claim | None = None
    given: tuple[Claim, ...] = ()


@dataclass
class Relate(Action):
    """Logical constraint between two Claims."""

    a: Claim | None = None
    b: Claim | None = None
    helper: Claim | None = None


@dataclass
class Equal(Relate):
    """Declares two Claims equivalent."""


@dataclass
class Contradict(Relate):
    """Declares two Claims contradictory."""


@dataclass
class Exclusive(Relate):
    """Declares two Claims form a closed binary partition."""


@dataclass
class Correlate(Action):
    """Probabilistic soft constraint between Claims."""

    helper: Claim | None = None


@dataclass
class Infer(Correlate):
    """Bayesian inference: P(E|H) update."""

    hypothesis: Claim | None = None
    evidence: Claim | None = None
    p_e_given_h: float | Claim = 0.5
    p_e_given_not_h: float | Claim = 0.5
    prior_hypothesis: float | None = None
    prior_evidence: float | None = None


@dataclass
class Associate(Correlate):
    """Symmetric probabilistic association between two Claims."""

    a: Claim | None = None
    b: Claim | None = None
    p_a_given_b: float = 0.5
    p_b_given_a: float = 0.5
    prior_a: float | None = None
    prior_b: float | None = None


@dataclass
class Compose(Action):
    """Action-level composition of child actions into a reviewable DAG."""

    name: str = ""
    version: str = ""
    inputs: tuple[Knowledge | str, ...] = ()
    actions: tuple[Action | str, ...] = ()
    conclusion: Claim | None = None

    def structure_hash(
        self,
        input_refs: list[str],
        action_refs: list[str],
        conclusion_ref: str,
        warrant_refs: list[str],
        background_refs: list[str] | None = None,
    ) -> str:
        payload = {
            "name": self.name,
            "version": self.version,
            "inputs": sorted(input_refs),
            "background": sorted(background_refs or []),
            "actions": list(action_refs),
            "conclusion": conclusion_ref,
            "warrants": sorted(warrant_refs),
        }
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode()).hexdigest()[:16]
