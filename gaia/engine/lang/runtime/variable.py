"""Variable — typed term Knowledge subclass.

Lang-only: like Domain, overrides __post_init__ to skip IR-bound knowledge map
registration. Carries the Term protocol marker so it can appear in formulas.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, ClassVar, cast

from gaia.engine.lang.formula.primitives import PrimitiveType
from gaia.engine.lang.runtime.domain import Domain
from gaia.engine.lang.runtime.knowledge import Knowledge, _current_package


@dataclass(init=False, eq=False)
class Variable(Knowledge):
    """A typed term referenceable by formulas, models, and actions.

    Subclasses Knowledge for identity, provenance, metadata. Carries a symbol
    used in formulas, a domain (PrimitiveType or user-declared Domain), and an
    optional bound value. Binding semantics (CONSTANT / FREE / BOUND_BY_CLAIM)
    are inferred by Milestone B's compiler; this class stores only authored data.

    Lang-only: does NOT enter the package's IR-bound knowledge map (spec §2.4).
    """

    # Term protocol marker — see gaia.engine.lang.formula.term.is_term (Milestone A Task 5)
    __gaia_term__: ClassVar[bool] = True

    symbol: str = field(default="")
    domain: PrimitiveType | Domain = field(default=cast(PrimitiveType, None))
    value: Any | None = None
    unit: str | None = None

    def __init__(
        self,
        *,
        symbol: str,
        domain: PrimitiveType | Domain,
        value: Any | None = None,
        unit: str | None = None,
        content: str | None = None,
        format: str = "markdown",
        **kwargs: Any,
    ) -> None:
        """Create a typed authoring variable."""
        if not isinstance(symbol, str) or not symbol:
            raise TypeError("symbol must be a non-empty string")
        if not isinstance(domain, (PrimitiveType, Domain)):
            raise TypeError("domain must be a PrimitiveType or a Domain")

        if value is not None:
            _validate_value(value, domain)

        canonical_unit_value: str | None = None
        if unit is not None:
            from gaia.unit import canonical_unit

            canonical_unit_value = canonical_unit(unit)

        if content is None:
            content = _default_content(symbol, domain, value, canonical_unit_value)

        super().__init__(content=content, type="variable", format=format, **kwargs)
        self.symbol = symbol
        self.domain = domain
        self.value = value
        self.unit = canonical_unit_value

    def __post_init__(self) -> None:
        """Associate the variable with package provenance without IR registration."""
        # Override Knowledge.__post_init__: associate with the package for provenance,
        # but DO NOT call pkg._register_knowledge — Variable is Lang-only (spec §2.4).
        pkg = _current_package.get()
        source_module = None
        if pkg is None:
            from gaia.engine.lang.runtime.package import infer_package_and_module

            pkg, source_module = infer_package_and_module()
        if pkg is not None:
            self._source_module = source_module
            self._package = pkg


def _validate_value(value: Any, domain: PrimitiveType | Domain) -> None:
    if isinstance(domain, PrimitiveType):
        if not domain.accepts(value):
            raise ValueError(f"value {value!r} not accepted by primitive type {domain}")
    else:
        if value not in domain.members:
            raise ValueError(f"value {value!r} not in domain members of {domain.label or 'Domain'}")


def _default_content(
    symbol: str,
    domain: PrimitiveType | Domain,
    value: Any | None,
    unit: str | None,
) -> str:
    domain_name = domain.name if isinstance(domain, PrimitiveType) else (domain.label or "Domain")
    unit_part = f" [{unit}]" if unit is not None else ""
    if value is None:
        return f"Variable {symbol}: {domain_name}{unit_part}"
    return f"Variable {symbol}: {domain_name}{unit_part} = {value!r}"
