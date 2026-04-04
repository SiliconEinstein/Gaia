"""Gaia Lang v5 — core runtime dataclasses for Python DSL."""

from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from gaia.lang.runtime.package import CollectedPackage

_current_package: ContextVar[CollectedPackage | None] = ContextVar("_current_package", default=None)


@dataclass
class Knowledge:
    """A knowledge declaration (claim, setting, or question)."""

    content: str
    type: str  # "claim" | "setting" | "question"
    title: str | None = None
    background: list[Knowledge] = field(default_factory=list)
    parameters: list[dict] = field(default_factory=list)
    provenance: list[dict[str, str]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    label: str | None = None
    strategy: Strategy | None = None
    _package: CollectedPackage | None = field(default=None, init=False, repr=False, compare=False)
    _source_module: str | None = field(default=None, init=False, repr=False, compare=False)
    _declaration_index: int | None = field(default=None, init=False, repr=False, compare=False)

    def __post_init__(self):
        pkg = _current_package.get()
        source_module = None
        if pkg is None:
            from gaia.lang.runtime.package import infer_package_and_module

            pkg, source_module = infer_package_and_module()
        if pkg is not None:
            self._source_module = source_module
            self._package = pkg
            pkg._register_knowledge(self)


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
