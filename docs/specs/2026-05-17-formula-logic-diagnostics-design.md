# Formula Logic Diagnostics API

**Status:** Draft for review
**Date:** 2026-05-17
**Branch:** `codex/formula-logic-diagnostics-design`
**Related PRs:** #632, #633
**Scope:** Gaia v0.5, reviewer-facing formula logic diagnostics
**Non-goals:** No theorem prover, no CLI gate in phase 1, no BP probability
estimation inside diagnostics, and no fatal errors for cross-claim disagreement.

## 1. Goal

Expose the smallest useful interface that lets reviewer-like callers inspect
formula-level logic issues in a compiled Gaia package.

The first implementation phase should cover:

1. Claim-local logic defects, where an internally contradictory formula is a
   fatal issue for that claim.
2. Conservative cross-claim logic warnings, where even hard logical
   incompatibility is not fatal because each claim can carry its own prior and
   posterior belief.
3. Machine-readable diagnostic conditions that a downstream BP or review layer
   can turn into a probability of the warning being active.

This is best treated as **A-prime + C0**:

- A-prime: connect the FormulaGraph IR added in #632 to a real diagnostics API.
- C0: include the minimal pairwise cross-claim analysis needed for useful
  warnings.
- B: defer CLI and presentation until the API contract is stable.
- C-rich: defer broader package-level theorem proving and probability queries.

## 2. First Principles

Formula logic diagnostics must separate four concepts that are easy to conflate:

| Concept | Meaning | Example |
|---|---|---|
| Logical structure | What follows from formulas if their formulas are treated as hard Boolean structure. | `A` and `not A` cannot both hold. |
| Claim belief | How credible each claim currently is under prior/reviewer/BP evidence. | `belief(A) = 0.7`. |
| Diagnostic severity | How Gaia should treat the issue operationally. | claim-local contradiction is `fatal`; cross-claim contradiction is `warning`. |
| Diagnostic probability | A downstream probability that the warning condition is active. | `Pr(A and B)`. |

The diagnostics layer should report structure, not decide scientific truth.
Cross-claim disagreement is usually a review signal, not a compilation failure.

The only fatal class in the first implementation should be a defect inside the
same formula-bearing claim, such as a single claim whose own formula is
unsatisfiable. That makes the claim malformed as a logical object.

## 3. Current Code Facts

The v0.5 branch already has the foundation needed for this API:

- `gaia.engine.ir.formula` defines `FormulaGraph`, `FormulaNode`,
  `FormulaEdge`, and `formula_node_id`.
- `LocalCanonicalGraph` includes `formula_graphs`, and the graph hash includes
  formula graph content.
- The compiler emits formula graphs from `claim(formula=...)`.
- IR validation checks formula graph source claims, node ids, root ids,
  descriptors, and edge references.
- `gaia.engine.ir.logic.propositional` currently projects existing
  `Operator`/`FormalStrategy` graphs into SymPy propositions.
- `gaia.engine.ir.review` provides `ReviewManifest`, but it is a qualitative
  review record model and should not be mutated by the first diagnostics API.

The missing piece is a formula-graph diagnostics module that consumes
`LocalCanonicalGraph.formula_graphs` directly.

## 4. Public API

Add a small module:

```python
gaia.engine.ir.logic.diagnostics
```

The primary entry point should be:

```python
def inspect_formula_graphs(
    graph: LocalCanonicalGraph,
    *,
    include_pairwise: bool = True,
) -> FormulaDiagnosticReport:
    ...
```

The API returns a report instead of raising for logical warnings. Structural IR
errors remain the responsibility of `validate_local_graph` and Pydantic model
validation.

### 4.1 Models

Use Pydantic models, consistent with the IR and review layers:

```python
FormulaDiagnosticSeverity = Literal["info", "warning", "fatal"]
FormulaDiagnosticScope = Literal["claim", "claim_pair", "package"]
FormulaLogicStrength = Literal["hard", "soft", "mixed", "unknown"]

DiagnosticConditionKind = Literal[
    "formula_unsat",
    "formula_tautology",
    "joint_incompatibility",
    "entailment_violation",
    "redundant_formula",
]

ConditionConfidenceBasis = Literal[
    "hard_logic",
    "soft_relation",
    "projection",
]
```

```python
class DiagnosticCondition(BaseModel):
    kind: DiagnosticConditionKind
    variables: list[str] = Field(default_factory=list)
    expression: dict[str, Any]
    confidence_basis: ConditionConfidenceBasis


class FormulaDiagnostic(BaseModel):
    code: str
    severity: FormulaDiagnosticSeverity
    scope: FormulaDiagnosticScope
    logic_strength: FormulaLogicStrength
    source_claim: str | None = None
    related_claims: list[str] = Field(default_factory=list)
    formula_nodes: list[str] = Field(default_factory=list)
    condition: DiagnosticCondition | None = None
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class FormulaDiagnosticReport(BaseModel):
    diagnostics: list[FormulaDiagnostic] = Field(default_factory=list)

    @property
    def has_fatal(self) -> bool:
        return any(d.severity == "fatal" for d in self.diagnostics)
```

The concrete implementation may use tuples internally, but the serialized
contract should be JSON-friendly and deterministic.

### 4.2 Condition Expression AST

`DiagnosticCondition.expression` should be a small JSON Boolean AST, not a
SymPy object and not Python source code.

Supported shapes in phase 1:

```json
{"var": "claim_a"}
{"op": "not", "arg": {"var": "claim_a"}}
{"op": "and", "args": [{"var": "claim_a"}, {"var": "claim_b"}]}
{"op": "or", "args": [{"var": "claim_a"}, {"var": "claim_b"}]}
```

Variables should use stable claim ids when the warning is about claim truth
values. The examples use short aliases; real diagnostics should use the exact
ids already present in Gaia IR. Formula node ids can be used for local formula
atoms only when no claim qid exists.

This condition is the bridge to BP. The diagnostics module does not estimate
`Pr(condition)`. It exposes a queryable event such as:

| Diagnostic | Condition event for downstream probability |
|---|---|
| Cross-claim incompatibility between `A` and `B` | `A and B` |
| Entailment from `A` to `B` | `A and not B` |
| Formula equivalence between `A` and `B` | `(A and not B) or (B and not A)` |
| Local unsatisfiable formula in `A` | `A`; usually no BP probability is needed because this is fatal. |

Downstream BP can estimate the probability with exact event queries,
approximate factor-graph queries, sampled beliefs, or a later dedicated joint
query API. The diagnostics contract should not depend on which estimator is
available.

## 5. Severity Semantics

Severity and logical strength are independent fields.

| Situation | Scope | Logic strength | Severity | Rationale |
|---|---|---|---|---|
| One claim formula is unsatisfiable | `claim` | `hard` | `fatal` | The claim is internally malformed as a logical object. |
| One claim formula is tautological | `claim` | `hard` | `warning` | The claim may be uninformative but not invalid. |
| Repeated redundant operands in one formula | `claim` | `hard` | `info` | Useful cleanup signal. |
| Two hard formula claims cannot both hold | `claim_pair` | `hard` | `warning` | Claims have priors and beliefs; this is review evidence, not compile failure. |
| A soft relation is crossed | `claim_pair` | `soft` | `warning` | Soft constraints are allowed to be violated. |
| One claim entails another | `claim_pair` | `hard` | `info` | The relation becomes important if BP assigns high probability to `A and not B`. |

The first implementation should not emit `fatal` for any cross-claim condition.
If future package policies want a stricter gate, that policy should live above
this diagnostics API.

## 6. Phase 1 Algorithm

### 6.1 FormulaGraph Projection

Add an internal projector from `FormulaGraph` roots to a backend Boolean
expression:

```python
formula_graph_to_sympy(formula_graph: FormulaGraph) -> Any
```

It should support only propositional shapes in phase 1:

- atom
- `and`
- `or`
- `not`
- `implies`
- `iff`

Unsupported first-order, quantifier, term, or predicate shapes should be
handled conservatively:

- If the whole formula cannot be projected, skip logic solving for that graph
  and optionally emit an `info` diagnostic with code
  `formula_projection_unsupported`.
- Do not fail the API because a formula is outside the current propositional
  subset.

Atom symbols should be stable and derived from formula node ids or claim-atom
qids. Do not use object identity or source order.

### 6.2 Claim-Local Diagnostics

For each projectable formula graph:

- `satisfiable(expr) is False` emits:
  - `code="formula_unsat"`
  - `severity="fatal"`
  - `scope="claim"`
  - `source_claim=<claim id>`
  - `condition.kind="formula_unsat"`
- `satisfiable(Not(expr)) is False` emits:
  - `code="formula_tautology"`
  - `severity="warning"`
  - `scope="claim"`
- repeated operands in a single commutative connective emit:
  - `code="formula_redundant_operand"`
  - `severity="info"`
  - `scope="claim"`

The local pass should not inspect reviewer beliefs.

### 6.3 Pairwise Cross-Claim Diagnostics

When `include_pairwise=True`, compare pairs of projectable formula graphs.

Candidate selection should be conservative:

- Compare only pairs that share at least one stable atom id or claim-atom qid.
- Avoid an unconditional `O(n^2)` scan across unrelated formulas.
- Do not compare a graph with itself.

For candidate pair `(A, B)`:

- If `A and B` is unsatisfiable, emit:
  - `code="cross_claim_incompatibility"`
  - `severity="warning"`
  - `scope="claim_pair"`
  - `logic_strength="hard"` unless metadata marks one side soft.
  - `condition.kind="joint_incompatibility"`
  - `condition.expression = A_claim and B_claim`
- If `A -> B` is tautological and not equivalent, emit:
  - `code="cross_claim_entailment"`
  - `severity="info"`
  - `condition.kind="entailment_violation"`
  - `condition.expression = A_claim and not B_claim`
- If `A` and `B` are equivalent, emit:
  - `code="cross_claim_equivalence"`
  - `severity="info"`
  - `condition.kind="redundant_formula"`

Cross-claim diagnostics are never fatal in phase 1.

## 7. Reviewer Integration

The first implementation should keep this independent from `ReviewManifest`.

Reviewer-like callers can do:

```python
compiled = compile_package(...)
report = inspect_formula_graphs(compiled.graph)
```

This avoids changing the existing `ReviewManifest` schema before the diagnostics
shape is proven useful.

A later adapter can map diagnostics into review records, for example:

```python
formula_diagnostics_to_reviews(report: FormulaDiagnosticReport) -> ReviewManifest
```

That adapter belongs in phase B or later because it is presentation and
workflow-specific. The core API should remain usable by CLI, reviewer, tests,
and BP code without depending on a review manifest.

## 8. BP Integration Contract

The diagnostics API must be BP-compatible without requiring BP to run.

The contract is:

1. Every probabilistic warning has a `DiagnosticCondition`.
2. The condition uses stable ids and a JSON Boolean AST.
3. The condition represents the bad event or violation event whose probability
   a downstream layer may estimate.
4. Diagnostics report `severity`, not posterior probability.

Example:

```json
{
  "code": "cross_claim_incompatibility",
  "severity": "warning",
  "scope": "claim_pair",
  "logic_strength": "hard",
  "source_claim": "claim_a",
  "related_claims": ["claim_b"],
  "condition": {
    "kind": "joint_incompatibility",
    "variables": ["claim_a", "claim_b"],
    "expression": {
      "op": "and",
      "args": [{"var": "claim_a"}, {"var": "claim_b"}]
    },
    "confidence_basis": "hard_logic"
  }
}
```

A BP layer can then compute or approximate `Pr(claim_a and claim_b)`. If that
probability is low, the warning may be low priority. If it is high, a reviewer
can prioritize it.

This design also allows future soft constraints:

```json
{
  "logic_strength": "soft",
  "condition": {
    "kind": "joint_incompatibility",
    "confidence_basis": "soft_relation",
    "expression": {"op": "and", "args": [{"var": "A"}, {"var": "B"}]}
  }
}
```

The contradiction remains legal; the probability and relation strength decide
review priority.

## 9. Tests

Phase 1 should add focused tests for:

- JSON round-trip of `FormulaDiagnostic` and `DiagnosticCondition`.
- Claim-local unsatisfiable formula produces `fatal`.
- Claim-local tautology produces `warning`.
- Redundant operands produce `info`.
- Cross-claim hard incompatibility produces `warning`, not `fatal`.
- Cross-claim incompatibility condition is `A and B`.
- Cross-claim entailment condition is `A and not B`.
- Disjoint formulas do not produce pairwise diagnostics.
- Unsupported quantifier or term formulas do not crash the API.
- Diagnostics can be consumed without constructing a `ReviewManifest`.

These tests should use compiled Gaia Lang fixtures where possible and direct IR
fixtures only for edge cases.

## 10. Later Phases

Phase B should add presentation only after the API stabilizes:

- `gaia inspect formula-graph`
- optional `gaia check --logic`
- JSON and human output for diagnostics

Phase C-rich can add deeper package reasoning:

- richer entailment indexing
- exact or approximate event probability queries
- support for finite grounded quantifiers where safe
- policy adapters that convert warnings into review tasks
- optional package-specific gates above the diagnostics API

None of these later features should change the first principle that claim-local
malformed logic can be fatal, while cross-claim logical tension remains a
reviewable warning unless a higher-level policy explicitly says otherwise.
