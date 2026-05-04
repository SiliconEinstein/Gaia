"""Term — value-bearing AST nodes (typed).

Spec §3 typed-AST discipline:
- Constant.primitive is a PrimitiveType reference; value must be accepted by it.
- FunctionApp.symbol is a FunctionSymbol; arity and arg domains validated.
- ArithOp operands must be Terms; op must be one of {+, -, *, /}.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, ClassVar, Protocol, runtime_checkable

from gaia.lang.formula.symbols import FunctionSymbol
from gaia.lang.runtime.domain import Domain
from gaia.lang.types.primitives import PrimitiveType


_ARITH_OPS = frozenset({"+", "-", "*", "/"})


@runtime_checkable
class Term(Protocol):
    """Marker protocol. A Term is a value-bearing expression node."""

    __gaia_term__: bool = True


def is_term(obj: object) -> bool:
    """Strict check — only objects explicitly tagged as terms qualify."""
    return getattr(obj, "__gaia_term__", False) is True


def _term_domain(t: Any) -> PrimitiveType | Domain | None:
    """Best-effort domain inference for a Term (used to validate FunctionApp args).

    Returns None when the domain cannot be statically determined (e.g. raw ArithOp).
    """
    if isinstance(t, Constant):
        return t.primitive
    if hasattr(t, "domain"):  # Variable
        return getattr(t, "domain")
    if isinstance(t, FunctionApp):
        return t.symbol.result_domain
    return None  # ArithOp — leave to compiler to type-check


@dataclass(frozen=True)
class Constant:
    """A primitive literal value, validated against its declared PrimitiveType."""

    value: Any
    primitive: PrimitiveType

    __gaia_term__: ClassVar[bool] = True

    def __post_init__(self) -> None:
        if not isinstance(self.primitive, PrimitiveType):
            raise TypeError(
                f"primitive must be a PrimitiveType, got {type(self.primitive).__name__}"
            )
        if not self.primitive.accepts(self.value):
            raise ValueError(
                f"value {self.value!r} not accepted by primitive type {self.primitive}"
            )


@dataclass(frozen=True)
class FunctionApp:
    """Application of a FunctionSymbol to a tuple of Term arguments."""

    symbol: FunctionSymbol
    args: tuple[Any, ...]

    __gaia_term__: ClassVar[bool] = True

    def __post_init__(self) -> None:
        if not isinstance(self.symbol, FunctionSymbol):
            raise TypeError(f"symbol must be a FunctionSymbol, got {type(self.symbol).__name__}")
        expected_arity = len(self.symbol.arg_domains)
        if len(self.args) != expected_arity:
            raise ValueError(
                f"FunctionApp arity mismatch: {self.symbol.name} expects "
                f"{expected_arity} args, got {len(self.args)}"
            )
        for i, (arg, expected_domain) in enumerate(zip(self.args, self.symbol.arg_domains)):
            if not is_term(arg):
                raise TypeError(f"FunctionApp argument {i} is not a Term: {arg!r}")
            actual = _term_domain(arg)
            if actual is not None and actual is not expected_domain:
                raise TypeError(
                    f"FunctionApp argument {i} domain mismatch: {self.symbol.name} expects "
                    f"{expected_domain}, got {actual}"
                )


@dataclass(frozen=True)
class ArithOp:
    """An arithmetic operation between two Terms."""

    op: str
    left: Any
    right: Any

    __gaia_term__: ClassVar[bool] = True

    def __post_init__(self) -> None:
        if self.op not in _ARITH_OPS:
            raise ValueError(f"op must be one of {_ARITH_OPS}, got {self.op!r}")
        if not is_term(self.left):
            raise TypeError(f"ArithOp.left is not a Term: {self.left!r}")
        if not is_term(self.right):
            raise TypeError(f"ArithOp.right is not a Term: {self.right!r}")
