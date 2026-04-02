"""Gaia Lang v5 — Package context manager."""

from __future__ import annotations

from gaia.lang.runtime.nodes import Knowledge, Operator, Strategy, _current_package


class Package:
    """Context manager that collects all DSL declarations."""

    def __init__(self, name: str, *, namespace: str = "reg", version: str = "0.1.0"):
        self.name = name
        self.namespace = namespace
        self.version = version
        self.knowledge: list[Knowledge] = []
        self.strategies: list[Strategy] = []
        self.operators: list[Operator] = []
        self._token = None

    def __enter__(self):
        self._token = _current_package.set(self)
        return self

    def __exit__(self, *exc):
        _current_package.reset(self._token)
        self._token = None

    def _register_knowledge(self, k: Knowledge):
        self.knowledge.append(k)

    def _register_strategy(self, s: Strategy):
        self.strategies.append(s)

    def _register_operator(self, o: Operator):
        self.operators.append(o)

    @property
    def exported(self) -> list[str]:
        return [k.label for k in self.knowledge if k.label is not None]
