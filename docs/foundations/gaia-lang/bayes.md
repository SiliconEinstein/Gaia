---
status: current-canonical
layer: gaia-lang
since: v0.5
---

# Bayes Module And Continuous Quantities

Gaia provides **two complementary mental models** for handling continuous
parameters and observations. Pick the one that matches your scientific
question:

| You want to … | Use this surface | Mental model |
|---|---|---|
| Compare competing parameter-value hypotheses (Mendel 3:1 vs 1:1, Galileo Model A vs Model B) | `gaia.lang.bayes` (this module) — `bayes.model` + `bayes.likelihood` | **Hypothesis comparison** via likelihood ratios |
| Estimate a single uncertain quantity and ask threshold / simple equation questions about it (`T_c > 100 K`, `y == baseline + slope * x`) | `Distribution` + `claim(content, predicate)` + `observe(dist, value, error)` | **Quantity with predicates** via generated prior records and equation metadata |

Both surfaces ride on the same scipy-backed distribution machinery
(``gaia.lang.bayes.distributions``); the difference is the authoring shape
and the lowering target. They can coexist freely in one package — for
example, a paper might use `bayes.likelihood` for the central hypothesis
test while declaring `Normal`-distributed quantities for nuisance
measurements.

## Hypothesis comparison surface (existing v0.5)

`gaia.lang.bayes` is the lifted authoring surface for model-data likelihood
updates. It decomposes the paper narrative into reviewable Gaia claims:

1. `parameter(variable, value)` declares the hypothesis shape.
2. `bayes.model(hypothesis, observable=..., distribution=...)` declares one
   predictive model helper for one hypothesis.
3. A formula `claim(...)` plus zero-premise `observe(...)` records measured
   data, optionally with Normal additive noise metadata.
4. `bayes.likelihood(data, model=..., against=[...])` computes likelihood
   factors and lowers them to existing IR `infer` strategies and deterministic
   exclusivity operators.

The Bayes module does not add IR knowledge types, BP factor types, or new
operator enums. `PredictiveModel` and `Likelihood` are action-shaped runtime
objects; their helper claims carry `metadata["bayes"]["role"]` values
`"prediction"` and `"comparison"` respectively. Both action subclasses go
through the standard action lowering pipeline (see
[knowledge-and-reasoning.md](knowledge-and-reasoning.md)),
share the package-wide `action_label_map`, and emit warrant helper Claims
that are addressable via `[@label]` references. Historical design records live at
`docs/specs/2026-05-04-bayes-module-design.md` and
`docs/specs/2026-05-05-bayes-actions-design.md`.

## Import Surface

Prefer the namespace import:

```python
from gaia.lang import bayes

dist = bayes.Binomial(n=395, p=0.75)
```

Bayes models are authored through `bayes.model(...)`. There is no
`from gaia.lang import predict` core verb and no `bayes.predict(...)` alias in
v0.5; use `derive(...)` for ordinary support steps and `bayes.model(...)` when
declaring a predictive distribution for a hypothesis.

The v1 hypothesis-comparison distribution set is:

- `Binomial`, `BetaBinomial`, `Poisson`
- `Normal`, `Beta`, `Exponential`, `LogNormal`, `StudentT`, `Cauchy`, `Gamma`,
  `ChiSquared`

Each distribution delegates numeric evaluation to `scipy.stats`. Parameters may
be concrete numbers or `Variable` objects (PR #505). Deferred variable parameters
are resolved by the compiler from hypothesis formulas; their serialized
descriptors are audit metadata, not identity keys.

`BetaBinomial(n, alpha, beta)` delegates to `scipy.stats.betabinom`. It is the
minimal wrapper for a common model-comparison pattern: integrate
`Binomial(n, p)` over `p ~ Beta(alpha, beta)` instead of hand-writing a
precomputed likelihood. The Mendel example package uses
`BetaBinomial(n=395, alpha=1, beta=1)` for the diffuse `p ~ Uniform[0, 1]`
alternative, where every exact count has marginal likelihood `1 / (n + 1)`.

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
) -> Claim                               # returns the model helper claim

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
from gaia.engine.bp.exact import exact_inference
from gaia.engine.bp.lowering import lower_local_graph
from gaia.engine.lang import Constant, Nat, Probability, Variable, bayes, claim, equals, observe, parameter
from gaia.engine.lang.compiler.compile import compile_package_artifact
from gaia.engine.lang.runtime.knowledge import _current_package
from gaia.engine.lang.runtime.package import CollectedPackage

pkg = CollectedPackage(name="bayes_doc_mendel_pkg", namespace="docs")
token = _current_package.set(pkg)
try:
    theta = Variable(symbol="theta", domain=Probability)
    k = Variable(symbol="k", domain=Nat, value=295)

    h_3_1 = parameter(theta, 0.75, content="theta = 0.75.", prior=0.5, label="h_3_1")
    h_null = parameter(theta, 0.5, content="theta = 0.5.", prior=0.5, label="h_null")
    data = claim("Observed k = 295.", formula=equals(k, Constant(295, Nat)))
    observe(data, rationale="Observed k = 295.", label="observe_data")
    data.label = "data"
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

For measurement noise, store a Normal additive model on the observed claim:

```python
data = claim(
    "Observed y = 3.0.",
    formula=equals(y, Constant(3.0, Real)),
    metadata={"bayes": {"noise": bayes.Normal(mu=0, sigma=sigma).model_dump()}},
)
observe(data, rationale="Observed y = 3.0.", label="observe_data")
```

The compiler convolves the predictive distribution with that noise model before
computing the likelihood.

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

## Quantity-With-Predicate Surface (v0.6+)

The hypothesis-comparison surface above is verbose for a common scientific
pattern: *"I have one continuous parameter with prior uncertainty, and I want
to ask threshold or equation questions about it"*. The
**quantity-with-predicate** surface added in v0.6 collapses that pattern into
three concepts:

1. **Distribution** — a named continuous (or discrete) quantity with a prior
   distribution attached.
2. **`claim(content, BoolExpr)`** — a Claim whose proposition is an
   inequality (`k > 1e-2`) or arithmetic equation (`y == baseline + slope * x`) over
   Distributions.
3. **`observe(dist, value=v, error=σ)`** — records a measurement event for
   the quantity with optional noise.

The compiler computes the prior of an inequality predicate from the
underlying Distribution's CDF, Cromwell-clamps it, and registers a
``prior_records`` entry with ``source_id="continuous_inference"``. The
package's ResolutionPolicy writes the resolved value to ``metadata["prior"]``
before IR emission. This means generated CDF priors outrank the low-friction
``claim(prior=...)`` inline shortcut, while documented ``register_prior(...)``
author priors still override them.

### Worked example — H₃S high-temperature superconductivity

```python
from gaia.lang import Normal, claim, observe
from gaia.unit import q

# Declare T_c as a Distribution-typed continuous quantity with a unit-aware
# prior. Distribution factories accept either bare scalars or
# gaia.unit.Quantity values; mixing the two for location/scale parameters
# raises a clear error.
T_c = Normal("T_c of H3S at 200 GPa", mu=q(200, "K"), sigma=q(50, "K"))

# Record the published measurement (Drozdov et al. 2015) with its
# experimental uncertainty. observe() infers the unit from the target
# distribution and accepts compatible units (Celsius is auto-converted).
measurement = observe(T_c, value=q(203, "K"), error=q(5, "K"),
                      source_refs=["Drozdov 2015"])

# Predicate claim with a Quantity-typed threshold. The compiler checks that
# the threshold's unit is dimensionally compatible with the distribution's
# unit, converts it to the distribution's canonical unit, and computes the
# prior from T_c's CDF.
high_Tc = claim("H3S is a high-temperature superconductor", T_c > q(77, "K"))
# After compile: high_Tc.metadata["prior"] ≈ 0.993 in the emitted IR.
```

`high_Tc` enters BP as an ordinary Claim with a resolved numeric prior. Downstream
``derive`` / ``contradict`` / ``equal`` actions operate on it identically to
prose claims with hand-set priors.

The unit-typed Quantity flows through to IR — ``high_Tc.metadata['predicate']
['rhs']`` becomes ``{'kind': 'quantity', 'value': 77.0, 'unit': 'kelvin'}``,
visible to ``gaia check`` and downstream renderers without losing the unit.

### Equation claims — laws and tolerances

For simple algebraic equations, use the `==` operator and an explicit prior
expressing the author's belief in the law or model:

```python
from gaia.lang import Normal, claim

baseline = Normal("baseline response", mu=10, sigma=1)
slope = Normal("pressure coefficient", mu=2, sigma=0.5)
response = Normal("response at 10 GPa", mu=30, sigma=3)

# Hard equation (default tolerance=None). The author's prior reflects
# confidence in the equation/model, not a value derived from the operands.
linear_response = claim(
    "linear pressure response holds at 10 GPa",
    response == baseline + slope * 10,
    prior=0.85,
)

# Soft equation — tolerance metadata for future equation-lowering work.
linear_response_loose = claim(
    "linear pressure response approximately holds at 10 GPa",
    response == baseline + slope * 10,
    tolerance=0.1,
    prior=0.85,
)
```

The author's prior reflects belief in the *law/model* itself. The
distributions on each operand carry marginal uncertainty of the parameters.
Current PR1 lowering preserves the equation and optional tolerance in
metadata and registers a neutral 0.5 default when no prior source is present;
it does not yet propagate constraints between operands or derive a prior from
the equation.

### `observe(distribution, value, error)` — measurement events

`observe()` is polymorphic. With a Distribution target it records a
measurement event as a fresh Claim pinned to ``1 - CROMWELL_EPS`` (the
measurement happened) with metadata linking back to the Distribution:

```python
from gaia.lang import Normal, observe

T_c = Normal("T_c of H3S at 200 GPa", mu=200, sigma=50)

# Single measurement
m1 = observe(T_c, value=203, error=5, source_refs=["Drozdov 2015"])

# Replicated measurement (different group / instrument)
m2 = observe(T_c, value=205, error=4, source_refs=["Eremets 2016"])

# Custom non-Gaussian noise model (Distribution-typed error)
custom_noise = Normal("Bayesian-fit measurement noise", mu=0, sigma=4.5)
m3 = observe(T_c, value=204, error=custom_noise)
```

PR1 v0.6 stores observation events; the posterior CDF used for predicate
claim priors still uses the prior distribution (observation-aware posterior
update is a follow-up PR — see `gaia/lang/compiler/predicate_lowering.py`
``PREDICATE_LOWERING_SOURCE_ID`` docstring). Until then, predicate priors
reflect the prior CDF directly; observed measurement events are visible in
IR (and to `gaia check`) but do not yet update the predicate prior.

### Unit-aware parameters

Distribution factories accept ``gaia.unit.Quantity`` values via
``gaia.unit.q``. Per-distribution semantics (raise on mismatch):

| Family | Location/scale group | Dimensionless params | Unit-carrying rate |
|---|---|---|---|
| ``Normal``, ``StudentT``, ``Cauchy`` | mu, sigma / mu, gamma — must share a unit | (``df`` for StudentT) | n/a |
| ``Exponential`` | n/a | n/a | ``rate`` carries the *inverse* of the random variable's unit (e.g. ``rate=q(2, "1/s")`` for a lifetime in seconds) |
| ``Gamma`` | n/a | ``alpha`` | ``rate`` carries the *inverse* of the random variable's unit |
| ``Poisson`` | n/a | ``rate`` (lambda is the dimensionless expected count for the interval implied by the content string) | n/a |
| ``LogNormal``, ``Beta``, ``ChiSquared``, ``Binomial`` | n/a | All — pass bare scalars; encode the random variable's unit in the content string | n/a |

> **Migration (v0.6 breaking change for Poisson):** ``Poisson(rate=q(2, "1/s"))``
> from earlier v0.5/v0.6 snapshots is no longer accepted. Poisson's ``rate``
> parameter is the dimensionless expected count for whatever observation
> interval is implied by the content string. Use
> ``Poisson("events per second", rate=2)`` instead, encoding the interval in
> the name. The previous version surfaced ``metadata['unit'] = '1 / second'``,
> which made predicates like ``count > 5`` either fail dimensional checks or
> silently apply the inverse unit; the new behaviour is consistent with the
> mathematical convention that ``lambda`` is a pure number.

> **For Exponential / Gamma**: the rate carries the *inverse* of the random
> variable's unit. Authors writing ``Exponential("lifetime", rate=q(2, "1/s"))``
> get ``metadata['unit'] = 'second'`` (the lifetime's unit), so predicates
> like ``lifetime > q(1, "s")`` and observations like
> ``observe(lifetime, value=q(0.5, "s"))`` work directly. Earlier snapshots
> stored ``'1 / second'`` instead, which surfaced as a unit-compatibility
> error at predicate-lowering time.

Authors writing scientific code typically pair Quantity-typed distribution
parameters with Quantity-typed predicate thresholds and observation values:

```python
from gaia.lang import Normal, claim, observe
from gaia.unit import q

reaction_rate = Normal("k for reaction X", mu=q(1.0e-3, "1/s"), sigma=q(2.0e-4, "1/s"))
fast = claim("reaction is fast", reaction_rate > q(5.0e-4, "1/s"))
observe(reaction_rate, value=q(1.1e-3, "1/s"), error=q(1.0e-4, "1/s"))
```

Unitless distributions (``Normal("k", mu=0, sigma=1)``) continue to work with
bare scalar predicates / observations. Mixing the two — passing a Quantity
threshold against a unitless distribution, or vice versa — raises a clear
error rather than silently dropping the unit.

### Operator overloading rules

Distribution operator overloading mirrors the SymPy / NumPy convention:

| Expression | Returns | Use |
|---|---|---|
| `dist > x`, `dist >= x`, `dist < x`, `dist <= x` | `BoolExpr` | predicate proposition for `claim(content, expr)` |
| `dist == other`, `dist != other` | `BoolExpr` (op `==` / `!=`) | equation proposition for `claim(content, expr)` |
| `dist + x`, `dist - x`, `dist * x`, `dist / x`, `-dist` | `DerivedDistribution` | equation right-hand side; chain into deeper trees |
| `bool(dist > x)` | **TypeError** | Python truth-value coercion is rejected (mirrors NumPy / SymPy). The author probably meant `claim("…", dist > x)`. |

`__hash__` on Distribution and BoolExpr is identity-based (matching
`Variable` and `Claim`), so set / dict membership works even though `__eq__`
is overloaded to construct a BoolExpr. Use ``dist_a is dist_b`` for identity
checks, not ``dist_a == dist_b``.

### Choosing between the two surfaces

A rough decision rule:

- **Use the hypothesis-comparison surface (`bayes.model` + `bayes.likelihood`)
  when** your scientific question is "*which of these pre-specified parameter
  values is most consistent with the data?*". Examples: Mendel 3:1 vs 1:1,
  Galileo Model A (weight-speed) vs Model B (medium resistance), Higgs vs
  no-Higgs.
- **Use the quantity-with-predicate surface (`Distribution` + predicate)
  when** your scientific question is "*what's the uncertainty in this
  quantity, and does it satisfy this threshold / equation?*". Examples:
  T_c > 77 K, k > 10⁻² s⁻¹, H₀ = 67 ± 1 km/s/Mpc.

You can mix both — use Distribution-backed observations to feed evidence
that a `bayes.likelihood` comparison consumes.

### Compile-time diagnostics

Two warning categories surface common authoring mistakes / known limitations:

* `DeadContinuousQuantityWarning` — a `Distribution` was declared but never
  referenced in any claim's predicate / equation / observation. Catches
  typos like declaring `T_c2` and then writing `claim("...", T_c > q(77, "K"))`
  with the wrong identifier. Suppress with `warnings.filterwarnings("ignore",
  category=DeadContinuousQuantityWarning)` for intentional placeholders.

* `ObservationNotUpdatingPredicateWarning` — both `observe(d, value=..., error=...)`
  and `claim("...", d > c)` reference the same `Distribution`, but the
  predicate prior is currently computed from the prior CDF directly without
  incorporating the observation. This is a real correctness gap that the
  posterior-CDF work (tracked separately, see project issues) will close.
  Until then, use `register_prior(predicate_claim, value, justification=...)`
  to record a documented post-observation belief, or express the inference via
  `gaia.lang.bayes.likelihood()`. The inline `claim(prior=...)` shortcut is
  deliberately lower priority than the generated CDF prior and will not
  suppress this warning by itself.

Both warnings emit through `warnings.warn` so they appear in pytest output,
the Gaia CLI, and any standard `warnings.catch_warnings` capture. They are
non-fatal — packages compile successfully.

### Source code

- `gaia/lang/bayes/distributions/` — hypothesis-comparison distribution
  literals (`Binomial`, `BetaBinomial`, `Poisson`, continuous families) backed
  by `scipy.stats`
- `gaia/lang/runtime/distribution.py` — Distribution Knowledge wrapper
  + family factories (`Normal`, `LogNormal`, `Beta`, `Gamma`, `Exponential`,
  `StudentT`, `Cauchy`, `ChiSquared`, `Binomial`, `Poisson`)
- `gaia/lang/dsl/bool_expr.py` — `BoolExpr`, `DerivedDistribution`
- `gaia/lang/dsl/knowledge.py` — `claim(content, proposition, ...)` accepts
  BoolExpr propositions; routes equality to `metadata['equation']`,
  inequality to `metadata['predicate']`
- `gaia/lang/dsl/support.py` — `observe(distribution, value, error, ...)`
  polymorphism
- `gaia/lang/compiler/predicate_lowering.py` — predicate → generated
  `continuous_inference` prior record at compile time; equation → low-priority
  default neutral prior record
- `gaia/lang/compiler/distribution_diagnostics.py` — dead-quantity and
  observation-not-updating-predicate detectors
