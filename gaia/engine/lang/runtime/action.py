"""Gaia Lang v6 Action class hierarchy."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable

    from gaia.engine.lang.runtime.knowledge import Claim, Knowledge
    from gaia.engine.lang.runtime.package import CollectedPackage


@dataclass
class GaiaGraph:
    """Base Gaia authoring graph record. Parallel to Knowledge, not a Knowledge subclass."""

    label: str | None = None
    rationale: str = ""
    background: list[Knowledge] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    _package: CollectedPackage | None = field(default=None, init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        """Register the graph record with the active or inferred package."""
        from gaia.engine.lang.runtime.knowledge import _current_package

        pkg = _current_package.get()
        if pkg is None:
            from gaia.engine.lang.runtime.package import infer_package_from_callstack

            pkg = infer_package_from_callstack()
        if pkg is not None:
            self._package = pkg
            pkg._register_action(self)


@dataclass
class Reasoning(GaiaGraph):
    """Reviewable reasoning record that can carry warrant Claims."""

    warrants: list[Claim] = field(default_factory=list)


# Compatibility alias for the pre-Reasoning public name. New code should use
# Reasoning; the alias remains while downstream packages migrate labels/types.
Action = Reasoning


def attach_reasoning(claim: Claim, reasoning: Reasoning) -> None:
    """Attach a reasoning record to a claim's reverse index exactly once."""
    if all(existing is not reasoning for existing in claim.from_actions):
        claim.from_actions.append(reasoning)


def validate_no_self_warrant(reasoning: Reasoning, primary: Claim) -> None:
    """Reject reasoning records whose primary claim/helper is also their warrant."""
    if any(warrant is primary for warrant in reasoning.warrants):
        raise ValueError("reasoning primary claim/helper must not also be its warrant")


@dataclass
class Directed(Reasoning):
    """Directed reasoning shape: sources or premises point toward a target."""


@dataclass
class Relation(Reasoning):
    """Symmetric or non-directed relation among Claims."""


@dataclass
class Support(Directed):
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
class Scaffold(GaiaGraph):
    """Formalization workflow record. Does not enter IR/BP as a warrant."""


@dataclass
class DependsOn(Scaffold):
    """Marks unformalized dependencies for a conclusion."""

    conclusion: Claim | None = None
    given: tuple[Claim, ...] = ()


@dataclass
class CandidateRelation(Scaffold):
    """Marks a hypothesized relation that has not been formalized yet."""

    claims: tuple[Claim, ...] = ()
    pattern: str | None = None
    status: str = "hypothesis"

    @property
    def a(self) -> Claim | None:
        """Compatibility view for older binary callers."""
        return self.claims[0] if len(self.claims) >= 1 else None

    @property
    def b(self) -> Claim | None:
        """Compatibility view for older binary callers."""
        return self.claims[1] if len(self.claims) >= 2 else None

    @property
    def proposed(self) -> str | None:
        """Compatibility view for older proposed-pattern callers."""
        return self.pattern


@dataclass
class MaterializationLink:
    """Bookkeeping link from scaffold to the formal graph records that handle it."""

    scaffold: Scaffold
    by: tuple[GaiaGraph, ...]
    label: str | None = None
    rationale: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Structural(Relation):
    """Hard structural constraint between claims or claim formulas."""


@dataclass
class Equal(Structural):
    """Declares two Claims equivalent."""

    a: Claim | None = None
    b: Claim | None = None
    helper: Claim | None = None


@dataclass
class Contradict(Structural):
    """Declares two Claims contradictory."""

    a: Claim | None = None
    b: Claim | None = None
    helper: Claim | None = None


@dataclass
class Exclusive(Structural):
    """Declares two Claims form a closed binary partition."""

    a: Claim | None = None
    b: Claim | None = None
    helper: Claim | None = None


@dataclass
class Decompose(Reasoning):
    """Declares a whole Claim equivalent to a formula over atomic Claims."""

    whole: Claim | None = None
    parts: tuple[Claim, ...] = ()
    formula: Any = None


@dataclass
class Infer(Directed):
    """Bayesian inference: P(E|H) update."""

    helper: Claim | None = None
    hypothesis: Claim | None = None
    evidence: Claim | None = None
    given: tuple[Claim, ...] = ()
    p_e_given_h: float | Claim = 0.5
    p_e_given_not_h: float | Claim | None = 0.5


@dataclass
class Associate(Relation):
    """Symmetric probabilistic association between two Claims."""

    helper: Claim | None = None
    a: Claim | None = None
    b: Claim | None = None
    p_a_given_b: float = 0.5
    p_b_given_a: float = 0.5
    pattern: str | None = None


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
        """Hash the canonical compose payload used for the IR compose ID."""
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
