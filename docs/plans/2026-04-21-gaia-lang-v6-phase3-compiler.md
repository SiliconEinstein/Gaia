# Gaia Lang v6 Implementation Plan — Phase 3: Compiler Updates

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Update the compiler to lower v6 Action objects to IR Strategy/Operator, including `action_label` in metadata, `rationale` → `steps`, helper claim warrant metadata (`review` flag), and `infer()` → `Strategy(type="infer")` + CPT.

**Architecture:** The compiler walks `CollectedPackage.actions` (new) alongside existing `strategies` and `operators`. Each Action subclass has a lowering path: Support actions → `FormalStrategy(type="deduction")`, Relate actions → `Operator`, Infer actions → `Strategy(type="infer")` + `StrategyParamRecord`. The `action_label` is stored in `metadata.action_label` and mapped bidirectionally to the compiled target ID (`strategy_id` for Strategies, `operator_id` for Operators).

**Tech Stack:** Python 3.12+, Pydantic v2, pytest

**Spec:** `docs/specs/2026-04-21-gaia-lang-v6-design.md` §4.4, §13; `docs/specs/2026-04-21-gaia-ir-v6-design.md` §2, §4

**Depends on:** Phase 1 + Phase 2

---

## File Structure

### Modified files

| File | Changes |
|---|---|
| `gaia/lang/compiler/compile.py` | New `_compile_action()` dispatcher, handle Action subclasses, `action_label` in metadata, `rationale` → `steps`, warrant metadata, infer CPT construction |
| `gaia/lang/runtime/package.py` | Ensure actions are accessible to compiler |
| `gaia/ir/parameterization.py` | No schema change, but compiler creates StrategyParamRecord for infer |

### New files

| File | Responsibility |
|---|---|
| `tests/gaia/lang/test_compiler_actions.py` | Compiler tests for Action → IR lowering |
| `tests/cli/test_compile_v6_actions.py` | End-to-end compile tests with derive/observe/equal/contradict/infer |

---

## Chunk 1: Support Action Lowering

### Task 1: Compile Derive → FormalStrategy(type="deduction")

- [ ] **Step 1: Write failing test**

Test that a package using `derive()` compiles to `FormalStrategy(type="deduction")` with:
- `metadata.action_label` set
- `metadata.pattern` = "derivation" (default)
- `steps=[Step(reasoning=rationale)]`
- Conjunction + Implication helper claims generated
- Helper claims have `metadata.review = True` for implication, `False` for conjunction

- [ ] **Step 2: Implement `_compile_action()` in compile.py**

Add a dispatcher that routes Action subclasses to the appropriate lowering:

```python
def _compile_action(action: Action, knowledge_map, namespace, package_name):
    if isinstance(action, Derive):
        return _compile_derive(action, ...)
    elif isinstance(action, Observe):
        return _compile_observe(action, ...)
    elif isinstance(action, Compute):
        return _compile_compute(action, ...)
    elif isinstance(action, Equal):
        return _compile_equal(action, ...)
    elif isinstance(action, Contradict):
        return _compile_contradict(action, ...)
    elif isinstance(action, Infer):
        return _compile_infer(action, ...)
```

`_compile_derive()` calls existing `formalize_named_strategy()` with type="deduction", adds `metadata.action_label` and `metadata.pattern`.

- [ ] **Step 3: Run — verify passes**
- [ ] **Step 4: Commit**

### Task 2: Compile Observe → FormalStrategy with pattern="observation"

- [ ] Same pattern as derive, but `metadata.pattern = "observation"`.
- [ ] No-premise observe: verify a reviewable `FormalStrategy(type="deduction", premises=[], metadata.pattern="observation")` is generated and the Claim also carries `Grounding(kind="source_fact")`.
- [ ] Verify BP lowering treats no-premise observe as a reviewed source grounding, not as a support edge from an empty premise set.
- [ ] Commit

### Task 3: Compile Compute → FormalStrategy with metadata.compute

- [ ] Same pattern as derive, but `metadata.pattern = "computation"` and `metadata.compute = {function_ref, code_hash, ...}`.
- [ ] Verify compute never introduces a new `StrategyType.COMPUTATION`; it lowers to deduction with computation metadata.
- [ ] Commit

---

## Chunk 2: Relate + Infer Lowering

### Task 4: Compile Equal → Operator(type="equivalence")

- [ ] **Step 1: Write failing test**

Verify `equal(A, B)` compiles to `Operator(type="equivalence")` with conclusion = helper Claim.

- [ ] **Step 2: Implement** — route to existing `_operator_to_ir()` with type="equivalence"
- [ ] **Step 3: Commit**

### Task 5: Compile Contradict → Operator(type="contradiction")

- [ ] Same as Task 4 with type="contradiction"
- [ ] Commit

### Task 6: Compile Infer → Strategy(type="infer") + CPT

- [ ] **Step 1: Write failing test**

Verify `infer(hypothesis=H, evidence=E, p_e_given_h=0.9, p_e_given_not_h=0.1)` compiles to:
- `Strategy(type="infer", premises=[H_id], conclusion=E_id, background=[...])`
- `StrategyParamRecord(conditional_probabilities=[0.1, 0.9])`
- `metadata.action_label` set
- StatisticalSupport helper Claim generated

- [ ] **Step 2: Implement `_compile_infer()`**

```python
def _compile_infer(action: Infer, knowledge_map, namespace, package_name):
    h_id = knowledge_map[id(action.hypothesis)]
    e_id = knowledge_map[id(action.evidence)]
    bg_ids = [knowledge_map[id(b)] for b in action.background if id(b) in knowledge_map]

    strategy = IrStrategy(
        scope="local",
        type="infer",
        premises=[h_id],
        conclusion=e_id,
        background=bg_ids or None,
        steps=[IrStep(reasoning=action.rationale)] if action.rationale else None,
        metadata={"action_label": action.label, "pattern": "inference"},
    )

    param_record = StrategyParamRecord(
        strategy_id=strategy.strategy_id,
        conditional_probabilities=[action.p_e_given_not_h, action.p_e_given_h],
        source_id="author",
        justification=action.rationale,
    )

    return strategy, param_record, [action.helper]  # helper claim to register
```

- [ ] **Step 3: Run — verify passes**
- [ ] **Step 4: Commit**

---

## Chunk 3: action_label ↔ target_id Mapping

### Task 7: Bidirectional label mapping

- [ ] **Step 1: Write test**

Verify that compiled IR has `metadata.action_label` on strategies/operators and that the `CompiledPackage` exposes a mapping `action_label → target_id`.

- [ ] **Step 2: Add `action_label_map` to CompiledPackage**
- [ ] **Step 3: Commit**

---

## Chunk 4: End-to-End Integration

### Task 8: Full v6 package with all verbs compiles + infers

- [ ] **Step 1: Write end-to-end test**

Package with derive, observe, equal, contradict, infer. Compile → infer → verify beliefs make sense.

- [ ] **Step 2: Run — verify passes**
- [ ] **Step 3: Commit**

---

## Verification

1. `pytest tests/gaia/lang/test_compiler_actions.py -v`
2. `pytest tests/cli/test_compile_v6_actions.py -v`
3. `pytest tests/ -x -q` (full regression)
4. `ruff check . && ruff format --check .`
