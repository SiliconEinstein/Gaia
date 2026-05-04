# Claim Formula Schema — Milestone A Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Land the structural foundation for the formula schema redesign — Variable / Domain as Knowledge subclasses, typed Formula AST module, and Claim's new `formula` + `kind` fields. **No DSL surface, no compiler, no migration in this milestone.** This is dataclass definitions plus their unit tests, plus the minimum compile-path contract that lets a package declaring Variables/Domains still compile cleanly.

**Architecture:** New `gaia/lang/formula/` module hosts the typed term/predicate/connective/quantifier AST. New files in `gaia/lang/runtime/` add `Variable` and `Domain` Knowledge subclasses (with a Lang-only `__post_init__` override that does NOT register them into the IR-bound knowledge map) and a `gaia/lang/types/primitives.py` module. `Claim` gains two optional fields (`formula`, `kind`) added **strictly additively** to its existing init logic — parameterized-Claim subclass support, docstring template rendering, and `[@label]` substitution all keep working. IR is not touched.

**Tech Stack:** Python 3.12 dataclasses, Pydantic v2 (only where existing IR uses it; new Lang code stays on dataclasses), pytest with `asyncio_mode = "auto"`, ruff for lint/format.

**Spec:** `docs/specs/2026-05-04-claim-formula-schema-design.md` (sections 2, 3, 4 of that spec — including §2.4 Lang-only registration and §3 typed-AST discipline).

**Out of scope for this milestone:**
- Operator overloading on Term (`p == 0.75` style) — Milestone B
- `forall / exists / land / lor / ...` DSL helpers — Milestone B
- Sugar constructors (`parameter / observation / causal`) — Milestone B
- Compiler lowering Formula → IR — Milestone B
- Cross-module Lang-side registry for Variables/Domains — Milestone B
- Migrating existing packages — Milestone C

In this milestone, formulas are constructed via direct AST node calls: `Equals(p, Constant(0.75, Probability))`. That's deliberately ugly — Milestone B makes it pretty.

---

## Task Order Rationale

`FunctionSymbol` and `PredicateSymbol` (declarations) come **before** `Term` and `Predicate` because the AST nodes reference symbol objects, not name strings (per spec §3 typed-AST discipline).

Final task order:

| # | Task |
|---|---|
| 1 | Primitive type tokens (`Nat`, `Real`, `Probability`, `Bool`) |
| 2 | `Domain` Knowledge subclass + Lang-only registration override |
| 3 | `Variable` Knowledge subclass + Lang-only registration override |
| 4 | `FunctionSymbol` / `PredicateSymbol` declarations |
| 5 | Formula AST — Term hierarchy (typed against `PrimitiveType` and `FunctionSymbol`) |
| 6 | Formula AST — Predicate hierarchy (typed against `PredicateSymbol`) |
| 7 | Formula AST — Connectives and Quantifiers |
| 8 | Extend `Claim` with `formula` and `kind` (strictly additive) |
| 9 | Public exports |
| 10 | End-to-end smoke (Mendel example + compile-no-regression smoke) |

---

## File Structure

```
gaia/lang/
├── runtime/
│   ├── knowledge.py        ← MODIFY: add formula, kind to Claim's existing init (additive); add ClaimKind enum
│   ├── domain.py           ← NEW: Domain Knowledge subclass + Lang-only __post_init__
│   ├── variable.py         ← NEW: Variable Knowledge subclass + Lang-only __post_init__
│   └── __init__.py         ← MODIFY: export Variable, Domain, ClaimKind
├── types/
│   ├── __init__.py         ← NEW
│   └── primitives.py       ← NEW: Nat, Real, Probability, Bool primitive type tokens
├── formula/
│   ├── __init__.py         ← NEW: re-exports
│   ├── symbols.py          ← NEW: FunctionSymbol, PredicateSymbol (created BEFORE term/predicate)
│   ├── term.py             ← NEW: Term protocol, Constant, FunctionApp, ArithOp
│   ├── predicate.py        ← NEW: Formula protocol, Equals, Greater, ..., ClaimAtom, Causes, UserPredicate
│   ├── connective.py       ← NEW: Land, Lor, Lnot, Implies, Iff
│   └── quantifier.py       ← NEW: Forall, Exists
└── __init__.py             ← MODIFY: top-level exports

tests/gaia/lang/
├── runtime/
│   ├── test_domain.py                  ← NEW
│   ├── test_variable.py                ← NEW
│   └── test_claim_formula_kind.py      ← NEW
├── types/
│   ├── __init__.py                     ← NEW
│   └── test_primitives.py              ← NEW
├── formula/
│   ├── __init__.py                     ← NEW
│   ├── test_symbols.py                 ← NEW
│   ├── test_term.py                    ← NEW
│   ├── test_predicate.py               ← NEW
│   ├── test_connective.py              ← NEW
│   └── test_quantifier.py              ← NEW
├── test_milestone_a_smoke.py           ← NEW: Mendel example with raw AST
└── test_milestone_a_compile_smoke.py   ← NEW: Lang-only registration regression check
```

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

import pytest

from gaia.lang.types.primitives import Bool, Nat, PrimitiveType, Probability, Real


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

## Task 2: Domain Knowledge Subclass + Lang-only Registration

**Files:**
- Create: `gaia/lang/runtime/domain.py`
- Test: `tests/gaia/lang/runtime/test_domain.py`

`Domain` is a user-declared typed sort with a finite, enumerable membership list. It subclasses `Knowledge` for identity/provenance/metadata, but **overrides `__post_init__` to skip `pkg._register_knowledge`** — Variables and Domains are Lang-only and must not enter the IR-bound knowledge map (spec §2.4).

- [ ] **Step 1: Write the failing tests**

Create `tests/gaia/lang/runtime/test_domain.py`:

```python
"""Tests for Domain Knowledge subclass and Lang-only registration."""

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


def test_domain_has_no_prior_field():
    d = Domain(content="x", members=[1])
    assert not hasattr(d, "prior")


def test_domain_does_not_register_into_package_knowledge_map(tmp_path, monkeypatch):
    """Spec §2.4: Domain must NOT enter pkg._register_knowledge so compile stays IR-clean."""
    from gaia.lang.runtime.knowledge import _current_package
    from gaia.lang.runtime.package import CollectedPackage

    pkg = CollectedPackage(name="test_pkg", namespace="test")
    token = _current_package.set(pkg)
    try:
        d = Domain(content="x", members=[1])
        # The domain should associate with the package for provenance...
        assert d._package is pkg
        # ...but NOT appear in the IR-bound knowledge list.
        registered = list(getattr(pkg, "knowledge", []) or [])
        assert d not in registered, (
            f"Domain leaked into pkg.knowledge — IR compile would attempt to translate it. "
            f"Registered: {registered}"
        )
    finally:
        _current_package.reset(token)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest tests/gaia/lang/runtime/test_domain.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'gaia.lang.runtime.domain'`

- [ ] **Step 3: Implement Domain with Lang-only registration**

Create `gaia/lang/runtime/domain.py`:

```python
"""Domain — a user-declared typed sort backing Variable types and quantification.

Lang-only: subclasses Knowledge for identity/provenance, but overrides
__post_init__ to skip the IR-bound knowledge map registration. See spec §2.4.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from gaia.lang.runtime.knowledge import Knowledge, _current_package


@dataclass(init=False, eq=False)
class Domain(Knowledge):
    """A user-declared, finite, enumerable typed sort.

    Subclasses Knowledge so it carries identity, provenance, and metadata.
    Use cases: ``Particle = domain("Particle", members=[p1, p2, ...])`` to type
    Variables and to provide enumerable members for quantifier grounding.

    Lang-only: does NOT enter the package's IR-bound knowledge map.
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

    def __post_init__(self):
        # Override Knowledge.__post_init__: associate with the package for provenance,
        # but DO NOT call pkg._register_knowledge — Domain is Lang-only (spec §2.4).
        pkg = _current_package.get()
        source_module = None
        if pkg is None:
            from gaia.lang.runtime.package import infer_package_and_module

            pkg, source_module = infer_package_and_module()
        if pkg is not None:
            self._source_module = source_module
            self._package = pkg
            # No pkg._register_knowledge(self) — Lang-only.
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
git commit -m "feat(lang): add Domain Knowledge subclass with Lang-only registration"
```

---

## Task 3: Variable Knowledge Subclass + Lang-only Registration + Term Marker

**Files:**
- Create: `gaia/lang/runtime/variable.py`
- Test: `tests/gaia/lang/runtime/test_variable.py`

`Variable` is a typed term that's also a Knowledge node. Holds an optional bound value (the CONSTANT case). Free / BOUND_BY_CLAIM cases are inferred by Milestone B's compiler. Like `Domain`, it overrides `__post_init__` to skip IR-bound registration. It also carries the Term protocol marker (`__gaia_term__ = True`) so it can appear in formulas built in Tasks 5–7.

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
    n = Variable(symbol="n", domain=Nat, value=0)
    assert "n" in n.content


def test_variable_carries_term_marker():
    """Spec §3 typed-AST discipline — Variable must satisfy the Term protocol."""
    n = Variable(symbol="n", domain=Nat, value=0)
    assert getattr(n, "__gaia_term__", False) is True


def test_variable_does_not_register_into_package_knowledge_map():
    """Spec §2.4: Variable must NOT enter pkg._register_knowledge."""
    from gaia.lang.runtime.knowledge import _current_package
    from gaia.lang.runtime.package import CollectedPackage

    pkg = CollectedPackage(name="test_pkg", namespace="test")
    token = _current_package.set(pkg)
    try:
        v = Variable(symbol="x", domain=Nat, value=1)
        assert v._package is pkg
        registered = list(getattr(pkg, "knowledge", []) or [])
        assert v not in registered
    finally:
        _current_package.reset(token)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest tests/gaia/lang/runtime/test_variable.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'gaia.lang.runtime.variable'`

- [ ] **Step 3: Implement Variable**

Create `gaia/lang/runtime/variable.py`:

```python
"""Variable — typed term Knowledge subclass.

Lang-only: like Domain, overrides __post_init__ to skip IR-bound knowledge map
registration. Carries the Term protocol marker so it can appear in formulas.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, ClassVar

from gaia.lang.runtime.domain import Domain
from gaia.lang.runtime.knowledge import Knowledge, _current_package
from gaia.lang.types.primitives import PrimitiveType


@dataclass(init=False, eq=False)
class Variable(Knowledge):
    """A typed term referenceable by formulas, models, and actions.

    Carries identity (via Knowledge), a symbol used in formulas, a domain
    (primitive type or user-declared Domain), and an optional bound value.
    Binding semantics (CONSTANT / FREE / BOUND_BY_CLAIM) are inferred by
    Milestone B's compiler from usage; this class stores only the authored data.

    Lang-only: does NOT enter the package's IR-bound knowledge map (spec §2.4).
    """

    # Term protocol marker — see gaia.lang.formula.term.is_term
    __gaia_term__: ClassVar[bool] = True

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

    def __post_init__(self):
        # Override Knowledge.__post_init__: associate with the package for provenance,
        # but DO NOT call pkg._register_knowledge — Variable is Lang-only (spec §2.4).
        pkg = _current_package.get()
        source_module = None
        if pkg is None:
            from gaia.lang.runtime.package import infer_package_and_module

            pkg, source_module = infer_package_and_module()
        if pkg is not None:
            self._source_module = source_module
            self._package = pkg
            # No pkg._register_knowledge(self) — Lang-only.


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
Expected: 13 passed.

- [ ] **Step 5: Lint and format**

Run: `ruff check gaia/lang/runtime/variable.py tests/gaia/lang/runtime/test_variable.py && ruff format gaia/lang/runtime/variable.py tests/gaia/lang/runtime/test_variable.py`
Expected: clean.

- [ ] **Step 6: Commit**

```bash
git add gaia/lang/runtime/variable.py tests/gaia/lang/runtime/test_variable.py
git commit -m "feat(lang): add Variable Knowledge subclass (typed, Lang-only, Term marker)"
```

---

## Task 4: FunctionSymbol and PredicateSymbol Declarations

**Files:**
- Create: `gaia/lang/formula/__init__.py`
- Create: `gaia/lang/formula/symbols.py`
- Create: `tests/gaia/lang/formula/__init__.py`
- Create: `tests/gaia/lang/formula/test_symbols.py`

These are typed declarations of named symbols (`E: Particle → Real`, `Stable: Particle → Bool`). They come **before** Term/Predicate because the AST nodes hold *references* to symbol objects (typed-AST discipline, spec §3).

- [ ] **Step 1: Write the failing tests**

Create `tests/gaia/lang/formula/__init__.py` (empty) and `tests/gaia/lang/formula/test_symbols.py`:

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
    with pytest.raises(ValueError, match="arity"):
        PredicateSymbol(name="P", arg_domains=())


def test_function_symbol_zero_arity_disallowed():
    with pytest.raises(ValueError, match="arity"):
        FunctionSymbol(name="f", arg_domains=(), result_domain=Real)


def test_function_symbol_result_domain_validation():
    with pytest.raises(TypeError, match="result_domain"):
        FunctionSymbol(name="f", arg_domains=(Nat,), result_domain="Real")  # type: ignore[arg-type]
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest tests/gaia/lang/formula/test_symbols.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'gaia.lang.formula'`

- [ ] **Step 3: Implement symbol declarations**

Create `gaia/lang/formula/__init__.py`:

```python
"""Gaia Lang Formula AST — typed term, predicate, connective, quantifier nodes.

Type discipline (spec §3): AST nodes carry references to PrimitiveType /
FunctionSymbol / PredicateSymbol — not name strings — and validate at construction.
"""

from gaia.lang.formula.symbols import FunctionSymbol, PredicateSymbol

__all__ = ["FunctionSymbol", "PredicateSymbol"]
```

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

- [ ] **Step 4: Run tests, verify pass**

Run: `pytest tests/gaia/lang/formula/test_symbols.py -v`
Expected: 9 passed.

- [ ] **Step 5: Lint and format**

Run: `ruff check gaia/lang/formula tests/gaia/lang/formula && ruff format gaia/lang/formula tests/gaia/lang/formula`
Expected: clean.

- [ ] **Step 6: Commit**

```bash
git add gaia/lang/formula tests/gaia/lang/formula
git commit -m "feat(lang): FunctionSymbol and PredicateSymbol declarations"
```

---

## Task 5: Formula AST — Term Hierarchy (typed)

**Files:**
- Create: `gaia/lang/formula/term.py`
- Test: `tests/gaia/lang/formula/test_term.py`

A Term is a value-bearing AST node: `Constant` (literal value with `PrimitiveType`), `FunctionApp` (application of a `FunctionSymbol` to typed args), `ArithOp` (arithmetic over Terms), or a `Variable` (already marked as Term in Task 3). Validation happens at construction: value matches primitive, arity and per-arg domain match the function symbol.

- [ ] **Step 1: Write the failing tests**

Create `tests/gaia/lang/formula/test_term.py`:

```python
"""Tests for Formula AST Term hierarchy with typed validation."""

import pytest

from gaia.lang.formula.symbols import FunctionSymbol
from gaia.lang.formula.term import ArithOp, Constant, FunctionApp, Term, is_term
from gaia.lang.runtime.domain import Domain
from gaia.lang.runtime.variable import Variable
from gaia.lang.types.primitives import Bool, Nat, Probability, Real


def test_constant_construction():
    c = Constant(value=395, primitive=Nat)
    assert c.value == 395
    assert c.primitive is Nat


def test_constant_value_must_match_primitive():
    """Spec §3 typed-AST: Constant validates its value against primitive."""
    with pytest.raises(ValueError, match="not accepted"):
        Constant(value=2, primitive=Probability)  # 2 is not in [0, 1]
    with pytest.raises(ValueError, match="not accepted"):
        Constant(value=-1, primitive=Nat)
    with pytest.raises(ValueError, match="not accepted"):
        Constant(value=1, primitive=Bool)  # strict bool


def test_constant_equality():
    c1 = Constant(value=395, primitive=Nat)
    c2 = Constant(value=395, primitive=Nat)
    c3 = Constant(value=396, primitive=Nat)
    assert c1 == c2
    assert c1 != c3


def test_constant_is_term():
    c = Constant(value=1, primitive=Nat)
    assert is_term(c)


def test_variable_is_term():
    n = Variable(symbol="n", domain=Nat, value=395)
    assert is_term(n)


def test_function_app_typed_construction():
    n = Variable(symbol="x", domain=Nat)
    E = FunctionSymbol(name="E", arg_domains=(Nat,), result_domain=Real)
    fa = FunctionApp(symbol=E, args=(n,))
    assert fa.symbol is E
    assert fa.args == (n,)


def test_function_app_arity_mismatch_rejected():
    E = FunctionSymbol(name="E", arg_domains=(Nat,), result_domain=Real)
    with pytest.raises(ValueError, match="arity"):
        FunctionApp(symbol=E, args=())
    with pytest.raises(ValueError, match="arity"):
        FunctionApp(symbol=E, args=(Constant(1, Nat), Constant(2, Nat)))


def test_function_app_arg_domain_mismatch_rejected():
    """E expects Nat; passing a Real-domain Variable should raise."""
    E = FunctionSymbol(name="E", arg_domains=(Nat,), result_domain=Real)
    real_var = Variable(symbol="r", domain=Real)
    with pytest.raises(TypeError, match="domain"):
        FunctionApp(symbol=E, args=(real_var,))


def test_function_app_arg_domain_match_with_custom_domain():
    Particle = Domain(content="x", members=["p1"])
    E = FunctionSymbol(name="E", arg_domains=(Particle,), result_domain=Real)
    x = Variable(symbol="x", domain=Particle)
    fa = FunctionApp(symbol=E, args=(x,))
    assert fa.symbol.name == "E"


def test_function_app_args_must_be_terms():
    E = FunctionSymbol(name="E", arg_domains=(Nat,), result_domain=Real)
    with pytest.raises(TypeError, match="argument"):
        FunctionApp(symbol=E, args=(395,))  # type: ignore[arg-type]


def test_function_app_is_term():
    E = FunctionSymbol(name="E", arg_domains=(Nat,), result_domain=Real)
    fa = FunctionApp(symbol=E, args=(Constant(1, Nat),))
    assert is_term(fa)


def test_arith_op_basic():
    n = Variable(symbol="n", domain=Nat, value=395)
    k = Variable(symbol="k", domain=Nat, value=295)
    expr = ArithOp(op="+", left=n, right=k)
    assert expr.op == "+"
    assert expr.left is n
    assert expr.right is k


def test_arith_op_is_term():
    n = Variable(symbol="n", domain=Nat)
    expr = ArithOp(op="+", left=n, right=Constant(1, Nat))
    assert is_term(expr)


def test_arith_op_rejects_unknown_op():
    n = Variable(symbol="n", domain=Nat)
    with pytest.raises(ValueError, match="op"):
        ArithOp(op="??", left=n, right=Constant(1, Nat))


def test_arith_op_operands_must_be_terms():
    with pytest.raises(TypeError, match="left"):
        ArithOp(op="+", left="x", right=Constant(1, Nat))  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="right"):
        ArithOp(op="+", left=Constant(1, Nat), right="y")  # type: ignore[arg-type]


def test_term_protocol_does_not_match_arbitrary_objects():
    assert not is_term(395)
    assert not is_term("string")
    assert not is_term([Constant(1, Nat)])


def test_nested_term_tree():
    """E(x + 1) — build a deep tree, walk it, confirm structure."""
    x = Variable(symbol="x", domain=Real)
    E = FunctionSymbol(name="E", arg_domains=(Real,), result_domain=Real)
    inner_arith = ArithOp(op="+", left=x, right=Constant(1, Real))
    e_call = FunctionApp(symbol=E, args=(inner_arith,))
    assert is_term(e_call)
    assert is_term(e_call.args[0])
    assert e_call.args[0].left is x
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest tests/gaia/lang/formula/test_term.py -v`
Expected: FAIL with `ImportError: cannot import name 'Constant'`

- [ ] **Step 3: Implement Term hierarchy**

Create `gaia/lang/formula/term.py`:

```python
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


def _term_domain(t: Term) -> PrimitiveType | Domain | None:
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
    args: tuple[Term, ...]

    __gaia_term__: ClassVar[bool] = True

    def __post_init__(self) -> None:
        if not isinstance(self.symbol, FunctionSymbol):
            raise TypeError(
                f"symbol must be a FunctionSymbol, got {type(self.symbol).__name__}"
            )
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
    left: Term
    right: Term

    __gaia_term__: ClassVar[bool] = True

    def __post_init__(self) -> None:
        if self.op not in _ARITH_OPS:
            raise ValueError(f"op must be one of {_ARITH_OPS}, got {self.op!r}")
        if not is_term(self.left):
            raise TypeError(f"ArithOp.left is not a Term: {self.left!r}")
        if not is_term(self.right):
            raise TypeError(f"ArithOp.right is not a Term: {self.right!r}")
```

Update `gaia/lang/formula/__init__.py`:

```python
"""Gaia Lang Formula AST — typed term, predicate, connective, quantifier nodes."""

from gaia.lang.formula.symbols import FunctionSymbol, PredicateSymbol
from gaia.lang.formula.term import ArithOp, Constant, FunctionApp, Term, is_term

__all__ = [
    # symbols
    "FunctionSymbol",
    "PredicateSymbol",
    # term
    "Term",
    "Constant",
    "FunctionApp",
    "ArithOp",
    "is_term",
]
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pytest tests/gaia/lang/formula/test_term.py tests/gaia/lang/runtime/test_variable.py -v`
Expected: all pass.

- [ ] **Step 5: Lint and format**

Run: `ruff check gaia/lang/formula tests/gaia/lang/formula && ruff format gaia/lang/formula tests/gaia/lang/formula`
Expected: clean.

- [ ] **Step 6: Commit**

```bash
git add gaia/lang/formula tests/gaia/lang/formula
git commit -m "feat(lang): formula AST term layer with typed validation"
```

---

## Task 6: Formula AST — Predicate Hierarchy (typed)

**Files:**
- Create: `gaia/lang/formula/predicate.py`
- Test: `tests/gaia/lang/formula/test_predicate.py`

Predicates are atomic formulas. `UserPredicate` references a `PredicateSymbol` (typed-AST discipline) and validates arity + arg domains the same way `FunctionApp` does. `ClaimAtom` references a `Claim` (the bridge from formula to claim graph). `Causes` is the v0.6 marker.

- [ ] **Step 1: Write the failing tests**

Create `tests/gaia/lang/formula/test_predicate.py`:

```python
"""Tests for Formula AST Predicate hierarchy (typed)."""

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
from gaia.lang.formula.symbols import PredicateSymbol
from gaia.lang.formula.term import Constant
from gaia.lang.runtime.knowledge import Claim
from gaia.lang.runtime.variable import Variable
from gaia.lang.types.primitives import Nat, Probability, Real


def test_equals_basic():
    p = Variable(symbol="p", domain=Probability)
    eq = Equals(left=p, right=Constant(value=0.75, primitive=Probability))
    assert eq.left is p
    assert eq.right.value == 0.75


def test_equals_is_formula():
    eq = Equals(left=Constant(1, Nat), right=Constant(1, Nat))
    assert is_formula(eq)


def test_equals_args_must_be_terms():
    with pytest.raises(TypeError):
        Equals(left="not_a_term", right=Constant(1, Nat))  # type: ignore[arg-type]


def test_comparisons():
    n = Variable(symbol="n", domain=Nat, value=395)
    z = Constant(value=0, primitive=Nat)
    assert is_formula(Greater(left=n, right=z))
    assert is_formula(Less(left=n, right=z))
    assert is_formula(GreaterEqual(left=n, right=z))
    assert is_formula(LessEqual(left=n, right=z))
    assert is_formula(NotEquals(left=n, right=z))


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


def test_user_predicate_typed():
    n = Variable(symbol="n", domain=Nat)
    Stable = PredicateSymbol(name="Stable", arg_domains=(Nat,))
    pred = UserPredicate(symbol=Stable, args=(n,))
    assert pred.symbol is Stable
    assert pred.args == (n,)


def test_user_predicate_arity_mismatch_rejected():
    Stable = PredicateSymbol(name="Stable", arg_domains=(Nat,))
    with pytest.raises(ValueError, match="arity"):
        UserPredicate(symbol=Stable, args=())
    with pytest.raises(ValueError, match="arity"):
        UserPredicate(symbol=Stable, args=(Constant(1, Nat), Constant(2, Nat)))


def test_user_predicate_arg_domain_mismatch_rejected():
    Stable = PredicateSymbol(name="Stable", arg_domains=(Nat,))
    real_var = Variable(symbol="r", domain=Real)
    with pytest.raises(TypeError, match="domain"):
        UserPredicate(symbol=Stable, args=(real_var,))


def test_user_predicate_is_formula():
    P = PredicateSymbol(name="P", arg_domains=(Nat,))
    pred = UserPredicate(symbol=P, args=(Constant(1, Nat),))
    assert is_formula(pred)


def test_user_predicate_args_must_be_terms():
    P = PredicateSymbol(name="P", arg_domains=(Nat,))
    with pytest.raises(TypeError, match="argument"):
        UserPredicate(symbol=P, args=(123,))  # type: ignore[arg-type]


def test_causes_predicate():
    a = Variable(symbol="a", domain=Real)
    b = Variable(symbol="b", domain=Real)
    c = Causes(cause=a, effect=b)
    assert c.cause is a
    assert c.effect is b
    assert is_formula(c)


def test_is_formula_rejects_terms():
    """A Term alone is not a Formula — it has no truth value."""
    assert not is_formula(Constant(1, Nat))
    assert not is_formula(Variable(symbol="x", domain=Nat))


def test_is_formula_rejects_arbitrary():
    assert not is_formula("hello")
    assert not is_formula(42)
    assert not is_formula([Equals(Constant(1, Nat), Constant(1, Nat))])
```

- [ ] **Step 2: Run the failing tests**

Run: `pytest tests/gaia/lang/formula/test_predicate.py -v`
Expected: FAIL with `ImportError`.

- [ ] **Step 3: Implement Predicate hierarchy**

Create `gaia/lang/formula/predicate.py`:

```python
"""Predicate — atomic formulas (truth-valued expressions over Terms or Claims).

Spec §3 typed-AST discipline: UserPredicate carries a PredicateSymbol reference
and validates arity + arg domains. Equals/Greater/etc. validate that operands
are Terms.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar, Protocol, runtime_checkable

from gaia.lang.formula.symbols import PredicateSymbol
from gaia.lang.formula.term import Term, _term_domain, is_term
from gaia.lang.runtime.knowledge import Claim


@runtime_checkable
class Formula(Protocol):
    """Marker protocol — a truth-valued AST node."""

    __gaia_formula__: bool = True


def is_formula(obj: object) -> bool:
    return getattr(obj, "__gaia_formula__", False) is True


def _check_term(name: str, value: object) -> None:
    if not is_term(value):
        raise TypeError(f"{name} is not a Term: {value!r}")


@dataclass(frozen=True)
class Equals:
    left: Term
    right: Term
    __gaia_formula__: ClassVar[bool] = True

    def __post_init__(self) -> None:
        _check_term("left", self.left)
        _check_term("right", self.right)


@dataclass(frozen=True)
class NotEquals:
    left: Term
    right: Term
    __gaia_formula__: ClassVar[bool] = True

    def __post_init__(self) -> None:
        _check_term("left", self.left)
        _check_term("right", self.right)


@dataclass(frozen=True)
class Greater:
    left: Term
    right: Term
    __gaia_formula__: ClassVar[bool] = True

    def __post_init__(self) -> None:
        _check_term("left", self.left)
        _check_term("right", self.right)


@dataclass(frozen=True)
class GreaterEqual:
    left: Term
    right: Term
    __gaia_formula__: ClassVar[bool] = True

    def __post_init__(self) -> None:
        _check_term("left", self.left)
        _check_term("right", self.right)


@dataclass(frozen=True)
class Less:
    left: Term
    right: Term
    __gaia_formula__: ClassVar[bool] = True

    def __post_init__(self) -> None:
        _check_term("left", self.left)
        _check_term("right", self.right)


@dataclass(frozen=True)
class LessEqual:
    left: Term
    right: Term
    __gaia_formula__: ClassVar[bool] = True

    def __post_init__(self) -> None:
        _check_term("left", self.left)
        _check_term("right", self.right)


@dataclass(frozen=True)
class UserPredicate:
    """Application of a user-declared PredicateSymbol to typed Term arguments."""

    symbol: PredicateSymbol
    args: tuple[Term, ...]
    __gaia_formula__: ClassVar[bool] = True

    def __post_init__(self) -> None:
        if not isinstance(self.symbol, PredicateSymbol):
            raise TypeError(
                f"symbol must be a PredicateSymbol, got {type(self.symbol).__name__}"
            )
        expected_arity = len(self.symbol.arg_domains)
        if len(self.args) != expected_arity:
            raise ValueError(
                f"UserPredicate arity mismatch: {self.symbol.name} expects "
                f"{expected_arity} args, got {len(self.args)}"
            )
        for i, (arg, expected_domain) in enumerate(zip(self.args, self.symbol.arg_domains)):
            if not is_term(arg):
                raise TypeError(f"UserPredicate argument {i} is not a Term: {arg!r}")
            actual = _term_domain(arg)
            if actual is not None and actual is not expected_domain:
                raise TypeError(
                    f"UserPredicate argument {i} domain mismatch: {self.symbol.name} expects "
                    f"{expected_domain}, got {actual}"
                )


@dataclass(frozen=True)
class Causes:
    """Built-in causal predicate. v0.5: marker; v0.6: interventional factor."""

    cause: Term
    effect: Term
    __gaia_formula__: ClassVar[bool] = True

    def __post_init__(self) -> None:
        _check_term("cause", self.cause)
        _check_term("effect", self.effect)


@dataclass(frozen=True)
class ClaimAtom:
    """A reference to another Claim's truth — the bridge from formula land to claim graph."""

    claim: Claim
    __gaia_formula__: ClassVar[bool] = True

    def __post_init__(self) -> None:
        if not isinstance(self.claim, Claim):
            raise TypeError(
                f"ClaimAtom requires a Claim instance, got {type(self.claim).__name__}"
            )
```

Update `gaia/lang/formula/__init__.py` re-exports:

```python
"""Gaia Lang Formula AST — typed term, predicate, connective, quantifier nodes."""

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
from gaia.lang.formula.symbols import FunctionSymbol, PredicateSymbol
from gaia.lang.formula.term import ArithOp, Constant, FunctionApp, Term, is_term

__all__ = [
    "FunctionSymbol",
    "PredicateSymbol",
    "Term",
    "Constant",
    "FunctionApp",
    "ArithOp",
    "is_term",
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

- [ ] **Step 4: Run the tests, verify pass**

Run: `pytest tests/gaia/lang/formula/ -v`
Expected: all pass.

- [ ] **Step 5: Lint and format**

Run: `ruff check gaia/lang/formula tests/gaia/lang/formula && ruff format gaia/lang/formula tests/gaia/lang/formula`
Expected: clean.

- [ ] **Step 6: Commit**

```bash
git add gaia/lang/formula tests/gaia/lang/formula
git commit -m "feat(lang): formula AST predicate layer (typed UserPredicate, Equals/comparisons, Causes/ClaimAtom)"
```

---

## Task 7: Formula AST — Connectives and Quantifiers

**Files:**
- Create: `gaia/lang/formula/connective.py`
- Create: `gaia/lang/formula/quantifier.py`
- Test: `tests/gaia/lang/formula/test_connective.py`
- Test: `tests/gaia/lang/formula/test_quantifier.py`

Connectives (∧, ∨, ¬, →, ↔) and quantifiers (∀, ∃) compose Formulas. Each is a frozen dataclass; sub-Formulas validated in `__post_init__`. Quantifier additionally requires the bound `Variable` is unbound.

- [ ] **Step 1: Write the failing tests for connectives**

Create `tests/gaia/lang/formula/test_connective.py`:

```python
"""Tests for Formula AST connectives."""

import pytest

from gaia.lang.formula.connective import Iff, Implies, Land, Lnot, Lor
from gaia.lang.formula.predicate import Equals, is_formula
from gaia.lang.formula.term import Constant
from gaia.lang.types.primitives import Nat


def _atom(v: int) -> Equals:
    return Equals(left=Constant(v, Nat), right=Constant(v, Nat))


def test_land_two_args():
    a, b = _atom(1), _atom(2)
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

- [ ] **Step 2: Run failing connective tests**

Run: `pytest tests/gaia/lang/formula/test_connective.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement connectives**

Create `gaia/lang/formula/connective.py`:

```python
"""Connectives — compound formulas built from sub-formulas."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from gaia.lang.formula.predicate import Formula, is_formula


def _check_formula(name: str, value: object) -> None:
    if not is_formula(value):
        raise TypeError(f"{name} is not a Formula: {value!r}")


@dataclass(frozen=True)
class Land:
    operands: tuple[Formula, ...]
    __gaia_formula__: ClassVar[bool] = True

    def __post_init__(self) -> None:
        if len(self.operands) < 2:
            raise ValueError("Land requires at least two operands")
        for i, op in enumerate(self.operands):
            if not is_formula(op):
                raise TypeError(f"Land.operands[{i}] is not a Formula: {op!r}")


@dataclass(frozen=True)
class Lor:
    operands: tuple[Formula, ...]
    __gaia_formula__: ClassVar[bool] = True

    def __post_init__(self) -> None:
        if len(self.operands) < 2:
            raise ValueError("Lor requires at least two operands")
        for i, op in enumerate(self.operands):
            if not is_formula(op):
                raise TypeError(f"Lor.operands[{i}] is not a Formula: {op!r}")


@dataclass(frozen=True)
class Lnot:
    operand: Formula
    __gaia_formula__: ClassVar[bool] = True

    def __post_init__(self) -> None:
        _check_formula("operand", self.operand)


@dataclass(frozen=True)
class Implies:
    antecedent: Formula
    consequent: Formula
    __gaia_formula__: ClassVar[bool] = True

    def __post_init__(self) -> None:
        _check_formula("antecedent", self.antecedent)
        _check_formula("consequent", self.consequent)


@dataclass(frozen=True)
class Iff:
    left: Formula
    right: Formula
    __gaia_formula__: ClassVar[bool] = True

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
    return Equals(left=Constant(1, Nat), right=Constant(1, Nat))


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
    """Spec §3: a variable that already has a value can't be quantifier-bound."""
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

- [ ] **Step 6: Run failing quantifier tests**

Run: `pytest tests/gaia/lang/formula/test_quantifier.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 7: Implement quantifiers**

Create `gaia/lang/formula/quantifier.py`:

```python
"""Quantifiers — universal and existential binding of a Variable inside a body Formula."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

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
    variable: Variable
    body: Formula
    __gaia_formula__: ClassVar[bool] = True

    def __post_init__(self) -> None:
        _check(self.variable, self.body)


@dataclass(frozen=True)
class Exists:
    variable: Variable
    body: Formula
    __gaia_formula__: ClassVar[bool] = True

    def __post_init__(self) -> None:
        _check(self.variable, self.body)
```

Update `gaia/lang/formula/__init__.py` to re-export connectives and quantifiers:

```python
from gaia.lang.formula.connective import Iff, Implies, Land, Lnot, Lor
from gaia.lang.formula.quantifier import Exists, Forall
```

And add to `__all__`: `"Land", "Lor", "Lnot", "Implies", "Iff", "Forall", "Exists"`.

- [ ] **Step 8: Run all formula tests**

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

## Task 8: Extend Claim with `formula` and `kind` (Strictly Additive)

**Files:**
- Modify: `gaia/lang/runtime/knowledge.py`
- Test: `tests/gaia/lang/runtime/test_claim_formula_kind.py`

The current `Claim.__init__` (around line ~155 in v0.5) does important work that **must not be broken**:
- builds `param_values` / `knowledge_kwargs` based on `_param_fields` (parameterized Claim subclasses)
- when `content is None`, renders `__class__.__doc__` template with `[@label]` substitution and `str.format(**render_values)`
- threads `parameters` into the parameters list with stored-val handling for Enums
- preserves `grounding`, `supports`, etc.

This task adds `formula` and `kind` **strictly as additional kwargs** to that existing init, validates them, and assigns them at the end. It does NOT replace the init body. Tests cover both the new fields and a parameterized Claim subclass to lock in non-regression.

- [ ] **Step 1: Inspect the current Claim init**

Read `gaia/lang/runtime/knowledge.py` and locate `class Claim`. Confirm the `__init__` signature is:

```python
def __init__(
    self,
    content: str | None = None,
    *,
    prior: float | None = None,
    grounding: Grounding | None = None,
    supports: list[Any] | None = None,
    **kwargs,
):
```

…and that it implements the param_fields / template / `[@label]` flow. Do NOT proceed to Step 3 until you've read the current implementation end-to-end and understand what each line does.

- [ ] **Step 2: Write the failing tests**

Create `tests/gaia/lang/runtime/test_claim_formula_kind.py`:

```python
"""Tests for Claim.formula and Claim.kind extensions (additive — must not regress prior behavior)."""

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
    eq = Equals(left=p, right=Constant(0.75, Probability))
    c = Claim(content="Mendelian", formula=eq, prior=0.5)
    assert c.formula is eq


def test_claim_with_explicit_kind():
    p = Variable(symbol="p", domain=Probability)
    eq = Equals(left=p, right=Constant(0.75, Probability))
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
    eq = Equals(left=p, right=Constant(0.75, Probability))
    with pytest.raises(TypeError, match="kind"):
        Claim(content="P", formula=eq, kind="parameter", prior=0.5)  # type: ignore[arg-type]


def test_existing_claim_construction_unchanged():
    """Plain Claim authoring like in v0.5 still works — formula/kind opt-in."""
    c = Claim(content="Mendelian 3:1 segregation holds.", prior=0.5)
    assert c.formula is None
    assert c.kind is ClaimKind.GENERAL
    assert c.prior == 0.5


def test_parameterized_claim_subclass_still_works():
    """Regression: docstring template + _param_fields path must not be disturbed.

    A parameterized Claim subclass renders content from its docstring, substituting
    [@param_name] for Knowledge-typed params and {param_name} for value params.
    """
    from gaia.lang.runtime.knowledge import Knowledge

    note = Knowledge(content="experiment X", type="note", label="exp_x")

    class MyClaim(Claim):
        """We observed {n} successes in [@exp]."""

        n: int = 0
        exp: Knowledge = None  # type: ignore[assignment]

    c = MyClaim(n=5, exp=note, prior=0.7)
    # template should have rendered
    assert "5" in c.content
    assert "exp_x" in c.content
    # prior preserved
    assert c.prior == 0.7
    # formula/kind defaults
    assert c.formula is None
    assert c.kind is ClaimKind.GENERAL
    # parameters list populated
    names = [p["name"] for p in c.parameters]
    assert "n" in names
    assert "exp" in names


def test_parameterized_claim_subclass_accepts_formula_and_kind():
    """The new fields work on subclasses too."""
    from gaia.lang.runtime.knowledge import Knowledge

    note = Knowledge(content="experiment X", type="note", label="exp_x")

    class MyClaim(Claim):
        """{n} hits in [@exp]."""

        n: int = 0
        exp: Knowledge = None  # type: ignore[assignment]

    p = Variable(symbol="p", domain=Probability)
    eq = Equals(left=p, right=Constant(0.5, Probability))
    c = MyClaim(n=3, exp=note, formula=eq, kind=ClaimKind.PARAMETER, prior=0.6)
    assert c.formula is eq
    assert c.kind is ClaimKind.PARAMETER
```

- [ ] **Step 3: Run failing tests**

Run: `pytest tests/gaia/lang/runtime/test_claim_formula_kind.py -v`
Expected: FAIL with `ImportError: cannot import name 'ClaimKind'`.

- [ ] **Step 4: Add the ClaimKind enum and the additive patch**

Edit `gaia/lang/runtime/knowledge.py`. At the top, alongside other imports, add:

```python
from gaia.lang.formula.predicate import is_formula
```

Just above the `Claim` class definition, add the enum:

```python
class ClaimKind(Enum):
    """Shape discriminator for the structured-content of a Claim (spec §4.2).

    GENERAL      — default; formula optional, no structural commitments
    PARAMETER    — asserts a Variable takes a specific value (Equals(var, const))
    OBSERVATION  — records observed values for one or more Variables
    QUANTIFIED   — top-level quantifier (Forall/Exists) in formula
    CAUSAL       — top-level Causes(...) predicate in formula

    NOT a "role" (hypothesis/prediction/observation-as-evidence) — those live
    on action graph nodes. NOT Grounding.kind. NOT helper-claim metadata.
    """

    GENERAL = "general"
    PARAMETER = "parameter"
    OBSERVATION = "observation"
    QUANTIFIED = "quantified"
    CAUSAL = "causal"
```

In the `Claim` class body, **add two new dataclass fields** (alongside `prior`, `grounding`, `supports`):

```python
    formula: Any = None
    kind: ClaimKind = ClaimKind.GENERAL
```

In `__init_subclass__`, **append** `"formula"` and `"kind"` to the `base_fields` whitelist:

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

In `__init__`, **add `formula` and `kind` to the signature** (keep all existing parameters and body intact):

```python
    def __init__(
        self,
        content: str | None = None,
        *,
        prior: float | None = None,
        grounding: Grounding | None = None,
        supports: list[Any] | None = None,
        formula: Any = None,                       # NEW
        kind: ClaimKind = ClaimKind.GENERAL,       # NEW
        **kwargs,
    ):
        # NEW: validate the two new fields up-front (fail fast).
        if formula is not None and not is_formula(formula):
            raise TypeError(
                f"formula must be a Formula or None, got {type(formula).__name__}"
            )
        if not isinstance(kind, ClaimKind):
            raise TypeError(
                f"kind must be a ClaimKind member, got {type(kind).__name__}"
            )

        # ────────────────────────────────────────────────────────────
        # EXISTING BODY — DO NOT MODIFY ANY OF THE LINES BELOW UNTIL
        # WE REACH THE END (see "NEW ASSIGNMENTS" marker).
        # ────────────────────────────────────────────────────────────
        param_fields = getattr(self.__class__, "_param_fields", {})
        param_values: dict[str, Any] = {}
        knowledge_kwargs: dict[str, Any] = {}
        for key, value in kwargs.items():
            if key in param_fields:
                param_values[key] = value
            else:
                knowledge_kwargs[key] = value

        # ... (keep the entire existing body — params building, template
        #      rendering, [@label] substitution, str.format(**render_values),
        #      super().__init__(...), self.prior = ..., self.grounding = ...,
        #      self.supports = ...)  unchanged ...

        # NEW ASSIGNMENTS — at the end, after all existing body lines:
        self.formula = formula
        self.kind = kind
```

> **Implementation note for the engineer:** open the current `Claim.__init__` and copy each existing line verbatim, then bracket it with the new validation at the top and the new assignments at the bottom. Do NOT rewrite the body.

- [ ] **Step 5: Run the new tests, verify pass**

Run: `pytest tests/gaia/lang/runtime/test_claim_formula_kind.py -v`
Expected: 10 passed.

- [ ] **Step 6: Run the full Lang test suite to confirm no regression**

Run: `pytest tests/gaia/lang/ -v`
Expected: all existing tests still pass; new tests pass. **If any existing parametrized-Claim test fails, revert and re-do Step 4 — you broke the existing init body.**

- [ ] **Step 7: Lint and format**

Run: `ruff check gaia/lang/runtime/knowledge.py tests/gaia/lang/runtime/test_claim_formula_kind.py && ruff format gaia/lang/runtime/knowledge.py tests/gaia/lang/runtime/test_claim_formula_kind.py`
Expected: clean.

- [ ] **Step 8: Commit**

```bash
git add gaia/lang/runtime/knowledge.py tests/gaia/lang/runtime/test_claim_formula_kind.py
git commit -m "feat(lang): add Claim.formula and Claim.kind (ClaimKind enum, strictly additive)"
```

---

## Task 9: Public Exports

**Files:**
- Modify: `gaia/lang/runtime/__init__.py`
- Modify: `gaia/lang/__init__.py`

Surface the new types so authors can `from gaia.lang import Variable, Domain, Forall, Equals, ...`.

- [ ] **Step 1: Inspect current exports**

Run: `cat gaia/lang/runtime/__init__.py | head -60`
Run: `cat gaia/lang/__init__.py | head -60`

Read existing exports to keep new ones in consistent style.

- [ ] **Step 2: Update `gaia/lang/runtime/__init__.py`**

Add `Domain`, `Variable`, and `ClaimKind` to imports and `__all__`:

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

__all__ = [
    # ... existing entries ...
    "Domain",
    "Variable",
    "ClaimKind",
]
```

- [ ] **Step 3: Update `gaia/lang/__init__.py`**

Add formula module re-exports and the new runtime types. Find the existing `from gaia.lang.runtime import (...)` block and append the new names; add a fresh `from gaia.lang.formula import (...)` block; add `from gaia.lang.types.primitives import (...)`. Update `__all__`.

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

- [ ] **Step 4: Add a smoke test for the public surface**

Create `tests/gaia/lang/test_public_surface_milestone_a.py`:

```python
"""Smoke test — every name introduced in Milestone A is reachable from `gaia.lang`."""


def test_milestone_a_public_surface():
    import gaia.lang as lang

    expected = {
        "Nat", "Real", "Probability", "Bool",
        "Variable", "Domain", "ClaimKind",
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

- [ ] **Step 5: Run smoke test**

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

## Task 10: End-to-End Smoke Tests

**Files:**
- Create: `tests/gaia/lang/test_milestone_a_smoke.py`
- Create: `tests/gaia/lang/test_milestone_a_compile_smoke.py`

Two smoke tests:

1. **AST smoke** — Build the Mendel example data shapes (parameter, observation, universal-quantified, causal) using only AST node constructors. Confirms everything wires together.
2. **Compile smoke** — Declare Variables and Domains in a package and confirm the package compiles cleanly via `compile_package_artifact()` and the resulting IR contains no `variable` or `domain` typed nodes (Codex blocker #1 regression check).

- [ ] **Step 1: Write the AST smoke test**

Create `tests/gaia/lang/test_milestone_a_smoke.py`:

```python
"""Milestone A AST smoke — build Mendel + universal + causal with raw constructors."""

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
from gaia.lang.formula.symbols import PredicateSymbol


def test_mendel_parameter_assertion():
    """H asserts P(dominant) = 0.75 via Equals(p, 0.75)."""
    p = Variable(symbol="p", domain=Probability)
    H = Claim(
        content="Mendelian 3:1 segregation: P(dominant) = 0.75.",
        formula=Equals(left=p, right=Constant(0.75, Probability)),
        kind=ClaimKind.PARAMETER,
        prior=0.5,
    )
    assert H.kind is ClaimKind.PARAMETER
    assert is_formula(H.formula)
    assert H.formula.left is p


def test_mendel_observation():
    """D records observed counts via conjunction of Equals."""
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
    assert D.kind is ClaimKind.OBSERVATION
    assert len(D.formula.operands) == 2


def test_universal_law_with_quantifier():
    """All particles have positive energy: Forall(x, E(x) > 0)."""
    Particle = Domain(content="Subatomic particles", members=["p1", "p2", "p3"])
    x = Variable(symbol="x", domain=Particle)
    E = FunctionSymbol(name="E", arg_domains=(Particle,), result_domain=Real)
    body = Greater(
        left=FunctionApp(symbol=E, args=(x,)),
        right=Constant(0, Real),
    )
    universal = Claim(
        content="All particles have positive energy.",
        formula=Forall(variable=x, body=body),
        kind=ClaimKind.QUANTIFIED,
        prior=0.95,
    )
    assert universal.kind is ClaimKind.QUANTIFIED
    assert universal.formula.variable is x


def test_causal_claim():
    """Causal predicate marker."""
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
    """¬(P ∧ ¬Q) — connective composition."""
    P = Equals(left=Constant(1, Nat), right=Constant(1, Nat))
    Q = Equals(left=Constant(2, Nat), right=Constant(2, Nat))
    f = Lnot(operand=Land(operands=(P, Lnot(operand=Q))))
    assert is_formula(f)


def test_user_predicate_in_compound():
    """Land(Stable(a), Stable(b))."""
    a = Variable(symbol="a", domain=Nat)
    b = Variable(symbol="b", domain=Nat)
    Stable = PredicateSymbol(name="Stable", arg_domains=(Nat,))
    f = Land(
        operands=(
            UserPredicate(symbol=Stable, args=(a,)),
            UserPredicate(symbol=Stable, args=(b,)),
        )
    )
    assert is_formula(f)
    assert len(f.operands) == 2
```

- [ ] **Step 2: Run AST smoke test**

Run: `pytest tests/gaia/lang/test_milestone_a_smoke.py -v`
Expected: 6 passed.

- [ ] **Step 3: Write the compile-smoke regression test**

Create `tests/gaia/lang/test_milestone_a_compile_smoke.py`:

```python
"""Milestone A compile smoke — packages declaring Variables/Domains compile cleanly.

Codex review blocker #1: Variable/Domain are Lang-only and must not enter the
IR-bound knowledge map. This test declares both inside a CollectedPackage,
runs compile_package_artifact, and asserts the resulting IR contains a Claim
but no `variable` or `domain` typed entries.
"""

from gaia.lang.compiler.compile import compile_package_artifact
from gaia.lang.runtime.domain import Domain
from gaia.lang.runtime.knowledge import Claim, _current_package
from gaia.lang.runtime.package import CollectedPackage
from gaia.lang.runtime.variable import Variable
from gaia.lang.types.primitives import Nat


def test_package_with_variables_and_domains_compiles_cleanly():
    pkg = CollectedPackage(name="t_smoke", namespace="t")
    token = _current_package.set(pkg)
    try:
        # Lang-only declarations.
        Particle = Domain(content="Particles", members=["p1", "p2"])  # noqa: F841
        n = Variable(symbol="n", domain=Nat, value=395)  # noqa: F841

        # An IR-bound Claim — this MUST appear in compiled output.
        Claim(content="A regular claim.", prior=0.5, label="C1")
    finally:
        _current_package.reset(token)

    artifact = compile_package_artifact(pkg)

    # No variable/domain typed entries leaked into IR.
    types = {k.type for k in artifact.knowledge}
    assert "variable" not in types, (
        f"variable leaked into IR knowledge — Lang-only registration failed. "
        f"Types in IR: {sorted(types)}"
    )
    assert "domain" not in types, (
        f"domain leaked into IR knowledge — Lang-only registration failed. "
        f"Types in IR: {sorted(types)}"
    )
    # The regular Claim is present.
    assert any(k.type == "claim" for k in artifact.knowledge), (
        "no claim found in compiled artifact"
    )
```

> **Note:** `compile_package_artifact` and `CollectedPackage` exact constructor signatures may differ slightly from this template — read `gaia/lang/compiler/compile.py` and `gaia/lang/runtime/package.py` to align argument names. The shape of the assertion (no `variable`/`domain` in compiled types; at least one `claim` present) stays the same.

- [ ] **Step 4: Run compile smoke**

Run: `pytest tests/gaia/lang/test_milestone_a_compile_smoke.py -v`
Expected: 1 passed.

- [ ] **Step 5: Run the full Lang suite (no regression check)**

Run: `pytest tests/gaia/lang/ -v`
Expected: all pass.

- [ ] **Step 6: Run the full repo suite (Neo4j tests auto-skip if unavailable)**

Run: `pytest`
Expected: existing test counts intact, plus the new tests pass.

- [ ] **Step 7: Lint and format final pass**

Run: `ruff check . && ruff format --check .`
Expected: clean.

- [ ] **Step 8: Commit**

```bash
git add tests/gaia/lang/test_milestone_a_smoke.py tests/gaia/lang/test_milestone_a_compile_smoke.py
git commit -m "test(lang): Milestone A end-to-end smoke (AST construction + compile-no-leak)"
```

---

## Wrap-up After Task 10

- [ ] Push branch and verify CI:

```bash
git push origin feat/v05-claim-formula-schema
gh run list --branch feat/v05-claim-formula-schema --limit 1
```

If CI fails:

```bash
gh run view <run-id> --log-failed
# Fix and push a new commit; do NOT amend or force-push.
```

- [ ] Tag the commit so Milestones B and C can branch off cleanly:

```bash
git tag v0.5-milestone-a
git push origin v0.5-milestone-a
```

- [ ] Author Milestone B's plan in a follow-up PR.

---

## Self-Review Notes

**Spec coverage check:**

| Spec section | Task |
|---|---|
| §2.1 Variable | Task 3 |
| §2.2 Domain | Task 2 |
| §2.3 Primitive types (built-in) | Task 1 |
| §2.4 Lang-only registration | Task 2, Task 3, Task 10 (compile smoke) |
| §3 Typed-AST discipline | Task 4 (symbols), Task 5 (typed Term), Task 6 (typed UserPredicate) |
| §3.1 Term | Task 5 |
| §3.2 Predicate (incl. ClaimAtom, Causes, UserPredicate) | Task 6 |
| §3.3 Connectives & Quantifiers | Task 7 |
| §3.4 Function symbol declaration | Task 4 |
| §3.5 User-declared predicate symbol | Task 4 |
| §4 Claim extension (formula, kind) | Task 8 |
| §4.2 ClaimKind boundary | Task 8 (ClaimKind docstring carries the boundary statement) |
| Public surface | Task 9 |
| §5 Author DSL | **Out of scope** — Milestone B |
| §6 Variable binding inference | **Out of scope** — Milestone B |
| §7 Compiler lowering | **Out of scope** — Milestone B |
| §8 Migration | **Out of scope** — Milestone C |

**Type/method consistency:**

- `__gaia_term__` and `__gaia_formula__` are the protocol markers across all AST node classes — consistent.
- `Variable` has `__gaia_term__ = True` (Task 3); `is_term(variable)` works in Task 5 onward.
- `is_term` and `is_formula` are the two strict checks; used uniformly in `__post_init__` validations.
- `Constant.primitive: PrimitiveType`, `FunctionApp.symbol: FunctionSymbol`, `UserPredicate.symbol: PredicateSymbol` — typed-AST discipline applied consistently.
- `ClaimKind` values: `general / parameter / observation / quantified / causal` — consistent between Task 8 enum and Task 10 smoke test.

**Codex review fixes incorporated:**

| Codex issue | How addressed |
|---|---|
| 1. Variable/Domain auto-registration breaks compile | Tasks 2 & 3 add `__post_init__` override (no `_register_knowledge` call). Task 10 step 3 adds compile-smoke regression test. Spec §2.4 documents the contract. |
| 2. Claim init patch destructive | Task 8 explicitly marked **strictly additive** with implementation note "do NOT rewrite the body". New regression tests cover parameterized Claim subclass and docstring template path. |
| 3. Causes uses `.id` (does not exist) | Spec §7.3 rewritten — descriptors use `symbol`/`domain.name`/`binding_provenance`; QID resolution happens during compile, not Lang runtime. (Milestone A only ships the `Causes` AST node — actual lowering is Milestone B.) |
| 4. Untyped AST | Spec §3 typed-AST discipline added. Task 4 hoisted before Term/Predicate. Tasks 5 & 6 use `PrimitiveType` / `FunctionSymbol` / `PredicateSymbol` references with arity + domain validation. |
| 5. trace.md in PR | Removed in the same commit batch (separate cleanup step in the next push). |
| 6. ClaimKind boundary | Spec §4.2 added; Task 8 enum docstring carries the same boundary statement. |
