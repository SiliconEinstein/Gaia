"""Gaia Lang v6 Action class hierarchy."""

from __future__ import annotations

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
class Infer(Action):
    """Bayesian inference: P(E|H) update."""

    hypothesis: Claim | None = None
    evidence: Claim | None = None
    p_e_given_h: float = 0.5
    p_e_given_not_h: float = 0.5
    helper: Claim | None = None
