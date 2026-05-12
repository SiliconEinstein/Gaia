"""Role projection over authored Gaia Lang actions."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, TypeAlias, cast

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
    Predict,
    Support,
)
from gaia.lang.runtime.knowledge import Claim

if TYPE_CHECKING:
    from gaia.lang.runtime.package import CollectedPackage


@dataclass(frozen=True)
class RoleOccurrence:
    """A claim role at a specific occurrence in an authored action."""

    claim: Claim
    role: str
    action: Action
    action_type: str
    action_label: str | None = None
    path: tuple[str, ...] = ()
    source: str = "explicit_field"


ActionGraph: TypeAlias = "CollectedPackage | Sequence[Action]"
RoleAdder = Callable[[Claim | None, str], None]
RoleHandler = Callable[[Action, RoleAdder], None]

_ROLE_HANDLERS: dict[type[Action], RoleHandler] = {}


def register_role_handler(action_type: type[Action], handler: RoleHandler) -> None:
    """Register role projection for an optional action subclass."""
    if not isinstance(action_type, type) or not issubclass(action_type, Action):
        raise TypeError("action_type must be an Action subclass")
    _ROLE_HANDLERS[action_type] = handler


def roles_for_claim(
    claim: Claim,
    graph: ActionGraph,
    *,
    include_background: bool = True,
    include_warrants: bool = True,
) -> tuple[RoleOccurrence, ...]:
    """Return all authored action roles for ``claim``."""
    return tuple(
        occurrence
        for occurrence in _iter_role_occurrences(
            graph,
            include_background=include_background,
            include_warrants=include_warrants,
        )
        if occurrence.claim is claim
    )


def roles_for_package(
    graph: ActionGraph,
    *,
    include_background: bool = True,
    include_warrants: bool = True,
) -> dict[Claim, tuple[RoleOccurrence, ...]]:
    """Index authored action roles by claim identity."""
    roles: dict[Claim, list[RoleOccurrence]] = defaultdict(list)
    for occurrence in _iter_role_occurrences(
        graph,
        include_background=include_background,
        include_warrants=include_warrants,
    ):
        roles[occurrence.claim].append(occurrence)
    return {claim: tuple(occurrences) for claim, occurrences in roles.items()}


def _graph_actions(graph: ActionGraph) -> Sequence[Action]:
    return tuple(cast(Sequence[Action], getattr(graph, "actions", graph)))


def _iter_role_occurrences(
    graph: ActionGraph,
    *,
    include_background: bool,
    include_warrants: bool,
) -> tuple[RoleOccurrence, ...]:
    occurrences: list[RoleOccurrence] = []
    for action in _graph_actions(graph):
        _collect_action_roles(
            action,
            occurrences,
            path=(),
            include_background=include_background,
            include_warrants=include_warrants,
        )
    return tuple(occurrences)


def _collect_action_roles(
    action: Action,
    occurrences: list[RoleOccurrence],
    *,
    path: tuple[str, ...],
    include_background: bool,
    include_warrants: bool,
) -> None:
    def add(claim: Claim | None, role: str, *, source: str = "explicit_field") -> None:
        if claim is None:
            return
        occurrences.append(
            RoleOccurrence(
                claim=claim,
                role=role,
                action=action,
                action_type=type(action).__name__,
                action_label=action.label,
                path=path,
                source=source,
            )
        )

    for cls in type(action).__mro__:
        handler = _ROLE_HANDLERS.get(cls)
        if handler is not None:
            handler(action, add)
            break

    # Match concrete classes before compatibility base classes.
    if isinstance(action, Observe):
        add(action.conclusion, "observation")
        for given in action.given:
            add(given, "observation_context")
    elif isinstance(action, Compute):
        add(action.conclusion, "computed_result")
        for given in action.given:
            add(given, "compute_input")
    elif isinstance(action, Predict):
        add(action.conclusion, "prediction")
        for given in action.given:
            add(given, "prediction_basis")
    elif isinstance(action, Derive):
        add(action.conclusion, "conclusion")
        for given in action.given:
            add(given, "premise")
    elif isinstance(action, DependsOn):
        add(action.conclusion, "dependency_target")
        for given in action.given:
            add(given, "unformalized_dependency")
    elif isinstance(action, CandidateRelation):
        add(action.a, f"candidate_{action.proposed}_target")
        add(action.b, f"candidate_{action.proposed}_target")
    elif isinstance(action, Infer):
        add(action.hypothesis, "hypothesis")
        add(action.evidence, "evidence")
        for given in action.given:
            add(given, "condition")
        add(action.helper, "likelihood_helper")
        if isinstance(action.p_e_given_h, Claim):
            add(action.p_e_given_h, "likelihood_parameter")
        if isinstance(action.p_e_given_not_h, Claim):
            add(action.p_e_given_not_h, "likelihood_parameter")
    elif isinstance(action, Associate):
        add(action.a, "association_target")
        add(action.b, "association_target")
        add(action.helper, "association_helper")
    elif isinstance(action, Equal):
        add(action.a, "equivalent_claim")
        add(action.b, "equivalent_claim")
        add(action.helper, "equivalence_helper")
    elif isinstance(action, Contradict):
        add(action.a, "contradiction_target")
        add(action.b, "contradiction_target")
        add(action.helper, "contradiction_helper")
    elif isinstance(action, Exclusive):
        add(action.a, "exclusive_alternative")
        add(action.b, "exclusive_alternative")
        add(action.helper, "exclusivity_helper")
    elif isinstance(action, Decompose):
        add(action.whole, "decomposition_whole")
        for part in action.parts:
            add(part, "decomposition_part")
    elif isinstance(action, Compose):
        for item in action.inputs:
            if isinstance(item, Claim):
                add(item, "composition_input")
        add(action.conclusion, "composition_conclusion")
        for index, child in enumerate(action.actions):
            if isinstance(child, Action):
                child_label = child.label or f"action_{index}"
                _collect_action_roles(
                    child,
                    occurrences,
                    path=(*path, child_label),
                    include_background=include_background,
                    include_warrants=include_warrants,
                )
    elif isinstance(action, Support):
        add(action.conclusion, "conclusion")
        for given in action.given:
            add(given, "premise")

    if include_background:
        for background in action.background:
            if isinstance(background, Claim):
                add(background, "background", source="background")
    if include_warrants:
        for warrant in action.warrants:
            add(warrant, "warrant", source="warrant")
