"""FunctionSymbol and PredicateSymbol — typed declarations of user-defined symbols."""

from __future__ import annotations

from dataclasses import dataclass

from gaia.engine.lang.runtime.domain import Domain
from gaia.engine.lang.types.primitives import PrimitiveType


def _validate_arg_domains(arg_domains: tuple[object, ...]) -> None:
    if len(arg_domains) == 0:
        raise ValueError(
            "arity zero is not allowed; use a Claim for nullary propositions or a "
            "Variable for nullary terms"
        )
    for i, d in enumerate(arg_domains):
        if not isinstance(d, (PrimitiveType, Domain)):
            raise TypeError(
                f"arg_domain[{i}] must be a PrimitiveType or Domain, got {type(d).__name__}"
            )


@dataclass(frozen=True)
class FunctionSymbol:
    """Declaration of a user function symbol like ``E: Particle → Real``."""

    name: str
    arg_domains: tuple[PrimitiveType | Domain, ...]
    result_domain: PrimitiveType | Domain

    def __post_init__(self) -> None:
        """Validate function symbol name, argument domains, and result domain."""
        if not self.name:
            raise ValueError("name must be a non-empty string")
        _validate_arg_domains(self.arg_domains)
        if not isinstance(self.result_domain, (PrimitiveType, Domain)):
            raise TypeError(
                f"result_domain must be a PrimitiveType or Domain, "
                f"got {type(self.result_domain).__name__}"
            )


@dataclass(frozen=True)
class PredicateSymbol:
    """Declaration of a user predicate symbol like ``Stable: Particle → Bool``."""

    name: str
    arg_domains: tuple[PrimitiveType | Domain, ...]

    def __post_init__(self) -> None:
        """Validate predicate symbol name and argument domains."""
        if not self.name:
            raise ValueError("name must be a non-empty string")
        _validate_arg_domains(self.arg_domains)
