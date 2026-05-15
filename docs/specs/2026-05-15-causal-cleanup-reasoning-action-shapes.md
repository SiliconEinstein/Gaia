# Causal Marker Cleanup and ReasoningAction Shape Refactor

**Status:** Design proposal for v0.5 follow-up
**Date:** 2026-05-15
**Branch:** off `v0.5`
**Scope:** Delete the current Gaia Lang causal marker surface and refactor the runtime reasoning hierarchy around graph shape.
**Refines:** `docs/specs/2026-05-15-gaia-graph-scaffold-reasoning-design.md`
**Non-goals:** No causal graph implementation, no do-calculus, no BP lowering changes, no public DSL return-value migration, and no persistent IR schema redesign.

## 1. Why This Change

The current runtime hierarchy is organized by implementation flavor:

```text
Action
  Support
    Derive / Observe / Compute
  Structural
    Equal / Contradict / Exclusive / Decompose
  Probabilistic
    Infer / Associate
  Compose
```

That shape is hard to explain because it mixes two different axes:

- graph shape: directed support-like edges vs relation-like edges;
- lowering/semantics: hard, empirical, computed, probabilistic.

`Infer` is probabilistic, but graph-shaped like directed reasoning:

```text
evidence + conditions -> hypothesis
```

`Associate` is probabilistic, but graph-shaped like a relation:

```text
claim A <-> claim B association
```

The inheritance tree should follow graph shape. Whether something is hard,
empirical, computed, or probabilistic should be handled by the concrete class
and lowering logic, not by the top-level family.

The causal marker surface has a related problem. Current code exposes
`Causes`, `causes(...)`, `causal(...)`, and `ClaimKind.CAUSAL`, but these are
only marker claims/formulas. They do not provide a formal GaiaGraph record,
interventional semantics, or causal lowering. Keeping them in the active DSL
suggests Gaia has causal support that it does not yet have. The cleaner v0.5
move is to delete this marker surface until causal returns as a real formal
graph record, for example a future `CausalEdge`.

## 2. Current Code Facts

The active Python causal surface is limited to:

| Surface | Current location | Current behavior |
|---|---|---|
| `Causes` formula node | `gaia/lang/formula/predicate.py` | Typed formula marker with `cause` and `effect` terms. |
| `causes(...)` helper | `gaia/lang/dsl/formula.py` | Constructs a `Causes` formula. |
| `causal(...)` sugar | `gaia/lang/dsl/sugar.py` | Creates a `Claim` with `formula=Causes(...)` and `kind=ClaimKind.CAUSAL`. |
| `ClaimKind.CAUSAL` | `gaia/lang/runtime/knowledge.py` | Classifies a top-level causal marker claim. |
| formula lowering metadata | `gaia/lang/compiler/lower_formula.py` | Records metadata such as `formula_atom.kind = "causes"` and `metadata["causal"]`. |
| public exports | `gaia/lang/__init__.py`, `gaia/lang/dsl/__init__.py`, `gaia/lang/formula/__init__.py` | Expose causal marker names. |

There is no active `gaia/causal` runtime package in the current tree. The
`gaia/trace/*` "Causal Health" text is trace-review rubric content, not Gaia
Lang causal DSL code, and is out of scope for this cleanup.

## 3. Target Runtime Hierarchy

Use graph shape as the primary hierarchy:

```text
ReasoningAction
  Directed
    Derive
    Observe
    Compute
    Infer
    Generalize   # future

  Relation
    Equal
    Contradict
    Exclusive
    Associate

  Decompose

  Compose
```

`ReasoningAction` is the code-facing base name. User-facing prose may shorten
it to `Reasoning`, matching the GaiaGraph design spec.

### 3.1 Directed

`Directed` means a graph-shaped step where source information points toward a
target claim or helper claim.

Current classes:

| Class | Directed shape | Existing fields remain |
|---|---|---|
| `Derive` | premises imply conclusion | `given`, `conclusion` |
| `Observe` | observation context points to observed claim/event | `given`, `conclusion` |
| `Compute` | inputs and callable produce result claim | `given`, `conclusion`, `fn`, `code_hash` |
| `Infer` | evidence/conditions update hypothesis | `evidence`, `given`, `hypothesis`, likelihood fields |

`Infer` belongs here even though it is probabilistic. Probability is its
lowering mode, not its top-level graph shape.

Future `Generalize` also belongs here:

```python
generalize(instances=[a, b, c], conclusion=universal)
```

### 3.2 Relation

`Relation` means a graph-shaped step whose main payload is a relation among
claims.

Current classes:

| Class | Relation shape | Existing fields remain |
|---|---|---|
| `Equal` | claims are equivalent | `a`, `b`, `helper` |
| `Contradict` | claims cannot both hold | `a`, `b`, `helper` |
| `Exclusive` | alternatives are mutually exclusive | `a`, `b`, `helper` |
| `Associate` | claims are probabilistically associated | `a`, `b`, probability fields, `helper` |

`Associate` belongs here even though it is probabilistic. It is relation-shaped
like `Equal`, `Contradict`, and `Exclusive`.

### 3.3 Decompose

`Decompose` stays its own direct `ReasoningAction` child. It is not a normal
directed step and not a simple relation:

```text
whole Claim <-> formula(parts)
```

The current parts boundary is correct and should be preserved:

```python
whole: Claim
parts: tuple[Claim, ...]
formula: Formula
```

Rules to keep:

- every `part` is a `Claim`;
- `parts` are unique;
- `formula` only references listed `parts`;
- `formula` does not reference `whole`;
- decomposition cycles are rejected.

### 3.4 Compose

`Compose` is a compound `ReasoningAction`. It groups child reasoning records
into a reusable workflow.

The first migration keeps existing fields such as `inputs`, `actions`, and
`conclusion`. A later cleanup may rename `actions` to `reasoning`, but this
spec does not require that change.

## 4. Minimal Code Migration

Do not change DSL return values, compiler IR output, BP lowering, or existing
field names in the first implementation.

Target class sketch:

```python
@dataclass
class ReasoningAction(GaiaGraph):
    label: str | None = None
    rationale: str = ""
    background: list[Knowledge] = field(default_factory=list)
    warrants: list[Claim] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Directed(ReasoningAction):
    """Graph shape: sources point toward a target claim/helper."""


@dataclass
class Relation(ReasoningAction):
    """Graph shape: claims participate in a relation."""


@dataclass
class Derive(Directed): ...
@dataclass
class Observe(Directed): ...
@dataclass
class Compute(Directed): ...
@dataclass
class Infer(Directed): ...

@dataclass
class Equal(Relation): ...
@dataclass
class Contradict(Relation): ...
@dataclass
class Exclusive(Relation): ...
@dataclass
class Associate(Relation): ...

@dataclass
class Decompose(ReasoningAction): ...

@dataclass
class Compose(ReasoningAction): ...
```

`Support`, `Structural`, and `Probabilistic` should stop being the public or
long-term runtime families. If a short compatibility bridge is needed inside a
single PR, it must not be used for new dispatch logic and should be removed
before the v0.5 surface is frozen.

### 4.1 Dispatch rule

Do not replace all existing compiler checks with broad `isinstance(action,
Directed)` or `isinstance(action, Relation)` checks. Shape is not lowering.

Examples:

- `Derive / Observe / Compute` still lower through the support-style strategy
  path.
- `Infer` still lowers through its likelihood/probabilistic path.
- `Equal / Contradict / Exclusive` still lower through hard relation operators.
- `Associate` still lowers through association/probabilistic relation logic.
- `Decompose` still lowers through decomposition-specific formula helper and
  equivalence operator logic.

Use concrete classes or explicit helper predicates when dispatching lowering:

```python
is_support_like = isinstance(action, Derive | Observe | Compute)
is_hard_relation = isinstance(action, Equal | Contradict | Exclusive)
```

`Directed` and `Relation` are for the runtime mental model, role projection,
graph display, and future extension placement. They are not a substitute for
lowering-specific dispatch.

### 4.2 Bayes opt-in actions

Bayes actions should not keep importing `Probabilistic` after this refactor.
They should choose the smallest existing shape:

- `PredictiveModel`: `Directed` if treated as a model declaration from a
  hypothesis to a model-helper claim; otherwise direct `ReasoningAction` until
  a more precise model-declaration shape exists.
- `Likelihood`: `Directed`, because data/model inputs point toward a
  model-preference helper claim.

Do not add a Bayes-specific top-level family as part of this refactor.

## 5. Causal Marker Code Deletion

Delete the current marker-only causal surface from active Gaia Lang.

Remove:

- `Causes` from `gaia/lang/formula/predicate.py`;
- `causes(...)` from `gaia/lang/dsl/formula.py`;
- `causal(...)` and `_causal_content(...)` from `gaia/lang/dsl/sugar.py`;
- `ClaimKind.CAUSAL` from `gaia/lang/runtime/knowledge.py`;
- `Causes` imports/exports from:
  - `gaia/lang/formula/__init__.py`;
  - `gaia/lang/dsl/__init__.py`;
  - `gaia/lang/__init__.py`;
- `Causes` lowering branches and `metadata["causal"]` emission from
  `gaia/lang/compiler/lower_formula.py`;
- tests that assert the marker surface exists.

Update or delete tests:

- `tests/gaia/lang/formula/test_predicate.py::test_causes_predicate`;
- `tests/gaia/lang/test_formula_lowering.py::test_top_level_causes_formula_records_causal_marker_without_implication`;
- `tests/gaia/lang/test_formula_sugar.py::test_causal_sugar_constructs_causal_claim_and_compiles_marker`;
- `tests/gaia/lang/test_milestone_a_smoke.py::test_causal_claim`;
- public-surface tests that include `Causes`, `causes`, `causal`, or
  `ClaimKind.CAUSAL`.

Do not delete:

- `gaia/trace/*` causal-health review text;
- historical design specs under `docs/specs/2026-05-06-causal-*`;
- prose mentions in archived or excluded design records.

Those are not executable Gaia Lang causal marker code. Future docs cleanup can
mark old causal specs as superseded, but that is separate from this code
cleanup.

## 6. Future Causal Direction

When causal returns, it should come back as a formal GaiaGraph record, not as a
claim formula marker.

Sketch:

```python
edge = causes(exposure, outcome, mechanism=..., label="exposure_causes_outcome")
```

Potential future class:

```text
GaiaGraph
  CausalEdge
```

`CausalEdge` should be materializable from scaffold:

```python
rel = candidate_relation(claims=[exposure, outcome], pattern=None)
edge = causes(exposure, outcome, label="exposure_causes_outcome")
materialize(rel, by=edge)
```

This future edge is not necessarily `ReasoningAction`. It may have its own
interventional semantics and later projections into causal graphs, BP factors,
or do-calculus engines.

## 7. Implementation Checklist

Runtime hierarchy:

- Add `ReasoningAction`, `Directed`, and `Relation`.
- Move `Derive`, `Observe`, `Compute`, and `Infer` under `Directed`.
- Move `Equal`, `Contradict`, `Exclusive`, and `Associate` under `Relation`.
- Move `Decompose` and `Compose` directly under `ReasoningAction`.
- Remove or de-publicize `Support`, `Structural`, and `Probabilistic`.
- Keep fields and DSL return values unchanged.

Compiler and roles:

- Update imports from old families to new families or concrete classes.
- Keep support-style lowering limited to `Derive / Observe / Compute`.
- Keep infer lowering separate from support-style lowering.
- Keep hard relation lowering limited to `Equal / Contradict / Exclusive`.
- Keep associate lowering separate from hard relation lowering.
- Keep decompose lowering specific to `Decompose`.
- Update role projection tests to assert shape membership instead of old
  `Support / Structural / Probabilistic` membership.

Causal deletion:

- Remove the causal marker formula and sugar code listed in §5.
- Remove causal marker exports.
- Remove causal marker lowering metadata.
- Remove/update causal marker tests.
- Leave trace causal-health text and historical causal specs alone.

## 8. Test Plan

Minimum tests:

- `issubclass(Derive, Directed)`.
- `issubclass(Observe, Directed)`.
- `issubclass(Compute, Directed)`.
- `issubclass(Infer, Directed)`.
- `issubclass(Equal, Relation)`.
- `issubclass(Contradict, Relation)`.
- `issubclass(Exclusive, Relation)`.
- `issubclass(Associate, Relation)`.
- `issubclass(Decompose, ReasoningAction)` and not `issubclass(Decompose, Relation)`.
- `issubclass(Compose, ReasoningAction)`.
- `Decompose.parts` remains `tuple[Claim, ...]` and non-Claim parts still fail.
- Causal marker names are no longer exported from `gaia.lang`.
- A formula with `Causes(...)` can no longer be constructed through public DSL.
- Existing compile/lower tests for derive, observe, compute, infer, associate,
  equal, contradict, exclusive, decompose, and compose still pass.
- Bayes likelihood tests still pass after removing `Probabilistic`.

## 9. Validation

Run targeted tests first:

```bash
python -m pytest \
  tests/gaia/lang/test_action_hierarchy.py \
  tests/gaia/lang/test_decompose.py \
  tests/gaia/lang/test_formula_sugar.py \
  tests/gaia/lang/test_formula_lowering.py \
  tests/gaia/lang/bayes/test_runtime_and_lowering.py \
  -q
```

Then run the broader language and CLI checks touched by dispatch changes:

```bash
python -m pytest tests/gaia/lang tests/cli/test_compile.py -q
```

Finally run documentation/format checks:

```bash
git diff --check
uv run --extra docs mkdocs build --strict
```
