# Induction Strategy Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `induction()` to the Gaia Lang DSL as a CompositeStrategy wrapping shared-conclusion abduction sub-strategies, and update all related docs/skills/tests.

**Architecture:** `induction()` is a single DSL function with two modes (top-down: Knowledge list; bottom-up: Strategy list). It reuses existing `abduction()` and `_composite_strategy()` internals. IR changes are minimal: add enum value, remove error guard. Protected layer (Gaia IR doc) updated in a separate logical chunk.

**Tech Stack:** Python 3.12+, Pydantic v2, pytest

---

## File Structure

| File | Responsibility | Action |
|------|---------------|--------|
| `gaia/ir/strategy.py` | StrategyType enum | Modify: add `INDUCTION` |
| `gaia/ir/formalize.py` | Strategy formalization | Modify: remove induction error |
| `gaia/lang/dsl/strategies.py` | DSL strategy functions | Modify: add `induction()` |
| `gaia/lang/dsl/__init__.py` | DSL re-exports | Modify: add `induction` |
| `gaia/lang/__init__.py` | Top-level re-exports | Modify: add `induction` |
| `tests/gaia/lang/test_strategies.py` | DSL strategy tests | Modify: add induction tests |
| `tests/gaia/lang/test_compiler.py` | Compiler integration tests | Modify: add induction compilation test |
| `.claude/skills/gaia-ir-authoring/SKILL.md` | Authoring skill | Modify: add induction usage |
| `.claude/skills/paper-formalization/SKILL.md` | Formalization skill | Modify: update induction row |
| `docs/foundations/gaia-ir/02-gaia-ir.md` | IR spec (protected) | Modify: promote induction from deferred |

---

## Chunk 1: IR layer + DSL implementation + tests

### Task 1: Add INDUCTION to StrategyType enum

**Files:**
- Modify: `gaia/ir/strategy.py:26-43`

- [ ] **Step 1: Write the failing test**

```python
# tests/gaia/lang/test_strategies.py — add at top of file after existing imports
# (We test via the DSL, but first confirm the enum value exists)
```

No separate test needed — the enum is tested implicitly by subsequent tasks. Proceed directly.

- [ ] **Step 2: Add INDUCTION to StrategyType**

In `gaia/ir/strategy.py`, add after `EXTRAPOLATION = "extrapolation"` (line 42):

```python
    # Composite strategies — non-atomic
    INDUCTION = "induction"  # CompositeStrategy wrapping shared-conclusion abductions
```

- [ ] **Step 3: Run existing tests to verify nothing breaks**

Run: `pytest tests/gaia -x -q`
Expected: All existing tests PASS (INDUCTION is just a new enum value, nothing references it yet)

- [ ] **Step 4: Commit**

```bash
git add gaia/ir/strategy.py
git commit -m "feat(ir): add INDUCTION to StrategyType enum"
```

---

### Task 2: Remove induction error guard from formalize.py

**Files:**
- Modify: `gaia/ir/formalize.py:474-478`

- [ ] **Step 1: Remove the induction ValueError**

Delete these lines from `gaia/ir/formalize.py`:

```python
    if type_ == "induction":
        raise ValueError(
            "induction is deferred in Gaia IR core; express it as repeated abduction "
            "with a shared conclusion instead"
        )
```

- [ ] **Step 2: Run existing tests**

Run: `pytest tests/gaia -x -q`
Expected: All PASS. The guard was only hit if someone tried to formalize `type=induction` directly, which no existing code does.

- [ ] **Step 3: Commit**

```bash
git add gaia/ir/formalize.py
git commit -m "feat(ir): remove induction deferral guard from formalize"
```

---

### Task 3: Implement induction() DSL function

**Files:**
- Modify: `gaia/lang/dsl/strategies.py`
- Test: `tests/gaia/lang/test_strategies.py`

- [ ] **Step 1: Add induction to DSL exports first (so tests can import it)**

In `gaia/lang/dsl/__init__.py`, add `induction` to the import from `strategies` and to `__all__` (alphabetical order):

```python
from gaia.lang.dsl.strategies import (
    abduction,
    analogy,
    case_analysis,
    composite,
    deduction,
    elimination,
    extrapolation,
    induction,        # ADD
    infer,
    mathematical_induction,
    noisy_and,
)
```

And add `"induction"` to `__all__` between `"extrapolation"` and `"infer"`.

In `gaia/lang/__init__.py`, add `induction` to both the import and `__all__` (alphabetical, between `extrapolation` and `infer`).

- [ ] **Step 2: Write failing tests for top-down mode**

Add to `tests/gaia/lang/test_strategies.py` (merge `induction` into the existing import block at top):

```python
from gaia.lang import induction


def test_induction_top_down_basic():
    """Top-down: pass Knowledge list, auto-generate AltExps."""
    law = claim("All metals expand when heated.")
    obs1 = claim("Iron expands when heated.")
    obs2 = claim("Copper expands when heated.")
    obs3 = claim("Silver expands when heated.")

    s = induction([obs1, obs2, obs3], law)
    assert s.type == "induction"
    assert s.conclusion is law
    assert len(s.sub_strategies) == 3
    # Each sub-strategy is an abduction with conclusion = law
    for sub in s.sub_strategies:
        assert sub.type == "abduction"
        assert sub.conclusion is law
    # law.strategy points to the CompositeStrategy, not a sub-abduction
    assert law.strategy is s


def test_induction_top_down_with_alt_exps():
    """Top-down: explicit AltExps provided."""
    law = claim("Drug X cures disease Y.")
    obs1 = claim("Patient 1 recovered.")
    obs2 = claim("Patient 2 recovered.")
    alt1 = claim("Patient 1 recovered spontaneously.")
    alt2 = claim("Patient 2 recovered spontaneously.")

    s = induction([obs1, obs2], law, alt_exps=[alt1, alt2])
    assert s.type == "induction"
    assert len(s.sub_strategies) == 2
    assert alt1 in s.sub_strategies[0].premises
    assert alt2 in s.sub_strategies[1].premises


def test_induction_top_down_mixed_alt_exps():
    """Top-down: some AltExps explicit, some None (auto-generated)."""
    law = claim("Law.")
    obs1 = claim("Obs 1.")
    obs2 = claim("Obs 2.")
    alt1 = claim("Alt 1.")

    s = induction([obs1, obs2], law, alt_exps=[alt1, None])
    assert alt1 in s.sub_strategies[0].premises
    assert len(s.sub_strategies[1].premises) == 1  # only obs, no explicit alt
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/gaia/lang/test_strategies.py::test_induction_top_down_basic -v`
Expected: FAIL with `ImportError: cannot import name 'induction'` (function not yet implemented)

- [ ] **Step 4: Implement induction() function**

Add to `gaia/lang/dsl/strategies.py` after the `composite()` function:

```python
def induction(
    items: list[Knowledge] | list[Strategy],
    law: Knowledge | None = None,
    *,
    alt_exps: list[Knowledge | None] | None = None,
    background: list[Knowledge] | None = None,
    reason: ReasonInput = "",
) -> Strategy:
    """Induction: multiple observations jointly supporting a law.

    Two modes, detected from the type of items[0]:

    Top-down (items = list[Knowledge]):
        Creates n abduction sub-strategies internally.
        law is required. alt_exps is optional (auto-generated if omitted).

    Bottom-up (items = list[Strategy]):
        Bundles existing abduction strategies.
        law is inferred from shared conclusion (validated if provided).
        alt_exps is ignored.
    """
    if not items:
        raise ValueError("induction() requires a non-empty list")

    # Detect mode from first element
    if isinstance(items[0], Strategy):
        return _induction_bottom_up(items, law, reason=reason)
    elif isinstance(items[0], Knowledge):
        if law is None:
            raise ValueError("induction() top-down mode requires law argument")
        return _induction_top_down(
            items, law, alt_exps=alt_exps, background=background, reason=reason
        )
    else:
        raise TypeError(
            f"induction() items must be Knowledge or Strategy, got {type(items[0])!r}"
        )


def _induction_top_down(
    observations: list,
    law: Knowledge,
    *,
    alt_exps: list[Knowledge | None] | None = None,
    background: list[Knowledge] | None = None,
    reason: ReasonInput = "",
) -> Strategy:
    if len(observations) < 2:
        raise ValueError("induction() requires at least 2 observations")
    if alt_exps is not None and len(alt_exps) != len(observations):
        raise ValueError(
            f"alt_exps length ({len(alt_exps)}) must match observations ({len(observations)})"
        )

    sub_strategies: list[Strategy] = []
    all_premises: list[Knowledge] = list(observations)

    for i, obs in enumerate(observations):
        alt = alt_exps[i] if alt_exps is not None else None
        premises = [obs]
        if alt is not None:
            premises.append(alt)
            all_premises.append(alt)
        sub = Strategy(
            type="abduction",
            premises=premises,
            conclusion=law,
            background=background or [],
            reason=reason,
        )
        sub_strategies.append(sub)

    return _composite_strategy(
        type_="induction",
        premises=all_premises,
        conclusion=law,
        sub_strategies=sub_strategies,
        background=background,
        reason=reason,
    )


def _induction_bottom_up(
    strategies: list,
    law: Knowledge | None = None,
    *,
    reason: ReasonInput = "",
) -> Strategy:
    if len(strategies) < 2:
        raise ValueError("induction() requires at least 2 sub-strategies")
    # Validate all are abduction with same conclusion
    conclusions: set[int] = set()
    for s in strategies:
        if not isinstance(s, Strategy):
            raise TypeError(f"induction() bottom-up items must be Strategy, got {type(s)!r}")
        if s.type != "abduction":
            raise ValueError(
                f"induction() bottom-up sub-strategies must be abduction, got '{s.type}'"
            )
        if s.conclusion is None:
            raise ValueError("induction() sub-strategy has no conclusion")
        conclusions.add(id(s.conclusion))

    if len(conclusions) != 1:
        raise ValueError(
            "induction() all sub-strategies must share the same conclusion (by identity)"
        )

    inferred_law = strategies[0].conclusion
    if law is not None and law is not inferred_law:
        raise ValueError("induction() law does not match sub-strategies' shared conclusion")

    # Collect all premises from sub-strategies
    all_premises: list[Knowledge] = []
    seen: set[int] = set()
    for s in strategies:
        for p in s.premises:
            if id(p) not in seen:
                all_premises.append(p)
                seen.add(id(p))

    return _composite_strategy(
        type_="induction",
        premises=all_premises,
        conclusion=inferred_law,
        sub_strategies=strategies,
        reason=reason,
    )
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/gaia/lang/test_strategies.py::test_induction_top_down_basic tests/gaia/lang/test_strategies.py::test_induction_top_down_with_alt_exps tests/gaia/lang/test_strategies.py::test_induction_top_down_mixed_alt_exps -v`
Expected: All 3 PASS

- [ ] **Step 6: Commit**

```bash
git add gaia/lang/dsl/strategies.py gaia/lang/dsl/__init__.py gaia/lang/__init__.py tests/gaia/lang/test_strategies.py
git commit -m "feat(lang): add induction() DSL function with top-down mode"
```

---

### Task 4: Add bottom-up mode tests and validation tests

**Files:**
- Test: `tests/gaia/lang/test_strategies.py`

- [ ] **Step 1: Write bottom-up and validation tests**

Add to `tests/gaia/lang/test_strategies.py`:

```python
def test_induction_bottom_up():
    """Bottom-up: bundle existing abductions."""
    law = claim("Law.")
    obs1 = claim("Obs 1.")
    obs2 = claim("Obs 2.")
    alt1 = claim("Alt 1.")
    alt2 = claim("Alt 2.")

    abd1 = abduction(obs1, law, alt1)
    abd2 = abduction(obs2, law, alt2)
    # At this point, law.strategy points to abd2 (last one wins)
    assert law.strategy is abd2

    s = induction([abd1, abd2])
    assert s.type == "induction"
    assert s.conclusion is law
    assert len(s.sub_strategies) == 2
    assert s.sub_strategies[0] is abd1
    assert s.sub_strategies[1] is abd2
    # After induction(), law.strategy is overwritten to CompositeStrategy
    assert law.strategy is s


def test_induction_bottom_up_with_law():
    """Bottom-up: law explicitly provided, validated for consistency."""
    law = claim("Law.")
    obs1 = claim("Obs 1.")
    obs2 = claim("Obs 2.")

    abd1 = abduction(obs1, law)
    abd2 = abduction(obs2, law)

    s = induction([abd1, abd2], law)
    assert s.conclusion is law


def test_induction_too_few_observations():
    """Top-down with fewer than 2 observations."""
    law = claim("Law.")
    obs = claim("Single obs.")
    with pytest.raises(ValueError, match="at least 2"):
        induction([obs], law)


def test_induction_alt_exps_length_mismatch():
    """alt_exps length doesn't match observations."""
    law = claim("Law.")
    obs1 = claim("Obs 1.")
    obs2 = claim("Obs 2.")
    alt1 = claim("Alt 1.")
    with pytest.raises(ValueError, match="alt_exps length"):
        induction([obs1, obs2], law, alt_exps=[alt1])


def test_induction_bottom_up_different_conclusions():
    """Bottom-up: sub-strategies with different conclusions."""
    law1 = claim("Law 1.")
    law2 = claim("Law 2.")
    obs1 = claim("Obs 1.")
    obs2 = claim("Obs 2.")
    abd1 = abduction(obs1, law1)
    abd2 = abduction(obs2, law2)
    with pytest.raises(ValueError, match="same conclusion"):
        induction([abd1, abd2])


def test_induction_bottom_up_non_abduction():
    """Bottom-up: sub-strategy is not abduction."""
    law = claim("Law.")
    a = claim("A.")
    b = claim("B.")
    s1 = noisy_and(premises=[a], conclusion=law)
    s2 = noisy_and(premises=[b], conclusion=law)
    with pytest.raises(ValueError, match="must be abduction"):
        induction([s1, s2])


def test_induction_bottom_up_law_mismatch():
    """Bottom-up: explicit law doesn't match sub-strategies."""
    law = claim("Law.")
    other_law = claim("Other law.")
    obs1 = claim("Obs 1.")
    obs2 = claim("Obs 2.")
    abd1 = abduction(obs1, law)
    abd2 = abduction(obs2, law)
    with pytest.raises(ValueError, match="does not match"):
        induction([abd1, abd2], other_law)


def test_induction_empty_list():
    """Empty items list."""
    with pytest.raises(ValueError, match="non-empty"):
        induction([])


def test_induction_top_down_no_law():
    """Top-down mode without law raises ValueError."""
    obs1 = claim("Obs 1.")
    obs2 = claim("Obs 2.")
    with pytest.raises(ValueError, match="requires law"):
        induction([obs1, obs2])


def test_induction_bottom_up_single():
    """Bottom-up with fewer than 2 strategies."""
    law = claim("Law.")
    obs = claim("Obs.")
    abd = abduction(obs, law)
    with pytest.raises(ValueError, match="at least 2"):
        induction([abd])
```

- [ ] **Step 2: Run all new tests**

Run: `pytest tests/gaia/lang/test_strategies.py -k induction -v`
Expected: All induction tests PASS

- [ ] **Step 3: Commit**

```bash
git add tests/gaia/lang/test_strategies.py
git commit -m "test(lang): add bottom-up and validation tests for induction()"
```

---

### Task 5: Add compiler integration test

**Files:**
- Test: `tests/gaia/lang/test_compiler.py`

- [ ] **Step 1: Write compiler test for induction**

Add `induction` to the existing import line in `tests/gaia/lang/test_compiler.py`:

```python
from gaia.lang import Step, claim, infer, noisy_and, setting, composite, abduction, contradiction, induction
```

Then add the test function:

```python
def test_compile_induction():
    """Induction compiles to CompositeStrategy + FormalStrategy sub-abductions."""
    pkg = CollectedPackage("test_induction", namespace="github", version="1.0.0")
    with pkg:
        law = claim("All metals expand when heated.")
        law.label = "law"
        obs1 = claim("Iron expands when heated.")
        obs1.label = "obs1"
        obs2 = claim("Copper expands when heated.")
        obs2.label = "obs2"
        alt1 = claim("Iron expansion has local cause.")
        alt1.label = "alt1"

        induction([obs1, obs2], law, alt_exps=[alt1, None])

    result = compile_package_artifact(pkg)

    # Find the CompositeStrategy (type=induction)
    composites = [s for s in result.graph.strategies if hasattr(s, "sub_strategies") and s.sub_strategies]
    assert len(composites) == 1
    comp = composites[0]
    assert comp.type == "induction"

    # It should reference 2 sub-strategies
    assert len(comp.sub_strategies) == 2

    # Sub-strategies should be FormalStrategy(type=abduction)
    strategy_by_id = {s.strategy_id: s for s in result.graph.strategies}
    for sub_id in comp.sub_strategies:
        sub = strategy_by_id[sub_id]
        assert sub.type == "abduction"
        assert hasattr(sub, "formal_expr")  # formalized at compile time
```

- [ ] **Step 2: Run the test**

Run: `pytest tests/gaia/lang/test_compiler.py::test_compile_induction -v`
Expected: PASS

- [ ] **Step 3: Run full test suite**

Run: `pytest tests/gaia -x -q`
Expected: All PASS

- [ ] **Step 4: Commit**

```bash
git add tests/gaia/lang/test_compiler.py
git commit -m "test(compiler): add induction compilation integration test"
```

---

## Chunk 2: Skills + Protected layer doc update

### Task 6: Update gaia-ir-authoring skill

**Files:**
- Modify: `.claude/skills/gaia-ir-authoring/SKILL.md:120-162`

- [ ] **Step 1: Add induction to Step 4 strategy examples**

In `.claude/skills/gaia-ir-authoring/SKILL.md`, after the `mathematical_induction` example in Step 4 (around line 159), add:

```python
# Induction: multiple observations → law (CompositeStrategy wrapping abductions)
# Top-down: pass observations, auto-generates abduction sub-strategies
induction([obs_1, obs_2, obs_3], law_claim)
# With explicit alternative explanations:
induction([obs_1, obs_2], law_claim, alt_exps=[alt_1, alt_2])
# Bottom-up: bundle existing abductions
abd1 = abduction(obs_1, law_claim, alt_1)
abd2 = abduction(obs_2, law_claim, alt_2)
induction([abd1, abd2])
```

Also add `induction` to the import line at the top of Step 4.

- [ ] **Step 2: Commit**

```bash
git add .claude/skills/gaia-ir-authoring/SKILL.md
git commit -m "docs(skill): add induction usage to gaia-ir-authoring"
```

---

### Task 7: Update paper-formalization skill

**Files:**
- Modify: `.claude/skills/paper-formalization/SKILL.md:307`

- [ ] **Step 1: Update the induction row in the strategy table**

Change line 307 from:

```
| 归纳（精确极限 + 数值→通则） | `infer`（暂） | 需要完整 CPT |
```

To:

```
| 归纳（多观测→通则） | `induction` | 由子 abduction 的 formal_expr 确定 |
```

- [ ] **Step 2: Commit**

```bash
git add .claude/skills/paper-formalization/SKILL.md
git commit -m "docs(skill): update induction entry in paper-formalization"
```

---

### Task 8: Update Gaia IR spec (protected layer)

**Files:**
- Modify: `docs/foundations/gaia-ir/02-gaia-ir.md:359` (§3.3 type table)
- Modify: `docs/foundations/gaia-ir/02-gaia-ir.md:573-586` (§3.5 induction defer section)

**⚠️ Protected layer — this change should be reviewed carefully.**

- [ ] **Step 1: Update §3.3 type table row**

Change line 359 from:

```
| **`induction`**（deferred） | — | — | theory 中保留；Gaia IR core 当前不设独立 primitive，可先展开成多条共享结论的 `abduction` |
```

To:

```
| **`induction`** | 无独立 strategy-level 参数 | CompositeStrategy | 包装 n 条共享同一 conclusion 的 `abduction` 子策略；归纳效应（观测累积→Law 置信度上升）由因子图拓扑涌现 |
```

- [ ] **Step 2: Replace §3.5 induction defer paragraph**

Replace lines 573-586 (the "归纳（induction）" deferred section) with:

```markdown
**归纳（induction）**：`CompositeStrategy(type=induction, sub_strategies=[abd₁, abd₂, ..., abdₙ], conclusion=Law)`

归纳 = n 条共享同一 `Law` 结论的 abduction 子策略的组合。每条子策略是独立的 `FormalStrategy(type=abduction)`，各自有自己的 `Obsᵢ` 和 `AltExpᵢ`（可自动生成 interface claim）。

```
CompositeStrategy(type=induction, conclusion=Law):
  sub_strategies:
    - FormalStrategy(type=abduction, premises=[Obs₁, AltExp₁], conclusion=Law)
    - FormalStrategy(type=abduction, premises=[Obs₂, AltExp₂], conclusion=Law)
    - ...
    - FormalStrategy(type=abduction, premises=[Obsₙ, AltExpₙ], conclusion=Law)
```

归纳效应由因子图拓扑的 emergent property 产生：n 条 abduction 共享 Law 节点，BP 自然算出累积后验 `P(Law=1 | all Obsᵢ=1) = π(Law) / [π(Law) + (1−π(Law))·∏ᵢ ρᵢ]`（假设各 AltExpᵢ 条件独立）。CompositeStrategy 不直接 formalize——子 abduction 各自独立走 `_build_abduction` 路径。

全局替代解释（GlobalAltExp）不属于归纳的原子定义——它是独立的建模选择，作者可通过其他已有机制（Operator、Strategy）在论证图中表达。
```

- [ ] **Step 3: Run tests to ensure nothing breaks**

Run: `pytest tests/gaia -x -q`
Expected: All PASS (doc changes don't affect code)

- [ ] **Step 4: Commit**

```bash
git add docs/foundations/gaia-ir/02-gaia-ir.md
git commit -m "docs(gaia-ir): promote induction from deferred to CompositeStrategy"
```

---

### Task 9: Final verification

- [ ] **Step 1: Run full test suite**

```bash
pytest tests/gaia -x -q
```

Expected: All PASS

- [ ] **Step 2: Lint and format**

```bash
ruff check gaia/ir/strategy.py gaia/ir/formalize.py gaia/lang/dsl/strategies.py gaia/lang/dsl/__init__.py gaia/lang/__init__.py tests/gaia/lang/test_strategies.py tests/gaia/lang/test_compiler.py
ruff format gaia/ir/strategy.py gaia/ir/formalize.py gaia/lang/dsl/strategies.py gaia/lang/dsl/__init__.py gaia/lang/__init__.py tests/gaia/lang/test_strategies.py tests/gaia/lang/test_compiler.py
```

- [ ] **Step 3: Fix any lint/format issues and commit**

```bash
git add -u
git commit -m "style: fix lint/format for induction implementation"
```

- [ ] **Step 4: Push and create PR**

```bash
git push -u origin feat/induction-strategy
gh pr create --title "feat: add induction strategy (CompositeStrategy)" --body "$(cat <<'EOF'
## Summary
- Add `induction()` to Gaia Lang DSL with top-down and bottom-up modes
- Add `INDUCTION` to `StrategyType` enum
- Remove induction deferral guard from `formalize.py`
- Update Gaia IR spec: promote induction from deferred to CompositeStrategy
- Update gaia-ir-authoring and paper-formalization skills

## Spec
`docs/specs/2026-04-05-induction-strategy-design.md`

## Test plan
- [ ] Top-down mode: basic, with alt_exps, mixed alt_exps
- [ ] Bottom-up mode: basic, with law validation
- [ ] Validation: too few obs, alt_exps mismatch, different conclusions, non-abduction, law mismatch, empty list
- [ ] Compiler integration: CompositeStrategy + FormalStrategy sub-abductions in IR output

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

- [ ] **Step 5: Verify CI passes**

```bash
gh run list --branch feat/induction-strategy --limit 1
# If failed:
gh run view <run-id> --log-failed
```
