# GaiaGraph, Scaffold, Reasoning, and `materialize(...)` Design

**Status:** Design proposal for v0.5 follow-up
**Date:** 2026-05-15
**Branch:** off `v0.5`
**Scope:** Minimal runtime and DSL model for `GaiaGraph`, `Scaffold`, `Reasoning`, `candidate_relation`, `associate(pattern=...)`, `compose`, and the `materialize(...)` linking function.
**Non-goals:** No graph engine, no causal graph hierarchy, no automatic scaffold-to-formal-record conversion, and no assumption that scaffold can only be formalized by reasoning.

## 1. Goal

The DSL should have a small, readable hierarchy:

```text
Knowledge
  Claim / Setting / Question

GaiaGraph
  Scaffold
    DependsOn
    CandidateRelation

  Reasoning
    Directed
      Derive / Observe / Compute / Infer
    Relation
      Equal / Contradict / Exclusive / Associate
    Decompose
    Compose

  Future formal graph records
    CausalEdge / MeasurementLink / other extensions
```

The important separation is:

- `Knowledge` is what the package talks about.
- `Scaffold` is a graph mark that says "this still needs formalization."
- `materialize(...)` records a checked link from scaffold to the formal graph
  record that handles it; the link is not a `GaiaGraph` subclass.
- `Reasoning` is a formal reasoning step that can participate in review,
  lowering, or inference.
- `Compose` is a compound `Reasoning` made from other reasoning records.

This keeps the model minimal while making the layer structure visible to
authors. Scaffold records and reasoning records are both graph records, but
they do not have the same semantics.

## 2. GaiaGraph Base

`GaiaGraph` is the common base for graph records only. `Knowledge` does not
inherit from it.

```python
@dataclass
class GaiaGraph:
    label: str | None = None
    rationale: str = ""
    background: list[Knowledge] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
```

The compiler assigns stable references to `GaiaGraph` records, just as it
already assigns references to lowered reasoning and scaffold entries. This
shared reference mechanism is needed so that:

- scaffold records can be displayed in `gaia check` and `gaia inquiry`;
- reasoning records can be reviewed and cited by label;
- `compose` can point to child reasoning records;
- future graph exports can show scaffold, reasoning, and composition together.

This proposal does not require a new graph runtime. The first implementation
can keep using the existing package registration and manifest machinery, with
the class hierarchy renamed and narrowed.

## 3. Scaffold

Scaffold records do not close holes, do not produce belief updates, and do not
lower into BP factors. They only preserve author intent while a package is
being formalized.

### 3.1 `depends_on`

```python
depends_on(
    conclusion,
    *,
    given=[a, b],
    rationale="These premises are needed, but the reasoning step is not written yet.",
)
```

Meaning: the package still needs a formal directed graph record or graph path
from `given` to `conclusion`. Today that is usually reasoning, but the scaffold
does not assume reasoning is the only possible formalization target.

`depends_on` should return the `DependsOn` scaffold record, not the conclusion
claim. That lets the author pass the scaffold to `materialize(...)` later.

### 3.2 `candidate_relation`

```python
candidate_relation(
    claims=[a, b, c],
    pattern=None | "equal" | "contradict" | "exclusive",
    rationale="These claims appear related, but the formal relation is not settled.",
)
```

`pattern` defaults to `None`.

| Pattern | Allowed claim count | Meaning |
|---|---:|---|
| `None` | two or more | There may be a relation, but the author has not classified it yet. |
| `"equal"` | two or more | These claims may be different formulations of the same assertion. |
| `"exclusive"` | two or more | These claims may be mutually exclusive alternatives. |
| `"contradict"` | exactly two | These two claims may directly contradict each other. |

`candidate_relation` is intentionally weaker than `equal`, `contradict`, or
`exclusive`. It says "look here later"; it does not assert the relation.

There is no `tension` pattern. If the author knows the shape, use
`"contradict"` or `"exclusive"`. If the author only knows that something is
odd, use `pattern=None`.

## 4. `materialize(...)`

`materialize` is the only explicit bridge from scaffold to formal graph
records. It is a DSL/API function that records a materialization link; it is
not a graph-record class and not part of the `GaiaGraph` hierarchy.

```python
materialize(
    scaffold,
    *,
    by=formal_graph_record,
    rationale="...",
)
```

It records: "this scaffold has been formalized by that graph record." It does
not create the formal record, does not change BP, and does not turn scaffold
into reasoning.

The `by` argument should accept a single record or a list of records. It should
not be limited to `Reasoning`, because future Gaia graph records may include
causal edges, measurement links, definition links, or other formal records that
are not reasoning records.

```python
gap = depends_on(
    conclusion=hypothesis,
    given=[evidence],
    rationale="The likelihood link still needs to be written.",
)

infer(
    evidence,
    hypothesis=hypothesis,
    p_e_given_h=0.9,
    p_e_given_not_h=0.2,
    label="evidence_likelihood",
)

materialize(gap, by="evidence_likelihood")
```

For relation scaffold:

```python
rel = candidate_relation(
    claims=[a, b],
    pattern="equal",
    rationale="These may be two statements of the same mechanism.",
)

same = equal(a, b, label="same_mechanism")
materialize(rel, by=same)
```

Future causal example:

```python
rel = candidate_relation(claims=[exposure, outcome], pattern=None)

edge = causes(exposure, outcome, label="exposure_causes_outcome")
materialize(rel, by=edge)
```

### 4.1 Return and reference rule

`materialize` needs a concrete scaffold record, so scaffold constructors return
scaffold records:

```python
gap = depends_on(...)
rel = candidate_relation(...)
```

Reasoning verbs may keep their current user-facing return values. For example,
`derive` returns its conclusion claim, `infer` returns its evidence claim, and
relation verbs return helper claims. To avoid a broad return-value migration,
`materialize(..., by=...)` can resolve `by` in three small ways:

| `by` value | Resolution rule |
|---|---|
| `GaiaGraph` record | use it directly |
| label string | resolve it through the shared GaiaGraph label table |
| returned `Claim` | use the producing graph record when the claim has exactly one producer; otherwise require a label |

This keeps the bridge explicit without forcing every reasoning verb to return a
different object.

### 4.2 Checks

`materialize` should do checks, but only the minimum checks needed to prevent
obvious misuse:

1. `scaffold` must be a `Scaffold`.
2. `by` must resolve to one or more formal `GaiaGraph` records.
3. `by` must not resolve to another `Scaffold`, and materialization links
   cannot materialize other materialization links.
4. `by` must reference at least one of the scaffold's core claims.
5. If `candidate_relation.pattern` is not `None` and `by` declares a relation
   pattern, the patterns must match.
6. If `by` is ambiguous, for example a returned claim has multiple producing
   graph records, the author must use a label.

These checks are deliberately not a proof that the formalization is correct.
They catch unrelated or contradictory links while leaving the scientific
judgment to the author and reviewer.

### 4.3 What `materialize` does not do

`materialize` does not:

- create `infer`, `equal`, `causes`, or any other formal record;
- infer that a scaffold is resolved automatically;
- remove or mutate the scaffold record;
- contribute a factor to BP;
- imply the formal record is accepted by review;
- require the formal record to be a `Reasoning`.

It is bookkeeping plus sanity checks.

## 5. Reasoning

`Reasoning` is the runtime and user-facing name for a formal reasoning record.
It is not an arbitrary operation.

```python
class Reasoning(GaiaGraph):
    ...
```

Existing reasoning records fit under four graph shapes:

- `Directed`: source information points toward a target claim or helper claim,
  as in `derive`, `observe`, `compute`, and `infer`;
- `Relation`: claims participate in a relation, as in `equal`, `contradict`,
  `exclusive`, and `associate`;
- `Decompose`: one whole claim is unpacked into claim parts and a formula;
- `Compose`: child reasoning records are grouped into a reusable workflow.

Whether a record is hard, empirical, computed, or probabilistic is decided by
the concrete class and lowering logic, not by a top-level runtime family.

### 5.1 Hard relations

The hard relation verbs are explicit reasoning. They are not created
automatically from scaffold records.

```python
equal(a, b, c)
exclusive(a, b, c)
contradict(a, b)
```

Minimal arity rules:

- `equal` accepts two or more claims.
- `exclusive` accepts two or more claims.
- `contradict` accepts exactly two claims.

## 6. `associate(pattern=...)`

`associate` remains a probabilistic soft constraint. It may optionally say what
kind of hard relation this empirical association might support later.

```python
associate(
    a,
    b,
    p_a_given_b=0.9,
    p_b_given_a=0.85,
    pattern=None | "equal" | "contradict" | "exclusive",
)
```

`pattern` defaults to `None`. There is no `"correlate"` pattern because
`associate(...)` already means empirical association. `None` means the author
is recording a probabilistic relationship without claiming it points toward a
specific hard relation.

### 6.1 Pattern validation

When `pattern` is not `None`, the declared pattern must agree with the two
conditional probabilities. The validation is intentionally simple: it checks
direction against the neutral point `0.5`; it does not try to prove a logical
relation.

| Pattern | Required probability shape |
|---|---|
| `None` | no pattern-specific validation |
| `"equal"` | `p_a_given_b > 0.5` and `p_b_given_a > 0.5` |
| `"contradict"` | `p_a_given_b < 0.5` and `p_b_given_a < 0.5` |
| `"exclusive"` | `p_a_given_b < 0.5` and `p_b_given_a < 0.5` |

Examples:

```python
# OK: the probabilities say A and B tend to appear together.
associate(a, b, p_a_given_b=0.9, p_b_given_a=0.8, pattern="equal")

# OK: the probabilities say A and B rarely co-occur.
associate(a, b, p_a_given_b=0.1, p_b_given_a=0.2, pattern="exclusive")

# Error: the probabilities do not support an equality-shaped association.
associate(a, b, p_a_given_b=0.2, p_b_given_a=0.8, pattern="equal")
```

Suggested error messages:

```text
associate(pattern='equal') requires p_a_given_b > 0.5 and p_b_given_a > 0.5.
associate(pattern='exclusive') requires p_a_given_b < 0.5 and p_b_given_a < 0.5.
associate(pattern='contradict') requires p_a_given_b < 0.5 and p_b_given_a < 0.5.
```

This check is deliberately weaker than a statistical independence test. With
only `P(A|B)` and `P(B|A)`, Gaia cannot determine whether the association is
positive or negative relative to the marginals `P(A)` and `P(B)`. The check
only prevents the author from writing a pattern that points in the opposite
direction of the probabilities they supplied.

## 7. Compose

`Compose` is a `Reasoning` because compound reasoning is still reasoning.

```text
Reasoning
  Compose
    child reasoning refs
```

`compose` should capture reasoning records, not scaffold records. If a package
contains scaffold inside a function decorated with `@compose`, that scaffold
should remain a package-level scaffold note rather than becoming part of the
formal reasoning workflow.

This keeps the meaning simple:

- scaffold says what still needs to be formalized;
- reasoning is the formalized step;
- compose names a reusable reasoning workflow.

## 8. Manifest Shape

The scaffold manifest should represent the new API directly.

```json
{
  "kind": "candidate_relation",
  "label": "mechanism_forms_may_match",
  "claims": ["pkg::claim_a", "pkg::claim_b", "pkg::claim_c"],
  "pattern": "equal",
  "rationale": "These appear to be three formulations of the same mechanism."
}
```

For open scaffold:

```json
{
  "kind": "candidate_relation",
  "claims": ["pkg::claim_a", "pkg::claim_b"],
  "pattern": null
}
```

`materialize(...)` links should be recorded alongside scaffold records, not in
the BP-facing IR:

```json
{
  "kind": "materialization",
  "label": "mechanism_forms_materialized",
  "scaffold": "pkg::scaffold::mechanism_forms_may_match",
  "by": ["pkg::graph::same_mechanism"],
  "rationale": "The equality relation makes the candidate relation explicit."
}
```

For reasoning records, existing compiler output can remain structurally similar
at first. The public naming should move from "action" to "reasoning", but the
initial implementation does not need to redesign the IR or BP schemas.

## 9. Implementation Checklist

Runtime:

- Add a thin `GaiaGraph` base for graph records.
- Keep `Knowledge` independent from `GaiaGraph`.
- Move `Scaffold` under `GaiaGraph`, not under reasoning.
- Add `materialize(...)` as a DSL/API function that records a checked
  materialization link outside the `GaiaGraph` hierarchy.
- Rename the old action-style public concept to `Reasoning`.
- Make `Compose` a `Reasoning`.
- Keep the implementation migration as small as possible; do not add a new
  graph engine.

DSL:

- Change `candidate_relation(a, b, proposed=...)` to
  `candidate_relation(claims=[...], pattern=None | "equal" | "contradict" | "exclusive")`.
- Make `candidate_relation.pattern` default to `None`.
- Make scaffold constructors return scaffold records so they can be passed to
  `materialize(...)`.
- Allow `candidate_relation(pattern="equal")` and
  `candidate_relation(pattern="exclusive")` to accept two or more claims.
- Restrict `candidate_relation(pattern="contradict")` to exactly two claims.
- Remove public `tension`.
- Add `associate(..., pattern=None | "equal" | "contradict" | "exclusive")`.
- Validate `associate(pattern=...)` against `p_a_given_b` and `p_b_given_a`.
- Add `materialize(scaffold, by=...)`, accepting a graph record, graph label,
  producer claim, or list of those values.
- Consider extending `equal` and `exclusive` to two-or-more claims, while
  keeping `contradict` binary.

Compiler and CLI:

- Emit scaffold records with `claims` and `pattern`, not `a`, `b`, and
  `proposed`.
- Ensure scaffold records still do not close holes.
- Ensure scaffold records are not counted as reasoning in review, lowering, or
  BP.
- Ensure `compose` captures only reasoning records.
- Emit materialization records outside the BP-facing IR.
- Validate `materialize(...)` with the minimum type, claim-reference, ambiguity,
  and pattern-consistency checks in §4.2.
- Update `gaia check` and `gaia inquiry` output for multi-claim candidate
  relations and `pattern=None`.

Tests:

- `candidate_relation(claims=[a, b], pattern=None)` compiles into the
  formalization manifest.
- `candidate_relation(claims=[a, b, c], pattern="equal")` is accepted.
- `candidate_relation(claims=[a, b, c], pattern="exclusive")` is accepted.
- `candidate_relation(claims=[a, b, c], pattern="contradict")` fails.
- Public `tension` import is removed.
- `depends_on(...)` and `candidate_relation(...)` return scaffold records.
- `materialize(scaffold, by=reasoning_label)` records a materialization link.
- `materialize(...)` rejects scaffold-to-scaffold links.
- `materialize(...)` rejects a `by` record that references none of the
  scaffold's core claims.
- `materialize(...)` rejects an ambiguous producer claim and asks for a label.
- `materialize(...)` rejects known relation-pattern conflicts.
- `associate(..., pattern=None)` preserves current association behavior.
- `associate(..., pattern="equal")` requires both conditionals above `0.5`.
- `associate(..., pattern="contradict")` requires both conditionals below
  `0.5`.
- `associate(..., pattern="exclusive")` requires both conditionals below
  `0.5`.
- `compose` does not treat scaffold records as child reasoning.

Docs:

- Update the user-facing language reference to explain:
  scaffold, reasoning, and compose.
- Update examples to use `candidate_relation(claims=[...], pattern=...)`.
- Remove `tension` from public docs.
- Explain that `associate(pattern=...)` is a soft probabilistic hint, not a
  hard relation.
- Explain `materialize(...)` as explicit bookkeeping/linking and checking, not
  a `GaiaGraph` subclass or reasoning primitive.
- Keep foundations docs aligned with the new `Knowledge` vs `GaiaGraph`
  split.

## 10. Deferred Work

The following ideas are compatible with this model but are intentionally out of
scope for the first change:

- `gaia graph` export command.
- Causal graph projection.
- Automatic scaffold resolution.
- A new persistent graph schema.

Those can be derived later from the same `Knowledge + Scaffold + Reasoning`
records and materialization links if the need becomes concrete.
