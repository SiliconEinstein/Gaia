# GaiaGraph, Scaffold, and Reasoning Design

**Status:** Design proposal for v0.5 follow-up
**Date:** 2026-05-15
**Branch:** off `v0.5`
**Scope:** Minimal runtime and DSL model for `GaiaGraph`, `Scaffold`, `Reasoning`, scaffold-to-reasoning mapping, `candidate_relation`, `associate(pattern=...)`, and `compose`.
**Non-goals:** No graph engine, no causal graph hierarchy, no `materialize()` DSL verb, no automatic scaffold-to-reasoning conversion.

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
    Support / Infer / Associate
    Equal / Contradict / Exclusive / Decompose
    Compose
```

The important separation is:

- `Knowledge` is what the package talks about.
- `Scaffold` is a graph mark that says "this still needs formalization."
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

Meaning: the package still needs a formal reasoning path from `given` to
`conclusion`.

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

## 4. Reasoning

`Reasoning` replaces the public mental model of `Action`. It means a formal
reasoning record, not an arbitrary operation.

```python
class Reasoning(GaiaGraph):
    ...
```

Existing reasoning families fit under it:

- support-style reasoning: `derive`, `observe`, `compute`, `support`;
- probabilistic reasoning: `infer`, `associate`;
- hard relation reasoning: `equal`, `contradict`, `exclusive`, `decompose`;
- composed reasoning: `compose`.

### 4.1 Hard relations

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

## 5. `associate(pattern=...)`

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

### 5.1 Pattern validation

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

## 6. Compose

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

## 7. Scaffold-to-Reasoning Mapping

Scaffold-to-reasoning mapping is a graph view, not a DSL verb. Authors do not
write `materialize(...)`. Gaia derives mapping links from the package graph so
that `gaia check`, `gaia inquiry`, and future graph export can show how a
scaffold note relates to formal reasoning that was later written.

The mapping does not change inference. It only answers:

```text
Which reasoning records appear to cover this scaffold record?
```

### 7.1 Mapping statuses

Use a small status vocabulary:

| Status | Meaning |
|---|---|
| `unmapped` | No compatible reasoning record was found. |
| `partial` | Some but not all scaffold claims or dependencies are covered. |
| `soft` | Probabilistic reasoning covers the scaffold, but no hard relation or full dependency path is present. |
| `hard` | A hard relation or direct reasoning path covers the scaffold. |
| `workflow` | A `Compose` reasoning covers the scaffold through its child reasoning records. |
| `conflict` | The scaffold pattern and the reasoning pattern disagree. |

These statuses are for reporting only. A scaffold with `hard` or `workflow`
mapping is still a scaffold record; the reasoning record is what carries the
formal semantics.

### 7.2 Reasoning footprint

The mapping pass extracts a small footprint from each reasoning record:

```text
reasoning_ref
kind
input_claims
output_claims
relation_claims
relation_pattern
child_reasoning_refs
```

Examples:

| Reasoning | Footprint |
|---|---|
| `derive(given=[a, b], conclusion=c)` | inputs `{a, b}`, outputs `{c}` |
| `infer(evidence=e, hypothesis=h, ...)` | inputs `{e}`, outputs `{h}` for mapping, even if the Python helper returns `e` |
| `associate(a, b, pattern="equal", ...)` | relation claims `{a, b}`, relation pattern `"equal"`, soft |
| `equal(a, b, c)` | relation claims `{a, b, c}`, relation pattern `"equal"`, hard |
| `exclusive(a, b, c)` | relation claims `{a, b, c}`, relation pattern `"exclusive"`, hard |
| `contradict(a, b)` | relation claims `{a, b}`, relation pattern `"contradict"`, hard |
| `compose(...)` | transitive union of child reasoning footprints |

This footprint is intentionally smaller than the full compiler model. It is
only enough to decide scaffold coverage.

### 7.3 `depends_on` mapping

```python
gap = depends_on(conclusion=c, given=[a, b])
```

The mapping pass looks for reasoning whose output is `c` and whose inputs cover
`a` and `b`.

Direct examples:

```python
derive(conclusion=c, given=[a, b])
```

maps to:

```json
{
  "scaffold_ref": "pkg::scaffold::gap",
  "reasoning_ref": "pkg::reasoning::derive_c",
  "status": "hard",
  "coverage": {"given": ["a", "b"], "conclusion": "c"}
}
```

An `infer` can also cover `depends_on` when its mapping output is the scaffold
conclusion and its evidence/given claims cover the scaffold `given` claims:

```python
infer(evidence=a, hypothesis=c, p_e_given_h=0.9, p_e_given_not_h=0.2)
```

This is a probabilistic reasoning step, but for scaffold coverage it is still a
formal reasoning path. The mapping status is `hard` only in the sense that the
scaffold dependency has been formally written; it does not mean the reasoning
is a hard logical constraint.

If a `Compose` contains child reasoning that jointly covers `a`, `b`, and `c`,
the mapping status is `workflow`.

### 7.4 `candidate_relation` mapping

For relation scaffold, the mapping pass compares claim sets and relation
patterns.

```python
rel = candidate_relation(claims=[a, b, c], pattern="equal")
```

Hard mapping:

```python
equal(a, b, c)
```

maps to `status="hard"` because the hard relation has the same pattern and the
same claim set.

Soft mapping:

```python
associate(a, b, p_a_given_b=0.9, p_b_given_a=0.8, pattern="equal")
associate(b, c, p_a_given_b=0.9, p_b_given_a=0.8, pattern="equal")
```

maps to `status="soft"` for the three-claim equality scaffold because the
positive association edges connect all scaffold claims. It does not assert
equality; it only says the empirical soft evidence points in the same
direction as the scaffold.

Open scaffold:

```python
candidate_relation(claims=[a, b], pattern=None)
```

can map to any compatible relation reasoning over the same claims. If the
first matching reasoning is `associate(a, b, pattern="exclusive", ...)`, Gaia
can report the scaffold as classified softly as `"exclusive"`. If the matching
reasoning is `exclusive(a, b)`, Gaia can report it as classified hard as
`"exclusive"`.

### 7.5 Multi-claim coverage rules

Use deterministic, easy-to-explain rules:

| Scaffold pattern | Hard coverage | Soft coverage through `associate` |
|---|---|---|
| `None` | any hard relation over the same claims classifies it | any patterned association over the same claims, or enough pairwise edges to classify the group |
| `"equal"` | one `equal(...)` over the same claim set | patterned `"equal"` association edges form a connected graph over all claims |
| `"exclusive"` | one `exclusive(...)` over the same claim set | patterned `"exclusive"` association edges cover every pair, because mutual exclusivity is pairwise |
| `"contradict"` | one `contradict(a, b)` over the same two claims | one `"contradict"` association over the same two claims |

Subset matches are `partial`. For example, `equal(a, b)` only partially covers
`candidate_relation(claims=[a, b, c], pattern="equal")`.

Pattern disagreement is `conflict`. For example:

```python
candidate_relation(claims=[a, b], pattern="equal")
exclusive(a, b)
```

The reasoning is formal, but it does not cover the scaffold; it contradicts
the scaffold classification.

### 7.6 Mapping output

The first implementation can generate a derived report section rather than a
new persistent schema:

```json
{
  "scaffold_ref": "pkg::scaffold::mechanism_forms",
  "reasoning_refs": ["pkg::reasoning::same_forms"],
  "status": "hard",
  "pattern": "equal",
  "coverage": {
    "claims": ["pkg::a", "pkg::b", "pkg::c"]
  }
}
```

If a persistent shape becomes useful later, the same payload can live in a
`scaffold_mappings` section of the formalization manifest. That is deferred
until `gaia check` or `gaia graph` needs it.

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

For reasoning records, existing compiler output can remain structurally similar
at first. The public naming should move from "action" to "reasoning", but the
initial implementation does not need to redesign the IR or BP schemas.

## 9. Implementation Checklist

Runtime:

- Add a thin `GaiaGraph` base for graph records.
- Keep `Knowledge` independent from `GaiaGraph`.
- Move `Scaffold` under `GaiaGraph`, not under reasoning.
- Rename the public concept currently called `Action` to `Reasoning`.
- Make `Compose` a `Reasoning`.
- Keep the implementation migration as small as possible; do not add a new
  graph engine.

DSL:

- Change `candidate_relation(a, b, proposed=...)` to
  `candidate_relation(claims=[...], pattern=None | "equal" | "contradict" | "exclusive")`.
- Make `candidate_relation.pattern` default to `None`.
- Allow `candidate_relation(pattern="equal")` and
  `candidate_relation(pattern="exclusive")` to accept two or more claims.
- Restrict `candidate_relation(pattern="contradict")` to exactly two claims.
- Remove public `tension`.
- Add `associate(..., pattern=None | "equal" | "contradict" | "exclusive")`.
- Validate `associate(pattern=...)` against `p_a_given_b` and `p_b_given_a`.
- Consider extending `equal` and `exclusive` to two-or-more claims, while
  keeping `contradict` binary.

Compiler and CLI:

- Emit scaffold records with `claims` and `pattern`, not `a`, `b`, and
  `proposed`.
- Ensure scaffold records still do not close holes.
- Ensure scaffold records are not counted as reasoning in review, lowering, or
  BP.
- Ensure `compose` captures only reasoning records.
- Add a derived scaffold-to-reasoning mapping pass for reporting.
- Update `gaia check` and `gaia inquiry` output for multi-claim candidate
  relations and `pattern=None`.
- Show scaffold mapping status as `unmapped`, `partial`, `soft`, `hard`,
  `workflow`, or `conflict`.

Tests:

- `candidate_relation(claims=[a, b], pattern=None)` compiles into the
  formalization manifest.
- `candidate_relation(claims=[a, b, c], pattern="equal")` is accepted.
- `candidate_relation(claims=[a, b, c], pattern="exclusive")` is accepted.
- `candidate_relation(claims=[a, b, c], pattern="contradict")` fails.
- Public `tension` import is removed.
- `associate(..., pattern=None)` preserves current association behavior.
- `associate(..., pattern="equal")` requires both conditionals above `0.5`.
- `associate(..., pattern="contradict")` requires both conditionals below
  `0.5`.
- `associate(..., pattern="exclusive")` requires both conditionals below
  `0.5`.
- `compose` does not treat scaffold records as child reasoning.
- `depends_on(conclusion=c, given=[a, b])` maps to direct reasoning from
  `{a, b}` to `c`.
- `depends_on(...)` maps to `workflow` when a compose footprint covers the
  dependency.
- `candidate_relation(pattern=None)` can be classified by matching hard or soft
  relation reasoning.
- `candidate_relation(pattern="equal")` maps softly when patterned association
  edges connect all scaffold claims.
- `candidate_relation(pattern="exclusive")` maps softly only when patterned
  association edges cover every pair.
- Pattern disagreement produces `conflict`, not `hard` or `soft`.

Docs:

- Update the user-facing language reference to explain:
  scaffold, reasoning, and compose.
- Update examples to use `candidate_relation(claims=[...], pattern=...)`.
- Remove `tension` from public docs.
- Explain that `associate(pattern=...)` is a soft probabilistic hint, not a
  hard relation.
- Explain scaffold-to-reasoning mapping as a derived graph view, not a user DSL
  verb.
- Keep foundations docs aligned with the new `Knowledge` vs `GaiaGraph`
  split.

## 10. Deferred Work

The following ideas are compatible with this model but are intentionally out of
scope for the first change:

- `gaia graph` export command.
- Causal graph projection.
- Automatic scaffold resolution.
- A `materialize()` DSL function.
- A new persistent graph schema.

Those can be derived later from the same `Knowledge + Scaffold + Reasoning`
records if the need becomes concrete.
