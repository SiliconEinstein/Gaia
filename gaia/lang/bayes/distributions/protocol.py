"""Distribution protocol and deferred-parameter errors."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

DistParam = int | float | Any


class UnresolvedParameterError(ValueError):
    """Raised when evaluating a distribution with unresolved deferred params."""

    def __init__(self, distribution_kind: str, deferred_params: list[str]) -> None:
        self.distribution_kind = distribution_kind
        self.deferred_params = list(deferred_params)
        names = ", ".join(deferred_params)
        super().__init__(
            f"{distribution_kind} has unresolved deferred parameter(s): {names}. "
            "Resolve Variable-backed distribution parameters before likelihood evaluation."
        )


@runtime_checkable
class Distribution(Protocol):
    kind: str
    params: dict[str, DistParam]

    def logpmf(self, x: int) -> float: ...

    def logpdf(self, x: float) -> float: ...

    def support(self) -> tuple[float, float]: ...

    def model_dump(self, **kwargs: Any) -> dict[str, Any]: ...
