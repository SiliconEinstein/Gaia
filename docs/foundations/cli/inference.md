---
status: current-canonical
layer: cli
since: v5-phase-1
---

# Inference Pipeline

## Overview

`gaia infer` runs local belief propagation on a compiled package, using a review
sidecar to supply parameterization (priors and conditional probabilities).

Pipeline:

```
compiled IR + review sidecar
  -> resolve parameterization
  -> validate IR structure
  -> validate parameterization completeness
  -> lower to factor graph
  -> run BP
  -> output beliefs
```

Source: `gaia/cli/commands/infer.py`

## Review Sidecar Model

A review sidecar is a Python file that exports a `ReviewBundle` -- an ordered
list of review objects that parameterize the package's knowledge and strategies
without mutating the structural IR.

### ReviewBundle Structure

`ReviewBundle` (defined in `gaia/review/models.py`) contains:

| Field | Type | Default | Purpose |
|-------|------|---------|---------|
| `objects` | `list[ClaimReview \| GeneratedClaimReview \| StrategyReview]` | required | Ordered review entries |
| `source_id` | `str` | `"self_review"` | Identifies the parameterization source |
| `model` | `str \| None` | `None` | Model/agent that produced the review |
| `policy` | `str \| None` | `None` | Policy label |
| `config` | `dict \| None` | `None` | Arbitrary source configuration |

Review object types:

- **`ClaimReview`** -- assigns a prior probability to an author-visible claim
  Knowledge node. Created via `review_claim(subject, prior=..., judgment=...,
  justification=...)`.

- **`GeneratedClaimReview`** -- assigns a prior to a generated interface claim
  introduced during formalization (e.g. an abduction's
  `AlternativeExplanationForObs`). Addressed by the owning Strategy plus an
  interface `role` and `occurrence` index. Created via
  `review_generated_claim(subject, role, prior=..., occurrence=0)`.

- **`StrategyReview`** -- supplies conditional probabilities for parameterized
  strategies (`infer` / `noisy_and`). Formal strategies may carry judgments but
  no numeric parameters. Created via `review_strategy(subject,
  conditional_probability=..., conditional_probabilities=[...])`. Accepts
  exactly one of the two probability arguments.

### Minimal Example

```python
from my_package import claim_A, claim_B, strategy_AB
from gaia.review import ReviewBundle, review_claim, review_strategy

REVIEW = ReviewBundle(objects=[
    review_claim(claim_A, prior=0.7, judgment="credible"),
    review_claim(claim_B, prior=0.4),
    review_strategy(strategy_AB, conditional_probability=0.9),
])
```

### Discovery

Review sidecars are discovered by `load_gaia_review()` in
`gaia/cli/_reviews.py`:

1. **Single review:** `<package>/review.py` exports `REVIEW = ReviewBundle(...)`.
2. **Multi-review:** `<package>/reviews/<name>.py`, each exports `REVIEW`.
   Files named `__init__.py` are skipped.
3. If only one candidate exists, it is selected automatically.
4. If multiple candidates exist, `--review <name>` is required.
5. Duplicate review names across the two locations are an error.

### Resolution

`resolve_gaia_review()` converts runtime review objects into IR
parameterization records:

| Review Object | Resolved Record | How |
|---------------|----------------|-----|
| `ClaimReview` | `PriorRecord(knowledge_id, value, source_id)` | `knowledge_id` looked up via `compiled.knowledge_ids_by_object` (object identity) |
| `GeneratedClaimReview` | `PriorRecord` | Strategy resolved via `compiled.strategies_by_object`; `knowledge_id` looked up from `strategy.metadata["interface_roles"][role][occurrence]` |
| `StrategyReview` | `StrategyParamRecord(strategy_id, conditional_probabilities, source_id)` | Strategy resolved via `compiled.strategies_by_object`; `noisy_and` accepts a single `conditional_probability` (wrapped to list), `infer` requires `conditional_probabilities` list |

The resolver also builds a `ParameterizationSource` (with `source_id`, `model`,
`policy`, `config`, `created_at`) and a `ResolutionPolicy(strategy="source",
source_id=...)`.

Source: `gaia/cli/_reviews.py`

## Parameterization Validation

Before lowering, `validate_parameterization()` in `gaia/ir/validator.py` checks
completeness and correctness:

### Prior coverage

- Every non-private, non-structural-helper claim must have at least one
  `PriorRecord`.
- Claims excluded from PriorRecord requirements (and **prohibited** from having
  one):
  - **Structural helper claims** -- conclusions of top-level Operators with
    structural types (`CONJUNCTION`, `DISJUNCTION`, `EQUIVALENCE`,
    `CONTRADICTION`, `COMPLEMENT`). Their truth values are fully determined by
    the Operator.
  - **FormalExpr private nodes** -- operator conclusions inside a `FormalExpr`
    that are not in the owning `FormalStrategy`'s premises/conclusion interface.
- Generated public interface claims (e.g. abduction's
  `AlternativeExplanationForObs`) remain ordinary claims and require
  `PriorRecord`.

### Strategy parameter coverage

- Every parameterized strategy (`infer`, `noisy_and`) must have a
  `StrategyParamRecord`.
- `infer`: requires `2^k` entries in `conditional_probabilities` (k = number of
  premises, one entry per premise truth-value combination).
- `noisy_and`: requires exactly 1 entry.
- `FormalStrategy` types (deduction, elimination, mathematical_induction,
  case_analysis, abduction, analogy, extrapolation) derive behavior from
  `FormalExpr` operators -- no independent `StrategyParamRecord`.

### Cromwell's rule

All probability values are clamped to `[EPS, 1-EPS]` where
**`CROMWELL_EPS = 1e-3`** (defined in `gaia/ir/parameterization.py`). The
validator rejects any value outside these bounds.

Reference: [Parameterization](../gaia-ir/06-parameterization.md)

## Lowering to Factor Graph

`lower_local_graph()` in `gaia/bp/lowering.py` converts a
`LocalCanonicalGraph` into a `FactorGraph` suitable for BP.

### Variable nodes

Each `type=claim` Knowledge becomes a variable node with its resolved prior.
Relation-conclusion claims (conclusions of `EQUIVALENCE`, `CONTRADICTION`,
`COMPLEMENT`, `DISJUNCTION` operators) default to `1 - CROMWELL_EPS` if no
explicit prior is provided.

### Factor types

The `FactorType` enum (`gaia/bp/factor_graph.py`) defines 8 factor types:

| FactorType | Parameters | Arity constraint |
|------------|-----------|-----------------|
| `IMPLICATION` | none (deterministic) | exactly 1 premise |
| `CONJUNCTION` | none (deterministic) | 2+ premises |
| `DISJUNCTION` | none (deterministic) | 2+ premises |
| `EQUIVALENCE` | none (deterministic) | exactly 2 premises |
| `CONTRADICTION` | none (deterministic) | exactly 2 premises |
| `COMPLEMENT` | none (deterministic) | exactly 2 premises |
| `SOFT_ENTAILMENT` | `p1`, `p2` (require `p1 + p2 > 1`) | exactly 1 premise |
| `CONDITIONAL` | `cpt` (length `2^k`) | 1+ premises |

Deterministic factors use Cromwell-softened potentials (`HIGH = 1 - EPS`,
`LOW = EPS`) rather than hard 0/1.

### Strategy lowering

Strategies are lowered by type:

**`infer`** (default path): becomes a single `CONDITIONAL` factor with the full
CPT from `StrategyParamRecord`. When `infer_use_degraded_noisy_and=True`, falls
back to `CONJUNCTION + SOFT_ENTAILMENT` using only the all-true/all-false CPT
entries (information loss for general CPTs).

**`noisy_and`**: decomposed into `CONJUNCTION + SOFT_ENTAILMENT`. For a single
premise, only `SOFT_ENTAILMENT` is emitted (no conjunction needed). Parameters:
`p1` = the conditional probability value, `p2 = 1 - CROMWELL_EPS`.

**Named formal types** (deduction, elimination, mathematical_induction,
case_analysis, abduction, analogy, extrapolation): auto-formalized via
`formalize_named_strategy()` before lowering. The resulting `FormalStrategy` is
then expanded: each operator in the `FormalExpr` becomes a deterministic factor,
and generated intermediate/interface claims become variable nodes.

**`FormalStrategy`** (pre-formalized): each operator in `formal_expr.operators`
is lowered to a deterministic factor via the `_OPERATOR_MAP`:

```
OperatorType.IMPLICATION   -> FactorType.IMPLICATION
OperatorType.CONJUNCTION   -> FactorType.CONJUNCTION
OperatorType.DISJUNCTION   -> FactorType.DISJUNCTION
OperatorType.EQUIVALENCE   -> FactorType.EQUIVALENCE
OperatorType.CONTRADICTION -> FactorType.CONTRADICTION
OperatorType.COMPLEMENT    -> FactorType.COMPLEMENT
```

**`CompositeStrategy`**: recursively lowers each sub-strategy.

Reference: [Lowering](../gaia-ir/07-lowering.md)

## Belief Propagation

### Algorithm

Sum-product loopy BP, implemented in `gaia/bp/bp.py` as `BeliefPropagation`.

Each iteration performs a synchronous sweep:

1. Compute all variable-to-factor messages (exclude-self product rule).
2. Compute all factor-to-variable messages (marginalization over
   `evaluate_potential()`).
3. Damp both message sets: `msg = alpha * new + (1 - alpha) * old`, then
   normalize.
4. Compute beliefs: `b(v) = normalize(prior(v) * product of f2v messages)`.
   Output belief = `b(v)[1]` (i.e. `P(x=1)`).
5. Check convergence: stop when `max|new_belief - old_belief| < threshold`.

### Default Parameters

As invoked by `gaia infer` (`gaia/cli/commands/infer.py` line 102):

| Parameter | Value | Description |
|-----------|-------|-------------|
| `damping` | **0.5** | Blending coefficient alpha in (0, 1]. 1.0 = full replacement (fast, may oscillate). 0.5 = half-step (balanced stability). |
| `max_iterations` | **100** | Upper bound on sweep iterations |
| `convergence_threshold` | **1e-6** | Stop when max absolute belief change falls below this |

### Convergence

BP stops early when the maximum belief change across all variables is below
`convergence_threshold`. If the budget of `max_iterations` is exhausted without
convergence, the result is returned with `diagnostics.converged = False`.

### Diagnostics

`BPDiagnostics` records:

- `converged` -- whether BP reached the convergence threshold
- `iterations_run` -- number of complete sweep iterations
- `max_change_at_stop` -- maximum belief change in the final iteration
- `belief_history` -- `{var_id: [belief_at_iter_0, belief_at_iter_1, ...]}` per
  variable, where `iter_0` is the initial belief from the prior
- `direction_changes` -- `{var_id: count}` of sign reversals in belief deltas
  (high counts indicate oscillation)

## Output Format

All output is written to `.gaia/reviews/<review_name>/` under the package
directory.

### `parameterization.json`

The resolved parameterization input, produced by
`ResolvedGaiaReview.to_json()`:

```json
{
  "ir_hash": "sha256:...",
  "review_content_hash": "sha256:...",
  "gaia_lang_version": "0.2.7",
  "source": {
    "source_id": "self_review",
    "model": "agent-authored",
    "created_at": "2026-04-03T..."
  },
  "resolution_policy": {
    "strategy": "source",
    "source_id": "self_review"
  },
  "objects": [
    {
      "kind": "claim",
      "knowledge_id": "github:my_pkg::my_claim",
      "label": "my_claim",
      "judgment": "credible",
      "justification": "",
      "prior": 0.7,
      "metadata": null
    }
  ],
  "priors": [
    {
      "knowledge_id": "github:my_pkg::my_claim",
      "value": 0.7,
      "source_id": "self_review"
    }
  ],
  "strategy_params": [
    {
      "strategy_id": "lcs_...",
      "conditional_probabilities": [0.9],
      "source_id": "self_review"
    }
  ]
}
```

### `beliefs.json`

Posterior beliefs and BP diagnostics:

```json
{
  "ir_hash": "sha256:...",
  "gaia_lang_version": "0.2.7",
  "review_content_hash": "sha256:...",
  "beliefs": [
    {
      "knowledge_id": "github:my_pkg::my_claim",
      "label": "my_claim",
      "belief": 0.683
    }
  ],
  "diagnostics": {
    "converged": true,
    "iterations_run": 12,
    "max_change_at_stop": 3.2e-7,
    "treewidth": -1,
    "belief_history": {
      "github:my_pkg::my_claim": [0.7, 0.691, 0.685, "..."]
    },
    "direction_changes": {
      "github:my_pkg::my_claim": 0
    }
  }
}
```

The `beliefs` array is sorted by `knowledge_id` and includes only knowledge
nodes present in the compiled graph (internal auxiliary variables are excluded).

### Provenance fields

Both output files carry three provenance fields that let downstream commands
verify freshness and trace back to the producing environment:

| Field | Meaning |
|-------|---------|
| `ir_hash` | Content hash of the compiled IR these beliefs were produced against. Must match the current `.gaia/ir_hash` when `gaia render` / `gaia register` is invoked, else the artifact is considered stale. |
| `review_content_hash` | Canonical hash of the resolved review's inference-relevant content (sorted priors + sorted strategy params). `gaia render` re-resolves the current review sidecar and compares its hash with this stored value — a mismatch means the review was edited between `gaia infer` and `gaia render`, so beliefs no longer reflect the current sidecar. `ir_hash` alone cannot catch this because review priors and strategy params are not part of the IR. |
| `gaia_lang_version` | Which `gaia-lang` version's BP engine produced these beliefs. Useful for detecting numerical drift: the same `ir_hash` + same `review_content_hash` can still produce slightly different beliefs across gaia-lang patch releases when the BP engine is refined. |
