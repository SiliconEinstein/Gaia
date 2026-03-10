# Relation Type Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add Relation (Contradiction, Equivalence) as the 8th root Knowledge type, RetractAction as Action subtype, with full BP integration and provenance tracking.

**Architecture:** Relation declarations compile to variable nodes (truth-apt) plus constraint factors in the factor graph. Two new factor potential functions (mutex for Contradiction, equiv for Equivalence) are added to BP. RetractAction is a provenance-only declaration (no direct BP effect). The Galileo example is refactored to use the new types.

**Tech Stack:** Python 3.12, Pydantic v2, NumPy (BP), PyYAML (loader)

**Design doc:** `docs/plans/2026-03-10-relation-type-design.md`

---

### Task 1: Add Relation, Contradiction, Equivalence Models

**Files:**
- Modify: `libs/lang/models.py:56-127`
- Create: `tests/libs/lang/test_relation_models.py`

**Step 1: Write the failing test**

```python
# tests/libs/lang/test_relation_models.py
from libs.lang.models import (
    Contradiction,
    Declaration,
    DECLARATION_TYPE_MAP,
    Equivalence,
    Relation,
)


def test_contradiction_model():
    c = Contradiction(
        name="test_contra",
        between=["claim_a", "claim_b"],
        prior=0.95,
    )
    assert c.type == "contradiction"
    assert c.between == ["claim_a", "claim_b"]
    assert c.prior == 0.95
    assert c.belief is None


def test_equivalence_model():
    e = Equivalence(
        name="test_equiv",
        between=["claim_x", "claim_y"],
        prior=0.90,
    )
    assert e.type == "equivalence"
    assert e.between == ["claim_x", "claim_y"]
    assert e.prior == 0.90
    assert e.belief is None


def test_relation_is_declaration():
    c = Contradiction(name="c", between=["a", "b"], prior=0.9)
    assert isinstance(c, Declaration)
    assert isinstance(c, Relation)


def test_relation_types_in_declaration_map():
    assert "contradiction" in DECLARATION_TYPE_MAP
    assert "equivalence" in DECLARATION_TYPE_MAP
    assert DECLARATION_TYPE_MAP["contradiction"] is Contradiction
    assert DECLARATION_TYPE_MAP["equivalence"] is Equivalence
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/libs/lang/test_relation_models.py -v`
Expected: FAIL with ImportError (Relation/Contradiction/Equivalence not defined)

**Step 3: Write minimal implementation**

Add to `libs/lang/models.py` after the `Setting` class (around line 80):

```python
class Relation(Declaration):
    """Base for logical relations between knowledge objects."""

    between: list[str] = Field(default_factory=list)
    belief: float | None = None


class Contradiction(Relation):
    type: str = "contradiction"


class Equivalence(Relation):
    type: str = "equivalence"
```

Update `DECLARATION_TYPE_MAP` to include:
```python
"contradiction": Contradiction,
"equivalence": Equivalence,
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/libs/lang/test_relation_models.py -v`
Expected: PASS

**Step 5: Run full test suite**

Run: `pytest tests/libs/lang/ -v`
Expected: All existing tests still pass

**Step 6: Commit**

```bash
git add libs/lang/models.py tests/libs/lang/test_relation_models.py
git commit -m "feat: add Relation, Contradiction, Equivalence model classes"
```

---

### Task 2: Add RetractAction Model

**Files:**
- Modify: `libs/lang/models.py:82-97`
- Modify: `tests/libs/lang/test_relation_models.py`

**Step 1: Write the failing test**

Append to `tests/libs/lang/test_relation_models.py`:

```python
from libs.lang.models import RetractAction


def test_retract_action_model():
    r = RetractAction(
        name="retract_aristotle",
        target="heavier_falls_faster",
        reason="tied_balls_contradiction",
        prior=0.96,
    )
    assert r.type == "retract_action"
    assert r.target == "heavier_falls_faster"
    assert r.reason == "tied_balls_contradiction"
    assert r.prior == 0.96


def test_retract_action_in_declaration_map():
    assert "retract_action" in DECLARATION_TYPE_MAP
    assert DECLARATION_TYPE_MAP["retract_action"] is RetractAction
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/libs/lang/test_relation_models.py::test_retract_action_model -v`
Expected: FAIL with ImportError

**Step 3: Write minimal implementation**

Add to `libs/lang/models.py` after `ToolCallAction`:

```python
class RetractAction(Action):
    type: str = "retract_action"
    target: str = ""
    reason: str = ""  # ref to a Contradiction Relation
```

Update `DECLARATION_TYPE_MAP`:
```python
"retract_action": RetractAction,
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/libs/lang/test_relation_models.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add libs/lang/models.py tests/libs/lang/test_relation_models.py
git commit -m "feat: add RetractAction model class"
```

---

### Task 3: Update Loader to Parse Relation and RetractAction

**Files:**
- Modify: `libs/lang/loader.py:59-80`
- Modify: `tests/libs/lang/test_relation_models.py`

**Step 1: Write the failing test**

Append to `tests/libs/lang/test_relation_models.py`:

```python
from libs.lang.loader import _parse_declaration


def test_parse_contradiction_from_yaml_dict():
    data = {
        "type": "contradiction",
        "name": "test_contra",
        "between": ["claim_a", "claim_b"],
        "prior": 0.95,
    }
    decl = _parse_declaration(data)
    assert isinstance(decl, Contradiction)
    assert decl.between == ["claim_a", "claim_b"]
    assert decl.prior == 0.95


def test_parse_equivalence_from_yaml_dict():
    data = {
        "type": "equivalence",
        "name": "test_equiv",
        "between": ["claim_x", "claim_y"],
        "prior": 0.90,
    }
    decl = _parse_declaration(data)
    assert isinstance(decl, Equivalence)
    assert decl.between == ["claim_x", "claim_y"]


def test_parse_retract_action_from_yaml_dict():
    data = {
        "type": "retract_action",
        "name": "retract_test",
        "target": "some_claim",
        "reason": "some_contradiction",
        "prior": 0.96,
    }
    decl = _parse_declaration(data)
    assert isinstance(decl, RetractAction)
    assert decl.target == "some_claim"
    assert decl.reason == "some_contradiction"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/libs/lang/test_relation_models.py::test_parse_contradiction_from_yaml_dict -v`
Expected: Likely passes already since `_parse_declaration` uses `DECLARATION_TYPE_MAP` and falls through to `cls.model_validate(data)`. If so, this test just confirms loader handles new types.

**Step 3: Verify and commit**

If tests pass, the loader already handles the new types via `DECLARATION_TYPE_MAP`. No code change needed.

Run: `pytest tests/libs/lang/test_relation_models.py -v`
Expected: All PASS

**Step 4: Commit**

```bash
git add tests/libs/lang/test_relation_models.py
git commit -m "test: verify loader handles Relation and RetractAction parsing"
```

---

### Task 4: Update Compiler — Relation as Variable Node

**Files:**
- Modify: `libs/lang/compiler.py:19`
- Create: `tests/libs/lang/test_relation_compiler.py`

**Step 1: Write the failing test**

```python
# tests/libs/lang/test_relation_compiler.py
from libs.lang.compiler import compile_factor_graph
from libs.lang.models import (
    Claim,
    Contradiction,
    Equivalence,
    Module,
    Package,
)


def test_contradiction_compiles_to_variable_node():
    claim_a = Claim(name="a", content="A", prior=0.8)
    claim_b = Claim(name="b", content="B", prior=0.7)
    contra = Contradiction(
        name="a_contradicts_b",
        between=["a", "b"],
        prior=0.95,
    )
    mod = Module(
        type="reasoning_module",
        name="m",
        declarations=[claim_a, claim_b, contra],
        export=["a", "b", "a_contradicts_b"],
    )
    pkg = Package(name="test", modules=["m"])
    pkg.loaded_modules = [mod]

    fg = compile_factor_graph(pkg)

    assert "a" in fg.variables
    assert "b" in fg.variables
    assert "a_contradicts_b" in fg.variables
    assert fg.variables["a_contradicts_b"] == 0.95


def test_equivalence_compiles_to_variable_node():
    claim_x = Claim(name="x", content="X", prior=0.6)
    claim_y = Claim(name="y", content="Y", prior=0.9)
    equiv = Equivalence(
        name="x_equiv_y",
        between=["x", "y"],
        prior=0.85,
    )
    mod = Module(
        type="reasoning_module",
        name="m",
        declarations=[claim_x, claim_y, equiv],
        export=["x", "y", "x_equiv_y"],
    )
    pkg = Package(name="test", modules=["m"])
    pkg.loaded_modules = [mod]

    fg = compile_factor_graph(pkg)

    assert "x_equiv_y" in fg.variables
    assert fg.variables["x_equiv_y"] == 0.85
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/libs/lang/test_relation_compiler.py::test_contradiction_compiles_to_variable_node -v`
Expected: FAIL — `a_contradicts_b` not in `fg.variables` (BP_VARIABLE_TYPES doesn't include "contradiction")

**Step 3: Write minimal implementation**

In `libs/lang/compiler.py`, update line 19:

```python
BP_VARIABLE_TYPES = {"claim", "setting", "contradiction", "equivalence"}
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/libs/lang/test_relation_compiler.py -v`
Expected: PASS

**Step 5: Run full test suite**

Run: `pytest tests/libs/lang/ -v`
Expected: All existing tests still pass

**Step 6: Commit**

```bash
git add libs/lang/compiler.py tests/libs/lang/test_relation_compiler.py
git commit -m "feat: compile Relation declarations to variable nodes"
```

---

### Task 5: Update Compiler — Relation Constraint Factor

**Files:**
- Modify: `libs/lang/compiler.py:36-75`
- Modify: `tests/libs/lang/test_relation_compiler.py`

**Step 1: Write the failing test**

Append to `tests/libs/lang/test_relation_compiler.py`:

```python
def test_contradiction_generates_constraint_factor():
    claim_a = Claim(name="a", content="A", prior=0.8)
    claim_b = Claim(name="b", content="B", prior=0.7)
    contra = Contradiction(
        name="a_contradicts_b",
        between=["a", "b"],
        prior=0.95,
    )
    mod = Module(
        type="reasoning_module",
        name="m",
        declarations=[claim_a, claim_b, contra],
        export=["a", "b", "a_contradicts_b"],
    )
    pkg = Package(name="test", modules=["m"])
    pkg.loaded_modules = [mod]

    fg = compile_factor_graph(pkg)

    # Should have one constraint factor from the Contradiction
    assert len(fg.factors) == 1
    factor = fg.factors[0]
    assert factor["edge_type"] == "relation_contradiction"
    assert set(factor["premises"]) == {"a", "b"}
    assert factor["conclusions"] == ["a_contradicts_b"]


def test_equivalence_generates_constraint_factor():
    claim_x = Claim(name="x", content="X", prior=0.6)
    claim_y = Claim(name="y", content="Y", prior=0.9)
    equiv = Equivalence(
        name="x_equiv_y",
        between=["x", "y"],
        prior=0.85,
    )
    mod = Module(
        type="reasoning_module",
        name="m",
        declarations=[claim_x, claim_y, equiv],
        export=["x", "y", "x_equiv_y"],
    )
    pkg = Package(name="test", modules=["m"])
    pkg.loaded_modules = [mod]

    fg = compile_factor_graph(pkg)

    assert len(fg.factors) == 1
    factor = fg.factors[0]
    assert factor["edge_type"] == "relation_equivalence"
    assert set(factor["premises"]) == {"x", "y"}
    assert factor["conclusions"] == ["x_equiv_y"]
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/libs/lang/test_relation_compiler.py::test_contradiction_generates_constraint_factor -v`
Expected: FAIL — `len(fg.factors) == 0` (compiler doesn't generate factors from Relations)

**Step 3: Write minimal implementation**

In `libs/lang/compiler.py`, add import and compilation function:

```python
from .models import (
    ChainExpr,
    Contradiction,
    Declaration,
    Equivalence,
    Package,
    Ref,
    Relation,
    StepApply,
    StepLambda,
    StepRef,
)
```

Add a `_compile_relation` function and call it from `compile_factor_graph`:

```python
def _compile_relation(
    rel: Relation,
    all_decls: dict[str, Declaration],
    fg: CompiledFactorGraph,
) -> None:
    """Compile a Relation into a constraint factor connecting related claims."""
    # Only include claims that are variable nodes
    related_vars = [name for name in rel.between if name in fg.variables]
    if len(related_vars) < 2:
        return

    edge_type = f"relation_{rel.type}"
    fg.factors.append(
        {
            "name": f"{rel.name}.constraint",
            "premises": related_vars,
            "conclusions": [rel.name] if rel.name in fg.variables else [],
            "probability": 0.99,  # constraint strength when relation is believed
            "edge_type": edge_type,
        }
    )
```

In `compile_factor_graph`, after the ChainExpr loop (after line 74), add:

```python
    # Add constraint factors from Relation declarations
    for module in pkg.loaded_modules:
        for decl in module.declarations:
            if isinstance(decl, Relation):
                _compile_relation(decl, all_decls, fg)
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/libs/lang/test_relation_compiler.py -v`
Expected: PASS

**Step 5: Run full test suite**

Run: `pytest tests/libs/lang/ -v`
Expected: All existing tests still pass

**Step 6: Commit**

```bash
git add libs/lang/compiler.py tests/libs/lang/test_relation_compiler.py
git commit -m "feat: compile Relation declarations to constraint factors"
```

---

### Task 6: Update BP — relation_contradiction Potential

**Files:**
- Modify: `libs/inference/bp.py:54-106`
- Modify: `tests/services/test_inference_engine/test_bp.py`

**Step 1: Write the failing test**

Add to `tests/services/test_inference_engine/test_bp.py`:

```python
class TestRelationContradiction:
    """Tests for the relation_contradiction factor (3-variable: A, B, E)."""

    def test_mutex_penalizes_both_true(self):
        """When E is believed, A=1 and B=1 should be penalized."""
        fg = FactorGraph()
        fg.add_variable(1, 0.8)  # Claim A
        fg.add_variable(2, 0.7)  # Claim B
        fg.add_variable(3, 0.95)  # Contradiction relation E
        fg.add_factor(
            edge_id=1,
            premises=[1, 2],
            conclusions=[3],
            probability=0.99,
            edge_type="relation_contradiction",
        )
        beliefs = bp.run(fg)
        # Both claims should drop (can't both be true)
        assert beliefs[1] < 0.8
        assert beliefs[2] < 0.7
        # Contradiction belief should remain high
        assert beliefs[3] > 0.8

    def test_mutex_no_effect_when_relation_low(self):
        """When E belief is low, A and B should be minimally affected."""
        fg = FactorGraph()
        fg.add_variable(1, 0.8)  # Claim A
        fg.add_variable(2, 0.7)  # Claim B
        fg.add_variable(3, 0.1)  # Low belief in contradiction
        fg.add_factor(
            edge_id=1,
            premises=[1, 2],
            conclusions=[3],
            probability=0.99,
            edge_type="relation_contradiction",
        )
        beliefs = bp.run(fg)
        # Claims should be minimally affected
        assert abs(beliefs[1] - 0.8) < 0.1
        assert abs(beliefs[2] - 0.7) < 0.1
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/services/test_inference_engine/test_bp.py::TestRelationContradiction -v`
Expected: FAIL — existing `_evaluate_potential` treats "relation_contradiction" as deduction (default)

**Step 3: Write minimal implementation**

In `libs/inference/bp.py`, update `_evaluate_potential` (add before the `all_premises_true` check):

```python
def _evaluate_potential(
    edge_type: str,
    premise_ids: list[int],
    conclusion_ids: list[int],
    assignment: dict[int, int],
    prob: float,
) -> float:
    # Relation types: custom gating (not "all premises true")
    if edge_type == "relation_contradiction":
        # premises = [A, B], conclusions = [E]
        # When E=1 and A=1 and B=1: penalty (1-prob)
        # Otherwise: unconstrained (1.0)
        e_val = assignment[conclusion_ids[0]] if conclusion_ids else 1
        if e_val == 0:
            return 1.0
        all_claims_true = all(assignment[p] == 1 for p in premise_ids)
        return (1.0 - prob) if all_claims_true else 1.0

    if edge_type == "relation_equivalence":
        # Handle in next task
        pass

    # ... existing code unchanged below ...
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/services/test_inference_engine/test_bp.py::TestRelationContradiction -v`
Expected: PASS

**Step 5: Run full test suite**

Run: `pytest tests/services/test_inference_engine/ -v`
Expected: All existing BP tests still pass

**Step 6: Commit**

```bash
git add libs/inference/bp.py tests/services/test_inference_engine/test_bp.py
git commit -m "feat: add relation_contradiction factor potential to BP"
```

---

### Task 7: Update BP — relation_equivalence Potential

**Files:**
- Modify: `libs/inference/bp.py:54-106`
- Modify: `tests/services/test_inference_engine/test_bp.py`

**Step 1: Write the failing test**

Add to `tests/services/test_inference_engine/test_bp.py`:

```python
class TestRelationEquivalence:
    """Tests for the relation_equivalence factor (3-variable: A, B, E)."""

    def test_equiv_pulls_beliefs_together(self):
        """When E is believed, A and B beliefs should converge."""
        fg = FactorGraph()
        fg.add_variable(1, 0.6)  # Claim A (lower evidence)
        fg.add_variable(2, 0.9)  # Claim B (higher evidence)
        fg.add_variable(3, 0.95)  # Equivalence relation E
        fg.add_factor(
            edge_id=1,
            premises=[1, 2],
            conclusions=[3],
            probability=0.99,
            edge_type="relation_equivalence",
        )
        beliefs = bp.run(fg)
        # Beliefs should be closer together than priors
        prior_gap = abs(0.9 - 0.6)
        posterior_gap = abs(beliefs[2] - beliefs[1])
        assert posterior_gap < prior_gap
        # Both should benefit from shared evidence
        assert beliefs[1] > 0.6  # A pulled up
        assert beliefs[2] <= 0.9  # B may dip slightly or stay

    def test_equiv_no_effect_when_relation_low(self):
        """When E belief is low, A and B should stay near priors."""
        fg = FactorGraph()
        fg.add_variable(1, 0.6)  # Claim A
        fg.add_variable(2, 0.9)  # Claim B
        fg.add_variable(3, 0.1)  # Low belief in equivalence
        fg.add_factor(
            edge_id=1,
            premises=[1, 2],
            conclusions=[3],
            probability=0.99,
            edge_type="relation_equivalence",
        )
        beliefs = bp.run(fg)
        # Beliefs should stay near priors
        assert abs(beliefs[1] - 0.6) < 0.15
        assert abs(beliefs[2] - 0.9) < 0.15
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/services/test_inference_engine/test_bp.py::TestRelationEquivalence -v`
Expected: FAIL

**Step 3: Write minimal implementation**

In `libs/inference/bp.py`, update the `relation_equivalence` branch:

```python
    if edge_type == "relation_equivalence":
        # premises = [A, B], conclusions = [E]
        # When E=1: reward A==B, penalize A!=B
        # When E=0: unconstrained
        e_val = assignment[conclusion_ids[0]] if conclusion_ids else 1
        if e_val == 0:
            return 1.0
        a_val = assignment[premise_ids[0]]
        b_val = assignment[premise_ids[1]]
        if a_val == b_val:
            return prob  # Agreement rewarded
        else:
            return 1.0 - prob  # Disagreement penalized
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/services/test_inference_engine/test_bp.py::TestRelationEquivalence -v`
Expected: PASS

**Step 5: Run full test suite**

Run: `pytest tests/services/test_inference_engine/ -v`
Expected: All PASS

**Step 6: Commit**

```bash
git add libs/inference/bp.py tests/services/test_inference_engine/test_bp.py
git commit -m "feat: add relation_equivalence factor potential to BP"
```

---

### Task 8: Update Runtime — Relation Belief Writeback

**Files:**
- Modify: `libs/lang/runtime.py:88-100`
- Create: `tests/libs/lang/test_relation_runtime.py`

**Step 1: Write the failing test**

```python
# tests/libs/lang/test_relation_runtime.py
from pathlib import Path

from libs.lang.compiler import compile_factor_graph
from libs.lang.models import (
    Claim,
    Contradiction,
    Module,
    Package,
)
from libs.lang.runtime import GaiaRuntime


async def test_contradiction_gets_belief_after_inference():
    """Relation declarations should have .belief set after BP."""
    claim_a = Claim(name="a", content="A", prior=0.8)
    claim_b = Claim(name="b", content="B", prior=0.7)
    contra = Contradiction(
        name="a_contradicts_b",
        between=["a", "b"],
        prior=0.95,
    )
    mod = Module(
        type="reasoning_module",
        name="m",
        declarations=[claim_a, claim_b, contra],
        export=["a", "b", "a_contradicts_b"],
    )
    pkg = Package(name="test_relation_bp", modules=["m"])
    pkg.loaded_modules = [mod]

    runtime = GaiaRuntime()
    result = await runtime.infer(
        type(runtime).load.__func__.__class__.__new__(type(None))  # skip this
    )
    # Actually, build the result manually:
    from libs.lang.runtime import RuntimeResult
    result = RuntimeResult(package=pkg)
    result = await runtime.infer(result)

    # Relation should have belief computed
    assert "a_contradicts_b" in result.beliefs
    assert contra.belief is not None
    assert contra.belief == result.beliefs["a_contradicts_b"]
```

**Step 2: Run test to verify behavior**

Run: `pytest tests/libs/lang/test_relation_runtime.py -v`
Expected: This may already pass since `runtime.infer()` writes back belief to any declaration with a `.belief` attribute, and Relation has `.belief`. If it passes, the runtime already handles Relation correctly.

**Step 3: If needed, update runtime**

The current runtime code (lines 97-100) does:
```python
for name, belief_val in result.beliefs.items():
    target = all_decls_by_name.get(name)
    if target is not None and hasattr(target, "belief"):
        target.belief = belief_val
```

Since `Relation` has a `.belief` field, this should work without changes. Verify by running the test.

**Step 4: Commit**

```bash
git add tests/libs/lang/test_relation_runtime.py
git commit -m "test: verify runtime handles Relation belief writeback"
```

---

### Task 9: Refactor Galileo Example — Add Relation Declarations

**Files:**
- Modify: `tests/fixtures/gaia_language_packages/galileo_falling_bodies/reasoning.yaml`
- Modify: `tests/libs/lang/test_compiler.py`
- Modify: `tests/libs/lang/test_integration.py`

This is the most involved task. The Galileo example currently models contradiction/retraction via ChainExpr `edge_type`. We refactor to use Relation + RetractAction declarations.

**Step 1: Update reasoning.yaml**

Replace the `tied_balls_contradiction` Claim with a Contradiction Relation:

```yaml
# OLD (remove):
- type: claim
  name: tied_balls_contradiction
  content: >
    同一定律对同一绑球系统同时预测"更慢"和"更快"，自相矛盾。
  prior: 0.6

# NEW (add):
- type: contradiction
  name: tied_balls_contradiction
  between:
    - tied_pair_slower_than_heavy
    - tied_pair_faster_than_heavy
  prior: 0.6
```

Update `contradiction_chain` — remove `edge_type: contradiction`, keep it as a standard deduction chain that produces the Relation:

```yaml
# OLD:
- type: chain_expr
  name: contradiction_chain
  edge_type: contradiction
  steps: ...

# NEW:
- type: chain_expr
  name: contradiction_chain
  steps:
    - step: 1
      ref: tied_pair_slower_than_heavy
    - step: 2
      apply: expose_mutual_exclusion
      args:
        - ref: tied_pair_slower_than_heavy
          dependency: direct
        - ref: tied_pair_faster_than_heavy
          dependency: direct
      prior: 0.97
    - step: 3
      ref: tied_balls_contradiction
```

Replace `retraction_chain` with a RetractAction:

```yaml
# OLD (remove):
- type: chain_expr
  name: retraction_chain
  edge_type: retraction
  steps: ...

# NEW (add):
- type: retract_action
  name: retract_aristotle
  target: heavier_falls_faster
  reason: tied_balls_contradiction
  prior: 0.96
```

**Step 2: Update test assertions**

In `tests/libs/lang/test_compiler.py`:

- `test_compile_produces_factor_graph`: Update variable count (14 → 14, `tied_balls_contradiction` is still a variable but now as Relation type). Factor count changes: 11 → 11 (contradiction_chain loses its contradiction edge_type but gains a constraint factor from the Relation; retraction_chain is removed but RetractAction adds nothing to factors). Recalculate exact counts after running.

- `test_contradiction_edge_captures_two_mutually_exclusive_predictions`: Update to check for `relation_contradiction` edge_type on the constraint factor.

- `test_retraction_edge_pushes_back_on_aristotle_law`: Remove this test (retraction_chain no longer exists).

In `tests/libs/lang/test_integration.py`:

- `test_galileo_full_pipeline`: Update `edge_types` assertion — "retraction" no longer in edge types, "relation_contradiction" is new. Update variable/factor counts if changed.

**Step 3: Run tests iteratively**

Run: `pytest tests/libs/lang/test_compiler.py -v`
Fix assertion counts until all pass.

Run: `pytest tests/libs/lang/test_integration.py -v`
Fix assertion counts until all pass.

Run: `pytest tests/libs/lang/ -v`
All must pass.

**Step 4: Commit**

```bash
git add tests/fixtures/gaia_language_packages/galileo_falling_bodies/reasoning.yaml \
        tests/libs/lang/test_compiler.py \
        tests/libs/lang/test_integration.py
git commit -m "refactor: Galileo example uses Relation + RetractAction instead of edge_type"
```

---

### Task 10: Deprecate edge_type on ChainExpr

**Files:**
- Modify: `libs/lang/models.py` (ChainExpr class)
- Modify: `libs/lang/compiler.py` (_compile_chain)
- Modify: `libs/lang/loader.py` (_parse_declaration)

**Step 1: Add deprecation warning**

In `libs/lang/compiler.py`, `_compile_chain` function, add a warning when `edge_type` is used:

```python
import warnings

def _compile_chain(...) -> None:
    if chain.edge_type is not None:
        warnings.warn(
            f"ChainExpr.edge_type is deprecated. Use Relation declarations instead. "
            f"Chain '{chain.name}' uses edge_type='{chain.edge_type}'.",
            DeprecationWarning,
            stacklevel=2,
        )
```

**Step 2: Write test for deprecation warning**

Add to `tests/libs/lang/test_relation_compiler.py`:

```python
import warnings

def test_edge_type_emits_deprecation_warning():
    claim_a = Claim(name="a", content="x", prior=0.8)
    claim_b = Claim(name="b", content="", prior=0.5)
    chain = ChainExpr(
        name="old_chain",
        edge_type="contradiction",
        steps=[
            StepRef(step=1, ref="a"),
            StepLambda(step=2, **{"lambda": "reason"}, prior=0.9),
            StepRef(step=3, ref="b"),
        ],
    )
    mod = Module(
        type="reasoning_module",
        name="m",
        declarations=[claim_a, claim_b, chain],
        export=["a", "b"],
    )
    pkg = Package(name="test_deprecated", modules=["m"])
    pkg.loaded_modules = [mod]

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        compile_factor_graph(pkg)
        assert any("deprecated" in str(warning.message).lower() for warning in w)
```

**Step 3: Run tests**

Run: `pytest tests/libs/lang/ -v`
Expected: All PASS

**Step 4: Commit**

```bash
git add libs/lang/models.py libs/lang/compiler.py libs/lang/loader.py \
        tests/libs/lang/test_relation_compiler.py
git commit -m "deprecate: ChainExpr.edge_type in favor of Relation declarations"
```

---

### Task 11: Final Integration Test

**Files:**
- Modify: `tests/libs/lang/test_relation_runtime.py`

**Step 1: Write integration test**

```python
async def test_contradiction_weakens_shared_premises():
    """Full pipeline: Contradiction relation should weaken beliefs of claims
    that are premises of both contradicting claims."""
    from libs.lang.models import (
        Claim, Contradiction, ChainExpr, InferAction,
        Module, Package, StepRef, StepLambda,
    )
    from libs.lang.runtime import GaiaRuntime, RuntimeResult

    # Setup: shared premise → two contradicting conclusions
    premise = Claim(name="premise", content="Shared premise", prior=0.8)
    claim_a = Claim(name="a", content="Prediction A", prior=0.5)
    claim_b = Claim(name="b", content="Prediction B", prior=0.5)

    chain_a = ChainExpr(
        name="chain_a",
        steps=[
            StepRef(step=1, ref="premise"),
            StepLambda(step=2, **{"lambda": "derive A"}, prior=0.9),
            StepRef(step=3, ref="a"),
        ],
    )
    chain_b = ChainExpr(
        name="chain_b",
        steps=[
            StepRef(step=1, ref="premise"),
            StepLambda(step=2, **{"lambda": "derive B"}, prior=0.9),
            StepRef(step=3, ref="b"),
        ],
    )
    contra = Contradiction(
        name="a_vs_b",
        between=["a", "b"],
        prior=0.95,
    )

    mod = Module(
        type="reasoning_module",
        name="m",
        declarations=[premise, claim_a, claim_b, chain_a, chain_b, contra],
        export=["premise", "a", "b", "a_vs_b"],
    )
    pkg = Package(name="test_integration", modules=["m"])
    pkg.loaded_modules = [mod]

    runtime = GaiaRuntime()
    result = RuntimeResult(package=pkg)
    result = await runtime.infer(result)

    # Both claims should be lower than without contradiction
    # (contradiction penalizes both being true)
    assert result.beliefs["a"] < 0.8  # Would be ~0.8 without contradiction
    assert result.beliefs["b"] < 0.8

    # Shared premise should also be weakened (indirect BP propagation)
    assert result.beliefs["premise"] < 0.8
```

**Step 2: Run tests**

Run: `pytest tests/libs/lang/test_relation_runtime.py -v`
Expected: PASS

**Step 3: Full suite**

Run: `pytest tests/ -v --timeout=60`
Expected: All PASS

**Step 4: Final commit**

```bash
git add tests/libs/lang/test_relation_runtime.py
git commit -m "test: add integration test for Contradiction belief propagation"
```

---

## Summary

| Task | What | Files |
|------|------|-------|
| 1 | Relation, Contradiction, Equivalence models | `models.py`, `test_relation_models.py` |
| 2 | RetractAction model | `models.py` |
| 3 | Loader parsing verification | `test_relation_models.py` |
| 4 | Compiler: Relation as variable node | `compiler.py`, `test_relation_compiler.py` |
| 5 | Compiler: Relation constraint factor | `compiler.py` |
| 6 | BP: relation_contradiction potential | `bp.py`, `test_bp.py` |
| 7 | BP: relation_equivalence potential | `bp.py`, `test_bp.py` |
| 8 | Runtime: Relation belief writeback | `test_relation_runtime.py` |
| 9 | Galileo example refactoring | `reasoning.yaml`, all test files |
| 10 | Deprecate ChainExpr.edge_type | `compiler.py`, `loader.py` |
| 11 | Integration test | `test_relation_runtime.py` |
