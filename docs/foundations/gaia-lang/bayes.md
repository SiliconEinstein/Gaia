---
status: stable
layer: gaia-lang
since: v0.5
---

# Bayes Module And Continuous Quantities

Gaia provides **one unified surface** for statistical reasoning. Three
verbs handle hypothesis comparison, and Distribution-as-Knowledge gives
you both the predictive distributions for that surface and the
quantity-with-predicate authoring style (`T_c > 77 K`).

| You want to … | Verbs / types | Mental model |
|---|---|---|
| Compare competing parameter-value hypotheses (Mendel 3:1 vs 1:1, Galileo Model A vs Model B) | `model(...) / observe(Variable, ...) / compare(...)` | Hypothesis comparison via likelihood ratios |
| Estimate a single uncertain quantity and ask threshold / simple equation questions (`T_c > 100 K`, `y == baseline + slope * x`) | `Distribution(...) > value` predicate proposition + `observe(distribution, value=, error=)` | Quantity with predicates via generated prior records and equation metadata |

Both reach the same scipy-backed numeric backend
(`gaia.engine.bayes.distributions`, internal). The difference is only
the authoring shape and the lowering target. You can mix them freely in
one package — a paper might use `compare()` for the central hypothesis
test while declaring `Normal`-distributed quantities for nuisance
measurements.

## Hypothesis comparison surface

`gaia.engine.bayes` is the lifted authoring surface for model-data
likelihood updates. It decomposes the paper narrative into reviewable
Gaia claims:

1. `parameter(variable, value)` declares the hypothesis shape (one
   Variable taking one concrete value).
2. `model(hypothesis, observable=..., distribution=...)` declares a
   predictive distribution helper Claim that ties a hypothesis to a
   named random variable's predictive shape.
3. `observe(target, value=..., error=...)` records measured data with
   optional Distribution-typed noise — same verb that records
   continuous-quantity observations.
4. `compare(data, models=[...])` computes likelihood factors over the
   equal-positioned list of competing models and lowers them to
   existing IR `infer` strategies plus structural exclusivity operators.

The Bayes module adds no new IR knowledge types, BP factor types, or
operator enums. `Model` and `ModelComparison` are `BayesInference`
reasoning records; their helper Claims carry `metadata["model"]`
and `metadata["comparison"]` respectively. Both records go through the
standard action lowering pipeline (see
[knowledge-and-reasoning.md](knowledge-and-reasoning.md)), share the
package-wide `action_label_map`, and emit helper Claims that are
addressable via `[@label]` references. The design record is at
[`docs/specs/2026-05-17-bayes-unified-design.md`](../../specs/2026-05-17-bayes-unified-design.md).

## Import Surface

Prefer the canonical namespace import for the verbs:

```python
import gaia.engine.bayes as bayes
from gaia.engine.lang import Binomial, BetaBinomial, Normal, observe, parameter
```

Distribution factories live at `gaia.engine.lang` — the same factories
the quantity-with-predicate surface uses. The pydantic backends at
`gaia.engine.bayes.distributions` are internal; new code does not
import them directly.

The distribution set is:

- `Binomial`, `BetaBinomial`, `Poisson`
- `Normal`, `Beta`, `Exponential`, `LogNormal`, `StudentT`, `Cauchy`,
  `Gamma`, `ChiSquared`

Each distribution delegates numeric evaluation to `scipy.stats`.
Parameters may be concrete numbers or `Variable` objects (deferred
references resolved by the compiler from hypothesis formulas).

`BetaBinomial(n, alpha, beta)` is the integrate-`Binomial(n, p)` over
`p ~ Beta(alpha, beta)` predictive distribution. The Mendel example
uses `BetaBinomial(n=395, alpha=1, beta=1)` for the diffuse
`p ~ Uniform[0, 1]` alternative, where every exact count has marginal
likelihood `1 / (n + 1)`.

## Verbs at a Glance

`model` declares one predictive distribution helper Claim per
hypothesis; `compare` declares a model-preference helper Claim that
evaluates an equal-positioned list of predictive models against the
same observation and emits the chosen exclusivity contract. The full
parameter list, return types, and current defaults are auto-generated
on [`docs/reference/engine/bayes.md`](../../reference/engine/bayes.md);
the conceptual contract this foundation doc owns is the **`exclusivity`
contract** below.

`exclusivity` accepts:

- `"pairwise_contradiction"` (default) — listed hypotheses are *at most
  one true*; emits a reviewable `Contradict` action for each pair that
  does not already have one.
- `"exhaustive_pairwise_complement"` — listed hypotheses are *exactly
  one true*; emits a reviewable `Exclusive` action when there are two
  hypotheses, or pairwise `Contradict` actions plus a clamped
  disjunction helper when there are three or more.

`"none"` is rejected. The earlier escape hatch for suppressing
auto-emitted relations was removed; write the structural relation
explicitly and `compare()` will deduplicate same-type relations that
already exist.

All emitted relation actions are auto-generated only when the
equivalent explicit author action does not already exist; this lets the
author override the structural pattern by writing the relation by hand.

## Worked Example

```python testable
from gaia.engine.bp.exact import exact_inference
from gaia.engine.bp.lowering import lower_local_graph
import gaia.engine.bayes as bayes
from gaia.engine.lang import Binomial, Nat, Probability, Variable, observe, parameter
from gaia.engine.lang.compiler.compile import compile_package_artifact
from gaia.engine.lang.runtime.knowledge import _current_package
from gaia.engine.lang.runtime.package import CollectedPackage

pkg = CollectedPackage(name="bayes_doc_mendel_pkg", namespace="docs")
token = _current_package.set(pkg)
try:
    theta = Variable(symbol="theta", domain=Probability)
    k = Variable(symbol="k", domain=Nat)

    h_3_1 = parameter(theta, 0.75, content="theta = 0.75.", prior=0.5, label="h_3_1")
    h_null = parameter(theta, 0.5, content="theta = 0.5.", prior=0.5, label="h_null")
    data = observe(k, value=295, label="data", rationale="Observed k = 295.")
    model_3_1 = bayes.model(
        h_3_1,
        observable=k,
        distribution=Binomial("k under 3:1", n=395, p=theta),
        label="f2_model_3_1",
    )
    model_null = bayes.model(
        h_null,
        observable=k,
        distribution=Binomial("k under null", n=395, p=theta),
        label="f2_model_null",
    )
    comparison = bayes.compare(
        data,
        models=[model_3_1, model_null],
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

`exclusivity="exhaustive_pairwise_complement"` is the **default**
(2-model only): exactly one listed hypothesis is true, so posterior
marginals sum to one and the result is a standard Bayesian
model-selection posterior. `pairwise_contradiction` is the "at most one
true" mode; pairwise odds are still meaningful, but the marginals can
sum to less than one because the "all-false" joint state carries
probability mass — this is the open-world mode for incomplete model
coverage. `compare()` deduplicates against same-type external
`exclusive(...)` or `contradict(...)` declarations over the same
hypothesis pair, so authors who already declared the structural
action upstream (typically with their own rationale and background)
can simply omit the argument and let the default skip auto-emission.
Cross-type external structural actions are allowed to coexist —
`Exclusive` implies `Contradict`, so the IR's own consistency machinery
governs whether the combined graph is legal.

Currently `exhaustive_pairwise_complement` is only implemented for two
hypotheses. With three or more hypotheses, `compare()` raises
`NotImplementedError`; pass `exclusivity="pairwise_contradiction"`
explicitly (at-most-one semantics) until the N-ary Exclusive operator
lands.

The realistic Mendel pipeline produces an unclamped Bayes factor of
roughly `exp(50.3) ≈ 7×10²¹`, which the Cromwell clamp on individual
likelihood factors caps at pairwise odds of ≈498 (`p1_null` is clamped
to ε). Authors who need to **rank** hypotheses always get the correct
ordering; authors who need **calibrated** Bayes factors at this
magnitude should read `comparison.metadata["comparison"]["likelihoods"]`
directly.

## Lowering Contract

For each hypothesis `H_i`, the compiler binds deferred distribution
parameters from `H_i.formula` (the binding put there by
`parameter(variable, value)`), evaluates `log P(data | H_i)` against
the unified `metadata["observation"]` schema on the data Claim,
normalizes likelihood ratios against the maximum log likelihood, and
emits one IR `infer` strategy:

```text
premises = [H_i]
conclusion = model_preference helper
conditional_probabilities = [0.5, clamp(exp(logL_i - logL_max))]
```

The raw log likelihood table is preserved on the compiled comparison
claim at `metadata["comparison"]["likelihoods"]`.

Exclusivity is structural:

- `"pairwise_contradiction"` creates reviewable pairwise `Contradict`
  actions when they do not already exist.
- `"exhaustive_pairwise_complement"` creates a reviewable `Exclusive`
  action for two hypotheses, or pairwise `Contradict` actions plus a
  clamped disjunction helper for three or more.

The previous `"none"` escape hatch is rejected; explicit structural
relations are deduplicated instead.

All of these are rigid operators. Probability lives only in claim
priors and `infer` CPTs.

## Noise And External Solvers

For measurement noise, pass `error=` to `observe(...)`. A scalar is
sugared into a zero-mean Normal additive standard deviation; a
Distribution Knowledge object is used as-is:

```python
data_a = observe(y, value=3.0, error=sigma, label="data_a")               # scalar sugar
data_b = observe(y, value=3.0, error=Normal("σ_meas", mu=0, sigma=sigma)) # explicit
```

The compiler convolves the predictive distribution with the noise
model before computing the likelihood. Noise is always a Distribution
Knowledge object once it reaches the lowering — never a dict payload.

For externally computed likelihoods (PyMC SMC, Stan HMC, NumPyro VI,
scipy quadrature, custom MCMC), wrap the external call with the
standard `compute()` decorator and return a `PrecomputedLikelihoods`
Claim:

```python
from gaia.engine.lang import compute
from gaia.engine.bayes import PrecomputedLikelihoods

@compute
def stan_log_marginals(data, h_3_1, h_null) -> PrecomputedLikelihoods:
    # ... call your external solver ...
    return PrecomputedLikelihoods(
        log_likelihoods={h_3_1: -1.2, h_null: -5.1},
        diagnostics={"seed": 42, "r_hat_max": 1.001},
        solver="stan-nuts-4000",
    )

result = stan_log_marginals(data, h_3_1, h_null)
comparison = bayes.compare(data, models=[model_3_1, model_null], precomputed=result)
```

`compare(precomputed=...)` also accepts a bare `dict[Claim, float]` as
a back-of-the-envelope escape hatch:

```python
comparison = bayes.compare(
    data, models=[model_3_1, model_null],
    precomputed={h_3_1: -1.2, h_null: -5.1},
)
```

Wrappers should record at least a `seed` and a convergence statistic
(`r_hat_max` / `ess_min` / `divergences` / `abs_error_estimate` / ...)
in the `diagnostics` payload; `gaia build check` will warn on empty or
unrecognised-only diagnostics. A standalone PyMC integration demo lives
at `scripts/demo_v06_pymc_integration.py` (requires
`pip install pymc arviz`).

`PrecomputedLikelihoods` is intentionally a Bayes artifact, not Gaia's
universal evidence abstraction. It says "this external computation has been
interpreted as log-likelihoods for these hypotheses" and is consumed only by
`compare(precomputed=...)`. Raw simulation traces, clinical trial tables,
benchmark runs, and other evidence artifacts should keep their own provenance
and await a separate common evidence layer instead of being forced through this
Bayes-specific record.

### Wrapper pattern for fully-specified vs latent-bearing distributions

PyMC SMC, NumPyro NUTS, and similar samplers cannot run on a model with
no free parameters. Wrappers that handle both "point hypothesis" and
"distribution-marginalised hypothesis" cases must dispatch on whether
the predictive distribution has deferred Variable parameters:

```python
# Point hypothesis (p = 0.75 fixed) — closed-form, no sampler.
log_marg_point = stats.binom.logpmf(K, n=N, p=0.75)

# Latent-bearing hypothesis (p ~ Beta(1, 1)) — SMC integrates p out.
with pm.Model() as marginal_model:
    p = pm.Beta("p", alpha=1.0, beta=1.0)
    pm.Binomial("k", n=N, p=p, observed=K)
    trace = pm.sample_smc(draws=2000, chains=4, random_seed=42)
log_marg_marginal = float(trace.sample_stats.log_marginal_likelihood.mean().item())
```

See the spec §4.4 for the full pattern; `gaia build check` does not
detect this dispatch automatically.

## Check Rules

`gaia build check` reports Bayes-specific diagnostics:

- `bayes:dangling-model` — a `model(...)` helper not consumed by
  any `compare(...)`.
- `bayes:unobserved-model-observable` — a model observable Variable with
  no matching `observe(observable, value=...)` call.
- `bayes:hypothesis-prior-coherence` — listed hypothesis priors don't
  sum sensibly for the chosen exclusivity.
- `bayes:comparison-without-data` — `compare(...)` data Claim has no
  `metadata["observation"]` payload.
- `bayes:infer-comparison-overlap` — a hand-written `infer(...)`
  strategy collides with the Bayes-emitted comparison factor on the
  same `(hypothesis, data)` pair.
- `bayes:precomputed-solver-diagnostics-missing` —
  `compare(precomputed=PrecomputedLikelihoods(...))` where the Claim's
  `diagnostics` payload is empty or carries only unrecognised keys.

The first two and the last are warnings. Prior-coherence and missing
data are hard errors because they change the meaning of the compiled
likelihood update. Infer-comparison-overlap is a warning so authors
can decide whether the overlap is intentional.

`bayes:hypothesis-prior-coherence` sums hypothesis priors as recorded in
the compiled IR. `gaia build check` applies `priors.py` before
compilation, so sidecar priors are visible to this rule once injected
into metadata. Hypotheses with no Claim prior and no `priors.py` entry
contribute `0.5` to the sum.

## Quantity-With-Predicate Surface

> **Current but partial.** Predicate priors are computed from the prior
> distribution. Measurement events are recorded, but they do not yet
> update those predicate priors through a posterior CDF.

The hypothesis-comparison surface above is verbose for a common
scientific pattern: *"I have one continuous parameter with prior
uncertainty, and I want to ask threshold or equation questions about
it"*. The **quantity-with-predicate** surface collapses that pattern
into three concepts:

1. **Distribution** — a named continuous (or discrete) quantity with a
   prior distribution attached.
2. **`claim(content, BoolExpr)`** — a Claim whose proposition is an
   inequality (`k > 1e-2`) or arithmetic equation (`y == baseline +
   slope * x`) over Distributions.
3. **`observe(dist, value=v, error=σ)`** — records a measurement event
   for the quantity with optional noise. Same verb as the
   hypothesis-comparison surface uses for `observe(Variable, ...)`.

The compiler computes the prior of an inequality predicate from the
underlying Distribution's CDF, Cromwell-clamps it, and registers a
`prior_records` entry with `source_id="continuous_inference"`. The
package's ResolutionPolicy writes the resolved value to
`metadata["prior"]` before IR emission. Generated CDF priors outrank
the low-friction `claim(prior=...)` inline shortcut, while documented
`register_prior(...)` author priors still override them.

### Worked example — H₃S high-temperature superconductivity

```python
from gaia.engine.lang import Normal, claim, observe
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

`high_Tc` enters BP as an ordinary Claim with a resolved numeric
prior. Downstream `derive` / `contradict` / `equal` actions operate on
it identically to prose claims with hand-set priors.

The unit-typed Quantity flows through to IR —
`high_Tc.metadata['predicate']['rhs']` becomes
`{'kind': 'quantity', 'value': 77.0, 'unit': 'kelvin'}`, visible to
`gaia build check` and downstream renderers without losing the unit.

### Equation claims — laws and tolerances

For simple algebraic equations, use the `==` operator and an explicit
prior expressing the author's belief in the law or model:

```python
from gaia.engine.lang import Normal, claim

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
distributions on each operand carry marginal uncertainty of the
parameters. Current lowering preserves the equation and optional
tolerance in metadata and registers a neutral 0.5 default when no prior
source is present; it does not yet propagate constraints between
operands or derive a prior from the equation.

### `observe(distribution, value, error)` — measurement events

`observe()` is polymorphic: passing a `Distribution` target records a
measurement event as a fresh Claim pinned to `1 - CROMWELL_EPS` (the
measurement happened) with the unified `metadata["observation"]`
payload linking back to the Distribution:

```python
from gaia.engine.lang import Normal, observe

T_c = Normal("T_c of H3S at 200 GPa", mu=200, sigma=50)

# Single measurement
m1 = observe(T_c, value=203, error=5, source_refs=["Drozdov 2015"])

# Replicated measurement (different group / instrument)
m2 = observe(T_c, value=205, error=4, source_refs=["Eremets 2016"])

# Custom non-Gaussian noise model (Distribution-typed error)
custom_noise = Normal("Bayesian-fit measurement noise", mu=0, sigma=4.5)
m3 = observe(T_c, value=204, error=custom_noise)
```

The unified observation schema (`{target, value, noise, kind}`) is the
same shape `observe(Variable, value=, error=)` writes for the
hypothesis-comparison surface — one reader covers both. The
posterior CDF used for predicate-claim priors still uses the prior
distribution (observation-aware posterior update is follow-up work).

### Unit-aware parameters

Distribution factories accept `gaia.unit.Quantity` values via
`gaia.unit.q`. Per-distribution semantics (raise on mismatch):

| Family | Location/scale group | Dimensionless params | Unit-carrying rate |
|---|---|---|---|
| `Normal`, `StudentT`, `Cauchy` | mu, sigma / mu, gamma — must share a unit | (`df` for StudentT) | n/a |
| `Exponential` | n/a | n/a | `rate` carries the *inverse* of the random variable's unit (e.g. `rate=q(2, "1/s")` for a lifetime in seconds) |
| `Gamma` | n/a | `alpha` | `rate` carries the *inverse* of the random variable's unit |
| `Poisson` | n/a | `rate` (lambda is the dimensionless expected count for the interval implied by the content string) | n/a |
| `LogNormal`, `Beta`, `ChiSquared`, `Binomial`, `BetaBinomial` | n/a | All — pass bare scalars; encode the random variable's unit in the content string | n/a |

> **For Exponential / Gamma**: the rate carries the *inverse* of the
> random variable's unit. Authors writing
> `Exponential("lifetime", rate=q(2, "1/s"))` get
> `metadata['unit'] = 'second'` (the lifetime's unit), so predicates
> like `lifetime > q(1, "s")` and observations like
> `observe(lifetime, value=q(0.5, "s"))` work directly.

Authors writing scientific code typically pair Quantity-typed
distribution parameters with Quantity-typed predicate thresholds and
observation values:

```python
from gaia.engine.lang import Normal, claim, observe
from gaia.unit import q

reaction_rate = Normal("k for reaction X", mu=q(1.0e-3, "1/s"), sigma=q(2.0e-4, "1/s"))
fast = claim("reaction is fast", reaction_rate > q(5.0e-4, "1/s"))
observe(reaction_rate, value=q(1.1e-3, "1/s"), error=q(1.0e-4, "1/s"))
```

Unitless distributions (`Normal("k", mu=0, sigma=1)`) continue to work
with bare scalar predicates / observations. Mixing the two — passing a
Quantity threshold against a unitless distribution, or vice versa —
raises a clear error rather than silently dropping the unit.

### Operator overloading rules

Distribution operator overloading mirrors the SymPy / NumPy convention:

| Expression | Returns | Use |
|---|---|---|
| `dist > x`, `dist >= x`, `dist < x`, `dist <= x` | `BoolExpr` | predicate proposition for `claim(content, expr)` |
| `dist == other`, `dist != other` | `BoolExpr` (op `==` / `!=`) | equation proposition for `claim(content, expr)` |
| `dist + x`, `dist - x`, `dist * x`, `dist / x`, `-dist` | `DerivedDistribution` | equation right-hand side; chain into deeper trees |
| `bool(dist > x)` | **TypeError** | Python truth-value coercion is rejected (mirrors NumPy / SymPy). The author probably meant `claim("…", dist > x)`. |

`__hash__` on Distribution and BoolExpr is identity-based (matching
`Variable` and `Claim`), so set / dict membership works even though
`__eq__` is overloaded to construct a BoolExpr. Use `dist_a is dist_b`
for identity checks, not `dist_a == dist_b`.

### Choosing between the two authoring styles

A rough decision rule:

- **Use `model / compare`** when your scientific question is "*which
  of these pre-specified parameter values is most consistent with the
  data?*". Examples: Mendel 3:1 vs 1:1, Galileo Model A (weight-speed)
  vs Model B (medium resistance), Higgs vs no-Higgs.
- **Use `Distribution` + predicate** when your scientific question is
  "*what's the uncertainty in this quantity, and does it satisfy this
  threshold / equation?*". Examples: T_c > 77 K, k > 10⁻² s⁻¹,
  H₀ = 67 ± 1 km/s/Mpc.

You can mix both — use Distribution-backed observations to feed
evidence that a `compare()` comparison consumes.

### Compile-time diagnostics

Two warning categories surface common authoring mistakes / known
limitations:

* `DeadContinuousQuantityWarning` — a `Distribution` was declared but
  never referenced in any claim's predicate / equation / observation.
  Catches typos like declaring `T_c2` and then writing
  `claim("...", T_c > q(77, "K"))` with the wrong identifier. Suppress
  with `warnings.filterwarnings("ignore",
  category=DeadContinuousQuantityWarning)` for intentional placeholders.

* `ObservationNotUpdatingPredicateWarning` — both `observe(d,
  value=..., error=...)` and `claim("...", d > c)` reference the same
  `Distribution`, but the predicate prior is currently computed from
  the prior CDF directly without incorporating the observation. The
  posterior-CDF work (tracked separately) will close this gap. Until
  then, use `register_prior(predicate_claim, value, justification=...)`
  to record a documented post-observation belief, or express the
  inference via `gaia.engine.bayes.compare()`.

Both warnings emit through `warnings.warn` so they appear in pytest
output, the Gaia CLI, and any standard `warnings.catch_warnings`
capture. They are non-fatal — packages compile successfully.

## Source code

- `gaia/engine/bayes/dsl/model.py`, `dsl/compare.py` — verbs.
- `gaia/engine/bayes/runtime/actions.py` — `Model` /
  `ModelComparison` Action classes.
- `gaia/engine/bayes/runtime/precomputed.py` — `PrecomputedLikelihoods`.
- `gaia/engine/bayes/compiler/lower.py` — single lowering pass through
  one unified reader for model / observation / comparison
  metadata.
- `gaia/engine/bayes/distributions/` (internal) — scipy-backed pydantic
  `_BaseDistribution` implementations.
- `gaia/engine/lang/runtime/distribution.py` — Distribution Knowledge
  wrapper + family factories (`Normal`, `LogNormal`, `Beta`, `Gamma`,
  `Exponential`, `StudentT`, `Cauchy`, `ChiSquared`, `Binomial`,
  `BetaBinomial`, `Poisson`).
- `gaia/engine/lang/dsl/bool_expr.py` — `BoolExpr`,
  `DerivedDistribution`.
- `gaia/engine/lang/dsl/knowledge.py` — `claim(content, proposition,
  ...)` accepts BoolExpr propositions; routes equality to
  `metadata['equation']`, inequality to `metadata['predicate']`.
- `gaia/engine/lang/dsl/support.py` — `observe(target, value, error,
  ...)` polymorphism over `Variable` / `Distribution` / `Claim`.
- `gaia/engine/lang/compiler/predicate_lowering.py` — predicate →
  generated `continuous_inference` prior record at compile time;
  equation → low-priority default neutral prior record.
- `gaia/engine/lang/compiler/distribution_diagnostics.py` — dead-quantity
  and observation-not-updating-predicate detectors.
