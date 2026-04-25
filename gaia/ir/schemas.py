"""Shared Gaia IR schema carriers for scientific parameters."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, model_validator


BuiltinDistributionKind = Literal[
    "normal",
    "lognormal",
    "student_t",
    "cauchy",
    "binomial",
    "poisson",
    "exponential",
    "beta",
]

DistributionKind = Literal[
    "normal",
    "lognormal",
    "student_t",
    "cauchy",
    "binomial",
    "poisson",
    "exponential",
    "beta",
    "custom",
]

BUILTIN_DISTRIBUTION_KINDS = frozenset(
    {
        "normal",
        "lognormal",
        "student_t",
        "cauchy",
        "binomial",
        "poisson",
        "exponential",
        "beta",
    }
)


class QuantityLiteral(BaseModel):
    """JSON-native IR carrier for unit-bearing scalar values."""

    schema_version: Literal["gaia.quantity_literal.v1"] = "gaia.quantity_literal.v1"
    value: float
    unit: str


class CallableRef(BaseModel):
    """Provenance pointer for a callable, not a runtime execution pointer."""

    schema_version: Literal["gaia.callable_ref.v1"] = "gaia.callable_ref.v1"
    name: str
    version: str | None = None
    signature: str | None = None
    source_hash: str | None = None
    purity: Literal["pure", "impure", "unknown"] = "unknown"


DistributionParam = QuantityLiteral | float | int


class DistributionSpec(BaseModel):
    """JSON-native distribution declaration for IR and adapter boundaries."""

    schema_version: Literal["gaia.distribution.v1"] = "gaia.distribution.v1"
    kind: DistributionKind
    params: dict[str, DistributionParam]
    callable_ref: CallableRef | None = None

    @model_validator(mode="after")
    def _validate_callable_ref(self) -> DistributionSpec:
        if self.kind == "custom":
            if self.callable_ref is None:
                raise ValueError("custom distributions require callable_ref")
            return self

        if self.callable_ref is not None:
            raise ValueError("Built-in distributions must not carry callable_ref")
        return self
