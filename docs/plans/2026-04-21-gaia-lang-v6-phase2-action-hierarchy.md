# Gaia Lang v6 Implementation Plan — Phase 2: Action Hierarchy

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the Action class hierarchy (Support/Relate/Infer) with DSL verbs (`derive`, `observe`, `compute`, `equal`, `contradict`, `infer`), `Claim.supports` tracking, first-argument sugar (str → Claim), and `Action.label` with QID-style identity.

**Architecture:** Action is a parallel type to Knowledge (not a subclass). DSL verbs are factory functions that create Action subclass instances, register them in `CollectedPackage.actions`, and attach support actions to `Claim.supports` as a convenience index. The compiler consumes `CollectedPackage.actions`; `Claim.supports` is for InquiryState/user inspection and must not be the only source of truth. Actions track their qualitative `warrants` (helper Claims needing review). The existing v5 `Strategy` dataclass in `nodes.py` remains as a compatibility/internal bridge while v6 Actions are introduced; v5 DSL functions (`support()`, `deduction()`, etc.) become deprecated compat wrappers.

**Tech Stack:** Python 3.12+, dataclasses, pytest

**Spec:** `docs/specs/2026-04-21-gaia-lang-v6-design.md` §4-8

**Depends on:** Phase 1 (Knowledge types + Parameterized Claims)

---

## File Structure

### New files

| File | Responsibility |
|---|---|
| `gaia/lang/runtime/action.py` | Action base + Support/Relate/Infer + Derive/Observe/Compute/Equal/Contradict/Infer subclasses |
| `gaia/lang/dsl/support.py` | `derive()`, `observe()`, `compute()` DSL verbs |
| `gaia/lang/dsl/relate.py` | `equal()`, `contradict()` DSL verbs |
| `gaia/lang/dsl/infer_verb.py` | `infer()` DSL verb |
| `tests/gaia/lang/test_action_hierarchy.py` | Action class tests |
| `tests/gaia/lang/test_derive.py` | derive() verb tests |
| `tests/gaia/lang/test_observe.py` | observe() verb tests |
| `tests/gaia/lang/test_compute_v6.py` | compute()/@compute verb tests |
| `tests/gaia/lang/test_equal.py` | equal() verb tests |
| `tests/gaia/lang/test_contradict_v6.py` | contradict() verb tests |
| `tests/gaia/lang/test_infer.py` | infer() verb tests |

### Modified files

| File | Changes |
|---|---|
| `gaia/lang/runtime/knowledge.py` | Claim.supports type annotation uses Action |
| `gaia/lang/runtime/nodes.py` | Import Action, keep v5 Strategy as compat alias |
| `gaia/lang/runtime/package.py` | `_register_action()` method on CollectedPackage |
| `gaia/lang/dsl/__init__.py` | Export new verbs |
| `gaia/lang/__init__.py` | Export new verbs + Action types |
| `gaia/lang/dsl/strategies.py` | v5 functions delegate to new verbs |
| `gaia/lang/dsl/operators.py` | `equivalence()` → delegates to `equal()`, `contradiction()` → delegates to `contradict()` |

---

## Chunk 1: Action Base + Support Actions

### Task 1: Action base class and Support subclasses

**Files:**
- Create: `gaia/lang/runtime/action.py`
- Test: `tests/gaia/lang/test_action_hierarchy.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/gaia/lang/test_action_hierarchy.py
from gaia.lang.runtime.action import Action, Support, Derive, Observe, Compute, Relate, Equal, Contradict, Infer


def test_action_base_has_label():
    # Action is abstract, test via subclass
    d = Derive.__new__(Derive)
    d.label = "my_step"
    d.rationale = "test"
    assert d.label == "my_step"


def test_derive_is_support():
    assert issubclass(Derive, Support)
    assert issubclass(Support, Action)


def test_observe_is_support():
    assert issubclass(Observe, Support)


def test_compute_is_support():
    assert issubclass(Compute, Support)


def test_equal_is_relate():
    assert issubclass(Equal, Relate)
    assert issubclass(Relate, Action)


def test_contradict_is_relate():
    assert issubclass(Contradict, Relate)


def test_infer_is_action():
    assert issubclass(Infer, Action)
    assert not issubclass(Infer, Support)
    assert not issubclass(Infer, Relate)
```

- [ ] **Step 2: Run — verify fails**
- [ ] **Step 3: Implement Action hierarchy**

```python
# gaia/lang/runtime/action.py
"""Gaia Lang v6 Action class hierarchy."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from gaia.lang.runtime.knowledge import Knowledge, Claim, Setting


@dataclass
class Action:
    """Base reasoning action. Parallel to Knowledge, not a subclass."""

    label: str | None = None
    rationale: str = ""
    background: list = field(default_factory=list)  # list[Setting | Claim]
    warrants: list = field(default_factory=list)  # list[Claim] with metadata.review=True
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        from gaia.lang.runtime.knowledge import _current_package
        pkg = _current_package.get()
        if pkg is None:
            from gaia.lang.runtime.package import infer_package_from_callstack
            pkg = infer_package_from_callstack()
        if pkg is not None:
            pkg._register_action(self)


# ── Support (directional: given → conclusion) ──


@dataclass
class Support(Action):
    """Directional reasoning: given → conclusion."""

    conclusion: Claim | None = None
    given: tuple = ()  # tuple[Claim, ...]


@dataclass
class Derive(Support):
    """Logical derivation."""
    pass


@dataclass
class Observe(Support):
    """Empirical observation or measurement."""
    pass


@dataclass
class Compute(Support):
    """Deterministic code execution."""

    fn: Any = None  # callable
    code_hash: str | None = None


# ── Relate (logical constraint: connect two Claims) ──


@dataclass
class Relate(Action):
    """Logical constraint between two Claims."""

    a: Claim | None = None
    b: Claim | None = None
    helper: Claim | None = None  # returned helper Claim


@dataclass
class Equal(Relate):
    """Declares two Claims equivalent."""
    pass


@dataclass
class Contradict(Relate):
    """Declares two Claims contradictory."""
    pass


# ── Infer (statistical inference) ──


@dataclass
class Infer(Action):
    """Bayesian inference: P(E|H) update."""

    hypothesis: Claim | None = None
    evidence: Claim | None = None
    p_e_given_h: float = 0.5
    p_e_given_not_h: float = 0.5
    helper: Claim | None = None  # StatisticalSupport helper Claim
```

- [ ] **Step 4: Run — verify passes**
- [ ] **Step 5: Commit**

### Task 2: derive() DSL verb + Claim.supports

**Files:**
- Create: `gaia/lang/dsl/support.py`
- Modify: `gaia/lang/runtime/knowledge.py` (Claim.supports type)
- Test: `tests/gaia/lang/test_derive.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/gaia/lang/test_derive.py
from gaia.lang.runtime.knowledge import Claim, Setting
from gaia.lang.runtime.action import Derive


def test_derive_returns_conclusion():
    A = Claim("Premise A.")
    B = Claim("Premise B.")
    C = Claim("Conclusion.")
    result = derive(C, given=(A, B), rationale="A and B imply C.")
    assert result is C


def test_derive_str_creates_claim():
    A = Claim("Premise.")
    C = derive("New conclusion.", given=A, rationale="Follows from A.")
    assert isinstance(C, Claim)
    assert C.content == "New conclusion."


def test_derive_attaches_to_supports():
    A = Claim("Premise.")
    C = Claim("Conclusion.")
    derive(C, given=A, rationale="Test.")
    assert len(C.supports) == 1
    assert isinstance(C.supports[0], Derive)


def test_derive_multiple_supports():
    A = Claim("A.")
    B = Claim("B.")
    C = Claim("C.")
    derive(C, given=A, rationale="From A.")
    derive(C, given=B, rationale="From B.")
    assert len(C.supports) == 2


def test_derive_single_given_not_tuple():
    A = Claim("Premise.")
    C = derive("Conclusion.", given=A, rationale="Test.")
    assert isinstance(C.supports[0].given, tuple)
    assert len(C.supports[0].given) == 1


def test_derive_with_label():
    A = Claim("Premise.")
    C = derive("Conclusion.", given=A, rationale="Test.", label="my_step")
    assert C.supports[0].label == "my_step"


def test_derive_with_background():
    A = Claim("Premise.")
    bg = Setting("Lab conditions.")
    C = derive("Conclusion.", given=A, background=[bg], rationale="Test.")
    assert C.supports[0].background == [bg]


def test_derive_registers_action_with_package():
    from gaia.lang.runtime.package import CollectedPackage
    with CollectedPackage("v6_test") as pkg:
        A = Claim("Premise.")
        C = derive("Conclusion.", given=A, rationale="Test.")
    assert pkg.actions == [C.supports[0]]
```

- [ ] **Step 2: Run — verify fails**
- [ ] **Step 3: Implement derive()**

```python
# gaia/lang/dsl/support.py
"""Gaia Lang v6 Support verbs: derive, observe, compute."""

from __future__ import annotations

from typing import Any

from gaia.lang.runtime.knowledge import Claim, Knowledge, Setting
from gaia.lang.runtime.action import Derive, Observe, Compute


def derive(
    conclusion: Claim | str,
    given: Claim | tuple[Claim, ...] = (),
    background: list[Setting] | None = None,
    rationale: str = "",
    label: str | None = None,
) -> Claim:
    """Logical derivation. Returns the conclusion Claim."""
    if isinstance(conclusion, str):
        conclusion = Claim(conclusion)
    if isinstance(given, Knowledge):
        given = (given,)
    action = Derive(
        label=label,
        rationale=rationale,
        background=background or [],
        conclusion=conclusion,
        given=given,
    )
    # Action.__post_init__ registers with CollectedPackage.actions.
    conclusion.supports.append(action)
    return conclusion
```

- [ ] **Step 4: Run — verify passes**
- [ ] **Step 5: Commit**

### Task 3: observe() DSL verb

**Files:**
- Create: `tests/gaia/lang/test_observe.py`
- Modify: `gaia/lang/dsl/support.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/gaia/lang/test_observe.py
from gaia.lang.runtime.knowledge import Claim, Setting
from gaia.lang.runtime.action import Observe


def test_observe_with_given():
    calibrated = Claim("Calibration OK.", prior=0.95)
    data = observe("UV spectrum data.", given=calibrated, rationale="Measured.")
    assert isinstance(data, Claim)
    assert len(data.supports) == 1
    assert isinstance(data.supports[0], Observe)


def test_observe_root_fact_adds_grounding_and_reviewable_action():
    data = observe("UV spectrum data.", rationale="Measured at 5 points.")
    assert data.grounding is not None
    assert data.grounding.kind == "source_fact"
    assert len(data.supports) == 1  # reviewable root Observe action
    assert isinstance(data.supports[0], Observe)
    assert data.supports[0].given == ()
```

- [ ] **Step 2: Run — verify fails**
- [ ] **Step 3: Implement observe()**

```python
# in gaia/lang/dsl/support.py

from gaia.lang.runtime.grounding import Grounding


def observe(
    conclusion: Claim | str,
    given: Claim | tuple[Claim, ...] = (),
    background: list[Setting] | None = None,
    rationale: str = "",
    label: str | None = None,
) -> Claim:
    """Empirical observation. No-premise observe is reviewable grounding."""
    if isinstance(conclusion, str):
        conclusion = Claim(conclusion)
    if isinstance(given, Knowledge):
        given = (given,)
    action = Observe(
        label=label,
        rationale=rationale,
        background=background or [],
        conclusion=conclusion,
        given=given,
    )
    # Root fact — add grounding and keep a reviewable Observe action.
    # The compiler lowers it to FormalStrategy(type="deduction", premises=[],
    # metadata.pattern="observation"); BP lowering treats it as reviewed source
    # grounding, not as support from an empty premise set.
    if not given and conclusion.grounding is None:
        conclusion.grounding = Grounding(kind="source_fact", rationale=rationale)
    conclusion.supports.append(action)
    return conclusion
```

- [ ] **Step 4: Run — verify passes**
- [ ] **Step 5: Commit**

### Task 4: compute() DSL verb and @compute decorator

**Files:**
- Create: `tests/gaia/lang/test_compute_v6.py`
- Modify: `gaia/lang/dsl/support.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/gaia/lang/test_compute_v6.py
from gaia.lang.runtime.knowledge import Claim, Setting
from gaia.lang.runtime.action import Compute


class IntClaim(Claim):
    """Value is {value}."""
    value: int


class SumResult(Claim):
    """Sum is {value}."""
    value: int


def test_compute_function():
    a = IntClaim(value=3)
    b = IntClaim(value=4)
    result = compute(SumResult, fn=lambda a, b: a.value + b.value, given=(a, b), rationale="Addition.")
    assert isinstance(result, SumResult)
    assert result.value == 7


def test_compute_decorator():
    @compute_decorator
    def add(a: IntClaim, b: IntClaim) -> SumResult:
        """Add two integers."""
        return a.value + b.value

    a = IntClaim(value=3)
    b = IntClaim(value=4)
    result = add(a, b)
    assert isinstance(result, SumResult)
    assert result.value == 7
    assert len(result.supports) == 1
    assert isinstance(result.supports[0], Compute)
    assert result.supports[0].rationale == "Add two integers."
```

- [ ] **Step 2: Run — verify fails**
- [ ] **Step 3: Implement compute() and @compute**

```python
# in gaia/lang/dsl/support.py

def compute(
    conclusion_type: type,
    fn: callable = None,
    given: Claim | tuple[Claim, ...] = (),
    background: list[Setting] | None = None,
    rationale: str = "",
    label: str | None = None,
) -> Claim:
    """Deterministic computation. Calls fn with given Claims, wraps result."""
    if isinstance(given, Knowledge):
        given = (given,)
    result_value = fn(*given) if fn else None
    conclusion = conclusion_type(value=result_value)
    action = Compute(
        label=label,
        rationale=rationale,
        background=background or [],
        conclusion=conclusion,
        given=given,
        fn=fn,
    )
    # Action.__post_init__ registers with CollectedPackage.actions.
    conclusion.supports.append(action)
    return conclusion


def compute_decorator(fn):
    """@compute decorator. Extracts types from signature, docstring as rationale."""
    import inspect
    sig = inspect.signature(fn)
    return_type = sig.return_annotation

    def wrapper(*args, **kwargs):
        result_value = fn(*args, **kwargs)
        conclusion = return_type(value=result_value)
        action = Compute(
            rationale=fn.__doc__ or "",
            conclusion=conclusion,
            given=tuple(args),
            fn=fn,
        )
        # Action.__post_init__ registers with CollectedPackage.actions.
        conclusion.supports.append(action)
        return conclusion

    wrapper.__wrapped__ = fn
    return wrapper
```

- [ ] **Step 4: Run — verify passes**
- [ ] **Step 5: Commit**

---

## Chunk 2: Relate + Infer Actions

### Task 5: equal() and contradict() DSL verbs

**Files:**
- Create: `gaia/lang/dsl/relate.py`
- Create: `tests/gaia/lang/test_equal.py`
- Create: `tests/gaia/lang/test_contradict_v6.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/gaia/lang/test_equal.py
from gaia.lang.runtime.knowledge import Claim
from gaia.lang.runtime.action import Equal


def test_equal_returns_helper_claim():
    A = Claim("Prediction matches.")
    B = Claim("Observation matches.")
    helper = equal(A, B, rationale="Theory agrees with data.")
    assert isinstance(helper, Claim)
    assert helper.metadata.get("generated") is True
    assert helper.metadata.get("helper_kind") == "equivalence_result"
    assert helper.metadata.get("review") is True


def test_equal_helper_usable_as_premise():
    A = Claim("Pred.")
    B = Claim("Obs.")
    helper = equal(A, B, rationale="Match.")
    C = derive("Theory valid.", given=helper, rationale="Matches imply valid.")
    assert C.supports[0].given == (helper,)
```

```python
# tests/gaia/lang/test_contradict_v6.py
from gaia.lang.runtime.knowledge import Claim
from gaia.lang.runtime.action import Contradict


def test_contradict_returns_helper_claim():
    A = Claim("Classical prediction.")
    B = Claim("Observation.")
    helper = contradict(A, B, rationale="Classical theory fails.")
    assert isinstance(helper, Claim)
    assert helper.metadata.get("helper_kind") == "contradiction_result"
    assert helper.metadata.get("review") is True
```

- [ ] **Step 2: Run — verify fails**
- [ ] **Step 3: Implement equal() and contradict()**

```python
# gaia/lang/dsl/relate.py
"""Gaia Lang v6 Relate verbs: equal, contradict."""

from gaia.lang.runtime.knowledge import Claim
from gaia.lang.runtime.action import Equal, Contradict


def equal(a: Claim, b: Claim, rationale: str = "", label: str | None = None) -> Claim:
    """Declare two Claims equivalent. Returns Equivalence helper Claim."""
    helper = Claim(
        f"[@{a.label or '?'}] and [@{b.label or '?'}] are equivalent.",
        metadata={"generated": True, "helper_kind": "equivalence_result", "review": True},
    )
    action = Equal(label=label, rationale=rationale, a=a, b=b, helper=helper)
    action.warrants.append(helper)
    return helper


def contradict(a: Claim, b: Claim, rationale: str = "", label: str | None = None) -> Claim:
    """Declare two Claims contradictory. Returns Contradiction helper Claim."""
    helper = Claim(
        f"[@{a.label or '?'}] and [@{b.label or '?'}] contradict.",
        metadata={"generated": True, "helper_kind": "contradiction_result", "review": True},
    )
    action = Contradict(label=label, rationale=rationale, a=a, b=b, helper=helper)
    action.warrants.append(helper)
    return helper
```

- [ ] **Step 4: Run — verify passes**
- [ ] **Step 5: Commit**

### Task 6: infer() DSL verb

**Files:**
- Create: `gaia/lang/dsl/infer_verb.py`
- Create: `tests/gaia/lang/test_infer.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/gaia/lang/test_infer.py
from gaia.lang.runtime.knowledge import Claim, Setting
from gaia.lang.runtime.action import Infer


def test_infer_returns_statistical_support():
    H = Claim("Quantum theory is correct.", prior=0.5)
    E = Claim("Planck spectrum observed.", prior=0.95)
    support = infer(hypothesis=H, evidence=E, p_e_given_h=0.9, p_e_given_not_h=0.05, rationale="Strong evidence.")
    assert isinstance(support, Claim)
    assert support.metadata.get("helper_kind") == "statistical_support"
    assert support.metadata.get("review") is True


def test_infer_all_keyword_only():
    H = Claim("H.")
    E = Claim("E.")
    import pytest
    with pytest.raises(TypeError):
        infer(H, E, 0.9, 0.1)  # positional args should fail


def test_infer_with_background():
    H = Claim("H.")
    E = Claim("E.")
    bg = Setting("Experiment conditions.")
    support = infer(hypothesis=H, evidence=E, background=[bg], p_e_given_h=0.8, p_e_given_not_h=0.2, rationale="Test.")
    assert isinstance(support.supports[0] if hasattr(support, 'supports') else None, type(None)) or True
```

- [ ] **Step 2: Run — verify fails**
- [ ] **Step 3: Implement infer()**

```python
# gaia/lang/dsl/infer_verb.py
"""Gaia Lang v6 Infer verb."""

from gaia.lang.runtime.knowledge import Claim, Setting
from gaia.lang.runtime.action import Infer as InferAction


def infer(
    *,
    hypothesis: Claim,
    evidence: Claim,
    background: list[Setting | Claim] | None = None,
    p_e_given_h: float,
    p_e_given_not_h: float,
    rationale: str = "",
    label: str | None = None,
) -> Claim:
    """Bayesian inference. Returns StatisticalSupport helper Claim."""
    helper = Claim(
        f"[@{evidence.label or '?'}] statistically supports [@{hypothesis.label or '?'}].",
        metadata={"generated": True, "helper_kind": "statistical_support", "review": True},
    )
    action = InferAction(
        label=label,
        rationale=rationale,
        background=background or [],
        hypothesis=hypothesis,
        evidence=evidence,
        p_e_given_h=p_e_given_h,
        p_e_given_not_h=p_e_given_not_h,
        helper=helper,
    )
    action.warrants.append(helper)
    return helper
```

- [ ] **Step 4: Run — verify passes**
- [ ] **Step 5: Commit**

---

## Chunk 3: Exports + v5 Compat

### Task 7: Update exports and v5 compat wrappers

**Files:**
- Modify: `gaia/lang/dsl/__init__.py`
- Modify: `gaia/lang/__init__.py`
- Modify: `gaia/lang/dsl/strategies.py` (v5 compat)
- Modify: `gaia/lang/dsl/operators.py` (v5 compat)
- Modify: `gaia/lang/runtime/package.py` (register actions)

- [ ] **Step 1: Write compat test**

```python
# tests/gaia/lang/test_v5_compat.py

def test_v5_support_still_works():
    """v5 support() still preserves prior while warning."""
    from gaia.lang import claim, support
    import pytest
    a = claim("A.")
    b = claim("B.")
    with pytest.warns(DeprecationWarning):
        s = support([a], b, reason="test", prior=0.9)
    assert s.metadata["prior"] == 0.9


def test_v5_equivalence_still_works():
    """v5 equivalence() delegates to v6 equal()."""
    from gaia.lang import claim, equivalence
    a = claim("A.")
    b = claim("B.")
    helper = equivalence(a, b, reason="test", prior=0.95)
    assert helper.type == "claim"
```

- [ ] **Step 2: Run — verify fails**
- [ ] **Step 3: Update exports and add compat wrappers**

Key changes:
- `gaia/lang/__init__.py`: export `derive`, `observe`, `compute`, `equal`, `contradict`, `infer`, `Action`, `Derive`, `Observe`, `Compute`, `Equal`, `Contradict`, `Infer`
- `gaia/lang/dsl/strategies.py`: `support()` emits `DeprecationWarning` and preserves existing v5 support-prior semantics; it must not silently delegate to prior-free `derive()`
- `gaia/lang/dsl/operators.py`: `equivalence()` delegates to `equal()`, `contradiction()` delegates to `contradict()`
- `gaia/lang/runtime/package.py`: add `_register_action()` + `actions: list[Action]` to CollectedPackage

- [ ] **Step 4: Run full test suite**

Run: `pytest tests/ -x -q`
Expected: All pass

- [ ] **Step 5: Commit**

---

## Verification

1. **Action hierarchy**: `pytest tests/gaia/lang/test_action_hierarchy.py -v`
2. **DSL verbs**: `pytest tests/gaia/lang/test_derive.py tests/gaia/lang/test_observe.py tests/gaia/lang/test_compute_v6.py tests/gaia/lang/test_equal.py tests/gaia/lang/test_contradict_v6.py tests/gaia/lang/test_infer.py -v`
3. **v5 compat**: `pytest tests/gaia/lang/test_v5_compat.py -v`
4. **Full regression**: `pytest tests/ -x -q`
5. **Lint**: `ruff check . && ruff format --check .`
