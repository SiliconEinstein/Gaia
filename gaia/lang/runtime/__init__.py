"""Runtime dataclasses and helpers backing the Gaia Lang DSL."""

from gaia.lang.runtime.action import (
    Action,
    Associate,
    CandidateRelation,
    Compose,
    Compute,
    Contradict,
    Decompose,
    DependsOn,
    Derive,
    Equal,
    Exclusive,
    Infer,
    Observe,
    Probabilistic,
    Scaffold,
    Structural,
    Support,
)
from gaia.lang.runtime.composition import Composition, compose, composition
from gaia.lang.runtime.distribution import Distribution
from gaia.lang.runtime.domain import Domain
from gaia.lang.runtime.knowledge import (
    Claim,
    ClaimKind,
    Context,
    Knowledge,
    Note,
    Question,
    Setting,
)
from gaia.lang.runtime.nodes import Operator, Step, Strategy
from gaia.lang.runtime.roles import (
    RoleOccurrence,
    register_role_handler,
    roles_for_claim,
    roles_for_package,
)
from gaia.lang.runtime.variable import Variable

__all__ = [
    "Action",
    "Associate",
    "CandidateRelation",
    "Claim",
    "ClaimKind",
    "Compose",
    "Composition",
    "Compute",
    "Context",
    "Contradict",
    "Decompose",
    "DependsOn",
    "Derive",
    "Distribution",
    "Domain",
    "Equal",
    "Exclusive",
    "Infer",
    "Knowledge",
    "Note",
    "Observe",
    "Operator",
    "Probabilistic",
    "Question",
    "RoleOccurrence",
    "Scaffold",
    "Setting",
    "Step",
    "Strategy",
    "Structural",
    "Support",
    "Variable",
    "compose",
    "composition",
    "register_role_handler",
    "roles_for_claim",
    "roles_for_package",
]
