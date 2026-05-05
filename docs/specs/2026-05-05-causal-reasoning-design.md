# Minimal Causal Reasoning Design

> **Status:** Replacement proposal for the causal design draft
> **Branch:** `codex/v05-causal-docs-refresh` (off `v0.5`)
> **Target release:** v0.6
> **Date:** 2026-05-06
> **Scope:** Define the smallest causal contract built on v0.5 Claims, formulas,
> Actions, and IR lowering: causal Claims as source of truth, CausalDAG as a
> derived view, and y0 as the first symbolic identification backend.
> **Non-goals:** `mechanism(...)` actions, `is_causal` flags on existing actions,
> causal discovery, DoWhy integration, data-driven effect estimation,
> counterfactuals, and a full CPD family.

---

## 0. Design Summary

The causal layer should be small enough to explain in one sentence:

> `causal(...)` creates a truth-bearing causal Claim; `build_causal_dag(...)`
> projects those causal Claims into a DAG; y0 identifies symbolic do-query
> formulas from that DAG.

Everything else stays in its current layer:

- `infer`, `support`, and `derive` support or attack Claims. They do not create
  causal edges.
- `implies(...)` and ordinary support relations are truth/evidence relations.
  They are not causal mechanisms.
- Gaia BP / FactorGraph remains the probability-computation backend for ordinary
  probabilistic reasoning. A CausalDAG by itself does not compute probabilities.
- DoWhy is intentionally deferred until Gaia has a data-binding and estimator
  contract.

The minimum contract is:

```text
Gaia IR
  Claim A
  Claim B
  Claim C = causal(A, B, prior=0.9)

Derived views
  CausalDAG:
    node: A
    node: B
    edge: A -> B, witnessed_by=C

  FactorGraph:
    ordinary BP lowering of Claims and Actions
```

The CausalDAG is not a new source of truth. It is a typed projection over causal
Claims in Gaia IR.

---

## 1. Current v0.5 Starting Point

v0.5 already has the right foundation:

- `Claim.formula` stores a typed formula AST.
- `Claim.kind == ClaimKind.CAUSAL` marks a Claim whose top-level formula is a
  causal predicate.
- `Causes(cause, effect)` and `causes(cause, effect)` exist in the formula
  layer.
- `causal(cause, effect, prior=...)` exists as public authoring sugar for
  current `Causes(...)` endpoints and returns
  `Claim(formula=Causes(...), kind=ClaimKind.CAUSAL, prior=...)`.
- Formula lowering already emits `metadata.causal = {"cause": ..., "effect": ...}`
  for top-level `Causes(...)` Claims.

The missing piece is not a second causal action system. The missing piece is a
small projection layer that reads these causal Claims as candidate DAG edges.

---

## 2. Public Authoring Surface

### 2.1 Common path: Claim-to-Claim causality

Most users should not need to write formula AST nodes directly:

```python
from gaia.lang import causal, claim, infer

rain = claim("It rains", prior=0.3)
wet = claim("The ground is wet", prior=0.2)

rain_causes_wet = causal(
    rain,
    wet,
    prior=0.9,
    describe="Rain causes the ground to become wet.",
)
```

`causal(rain, wet, ...)` normalizes internally to:

```python
Claim(
    formula=Causes(ClaimAtom(rain), ClaimAtom(wet)),
    kind=ClaimKind.CAUSAL,
    prior=0.9,
)
```

This requires one small v0.6 widening: `Causes` endpoint validation should accept
`Term | ClaimAtom`. The current v0.5 term-only variable path stays valid.

The resulting causal relation is a normal Claim. It can be supported, attacked,
reviewed, imported, exported, and assigned a prior like any other Claim.

```python
field_study = claim("In the field study, rain events precede wet ground events.")

infer(
    field_study,
    hypothesis=rain_causes_wet,
    p_e_given_h=0.8,
    p_e_given_not_h=0.2,
)
```

This `infer(...)` supports the causal Claim. It does not create a separate
causal edge.

### 2.2 Existing path: variable-level causality

The current v0.5 style remains valid:

```python
from gaia.lang import Real, Variable, causal

co2 = Variable(symbol="co2", domain=Real)
temp = Variable(symbol="temp", domain=Real)

co2_causes_temp = causal(
    co2,
    temp,
    prior=0.85,
    describe="Atmospheric CO2 concentration causes mean temperature change.",
)
```

This keeps the existing formula/Variable capability without forcing users into a
new graph API.

### 2.3 Explicit formula path

Advanced users can still write the normalized formula directly:

```python
from gaia.lang import ClaimKind, ClaimAtom, Causes, claim

edge = claim(
    "Rain causes wet ground.",
    formula=Causes(ClaimAtom(rain), ClaimAtom(wet)),
    kind=ClaimKind.CAUSAL,
    prior=0.9,
)
```

The public rule is:

```text
causal(...) is the Pythonic surface.
Causes(...) is the normalized formula representation.
```

### 2.4 What is not added

Do not add:

- `mechanism(...)`
- `cause(...)`
- `is_causal=True` on `infer`, `support`, `derive`, or `implies`
- a separate action type whose only purpose is to create causal edges

The edge exists because there is a causal Claim.

---

## 3. Core Semantics

### 3.1 Three relations that must stay separate

```text
implication:
  If A is true, B should be true in the same world.

infer:
  Evidence E changes belief in hypothesis H.

causation:
  Under intervention do(A=a), the generating process for B changes.
```

Therefore:

- `implies(A, B)` is not a causal edge.
- `infer(evidence=E, hypothesis=H)` is not a causal edge.
- `infer(evidence=E, hypothesis=causal(A, B))` supports the edge Claim.
- `causal(A, B)` is the only authoring surface that contributes an edge to
  CausalDAG.

### 3.2 Prior means belief in the edge, not effect strength

For a causal Claim:

```python
edge = causal(A, B, prior=0.9)
```

`prior=0.9` means:

```text
P("A causes B" is true) = 0.9
```

It does not mean:

```text
P(B | A) = 0.9
P(B | do(A)) = 0.9
```

This distinction is non-negotiable. Edge belief and mechanism strength are
different quantities.

### 3.3 CausalDAG does not compute probabilities

A DAG such as:

```text
Z -> X
Z -> Y
X -> Y
```

can answer structural questions:

- Is the graph acyclic?
- Is a do-query structurally meaningful?
- Which variables are ancestors or descendants?
- Which adjustment sets identify `P(Y | do(X))`?

It cannot answer numeric questions by itself:

- `P(Y=1 | do(X=1)) = ?`
- `ATE(X -> Y) = ?`

Numeric answers require CPDs, observational distributions, Gaia BP beliefs, or
data estimators. The minimal v0.6 causal layer only promises symbolic
identification, not numeric effect estimation.

---

## 4. IR and Metadata Contract

### 4.1 Source of truth

The source of truth is the compiled causal Claim:

```python
{
    "id": "pkg::rain_causes_wet",
    "type": "claim",
    "metadata": {
        "prior": 0.9,
        "formula_atom": {"kind": "causes"},
        "causal": {
            "cause": {"kind": "claim", "qid": "pkg::rain"},
            "effect": {"kind": "claim", "qid": "pkg::wet"},
        },
    },
}
```

The exact metadata shape can preserve the current v0.5 flat form:

```python
metadata["causal"] = {"cause": ..., "effect": ...}
```

No `metadata.causal_mechanism` key is introduced.

### 4.2 Endpoint descriptors

`metadata.causal.cause` and `metadata.causal.effect` describe nodes in the
derived CausalDAG.

Supported in the minimal design:

```python
{"kind": "claim", "qid": "<compiled Claim QID>"}
{"kind": "variable", "symbol": "co2", "domain": "Real", "cnid": "<stable CNID>"}
```

Rules:

- Claim endpoints use QIDs.
- Variable endpoints use stable CNIDs because `Variable` is Lang-only and does
  not enter the IR Knowledge map.
- Cross-package variables use the declaring package when known; otherwise the
  current package namespace is used as a fallback.
- Quantified causal formulas are allowed as Claims, but the minimal DAG builder
  only includes endpoints that can be normalized to concrete QIDs or CNIDs.

### 4.3 Optional CPD metadata

CPD support is not required for symbolic identification. It is optional metadata
for later numeric intervention work:

```python
edge = causal(
    A,
    B,
    prior=0.9,
    cpd=BinaryCPD(
        p_effect_given_cause=0.8,
        p_effect_given_not_cause=0.1,
    ),
)
```

Compiled metadata:

```python
metadata["causal"]["cpd"] = {
    "kind": "binary",
    "p_effect_given_cause": 0.8,
    "p_effect_given_not_cause": 0.1,
}
```

Only one CPD shape is in scope for the minimal spec:

```python
BinaryCPD(p_effect_given_cause: float, p_effect_given_not_cause: float)
```

No noisy-OR, no arbitrary multi-parent CPT, no estimator registry. If an effect
has multiple causal parents and numeric intervention is required, v0.6 may report
that numeric lowering is not implemented for that graph. y0 symbolic
identification can still run because it only needs structure.

---

## 5. CausalDAG Projection

### 5.1 Public API

```python
from gaia.causal import build_causal_dag

dag = build_causal_dag(artifact.graph)
```

Minimal data model:

```python
@dataclass(frozen=True)
class CausalNode:
    id: str                 # QID or CNID
    kind: Literal["claim", "variable"]
    label: str | None = None


@dataclass(frozen=True)
class CausalEdge:
    cause_id: str
    effect_id: str
    witness_claim_qid: str
    belief: float | None = None
    cpd: BinaryCPD | None = None


@dataclass(frozen=True)
class CausalDAG:
    nodes: dict[str, CausalNode]
    edges: tuple[CausalEdge, ...]
```

### 5.2 Projection rule

`build_causal_dag(graph)` scans compiled knowledges and includes a Claim when all
of these are true:

1. The knowledge is a Claim.
2. It has a top-level causal formula marker. In compiled IR this is
   `metadata.formula_atom.kind == "causes"` plus `metadata.causal`; in runtime
   objects it may also be visible as `Claim.kind == ClaimKind.CAUSAL`.
3. `metadata.causal.cause` and `metadata.causal.effect` can be normalized to QID
   or CNID endpoints.
4. The resulting graph remains acyclic.

The edge is:

```text
cause_id -> effect_id
witnessed_by = causal Claim QID
belief = causal Claim prior, if present
```

The default projection is structural: it includes authored causal Claims without
thresholding on prior. Applications can filter low-belief edges before calling
`build_causal_dag`, but the core API does not guess a MAP structure.

### 5.3 Validation failures

Hard errors:

- endpoint cannot be normalized
- duplicate contradictory endpoint descriptors for the same causal Claim
- cycle in the projected CausalDAG
- `do(X)` requested for a node that is not in the CausalDAG

Warnings:

- causal Claim has no prior
- causal Claim has no CPD and user requested numeric intervention
- quantified causal Claim has not been grounded

---

## 6. Symbolic Identification with y0

### 6.1 Gaia-facing API

```python
from gaia.causal import identify_effect

result = identify_effect(
    dag,
    treatment=rain,
    outcome=wet,
)

print(result.expression_latex)
```

Gaia owns the public result type:

```python
@dataclass(frozen=True)
class IdentificationResult:
    treatment_id: str
    outcome_id: str
    identifiable: bool
    backend: Literal["y0"]
    expression_latex: str | None
    expression_text: str | None
    assumptions: tuple[str, ...] = ()
```

y0 is a first-party backend behind this API. Users do not need to construct y0
objects directly.

### 6.2 Backend boundary

Gaia does not store y0 objects in IR. The adapter converts at runtime:

```text
CausalDAG -> y0 graph/expression -> IdentificationResult
```

This keeps Gaia's schema stable and lets future adapters coexist without
rewriting causal Claims.

### 6.3 Why DoWhy is deferred

DoWhy is valuable for empirical workflows:

```text
CausalDAG + dataset -> estimate/refute
```

That requires decisions Gaia should not make in this minimal spec:

- dataset binding
- column naming
- treatment/outcome schema
- estimator selection
- confidence intervals and robustness checks

The minimal v0.6 target is:

```text
CausalDAG -> symbolic estimand
```

That is the y0-shaped problem.

---

## 7. Relationship to BP and `do()`

### 7.1 Minimal v0.6

The first deliverable does not need numeric `do()`:

```text
causal Claims -> CausalDAG -> y0 symbolic identification
```

This is enough to answer:

```text
Is P(Y | do(X)) identifiable from this causal structure?
What expression should be estimated from observational quantities?
```

### 7.2 Later numeric intervention

Numeric intervention requires more than the DAG:

```text
CausalDAG + CPDs or observational distribution + BP/data backend
```

When numeric `do()` is added, the rule should be:

1. Validate the treatment node exists in CausalDAG.
2. Use CausalDAG to identify which causal incoming edge factors to remove.
3. Use CPD metadata or an observational estimand to build a numeric query.
4. Reuse Gaia BP when the query can be represented as a FactorGraph.

This later work must not infer CPDs from causal Claim priors.

---

## 8. Implementation Plan

### D1. Normalize causal authoring

- Keep `causal(cause, effect, ...)` as the primary public API.
- Extend it to accept Claim endpoints by wrapping them in `ClaimAtom`.
- Widen `Causes` endpoint validation to accept `Term | ClaimAtom`.
- Keep Variable/Term endpoints working as they do today.
- Keep explicit `Claim(formula=Causes(...), kind=CAUSAL)` valid.
- Do not add `mechanism(...)` or `is_causal`.

### D2. Compile causal endpoint descriptors

- Preserve the current `metadata.causal = {"cause": ..., "effect": ...}` shape.
- Add descriptor support for ClaimAtom endpoints:

```python
{"kind": "claim", "qid": "..."}
```

- Add stable CNIDs for Variable endpoints:

```python
{"kind": "variable", "symbol": "x", "domain": "Real", "cnid": "..."}
```

### D3. Add `gaia.causal.dag`

- Implement `CausalNode`, `CausalEdge`, `CausalDAG`.
- Implement `build_causal_dag(graph)`.
- Validate acyclicity.
- Expose structural helpers only if needed by y0 adapter.

### D4. Add y0 adapter

- Add `gaia.causal.identify_effect(...)`.
- Add runtime conversion from `CausalDAG` to y0.
- Return Gaia-owned `IdentificationResult`.
- Lazy-import y0 or place it behind a small optional extra.

### D5. Defer numeric intervention

Do not implement full numeric `do()` until after D1-D4 are stable. Add only the
minimal `BinaryCPD` payload if needed to preserve authored parameters.

---

## 9. Open Questions

Only two questions remain open for the minimal spec:

1. **Should y0 be a hard dependency or optional extra?**

   Recommendation: first-party API, lazy-import backend. User experience is
   built-in; Gaia IR does not depend on y0 object types.

2. **Should quantified causal Claims be grounded in v0.6?**

   Recommendation: not in the first causal PR. Store and render quantified
   causal Claims, but require concrete QID/CNID endpoints for CausalDAG
   projection.

Everything else is intentionally out of scope for the minimal release.

---

## 10. Non-Goals Recap

- No `mechanism` action.
- No `is_causal` boolean flag.
- No DoWhy in the first causal release.
- No data-driven estimation.
- No causal discovery.
- No counterfactuals.
- No full CPD taxonomy.
- No attempt to recover causal structure from ordinary `infer` or
  `implies` relations.
