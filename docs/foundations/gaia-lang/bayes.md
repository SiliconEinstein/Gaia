---
status: current-canonical
layer: gaia-lang
since: v0.5
---

# Bayes Module

`gaia.lang.bayes` is the lifted authoring surface for model-data likelihood
updates. It decomposes the paper narrative into reviewable Gaia claims:

1. `parameter(variable, value)` declares the hypothesis shape.
2. `bayes.model(hypothesis, observable=..., distribution=...)` declares one
   predictive model helper for one hypothesis.
3. `observation(...)` records measured data, optionally with Normal additive
   noise.
4. `bayes.likelihood(data, model=..., against=[...])` computes likelihood
   factors and lowers them to existing IR `infer` strategies and deterministic
   exclusivity operators.

The Bayes module does not add IR knowledge types, BP factor types, or new
operator enums. `PredictiveModel` and `Likelihood` are action-shaped runtime
objects; their helper claims carry `metadata["bayes"]["role"]` values
`"prediction"` and `"comparison"` respectively. Both action subclasses go
through the standard action lowering pipeline (see
[knowledge-and-reasoning.md §4](knowledge-and-reasoning.md#4-action-lowering)),
share the package-wide `action_label_map`, and emit warrant helper Claims
that are addressable via `[@label]` references. Specs:
[Bayes Module Design](../../specs/2026-05-04-bayes-module-design.md),
[Bayes Actions Design](../../specs/2026-05-05-bayes-actions-design.md).

## Import Surface

Prefer the namespace import:

```python
from gaia.lang import bayes

dist = bayes.Binomial(n=395, p=0.75)
```

`from gaia.lang import predict` is the core Bayes-free prediction verb (a
`Support` action). The legacy `bayes.predict(...)` function is kept as a
deprecation alias for `bayes.model(...)` and emits `DeprecationWarning`;
new packages should call `bayes.model(...)` directly.

The v1 distribution set is:

- `Binomial`, `Poisson`
- `Normal`, `Beta`, `Exponential`, `LogNormal`, `StudentT`, `Cauchy`, `Gamma`,
  `ChiSquared`

Each distribution delegates numeric evaluation to `scipy.stats`. Parameters may
be concrete numbers or `Variable` objects (PR #505). Deferred variable parameters
are resolved by the compiler from hypothesis formulas; their serialized
descriptors are audit metadata, not identity keys.

## Verbs at a Glance

```python
bayes.model(
    hypothesis: Claim,
    *,
    observable: Variable,
    distribution: Distribution,
    background: list[Knowledge] | None = None,
    rationale: str = "",
    label: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> Claim                               # returns the prediction helper claim

bayes.likelihood(
    data: Claim | list[Claim] | tuple[Claim, ...],
    *,
    model: Claim,
    against: Claim | list[Claim] | tuple[Claim, ...] = (),
    background: list[Knowledge] | None = None,
    rationale: str = "",
    label: str | None = None,
    exclusivity: str = "pairwise_contradiction",
    precomputed: dict[Claim, float] | None = None,
    metadata: dict[str, Any] | None = None,
) -> Claim                               # returns the comparison helper claim
```

`exclusivity` accepts:

- `"none"` — no relation operators emitted; all listed hypotheses are
  independent.
- `"pairwise_contradiction"` (default) — listed hypotheses are *at most one
  true*; emits a reviewable `Contradict` action for each pair that does not
  already have one.
- `"exhaustive_pairwise_complement"` — listed hypotheses are *exactly one
  true*; emits a reviewable `Exclusive` action when there are two
  hypotheses, or pairwise `Contradict` actions plus a clamped disjunction
  helper when there are three or more.

All emitted relation actions are auto-generated only when the equivalent
explicit author action does not already exist; this lets the author
override the structural pattern by writing the relation by hand.

## Worked Example

```python testable
from gaia.bp.exact import exact_inference
from gaia.bp.lowering import lower_local_graph
from gaia.lang import Nat, Probability, Variable, bayes, observation, parameter
from gaia.lang.compiler.compile import compile_package_artifact
from gaia.lang.runtime.knowledge import _current_package
from gaia.lang.runtime.package import CollectedPackage

pkg = CollectedPackage(name="bayes_doc_mendel_pkg", namespace="docs")
token = _current_package.set(pkg)
try:
    theta = Variable(symbol="theta", domain=Probability)
    k = Variable(symbol="k", domain=Nat, value=295)

    h_3_1 = parameter(theta, 0.75, content="theta = 0.75.", prior=0.5, label="h_3_1")
    h_null = parameter(theta, 0.5, content="theta = 0.5.", prior=0.5, label="h_null")
    data = observation(count=k, content="Observed k = 295.", prior=0.999, label="data")
    model_3_1 = bayes.model(
        h_3_1,
        observable=k,
        distribution=bayes.Binomial(n=395, p=theta),
        label="f2_model_3_1",
    )
    model_null = bayes.model(
        h_null,
        observable=k,
        distribution=bayes.Binomial(n=395, p=theta),
        label="f2_model_null",
    )
    comparison = bayes.likelihood(
        data,
        model=model_3_1,
        against=[model_null],
        exclusivity="exhaustive_pairwise_complement",
        label="f2_likelihood",
    )
finally:
    _current_package.reset(token)

compiled = compile_package_artifact(pkg)
beliefs, _ = exact_inference(lower_local_graph(compiled.graph))
h_3_1_id = compiled.knowledge_ids_by_object[id(h_3_1)]
h_null_id = compiled.knowledge_ids_by_object[id(h_null)]
comparison_id = compiled.knowledge_ids_by_object[id(comparison)]

odds = beliefs[h_3_1_id] / beliefs[h_null_id]
assert odds > 40.0
assert beliefs[h_3_1_id] > 0.95
assert beliefs[h_null_id] < 0.03
assert beliefs[comparison_id] > 0.99
```

`exclusivity="exhaustive_pairwise_complement"` means exactly one listed
hypothesis is true. For the default `pairwise_contradiction`, the listed
hypotheses are only "at most one true", so pairwise odds are meaningful but the
listed marginals need not sum to one.

The realistic Mendel pipeline produces an unclamped Bayes factor of roughly
`exp(50.3) ≈ 7×10²¹`, which the Cromwell clamp on individual likelihood factors
caps at pairwise odds of ≈498 (`p1_null` is clamped to ε). Authors who need to
**rank** hypotheses always get the correct ordering; authors who need
**calibrated** Bayes factors at this magnitude should read
`comparison.metadata["bayes"]["likelihoods"]` directly. The `> 40.0` lower bound
in the assertion above is intentionally loose: any clamp ceiling above the
discrimination threshold satisfies it. See the spec §4.3 "realistic Mendel"
worked example for full numbers.

## Lowering Contract

For each hypothesis `H_i`, the compiler binds deferred distribution parameters
from `H_i.formula`, evaluates `log P(data | H_i)`, normalizes likelihood ratios
against the maximum log likelihood, and emits one existing IR `infer` strategy:

```text
premises = [H_i]
conclusion = model_preference helper
conditional_probabilities = [0.5, clamp(exp(logL_i - logL_max))]
```

The raw log likelihood table is preserved on the compiled comparison claim at
`metadata["bayes"]["likelihoods"]`.

Exclusivity is structural:

- `"none"` emits no relation operators.
- `"pairwise_contradiction"` creates reviewable pairwise `Contradict` actions
  when they do not already exist.
- `"exhaustive_pairwise_complement"` creates a reviewable `Exclusive` action for
  two hypotheses, or pairwise `Contradict` actions plus a clamped disjunction
  helper for three or more.

All of these are rigid operators. Probability lives only in claim priors and
`infer` CPTs.

## Noise And Escape Hatch

`observation(..., noise=bayes.Normal(mu=0, sigma=sigma))` stores a Normal
additive measurement-noise model in `metadata["bayes"]["noise"]`. The compiler
convolves the predictive distribution with that noise model before computing
the likelihood.

For custom likelihood calculations, pass runtime Claim objects as keys:

```python
comparison = bayes.likelihood(
    data,
    model=model_3_1,
    against=[model_null],
    precomputed={h_3_1: -1.2, h_null: -5.1},
)
```

The compiler converts those runtime object references to QIDs in IR metadata.
Runtime objects do not expose stable `.id` or `.qid` fields.

## Check Rules

`gaia check` reports Bayes-specific diagnostics:

- `bayes:dangling-prediction`
- `bayes:unobserved-prediction-target`
- `bayes:hypothesis-prior-coherence`
- `bayes:likelihood-without-data`
- `bayes:infer-likelihood-overlap`

The first two are warnings. Prior-coherence and missing-data diagnostics are
hard errors because they change the meaning of the compiled likelihood update.

`bayes:hypothesis-prior-coherence` sums hypothesis priors as recorded in the
compiled IR. `gaia check` applies `priors.py` before compilation, so sidecar
priors are visible to this rule once injected into metadata. Hypotheses with no
Claim prior and no `priors.py` entry contribute `0.5` to the sum.
