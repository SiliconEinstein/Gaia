"""BoolExpr — boolean expression over Distribution objects (and constants).

The dataclasses in this module are produced by Distribution operator overloads
(``k > 1e-3``, ``y == baseline + slope * x``, ``A / B``).
They carry no semantic meaning on their own — they are intermediate values
that ``claim(content, expr)`` accepts as a structured proposition.

At compile time the BoolExpr is lowered into Claim metadata
(``metadata['predicate']`` or ``metadata['equation']``) which the BP layer
reads to compute inequality predicate priors via the underlying distribution's
CDF. Equation propositions are currently metadata plus an author/default prior;
joint-distribution constraint lowering is future work.

``BoolExpr.__bool__`` raises with a helpful message — analogous to
:meth:`gaia.engine.lang.runtime.knowledge.Claim.__bool__` — so accidental use in
Python control flow (``if k > 1e-3: ...``) surfaces as a clear error rather
than as silently always-truthy.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

ComparisonOp = Literal[">", ">=", "<", "<=", "==", "!="]
ArithmeticOp = Literal["+", "-", "*", "/"]


@dataclass(eq=False)
class DerivedDistribution:
    """Arithmetic combination of distributions / scalars (e.g. ``baseline + slope * x``).

    Used as the right-hand side of an :class:`Equation` proposition. Carries no
    runtime sampling logic — it is a syntactic placeholder retained in
    equation metadata for audit and future constraint lowering.

    Constants (Python ``int`` / ``float`` / ``Quantity``) and other
    DerivedDistributions may appear on either operand position.
    """

    op: ArithmeticOp
    left: Any
    right: Any

    def __post_init__(self) -> None:
        """Validate the arithmetic operator."""
        if self.op not in {"+", "-", "*", "/"}:
            raise ValueError(
                f"DerivedDistribution op must be one of '+', '-', '*', '/', got {self.op!r}"
            )

    def __hash__(self) -> int:
        """Identity-based hash (mirrors Distribution behaviour)."""
        return id(self)

    # Arithmetic operators — chain into deeper DerivedDistribution trees.
    def __add__(self, other: Any) -> DerivedDistribution:
        """Right-side addition, producing ``self + other`` derived expression."""
        return DerivedDistribution("+", self, other)

    def __radd__(self, other: Any) -> DerivedDistribution:
        """Reflected addition, producing ``other + self`` derived expression."""
        return DerivedDistribution("+", other, self)

    def __sub__(self, other: Any) -> DerivedDistribution:
        """Right-side subtraction producing ``self - other`` derived expression."""
        return DerivedDistribution("-", self, other)

    def __rsub__(self, other: Any) -> DerivedDistribution:
        """Reflected subtraction producing ``other - self`` derived expression."""
        return DerivedDistribution("-", other, self)

    def __mul__(self, other: Any) -> DerivedDistribution:
        """Right-side multiplication producing ``self * other`` derived expression."""
        return DerivedDistribution("*", self, other)

    def __rmul__(self, other: Any) -> DerivedDistribution:
        """Reflected multiplication producing ``other * self`` derived expression."""
        return DerivedDistribution("*", other, self)

    def __truediv__(self, other: Any) -> DerivedDistribution:
        """Right-side division producing ``self / other`` derived expression."""
        return DerivedDistribution("/", self, other)

    def __rtruediv__(self, other: Any) -> DerivedDistribution:
        """Reflected division producing ``other / self`` derived expression."""
        return DerivedDistribution("/", other, self)

    def __neg__(self) -> DerivedDistribution:
        """Unary negation producing ``-self`` derived expression."""
        return DerivedDistribution("-", 0, self)

    # Comparison operators — produce BoolExpr (so ``baseline + slope * x == y`` works).
    def __gt__(self, other: Any) -> BoolExpr:
        """Greater-than comparison returning a BoolExpr proposition."""
        return BoolExpr(">", self, other)

    def __ge__(self, other: Any) -> BoolExpr:
        """Greater-or-equal comparison returning a BoolExpr proposition."""
        return BoolExpr(">=", self, other)

    def __lt__(self, other: Any) -> BoolExpr:
        """Less-than comparison returning a BoolExpr proposition."""
        return BoolExpr("<", self, other)

    def __le__(self, other: Any) -> BoolExpr:
        """Less-or-equal comparison returning a BoolExpr proposition."""
        return BoolExpr("<=", self, other)

    def __eq__(self, other: Any) -> Any:
        """Equation comparison returning a BoolExpr (op ``==``)."""
        return BoolExpr("==", self, other)

    def __ne__(self, other: Any) -> Any:
        """Inequality comparison returning a BoolExpr (op ``!=``)."""
        return BoolExpr("!=", self, other)


@dataclass(eq=False)
class BoolExpr:
    """Boolean proposition over Distribution objects.

    Created by Distribution comparison operators (``k > 1e-3``,
    ``y == baseline + slope * x``). ``claim(content, expr)`` accepts a BoolExpr as the
    second argument and lowers it to claim metadata so the compiler can
    compute the resulting prior via the underlying distribution's CDF (for
    inequality predicates). Equality / equation predicates are preserved in
    metadata with author/default priors; constraint lowering is future work.

    The :meth:`__bool__` override raises so accidental Python control-flow use
    (``if k > 1e-3: ...``) surfaces immediately rather than silently always
    evaluating to True (the dataclass would otherwise be truthy).
    """

    op: ComparisonOp
    left: Any
    right: Any

    def __post_init__(self) -> None:
        """Validate the comparison operator."""
        if self.op not in {">", ">=", "<", "<=", "==", "!="}:
            raise ValueError(
                f"BoolExpr op must be one of '>', '>=', '<', '<=', '==', '!=', got {self.op!r}"
            )

    def __hash__(self) -> int:
        """Identity-based hash (mirrors Distribution / DerivedDistribution)."""
        return id(self)

    def __bool__(self) -> bool:
        """Reject Python truth-value coercion with a helpful error.

        Mirrors :meth:`Claim.__bool__`. Authors often write ``if k > 1e-3:``
        in scratch code; without this guard, the BoolExpr would be truthy
        (non-empty dataclass), masking the bug. The error message points to
        the intended use as a claim proposition.
        """
        raise TypeError(
            "BoolExpr does not have a Python truth value (analogous to numpy "
            "or sympy expressions). Use it as the proposition argument to "
            'claim(...): claim("k is fast", k > 1e-2)'
        )

    # Comparison operators on a BoolExpr would be unusual but are defined for
    # symmetry — for example ``(k > 1e-3) != True`` should still produce a
    # BoolExpr rather than coercing.
    def __eq__(self, other: Any) -> Any:
        """Equality comparison returning a nested BoolExpr (rare)."""
        return BoolExpr("==", self, other)

    def __ne__(self, other: Any) -> Any:
        """Inequality comparison returning a nested BoolExpr (rare)."""
        return BoolExpr("!=", self, other)
