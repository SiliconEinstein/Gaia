# Gaia IR v6 Design

> **Status:** Target design  
> **Date:** 2026-04-21  
> **Scope:** Gaia IR structural contract — Knowledge types, Strategy types, Operator, helper Claims, ReviewManifest/Warrant  
> **Supersedes:** [2026-04-20-gaia-ir-v6-strategy-warrant-redesign.md](2026-04-20-gaia-ir-v6-strategy-warrant-redesign.md)  
> **Companion:** [2026-04-21-gaia-lang-v6-design.md](2026-04-21-gaia-lang-v6-design.md)  
> **Non-goal:** This document specifies the IR contract. BP lowering semantics are in `docs/foundations/bp/`. Lang surface API is in the companion spec.

---

## 0. Executive Summary

Gaia IR v6 keeps the current core shape:

```
Knowledge
Operator
Strategy
```

and adds a package-level review layer:

```
ReviewManifest / Warrant
```

The main semantic change:

```
Old Strategy:
  probabilistic reasoning edge with strategy prior / warrant prior

New Strategy:
  reviewed information-use step that asserts helper claims,
  applies Bayesian inference, or validates a computation.
  Strategy carries no probability.
```

### Core rules

1. **Only `Claim` carries epistemic probability.** Setting, Context, Question do not.
2. **`Strategy` carries no probability.** Uncertainty is expressed through explicit premise Claims.
3. **`Operator` remains deterministic** and continues to produce `conclusion` helper Claims.
4. **Generated helper Claims are neutral** unless asserted by an accepted Strategy.
5. **`Warrant` is a review block in `ReviewManifest`**, not a Claim and not a probability variable.
6. **Statistical evidence** is represented as `Strategy(type="infer")` with a `LikelihoodMethod` payload, not as probabilistic support.

---

## 1. Knowledge

### 1.1 Knowledge types

```python
Knowledge.type ∈ {
    "claim",
    "setting",
    "question",
    "context",
}
```

#### `claim`

A proposition with truth value. The only Knowledge type that receives a prior/posterior and becomes a random variable during BP lowering.

#### `setting`

Formalized background context, convention, or scope statement. Does not carry belief and does not become a BP variable. May appear in Strategy `background`.

#### `question`

Inquiry lens or research target. Organizes exploration but is not itself a belief variable. Does not enter BP.

#### `context`

Raw, not-yet-formalized text or artifact excerpt. Examples: paper paragraph, experiment dashboard excerpt, lab note, reviewer comment source text. Does not participate in BP. Provides traceability and raw material for later formalization.

### 1.2 Parameter values

Parameters support bound values for ground parameterized Claims:

```python
class Parameter:
    name: str
    type: str
    value: JsonValue | None = None
```

The `value` participates in the content hash of a ground parameterized Claim.

#### Knowledge references in parameters

When a parameter's type is a Knowledge type (e.g., `Setting`, `Claim`), the `value` stores the referenced node's QID:

```python
Parameter(name="experiment", type="Setting", value="github:my_package::exp_123")
```

The `[@param_name]` syntax in `content` is resolved at compile time to the referenced node's QID.

### 1.3 Grounding metadata

A root Claim may include grounding metadata explaining why its prior exists:

```python
class Grounding:
    kind: Literal[
        "assumption",
        "source_fact",
        "definition",
        "imported",
        "judgment",
        "open",
    ]
    rationale: str | None = None
    source_refs: list[KnowledgeID] = []
```

Grounding is metadata; it does not affect BP directly.

Recommended lint rule:

```
Every root Claim with a non-default prior should have grounding metadata,
or be supported by a Strategy.
```

---

## 2. Operator

### 2.1 Schema (unchanged)

```python
class Operator:
    operator_id: str | None = None
    scope: Literal["local"] | None = None
    operator: OperatorType
    variables: list[ClaimID]
    conclusion: ClaimID
    metadata: dict | None = None
```

`Operator.conclusion` is separate from `Operator.variables` — it reifies expression results as helper Claims.

### 2.2 Semantics

An Operator is deterministic:

```
Operator defines conclusion = f(variables).
```

Examples:

```
G = Conjunction(A, B, C)
R = Equivalence(A, B)
K = Contradiction(A, B)
S = Implication(G, C)
```

v6 change:

```
Operator.conclusion is not automatically asserted true.
```

It is an expression-result helper Claim. It takes effect only when an accepted Strategy lists it in `assertions`.

### 2.3 Helper Claim defaults

All generated Operator helper Claims default to neutral unless explicitly asserted:

```
default prior/helper treatment = neutral
```

They must not be automatically pinned to `true` merely because they are relation helper Claims.

### 2.4 Helper metadata

Generated helpers should be tagged for traceability:

```python
metadata={
    "generated": True,
    "generated_kind": "helper_claim",
    "helper_kind": "implication_result" | "conjunction_result" | "equivalence_result" | ...,
    "visibility": "formal_internal" | "public",
    "owning_strategy_id": "...",
}
```

---

## 3. Strategy

### 3.1 Contract

```
Strategy is a reviewed information-use step.
It has inputs, a conclusion/target, a method, generated helper assertions,
and a first-class rationale.

Strategy carries no probability parameter.
```

A Strategy answers:

```
What information is being used?
By what method?
For what target?
What helper Claims are asserted when review permits?
Why is this step valid?
```

### 3.2 Schema

```python
class Strategy:
    strategy_id: str | None = None
    scope: Literal["local"]

    type: StrategyType

    premises: list[ClaimID]
    conclusion: ClaimID | None = None
    background: list[KnowledgeID] | None = None

    rationale: str                          # required for v6 Strategies
    assertions: list[ClaimID] = []          # relation helper Claims to assert

    steps: list[Step] | None = None
    method: MethodPayload | None = None
    metadata: dict[str, Any] | None = None
```

`rationale` is required for all v6 Strategies.

`assertions` explicitly lists the relation helper Claims this Strategy asserts as true when review permits. These are the review focus.

### 3.3 Strategy types

```python
class StrategyType(StrEnum):
    DEDUCTION = "deduction"
    OBSERVATION = "observation"
    COMPUTATION = "computation"
    INFER = "infer"
```

`infer` is an existing Strategy type repurposed for Bayesian inference. When it carries a `LikelihoodMethod` payload, it represents a statistical evidence update. Legacy types (`support`, `compare`, etc.) are preserved as aliases for backward compatibility but should not be used in new code.

### 3.4 Method payloads

Each Strategy type may have a type-specific method payload:

```python
class DeductionMethod:
    kind: Literal["deduction"] = "deduction"

class ObservationMethod:
    kind: Literal["observation"] = "observation"

class ComputationMethod:
    kind: Literal["computation"] = "computation"
    function_ref: str
    input_bindings: dict[str, ClaimID]
    output: ClaimID
    output_binding: dict[str, str] | None = None
    code_hash: str | None = None

class LikelihoodMethod:
    kind: Literal["infer"] = "infer"
    hypothesis: ClaimID
    evidence: ClaimID
    p_e_given_h: float
    p_e_given_not_h: float
```

### 3.5 FormalStrategy

`FormalStrategy` remains the canonical way to attach deterministic Operator expansion to a Strategy:

```python
class FormalStrategy(Strategy):
    formal_expr: FormalExpr

class FormalExpr:
    operators: list[Operator]
```

v6 interpretation:

```
FormalExpr creates helper Claims via deterministic Operators.
Strategy.assertions lists which of those helper Claims are asserted when review permits.
```

### 3.6 Strategy.assertions semantics

`assertions` contains **relation helper Claims** that this Strategy asserts as true. These are the review focus:

- `Implication` — from derive: AllTrue(given) ⟹ conclusion
- `Equivalence` — from match
- `Contradiction` — from contradict
- `StatisticalSupport` — from infer

**NOT included** (mechanical, no review needed):
- Conjunction helpers (auto-generated from tuple premises)
- Disjunction helpers

---

## 4. Deduction Strategy

### 4.1 Canonical form

For a user-level derive step `given=(A, B, rule) → conclusion=C`:

```
G = AllTrue(A, B, rule)
S = Implies(G, C)
```

IR:

```python
FormalStrategy(
    type="deduction",
    premises=[A, B, rule],
    conclusion=C,
    rationale="Given A, B, and the rule, C follows.",
    assertions=[S],
    formal_expr=FormalExpr(operators=[
        Operator("conjunction", [A, B, rule], conclusion=G),
        Operator("implication", [G, C], conclusion=S),
    ]),
)
```

Review policy decides whether `S` is asserted.

### 4.2 Empty premises

A deduction Strategy with empty premises is an unconditional assertion. Allowed only for definitions, axioms, or compiler-generated internals.

## 5. Observation Strategy

### 5.1 Semantics

`Strategy(type="observation")` represents empirical observation or measurement. Structurally identical to deduction (AllTrue(given) ⟹ conclusion), but carries different review semantics.

The distinction from deduction is semantic, not structural — the audit question focuses on observation reliability rather than logical validity.

### 5.2 No-premise observation

A no-premise observe (root fact) does not generate a Strategy. It only adds `Grounding(kind="source_fact")` to the Claim.

---

## 6. Computation Strategy

### 6.1 Semantics

`Strategy(type="computation")` represents execution or validation of a deterministic computation that produces a parameterized Claim.

### 6.2 Method payload

```python
class ComputationMethod:
    kind: Literal["computation"] = "computation"
    function_ref: str
    input_bindings: dict[str, ClaimID]
    output: ClaimID
    output_binding: dict[str, str] | None = None
    code_hash: str | None = None
```

### 6.3 Computation uncertainty

Do not put probability on the computation Strategy. If something is uncertain, add explicit premise Claims:

```
FormulaCorrect — "The formula is mathematically correct."
ImplementationCorrect — "The code implements the formula without bugs."
```

Include them in Strategy premises.

---

## 7. Infer Strategy

### 7.1 Semantics

`Strategy(type="infer")` with a `LikelihoodMethod` payload represents Jaynes/Bayes-style evidence update:

```
Given premises (gate), apply Bayesian inference to update target Claim.
```

It is **inferential** (statistical), not relational (logical) or directional (support). It creates a bidirectional factor between hypothesis and evidence.

### 7.2 Method payload

```python
class LikelihoodMethod:
    kind: Literal["infer"] = "infer"
    hypothesis: ClaimID
    evidence: ClaimID
    p_e_given_h: float       # P(E|H,I)
    p_e_given_not_h: float   # P(E|¬H,I)
```

### 7.3 BP lowering

For binary hypothesis H and evidence E:

```
if all gate premises are true:
    odds(H) *= P(E|H) / P(E|¬H)
else:
    no update (neutral factor)
```

The Strategy itself has no probability. The gate premises carry epistemic reliability.

### 7.4 Helper Claim

Likelihood generates a `StatisticalSupport` helper Claim:

```
StatisticalSupport(hypothesis=H, evidence=E, conditions=conjunction(given))
```

This helper can be used as a premise in downstream derive steps.

---

## 8. ReviewManifest and Warrant

### 8.1 Separation from semantic graph

```python
class GaiaPackageArtifact:
    graph: LocalCanonicalGraph
    review: ReviewManifest | None = None
```

Review status is deliberately separated from the canonical semantic graph. Review status can change without changing the semantic content.

### 8.2 Warrant schema

```python
class WarrantStatus(StrEnum):
    UNREVIEWED = "unreviewed"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    NEEDS_INPUTS = "needs_inputs"

class Warrant:
    warrant_id: str
    strategy_id: str            # points to the reviewed Strategy
    status: WarrantStatus
    audit_question: str         # auto-generated from Strategy type
    reviewer_notes: str | None = None
    timestamp: str
    round: int                  # supports multi-round review
```

### 8.3 Multi-round review

A single Strategy can have multiple Warrants across review rounds. The latest Warrant's status determines whether the Strategy participates in inference.

### 8.4 Default behavior

**Unreviewed Strategies do NOT participate in inference** (pessimistic default). A Strategy must be explicitly accepted before it contributes to belief propagation.

### 8.5 Warrant has no probability

```
Warrant is procedural review state, not epistemic uncertainty.
```

No `Warrant(prior=...)`. No `WARRANT_PRIORS = {...}`.

If reviewer finds an issue, the fix is to modify the reasoning graph directly: add missing premise Claims, adjust Claim priors, or mark the Warrant as `needs_inputs`.

### 8.6 Auto-generated audit questions

Audit questions are automatically generated from Strategy type and assertions, using `[@...]` reference templates:

| Strategy type | Audit question template |
|---|---|
| deduction | "Do the listed premises suffice to establish [@conclusion]?" |
| observation | "Is the observation of [@conclusion] reliable under the stated conditions?" |
| computation | "Is the computation of [@conclusion] correctly implemented?" |
| infer | "Is the statistical association between [@hypothesis] and [@evidence] valid at the stated probabilities?" |
| match (Relate) | "Are [@a] and [@b] truly equivalent?" |
| contradict (Relate) | "Do [@a] and [@b] truly contradict?" |

Templates are rendered to concrete questions using the referenced Claims' labels or content.

---

## 9. Compilation target summary

| Lang construct | IR compilation target |
|---|---|
| `Context(...)` | `Knowledge(type="context")` |
| `Setting(...)` | `Knowledge(type="setting")` |
| `Claim(...)` / subclasses | `Knowledge(type="claim")` + bound parameters |
| `Question(...)` | `Knowledge(type="question")` |
| `derive(...)` | `FormalStrategy(type="deduction")` + conjunction + implication helpers |
| `observe(...)` with premises | `FormalStrategy(type="observation")` + conjunction + implication helpers |
| `observe(...)` no premises | `Grounding(kind="source_fact")` on the Claim |
| `compute(...)` / `@compute` | `Strategy(type="computation")` + ComputationMethod |
| `match(A, B)` | `Operator(type="equivalence")` + Equivalence helper Claim |
| `contradict(A, B)` | `Operator(type="contradiction")` + Contradiction helper Claim |
| `infer(...)` | `Strategy(type="infer")` + LikelihoodMethod + StatisticalSupport helper |
| `given=(A, B, C)` tuple | `Operator(type="conjunction")` + conjunction helper Claim |
| `rationale=` | `Strategy.rationale` |
| `background=` | `Strategy.background` |
| Warrant review | `ReviewManifest` with `Warrant` entries |

---

## 10. Required IR schema extensions

### 10.1 New fields

- `Knowledge.type` adds `"context"` value
- `Parameter.value: JsonValue | None` — bound parameter values (including QID references for Knowledge-typed parameters)
- `Knowledge.grounding: Grounding | None` — root Claim provenance metadata
- `Knowledge.content_template: str | None` — original docstring template before rendering
- `Knowledge.rendered_content: str | None` — content after template substitution
- `Strategy.rationale: str` — required for v6
- `Strategy.assertions: list[ClaimID]` — helper Claims to assert
- `Strategy.method: MethodPayload | None` — type-specific payload
- `StrategyType` adds `OBSERVATION`, `COMPUTATION` (note: `INFER` already exists)

### 10.2 New types

- `Grounding` — root Claim provenance metadata
- `ReviewManifest` — package-level review state
- `Warrant` — individual Strategy review record
- `LikelihoodMethod` — infer Strategy payload for Bayesian inference
- `ComputationMethod` — computation Strategy payload
- `StatisticalSupport` — helper Claim type for infer

### 10.3 Not changed

- `Operator` schema unchanged
- `FormalStrategy` / `FormalExpr` unchanged
- Existing Strategy types preserved as legacy aliases
- Package, Module structure unchanged

---

## 11. Open questions

1. Should `CompositeStrategy` be kept in IR for future composition support?
   Recommended: keep for forward compatibility, but v6 does not use it.

2. Should `exhaust()` (exhaustive alternatives) be added?
   Recommended: defer, requires new Operator type.

3. Should `StrategyType.SUPPORT` and `StrategyType.INFER` be kept as legacy aliases?
   Recommended: yes for migration, but canonical v6 code should use `deduction`/`observation`/`computation`/`infer`.
