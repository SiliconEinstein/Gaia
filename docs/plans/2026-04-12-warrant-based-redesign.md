# Warrant-Based Operator/Strategy Redesign Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the warrant-based audit framework: implication becomes a Relation operator, new `support()` and `compare()` DSL primitives, abduction/induction as binary CompositeStrategies with composition warrants.

**Architecture:** The core change is implication moving from Directed (1 variable) to Relation (2 variables, generates helper claim H). This enables `support()` (two IMPLIES) and `compare()` (two equivalences) as FormalStrategy primitives. Abduction and induction become binary CompositeStrategies built from support + compare.

**Tech Stack:** Python 3.12+, Pydantic v2, pytest

**Spec:** `docs/specs/2026-04-06-operator-strategy-redesign.md` (PR #412 merged, PR #414 open)

---

## File Map

| File | Responsibility | Action |
|------|---------------|--------|
| `gaia/ir/operator.py` | Operator schema + arity validation | Modify: implication arity 1→2 |
| `gaia/ir/formalize.py` | Named strategy → FormalExpr expansion | Modify: all builders using implication |
| `gaia/bp/potentials.py` | Factor potential functions | Modify: implication_potential signature |
| `gaia/bp/lowering.py` | IR → FactorGraph lowering | Modify: implication factor construction |
| `gaia/lang/runtime/nodes.py` | DSL Strategy dataclass | Modify: add composition_warrant field |
| `gaia/lang/dsl/strategies.py` | DSL strategy functions | Modify: deduction, abduction, induction; Add: support, compare |
| `gaia/lang/dsl/operators.py` | DSL operator functions | No change (equivalence etc. already Relation) |
| `gaia/lang/__init__.py` | Public API exports | Modify: add support, compare |
| `gaia/lang/compiler/compile.py` | DSL → IR compilation | Modify: handle composition_warrant, new strategy types |
| `tests/ir/test_operator.py` | Operator arity tests | Modify: implication arity 1→2 |
| `tests/ir/test_formalize.py` | Formalization tests | Modify: deduction builds |
| `tests/gaia/lang/test_strategies.py` | DSL strategy tests | Add: support, compare, new abduction/induction |
| `tests/gaia/bp/test_potentials.py` | BP potential tests | Modify: implication potential |

---

## Chunk 1: Implication Operator Change (Phase 0)

The foundation: implication moves from Directed (1 variable, conclusion = consequent) to Relation (2 variables, conclusion = helper claim H asserting "A→B").

### Task 1: Update Implication Arity + Reclassify as Relation

**Files:**
- Modify: `gaia/ir/operator.py` (arity validator, ~line 50)
- Modify: `gaia/bp/lowering.py:27` (add IMPLICATION to `_RELATION_OPS`)
- Modify: `gaia/cli/commands/_detailed_reasoning.py:113` (add "implication" to `_UNDIRECTED_OPERATORS`)
- Modify: `gaia/cli/commands/_simplified_mermaid.py:35` (same)
- Modify: `gaia/cli/commands/_github.py:337` (add "implication" to `_UNDIRECTED`)
- Test: `tests/ir/test_operator.py`

- [ ] **Step 1: Write failing test — implication now accepts 2 variables**

```python
# tests/ir/test_operator.py — add new test
def test_implication_binary():
    """Implication now takes 2 variables (antecedent + consequent) and a helper claim conclusion."""
    op = Operator(
        operator=OperatorType.IMPLICATION,
        variables=["claim_A", "claim_B"],
        conclusion="helper_implies_A_B",
    )
    assert op.variables == ["claim_A", "claim_B"]
    assert op.conclusion == "helper_implies_A_B"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/ir/test_operator.py::test_implication_binary -v`
Expected: FAIL — arity validator rejects 2 variables for implication (currently requires exactly 1)

- [ ] **Step 3: Update arity validator**

In `gaia/ir/operator.py`, find the `@model_validator` that checks arity. Change implication's expected arity from 1 to 2:

```python
# In the arity validation section, change:
#   OperatorType.IMPLICATION: 1
# To:
#   OperatorType.IMPLICATION: 2
```

- [ ] **Step 4: Reclassify implication as Relation in lowering and rendering**

In `gaia/bp/lowering.py:27`, add IMPLICATION to `_RELATION_OPS`:
```python
_RELATION_OPS = frozenset({
    OperatorType.EQUIVALENCE,
    OperatorType.CONTRADICTION,
    OperatorType.COMPLEMENT,
    OperatorType.IMPLICATION,  # NEW: implication is now Relation
})
```

In `gaia/cli/commands/_detailed_reasoning.py:113` and `_simplified_mermaid.py:35`, add "implication" to `_UNDIRECTED_OPERATORS`:
```python
_UNDIRECTED_OPERATORS = frozenset({"equivalence", "contradiction", "complement", "implication"})
```

In `gaia/cli/commands/_github.py:337`:
```python
_UNDIRECTED = {"equivalence", "contradiction", "complement", "implication"}
```

This means implication conclusions now get `π = 1-ε` default in lowering (same as other Relation operators) until review sets the actual value.

- [ ] **Step 5: Update existing test that expects arity 1**

In `tests/ir/test_operator.py`, find the test that validates implication with 1 variable and update it to expect 2. Also update the "wrong arity" test to reject 1 variable.

- [ ] **Step 6: Run all operator tests + lowering tests + mermaid tests**

Run: `pytest tests/ir/test_operator.py tests/gaia/bp/ tests/cli/ -v`
Expected: All PASS

- [ ] **Step 7: Commit**

```bash
git add gaia/ir/operator.py gaia/bp/lowering.py \
       gaia/cli/commands/_detailed_reasoning.py \
       gaia/cli/commands/_simplified_mermaid.py \
       gaia/cli/commands/_github.py \
       tests/ir/test_operator.py
git commit -m "feat(ir): implication arity 1→2, reclassify Directed→Relation (Computation vs Relation)"
```

### Task 2: Update Implication Potential Function

**Files:**
- Modify: `gaia/bp/potentials.py` (~line 25)
- Test: `tests/gaia/bp/test_potentials.py` (or equivalent)

- [ ] **Step 1: Write failing test — implication potential with 3 variables (A, B, H)**

The new implication factor is a 3-variable factor f(A, B, H) where H = "A→B holds":

| A | B | H=1 (holds) | H=0 (violated) |
|---|---|-------------|----------------|
| 0 | 0 | HIGH | LOW |
| 0 | 1 | HIGH | LOW |
| 1 | 0 | LOW | HIGH |
| 1 | 1 | HIGH | LOW |

```python
def test_implication_potential_ternary():
    """Implication is now a ternary factor f(antecedent, consequent, helper)."""
    from gaia.bp.potentials import implication_potential, CROMWELL_EPS

    HIGH = 1.0 - CROMWELL_EPS
    LOW = CROMWELL_EPS

    # H=1: standard truth table
    assert implication_potential({"A": 0, "B": 0, "H": 1}, "A", "B", "H") == pytest.approx(HIGH)
    assert implication_potential({"A": 0, "B": 1, "H": 1}, "A", "B", "H") == pytest.approx(HIGH)
    assert implication_potential({"A": 1, "B": 0, "H": 1}, "A", "B", "H") == pytest.approx(LOW)
    assert implication_potential({"A": 1, "B": 1, "H": 1}, "A", "B", "H") == pytest.approx(HIGH)

    # H=0: complement of truth table
    assert implication_potential({"A": 1, "B": 0, "H": 0}, "A", "B", "H") == pytest.approx(HIGH)
    assert implication_potential({"A": 1, "B": 1, "H": 0}, "A", "B", "H") == pytest.approx(LOW)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/gaia/bp/test_potentials.py::test_implication_potential_ternary -v`
Expected: FAIL — current signature doesn't accept helper variable

- [ ] **Step 3: Update implication_potential to ternary**

```python
def implication_potential(
    assignment: Assignment,
    antecedent: str,
    consequent: str,
    helper: str,
) -> float:
    """Ternary implication factor: f(A, B, H).
    
    H=1: standard implication truth table (A=1,B=0 forbidden).
    H=0: complement (A=1,B=0 allowed, others forbidden).
    """
    a, b, h = assignment[antecedent], assignment[consequent], assignment[helper]
    truth_table_holds = not (a == 1 and b == 0)
    if h == 1:
        return _HIGH if truth_table_holds else _LOW
    else:
        return _LOW if truth_table_holds else _HIGH
```

- [ ] **Step 4: Run test**

Run: `pytest tests/gaia/bp/test_potentials.py -v`
Expected: PASS (new test passes, check existing tests — may need updates)

- [ ] **Step 5: Commit**

```bash
git add gaia/bp/potentials.py tests/gaia/bp/test_potentials.py
git commit -m "feat(bp): update implication to ternary factor f(A, B, H)"
```

### Task 3: Update Formalization — Deduction Builder

**Files:**
- Modify: `gaia/ir/formalize.py` (~line 220, `_build_deduction`)
- Test: `tests/ir/test_formalize.py`

- [ ] **Step 1: Write failing test — deduction generates binary implication with helper claim**

```python
def test_deduction_single_premise_generates_helper():
    """Single-premise deduction: implication([A, C], conclusion=H) where H is a helper claim."""
    # Build a minimal strategy
    result = formalize_named_strategy(
        strategy_type="deduction",
        premises=["premise_A"],
        conclusion="conclusion_C",
        # ... (fill in required params based on existing test patterns)
    )
    # Find the implication operator
    impl_ops = [op for op in result.strategy.formal_expr.operators if op.operator == "implication"]
    assert len(impl_ops) == 1
    impl = impl_ops[0]
    # Binary: 2 variables
    assert len(impl.variables) == 2
    assert impl.variables == ["premise_A", "conclusion_C"]
    # Conclusion is a NEW helper claim, not conclusion_C
    assert impl.conclusion != "conclusion_C"
    assert impl.conclusion.startswith("__")  # helper claim naming convention
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/ir/test_formalize.py::test_deduction_single_premise_generates_helper -v`
Expected: FAIL — current deduction uses 1-variable implication

- [ ] **Step 3: Update `_build_deduction` in formalize.py**

```python
def _build_deduction(builder: _TemplateBuilder) -> list[Operator]:
    if len(builder.premises) == 1:
        # Single premise: implication([premise, conclusion], helper_H)
        h = builder.add_helper("implication", f"implies({builder.premises[0]}, {builder.conclusion})")
        return [
            Operator(
                operator="implication",
                variables=[builder.premises[0], builder.conclusion],
                conclusion=h.id,
            ),
        ]
    else:
        # Multiple premises: conjunction + implication
        conj = builder.add_helper("conjunction", _all_true_name(builder.premises))
        h = builder.add_helper("implication", f"implies({conj.id}, {builder.conclusion})")
        return [
            Operator(
                operator="conjunction",
                variables=builder.premises,
                conclusion=conj.id,
            ),
            Operator(
                operator="implication",
                variables=[conj.id, builder.conclusion],
                conclusion=h.id,
            ),
        ]
```

- [ ] **Step 4: Update all other builders that use implication**

Search `formalize.py` for `operator="implication"` and update each to use 2 variables + helper claim conclusion. Affected builders:
- `_build_deduction` (done above)
- `_build_mathematical_induction`
- `_build_elimination`
- `_build_case_analysis`
- `_build_analogy`
- `_build_extrapolation`

Each needs the same pattern: `variables=[antecedent, consequent]` with a new helper claim as conclusion.

- [ ] **Step 5: Run all formalization tests**

Run: `pytest tests/ir/test_formalize.py -v`
Expected: Some may need updates — fix them

- [ ] **Step 6: Commit**

```bash
git add gaia/ir/formalize.py tests/ir/test_formalize.py
git commit -m "feat(ir): update all formalization builders for binary implication"
```

### Task 4: Update Lowering for Binary Implication

**Files:**
- Modify: `gaia/bp/lowering.py`
- Test: `tests/gaia/bp/test_lowering.py` (or equivalent)

- [ ] **Step 1: Write failing test — lowering creates 3-variable factor for implication**

```python
def test_lower_implication_ternary_factor():
    """Implication operator lowers to a 3-variable factor (antecedent, consequent, helper)."""
    # Create a minimal LocalCanonicalGraph with one implication operator
    # ... (follow existing lowering test patterns)
    fg = lower_local_graph(graph)
    # Find the implication factor
    impl_factors = [f for f in fg.factors if f.type == FactorType.IMPLICATION]
    assert len(impl_factors) == 1
    assert len(impl_factors[0].variables) == 3  # A, B, H
```

- [ ] **Step 2: Run test, expect FAIL**

- [ ] **Step 3: Update lowering to pass antecedent + consequent + helper to factor**

In `gaia/bp/lowering.py`, find where implication operators are lowered. Currently it likely maps `variables[0]` (antecedent) and `conclusion` (consequent) to a 2-variable factor. Change to: `variables[0]` (antecedent), `variables[1]` (consequent), `conclusion` (helper claim) → 3-variable factor.

- [ ] **Step 4: Run all lowering + BP tests**

Run: `pytest tests/gaia/bp/ -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add gaia/bp/lowering.py tests/gaia/bp/
git commit -m "feat(bp): lower binary implication to 3-variable factor"
```

### Task 5: Warrant Metadata on Helper Claims

**Files:**
- Modify: `gaia/ir/formalize.py` (helper claim generation)
- Modify: `gaia/lang/dsl/operators.py` (DSL operator helper claims)
- Test: `tests/ir/test_formalize.py`

- [ ] **Step 1: Write failing test — relation operator helper claims have warrant metadata**

```python
def test_implication_helper_has_warrant_metadata():
    """Implication helper claim should have question + warrant in metadata."""
    result = formalize_named_strategy(
        strategy_type="deduction",
        premises=["A"],
        conclusion="B",
        reason="mathematical derivation",
        # ...
    )
    # Find the helper claim for implication
    helpers = [k for k in result.knowledges if k.metadata.get("helper_kind") == "implication_result"]
    assert len(helpers) == 1
    h = helpers[0]
    assert "question" in h.metadata
    assert "warrant" in h.metadata
    assert h.metadata["warrant"] == "mathematical derivation"
```

- [ ] **Step 2: Run test, expect FAIL**

- [ ] **Step 3: Update helper claim generation to include question + warrant**

In `gaia/ir/formalize.py`, update `_TemplateBuilder.add_helper()` to include question template and warrant text:

```python
def add_helper(self, operator_name: str, canonical_name: str, warrant: str = "") -> Knowledge:
    # ... existing logic ...
    metadata = {
        # ... existing metadata ...
        "question": self._question_template(operator_name, variables),
        "warrant": warrant or "显而易见",
    }
    # ...

def _question_template(self, operator_name: str, variables: list[str]) -> str:
    templates = {
        "implication": f"Does {variables[0]} imply {variables[1]}?",
        "equivalence": f"Are {variables[0]} and {variables[1]} equivalent?",
        "contradiction": f"Can {variables[0]} and {variables[1]} not both be true?",
        "complement": f"Is exactly one of {variables[0]}, {variables[1]} true?",
    }
    return templates.get(operator_name, "")
```

- [ ] **Step 4: Propagate reason from DSL to warrant metadata**

In `gaia/lang/compiler/compile.py`, ensure Strategy.reason is passed through to formalize_named_strategy so it reaches the helper claim's metadata["warrant"].

- [ ] **Step 5: Run tests**

Run: `pytest tests/ir/test_formalize.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add gaia/ir/formalize.py gaia/lang/compiler/compile.py tests/ir/test_formalize.py
git commit -m "feat(ir): add warrant metadata (question + reason) to relation operator helper claims"
```

---

## Chunk 2: New DSL Primitives (Phase 1)

### Task 6: Add `support()` DSL Function

**Files:**
- Modify: `gaia/lang/dsl/strategies.py`
- Modify: `gaia/lang/__init__.py`
- Create: `tests/gaia/lang/test_support.py`

- [ ] **Step 1: Write failing test**

```python
# tests/gaia/lang/test_support.py
from gaia.lang import claim, support

def test_support_basic():
    """support() creates a Strategy with type='support' and stores reverse_reason."""
    a = claim("Theory A")
    b = claim("Observation B")
    s = support(
        [a], b,
        reason="A predicts B",
        reverse_reason="B confirms A",
    )
    assert s.type == "support"
    assert s.premises == [a]
    assert s.conclusion is b
    assert s.reason == "A predicts B"
    assert s.metadata.get("reverse_reason") == "B confirms A"

def test_support_requires_at_least_one_premise():
    with pytest.raises(ValueError):
        support([], claim("B"))
```

- [ ] **Step 2: Run test, expect FAIL**

Run: `pytest tests/gaia/lang/test_support.py -v`
Expected: FAIL — `support` not importable

- [ ] **Step 3: Implement `support()`**

```python
# gaia/lang/dsl/strategies.py
def support(
    premises: list[Knowledge],
    conclusion: Knowledge,
    *,
    background: list[Knowledge] | None = None,
    reason: ReasonInput = "",
    reverse_reason: ReasonInput = "",
) -> Strategy:
    """Bidirectional support (sufficiency + necessity). Compiles to two IMPLIES.

    reason → forward implication warrant (sufficiency: A → B).
    reverse_reason → reverse implication warrant (necessity: B → A).
    """
    if len(premises) < 1:
        raise ValueError("support() requires at least 1 premise")
    return _named_strategy(
        "support",
        premises=premises,
        conclusion=conclusion,
        background=background,
        reason=reason,
        metadata={"reverse_reason": reverse_reason},
    )
```

- [ ] **Step 4: Add to exports**

In `gaia/lang/__init__.py`, add `support` to imports and `__all__`.

- [ ] **Step 5: Run test**

Run: `pytest tests/gaia/lang/test_support.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add gaia/lang/dsl/strategies.py gaia/lang/__init__.py tests/gaia/lang/test_support.py
git commit -m "feat(dsl): add support() — bidirectional reasoning primitive"
```

### Task 7: Add `support` Formalization Builder

**Files:**
- Modify: `gaia/ir/formalize.py`
- Modify: `gaia/ir/strategy.py` (add SUPPORT to StrategyType)
- Test: `tests/ir/test_formalize.py`

- [ ] **Step 1: Write failing test — support formalizes to two IMPLIES**

```python
def test_formalize_support():
    """Support generates forward + reverse IMPLIES, each with helper claim."""
    result = formalize_named_strategy(
        strategy_type="support",
        premises=["A"],
        conclusion="B",
        reason="A predicts B",
        metadata={"reverse_reason": "B confirms A"},
    )
    ops = result.strategy.formal_expr.operators
    impl_ops = [op for op in ops if op.operator == "implication"]
    assert len(impl_ops) == 2

    # Forward: [A, B] → H_fwd
    fwd = impl_ops[0]
    assert fwd.variables == ["A", "B"]

    # Reverse: [B, A] → H_rev
    rev = impl_ops[1]
    assert rev.variables == ["B", "A"]
```

- [ ] **Step 2: Run test, expect FAIL**

- [ ] **Step 3: Add SUPPORT to StrategyType and implement builder**

In `gaia/ir/strategy.py`:
```python
class StrategyType(StrEnum):
    # ... existing ...
    SUPPORT = "support"
```

In `gaia/ir/formalize.py`:
```python
def _build_support(builder: _TemplateBuilder) -> list[Operator]:
    """Support: forward IMPLIES + reverse IMPLIES."""
    reverse_reason = builder.metadata.get("reverse_reason", "")

    if len(builder.premises) == 1:
        antecedent = builder.premises[0]
    else:
        conj = builder.add_helper("conjunction", _all_true_name(builder.premises))
        antecedent = conj.id

    h_fwd = builder.add_helper(
        "implication",
        f"implies({antecedent}, {builder.conclusion})",
        warrant=builder.reason,
    )
    h_rev = builder.add_helper(
        "implication",
        f"implies({builder.conclusion}, {antecedent})",
        warrant=reverse_reason,
    )

    ops = []
    if len(builder.premises) > 1:
        ops.append(Operator(
            operator="conjunction",
            variables=builder.premises,
            conclusion=conj.id,
        ))
    ops.extend([
        Operator(operator="implication", variables=[antecedent, builder.conclusion], conclusion=h_fwd.id),
        Operator(operator="implication", variables=[builder.conclusion, antecedent], conclusion=h_rev.id),
    ])
    return ops
```

Register in the builder dispatch map.

- [ ] **Step 4: Run tests**

Run: `pytest tests/ir/test_formalize.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add gaia/ir/strategy.py gaia/ir/formalize.py tests/ir/test_formalize.py
git commit -m "feat(ir): add support formalization — two IMPLIES with independent warrants"
```

### Task 8: Add `compare()` DSL Function + Formalization

**Files:**
- Modify: `gaia/lang/dsl/strategies.py`
- Modify: `gaia/ir/formalize.py`
- Modify: `gaia/ir/strategy.py` (add COMPARE)
- Modify: `gaia/lang/__init__.py`
- Create: `tests/gaia/lang/test_compare.py`

- [ ] **Step 1: Write failing test**

```python
# tests/gaia/lang/test_compare.py
from gaia.lang import claim, compare

def test_compare_basic():
    """compare() creates a Strategy with auto-generated comparison claim."""
    pred_h = claim("H predicts 0.97K")
    pred_alt = claim("Alt predicts 2K")
    obs = claim("Measured 1.2K")

    comp = compare(pred_h, pred_alt, obs, reason="same experiment")
    assert comp.type == "compare"
    assert comp.conclusion is not None
    assert comp.conclusion.type == "claim"
    assert "comparison" in comp.conclusion.metadata.get("helper_kind", "")
```

- [ ] **Step 2: Run test, expect FAIL**

- [ ] **Step 3: Implement compare()**

```python
# gaia/lang/dsl/strategies.py
def compare(
    pred_h: Knowledge,
    pred_alt: Knowledge,
    observation: Knowledge,
    *,
    background: list[Knowledge] | None = None,
    reason: ReasonInput = "",
) -> Strategy:
    """Compare two predictions against observation. First arg is claimed-better.

    Compiles to: equivalence(pred_h, obs) + equivalence(pred_alt, obs).
    Conclusion: auto-generated comparison claim (pi=0.5, no warrant).
    """
    comparison_claim = Knowledge(
        content=f"comparison({pred_h.label or 'H'}, {pred_alt.label or 'Alt'}, {observation.label or 'Obs'})",
        type="claim",
        metadata={"helper_kind": "comparison_result", "generated": True},
    )
    return _named_strategy(
        "compare",
        premises=[pred_h, pred_alt, observation],
        conclusion=comparison_claim,
        background=background,
        reason=reason,
    )
```

- [ ] **Step 4: Add COMPARE to StrategyType and formalization builder**

```python
# gaia/ir/strategy.py
COMPARE = "compare"

# gaia/ir/formalize.py
def _build_compare(builder: _TemplateBuilder) -> list[Operator]:
    """Compare: two equivalences (pred_h vs obs, pred_alt vs obs)."""
    pred_h, pred_alt, observation = builder.premises[0], builder.premises[1], builder.premises[2]

    h_eq1 = builder.add_helper("equivalence", f"matches({pred_h}, {observation})")
    h_eq2 = builder.add_helper("equivalence", f"matches({pred_alt}, {observation})")

    return [
        Operator(operator="equivalence", variables=[pred_h, observation], conclusion=h_eq1.id),
        Operator(operator="equivalence", variables=[pred_alt, observation], conclusion=h_eq2.id),
    ]
```

- [ ] **Step 5: Add to exports, run tests**

Run: `pytest tests/gaia/lang/test_compare.py tests/ir/test_formalize.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add gaia/lang/dsl/strategies.py gaia/ir/strategy.py gaia/ir/formalize.py \
       gaia/lang/__init__.py tests/gaia/lang/test_compare.py
git commit -m "feat: add compare() — prediction matching primitive with comparison claim"
```

---

## Chunk 3: Composite Strategies (Phase 2)

### Task 9: Add composition_warrant to Strategy Dataclass

**Files:**
- Modify: `gaia/lang/runtime/nodes.py`
- Test: `tests/gaia/lang/test_strategies.py`

- [ ] **Step 1: Write test**

```python
def test_strategy_composition_warrant():
    """Strategy can hold a composition warrant claim."""
    warrant = Knowledge(content="validity check", type="claim")
    s = Strategy(type="abduction", composition_warrant=warrant)
    assert s.composition_warrant is warrant
```

- [ ] **Step 2: Add field to Strategy**

```python
# gaia/lang/runtime/nodes.py, in Strategy dataclass
composition_warrant: Knowledge | None = None
```

- [ ] **Step 3: Run tests**

Run: `pytest tests/gaia/lang/ -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add gaia/lang/runtime/nodes.py tests/gaia/lang/
git commit -m "feat(runtime): add composition_warrant field to Strategy"
```

### Task 10: Refactor abduction() as Binary CompositeStrategy

**Files:**
- Modify: `gaia/lang/dsl/strategies.py` (rewrite abduction)
- Create: `tests/gaia/lang/test_abduction_v2.py`

- [ ] **Step 1: Write failing test**

```python
# tests/gaia/lang/test_abduction_v2.py
from gaia.lang import claim, support, abduction

def test_abduction_binary_composite():
    """abduction takes 2 supports + observation, returns CompositeStrategy."""
    H = claim("New theory")
    Alt = claim("Old theory")
    pred_h = claim("H predicts 0.97K")
    pred_alt = claim("Alt predicts 2K")
    obs = claim("Measured 1.2K")

    s_h = support([H], pred_h, reason="first-principles", reverse_reason="validates method")
    s_alt = support([Alt], pred_alt, reason="empirical formula", reverse_reason="supports framework")

    abd = abduction(s_h, s_alt, observation=obs, reason="same experiment")

    assert abd.type == "abduction"
    assert len(abd.sub_strategies) == 3  # 2 supports + 1 compare
    assert abd.composition_warrant is not None
    assert abd.composition_warrant.type == "claim"
    # Conclusion is comparison claim from internal compare
    assert abd.conclusion is not None
    assert "comparison" in abd.conclusion.metadata.get("helper_kind", "")

def test_abduction_first_arg_is_claimed_better():
    """First support argument is the claimed-better theory."""
    # ... verify ordering in comparison claim content
```

- [ ] **Step 2: Run test, expect FAIL**

- [ ] **Step 3: Rewrite abduction()**

```python
def abduction(
    support_h: Strategy,
    support_alt: Strategy,
    observation: Knowledge,
    *,
    background: list[Knowledge] | None = None,
    reason: ReasonInput = "",
) -> Strategy:
    """Binary hypothesis comparison (IBE). First arg is claimed-better theory.

    Internally creates compare(support_h.conclusion, support_alt.conclusion, observation).
    Outputs auto-generated comparison claim (pi=0.5).
    """
    if not isinstance(support_h, Strategy) or support_h.type != "support":
        raise TypeError("abduction() first arg must be a support Strategy")
    if not isinstance(support_alt, Strategy) or support_alt.type != "support":
        raise TypeError("abduction() second arg must be a support Strategy")

    # Internal compare
    comp = compare(support_h.conclusion, support_alt.conclusion, observation)

    # Composition warrant
    comp_warrant = Knowledge(
        content=f"compatibility({support_h.conclusion.label or 'H'}, {support_alt.conclusion.label or 'Alt'}, {observation.label or 'Obs'})",
        type="claim",
        metadata={"helper_kind": "composition_validity", "generated": True},
    )
    if isinstance(reason, str) and reason:
        comp_warrant.metadata["warrant"] = reason

    # Gather all premises from sub-strategies
    all_premises = list(support_h.premises) + list(support_alt.premises) + [observation]
    seen = set()
    unique_premises = []
    for p in all_premises:
        if id(p) not in seen:
            unique_premises.append(p)
            seen.add(id(p))

    strategy = Strategy(
        type="abduction",
        premises=unique_premises,
        conclusion=comp.conclusion,  # comparison claim
        background=background or [],
        reason=reason,
        sub_strategies=[support_h, support_alt, comp],
        composition_warrant=comp_warrant,
        metadata={},
    )
    _attach_strategy(comp.conclusion, strategy)
    return strategy
```

- [ ] **Step 4: Run test**

Run: `pytest tests/gaia/lang/test_abduction_v2.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add gaia/lang/dsl/strategies.py tests/gaia/lang/test_abduction_v2.py
git commit -m "feat(dsl): rewrite abduction as binary CompositeStrategy of 2 supports + 1 compare"
```

### Task 11: Refactor induction() as Binary CompositeStrategy

**Files:**
- Modify: `gaia/lang/dsl/strategies.py` (rewrite induction)
- Create: `tests/gaia/lang/test_induction_v2.py`

- [ ] **Step 1: Write failing test**

```python
# tests/gaia/lang/test_induction_v2.py
from gaia.lang import claim, support, induction

def test_induction_binary_composite():
    """induction takes 2 supports + law, returns CompositeStrategy with law as conclusion."""
    H = claim("Mendel's law")
    obs1 = claim("Seed shape 2.96:1")
    obs2 = claim("Seed color 3.01:1")

    s1 = support([H], obs1, reason="H predicts 3:1", reverse_reason="2.96 matches")
    s2 = support([H], obs2, reason="H predicts 3:1", reverse_reason="3.01 matches")

    ind = induction(s1, s2, law=H, reason="seed shape and color are independent traits")

    assert ind.type == "induction"
    assert ind.conclusion is H
    assert len(ind.sub_strategies) == 2
    assert ind.composition_warrant is not None

def test_induction_chaining():
    """induction can chain: induction(prev_induction, new_support, law)."""
    H = claim("Law")
    obs1, obs2, obs3 = claim("Obs1"), claim("Obs2"), claim("Obs3")
    s1 = support([H], obs1, reason="...", reverse_reason="...")
    s2 = support([H], obs2, reason="...", reverse_reason="...")
    s3 = support([H], obs3, reason="...", reverse_reason="...")

    ind_12 = induction(s1, s2, law=H, reason="independent")
    ind_123 = induction(ind_12, s3, law=H, reason="obs3 independent of 1,2")

    assert ind_123.conclusion is H
    assert len(ind_123.sub_strategies) == 2  # prev_induction + s3
```

- [ ] **Step 2: Run test, expect FAIL**

- [ ] **Step 3: Rewrite induction()**

```python
def induction(
    support_1: Strategy,
    support_2: Strategy,
    law: Knowledge,
    *,
    background: list[Knowledge] | None = None,
    reason: ReasonInput = "",
) -> Strategy:
    """Binary evidence accumulation. Outputs law itself.

    support_1: support(law, obs1) or previous induction result.
    support_2: support(law, obs2).
    """
    if not isinstance(support_1, Strategy):
        raise TypeError("induction() first arg must be a Strategy")
    if not isinstance(support_2, Strategy):
        raise TypeError("induction() second arg must be a Strategy")

    # Composition warrant
    comp_warrant = Knowledge(
        content=f"independence({support_1.conclusion.label or 'S1'}, {support_2.conclusion.label or 'S2'})",
        type="claim",
        metadata={"helper_kind": "composition_validity", "generated": True},
    )
    if isinstance(reason, str) and reason:
        comp_warrant.metadata["warrant"] = reason

    all_premises = list(support_1.premises) + list(support_2.premises)
    seen = set()
    unique_premises = []
    for p in all_premises:
        if id(p) not in seen:
            unique_premises.append(p)
            seen.add(id(p))

    strategy = Strategy(
        type="induction",
        premises=unique_premises,
        conclusion=law,
        background=background or [],
        reason=reason,
        sub_strategies=[support_1, support_2],
        composition_warrant=comp_warrant,
        metadata={},
    )
    _attach_strategy(law, strategy)
    return strategy
```

- [ ] **Step 4: Run test**

Run: `pytest tests/gaia/lang/test_induction_v2.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add gaia/lang/dsl/strategies.py tests/gaia/lang/test_induction_v2.py
git commit -m "feat(dsl): rewrite induction as binary CompositeStrategy"
```

### Task 12: Deprecate noisy_and

**Files:**
- Modify: `gaia/lang/dsl/strategies.py`
- Test: `tests/gaia/lang/test_strategies.py`

- [ ] **Step 1: Add deprecation warning to noisy_and()**

```python
import warnings

def noisy_and(
    premises: list[Knowledge],
    conclusion: Knowledge,
    *,
    background: list[Knowledge] | None = None,
    reason: ReasonInput = "",
) -> Strategy:
    """DEPRECATED: Use support() instead."""
    warnings.warn(
        "noisy_and() is deprecated. Use support() with reverse_reason='' instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    return support(
        premises=premises,
        conclusion=conclusion,
        background=background,
        reason=reason,
        reverse_reason="",  # silent reverse
    )
```

- [ ] **Step 2: Test deprecation**

```python
def test_noisy_and_deprecated():
    with pytest.warns(DeprecationWarning, match="noisy_and.*deprecated"):
        noisy_and([claim("A")], claim("B"))
```

- [ ] **Step 3: Run tests**

Run: `pytest tests/gaia/lang/ -v`
Expected: PASS (existing noisy_and tests should still work with deprecation warning)

- [ ] **Step 4: Commit**

```bash
git add gaia/lang/dsl/strategies.py tests/gaia/lang/
git commit -m "deprecate(dsl): noisy_and → support with reverse_reason=''"
```

---

## Chunk 4: Integration and Regression (Phase 3-4)

### Task 13: End-to-End Compilation Test

**Files:**
- Create: `tests/integration/test_warrant_e2e.py`

- [ ] **Step 1: Write end-to-end test: Mendel example compiles**

```python
def test_mendel_peirce_cycle_compiles():
    """Full Peirce cycle: deduction → support → abduction → induction."""
    from gaia.lang import claim, setting, deduction, support, compare, abduction, induction

    H = claim("Discrete heritable factors")
    alt = claim("Blending inheritance")
    obs_3to1 = claim("F2 ratio 2.96:1")
    pred_h = claim("H predicts 3:1")
    pred_alt = claim("Alt predicts continuous")

    # Deduction
    deduction([H], pred_h, reason="Punnett square derivation")

    # Supports
    s_h = support([H], pred_h, reason="H implies 3:1", reverse_reason="3:1 characteristic of H")
    s_alt = support([alt], pred_alt, reason="blending implies continuous", reverse_reason="continuous indicates blending")

    # Abduction
    abd = abduction(s_h, s_alt, observation=obs_3to1, reason="both predict F2 pattern")
    assert abd.conclusion is not None

    # Induction (multiple traits)
    obs_color = claim("Seed color 3.01:1")
    s_shape = support([H], obs_3to1, reason="H predicts", reverse_reason="matches")
    s_color = support([H], obs_color, reason="H predicts", reverse_reason="matches")
    ind = induction(s_shape, s_color, law=H, reason="traits independent")
    assert ind.conclusion is H
```

- [ ] **Step 2: Run**

Run: `pytest tests/integration/test_warrant_e2e.py -v`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add tests/integration/test_warrant_e2e.py
git commit -m "test: Mendel end-to-end Peirce cycle — deduction + support + abduction + induction"
```

### Task 14: BP Regression — Support Equivalence to SOFT_ENTAILMENT

**Files:**
- Create: `tests/gaia/bp/test_support_bp.py`

- [ ] **Step 1: Write BP equivalence test**

Verify that support (two IMPLIES) produces the same BP message ratios as SOFT_ENTAILMENT:

```python
def test_support_bp_ratios_match_soft_entailment():
    """Two independent IMPLIES produce same BP ratios as SOFT_ENTAILMENT (Appendix A)."""
    # Build factor graph with two IMPLIES
    # Run BP
    # Check that belief ratios match SOFT_ENTAILMENT formula:
    #   psi(1,1)/psi(1,0) = p1/(1-p1)
    #   psi(0,0)/psi(0,1) = p2/(1-p2)
```

- [ ] **Step 2: Implement and run**

Run: `pytest tests/gaia/bp/test_support_bp.py -v`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add tests/gaia/bp/test_support_bp.py
git commit -m "test(bp): verify support BP ratios match SOFT_ENTAILMENT (Appendix A proof)"
```

### Task 15: Full Test Suite Regression

- [ ] **Step 1: Run full test suite**

Run: `pytest --tb=short -q`
Expected: All existing tests pass (some may need updates from implication arity change)

- [ ] **Step 2: Fix any remaining failures**

- [ ] **Step 3: Run linting**

Run: `ruff check . && ruff format --check .`
Expected: Clean

- [ ] **Step 4: Final commit**

```bash
git commit -m "fix: resolve remaining test failures from implication arity change"
```

---

## PR Strategy

| PR | Tasks | Branch |
|----|-------|--------|
| **PR A** | Tasks 1-5 (implication change + warrant metadata) | `feat/implication-relation` |
| **PR B** | Tasks 6-8 (support + compare primitives) | `feat/support-compare` |
| **PR C** | Tasks 9-12 (abduction + induction + deprecate noisy_and) | `feat/composite-strategies` |
| **PR D** | Tasks 13-15 (integration + regression) | `test/warrant-e2e` |

Each PR depends on the previous. PR A is the riskiest (changes fundamental operator semantics); PRs B-D are incremental.
