# Minimal Causal Mechanism Design

> **Status:** Replacement proposal for the causal design draft
> **Branch:** `codex/v05-causal-docs-refresh` (off `v0.5`)
> **Target release:** v0.6 design discussion
> **Date:** 2026-05-06
> **Scope:** Promote causal mechanisms to a first-class Gaia `Knowledge` type,
> project those mechanism nodes into `CausalDAG`, and use y0 as the first
> symbolic identification backend.
> **Non-goals:** Encoding mechanisms as `Claim(kind=CAUSAL)`, `is_causal`
> flags on existing actions, DoWhy integration, causal discovery, data-driven
> effect estimation, counterfactuals, and a full CPD family.

---

## 0. Core Decision

The causal layer should not model a mechanism as a Claim plus metadata. A
mechanism is a piece of world structure:

```text
X causes Y
Y is generated from its causal parents
```

That is not the same kind of object as a proposition, and it is not a reasoning
step. Therefore v0.6 should introduce:

```python
CausalMechanism(Knowledge)
```

The minimal contract becomes:

```text
Gaia IR
  Claim A
  Claim B
  CausalMechanism M = mechanism(A, B)

Derived views
  CausalDAG:
    node: A
    node: B
    edge: A -> B, source=M

  FactorGraph:
    ordinary BP lowering of Claims and Actions
    later: causal factors lowered from CausalMechanism nodes when CPDs exist
```

The CausalDAG is a typed projection over `CausalMechanism` Knowledge nodes. It is
not built from causal Claim metadata, and it is not a new source of truth.

---

## 1. First-Principles Semantics

Gaia needs three different object kinds:

| Kind | Meaning | Examples |
|---|---|---|
| `Claim` | A truth-bearing proposition | "It is raining"; "the field study is reliable" |
| `Action` | A reasoning/review step connecting knowledge | `infer`, `derive`, `support`, `decompose` |
| `CausalMechanism` | A structural causal relation in the modeled world | "rain causes wet ground"; "CO2 drives temperature" |

This keeps three relations separate:

```text
implication:
  If A is true, B should be true in the same world.

infer:
  Evidence E changes belief in hypothesis H.

causation:
  Under intervention do(A=a), the generating process for B changes.
```

Consequences:

- `implies(A, B)` is not a causal edge.
- `infer(evidence=E, hypothesis=H)` is not a causal edge.
- `CausalMechanism(A, B)` is the object that contributes edge `A -> B` to
  `CausalDAG`.
- Claims and Actions may support, challenge, justify, review, or decompose the
  evidence for a mechanism, but they are not the mechanism itself.

---

## 2. Why Not `Claim(kind=CAUSAL)` as the Edge

v0.5 introduced `Causes(X, Y)` as a formula marker inside a Claim. That remains
useful for natural-language propositions, migration, and compatibility, but it
should not be the long-term source of causal structure.

The failure mode is semantic drift:

```python
edge = causal(A, B, prior=0.9)
```

If `edge` is a Claim, then `prior=0.9` means:

```text
P("A causes B" is true) = 0.9
```

But a causal mechanism needs different fields:

```text
source endpoint
target endpoint
optional structural parameters / CPD
review state or support/challenge actions
```

Reusing `Claim.prior` as an "edge existence prior" makes Gaia explain away a
type mismatch with documentation. The minimal design avoids that mismatch:

- `Claim.prior` stays a proposition prior.
- `CausalMechanism` has no `prior` / `exists_prior` field.
- Mechanism status is handled by causal review/support/challenge actions and
  package review policy.
- CPDs, when present, belong to the mechanism node.

This is closer to Pearl's SCM split between variables and structural functions:
the mechanism is part of the modeled world's structure, not just a proposition
about the world.

---

## 3. Public Authoring Surface

### 3.1 Primary API

Use `mechanism(...)` as the Pythonic factory for a `CausalMechanism` Knowledge
node:

```python
from gaia.lang import claim, mechanism

rain = claim("It rains", prior=0.3)
wet = claim("The ground is wet", prior=0.2)

rain_wets_ground = mechanism(
    rain,
    wet,
    label="rain_wets_ground",
    describe="Rain is a causal mechanism for wet ground.",
)
```

`mechanism(...)` returns `CausalMechanism`, not `Claim` and not `Action`.

### 3.2 Variable endpoint path

Mechanisms may also point at formula Variables, preserving the useful part of
the current v0.5 `Causes(...)` work:

```python
from gaia.lang import Real, Variable, mechanism

co2 = Variable(symbol="co2", domain=Real)
temp = Variable(symbol="temp", domain=Real)

co2_drives_temp = mechanism(
    co2,
    temp,
    label="co2_drives_temp",
)
```

Claim endpoints compile to QIDs. Variable endpoints compile to stable CNIDs
because `Variable` is Lang-only and does not enter the IR Knowledge map.

### 3.3 Optional CPD

The first symbolic causal release does not need CPDs. CPDs are only needed for
later numeric `do()` or SCM simulation.

If preserved in v0.6, support exactly one minimal CPD type:

```python
from gaia.lang import BinaryCPD, mechanism

m = mechanism(
    rain,
    wet,
    cpd=BinaryCPD(
        p_effect_given_cause=0.8,
        p_effect_given_not_cause=0.1,
    ),
)
```

The CPD is a structural parameter of the mechanism. It is not a Claim prior, not
an Action score, and not Bayes evidence.

Out of scope for the first release:

- noisy-OR
- arbitrary multi-parent CPT authoring
- learned CPDs
- stochastic/policy interventions

### 3.4 Causal evidence and review actions

Because `CausalMechanism` has no `exists_prior`, Gaia needs actions that record
why a mechanism should be trusted or challenged. The minimal design can start
with qualitative actions:

```python
from gaia.lang import support_mechanism, challenge_mechanism

study = claim("Rain events reliably precede wet ground in the field study.")

support_mechanism(
    [study],
    rain_wets_ground,
    reason="Temporal order and intervention evidence support the mechanism.",
)
```

These actions do not create DAG edges. They explain and review an existing
mechanism node. A registry/review policy can later decide whether a mechanism is
accepted for a published package, but the mechanism object itself does not store
probabilistic existence belief.

For v0.6, `build_causal_dag(...)` uses authored mechanisms by default. A stricter
review-gated policy can be added after Gaia's review manifest has an explicit
mechanism target status.

### 3.5 Compatibility with `causal(...)` and `Causes(...)`

Existing v0.5 APIs should not disappear abruptly:

- `Causes(...)` remains a formula predicate.
- `causal(...)` may remain a compatibility helper that creates a causal Claim.
- Causal Claims are not the canonical source for new CausalDAG edges.

Migration rule:

```text
New packages:
  use mechanism(...)

Old packages:
  compile existing Claim(kind=CAUSAL, formula=Causes(...)) as legacy causal
  propositions; optionally migrate them into CausalMechanism nodes.
```

This keeps old packages readable while preventing the new causal layer from
depending on Claim metadata as its primary structure.

---

## 4. Runtime and IR Contract

### 4.1 Runtime object

Minimal runtime shape:

```python
CausalEndpoint = Claim | Variable


@dataclass(init=False, eq=False)
class CausalMechanism(Knowledge):
    cause: CausalEndpoint
    effect: CausalEndpoint
    cpd: BinaryCPD | None = None
```

Rules:

- It subclasses `Knowledge`, not `Claim`.
- It cannot carry `prior`.
- It does not participate in BP as a Boolean variable by default.
- Its endpoints are typed references to Claims or Variables. They are not
  arbitrary `Knowledge` nodes; `Note`, `Composition`, and other non-causal-node
  objects are rejected.
- `Variable` happens to subclass runtime `Knowledge`, but it is Lang-only and
  compiles to a CNID endpoint rather than an IR Knowledge QID. The explicit
  `CausalEndpoint` alias keeps that distinction visible.
- Its `metadata` may carry display/provenance information, but not causal edge
  identity; the object itself is the edge identity.

### 4.2 IR knowledge type

Add a first-class IR type:

```python
class KnowledgeType(StrEnum):
    CLAIM = "claim"
    NOTE = "note"
    COMPOSITION = "composition"
    CAUSAL_MECHANISM = "causal_mechanism"
```

Minimal serialized shape:

```python
{
    "id": "pkg::rain_wets_ground",
    "type": "causal_mechanism",
    "content": "Rain is a causal mechanism for wet ground.",
    "metadata": {
        "cause": {"kind": "claim", "qid": "pkg::rain"},
        "effect": {"kind": "claim", "qid": "pkg::wet"},
        "cpd": null,
    },
}
```

Validation:

- `metadata.prior` is invalid for `causal_mechanism`.
- `cause` and `effect` must normalize to QID or CNID endpoints.
- If `cpd` is present, its values must satisfy the normal Cromwell bounds.

### 4.3 Endpoint descriptors

Supported endpoint descriptors:

```python
{"kind": "claim", "qid": "<compiled Claim QID>"}
{"kind": "variable", "symbol": "co2", "domain": "Real", "cnid": "<stable CNID>"}
```

Rules:

- Claim endpoints use QIDs.
- Variable endpoints use stable CNIDs.
- Cross-package variables use the declaring package when known; otherwise the
  using package namespace is the fallback.
- Quantified mechanisms are out of scope for the first release.

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
    id: str
    kind: Literal["claim", "variable"]
    label: str | None = None


@dataclass(frozen=True)
class CausalEdge:
    cause_id: str
    effect_id: str
    mechanism_qid: str
    cpd: BinaryCPD | None = None


@dataclass(frozen=True)
class CausalDAG:
    nodes: dict[str, CausalNode]
    edges: tuple[CausalEdge, ...]
```

No `belief` field appears on `CausalEdge`. Belief/review status belongs to
actions or review manifests, not the structural edge.

### 5.2 Projection rule

`build_causal_dag(graph)` scans compiled knowledges and includes a node when:

1. `knowledge.type == "causal_mechanism"`.
2. Its cause/effect descriptors normalize to QID or CNID endpoints.
3. The resulting graph remains acyclic.

The edge is:

```text
cause_id -> effect_id
mechanism_qid = CausalMechanism QID
cpd = mechanism.cpd, if present
```

The default projection is structural: it includes authored mechanisms. Review
gating can be added later as a policy layer:

```python
build_causal_dag(graph, review_manifest=manifest, policy="accepted")
```

That policy is not part of the minimal implementation.

### 5.3 Validation failures

Hard errors:

- endpoint cannot be normalized
- cycle in the projected CausalDAG
- duplicate mechanism labels/QIDs
- `do(X)` requested for a node that is not in the CausalDAG

Warnings:

- mechanism has no CPD and user requested numeric intervention
- legacy causal Claim was found but no migrated `CausalMechanism` exists
- causal support/challenge actions target an unknown mechanism

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
rewriting mechanism Knowledge nodes.

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

## 7. Relationship to BP and Numeric `do()`

### 7.1 Minimal v0.6

The first deliverable does not need numeric `do()`:

```text
CausalMechanism Knowledge -> CausalDAG -> y0 symbolic identification
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

When numeric `do()` is added:

1. Validate the treatment node exists in CausalDAG.
2. Lower CPD-bearing `CausalMechanism` nodes into causal factors.
3. Record factor source as `source_type="causal_mechanism"` and
   `source_id=<mechanism_qid>`.
4. `mutilate()` removes factors sourced from incoming mechanisms to the
   intervened node.
5. Reuse Gaia BP when the resulting query is representable as a FactorGraph.

This does not require a generic `Factor.metadata["modality"] = "causal"` tag.
The factor's source type is the mechanism Knowledge type.

---

## 8. Implementation Plan

### D0. Gaia IR design discussion

This proposal changes the IR schema. It should not be smuggled in as a docs-only
cleanup. Open an explicit design discussion before implementation:

```text
Promote causal mechanisms to first-class Knowledge?
```

The discussion should cover:

- `KnowledgeType.CAUSAL_MECHANISM`
- runtime `CausalMechanism`
- storage/index impact
- renderer/review impact
- migration from v0.5 `causal()` Claims

### D1. Runtime and DSL

- Add runtime `CausalMechanism(Knowledge)`.
- Add a narrow `CausalEndpoint = Claim | Variable` contract; do not accept
  arbitrary `Knowledge`.
- Add `mechanism(cause, effect, *, cpd=None, label=None, describe=None)`.
- Ensure `mechanism(...)` returns Knowledge, not Claim and not Action.
- Keep `causal(...)` as compatibility Claim helper or deprecate it after a
  migration period.
- Add minimal `BinaryCPD` only if numeric parameters must be preserved.

### D2. IR lowering

- Add `KnowledgeType.CAUSAL_MECHANISM`.
- Compile runtime `CausalMechanism` into an IR Knowledge node.
- Normalize endpoint descriptors to QID/CNID.
- Reject `metadata.prior` on mechanism Knowledge.
- Preserve legacy causal Claim metadata for migration and rendering, but do not
  use it as the canonical DAG source.

### D3. Causal actions/review hooks

- Add minimal mechanism-targeted actions, such as `support_mechanism(...)` and
  `challenge_mechanism(...)`, or extend review manifests to target mechanism
  QIDs directly.
- Do not make these actions create edges.
- Use them only for justification, review, and future accepted/rejected policy.

### D4. CausalDAG

- Implement `CausalNode`, `CausalEdge`, `CausalDAG`.
- Implement `build_causal_dag(graph)` over `KnowledgeType.CAUSAL_MECHANISM`.
- Validate acyclicity and endpoint normalization.

### D5. y0 adapter

- Add `gaia.causal.identify_effect(...)`.
- Convert `CausalDAG` to y0 at runtime.
- Return Gaia-owned `IdentificationResult`.
- Lazy-import y0 or place it behind a small optional extra.

### D6. Defer numeric intervention

Do not implement full numeric `do()` until mechanism Knowledge, DAG projection,
and y0 identification are stable.

---

## 9. Open Questions

1. **What is the exact action/review surface for mechanism status?**

   Recommendation: start with mechanism-targeted support/challenge actions or
   review-manifest statuses. Do not put `exists_prior` on the mechanism.

2. **Should `mechanism(...)` replace or coexist with `causal(...)`?**

   Recommendation: use `mechanism(...)` for new structural causal knowledge.
   Keep `causal(...)` as a legacy Claim factory for one release.

3. **Should y0 be a hard dependency or optional extra?**

   Recommendation: first-party Gaia API with lazy-import y0 backend. User
   experience is built in; IR does not depend on y0 object types.

4. **How much storage/index work is required?**

   Recommendation: treat this as an IR/storage-impacting design PR, not a
   local lowering-only change.

---

## 10. Non-Goals Recap

- No `Claim(kind=CAUSAL)` as the canonical DAG source.
- No `exists_prior` on `CausalMechanism`.
- No `is_causal` boolean flag.
- No DoWhy in the first causal release.
- No data-driven estimation.
- No causal discovery.
- No counterfactuals.
- No full CPD taxonomy.
- No attempt to recover causal structure from ordinary `infer` or `implies`
  relations.
