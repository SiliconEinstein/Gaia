# Diagnostic Probabilities

> **Status:** Current canonical (v0.5 + logic diagnostics probability scoring, 2026-05-17)
>
> **定位：** 本页说明如何给 reviewer-facing logic warning 计算概率。上游
> formula logic 的作者/编译/诊断语义见
> [Formula Logic In Gaia Lang](../gaia-lang/formula-logic.md)。本页是 BP 层的
> 契约文档，不是完整 API reference；具体 signature 和 Pydantic 字段见
> [Python API Reference](../../reference/engine/index.md)。

Formula diagnostics answer a structural question:

```text
Which logic condition would be bad if it were active?
```

Diagnostic probabilities answer a different probabilistic question:

```text
Under the current belief graph, how much joint probability mass makes that
logic warning active?
```

This separation matters. A cross-claim hard-logic conflict is a review warning,
not a compile-time contradiction, because each claim can carry its own prior and
belief. The probability scorer ranks that warning by the joint belief that both
claims are currently true.

## 1. First-principles contract

Every probability is computed from a joint distribution over the variables in
the diagnostic condition:

```text
Pr(E) = sum_x q(x) * 1[E(x)]
```

where:

- `E` is the JSON Boolean event carried by `DiagnosticCondition.expression`.
- `q(x)` is a joint table over exactly the variables in the condition.
- `1[E(x)]` is 1 when the assignment satisfies the event and 0 otherwise.

Gaia deliberately does **not** recover diagnostic probabilities from marginal
beliefs. In particular, it does not use `P(A) * P(B)`, Frechet bounds, or an
independence assumption unless a provider explicitly returns a joint table whose
basis is factorized, such as mean-field's variational distribution.

No joint table means no diagnostic probability. Provider failures are returned
as explicit unavailable results rather than synthetic estimates.

## 2. Layer boundaries

| Layer | Responsibility |
|---|---|
| `inspect_formula_graphs(graph)` | Emits `FormulaDiagnostic` objects from compiled `FormulaGraph` structure. |
| `DiagnosticCondition` | Carries the Boolean event to score, such as `A and B`. |
| `lower_local_graph(graph)` | Builds the `FactorGraph` that represents the current belief model. |
| `belief_graph_for_formula_scoring(graph)` | Filters compiler-generated formula operators and lowers a reviewer-safe scoring graph. |
| `joint_over(...)` / `compare_joint_over(...)` | Produces method-specific joint distributions over the condition variables. |
| `event_probability(...)` | Sums the joint mass satisfying the event. |
| `score_diagnostic_conditions(...)` | Runs joint providers and returns per-method probabilities for each diagnostic condition. |
| Reviewer policy | Decides how to rank, display, suppress, or gate scored warnings. |

The diagnostics layer stays independent from BP. Probability scoring is an
optional downstream pass over diagnostics that already have a machine-readable
condition.

## 3. Warning vs fatal semantics

The logic diagnostics API distinguishes claim-local defects from cross-claim
tension:

| Situation | Operational status |
|---|---|
| One claim's own formula is internally unsatisfiable | `fatal` for that claim |
| Two different claims cannot both hold under hard formula logic | `warning` |
| A soft constraint is crossed | legal `warning` |

The probability scorer does not change severity. A high-probability warning is
still a warning; it is simply more important for a reviewer to inspect.

## 4. Choosing the belief graph to score

Score the diagnostic under the current belief graph, not under the formula
operators that generated the diagnostic itself.

For example, suppose two formula-bearing claims are logically incompatible. The
formula diagnostics layer may discover the warning by comparing their formula
graphs. If the same hard formula operators are also used as evidence in the
scoring graph, the bad event will be Cromwell-clamped close to zero because the
graph already encodes that the claims cannot jointly hold.

For reviewer prioritization, the more useful question is usually:

```text
How much current belief mass is assigned to the two incompatible claims both
being true before this warning is enforced as a hard correction?
```

That graph can still include independent priors, evidence, and probabilistic
associations between the claim variables. It should not include the warning
itself as conditioning evidence. Use `belief_graph_for_formula_scoring(...)`
for this common reviewer path.

## 5. Python DSL example

Use the CMB B-mode package from
[Formula Logic § Worked Physics Example](../gaia-lang/formula-logic.md#6-worked-physics-example)
as the source graph. That page owns the full claim/formula setup; this page
starts from the compiled artifact and focuses on scoring the emitted diagnostic:

```python
from gaia.engine.ir.logic import (
    belief_graph_for_formula_scoring,
    inspect_formula_graphs,
    score_diagnostic_conditions,
)
from gaia.engine.lang.compiler import compile_package_artifact

artifact = compile_package_artifact(pkg)
report = inspect_formula_graphs(artifact.graph)
factor_graph = belief_graph_for_formula_scoring(artifact.graph)

scored = score_diagnostic_conditions(
    report.diagnostics,
    factor_graph,
    methods=("exact", "junction_tree", "trw_bp", "mean_field"),
)
```

Formula diagnostics emit a `cross_claim_incompatibility` warning because:

```text
tensor interpretation = bmode_excess AND primordial_tensor
dust interpretation   = bmode_excess AND NOT primordial_tensor
```

The warning condition is:

```text
tensor_interpretation AND dust_interpretation
```

The `associate(...)` call models the current belief relation between the two
claim variables. With `P(tensor)=0.4`, `P(dust)=0.6`,
`P(tensor | dust)=0.5`, and `P(dust | tensor)=0.75`, the exact joint warning
probability is:

```text
P(tensor AND dust) = P(tensor | dust) * P(dust) = 0.5 * 0.6 = 0.3
P(tensor AND dust) = P(dust | tensor) * P(tensor) = 0.75 * 0.4 = 0.3
```

In the regression test for this contract, exact enumeration and junction tree
both return `0.3`; TRW-BP and mean-field return approximate joint estimates with
their method provenance attached.

## 6. Provider semantics

`score_diagnostic_conditions(...)` can compare several joint providers:

| Method | Basis | Exact? | Notes |
|---|---|---:|---|
| `exact` | `exact_joint_distribution` | yes | Brute-force enumeration; suitable for small condition scopes and tests. |
| `junction_tree` | `calibrated_clique_marginal` | yes | Uses a calibrated clique containing the requested variables; independent singleton graphs are handled as products of calibrated singleton priors. |
| `trw_bp` | `approximate_joint_distribution` | no | Uses an available factor-scope joint approximation when the requested variables sit inside a TRW factor belief. |
| `mean_field` | `variational_joint_distribution` | no | Uses the factorized variational joint defined by mean-field VI. |

Unavailable providers are not errors in comparison mode. They appear in the
`unavailable` list with a reason and diagnostics payload.

The current `score_diagnostic_conditions(...)` helper is intentionally simple:
it runs the requested providers once per scored diagnostic. Its cost model is
`O(number_of_scored_diagnostics * inference_cost(methods))`. Bulk reviewer
tools should either score a small candidate set or cache provider state in a
higher-level orchestration layer until Gaia grows a dedicated cached query
context.

## 7. Interpretation guidelines

- Use `exact_spread` to catch disagreements among exact providers. It should be
  zero or near numerical tolerance when both exact and junction tree are
  available.
- Use `spread` to see how far approximate providers are from each other and from
  exact providers.
- Treat a high diagnostic probability as a reviewer-priority signal, not as an
  automatic rejection.
- Keep claim text self-contained. If a warning involves scientific jargon, each
  participating claim should explain enough context for the reviewer to
  understand the conflict without chasing earlier package declarations.

## 8. Related docs and code

- [`../gaia-lang/formula-logic.md`](../gaia-lang/formula-logic.md) — formula-bearing claims, `FormulaGraph`, and logic diagnostics.
- [`../gaia-lang/predicate-logic.md`](../gaia-lang/predicate-logic.md) — variables, domains, predicates, and quantifiers used inside formulas.
- [`inference.md`](inference.md) — FactorGraph construction, priors, Cromwell clamp, and inference algorithms.
- [`potentials.md`](potentials.md) — FactorType potential definitions, including pairwise potentials.
- [`../gaia-ir/07-lowering.md`](../gaia-ir/07-lowering.md) — backend-facing lowering boundary.
- `gaia.engine.ir.logic.diagnostics` — formula diagnostics and `DiagnosticCondition`.
- `gaia.engine.ir.logic.probability` — event scoring and diagnostic probability results.
- `gaia.engine.bp.joint_query` — method-specific joint query providers.
