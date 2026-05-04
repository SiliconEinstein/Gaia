# Claim Formula Schema — Milestone A Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Land the structural foundation for the formula schema redesign — Variable / Domain as Knowledge subclasses, Formula AST module, and Claim's new `formula` + `kind` fields. **No DSL surface, no compiler, no migration in this milestone.** This is pure dataclass definitions plus their unit tests.

**Architecture:** New `gaia/lang/formula/` module hosts the term/predicate/connective/quantifier AST. New files in `gaia/lang/runtime/` add `Variable` and `Domain` Knowledge subclasses and a `primitives` module. `Claim` gets two optional fields (`formula`, `kind`); existing claim authoring keeps working unchanged. IR is not touched.

**Tech Stack:** Python 3.12 dataclasses, Pydantic v2 (only where existing IR uses it; new Lang code stays on dataclasses), pytest with `asyncio_mode = "auto"`, ruff for lint/format.

**Spec:** `docs/specs/2026-05-04-claim-formula-schema-design.md` (sections 2, 3, 4 of that spec).

**Out of scope for this milestone:**
- Operator overloading on Term (`p == 0.75` style) — that's Milestone B
- `forall / exists / land / lor / ...` DSL helpers — Milestone B
- Sugar constructors (`parameter / observation / causal`) — Milestone B
- Compiler lowering Formula → IR — Milestone B
- Migrating existing packages — Milestone C
- Variable binding inference — Milestone B (compiler-side)

In this milestone, formulas are constructed via direct AST node calls: `Equals(VariableRef("p"), Constant(0.75, "Probability"))`. That's deliberately ugly — Milestone B makes it pretty.

---

## File Structure

```
gaia/lang/
├── runtime/
│   ├── knowledge.py        ← MODIFY: add formula, kind to Claim; add ClaimKind enum
│   ├── domain.py           ← NEW: Domain Knowledge subclass
│   ├── variable.py         ← NEW: Variable Knowledge subclass
│   └── __init__.py         ← MODIFY: export Variable, Domain, ClaimKind
├── types/
│   ├── __init__.py         ← NEW
│   └── primitives.py       ← NEW: Nat, Real, Probability, Bool primitive type tokens
├── formula/
│   ├── __init__.py         ← NEW: re-exports
│   ├── term.py             ← NEW: Term base, Constant, FunctionApp, ArithOp
│   ├── predicate.py        ← NEW: Predicate base, Equals, Greater, ..., ClaimAtom, Causes, UserPredicate
│   ├── connective.py       ← NEW: Connective base, Land, Lor, Lnot, Implies, Iff
│   ├── quantifier.py       ← NEW: Quantifier base, Forall, Exists
│   └── symbols.py          ← NEW: FunctionSymbol, PredicateSymbol declarations
└── __init__.py             ← MODIFY: add new top-level exports

tests/gaia/lang/
├── runtime/
│   ├── test_domain.py      ← NEW
│   ├── test_variable.py    ← NEW
│   └── test_claim_formula_kind.py   ← NEW (focused on the new fields)
├── types/
│   └── test_primitives.py  ← NEW
└── formula/
    ├── __init__.py         ← NEW
    ├── test_term.py        ← NEW
    ├── test_predicate.py   ← NEW
    ├── test_connective.py  ← NEW
    ├── test_quantifier.py  ← NEW
    └── test_symbols.py     ← NEW
```

Each new module is small (typically ≤120 lines). Tests mirror source structure.

---

## Task 1: Primitive Type Tokens

**Files:**
- Create: `gaia/lang/types/__init__.py`
- Create: `gaia/lang/types/primitives.py`
- Test: `tests/gaia/lang/types/__init__.py`, `tests/gaia/lang/types/test_primitives.py`

A `PrimitiveType` is a built-in, runtime-singleton typed sort. Authors don't subclass it — they reference the four built-ins (`Nat`, `Real`, `Probability`, `Bool`).

- [ ] **Step 1: Write the failing tests**

Create `tests/gaia/lang/types/__init__.py` (empty) and `tests/gaia/lang/types/test_primitives.py`:

```python
"""Tests for primitive type tokens."""

from gaia.lang.types.primitives import Nat, Real, Probability, Bool, PrimitiveType


def test_primitives_are_distinct_singletons():
    assert Nat is Nat
    assert Nat is not Real
    assert Real is not Probability
    assert Probability is not Bool


def test_primitive_has_name():
    assert Nat.name == "Nat"
    assert Real.name == "Real"
    assert Probability.name == "Probability"
    assert Bool.name == "Bool"


def test_primitive_validates_value():
    assert Nat.accepts(0) is True
    assert Nat.accepts(395) is True
    assert Nat.accepts(-1) is False
    assert Nat.accepts(1.5) is False

    assert Real.accepts(1.5) is True
    assert Real.accepts(0) is True

    assert Probability.accepts(0.0) is True
    assert Probability.accepts(0.75) is True
    assert Probability.accepts(1.0) is True
    assert Probability.accepts(1.5) is False
    assert Probability.accepts(-0.1) is False

    assert Bool.accepts(True) is True
    assert Bool.accepts(False) is True
    assert Bool.accepts(0) is False  # strict bool, not int


def test_primitive_repr():
    assert repr(Nat) == "Nat"
    assert repr(Probability) == "Probability"


def test_primitive_type_is_sealed():
    """Cannot construct ad-hoc PrimitiveType outside the four built-ins."""
    import pytest
    with pytest.raises(TypeError):
        PrimitiveType("MadeUp", lambda v: True)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest tests/gaia/lang/types/test_primitives.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'gaia.lang.types'`

- [ ] **Step 3: Implement the primitives module**

Create `gaia/lang/types/__init__.py`:

```python
"""Gaia Lang built-in primitive type tokens."""

from gaia.lang.types.primitives import Bool, Nat, PrimitiveType, Probability, Real

__all__ = ["PrimitiveType", "Nat", "Real", "Probability", "Bool"]
```

Create `gaia/lang/types/primitives.py`:

```python
"""Built-in primitive type tokens for Gaia Lang.

A primitive type is a runtime singleton that knows its name and how to validate
a candidate value. Authors reference the four built-ins (Nat, Real, Probability,
Bool); they do not construct PrimitiveType instances directly.
"""

from __future__ import annotations

from typing import Callable

_SEALED = False


class PrimitiveType:
    """A built-in typed sort. Construction is sealed once the module finishes loading."""

    __slots__ = ("name", "_accept")

    def __init__(self, name: str, accept: Callable[[object], bool]) -> None:
        if _SEALED:
            raise TypeError(
                "PrimitiveType is sealed. Use the four built-ins: Nat, Real, Probability, Bool."
            )
        self.name = name
        self._accept = accept

    def accepts(self, value: object) -> bool:
        return self._accept(value)

    def __repr__(self) -> str:
        return self.name

    def __reduce__(self):
        return (_lookup_primitive, (self.name,))


def _is_nat(v: object) -> bool:
    return isinstance(v, int) and not isinstance(v, bool) and v >= 0


def _is_real(v: object) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _is_probability(v: object) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and 0.0 <= float(v) <= 1.0


def _is_bool(v: object) -> bool:
    return isinstance(v, bool)


Nat = PrimitiveType("Nat", _is_nat)
Real = PrimitiveType("Real", _is_real)
Probability = PrimitiveType("Probability", _is_probability)
Bool = PrimitiveType("Bool", _is_bool)


_BY_NAME = {p.name: p for p in (Nat, Real, Probability, Bool)}


def _lookup_primitive(name: str) -> PrimitiveType:
    return _BY_NAME[name]


_SEALED = True
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pytest tests/gaia/lang/types/test_primitives.py -v`
Expected: 5 passed.

- [ ] **Step 5: Lint and format**

Run: `ruff check gaia/lang/types tests/gaia/lang/types && ruff format gaia/lang/types tests/gaia/lang/types`
Expected: clean.

- [ ] **Step 6: Commit**

```bash
git add gaia/lang/types tests/gaia/lang/types
git commit -m "feat(lang): add primitive type tokens (Nat/Real/Probability/Bool)"
```

---

## Task 2: Domain Knowledge Subclass

**Files:**
- Create: `gaia/lang/runtime/domain.py`
- Test: `tests/gaia/lang/runtime/test_domain.py`

`Domain` is a user-declared typed sort with a finite, enumerable membership list. Examples: `Particle`, `F2_plant`. Subclasses `Knowledge`, so it gets identity, provenance, metadata, and package registration for free.

- [ ] **Step 1: Write the failing tests**

Create `tests/gaia/lang/runtime/test_domain.py`:

```python
"""Tests for Domain Knowledge subclass."""

import pytest

from gaia.lang.runtime.domain import Domain
from gaia.lang.runtime.knowledge import Knowledge


def test_domain_is_knowledge_subclass():
    assert issubclass(Domain, Knowledge)


def test_domain_basic_construction():
    d = Domain(content="Single-celled organisms used in genetics", members=["yeast", "ecoli"])
    assert d.members == ["yeast", "ecoli"]
    assert d.content == "Single-celled organisms used in genetics"


def test_domain_members_required_nonempty():
    with pytest.raises(ValueError, match="members"):
        Domain(content="x", members=[])


def test_domain_members_must_be_a_list():
    with pytest.raises(TypeError, match="members"):
        Domain(content="x", members="yeast")  # type: ignore[arg-type]


def test_domain_metadata_independent_per_instance():
    d1 = Domain(content="d1", members=[1])
    d2 = Domain(content="d2", members=[2])
    d1.metadata["k"] = "v"
    assert "k" not in d2.metadata


def test_domain_no_prior_field():
    d = Domain(content="x", members=[1])
    assert not hasattr(d, "prior")


def test_domain_label_optional():
    d = Domain(content="x", members=[1])
    assert d.label is None
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest tests/gaia/lang/runtime/test_domain.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'gaia.lang.runtime.domain'`

- [ ] **Step 3: Implement Domain**

Create `gaia/lang/runtime/domain.py`:

```python
"""Domain — a user-declared typed sort backing Variable types and quantification."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from gaia.lang.runtime.knowledge import Knowledge


@dataclass(init=False, eq=False)
class Domain(Knowledge):
    """A user-declared, finite, enumerable typed sort.

    Subclasses Knowledge so it carries identity, provenance, and metadata.
    Use cases: ``Particle = domain("Particle", members=[p1, p2, ...])`` to type
    Variables and to provide enumerable members for quantifier grounding.
    """

    members: list[Any] = field(default_factory=list)

    def __init__(
        self,
        content: str,
        *,
        members: list[Any],
        format: str = "markdown",
        **kwargs,
    ):
        if not isinstance(members, list):
            raise TypeError("members must be a list")
        if len(members) == 0:
            raise ValueError("members must be a non-empty list")
        super().__init__(content=content, type="domain", format=format, **kwargs)
        self.members = list(members)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pytest tests/gaia/lang/runtime/test_domain.py -v`
Expected: 7 passed.

- [ ] **Step 5: Lint and format**

Run: `ruff check gaia/lang/runtime/domain.py tests/gaia/lang/runtime/test_domain.py && ruff format gaia/lang/runtime/domain.py tests/gaia/lang/runtime/test_domain.py`
Expected: clean.

- [ ] **Step 6: Commit**

```bash
git add gaia/lang/runtime/domain.py tests/gaia/lang/runtime/test_domain.py
git commit -m "feat(lang): add Domain Knowledge subclass for typed sorts"
```

---

## Task 3: Variable Knowledge Subclass

**Files:**
- Create: `gaia/lang/runtime/variable.py`
- Test: `tests/gaia/lang/runtime/test_variable.py`

`Variable` is a typed term that's also a Knowledge node. Holds an optional bound value (the CONSTANT case). Free / BOUND_BY_CLAIM cases are inferred by the compiler from usage in Milestone B; in this milestone, only the data shape is established.

- [ ] **Step 1: Write the failing tests**

Create `tests/gaia/lang/runtime/test_variable.py`:

```python
"""Tests for Variable Knowledge subclass."""

import pytest

from gaia.lang.runtime.domain import Domain
from gaia.lang.runtime.knowledge import Knowledge
from gaia.lang.runtime.variable import Variable
from gaia.lang.types.primitives import Nat, Probability, Real


def test_variable_is_knowledge_subclass():
    assert issubclass(Variable, Knowledge)


def test_variable_with_primitive_domain_and_value():
    n = Variable(symbol="n", domain=Nat, value=395)
    assert n.symbol == "n"
    assert n.domain is Nat
    assert n.value == 395


def test_variable_unbound():
    p = Variable(symbol="p", domain=Probability)
    assert p.value is None


def test_variable_with_custom_domain():
    Particle = Domain(content="Subatomic particles", members=["p1", "p2"])
    x = Variable(symbol="x", domain=Particle)
    assert x.domain is Particle


def test_variable_value_must_be_in_primitive_domain():
    with pytest.raises(ValueError, match="value .* not accepted"):
        Variable(symbol="n", domain=Nat, value=-1)


def test_variable_value_must_be_in_probability_range():
    with pytest.raises(ValueError, match="value .* not accepted"):
        Variable(symbol="p", domain=Probability, value=1.5)


def test_variable_with_custom_domain_value_must_be_member():
    Particle = Domain(content="x", members=["p1", "p2"])
    with pytest.raises(ValueError, match="value .* not in domain members"):
        Variable(symbol="x", domain=Particle, value="p3")


def test_variable_with_custom_domain_member_value_ok():
    Particle = Domain(content="x", members=["p1", "p2"])
    x = Variable(symbol="x", domain=Particle, value="p1")
    assert x.value == "p1"


def test_variable_symbol_required():
    with pytest.raises(TypeError, match="symbol"):
        Variable(domain=Nat)  # type: ignore[call-arg]


def test_variable_no_prior():
    n = Variable(symbol="n", domain=Nat, value=0)
    assert not hasattr(n, "prior")


def test_variable_default_content_uses_symbol():
    """If content is not provided, fall back to a sensible default derived from symbol."""
    n = Variable(symbol="n", domain=Nat, value=0)
    assert "n" in n.content
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest tests/gaia/lang/runtime/test_variable.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'gaia.lang.runtime.variable'`

- [ ] **Step 3: Implement Variable**

Create `gaia/lang/runtime/variable.py`:

```python
"""Variable — typed term Knowledge subclass."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from gaia.lang.runtime.domain import Domain
from gaia.lang.runtime.knowledge import Knowledge
from gaia.lang.types.primitives import PrimitiveType


@dataclass(init=False, eq=False)
class Variable(Knowledge):
    """A typed term referenceable by formulas, models, and actions.

    Carries identity (via Knowledge), a symbol used in formulas, a domain
    (primitive type or user-declared Domain), and an optional bound value.
    Binding semantics (CONSTANT / FREE / BOUND_BY_CLAIM) are inferred by the
    compiler from usage; this class stores only the authored data.
    """

    symbol: str
    domain: PrimitiveType | Domain
    value: Any | None = None

    def __init__(
        self,
        *,
        symbol: str,
        domain: PrimitiveType | Domain,
        value: Any | None = None,
        content: str | None = None,
        format: str = "markdown",
        **kwargs,
    ):
        if not isinstance(symbol, str) or not symbol:
            raise TypeError("symbol must be a non-empty string")
        if not isinstance(domain, (PrimitiveType, Domain)):
            raise TypeError("domain must be a PrimitiveType or a Domain")

        if value is not None:
            _validate_value(value, domain)

        if content is None:
            content = _default_content(symbol, domain, value)

        super().__init__(content=content, type="variable", format=format, **kwargs)
        self.symbol = symbol
        self.domain = domain
        self.value = value


def _validate_value(value: Any, domain: PrimitiveType | Domain) -> None:
    if isinstance(domain, PrimitiveType):
        if not domain.accepts(value):
            raise ValueError(f"value {value!r} not accepted by primitive type {domain}")
    else:
        if value not in domain.members:
            raise ValueError(f"value {value!r} not in domain members of {domain.label or 'Domain'}")


def _default_content(symbol: str, domain: PrimitiveType | Domain, value: Any | None) -> str:
    domain_name = domain.name if isinstance(domain, PrimitiveType) else (domain.label or "Domain")
    if value is None:
        return f"Variable {symbol}: {domain_name}"
    return f"Variable {symbol}: {domain_name} = {value!r}"
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pytest tests/gaia/lang/runtime/test_variable.py -v`
Expected: 11 passed.

- [ ] **Step 5: Lint and format**

Run: `ruff check gaia/lang/runtime/variable.py tests/gaia/lang/runtime/test_variable.py && ruff format gaia/lang/runtime/variable.py tests/gaia/lang/runtime/test_variable.py`
Expected: clean.

- [ ] **Step 6: Commit**

```bash
git add gaia/lang/runtime/variable.py tests/gaia/lang/runtime/test_variable.py
git commit -m "feat(lang): add Variable Knowledge subclass with typed domain"
```

---

## Task 4: Formula AST — Term Hierarchy

**Files:**
- Create: `gaia/lang/formula/__init__.py`
- Create: `gaia/lang/formula/term.py`
- Create: `tests/gaia/lang/formula/__init__.py`
- Create: `tests/gaia/lang/formula/test_term.py`

A Term is anything that has a value in a typed domain: a constant literal, a function application, an arithmetic combination, or a Variable reference. Variable already exists (Task 3) and will satisfy Term via Protocol — no inheritance changes there.

- [ ] **Step 1: Write the failing tests**

Create `tests/gaia/lang/formula/__init__.py` (empty) and `tests/gaia/lang/formula/test_term.py`:

```python
"""Tests for Formula AST Term hierarchy."""

from gaia.lang.formula.term import ArithOp, Constant, FunctionApp, Term, is_term
from gaia.lang.runtime.variable import Variable
from gaia.lang.types.primitives import Nat, Real


def test_constant_construction():
    c = Constant(value=395, primitive="Nat")
    assert c.value == 395
    assert c.primitive == "Nat"


def test_constant_equality():
    c1 = Constant(value=395, primitive="Nat")
    c2 = Constant(value=395, primitive="Nat")
    c3 = Constant(value=396, primitive="Nat")
    assert c1 == c2
    assert c1 != c3


def test_constant_is_term():
    c = Constant(value=1, primitive="Nat")
    assert is_term(c)


def test_variable_is_term():
    n = Variable(symbol="n", domain=Nat, value=395)
    assert is_term(n)


def test_function_app_construction():
    n = Variable(symbol="x", domain=Nat)
    fa = FunctionApp(symbol_name="E", args=(n,))
    assert fa.symbol_name == "E"
    assert fa.args == (n,)


def test_function_app_is_term():
    fa = FunctionApp(symbol_name="E", args=())
    assert is_term(fa)


def test_function_app_args_must_be_terms():
    import pytest
    with pytest.raises(TypeError, match="argument"):
        FunctionApp(symbol_name="E", args=("not_a_term",))  # type: ignore[arg-type]


def test_arith_op_basic():
    n = Variable(symbol="n", domain=Nat, value=395)
    k = Variable(symbol="k", domain=Nat, value=295)
    expr = ArithOp(op="+", left=n, right=k)
    assert expr.op == "+"
    assert expr.left is n
    assert expr.right is k


def test_arith_op_is_term():
    n = Variable(symbol="n", domain=Nat)
    expr = ArithOp(op="+", left=n, right=Constant(1, "Nat"))
    assert is_term(expr)


def test_arith_op_rejects_unknown_op():
    import pytest
    n = Variable(symbol="n", domain=Nat)
    with pytest.raises(ValueError, match="op"):
        ArithOp(op="??", left=n, right=Constant(1, "Nat"))


def test_arith_op_operands_must_be_terms():
    import pytest
    with pytest.raises(TypeError, match="left"):
        ArithOp(op="+", left="x", right=Constant(1, "Nat"))  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="right"):
        ArithOp(op="+", left=Constant(1, "Nat"), right="y")  # type: ignore[arg-type]


def test_term_protocol_does_not_match_arbitrary_objects():
    assert not is_term(395)
    assert not is_term("string")
    assert not is_term([Constant(1, "Nat")])


def test_nested_term_tree():
    """E(x + 1) > 0 — build a deep tree, walk it, confirm structure."""
    x = Variable(symbol="x", domain=Real)
    inner_arith = ArithOp(op="+", left=x, right=Constant(1, "Real"))
    e_call = FunctionApp(symbol_name="E", args=(inner_arith,))
    assert is_term(e_call)
    assert is_term(e_call.args[0])
    assert e_call.args[0].left is x
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest tests/gaia/lang/formula/test_term.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'gaia.lang.formula'`

- [ ] **Step 3: Implement Term hierarchy**

Create `gaia/lang/formula/__init__.py`:

```python
"""Gaia Lang Formula AST — term, predicate, connective, quantifier nodes.

This module defines the data shape only. Operator overloading and DSL helpers
(forall, exists, land, ...) live in gaia/lang/dsl/ and are introduced in
Milestone B. The compiler that lowers Formula → IR is also Milestone B.
"""

from gaia.lang.formula.term import ArithOp, Constant, FunctionApp, Term, is_term

__all__ = ["Term", "Constant", "FunctionApp", "ArithOp", "is_term"]
```

Create `gaia/lang/formula/term.py`:

```python
"""Term — value-bearing AST nodes (constants, function applications, arithmetic)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable


_ARITH_OPS = frozenset({"+", "-", "*", "/"})


@runtime_checkable
class Term(Protocol):
    """Marker protocol. A Term is a value-bearing expression node.

    Implementations: ``Constant``, ``FunctionApp``, ``ArithOp``, ``Variable``
    (defined in gaia.lang.runtime.variable). ``is_term`` performs a strict check
    that excludes arbitrary objects that happen to satisfy the empty protocol.
    """

    __gaia_term__: bool = True


def is_term(obj: object) -> bool:
    """Strict check — only objects explicitly tagged as terms qualify."""
    return getattr(obj, "__gaia_term__", False) is True


@dataclass(frozen=True)
class Constant:
    """A primitive literal value."""

    value: Any
    primitive: str  # name of a PrimitiveType ("Nat", "Real", "Probability", "Bool")
    __gaia_term__: bool = True


@dataclass(frozen=True)
class FunctionApp:
    """Application of a function symbol to a tuple of Term arguments."""

    symbol_name: str
    args: tuple[Term, ...]
    __gaia_term__: bool = True

    def __post_init__(self) -> None:
        for i, arg in enumerate(self.args):
            if not is_term(arg):
                raise TypeError(f"FunctionApp argument {i} is not a Term: {arg!r}")


@dataclass(frozen=True)
class ArithOp:
    """An arithmetic operation between two Terms."""

    op: str
    left: Term
    right: Term
    __gaia_term__: bool = True

    def __post_init__(self) -> None:
        if self.op not in _ARITH_OPS:
            raise ValueError(f"op must be one of {_ARITH_OPS}, got {self.op!r}")
        if not is_term(self.left):
            raise TypeError(f"ArithOp.left is not a Term: {self.left!r}")
        if not is_term(self.right):
            raise TypeError(f"ArithOp.right is not a Term: {self.right!r}")
```

Now mark Variable as a Term. Edit `gaia/lang/runtime/variable.py` and add the class attribute:

```python
@dataclass(init=False, eq=False)
class Variable(Knowledge):
    # ... existing class body ...

    __gaia_term__: bool = True  # Term protocol marker — see gaia.lang.formula.term
```

Insert the line right above the existing fields (`symbol`, `domain`, `value`).

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pytest tests/gaia/lang/formula/test_term.py tests/gaia/lang/runtime/test_variable.py -v`
Expected: all pass.

- [ ] **Step 5: Lint and format**

Run: `ruff check gaia/lang/formula gaia/lang/runtime/variable.py tests/gaia/lang/formula && ruff format gaia/lang/formula gaia/lang/runtime/variable.py tests/gaia/lang/formula`
Expected: clean.

- [ ] **Step 6: Commit**

```bash
git add gaia/lang/formula tests/gaia/lang/formula gaia/lang/runtime/variable.py
git commit -m "feat(lang): formula AST term layer (Constant/FunctionApp/ArithOp + Variable as Term)"
```

---

## Task 5: Formula AST — Predicate Hierarchy

**Files:**
- Create: `gaia/lang/formula/predicate.py`
- Test: `tests/gaia/lang/formula/test_predicate.py`

A Predicate is an atomic formula — a Boolean-valued expression over Terms (or, in the case of `ClaimAtom`, a reference to another Claim's truth). Inherits from a `Formula` marker. Compound formulas (Connectives, Quantifiers) build on top of Predicates in subsequent tasks.

- [ ] **Step 1: Write the failing tests**

Create `tests/gaia/lang/formula/test_predicate.py`:

```python
"""Tests for Formula AST Predicate hierarchy."""

import pytest

from gaia.lang.formula.predicate import (
    Causes,
    ClaimAtom,
    Equals,
    Formula,
    Greater,
    GreaterEqual,
    Less,
    LessEqual,
    NotEquals,
    UserPredicate,
    is_formula,
)
from gaia.lang.formula.term import Constant
from gaia.lang.runtime.knowledge import Claim
from gaia.lang.runtime.variable import Variable
from gaia.lang.types.primitives import Nat, Probability


def test_equals_basic():
    p = Variable(symbol="p", domain=Probability)
    eq = Equals(left=p, right=Constant(value=0.75, primitive="Probability"))
    assert eq.left is p
    assert eq.right.value == 0.75


def test_equals_is_formula():
    eq = Equals(left=Constant(1, "Nat"), right=Constant(1, "Nat"))
    assert is_formula(eq)


def test_equals_args_must_be_terms():
    with pytest.raises(TypeError):
        Equals(left="not_a_term", right=Constant(1, "Nat"))  # type: ignore[arg-type]


def test_comparisons():
    n = Variable(symbol="n", domain=Nat, value=395)
    z = Constant(value=0, primitive="Nat")
    assert isinstance(Greater(left=n, right=z), Formula)
    assert isinstance(Less(left=n, right=z), Formula)
    assert isinstance(GreaterEqual(left=n, right=z), Formula)
    assert isinstance(LessEqual(left=n, right=z), Formula)
    assert isinstance(NotEquals(left=n, right=z), Formula)


def test_claim_atom_holds_a_claim_reference():
    c = Claim(content="P", prior=0.5)
    atom = ClaimAtom(claim=c)
    assert atom.claim is c


def test_claim_atom_is_formula():
    c = Claim(content="P", prior=0.5)
    atom = ClaimAtom(claim=c)
    assert is_formula(atom)


def test_claim_atom_rejects_non_claim():
    with pytest.raises(TypeError, match="Claim"):
        ClaimAtom(claim="not_a_claim")  # type: ignore[arg-type]


def test_user_predicate():
    n = Variable(symbol="n", domain=Nat)
    pred = UserPredicate(symbol_name="Stable", args=(n,))
    assert pred.symbol_name == "Stable"
    assert pred.args == (n,)


def test_user_predicate_is_formula():
    pred = UserPredicate(symbol_name="P", args=(Constant(1, "Nat"),))
    assert is_formula(pred)


def test_user_predicate_args_must_be_terms():
    with pytest.raises(TypeError, match="argument"):
        UserPredicate(symbol_name="P", args=(123,))  # type: ignore[arg-type]


def test_causes_predicate():
    a = Variable(symbol="a", domain=Nat)
    b = Variable(symbol="b", domain=Nat)
    c = Causes(cause=a, effect=b)
    assert c.cause is a
    assert c.effect is b


def test_causes_is_formula():
    a = Variable(symbol="a", domain=Nat)
    b = Variable(symbol="b", domain=Nat)
    assert is_formula(Causes(cause=a, effect=b))


def test_is_formula_rejects_terms():
    """A Term alone is not a Formula — it has no truth value."""
    assert not is_formula(Constant(1, "Nat"))
    assert not is_formula(Variable(symbol="x", domain=Nat))


def test_is_formula_rejects_arbitrary():
    assert not is_formula("hello")
    assert not is_formula(42)
    assert not is_formula([Equals(Constant(1, "Nat"), Constant(1, "Nat"))])
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest tests/gaia/lang/formula/test_predicate.py -v`
Expected: FAIL with `ImportError: cannot import name 'Equals' from 'gaia.lang.formula.predicate'`

- [ ] **Step 3: Implement Predicate hierarchy**

Create `gaia/lang/formula/predicate.py`:

```python
"""Predicate — atomic formulas (truth-valued expressions over Terms or Claims)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from gaia.lang.formula.term import Term, is_term
from gaia.lang.runtime.knowledge import Claim


@runtime_checkable
class Formula(Protocol):
    """Marker protocol — a truth-valued AST node."""

    __gaia_formula__: bool = True


def is_formula(obj: object) -> bool:
    """Strict check — only objects explicitly tagged as formulas qualify."""
    return getattr(obj, "__gaia_formula__", False) is True


def _check_term(name: str, value: object) -> None:
    if not is_term(value):
        raise TypeError(f"{name} is not a Term: {value!r}")


@dataclass(frozen=True)
class Equals:
    left: Term
    right: Term
    __gaia_formula__: bool = True

    def __post_init__(self) -> None:
        _check_term("left", self.left)
        _check_term("right", self.right)


@dataclass(frozen=True)
class NotEquals:
    left: Term
    right: Term
    __gaia_formula__: bool = True

    def __post_init__(self) -> None:
        _check_term("left", self.left)
        _check_term("right", self.right)


@dataclass(frozen=True)
class Greater:
    left: Term
    right: Term
    __gaia_formula__: bool = True

    def __post_init__(self) -> None:
        _check_term("left", self.left)
        _check_term("right", self.right)


@dataclass(frozen=True)
class GreaterEqual:
    left: Term
    right: Term
    __gaia_formula__: bool = True

    def __post_init__(self) -> None:
        _check_term("left", self.left)
        _check_term("right", self.right)


@dataclass(frozen=True)
class Less:
    left: Term
    right: Term
    __gaia_formula__: bool = True

    def __post_init__(self) -> None:
        _check_term("left", self.left)
        _check_term("right", self.right)


@dataclass(frozen=True)
class LessEqual:
    left: Term
    right: Term
    __gaia_formula__: bool = True

    def __post_init__(self) -> None:
        _check_term("left", self.left)
        _check_term("right", self.right)


@dataclass(frozen=True)
class UserPredicate:
    """Application of a user-declared predicate symbol to Term arguments."""

    symbol_name: str
    args: tuple[Term, ...]
    __gaia_formula__: bool = True

    def __post_init__(self) -> None:
        for i, arg in enumerate(self.args):
            if not is_term(arg):
                raise TypeError(f"UserPredicate argument {i} is not a Term: {arg!r}")


@dataclass(frozen=True)
class Causes:
    """Built-in causal predicate. v0.5: marker only; v0.6: interventional factor."""

    cause: Term
    effect: Term
    __gaia_formula__: bool = True

    def __post_init__(self) -> None:
        _check_term("cause", self.cause)
        _check_term("effect", self.effect)


@dataclass(frozen=True)
class ClaimAtom:
    """A reference to another Claim's truth — the bridge from formula land to claim graph."""

    claim: Claim
    __gaia_formula__: bool = True

    def __post_init__(self) -> None:
        if not isinstance(self.claim, Claim):
            raise TypeError(f"ClaimAtom requires a Claim instance, got {type(self.claim).__name__}")
```

Update `gaia/lang/formula/__init__.py` to re-export:

```python
"""Gaia Lang Formula AST — term, predicate, connective, quantifier nodes."""

from gaia.lang.formula.predicate import (
    Causes,
    ClaimAtom,
    Equals,
    Formula,
    Greater,
    GreaterEqual,
    Less,
    LessEqual,
    NotEquals,
    UserPredicate,
    is_formula,
)
from gaia.lang.formula.term import ArithOp, Constant, FunctionApp, Term, is_term

__all__ = [
    # term
    "Term",
    "Constant",
    "FunctionApp",
    "ArithOp",
    "is_term",
    # formula
    "Formula",
    "is_formula",
    "Equals",
    "NotEquals",
    "Greater",
    "GreaterEqual",
    "Less",
    "LessEqual",
    "UserPredicate",
    "Causes",
    "ClaimAtom",
]
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pytest tests/gaia/lang/formula/ -v`
Expected: all term + predicate tests pass.

- [ ] **Step 5: Lint and format**

Run: `ruff check gaia/lang/formula tests/gaia/lang/formula && ruff format gaia/lang/formula tests/gaia/lang/formula`
Expected: clean.

- [ ] **Step 6: Commit**

```bash
git add gaia/lang/formula tests/gaia/lang/formula
git commit -m "feat(lang): formula AST predicate layer (Equals/<,>,>=,<=,!= + UserPredicate/Causes/ClaimAtom)"
```

---

## Task 6: Formula AST — Connectives and Quantifiers

**Files:**
- Create: `gaia/lang/formula/connective.py`
- Create: `gaia/lang/formula/quantifier.py`
- Test: `tests/gaia/lang/formula/test_connective.py`
- Test: `tests/gaia/lang/formula/test_quantifier.py`

Connectives (∧, ∨, ¬, →, ↔) and quantifiers (∀, ∃) compose Formulas into compound Formulas. Each is a frozen dataclass with `__gaia_formula__ = True` so it satisfies the Formula protocol; sub-Formulas are validated in `__post_init__`.

- [ ] **Step 1: Write the failing tests for connectives**

Create `tests/gaia/lang/formula/test_connective.py`:

```python
"""Tests for Formula AST connectives."""

import pytest

from gaia.lang.formula.connective import Iff, Implies, Land, Lnot, Lor
from gaia.lang.formula.predicate import Equals, is_formula
from gaia.lang.formula.term import Constant


def _atom(v: int) -> Equals:
    return Equals(left=Constant(v, "Nat"), right=Constant(v, "Nat"))


def test_land_two_args():
    a = _atom(1)
    b = _atom(2)
    f = Land(operands=(a, b))
    assert f.operands == (a, b)
    assert is_formula(f)


def test_land_n_args():
    f = Land(operands=tuple(_atom(i) for i in range(5)))
    assert len(f.operands) == 5


def test_land_requires_at_least_two():
    with pytest.raises(ValueError, match="at least two"):
        Land(operands=(_atom(1),))


def test_land_operands_must_be_formulas():
    with pytest.raises(TypeError, match="not a Formula"):
        Land(operands=(_atom(1), "not_a_formula"))  # type: ignore[arg-type]


def test_lor_basic():
    a, b = _atom(1), _atom(2)
    f = Lor(operands=(a, b))
    assert is_formula(f)


def test_lnot_single_operand():
    a = _atom(1)
    f = Lnot(operand=a)
    assert f.operand is a
    assert is_formula(f)


def test_lnot_operand_must_be_formula():
    with pytest.raises(TypeError, match="not a Formula"):
        Lnot(operand="x")  # type: ignore[arg-type]


def test_implies_basic():
    a, b = _atom(1), _atom(2)
    f = Implies(antecedent=a, consequent=b)
    assert f.antecedent is a
    assert f.consequent is b
    assert is_formula(f)


def test_iff_basic():
    a, b = _atom(1), _atom(2)
    f = Iff(left=a, right=b)
    assert is_formula(f)


def test_nested_compound():
    a, b, c = _atom(1), _atom(2), _atom(3)
    inner = Lor(operands=(a, b))
    outer = Land(operands=(inner, Lnot(operand=c)))
    assert is_formula(outer)
    assert outer.operands[0].operands[0] is a
```

- [ ] **Step 2: Run the failing tests**

Run: `pytest tests/gaia/lang/formula/test_connective.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement connectives**

Create `gaia/lang/formula/connective.py`:

```python
"""Connectives — compound formulas built from sub-formulas."""

from __future__ import annotations

from dataclasses import dataclass

from gaia.lang.formula.predicate import Formula, is_formula


def _check_formula(name: str, value: object) -> None:
    if not is_formula(value):
        raise TypeError(f"{name} is not a Formula: {value!r}")


@dataclass(frozen=True)
class Land:
    """Logical conjunction over two or more sub-formulas."""

    operands: tuple[Formula, ...]
    __gaia_formula__: bool = True

    def __post_init__(self) -> None:
        if len(self.operands) < 2:
            raise ValueError("Land requires at least two operands")
        for i, op in enumerate(self.operands):
            if not is_formula(op):
                raise TypeError(f"Land.operands[{i}] is not a Formula: {op!r}")


@dataclass(frozen=True)
class Lor:
    """Logical disjunction over two or more sub-formulas."""

    operands: tuple[Formula, ...]
    __gaia_formula__: bool = True

    def __post_init__(self) -> None:
        if len(self.operands) < 2:
            raise ValueError("Lor requires at least two operands")
        for i, op in enumerate(self.operands):
            if not is_formula(op):
                raise TypeError(f"Lor.operands[{i}] is not a Formula: {op!r}")


@dataclass(frozen=True)
class Lnot:
    """Logical negation."""

    operand: Formula
    __gaia_formula__: bool = True

    def __post_init__(self) -> None:
        _check_formula("operand", self.operand)


@dataclass(frozen=True)
class Implies:
    """Material implication."""

    antecedent: Formula
    consequent: Formula
    __gaia_formula__: bool = True

    def __post_init__(self) -> None:
        _check_formula("antecedent", self.antecedent)
        _check_formula("consequent", self.consequent)


@dataclass(frozen=True)
class Iff:
    """Material biconditional."""

    left: Formula
    right: Formula
    __gaia_formula__: bool = True

    def __post_init__(self) -> None:
        _check_formula("left", self.left)
        _check_formula("right", self.right)
```

- [ ] **Step 4: Run connective tests, verify pass**

Run: `pytest tests/gaia/lang/formula/test_connective.py -v`
Expected: all pass.

- [ ] **Step 5: Write quantifier tests**

Create `tests/gaia/lang/formula/test_quantifier.py`:

```python
"""Tests for Formula AST quantifiers."""

import pytest

from gaia.lang.formula.predicate import Equals, is_formula
from gaia.lang.formula.quantifier import Exists, Forall
from gaia.lang.formula.term import Constant
from gaia.lang.runtime.domain import Domain
from gaia.lang.runtime.variable import Variable
from gaia.lang.types.primitives import Nat


def _body() -> Equals:
    return Equals(left=Constant(1, "Nat"), right=Constant(1, "Nat"))


def test_forall_with_primitive_domain_variable():
    x = Variable(symbol="x", domain=Nat)
    q = Forall(variable=x, body=_body())
    assert q.variable is x
    assert is_formula(q)


def test_forall_with_custom_domain_variable():
    Particle = Domain(content="x", members=["p1", "p2"])
    x = Variable(symbol="x", domain=Particle)
    q = Forall(variable=x, body=_body())
    assert q.variable is x


def test_forall_variable_must_be_variable():
    with pytest.raises(TypeError, match="Variable"):
        Forall(variable="x", body=_body())  # type: ignore[arg-type]


def test_forall_body_must_be_formula():
    x = Variable(symbol="x", domain=Nat)
    with pytest.raises(TypeError, match="body"):
        Forall(variable=x, body="not_formula")  # type: ignore[arg-type]


def test_forall_with_bound_variable_rejected():
    """A variable that already has a value is not eligible for quantification."""
    x = Variable(symbol="x", domain=Nat, value=0)
    with pytest.raises(ValueError, match="bound"):
        Forall(variable=x, body=_body())


def test_exists_basic():
    x = Variable(symbol="x", domain=Nat)
    q = Exists(variable=x, body=_body())
    assert is_formula(q)


def test_exists_same_validations():
    x = Variable(symbol="x", domain=Nat, value=0)
    with pytest.raises(ValueError, match="bound"):
        Exists(variable=x, body=_body())
```

- [ ] **Step 6: Run quantifier tests, see them fail**

Run: `pytest tests/gaia/lang/formula/test_quantifier.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 7: Implement quantifiers**

Create `gaia/lang/formula/quantifier.py`:

```python
"""Quantifiers — universal and existential binding of a Variable inside a body Formula."""

from __future__ import annotations

from dataclasses import dataclass

from gaia.lang.formula.predicate import Formula, is_formula
from gaia.lang.runtime.variable import Variable


def _check(variable: object, body: object) -> None:
    if not isinstance(variable, Variable):
        raise TypeError(f"variable must be a Variable, got {type(variable).__name__}")
    if variable.value is not None:
        raise ValueError(
            f"variable {variable.symbol!r} is already bound to a value; "
            "quantifiers must bind FREE variables"
        )
    if not is_formula(body):
        raise TypeError(f"body is not a Formula: {body!r}")


@dataclass(frozen=True)
class Forall:
    """Universal quantification: ∀ variable: body."""

    variable: Variable
    body: Formula
    __gaia_formula__: bool = True

    def __post_init__(self) -> None:
        _check(self.variable, self.body)


@dataclass(frozen=True)
class Exists:
    """Existential quantification: ∃ variable: body."""

    variable: Variable
    body: Formula
    __gaia_formula__: bool = True

    def __post_init__(self) -> None:
        _check(self.variable, self.body)
```

Update `gaia/lang/formula/__init__.py` to re-export connectives and quantifiers:

```python
"""Gaia Lang Formula AST — term, predicate, connective, quantifier nodes."""

from gaia.lang.formula.connective import Iff, Implies, Land, Lnot, Lor
from gaia.lang.formula.predicate import (
    Causes,
    ClaimAtom,
    Equals,
    Formula,
    Greater,
    GreaterEqual,
    Less,
    LessEqual,
    NotEquals,
    UserPredicate,
    is_formula,
)
from gaia.lang.formula.quantifier import Exists, Forall
from gaia.lang.formula.term import ArithOp, Constant, FunctionApp, Term, is_term

__all__ = [
    # term
    "Term",
    "Constant",
    "FunctionApp",
    "ArithOp",
    "is_term",
    # formula base
    "Formula",
    "is_formula",
    # atomic predicates
    "Equals",
    "NotEquals",
    "Greater",
    "GreaterEqual",
    "Less",
    "LessEqual",
    "UserPredicate",
    "Causes",
    "ClaimAtom",
    # connectives
    "Land",
    "Lor",
    "Lnot",
    "Implies",
    "Iff",
    # quantifiers
    "Forall",
    "Exists",
]
```

- [ ] **Step 8: Run quantifier and full formula tests**

Run: `pytest tests/gaia/lang/formula/ -v`
Expected: all pass.

- [ ] **Step 9: Lint and format**

Run: `ruff check gaia/lang/formula tests/gaia/lang/formula && ruff format gaia/lang/formula tests/gaia/lang/formula`
Expected: clean.

- [ ] **Step 10: Commit**

```bash
git add gaia/lang/formula tests/gaia/lang/formula
git commit -m "feat(lang): formula AST connectives and quantifiers"
```

---

## Task 7: Function and Predicate Symbol Declarations

**Files:**
- Create: `gaia/lang/formula/symbols.py`
- Test: `tests/gaia/lang/formula/test_symbols.py`

`FunctionSymbol` and `PredicateSymbol` are typed declarations of named symbols (`E: Particle → Real`, `Stable: Particle → Bool`). They are constructed via the `function(...)` and `predicate(...)` helpers (DSL is Milestone B; in Milestone A we ship just the dataclass for direct construction in tests and IR consumers).

- [ ] **Step 1: Write the failing tests**

Create `tests/gaia/lang/formula/test_symbols.py`:

```python
"""Tests for FunctionSymbol and PredicateSymbol declarations."""

import pytest

from gaia.lang.formula.symbols import FunctionSymbol, PredicateSymbol
from gaia.lang.runtime.domain import Domain
from gaia.lang.types.primitives import Nat, Real


def test_function_symbol_basic():
    f = FunctionSymbol(name="E", arg_domains=(Nat,), result_domain=Real)
    assert f.name == "E"
    assert f.arg_domains == (Nat,)
    assert f.result_domain is Real


def test_function_symbol_multi_arity():
    f = FunctionSymbol(name="V", arg_domains=(Nat, Nat), result_domain=Real)
    assert f.arg_domains == (Nat, Nat)


def test_function_symbol_name_required():
    with pytest.raises(ValueError, match="name"):
        FunctionSymbol(name="", arg_domains=(Nat,), result_domain=Real)


def test_function_symbol_arg_domains_must_be_typed():
    with pytest.raises(TypeError, match="arg_domain"):
        FunctionSymbol(name="E", arg_domains=("Nat",), result_domain=Real)  # type: ignore[arg-type]


def test_function_symbol_with_custom_domain():
    Particle = Domain(content="x", members=["p1"])
    f = FunctionSymbol(name="E", arg_domains=(Particle,), result_domain=Real)
    assert f.arg_domains == (Particle,)


def test_predicate_symbol_basic():
    p = PredicateSymbol(name="Stable", arg_domains=(Nat,))
    assert p.name == "Stable"
    assert p.arg_domains == (Nat,)


def test_predicate_symbol_zero_arity_disallowed():
    """A predicate with no arguments would just be a propositional atom — use a Claim instead."""
    with pytest.raises(ValueError, match="arity"):
        PredicateSymbol(name="P", arg_domains=())


def test_function_symbol_zero_arity_disallowed():
    """Same reasoning — use a Variable for nullary terms."""
    with pytest.raises(ValueError, match="arity"):
        FunctionSymbol(name="f", arg_domains=(), result_domain=Real)
```

- [ ] **Step 2: Run the failing tests**

Run: `pytest tests/gaia/lang/formula/test_symbols.py -v`
Expected: FAIL with `ImportError`.

- [ ] **Step 3: Implement symbol declarations**

Create `gaia/lang/formula/symbols.py`:

```python
"""FunctionSymbol and PredicateSymbol — typed declarations of user-defined symbols."""

from __future__ import annotations

from dataclasses import dataclass

from gaia.lang.runtime.domain import Domain
from gaia.lang.types.primitives import PrimitiveType


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
        if not self.name:
            raise ValueError("name must be a non-empty string")
        _validate_arg_domains(self.arg_domains)
```

Update `gaia/lang/formula/__init__.py` re-exports — add `FunctionSymbol` and `PredicateSymbol`:

```python
from gaia.lang.formula.symbols import FunctionSymbol, PredicateSymbol
```

And add them to `__all__`:

```python
__all__ = [
    # ... previous entries ...
    "FunctionSymbol",
    "PredicateSymbol",
]
```

- [ ] **Step 4: Run tests, verify pass**

Run: `pytest tests/gaia/lang/formula/ -v`
Expected: all pass.

- [ ] **Step 5: Lint and format**

Run: `ruff check gaia/lang/formula tests/gaia/lang/formula && ruff format gaia/lang/formula tests/gaia/lang/formula`
Expected: clean.

- [ ] **Step 6: Commit**

```bash
git add gaia/lang/formula tests/gaia/lang/formula
git commit -m "feat(lang): FunctionSymbol and PredicateSymbol declarations"
```

---

## Task 8: Extend Claim with `formula` and `kind` Fields

**Files:**
- Modify: `gaia/lang/runtime/knowledge.py`
- Test: `tests/gaia/lang/runtime/test_claim_formula_kind.py`

Add two new optional fields to `Claim`: `formula: Formula | None` (default None) and `kind: ClaimKind` (default `ClaimKind.GENERAL`). The new `ClaimKind` enum lives in `knowledge.py`. Existing claim authoring is unaffected — both fields default to "no structured content, generic kind".

- [ ] **Step 1: Write the failing tests**

Create `tests/gaia/lang/runtime/test_claim_formula_kind.py`:

```python
"""Tests for Claim.formula and Claim.kind extensions."""

import pytest

from gaia.lang.formula.predicate import Equals
from gaia.lang.formula.term import Constant
from gaia.lang.runtime.knowledge import Claim, ClaimKind
from gaia.lang.runtime.variable import Variable
from gaia.lang.types.primitives import Probability


def test_claim_default_formula_is_none():
    c = Claim(content="P", prior=0.5)
    assert c.formula is None


def test_claim_default_kind_is_general():
    c = Claim(content="P", prior=0.5)
    assert c.kind is ClaimKind.GENERAL


def test_claim_with_formula():
    p = Variable(symbol="p", domain=Probability)
    eq = Equals(left=p, right=Constant(0.75, "Probability"))
    c = Claim(content="Mendelian", formula=eq, prior=0.5)
    assert c.formula is eq


def test_claim_with_explicit_kind():
    p = Variable(symbol="p", domain=Probability)
    eq = Equals(left=p, right=Constant(0.75, "Probability"))
    c = Claim(content="Mendelian", formula=eq, kind=ClaimKind.PARAMETER, prior=0.5)
    assert c.kind is ClaimKind.PARAMETER


def test_claim_kind_enum_values():
    assert {k.value for k in ClaimKind} == {
        "general",
        "parameter",
        "observation",
        "quantified",
        "causal",
    }


def test_claim_formula_must_be_formula_or_none():
    with pytest.raises(TypeError, match="formula"):
        Claim(content="P", formula="not_a_formula", prior=0.5)  # type: ignore[arg-type]


def test_claim_kind_must_be_claimkind_member():
    p = Variable(symbol="p", domain=Probability)
    eq = Equals(left=p, right=Constant(0.75, "Probability"))
    with pytest.raises(TypeError, match="kind"):
        Claim(content="P", formula=eq, kind="parameter", prior=0.5)  # type: ignore[arg-type]


def test_existing_claim_construction_unchanged():
    """Authoring a plain Claim like in v0.5 still works — formula/kind are opt-in."""
    c = Claim(
        content="Mendelian 3:1 segregation holds.",
        prior=0.5,
    )
    assert c.formula is None
    assert c.kind is ClaimKind.GENERAL
    assert c.prior == 0.5
```

- [ ] **Step 2: Run the failing tests**

Run: `pytest tests/gaia/lang/runtime/test_claim_formula_kind.py -v`
Expected: FAIL with `ImportError: cannot import name 'ClaimKind'`.

- [ ] **Step 3: Add ClaimKind enum and extend Claim**

Edit `gaia/lang/runtime/knowledge.py`. Locate the existing `Claim` definition (around line 95). Add the import for the formula protocol at the top of the file:

```python
from gaia.lang.formula.predicate import is_formula
```

Add the `ClaimKind` enum just above the `Claim` class:

```python
class ClaimKind(Enum):
    """Discriminator for the structured-content shape of a Claim.

    GENERAL      — default; formula optional, no structural commitments
    PARAMETER    — asserts a Variable takes a specific value (Equals(var, const))
    OBSERVATION  — records observed values for one or more Variables
    QUANTIFIED   — top-level quantifier (Forall/Exists) in formula
    CAUSAL       — top-level Causes(...) predicate in formula
    """

    GENERAL = "general"
    PARAMETER = "parameter"
    OBSERVATION = "observation"
    QUANTIFIED = "quantified"
    CAUSAL = "causal"
```

Then extend the `Claim` class. The current structure uses `@dataclass(init=False, eq=False)` with a custom `__init__` (look at how `Note`, `Setting` do it). Add the two new fields and validate them in `__init__`. The relevant patch:

```python
@dataclass(init=False, eq=False)
class Claim(Knowledge):
    """Proposition with prior. Participates in BP."""

    prior: float | None = None
    grounding: Grounding | None = None
    supports: list[Action] = field(default_factory=list)
    formula: Any = None  # Formula | None — runtime check via is_formula
    kind: ClaimKind = ClaimKind.GENERAL
    _param_fields: ClassVar[dict[str, Any]] = {}
```

Find Claim's `__init__` (it's not currently in the file because Claim today inherits its dataclass `__init__`). Looking at the existing structure, Claim is a plain `@dataclass(init=False, eq=False)` with `__init_subclass__` building `_param_fields`. The dataclass-generated init handles fields. **However** the current code uses `init=False` AND has no manual `__init__` for Claim itself, because Claim is constructed via the same call signature as Knowledge plus Claim-specific fields, dispatched through `Knowledge.__init__`'s `**kwargs`.

Inspect the file once more before editing to confirm the current init pattern. The implementation should:

1. Add `formula` and `kind` to the `_base_fields` whitelist used by `__init_subclass__`.
2. Validate `formula` and `kind` in `__post_init__` or in a wrapper init — given Claim uses `init=False` and Knowledge uses `__post_init__`, add a `__post_init__` on `Claim` (or extend the one if it already exists) that validates these two fields.

Patch:

```python
@dataclass(init=False, eq=False)
class Claim(Knowledge):
    """Proposition with prior. Participates in BP."""

    prior: float | None = None
    grounding: Grounding | None = None
    supports: list[Action] = field(default_factory=list)
    formula: Any = None
    kind: ClaimKind = ClaimKind.GENERAL
    _param_fields: ClassVar[dict[str, Any]] = {}

    def __init__(
        self,
        content: str,
        *,
        format: str = "markdown",
        prior: float | None = None,
        grounding: Grounding | None = None,
        formula: Any = None,
        kind: ClaimKind = ClaimKind.GENERAL,
        **kwargs,
    ):
        if formula is not None and not is_formula(formula):
            raise TypeError(f"formula must be a Formula or None, got {type(formula).__name__}")
        if not isinstance(kind, ClaimKind):
            raise TypeError(f"kind must be a ClaimKind member, got {type(kind).__name__}")
        super().__init__(content=content, type="claim", format=format, **kwargs)
        self.prior = prior
        self.grounding = grounding
        self.supports = []
        self.formula = formula
        self.kind = kind
```

Update the `__init_subclass__` `base_fields` set to include the new fields:

```python
        base_fields = {
            "content",
            "format",
            "type",
            "title",
            "background",
            "parameters",
            "provenance",
            "metadata",
            "label",
            "strategy",
            "prior",
            "grounding",
            "supports",
            "targets",
            "formula",   # NEW
            "kind",      # NEW
        }
```

- [ ] **Step 4: Run the new tests, verify pass**

Run: `pytest tests/gaia/lang/runtime/test_claim_formula_kind.py -v`
Expected: 8 passed.

- [ ] **Step 5: Run the full Lang test suite to confirm no regression**

Run: `pytest tests/gaia/lang/ -v`
Expected: all existing tests still pass; new tests pass.

If any existing test fails because of the explicit `formula`/`kind` parameters now being required-named, fix the test by updating signature mismatches. If failures are because the default behavior changed, the patch above is wrong — revisit `__init__` to ensure `formula=None` and `kind=ClaimKind.GENERAL` are truly the defaults and existing zero-arg paths still work.

- [ ] **Step 6: Lint and format**

Run: `ruff check gaia/lang/runtime/knowledge.py tests/gaia/lang/runtime/test_claim_formula_kind.py && ruff format gaia/lang/runtime/knowledge.py tests/gaia/lang/runtime/test_claim_formula_kind.py`
Expected: clean.

- [ ] **Step 7: Commit**

```bash
git add gaia/lang/runtime/knowledge.py tests/gaia/lang/runtime/test_claim_formula_kind.py
git commit -m "feat(lang): add Claim.formula and Claim.kind (ClaimKind enum)"
```

---

## Task 9: Public Exports

**Files:**
- Modify: `gaia/lang/runtime/__init__.py`
- Modify: `gaia/lang/__init__.py`

Surface the new types at the package boundaries so authors and downstream code can `from gaia.lang import Variable, Domain, Forall, Equals, ...`. This is wiring only — no logic.

- [ ] **Step 1: Inspect current exports**

Run: `grep -n "from gaia.lang" gaia/lang/__init__.py | head -30`
Run: `cat gaia/lang/runtime/__init__.py`

Read the existing exports to keep the new ones in alphabetical (or grouped) consistency.

- [ ] **Step 2: Update `gaia/lang/runtime/__init__.py`**

Add `Domain`, `Variable`, and `ClaimKind` to the imports and `__all__`:

```python
from gaia.lang.runtime.domain import Domain
from gaia.lang.runtime.knowledge import (
    Claim,
    ClaimKind,        # NEW
    Knowledge,
    Note,
    Question,
    # ... whatever else was already imported here
)
from gaia.lang.runtime.variable import Variable

# ... existing imports ...

__all__ = [
    # ... existing entries ...
    "Domain",
    "Variable",
    "ClaimKind",
]
```

- [ ] **Step 3: Update `gaia/lang/__init__.py`**

Add the formula module re-exports and the new runtime types. Find the existing `from gaia.lang.runtime import (...)` block and append:

```python
from gaia.lang.runtime import (
    # ... existing names ...
    ClaimKind,
    Domain,
    Variable,
)

from gaia.lang.formula import (
    ArithOp,
    Causes,
    ClaimAtom,
    Constant,
    Equals,
    Exists,
    Forall,
    Formula,
    FunctionApp,
    FunctionSymbol,
    Greater,
    GreaterEqual,
    Iff,
    Implies,
    Land,
    Less,
    LessEqual,
    Lnot,
    Lor,
    NotEquals,
    PredicateSymbol,
    Term,
    UserPredicate,
    is_formula,
    is_term,
)

from gaia.lang.types.primitives import Bool, Nat, Probability, Real
```

Add all the new names to `__all__` (alphabetical with existing entries).

- [ ] **Step 4: Add a smoke test for the public surface**

Create `tests/gaia/lang/test_public_surface_milestone_a.py`:

```python
"""Smoke test — every name introduced in Milestone A is reachable from the top of `gaia.lang`."""


def test_milestone_a_public_surface():
    import gaia.lang as lang

    expected = {
        # primitives
        "Nat", "Real", "Probability", "Bool",
        # knowledge
        "Variable", "Domain", "ClaimKind",
        # formula AST
        "Term", "Constant", "FunctionApp", "ArithOp", "is_term",
        "Formula", "is_formula",
        "Equals", "NotEquals", "Greater", "GreaterEqual", "Less", "LessEqual",
        "UserPredicate", "Causes", "ClaimAtom",
        "Land", "Lor", "Lnot", "Implies", "Iff",
        "Forall", "Exists",
        "FunctionSymbol", "PredicateSymbol",
    }
    missing = expected - set(dir(lang))
    assert not missing, f"missing public exports: {sorted(missing)}"
```

- [ ] **Step 5: Run the smoke test**

Run: `pytest tests/gaia/lang/test_public_surface_milestone_a.py -v`
Expected: passes.

- [ ] **Step 6: Run the full Lang suite**

Run: `pytest tests/gaia/lang/ -v`
Expected: all tests pass.

- [ ] **Step 7: Lint and format**

Run: `ruff check gaia/lang tests/gaia/lang && ruff format gaia/lang tests/gaia/lang`
Expected: clean.

- [ ] **Step 8: Commit**

```bash
git add gaia/lang/__init__.py gaia/lang/runtime/__init__.py tests/gaia/lang/test_public_surface_milestone_a.py
git commit -m "feat(lang): export Milestone A surface (Variable/Domain/Formula AST/primitives)"
```

---

## Task 10: End-to-end smoke test — construct the Mendel example formulas

**Files:**
- Create: `tests/gaia/lang/test_milestone_a_smoke.py`

Build the data shapes for the Mendel example **using only the AST node constructors** (no DSL, no compiler). Confirm the entire structure can be instantiated, walked, and equality-compared. This is the integration check that everything wires together.

- [ ] **Step 1: Write the smoke test**

Create `tests/gaia/lang/test_milestone_a_smoke.py`:

```python
"""End-to-end Milestone A smoke — build Mendel example with raw AST constructors."""

from gaia.lang import (
    Causes,
    Claim,
    ClaimKind,
    Constant,
    Domain,
    Equals,
    Forall,
    FunctionApp,
    FunctionSymbol,
    Greater,
    Land,
    Lnot,
    Nat,
    Probability,
    Real,
    UserPredicate,
    Variable,
    is_formula,
)


def test_mendel_parameter_assertion():
    """H = "Mendelian 3:1: P(dominant) = 0.75" with formula = Equals(p, 0.75)."""
    p = Variable(symbol="p", domain=Probability)
    H = Claim(
        content="Mendelian 3:1 segregation: P(dominant) = 0.75.",
        formula=Equals(left=p, right=Constant(0.75, "Probability")),
        kind=ClaimKind.PARAMETER,
        prior=0.5,
    )
    assert H.kind is ClaimKind.PARAMETER
    assert is_formula(H.formula)
    assert H.formula.left is p


def test_mendel_observation():
    """D = "295 of 395 F2 plants are dominant" with conjunction of Equals."""
    n_obs = Variable(symbol="n_obs", domain=Nat, value=395)
    k_obs = Variable(symbol="k_obs", domain=Nat, value=295)
    n = Variable(symbol="n", domain=Nat)
    k = Variable(symbol="k", domain=Nat)
    formula = Land(
        operands=(
            Equals(left=n, right=n_obs),
            Equals(left=k, right=k_obs),
        )
    )
    D = Claim(
        content="295 of 395 F2 plants are dominant.",
        formula=formula,
        kind=ClaimKind.OBSERVATION,
        prior=0.95,
    )
    assert is_formula(D.formula)
    assert D.kind is ClaimKind.OBSERVATION
    assert len(D.formula.operands) == 2


def test_universal_law_with_quantifier():
    """All particles have positive energy: Forall(x, E(x) > 0)."""
    Particle = Domain(content="Subatomic particles", members=["p1", "p2", "p3"])
    x = Variable(symbol="x", domain=Particle)
    E = FunctionSymbol(name="E", arg_domains=(Particle,), result_domain=Real)
    body = Greater(
        left=FunctionApp(symbol_name=E.name, args=(x,)),
        right=Constant(0, "Real"),
    )
    universal = Claim(
        content="All particles have positive energy.",
        formula=Forall(variable=x, body=body),
        kind=ClaimKind.QUANTIFIED,
        prior=0.95,
    )
    assert universal.kind is ClaimKind.QUANTIFIED
    assert is_formula(universal.formula)
    assert universal.formula.variable is x


def test_causal_claim():
    """Rising CO₂ causes increased temperature."""
    co2 = Variable(symbol="co2", domain=Real)
    temp = Variable(symbol="temp", domain=Real)
    C = Claim(
        content="Rising CO₂ causes increased global mean temperature.",
        formula=Causes(cause=co2, effect=temp),
        kind=ClaimKind.CAUSAL,
        prior=0.9,
    )
    assert C.kind is ClaimKind.CAUSAL
    assert C.formula.cause is co2


def test_compound_formula_round_trip():
    """¬(P ∧ ¬Q) — sanity check on connective composition."""
    P = Equals(left=Constant(1, "Nat"), right=Constant(1, "Nat"))
    Q = Equals(left=Constant(2, "Nat"), right=Constant(2, "Nat"))
    f = Lnot(operand=Land(operands=(P, Lnot(operand=Q))))
    assert is_formula(f)
    assert is_formula(f.operand)
    assert is_formula(f.operand.operands[0])


def test_user_predicate_in_compound():
    """Land(Stable(x), Stable(y)) — user predicates compose with connectives."""
    a = Variable(symbol="a", domain=Nat)
    b = Variable(symbol="b", domain=Nat)
    f = Land(
        operands=(
            UserPredicate(symbol_name="Stable", args=(a,)),
            UserPredicate(symbol_name="Stable", args=(b,)),
        )
    )
    assert is_formula(f)
    assert len(f.operands) == 2
```

- [ ] **Step 2: Run the smoke test**

Run: `pytest tests/gaia/lang/test_milestone_a_smoke.py -v`
Expected: 6 passed.

- [ ] **Step 3: Run the entire Lang suite to confirm no regression**

Run: `pytest tests/gaia/lang/ -v`
Expected: all pass.

- [ ] **Step 4: Run the full repo suite (Neo4j tests auto-skip if unavailable)**

Run: `pytest`
Expected: existing test counts intact, plus the new tests pass.

- [ ] **Step 5: Lint and format final pass**

Run: `ruff check . && ruff format --check .`
Expected: clean.

- [ ] **Step 6: Commit**

```bash
git add tests/gaia/lang/test_milestone_a_smoke.py
git commit -m "test(lang): Milestone A end-to-end smoke (Mendel + universal + causal)"
```

---

## Wrap-up After Task 10

- [ ] Push branch and open / update PR against `v0.5`:

```bash
git push origin feat/v05-claim-formula-schema
# PR #505 already exists with the spec; this milestone's commits go on the same branch.
# Or open a new PR for just-the-implementation if desired.
```

- [ ] Verify CI is green:

```bash
gh run list --branch feat/v05-claim-formula-schema --limit 1
```

If CI fails:

```bash
gh run view <run-id> --log-failed
# Fix the issue, push a new commit; do NOT amend or force-push.
```

- [ ] Tag the commit that finishes Milestone A so Milestones B and C can branch off cleanly:

```bash
git tag v0.5-milestone-a
git push origin v0.5-milestone-a
```

- [ ] Author Milestone B's plan in a follow-up.

---

## Self-Review Notes

**Spec coverage check:**

| Spec section | Task |
|---|---|
| §2.1 Variable | Task 3 |
| §2.2 Domain | Task 2 |
| §2.3 Primitive types (built-in) | Task 1 |
| §3.1 Term | Task 4 |
| §3.2 Predicate (incl. ClaimAtom, Causes, UserPredicate) | Task 5 |
| §3.3 Connectives & Quantifiers | Task 6 |
| §3.4 Function symbol declaration | Task 7 |
| §3.5 User-declared predicate symbol | Task 7 |
| §4 Claim extension (formula, kind) | Task 8 |
| Public DSL surface | Task 9 (export only — no operator overloading; that's Milestone B) |
| §5 Author DSL (operator overloading, sugar) | **Out of scope** — Milestone B |
| §6 Variable binding inference | **Out of scope** — Milestone B |
| §7 Compiler lowering | **Out of scope** — Milestone B |
| §8 Migration | **Out of scope** — Milestone C |
| §10 v0.6+ deferrals | Documented in spec; no work in this milestone |

**Type/method consistency:**

- `__gaia_term__` and `__gaia_formula__` are the protocol markers across all AST node classes — consistent.
- `Variable` declared in Task 3 carries `__gaia_term__` after Task 4's edit; tested in Task 4 step 4.
- `is_term` and `is_formula` are the two strict checks; used uniformly in `__post_init__` validations.
- `ClaimKind` values: `general / parameter / observation / quantified / causal` — consistent between Task 8 and Task 10 smoke test.

**Anticipated friction:**

- Task 8 modifies `Claim` which is a load-bearing class — existing tests in `tests/gaia/lang/` will run after Task 8 and could surface init-signature regressions. Step 5 of Task 8 catches this.
- The `Term` / `Formula` Protocols use a tag attribute (`__gaia_term__`, `__gaia_formula__`) rather than `runtime_checkable` alone, because an empty `Protocol` matches everything. The `is_term` / `is_formula` helpers do strict tag checks. This pattern is used uniformly.
