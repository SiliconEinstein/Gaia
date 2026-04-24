"""Runtime support for Gaia action composition templates."""

from __future__ import annotations

from collections.abc import Iterable
from contextvars import ContextVar
from dataclasses import dataclass, field
from functools import wraps
from typing import Any

from gaia.lang.runtime.action import (
    Action,
    Associate,
    Compose,
    Infer,
    Relate,
    Support,
)
from gaia.lang.runtime.knowledge import Claim, Knowledge


@dataclass
class _CompositionScope:
    name: str
    version: str
    captured_actions: list[Action] = field(default_factory=list)
    seen_actions: set[int] = field(default_factory=set)

    def capture(self, obj: Any) -> None:
        if not isinstance(obj, Action):
            return
        key = id(obj)
        if key in self.seen_actions:
            return
        self.seen_actions.add(key)
        self.captured_actions.append(obj)


_current_composition_scope: ContextVar[_CompositionScope | None] = ContextVar(
    "_current_composition_scope",
    default=None,
)


def _capture_registered(obj: Any) -> None:
    scope = _current_composition_scope.get()
    if scope is not None:
        scope.capture(obj)


def _knowledge_items(value: Any) -> Iterable[Knowledge]:
    if isinstance(value, Knowledge):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from _knowledge_items(item)
    elif isinstance(value, Iterable) and not isinstance(value, str | bytes):
        for item in value:
            yield from _knowledge_items(item)


def _unique_knowledge(items: Iterable[Knowledge]) -> tuple[Knowledge, ...]:
    seen: set[int] = set()
    result: list[Knowledge] = []
    for item in items:
        key = id(item)
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return tuple(result)


def _action_inputs(action: Action) -> Iterable[Knowledge]:
    if isinstance(action, Compose):
        yield from (item for item in action.inputs if isinstance(item, Knowledge))
    elif isinstance(action, Support):
        yield from action.given
    elif isinstance(action, Relate):
        if action.a is not None:
            yield action.a
        if action.b is not None:
            yield action.b
    elif isinstance(action, Infer):
        if action.hypothesis is not None:
            yield action.hypothesis
        if action.evidence is not None:
            yield action.evidence
        if isinstance(action.p_e_given_h, Knowledge):
            yield action.p_e_given_h
        if isinstance(action.p_e_given_not_h, Knowledge):
            yield action.p_e_given_not_h
    elif isinstance(action, Associate):
        if action.a is not None:
            yield action.a
        if action.b is not None:
            yield action.b


def _action_outputs(action: Action) -> Iterable[Knowledge]:
    if isinstance(action, Compose):
        if action.conclusion is not None:
            yield action.conclusion
    elif isinstance(action, Support):
        if action.conclusion is not None:
            yield action.conclusion
    elif isinstance(action, Relate):
        if action.helper is not None:
            yield action.helper
    elif isinstance(action, Infer | Associate):
        if action.helper is not None:
            yield action.helper
    yield from action.warrants


def _infer_inputs(
    *,
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
    actions: list[Action],
    background: list[Knowledge],
) -> tuple[Knowledge, ...]:
    explicit_inputs = list(_knowledge_items(args))
    explicit_inputs.extend(_knowledge_items(kwargs))

    produced = {id(item) for action in actions for item in _action_outputs(action)}
    background_ids = {id(item) for item in background}
    action_inputs = [
        item
        for action in actions
        for item in _action_inputs(action)
        if id(item) not in produced and id(item) not in background_ids
    ]
    return _unique_knowledge([*explicit_inputs, *action_inputs])


def compose(
    *,
    name: str,
    version: str,
    background: list[Knowledge] | None = None,
    warrants: list[Claim] | None = None,
    rationale: str = "",
    label: str | None = None,
):
    """Decorate a function as a Gaia action composition template."""

    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            scope = _CompositionScope(name, version)
            token = _current_composition_scope.set(scope)
            try:
                result = fn(*args, **kwargs)
            finally:
                _current_composition_scope.reset(token)
            if not isinstance(result, Claim):
                raise TypeError("@compose functions must return a Claim object")

            compose_background = list(background or [])
            Compose(
                label=label,
                rationale=rationale,
                background=compose_background,
                warrants=list(warrants or []),
                name=name,
                version=version,
                inputs=_infer_inputs(
                    args=args,
                    kwargs=kwargs,
                    actions=scope.captured_actions,
                    background=compose_background,
                ),
                actions=tuple(scope.captured_actions),
                conclusion=result,
            )
            return result

        return wrapper

    return decorator


composition = compose
Composition = Compose
