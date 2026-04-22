"""Gaia Lang v5 — core runtime dataclasses for Python DSL."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from gaia.lang.runtime.knowledge import Knowledge, _current_package


@dataclass
class Step:
    """A single reasoning step with optional premise references."""

    reason: str
    premises: list[Knowledge] | None = None
    metadata: dict[str, Any] | None = None


# Accepted types for the ``reason`` parameter on strategy functions.
ReasonInput = str | list[str | Step]


@dataclass
class Strategy:
    """A reasoning declaration."""

    type: str
    premises: list[Knowledge] = field(default_factory=list)
    conclusion: Knowledge | None = None
    background: list[Knowledge] = field(default_factory=list)
    reason: ReasonInput = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    label: str | None = None
    formal_expr: list | None = None
    sub_strategies: list[Strategy] = field(default_factory=list)
    composition_warrant: Knowledge | None = None

    def __post_init__(self):
        pkg = _current_package.get()
        if pkg is None:
            from gaia.lang.runtime.package import infer_package_from_callstack

            pkg = infer_package_from_callstack()
        if pkg is not None:
            pkg._register_strategy(self)


@dataclass
class Operator:
    """A deterministic logical constraint."""

    operator: str
    variables: list[Knowledge] = field(default_factory=list)
    conclusion: Knowledge | None = None
    reason: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        pkg = _current_package.get()
        if pkg is None:
            from gaia.lang.runtime.package import infer_package_from_callstack

            pkg = infer_package_from_callstack()
        if pkg is not None:
            pkg._register_operator(self)
