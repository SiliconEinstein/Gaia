"""Extension lowering hooks for Gaia Lang compilation."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field, replace
from typing import Any

from gaia.engine.ir import Knowledge as IrKnowledge
from gaia.engine.ir import Operator as IrOperator
from gaia.engine.ir import Strategy as IrStrategy

ActionPredicate = Callable[[Any], bool]


@dataclass(frozen=True)
class ActionLoweringContext:
    """Inputs shared with registered action lowerers."""

    knowledge_nodes: list[Any]
    actions: tuple[Any, ...]
    namespace: str
    package_name: str
    knowledge_map: dict[int, str]
    action_labels_by_object: dict[int, str]
    existing_operators: list[IrOperator]


@dataclass
class ActionLoweringResult:
    """IR additions and action-target mappings emitted by extension lowerers."""

    knowledges: list[IrKnowledge] = field(default_factory=list)
    operators: list[IrOperator] = field(default_factory=list)
    strategies: list[IrStrategy] = field(default_factory=list)
    metadata_updates: dict[str, dict[str, Any]] = field(default_factory=dict)
    action_label_map: dict[str, str] = field(default_factory=dict)
    target_action_labels_by_id: dict[str, str] = field(default_factory=dict)
    action_target_ids_by_object: dict[int, str] = field(default_factory=dict)


ActionLowerer = Callable[[ActionLoweringContext], ActionLoweringResult]


@dataclass(frozen=True)
class RegisteredActionLowerer:
    """Registered compiler extension for one family of runtime actions."""

    name: str
    handles: ActionPredicate
    lower: ActionLowerer


_ACTION_LOWERERS: dict[str, RegisteredActionLowerer] = {}


def register_action_lowerer(
    name: str,
    *,
    handles: ActionPredicate,
    lower: ActionLowerer,
) -> None:
    """Register an extension lowerer by stable name."""
    if not name:
        raise ValueError("action lowerer name must not be empty")
    _ACTION_LOWERERS[name] = RegisteredActionLowerer(name=name, handles=handles, lower=lower)


def registered_action_lowerers() -> tuple[RegisteredActionLowerer, ...]:
    """Return registered action lowerers in registration order."""
    return tuple(_ACTION_LOWERERS.values())


def is_registered_action(action: Any) -> bool:
    """Return whether any registered lowerer owns this action."""
    return any(lowerer.handles(action) for lowerer in _ACTION_LOWERERS.values())


def lower_registered_actions(context: ActionLoweringContext) -> ActionLoweringResult:
    """Run registered action lowerers and merge their IR additions."""
    combined = ActionLoweringResult()
    existing_operators = list(context.existing_operators)
    for lowerer in _ACTION_LOWERERS.values():
        if not any(lowerer.handles(action) for action in context.actions):
            continue
        scoped_context = replace(context, existing_operators=list(existing_operators))
        result = lowerer.lower(scoped_context)
        _merge_result(combined, result, context=context, lowerer=lowerer)
        existing_operators.extend(result.operators)
    return combined


def _merge_result(
    combined: ActionLoweringResult,
    result: ActionLoweringResult,
    *,
    context: ActionLoweringContext,
    lowerer: RegisteredActionLowerer,
) -> None:
    combined.knowledges.extend(result.knowledges)
    combined.operators.extend(result.operators)
    combined.strategies.extend(result.strategies)
    combined.metadata_updates.update(result.metadata_updates)
    _merge_action_labels(combined, result, lowerer=lowerer)
    combined.action_target_ids_by_object.update(result.action_target_ids_by_object)
    _record_owned_action_targets(combined, result, context=context, lowerer=lowerer)


def _merge_action_labels(
    combined: ActionLoweringResult,
    result: ActionLoweringResult,
    *,
    lowerer: RegisteredActionLowerer,
) -> None:
    for action_label, target_id in result.action_label_map.items():
        existing = combined.action_label_map.get(action_label)
        if existing is not None and existing != target_id:
            raise ValueError(
                f"extension lowerer {lowerer.name!r} changed action label "
                f"{action_label!r} target from {existing!r} to {target_id!r}"
            )
        combined.action_label_map[action_label] = target_id
    combined.target_action_labels_by_id.update(result.target_action_labels_by_id)


def _record_owned_action_targets(
    combined: ActionLoweringResult,
    result: ActionLoweringResult,
    *,
    context: ActionLoweringContext,
    lowerer: RegisteredActionLowerer,
) -> None:
    for action in context.actions:
        if not lowerer.handles(action):
            continue
        action_label = context.action_labels_by_object.get(id(action))
        if action_label is None:
            continue
        target_id = result.action_label_map.get(action_label)
        if target_id is not None:
            combined.action_target_ids_by_object[id(action)] = target_id
