"""Restricted-globals sandbox for cli-author formula / predicate expressions.

R3·❓C=A (locked in 协作单 §三 / §五) — when a user passes a Python expression
through ``decompose --formula-expr`` or ``claim --predicate``, the cli compiles
it inside a sandbox whose globals contain ``__builtins__ = {}`` and an
explicit whitelist of formula primitives + Distribution factories. Names
outside the whitelist raise :class:`FormulaSandboxError`, which the caller
maps to a ``prewrite.expr_unsafe`` diagnostic with exit code 2
(``EXIT_INPUT_SYNTAX``).

Why restricted-globals rather than refusing to eval at all? The DSL formula
surface naturally lives at expression level — forcing the agent into a
stub-DSL inside argv would be worse than letting Python parse a tight
whitelist of names. The sandbox is defense-in-depth, not the only defense:
the resulting formula source still goes through ``ast.parse`` in the
pre-write (b) invariant, and the engine performs its own type checks when
the rendered statement is loaded. The sandbox is what prevents
``__import__("os").system("…")`` shapes from ever reaching the file.

Whitelist sources (rev 58 §五 explicit + concrete-shipping reality):

* Formula primitives — ``land`` / ``lor`` / ``lnot`` / ``implies`` / ``iff``
  / ``equals`` / ``forall`` / ``exists``. All exported by
  ``gaia.engine.lang.dsl.formula``.
* Atom constructor — ``ClaimAtom`` from
  ``gaia.engine.lang.dsl.bool_expr`` (so authors can wrap a Claim
  identifier inside ``land(...)`` etc.). The brief listed only the
  bare formula primitives; the engine surface always pairs them with
  ``ClaimAtom`` for authoring shape, so we include the atom constructor
  alongside.
* Distribution factories — the engine's shipping set
  (``Normal`` / ``LogNormal`` / ``Beta`` / ``Exponential`` / ``Gamma``
  / ``StudentT`` / ``Cauchy`` / ``ChiSquared`` / ``Binomial`` /
  ``Poisson``). The brief listed ``Uniform`` but that family is not
  in the v0.5 surface (see ``gaia.engine.lang.runtime.distribution``
  ``__all__``); listing only the shipping concrete factories keeps the
  sandbox honest. Including all of them prevents
  ``"Uniform not whitelisted but Poisson is"`` confusion.

Identifier resolution at sandbox time: the caller passes a ``locals_map``
of identifier → value pairs (typically the ``ClaimAtom`` references the
user named on the command line). Bare identifiers therefore resolve against
both the locals_map and the whitelist; missing names produce
``FormulaSandboxError``.

Notes:
* The sandbox parses the expression with ``ast.parse(mode="eval")`` and
  walks the AST to reject ``Attribute`` / ``Subscript`` / ``Import`` /
  ``Lambda`` / ``Call`` to internal-looking dunder names. Anything that
  reaches the ``eval`` step has been name-checked already, so the
  restricted globals are belt-and-braces.
* The sandbox returns the parsed source string rather than the evaluated
  object: the cli's job is to write a self-contained Python snippet to
  the package source. The engine evaluates the snippet at package-load
  time inside its own scope. Sandbox-evaluation would lose the literal
  identifier names (replaced with concrete Claim objects), defeating
  the writer's reproducible-source contract.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from typing import ClassVar

# --------------------------------------------------------------------------- #
# Whitelist                                                                   #
# --------------------------------------------------------------------------- #

# Formula primitives — top-level connectives + quantifiers + equality.
# Exported by ``gaia.engine.lang.dsl.formula``.
_FORMULA_PRIMITIVES: frozenset[str] = frozenset(
    {
        "land",
        "lor",
        "lnot",
        "implies",
        "iff",
        "equals",
        "forall",
        "exists",
    }
)

# Atom constructor — the bridge between Claim identifiers and the formula
# AST. Authors write ``land(ClaimAtom(a), ClaimAtom(b))``; without
# ``ClaimAtom`` the whitelist would force them out of the sandbox path.
_ATOM_CONSTRUCTORS: frozenset[str] = frozenset({"ClaimAtom"})

# Distribution factories — concrete shipping set from
# ``gaia.engine.lang.runtime.distribution`` ``__all__``. ``Distribution``
# (the base class) is also listed because the DSL surface re-exports
# it as the umbrella name authors reach for first.
_DISTRIBUTION_FACTORIES: frozenset[str] = frozenset(
    {
        "Distribution",
        "Normal",
        "LogNormal",
        "Beta",
        "Exponential",
        "Gamma",
        "StudentT",
        "Cauchy",
        "ChiSquared",
        "Binomial",
        "Poisson",
    }
)

# Constants — bare literals.
_CONSTANTS: frozenset[str] = frozenset({"True", "False", "None"})

# R7 G4 — Variable + Constant + Domain primitives. Allows formula
# expressions to reference typed terms (e.g. ``equals(my_var,
# Constant(395, Nat))`` matches the mendel pattern). The whitelist
# permits the class names; pre-write resolves user-named identifiers
# (the Variable's own label) through the same ``extra_names`` channel
# decompose / claim --formula already feed in.
_TYPED_TERMS: frozenset[str] = frozenset(
    {
        "Variable",
        "Constant",
        "Nat",
        "Real",
        "Bool",
        "Probability",
    }
)

WHITELIST: frozenset[str] = (
    _FORMULA_PRIMITIVES | _ATOM_CONSTRUCTORS | _DISTRIBUTION_FACTORIES | _CONSTANTS | _TYPED_TERMS
)


# --------------------------------------------------------------------------- #
# Sandbox error                                                               #
# --------------------------------------------------------------------------- #


class FormulaSandboxError(ValueError):
    """Raised when an expression references a name outside the whitelist."""

    def __init__(self, message: str, *, offending_name: str | None = None) -> None:
        super().__init__(message)
        self.offending_name = offending_name


# --------------------------------------------------------------------------- #
# Validation                                                                  #
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class SandboxValidation:
    """Outcome of :func:`validate_formula_expr`."""

    expression: str
    referenced_names: tuple[str, ...]


def validate_formula_expr(
    expr: str,
    *,
    extra_names: frozenset[str] | set[str] | None = None,
) -> SandboxValidation:
    """Validate a cli-author formula / predicate expression.

    Parses ``expr`` as a Python expression (``mode="eval"``), walks the AST,
    and confirms every referenced :class:`ast.Name` resolves against the
    static whitelist (formula primitives + ``ClaimAtom`` + Distribution
    factories + literal constants) or the ``extra_names`` set the caller
    provided (typically the Claim identifiers named on the command line).

    Args:
        expr: The expression source to validate.
        extra_names: Names the caller wants to permit in addition to the
            standing whitelist — e.g. ``--parts`` identifiers for
            ``decompose --formula-expr``.

    Returns:
        :class:`SandboxValidation` with the original expression (stripped)
        and the sorted tuple of names that actually appeared.

    Raises:
        FormulaSandboxError: when the expression contains a name not in the
            whitelist or ``extra_names``, references a dunder attribute /
            global, uses unsafe constructs (``Lambda`` / ``Yield`` /
            comprehension scopes), or fails to parse.
    """
    text = expr.strip()
    if not text:
        raise FormulaSandboxError("expression is empty")

    try:
        tree = ast.parse(text, mode="eval")
    except SyntaxError as exc:
        raise FormulaSandboxError(
            f"expression is not valid Python: {exc.msg}",
        ) from exc

    allowed = WHITELIST | (frozenset(extra_names) if extra_names else frozenset())

    visitor = _SandboxVisitor(allowed)
    visitor.visit(tree)
    return SandboxValidation(
        expression=text,
        referenced_names=tuple(sorted(visitor.referenced_names)),
    )


class _SandboxVisitor(ast.NodeVisitor):
    """Walk the expression AST and enforce the sandbox rules."""

    # Node types we refuse outright. Each entry is the node class plus a
    # human-readable phrase for the error message. We deliberately *do*
    # allow ``Call`` (formula construction lives in calls), ``Tuple`` /
    # ``List`` (operands), and ``Compare`` / ``BoolOp`` / ``BinOp`` (so
    # ``k > 1e-2`` style predicates parse).
    _DISALLOWED_NODES: ClassVar[dict[type[ast.AST], str]] = {
        ast.Attribute: "attribute access",
        ast.Subscript: "subscripting",
        ast.Lambda: "lambda",
        ast.IfExp: "ternary expression",
        ast.Yield: "yield",
        ast.YieldFrom: "yield-from",
        ast.Await: "await",
        ast.GeneratorExp: "generator expression",
        ast.ListComp: "list comprehension",
        ast.DictComp: "dict comprehension",
        ast.SetComp: "set comprehension",
        ast.Starred: "starred expression",
        ast.NamedExpr: "walrus expression",
        ast.FormattedValue: "f-string interpolation",
        ast.JoinedStr: "f-string",
    }

    def __init__(self, allowed: frozenset[str]) -> None:
        self.allowed = allowed
        self.referenced_names: set[str] = set()

    def visit(self, node: ast.AST) -> None:
        # Refuse first; recurse second so the offending node is reported.
        for forbidden, label in self._DISALLOWED_NODES.items():
            if isinstance(node, forbidden):
                raise FormulaSandboxError(
                    f"expression uses {label}, which is not allowed in the formula sandbox",
                )
        super().visit(node)

    def visit_Name(self, node: ast.Name) -> None:
        name = node.id
        self.referenced_names.add(name)
        if name.startswith("__"):
            raise FormulaSandboxError(
                f"dunder name {name!r} is not allowed in the formula sandbox",
                offending_name=name,
            )
        if name not in self.allowed:
            raise FormulaSandboxError(
                f"name {name!r} is not in the formula sandbox whitelist",
                offending_name=name,
            )

    def visit_Call(self, node: ast.Call) -> None:
        # Reject keyword-only ``**kwargs`` unpacking; we still allow
        # named-keyword args (``mu=0``) since they're how distribution
        # factories take parameters.
        for kw in node.keywords:
            if kw.arg is None:
                raise FormulaSandboxError(
                    "**kwargs unpacking is not allowed in the formula sandbox",
                )
        self.generic_visit(node)


__all__ = [
    "WHITELIST",
    "FormulaSandboxError",
    "SandboxValidation",
    "validate_formula_expr",
]
