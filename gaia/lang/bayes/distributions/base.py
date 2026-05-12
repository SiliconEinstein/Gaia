"""Shared machinery for Bayes distribution literals."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, model_validator

from gaia.lang.bayes.distributions.protocol import UnresolvedParameterError


def _is_concrete_number(value: Any) -> bool:
    return not isinstance(value, bool) and isinstance(value, (int, float))


def _is_deferred_reference(value: Any) -> bool:
    return isinstance(getattr(value, "symbol", None), str)


def _domain_descriptor(value: Any) -> str:
    if isinstance(value, str):
        return value
    for attr in ("name", "label", "content"):
        candidate = getattr(value, attr, None)
        if isinstance(candidate, str):
            return candidate
    return repr(value)


def _deferred_reference_descriptor(value: Any) -> dict[str, Any]:
    descriptor: dict[str, Any] = {"symbol": value.symbol}
    domain = getattr(value, "domain", None)
    if domain is not None:
        descriptor["domain"] = _domain_descriptor(domain)
    label = getattr(value, "label", None)
    if label is not None:
        descriptor["label"] = label
    return descriptor


class _BaseDistribution(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True, frozen=True)

    kind: str
    params: dict[str, Any]

    @model_validator(mode="after")
    def _validate_params(self) -> "_BaseDistribution":
        for name, value in self.params.items():
            if not _is_concrete_number(value) and not _is_deferred_reference(value):
                raise ValueError(
                    f"{self.kind} parameter {name!r} must be a number "
                    "or a deferred reference with a string `.symbol` attribute"
                )
        return self

    def _deferred_param_names(self) -> list[str]:
        return sorted(name for name, value in self.params.items() if _is_deferred_reference(value))

    def _resolved_params(self) -> dict[str, float]:
        deferred = self._deferred_param_names()
        if deferred:
            raise UnresolvedParameterError(self.kind, deferred)
        return {name: float(value) for name, value in self.params.items()}

    def _replace_params(self, params: dict[str, Any]) -> "_BaseDistribution":
        return self.__class__(**params)

    def model_dump(self, **kwargs: Any) -> dict[str, Any]:
        concrete = {
            name: value for name, value in self.params.items() if not _is_deferred_reference(value)
        }
        deferred = {
            name: _deferred_reference_descriptor(value)
            for name, value in sorted(self.params.items())
            if _is_deferred_reference(value)
        }
        payload: dict[str, Any] = {"kind": self.kind, "params": concrete}
        if deferred:
            payload["deferred_params"] = deferred
        return payload
