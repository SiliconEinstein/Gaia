# Joint Query Diagnostic Probability Design

**Status:** Draft for review
**Date:** 2026-05-17
**Branch:** `codex/joint-query-diagnostic-probability-design`
**Scope:** Gaia v0.5, BP-backed probability scoring for formula logic diagnostics
**Depends on:** PR #648, `gaia.engine.ir.logic.diagnostics`
**Non-goals:** No marginal fallback, no ad hoc independence assumption over posterior marginals, no policy that turns cross-claim warnings into fatal errors.

## 1. Goal

PR #648 added reviewer-facing formula logic diagnostics. Those diagnostics emit
machine-readable `DiagnosticCondition.expression` values such as:

- `A and B` for cross-claim incompatibility.
- `A and not B` for entailment violation.
- `(A and not B) or (B and not A)` for equivalence mismatch.

The next step is to compute the probability that each diagnostic condition is
active. The first-principles definition is:

```text
Pr(E) = sum_x q(x) * 1[E(x)]
```

where `q(x)` is a joint distribution over the variables in the condition. The
probability scorer should evaluate the event over a joint distribution. It
should not infer a joint distribution from independent marginals.

## 2. First Principles

Logic diagnostics and probabilistic inference must remain separate:

| Layer | Responsibility |
|---|---|
| `DiagnosticCondition` | Describes the Boolean bad event. |
| Joint query provider | Produces a joint distribution over a requested variable set. |
| Event scorer | Sums joint probability mass for assignments that satisfy the event. |
| Reviewer policy | Decides how to rank, display, or gate the scored diagnostics. |

The event scorer is exact relative to its input joint table. If the joint table
comes from an approximate inference method, the scored probability is the event
probability under that approximate joint distribution. That provenance must be
visible in the result.

The core invariant is:

```text
No joint table, no diagnostic probability.
```

The implementation must not use `P(A) * P(B)`, Frechet bounds, or any other
marginal-only substitute as a probability for a logic condition. Provider-defined
approximate joints are allowed only when the provider explicitly defines a joint
distribution, such as mean field's factorized variational `q`. Marginal-only
substitutes may be useful in separate exploratory analysis, but not in this
diagnostic probability contract.

## 3. Proposed Modules

Add two small modules:

```python
gaia.engine.bp.joint_query
gaia.engine.ir.logic.probability
```

`joint_query` owns inference-method-specific joint distribution providers.
`logic.probability` owns diagnostic-condition event evaluation and cross-method
comparison.

This keeps `gaia.engine.ir.logic.diagnostics` independent from BP. The formula
diagnostics API continues to report structure. Probability scoring is an
optional downstream pass.

## 4. Data Models

### 4.1 Joint Distribution

```python
JointQueryMethod = Literal[
    "exact",
    "junction_tree",
    "trw_bp",
    "mean_field",
]

JointDistributionBasis = Literal[
    "exact_joint_distribution",
    "calibrated_clique_marginal",
    "approximate_joint_distribution",
    "variational_joint_distribution",
]


class JointDistribution(BaseModel):
    variables: list[str]
    probabilities: list[float]
    method: JointQueryMethod
    is_exact: bool
    basis: JointDistributionBasis
    diagnostics: dict[str, Any] = Field(default_factory=dict)
```

`probabilities` uses the same bit-index convention as
`exact_joint_over(graph, free_vars)`:

```text
index = sum(value_i << i for i, value_i in enumerate(variables))
```

For `variables=["A", "B"]`:

| Index | Assignment |
|---:|---|
| 0 | `A=0, B=0` |
| 1 | `A=1, B=0` |
| 2 | `A=0, B=1` |
| 3 | `A=1, B=1` |

### 4.2 Unavailable Results

Cross-method comparison should not fail because one provider cannot produce a
joint table. Use an explicit unavailable result:

```python
class JointQueryUnavailable(BaseModel):
    variables: list[str]
    method: JointQueryMethod
    reason: str
    diagnostics: dict[str, Any] = Field(default_factory=dict)
```

This is distinct from a probability value. A method that cannot provide a joint
distribution must not emit a synthetic estimate.

### 4.3 Condition Probability

```python
class ConditionProbabilityEstimate(BaseModel):
    method: JointQueryMethod
    probability: float
    is_exact: bool
    basis: JointDistributionBasis
    diagnostics: dict[str, Any] = Field(default_factory=dict)


class DiagnosticProbability(BaseModel):
    diagnostic_code: str | None = None
    condition_kind: str
    variables: list[str]
    event_expression: dict[str, Any]
    estimates: list[ConditionProbabilityEstimate] = Field(default_factory=list)
    unavailable: list[JointQueryUnavailable] = Field(default_factory=list)
    spread: float | None = None
    exact_spread: float | None = None
```

`spread` is `max(estimates.probability) - min(estimates.probability)` across
all available methods. `exact_spread` is the same computation restricted to
`is_exact=True` estimates, useful for catching implementation disagreement
between exact enumeration and junction tree.

## 5. Public API

### 5.1 Joint Query

```python
def joint_over(
    graph: FactorGraph,
    variables: Sequence[str],
    *,
    method: JointQueryMethod,
) -> JointDistribution:
    ...
```

The function either returns a normalized joint table for exactly the requested
variables or raises a controlled `JointQueryUnavailableError`.

```python
def compare_joint_over(
    graph: FactorGraph,
    variables: Sequence[str],
    *,
    methods: Sequence[JointQueryMethod] = (
        "exact",
        "junction_tree",
        "trw_bp",
        "mean_field",
    ),
) -> list[JointDistribution | JointQueryUnavailable]:
    ...
```

This helper collects unavailable providers instead of raising.

### 5.2 Condition Scoring

```python
def event_probability(
    expression: dict[str, Any],
    joint: JointDistribution,
) -> float:
    ...
```

This function evaluates the Boolean AST over every assignment in `joint` and
sums the probability mass for satisfying assignments.

```python
def score_condition(
    condition: DiagnosticCondition,
    joints: Sequence[JointDistribution | JointQueryUnavailable],
    *,
    diagnostic_code: str | None = None,
) -> DiagnosticProbability:
    ...
```

```python
def score_diagnostic_conditions(
    diagnostics: Sequence[FormulaDiagnostic],
    graph: FactorGraph,
    *,
    methods: Sequence[JointQueryMethod] = (
        "exact",
        "junction_tree",
        "trw_bp",
        "mean_field",
    ),
) -> list[DiagnosticProbability]:
    ...
```

`score_diagnostic_conditions` skips diagnostics without a condition and returns
one probability report for each condition-bearing diagnostic.

## 6. Joint Provider Semantics

### 6.1 Exact Enumeration

Use the existing `exact_joint_over(graph, variables)`.

- `basis="exact_joint_distribution"`
- `is_exact=True`
- Failure mode: too many variables for brute-force enumeration.

This method marginalizes the full factor-graph joint distribution to the
requested variables. It is the reference implementation for small graphs.

### 6.2 Junction Tree

Use calibrated clique potentials from `JunctionTreeInference`.

The first implementation may expose a lower-level helper that returns the
calibrated cliques, then `joint_over(..., method="junction_tree")` should:

1. Run junction tree calibration.
2. Find a calibrated clique whose variable set contains the requested variables.
3. Marginalize that clique table down to the requested variables.
4. Normalize the result.

- `basis="calibrated_clique_marginal"`
- `is_exact=True`
- Failure mode: requested variables are not contained in a single available
  calibrated clique.

The single-clique limitation is acceptable for the first pass because many
diagnostic events involve one or two claims. A later implementation can add
general clique-tree marginal queries for arbitrary variable subsets.

### 6.3 Mean Field

Run `MeanFieldVI` and use the variational distribution:

```text
q(x_1, ..., x_k) = product_i q_i(x_i)
```

This is not a marginal fallback from arbitrary posterior beliefs. It is the
joint distribution defined by the mean-field approximation itself.

- `basis="variational_joint_distribution"`
- `is_exact=False`
- Failure mode: mean-field inference fails to converge or lacks a variable.

The result should include convergence diagnostics and method metadata.

### 6.4 TRW-BP

TRW-BP should only return a joint table when it can construct one from its own
approximate inference state.

First implementation target:

- If the requested variables are contained in a factor scope, construct a
  normalized factor-scope pseudo-joint from the converged messages and
  marginalize to the requested variables.
- Otherwise return `JointQueryUnavailable`.

- `basis="approximate_joint_distribution"`
- `is_exact=False`

The implementation must not multiply final single-variable beliefs to create a
TRW joint table. If TRW cannot expose a method-consistent pseudo-joint for the
requested scope, it is unavailable for that query.

## 7. Event Expression Evaluation

Supported Boolean AST shapes are the phase-1 diagnostic condition shapes:

```json
{"var": "A"}
{"op": "not", "arg": {"var": "A"}}
{"op": "and", "args": [{"var": "A"}, {"var": "B"}]}
{"op": "or", "args": [{"var": "A"}, {"var": "B"}]}
```

Evaluation rules:

- A variable must appear in `joint.variables`.
- `not` requires exactly one `arg`.
- `and` and `or` require non-empty `args`.
- Unknown operators raise a validation error.
- The event probability is the sum of all assignment probabilities where the
  expression evaluates true.

This evaluator should live outside `diagnostics.py` so the structural
diagnostics module remains BP-free.

## 8. Cross-Check Output

For a condition such as `A and B`, the scored output should preserve per-method
provenance:

```json
{
  "diagnostic_code": "cross_claim_incompatibility",
  "condition_kind": "joint_incompatibility",
  "variables": ["A", "B"],
  "event_expression": {
    "op": "and",
    "args": [{"var": "A"}, {"var": "B"}]
  },
  "estimates": [
    {
      "method": "exact",
      "probability": 0.071,
      "is_exact": true,
      "basis": "exact_joint_distribution"
    },
    {
      "method": "junction_tree",
      "probability": 0.071,
      "is_exact": true,
      "basis": "calibrated_clique_marginal"
    },
    {
      "method": "mean_field",
      "probability": 0.119,
      "is_exact": false,
      "basis": "variational_joint_distribution"
    }
  ],
  "unavailable": [
    {
      "method": "trw_bp",
      "variables": ["A", "B"],
      "reason": "no converged factor-scope joint contains all query variables"
    }
  ],
  "spread": 0.048,
  "exact_spread": 0.0
}
```

High spread is a reviewer signal about inference-method sensitivity. It is not
itself a logic contradiction.

## 9. Reviewer Semantics

Scored probabilities refine warning priority; they do not change the
underlying diagnostic severity.

- Claim-local `fatal` diagnostics remain fatal because the formula is
  structurally malformed.
- Cross-claim incompatibility remains a warning, even when its bad-event
  probability is high.
- Soft-constraint violations remain legal warnings.
- Reviewer or package policy may rank high-probability warnings first, but that
  policy lives above the scoring API.

## 10. Error Handling

Use controlled failure modes:

- Missing variable in factor graph: unavailable for that method.
- Unsupported expression shape: validation error in the event scorer.
- Provider cannot construct a joint table: `JointQueryUnavailable`.
- Provider numerical failure: unavailable with diagnostics.
- Joint table not normalized within tolerance: validation error.

`compare_joint_over` should collect provider-level unavailability so one failed
method does not hide other useful estimates.

## 11. Testing

Add focused tests in two groups.

### 11.1 Joint Query Tests

- `exact` wraps `exact_joint_over` and preserves bit ordering.
- `junction_tree` matches `exact` on small graphs where both can answer.
- `mean_field` returns a normalized variational joint and records
  `is_exact=False`.
- `trw_bp` returns unavailable when no factor-scope pseudo-joint is available.
- Unknown variables produce controlled unavailable results.

### 11.2 Diagnostic Probability Tests

- `event_probability` computes `P(A and B)` from an explicit joint table.
- `event_probability` computes `P(A and not B)`.
- `event_probability` computes `(A and not B) or (B and not A)`.
- `score_condition` refuses missing variables rather than using marginals.
- `score_diagnostic_conditions` scores #648-style cross-claim diagnostics.
- Cross-method output includes `spread`, `exact_spread`, and unavailable
  provider records.

## 12. Rollout Plan

The design should be implemented as one focused PR after this spec is reviewed:

1. Add data models and explicit joint-table event evaluator.
2. Add `exact` and `mean_field` joint providers.
3. Add junction-tree calibrated-clique provider.
4. Add conservative TRW provider or explicit unavailable path.
5. Add diagnostic-condition scoring and cross-method comparison.
6. Add tests and export only the stable public API.

The first PR should avoid CLI or review-manifest integration. Once the scoring
contract is stable, a later B-lite PR can expose these probabilities in
`gaia check --logic` or reviewer output.
