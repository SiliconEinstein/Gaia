# Gaia IR Validation Consolidation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Merge PR 257's validation additions into PR 256's branch, establishing a clean two-tier validation architecture with no duplication.

**Architecture:** Tier 1 (Pydantic model validators) handles single-object invariants at construction time. Tier 2 (`validator.py`) handles all cross-entity/graph-level validation via an accumulator pattern. Graph containers (`LocalCanonicalGraph`, `GlobalCanonicalGraph`) do NOT validate cross-entity references — they only auto-compute hashes and store data.

**Tech Stack:** Python 3.12, Pydantic v2, pytest

**Working branch:** `work/gaia-ir-validator` (PR 256's branch)

---

## Design: Validation Responsibility Split

### Tier 1 — Pydantic `model_validator` (inside each model, fail-fast at construction)

Single-object invariants that can be checked with no external context:

| Model | Validation | Source |
|-------|-----------|--------|
| `Knowledge._compute_id` | Auto-compute content-addressed ID; require `id` or `content+package_id` | PR 255 (already in 256) |
| `Operator._validate_invariants` | conclusion rules per type (§2.4); scope ∈ {None, "local", "global"}; scope↔prefix (`lco_`/`gco_`); directed operators require `conclusion == variables[-1]` | PR 255 + **merge from 257** |
| `Strategy._compute_id_and_validate` | Auto-compute ID; scope ∈ {"local", "global"}; scope↔prefix (`lcs_`/`gcs_`); global must not have steps | PR 255 + **merge from 257** |
| `Strategy._validate_leaf_form` | Base Strategy class allows only leaf types (infer, noisy_and, toolcall, proof) | **New from 257** |
| `CompositeStrategy._validate_sub_strategies` | ≥1 sub-strategy; type must be composite type (abduction, induction, analogy, extrapolation) | PR 255 + **merge from 257** |
| `FormalStrategy._validate_formal_expr` | ≥1 operator; type must be formal type (deduction, reductio, elimination, mathematical_induction, case_analysis) | PR 255 + **merge from 257** |
| `PriorRecord` / `StrategyParamRecord` | Cromwell clamping | PR 255 (already in 256) |
| `LocalCanonicalGraph._compute_hash` | Auto-compute `ir_hash` with canonical JSON (sorted entities) | PR 255 + **canonicalization from 257** |

### Tier 2 — External `validator.py` (accumulator pattern, explicit call)

Cross-entity and pipeline-level checks:

| Function | Validation | Source |
|----------|-----------|--------|
| `validate_local_graph` | Knowledge: ID prefix `lcn_`, uniqueness, claim content completeness, **must have content** (local layer), **must not have representative_lcn/local_members**; Operator: reference completeness (vars exist + are claims), scope ∈ {None, "local"}; Strategy: prefix, uniqueness, premise/conclusion ref + must be claim, self-loop, background warning, scope must be "local"; Scope consistency; Hash consistency | PR 256 + **local-layer shape rules from 257** |
| `validate_global_graph` | Knowledge: ID prefix `gcn_`, uniqueness, **must have content or representative_lcn**; same Operator/Strategy cross-ref checks; scope rules for global | PR 256 + **global-layer shape rules from 257** |
| `validate_parameterization` | Prior coverage for claims, strategy param coverage, Cromwell bounds, dangling ref warnings | PR 256 (unchanged) |
| `validate_bindings` | 1:1 binding for every local knowledge, ref validity | PR 256 (unchanged) |

### What gets REMOVED

- `graphs.py`: `_validate_contract` on `LocalCanonicalGraph` and `GlobalCanonicalGraph` (PR 257) — **deleted**, these checks move to `validator.py`
- `graphs.py`: `_validate_local_knowledge`, `_validate_global_knowledge`, `_validate_operator_ids`, `_validate_strategy_connections` helper functions (PR 257) — **deleted**, equivalent logic already in `validator.py`
- `graphs.py`: Tests in `test_graphs.py` that test contract validation via construction (`test_rejects_local_knowledge_without_content`, `test_rejects_global_knowledge_without_content_source`) — **moved** to `test_validator.py`

### What gets KEPT from PR 257

Into `operator.py` (Tier 1):
- scope validation (`None`, `"local"`, `"global"`)
- scope↔prefix enforcement (`lco_`/`gco_`)
- `implication`/`conjunction`: conclusion must be `variables[-1]`

Into `strategy.py` (Tier 1):
- scope validation (`"local"`, `"global"`)
- scope↔prefix enforcement (`lcs_`/`gcs_`)
- global must not have steps
- `_validate_leaf_form` (leaf type restriction)
- `_LEAF_STRATEGY_TYPES`, `_COMPOSITE_STRATEGY_TYPES`, `_FORMAL_STRATEGY_TYPES` constants
- CompositeStrategy type restriction
- FormalStrategy type restriction

Into `graphs.py` (hash only):
- `_canonicalize_knowledge_dump`, `_canonicalize_operator_dump`, `_canonicalize_strategy_dump` (canonical JSON for insertion-order-independent hashing)

Into `validator.py` (Tier 2):
- Local knowledge shape rules (must have content, must not have representative_lcn/local_members)
- Global knowledge shape rules (must have content or representative_lcn)

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `gaia/gaia_ir/operator.py` | Modify | Add scope validation + scope↔prefix + conclusion position from PR 257 |
| `gaia/gaia_ir/strategy.py` | Modify | Add scope/prefix, global-steps, form↔type from PR 257 |
| `gaia/gaia_ir/graphs.py` | Modify | Add canonicalization helpers from PR 257; NO `_validate_contract` |
| `gaia/gaia_ir/validator.py` | Modify | Add local/global knowledge shape rules from PR 257 |
| `tests/gaia_ir/test_operator.py` | Modify | Add tests for scope/prefix/position from PR 257 |
| `tests/gaia_ir/test_strategy.py` | Modify | Add tests for scope/prefix/form↔type from PR 257 |
| `tests/gaia_ir/test_graphs.py` | Modify | Add hash-order-independence test; remove contract-validation tests |
| `tests/gaia_ir/test_validator.py` | Modify | Add knowledge shape rule tests |

---

## Chunk 1: Tier 1 — Entity-Level Validators

### Task 1: Update `Operator._validate_invariants`

**Files:**
- Modify: `gaia/gaia_ir/operator.py`
- Test: `tests/gaia_ir/test_operator.py`

- [ ] **Step 1: Write failing tests for new Operator invariants**

Add to `tests/gaia_ir/test_operator.py`:

```python
def test_implication_requires_conclusion_as_last_variable(self):
    with pytest.raises(ValueError, match="variables\\[-1\\]"):
        Operator(operator="implication", variables=["a", "b"], conclusion="a")

def test_conjunction_requires_conclusion_as_last_variable(self):
    with pytest.raises(ValueError, match="variables\\[-1\\]"):
        Operator(operator="conjunction", variables=["a", "b", "m"], conclusion="a")

def test_invalid_scope_rejected(self):
    with pytest.raises(ValueError, match="scope must be one of"):
        Operator(scope="detached", operator="equivalence", variables=["a", "b"])

# Existing scope prefix tests already pass implicitly, but add explicit ones:
def test_local_scope_requires_lco_prefix(self):
    with pytest.raises(ValueError, match="lco_ prefix"):
        Operator(
            operator_id="gco_wrong", scope="local",
            operator="equivalence", variables=["a", "b"],
        )

def test_global_scope_requires_gco_prefix(self):
    with pytest.raises(ValueError, match="gco_ prefix"):
        Operator(
            operator_id="lco_wrong", scope="global",
            operator="equivalence", variables=["a", "b"],
        )
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/gaia_ir/test_operator.py -v -x`
Expected: FAIL — the new tests should fail because current code lacks scope/position checks.

- [ ] **Step 3: Implement Operator validator changes**

Replace `Operator._validate_invariants` in `gaia/gaia_ir/operator.py` with the version from PR 257. Key additions:
- scope validation: `self.scope not in (None, "local", "global")` → ValueError
- local scope + operator_id → must start with `lco_`
- global scope + operator_id → must start with `gco_`
- implication: add `conclusion != variables[-1]` check
- conjunction: add `conclusion != variables[-1]` check
- Restructure `conclusion in variables` check to avoid duplicate with implication/conjunction blocks

Full replacement for `_validate_invariants`:

```python
@model_validator(mode="after")
def _validate_invariants(self) -> Operator:
    if self.scope not in (None, "local", "global"):
        raise ValueError("scope must be one of: None, 'local', 'global'")

    if self.scope == "local" and self.operator_id is not None and not self.operator_id.startswith("lco_"):
        raise ValueError("local operators must use an operator_id with lco_ prefix")

    if self.scope == "global" and self.operator_id is not None and not self.operator_id.startswith("gco_"):
        raise ValueError("global operators must use an operator_id with gco_ prefix")

    # §2.4: conclusion rules by operator type
    if self.operator in (
        OperatorType.EQUIVALENCE,
        OperatorType.CONTRADICTION,
        OperatorType.COMPLEMENT,
        OperatorType.DISJUNCTION,
    ):
        if self.conclusion is not None:
            raise ValueError(f"operator={self.operator} must have conclusion=None")

    if self.operator == OperatorType.IMPLICATION:
        if self.conclusion is None:
            raise ValueError("operator=implication requires conclusion")
        if len(self.variables) != 2:
            raise ValueError("operator=implication requires exactly 2 variables")
        if self.conclusion not in self.variables:
            raise ValueError(f"conclusion {self.conclusion} must appear in variables")
        if self.conclusion != self.variables[-1]:
            raise ValueError("operator=implication requires conclusion=variables[-1]")

    if self.operator == OperatorType.CONJUNCTION:
        if self.conclusion is None:
            raise ValueError("operator=conjunction requires conclusion (the conjunct M)")
        if self.conclusion not in self.variables:
            raise ValueError(f"conclusion {self.conclusion} must appear in variables")
        if self.conclusion != self.variables[-1]:
            raise ValueError("operator=conjunction requires conclusion=variables[-1]")

    if self.operator in (OperatorType.EQUIVALENCE, OperatorType.COMPLEMENT):
        if len(self.variables) != 2:
            raise ValueError(f"operator={self.operator} requires exactly 2 variables")

    # conclusion must be in variables (catch-all for future types)
    if (
        self.conclusion is not None
        and self.operator not in (OperatorType.IMPLICATION, OperatorType.CONJUNCTION)
        and self.conclusion not in self.variables
    ):
        raise ValueError(f"conclusion {self.conclusion} must appear in variables")

    return self
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/gaia_ir/test_operator.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add gaia/gaia_ir/operator.py tests/gaia_ir/test_operator.py
git commit -m "feat(gaia-ir): enforce operator scope/prefix and conclusion position invariants"
```

---

### Task 2: Update Strategy validators

**Files:**
- Modify: `gaia/gaia_ir/strategy.py`
- Test: `tests/gaia_ir/test_strategy.py`

- [ ] **Step 1: Write failing tests for Strategy invariants**

Add to `tests/gaia_ir/test_strategy.py`:

```python
# In TestStrategyCreation:
def test_invalid_scope_rejected(self):
    with pytest.raises(ValueError, match="scope must be one of"):
        Strategy(scope="detached", type="infer", premises=["a"], conclusion="b")

def test_global_steps_rejected(self):
    with pytest.raises(ValueError, match="must not carry steps"):
        Strategy(
            scope="global", type="infer",
            premises=["gcn_a"], conclusion="gcn_b",
            steps=[Step(reasoning="should stay local")],
        )

def test_leaf_rejects_named_strategy_type(self):
    with pytest.raises(ValueError, match="Strategy form only allows types"):
        Strategy(scope="global", type="deduction", premises=["gcn_a"], conclusion="gcn_b")

# In TestCompositeStrategy:
def test_composite_rejects_leaf_type(self):
    with pytest.raises(ValueError, match="CompositeStrategy form only allows types"):
        CompositeStrategy(
            scope="global", type="infer",
            premises=["gcn_a"], conclusion="gcn_b",
            sub_strategies=[Strategy(scope="global", type="infer", premises=["gcn_a"], conclusion="gcn_b")],
        )

# In TestFormalStrategy:
def test_formal_rejects_composite_type(self):
    with pytest.raises(ValueError, match="FormalStrategy form only allows types"):
        FormalStrategy(
            scope="local", type="induction",
            premises=["a"], conclusion="b",
            formal_expr=FormalExpr(operators=[
                Operator(operator="implication", variables=["a", "b"], conclusion="b"),
            ]),
        )
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/gaia_ir/test_strategy.py -v -x`
Expected: FAIL

- [ ] **Step 3: Implement Strategy validator changes**

In `gaia/gaia_ir/strategy.py`:

1. Add type set constants before `Strategy` class:

```python
_LEAF_STRATEGY_TYPES = frozenset({
    StrategyType.INFER, StrategyType.NOISY_AND,
    StrategyType.TOOLCALL, StrategyType.PROOF,
})

_COMPOSITE_STRATEGY_TYPES = frozenset({
    StrategyType.ABDUCTION, StrategyType.INDUCTION,
    StrategyType.ANALOGY, StrategyType.EXTRAPOLATION,
})

_FORMAL_STRATEGY_TYPES = frozenset({
    StrategyType.DEDUCTION, StrategyType.REDUCTIO,
    StrategyType.ELIMINATION, StrategyType.MATHEMATICAL_INDUCTION,
    StrategyType.CASE_ANALYSIS,
})
```

2. Replace `Strategy._compute_id_and_validate`:

```python
@model_validator(mode="after")
def _compute_id_and_validate(self) -> Strategy:
    if self.scope not in {"local", "global"}:
        raise ValueError("scope must be one of: 'local', 'global'")

    if self.scope == "global" and self.steps is not None:
        raise ValueError("global Strategy must not carry steps")

    if self.strategy_id is not None:
        expected_prefix = "lcs_" if self.scope == "local" else "gcs_"
        if not self.strategy_id.startswith(expected_prefix):
            raise ValueError(
                f"{self.scope} strategies must use a strategy_id with {expected_prefix} prefix"
            )

    if self.strategy_id is None:
        self.strategy_id = _compute_strategy_id(
            self.scope, self.type, self.premises, self.conclusion
        )
    return self
```

3. Add `_validate_leaf_form` to `Strategy`:

```python
@model_validator(mode="after")
def _validate_leaf_form(self) -> Strategy:
    if self.__class__ is Strategy and self.type not in _LEAF_STRATEGY_TYPES:
        allowed = ", ".join(sorted(t.value for t in _LEAF_STRATEGY_TYPES))
        raise ValueError(
            f"Strategy form only allows types: {allowed}; got {self.type.value}"
        )
    return self
```

4. Add type check in `CompositeStrategy._validate_sub_strategies`:

```python
@model_validator(mode="after")
def _validate_sub_strategies(self) -> CompositeStrategy:
    if not self.sub_strategies:
        raise ValueError("CompositeStrategy requires at least one sub_strategy")
    if self.type not in _COMPOSITE_STRATEGY_TYPES:
        allowed = ", ".join(sorted(t.value for t in _COMPOSITE_STRATEGY_TYPES))
        raise ValueError(
            f"CompositeStrategy form only allows types: {allowed}; got {self.type.value}"
        )
    return self
```

5. Add type check in `FormalStrategy._validate_formal_expr`:

```python
@model_validator(mode="after")
def _validate_formal_expr(self) -> FormalStrategy:
    if not self.formal_expr.operators:
        raise ValueError("FormalStrategy requires at least one operator in formal_expr")
    if self.type not in _FORMAL_STRATEGY_TYPES:
        allowed = ", ".join(sorted(t.value for t in _FORMAL_STRATEGY_TYPES))
        raise ValueError(
            f"FormalStrategy form only allows types: {allowed}; got {self.type.value}"
        )
    return self
```

- [ ] **Step 4: Fix existing tests that break due to new constraints**

Some existing tests in PR 256 use invalid form↔type combos (e.g. `CompositeStrategy` with `type="infer"`). Fix them:
- `test_strategy.py::TestCompositeStrategy::test_recursive_nesting`: change inner CompositeStrategy type from `"infer"` to `"abduction"`

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/gaia_ir/test_strategy.py -v`
Expected: ALL PASS

- [ ] **Step 6: Commit**

```bash
git add gaia/gaia_ir/strategy.py tests/gaia_ir/test_strategy.py
git commit -m "feat(gaia-ir): enforce strategy scope/prefix, form↔type, and global-steps invariants"
```

---

## Chunk 2: Graphs — Canonicalization Without Contract Validation

### Task 3: Update `graphs.py` with canonicalization, without contract validators

**Files:**
- Modify: `gaia/gaia_ir/graphs.py`
- Test: `tests/gaia_ir/test_graphs.py`

- [ ] **Step 1: Write hash-order-independence test**

Add to `tests/gaia_ir/test_graphs.py`:

```python
def test_hash_independent_of_entity_order(self):
    k1 = Knowledge(id="lcn_1", type="claim", content="A")
    k2 = Knowledge(id="lcn_2", type="claim", content="B")
    s = Strategy(scope="local", type="infer", premises=["lcn_1"], conclusion="lcn_2")

    g1 = LocalCanonicalGraph(knowledges=[k1, k2], strategies=[s])
    g2 = LocalCanonicalGraph(knowledges=[k2, k1], strategies=[s])

    assert g1.ir_hash == g2.ir_hash
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/gaia_ir/test_graphs.py::TestLocalCanonicalGraph::test_hash_independent_of_entity_order -v`
Expected: FAIL (current `_canonical_json` doesn't sort entities)

- [ ] **Step 3: Add canonicalization helpers and update `_canonical_json`**

Add the three canonicalization helpers from PR 257 to `gaia/gaia_ir/graphs.py`:

```python
import json
from typing import Any

def _json_sort_key(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False)

def _canonicalize_knowledge_dump(data: dict[str, Any]) -> dict[str, Any]:
    canonical = dict(data)
    canonical["parameters"] = sorted(canonical.get("parameters", []), key=_json_sort_key)
    if canonical.get("provenance") is not None:
        canonical["provenance"] = sorted(canonical["provenance"], key=_json_sort_key)
    if canonical.get("local_members") is not None:
        canonical["local_members"] = sorted(canonical["local_members"], key=_json_sort_key)
    return canonical

def _canonicalize_operator_dump(data: dict[str, Any]) -> dict[str, Any]:
    canonical = dict(data)
    variables = list(canonical.get("variables", []))
    conclusion = canonical.get("conclusion")
    operator = canonical.get("operator")
    if operator in {"equivalence", "contradiction", "complement", "disjunction"}:
        canonical["variables"] = sorted(variables)
    elif operator == "conjunction" and conclusion is not None:
        premises = sorted(v for v in variables if v != conclusion)
        canonical["variables"] = premises + [conclusion]
    return canonical

def _canonicalize_strategy_dump(data: dict[str, Any]) -> dict[str, Any]:
    canonical = dict(data)
    canonical["premises"] = sorted(canonical.get("premises", []))
    if canonical.get("background") is not None:
        canonical["background"] = sorted(canonical["background"])
    if canonical.get("sub_strategies") is not None:
        canonical["sub_strategies"] = sorted(
            [_canonicalize_strategy_dump(sub) for sub in canonical["sub_strategies"]],
            key=_json_sort_key,
        )
    if canonical.get("formal_expr") is not None:
        formal_expr = dict(canonical["formal_expr"])
        formal_expr["operators"] = sorted(
            [_canonicalize_operator_dump(op) for op in formal_expr.get("operators", [])],
            key=_json_sort_key,
        )
        canonical["formal_expr"] = formal_expr
    return canonical
```

Update `_canonical_json` to sort:

```python
def _canonical_json(
    knowledges: list[Knowledge],
    operators: list[Operator],
    strategies: list[Strategy],
) -> str:
    data = {
        "knowledges": sorted(
            [_canonicalize_knowledge_dump(k.model_dump(mode="json")) for k in knowledges],
            key=_json_sort_key,
        ),
        "operators": sorted(
            [_canonicalize_operator_dump(o.model_dump(mode="json")) for o in operators],
            key=_json_sort_key,
        ),
        "strategies": sorted(
            [_canonicalize_strategy_dump(s.model_dump(mode="json")) for s in strategies],
            key=_json_sort_key,
        ),
    }
    return json.dumps(data, sort_keys=True, ensure_ascii=False)
```

**Do NOT add `_validate_contract` to either graph class.** Graphs remain pure data containers + hash computation.

- [ ] **Step 4: Run all graph tests**

Run: `pytest tests/gaia_ir/test_graphs.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add gaia/gaia_ir/graphs.py tests/gaia_ir/test_graphs.py
git commit -m "feat(gaia-ir): canonical JSON with insertion-order-independent hashing"
```

---

## Chunk 3: Tier 2 — Validator Enhancements

### Task 4: Add knowledge shape rules to `validator.py`

**Files:**
- Modify: `gaia/gaia_ir/validator.py`
- Modify: `tests/gaia_ir/test_validator.py`

- [ ] **Step 1: Write failing tests for knowledge shape rules**

Add to `tests/gaia_ir/test_validator.py` in `TestKnowledgeValidation`:

```python
def test_local_knowledge_must_have_content(self):
    k = Knowledge(id="lcn_a", type=KnowledgeType.CLAIM)
    g = _local_graph(knowledges=[k])
    r = validate_local_graph(g)
    assert not r.valid
    assert any("content" in e for e in r.errors)

def test_local_knowledge_must_not_have_representative_lcn(self):
    from gaia.gaia_ir import LocalCanonicalRef
    k = Knowledge(
        id="lcn_a", type=KnowledgeType.CLAIM, content="test",
        representative_lcn=LocalCanonicalRef(
            local_canonical_id="lcn_x", package_id="pkg", version="1"
        ),
    )
    g = _local_graph(knowledges=[k])
    r = validate_local_graph(g)
    assert not r.valid
    assert any("representative_lcn" in e for e in r.errors)

def test_local_knowledge_must_not_have_local_members(self):
    from gaia.gaia_ir import LocalCanonicalRef
    k = Knowledge(
        id="lcn_a", type=KnowledgeType.CLAIM, content="test",
        local_members=[LocalCanonicalRef(
            local_canonical_id="lcn_x", package_id="pkg", version="1"
        )],
    )
    g = _local_graph(knowledges=[k])
    r = validate_local_graph(g)
    assert not r.valid
    assert any("local_members" in e for e in r.errors)

def test_global_knowledge_must_have_content_or_representative(self):
    k = Knowledge(id="gcn_bad", type=KnowledgeType.CLAIM)
    g = _global_graph(knowledges=[k])
    r = validate_global_graph(g)
    assert not r.valid
    assert any("content or representative_lcn" in e for e in r.errors)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/gaia_ir/test_validator.py::TestKnowledgeValidation -v -x`
Expected: FAIL — the new shape rules aren't in validator.py yet.

- [ ] **Step 3: Add layer-specific knowledge shape validation to validator.py**

Update `_validate_knowledges` in `gaia/gaia_ir/validator.py` to accept a `scope` parameter and enforce layer-specific rules:

After the existing claim content completeness check, add:

```python
# local-layer shape rules
if scope == "local":
    if k.content is None:
        result.error(f"Knowledge '{k.id}': local layer requires content")
    if k.representative_lcn is not None:
        result.error(f"Knowledge '{k.id}': local layer must not set representative_lcn")
    if k.local_members is not None:
        result.error(f"Knowledge '{k.id}': local layer must not set local_members")

# global-layer shape rules
if scope == "global":
    if k.type == KnowledgeType.CLAIM:
        if k.content is None and k.representative_lcn is None:
            # Already checked above, but explicit for global layer
            pass
```

Note: the global claim completeness check (`content or representative_lcn`) already exists in the current `_validate_knowledges`. Just add the local-layer rules.

- [ ] **Step 4: Run all validator tests**

Run: `pytest tests/gaia_ir/test_validator.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add gaia/gaia_ir/validator.py tests/gaia_ir/test_validator.py
git commit -m "feat(gaia-ir): add layer-specific knowledge shape rules to validator"
```

---

### Task 5: Add Operator scope validation to `validator.py`

**Files:**
- Modify: `gaia/gaia_ir/validator.py`
- Modify: `tests/gaia_ir/test_validator.py`

- [ ] **Step 1: Write failing tests for operator scope in graph context**

Add to `tests/gaia_ir/test_validator.py` in `TestOperatorValidation`:

```python
def test_local_graph_rejects_global_scoped_operator(self):
    g = _local_graph(
        knowledges=[_claim("lcn_a"), _claim("lcn_b")],
        operators=[Operator(scope="global", operator="equivalence", variables=["lcn_a", "lcn_b"])],
    )
    r = validate_local_graph(g)
    assert not r.valid
    assert any("scope" in e.lower() for e in r.errors)

def test_global_graph_rejects_local_scoped_operator(self):
    g = _global_graph(
        knowledges=[_claim("gcn_a"), _claim("gcn_b")],
        operators=[Operator(scope="local", operator="equivalence", variables=["gcn_a", "gcn_b"])],
    )
    r = validate_global_graph(g)
    assert not r.valid
    assert any("scope" in e.lower() for e in r.errors)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/gaia_ir/test_validator.py::TestOperatorValidation -v -x`
Expected: FAIL

- [ ] **Step 3: Add operator scope check to `_validate_operators`**

In `gaia/gaia_ir/validator.py`, update `_validate_operators` to accept `scope` and check:

```python
def _validate_operators(
    operators: list[Operator],
    knowledge_lookup: dict[str, Knowledge],
    scope: str,
    result: ValidationResult,
) -> None:
    for op in operators:
        # operator scope must be compatible with graph scope
        if op.scope is not None and op.scope != scope:
            result.error(
                f"Operator '{op.operator_id}': scope '{op.scope}' incompatible "
                f"with {scope} graph"
            )

        # ... rest of existing checks unchanged ...
```

Update all call sites (`validate_local_graph`, `validate_global_graph`) to pass scope:
- `_validate_operators(graph.operators, knowledge_lookup, "local", result)`
- `_validate_operators(graph.operators, knowledge_lookup, "global", result)`

Also update the FormalStrategy recursive call in `_validate_strategy` to pass scope.

- [ ] **Step 4: Run all validator tests**

Run: `pytest tests/gaia_ir/test_validator.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add gaia/gaia_ir/validator.py tests/gaia_ir/test_validator.py
git commit -m "feat(gaia-ir): validate operator scope against graph scope"
```

---

### Task 6: Add Strategy scope validation to `validator.py`

**Files:**
- Modify: `gaia/gaia_ir/validator.py`
- Modify: `tests/gaia_ir/test_validator.py`

- [ ] **Step 1: Write failing tests for strategy scope in graph context**

Add to `tests/gaia_ir/test_validator.py` in `TestStrategyValidation`:

```python
def test_local_graph_rejects_global_scoped_strategy(self):
    g = _local_graph(
        knowledges=[_claim("lcn_a"), _claim("lcn_b")],
        strategies=[Strategy(scope="global", type="infer", premises=["lcn_a"], conclusion="lcn_b")],
    )
    r = validate_local_graph(g)
    assert not r.valid
    assert any("scope" in e.lower() for e in r.errors)

def test_global_graph_rejects_local_scoped_strategy(self):
    g = _global_graph(
        knowledges=[_claim("gcn_a"), _claim("gcn_b")],
        strategies=[Strategy(scope="local", type="infer", premises=["gcn_a"], conclusion="gcn_b")],
    )
    r = validate_global_graph(g)
    assert not r.valid
    assert any("scope" in e.lower() for e in r.errors)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/gaia_ir/test_validator.py::TestStrategyValidation -v -x`
Expected: FAIL

- [ ] **Step 3: Add strategy scope check to `_validate_strategies`**

In `_validate_strategies`, after the existing prefix check, add:

```python
# strategy scope must match graph scope
if s.scope != scope:
    result.error(
        f"Strategy '{s.strategy_id}': scope '{s.scope}' incompatible "
        f"with {scope} graph"
    )
```

- [ ] **Step 4: Run all validator tests**

Run: `pytest tests/gaia_ir/test_validator.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add gaia/gaia_ir/validator.py tests/gaia_ir/test_validator.py
git commit -m "feat(gaia-ir): validate strategy scope against graph scope"
```

---

## Chunk 4: Update `validator.py` hash check + Final Verification

### Task 7: Fix hash consistency check in validator to use canonical JSON

**Files:**
- Modify: `gaia/gaia_ir/validator.py`

The `validate_local_graph` hash check uses `_canonical_json` from graphs.py. After Task 3's canonicalization changes, the validator's hash re-computation must use the same updated `_canonical_json`. Since `validator.py` already imports `_canonical_json` from `graphs.py`, this should work automatically. But verify:

- [ ] **Step 1: Run hash consistency tests**

Run: `pytest tests/gaia_ir/test_validator.py::TestGraphLevelValidation -v`
Expected: ALL PASS (hash computed by graph matches hash recomputed by validator)

- [ ] **Step 2: If hash test fails, update import**

Verify `validator.py` imports `_canonical_json` from `gaia.gaia_ir.graphs` (it already does). No change needed if import is correct.

---

### Task 8: Full test suite verification

- [ ] **Step 1: Run all gaia_ir tests**

Run: `pytest tests/gaia_ir/ -v`
Expected: ALL PASS

- [ ] **Step 2: Run linting**

Run: `ruff check gaia/gaia_ir/ tests/gaia_ir/` and `ruff format --check gaia/gaia_ir/ tests/gaia_ir/`
Expected: No errors

- [ ] **Step 3: Fix any lint issues**

If any, fix and commit.

- [ ] **Step 4: Run full test suite to check nothing else broke**

Run: `pytest tests/ -v --ignore=tests/integration`
Expected: ALL PASS (or only pre-existing failures unrelated to this change)
