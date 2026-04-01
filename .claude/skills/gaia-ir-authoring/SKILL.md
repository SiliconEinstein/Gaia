---
name: gaia-ir-authoring
description: "Use when constructing a Gaia IR LocalCanonicalGraph from source material — teaches how to build valid knowledge graphs using existing gaia.gaia_ir models, validate them, and run BP inference."
---

# Gaia IR Authoring

Construct valid `LocalCanonicalGraph` instances using the existing data models in `gaia/gaia_ir/`, validate with `validate_local_graph`, and run inference via `gaia/bp/`.

## When to use

- Building **local** Gaia IR graphs for reasoning experiments, tests, or tooling.
- Translating a scientific argument or knowledge structure into Gaia IR.
- Running local BP inference on a hand-built graph.

Do **not** use for: Typst package authoring (`gaia init` / `gaia build`), modifying core IR in `gaia/gaia_ir/` or BP in `gaia/bp/`, review workflows.

## Imports

```python
from gaia.gaia_ir import (
    Knowledge, KnowledgeType, Operator, OperatorType,
    Strategy, StrategyType, LocalCanonicalGraph, make_qid,
)
from gaia.gaia_ir.validator import validate_local_graph
from gaia.bp import lower_local_graph
from gaia.bp.exact import exact_inference
from gaia.bp.bp import BeliefPropagation
```

## Process

### 1. Define identity

Pick `namespace` and `package_name`. All Knowledge IDs use QID format: `{namespace}:{package_name}::{label}`.

```python
NS, PKG = "my_ns", "my_pkg"

def qid(label: str) -> str:
    return make_qid(NS, PKG, label)
```

### 2. Create Knowledge nodes

Three types per `02-gaia-ir.md` §1.2:

| Type | Role | Carries probability |
|------|------|---------------------|
| `claim` | Scientific assertions, hypotheses, observations | Yes (only type with prior + belief) |
| `setting` | Background / frame assumptions | No |
| `question` | Open problems | No |

```python
k1 = Knowledge(id=qid("observation_a"), type="claim", content="描述")
k2 = Knowledge(id=qid("background"), type="setting", content="背景")
k3 = Knowledge(id=qid("open_problem"), type="question", content="问题")
```

**Rules:**
- Labels must be unique within the package (enforced by validator).
- Labels must match `[a-z_][a-z0-9_]*` (lowercase + underscores).
- `content` stores the proposition text (local layer).
- `LocalCanonicalGraph` auto-assigns QIDs for nodes that have `label` but no `id`, but explicit `id=qid(...)` is recommended.

### 3. Add Operators (structural constraints)

Operators encode **deterministic** logical relations between claims. **No probability parameters.** Per `02-gaia-ir.md` §2:

| Operator | Variables | Conclusion | Semantics |
|----------|-----------|------------|-----------|
| `implication` | `[A]` | `B` | A=1 → B=1 |
| `conjunction` | `[A₁,...,Aₖ]` (≥2) | `M` | M = A₁ ∧ ... ∧ Aₖ |
| `disjunction` | `[A₁,...,Aₖ]` (≥2) | helper | ¬(all=0) |
| `equivalence` | `[A, B]` | helper | A=B |
| `contradiction` | `[A, B]` | helper | ¬(A=1 ∧ B=1) |
| `complement` | `[A, B]` | helper | A≠B (XOR) |

**Top-level operators MUST have `operator_id` (prefix `lco_`) and `scope="local"`** — the validator rejects them otherwise:

```python
contra_helper = Knowledge(
    id=qid("deflection_contradiction_h"), type="claim",
    content="GR与牛顿预测矛盾",
    metadata={
        "helper_kind": "contradiction_result",
        "helper_visibility": "top_level",
        "canonical_name": "not_both_true(gr_deflection,soldner_deflection)",
        "generated": True,
        "generated_kind": "helper_claim",
    },
)
contra_op = Operator(
    operator_id="lco_001", scope="local",
    operator="contradiction",
    variables=[qid("gr_deflection"), qid("soldner_deflection")],
    conclusion=contra_helper.id,
)
```

**Helper claim metadata** per `04-helper-claims.md` §4–§5:

| Field | Value |
|-------|-------|
| `helper_kind` | `conjunction_result` / `disjunction_result` / `equivalence_result` / `contradiction_result` / `complement_result` |
| `helper_visibility` | `top_level` (for graph-level operators) or `formal_internal` (inside FormalExpr) |
| `canonical_name` | Stable function-style name: `not_both_true(A,B)`, `same_truth(A,B)`, `all_true(A,B)`, `any_true(A,B,...)`, `opposite_truth(A,B)` |

**Key invariant:** `conclusion` must NOT appear in `variables` — variables are inputs only.

### 4. Add Strategies (reasoning declarations)

Strategies carry **all probability** — per `02-gaia-ir.md` §3. Premises must reference `claim` Knowledge IDs.

| Type | Use | Parameters |
|------|-----|------------|
| `noisy_and` | Premises jointly support conclusion | 1 float (strength p) |
| `infer` | General CPT | 2^k floats |
| `deduction` | Deterministic derivation | None (auto-formalized at lowering) |
| `abduction` | Observation → hypothesis | None (auto-formalized) |
| `analogy` | 2 premises → target | None |
| `extrapolation` | 2 premises → target | None |
| `elimination` | `[exhaustiveness, cand₁, ev₁, ...]` → conclusion | None |
| `case_analysis` | `[exhaustiveness, case₁, sup₁, ...]` → conclusion | None |
| `mathematical_induction` | 2 premises → law | None |

```python
s = Strategy(
    scope="local", type="noisy_and",
    premises=[qid("premise_a"), qid("premise_b")],
    conclusion=qid("conclusion_c"),
)
```

**Named strategies** (`deduction`, `abduction`, etc.) are stored as leaf `Strategy` and **auto-formalized** by `lower_local_graph` into `FormalStrategy` with generated intermediate claims — you do NOT need to build `FormalExpr` by hand.

`setting` and `question` can appear in `background` but **not** in `premises` (validator rejects non-claim premises).

### 5. Assemble the graph

```python
graph = LocalCanonicalGraph(
    namespace=NS,
    package_name=PKG,
    knowledges=[k1, k2, ...],
    operators=[op1, ...],       # may be empty
    strategies=[s1, s2, ...],
)
```

`ir_hash` is auto-computed (SHA-256 of canonical JSON).

### 6. Validate

```python
from gaia.gaia_ir.validator import validate_local_graph

result = validate_local_graph(graph)
if not result.valid:
    for err in result.errors:
        print(f"ERROR: {err}")
    raise SystemExit(1)
```

`validate_local_graph` checks (~80 rules per `08-validation.md`):
- QID format, label uniqueness, type constraints
- Operator variable/conclusion references exist and are claims
- Strategy premises are claims, conclusion exists
- No cycles in operator dependency graph
- `ir_hash` consistency (if pre-set)

### 7. Lower and run inference

```python
from gaia.bp import lower_local_graph
from gaia.bp.exact import exact_inference

fg = lower_local_graph(
    graph,
    node_priors={"ns:pkg::label": 0.9, ...},            # claim priors
    strategy_conditional_params={s.strategy_id: [0.85]}, # noisy_and: 1 param
)

beliefs, _ = exact_inference(fg)
for node, belief in sorted(beliefs.items()):
    print(f"  {node}: {belief:.4f}")
```

For loopy BP (larger graphs):

```python
from gaia.bp.bp import BeliefPropagation

bp = BeliefPropagation(damping=0.5, max_iterations=100)
result = bp.run(fg)
assert result.diagnostics.converged
beliefs = result.beliefs
```

## Complete example — Galileo coarse

```python
from gaia.gaia_ir import Knowledge, Strategy, LocalCanonicalGraph, make_qid
from gaia.gaia_ir.validator import validate_local_graph
from gaia.bp import lower_local_graph
from gaia.bp.exact import exact_inference

NS, PKG = "reg", "galileo"
def qid(label): return make_qid(NS, PKG, label)
def claim(label, content): return Knowledge(id=qid(label), type="claim", content=content)

tied = claim("tied_balls_contradiction", "绑球矛盾")
air  = claim("air_resistance_is_confound", "介质阻力是混淆因素")
inc  = claim("inclined_plane_observation", "斜面实验")
venv = claim("vacuum_env", "真空环境设定")
pred = claim("vacuum_prediction", "真空中等速下落")

s = Strategy(
    scope="local", type="noisy_and",
    premises=[tied.id, air.id, inc.id, venv.id],
    conclusion=pred.id,
)

graph = LocalCanonicalGraph(
    namespace=NS, package_name=PKG,
    knowledges=[tied, air, inc, venv, pred],
    strategies=[s],
)

result = validate_local_graph(graph)
assert result.valid, result.errors

fg = lower_local_graph(graph, node_priors={
    tied.id: 0.9, air.id: 0.85, inc.id: 0.95, venv.id: 0.99,
}, strategy_conditional_params={s.strategy_id: [0.9]})

beliefs, _ = exact_inference(fg)
assert beliefs[pred.id] > 0.6
```

## Anti-patterns

- **Omitting `operator_id` / `scope` on top-level Operators** — validator rejects them. Use `operator_id="lco_001"` (or any `lco_` prefix), `scope="local"`.
- **Using `setting` or `question` as Strategy premise** — must be `claim`.
- **Putting conclusion in variables** — variables are inputs only; conclusion is separate.
- **Forgetting helper claims for relation operators** — `contradiction`, `equivalence`, `complement`, `disjunction` need a conclusion claim node in the graph.
- **Manually building FormalExpr for named strategies** — `lower_local_graph` auto-formalizes `deduction`, `abduction`, etc. Just use leaf `Strategy`.
- **Skipping validation** — always call `validate_local_graph` before lowering.

## Spec pointers

- `docs/foundations/gaia-ir/02-gaia-ir.md` — Knowledge / Operator / Strategy schemas and invariants
- `docs/foundations/gaia-ir/04-helper-claims.md` — Helper claim metadata conventions
- `docs/foundations/gaia-ir/08-validation.md` — Full validation rule set
- `docs/foundations/gaia-ir/07-lowering.md` — Lowering contract (IR → FactorGraph)
- `tests/test_science_examples.py` — Galileo / Newton / Einstein end-to-end references
