# `gaia bayes`

> **Status:** Reference for the Bayesian-modelling cli surface (v0.5).

The `gaia bayes` subcommand group exposes the engine's
[`gaia.engine.bayes`](https://github.com/SiliconEinstein/gaia/tree/main/gaia/engine/bayes)
authoring surface through structured cli verbs. It mirrors the engine's
organisation: `model` + `likelihood` + one verb per shipping
Distribution class.

Output is **JSON-by-default** through the same uniform envelope as
[`gaia author`](author.md); see [Envelope shape](author.md#envelope-shape)
for the contract.

## Verb inventory — 13 verbs

| Layer | Verb | DSL signature |
|---|---|---|
| Structural | `model` | `bayes.model(hypothesis, *, observable, distribution, background=…, rationale="", label=…)` |
| Structural | `likelihood` | `bayes.likelihood(data, *, model, against=…, background=…, rationale="", label=…, exclusivity=…)` |
| Discrete dist | `binomial` | `bayes.Binomial(n=…, p=…)` |
| Discrete dist | `beta-binomial` | `bayes.BetaBinomial(n=…, alpha=…, beta=…)` |
| Discrete dist | `poisson` | `bayes.Poisson(rate=…)` |
| Continuous dist | `normal` | `bayes.Normal(mu=…, sigma=…)` |
| Continuous dist | `log-normal` | `bayes.LogNormal(mu=…, sigma=…)` |
| Continuous dist | `beta` | `bayes.Beta(alpha=…, beta=…)` |
| Continuous dist | `exponential` | `bayes.Exponential(rate=…)` |
| Continuous dist | `gamma` | `bayes.Gamma(alpha=…, rate=…)` |
| Continuous dist | `student-t` | `bayes.StudentT(df=…, mu=0.0, sigma=1.0)` |
| Continuous dist | `cauchy` | `bayes.Cauchy(mu=…, gamma=…)` |
| Continuous dist | `chi-squared` | `bayes.ChiSquared(df=…)` |

Every verb shares the [`gaia author`](author.md) cross-cutting flags
(`--target`, `--file`, `--label`, `--check / --no-check`, `--human`,
`--interactive`, `--metadata`). Distribution verbs forward their
parameter values verbatim; pre-write parses the rendered statement as
Python to catch obvious malformations, and the engine's Pydantic
validators surface out-of-range values at engine-load time.

## Distribution-literal verbs

Each verb binds a Distribution instance to a module-scope identifier
that subsequent `bayes model` / `observe` calls can reference by name.

```bash
gaia bayes binomial --n 395 --p 0.75 --label mendel_binomial
# → mendel_binomial = bayes.Binomial(n=395, p=0.75)

gaia bayes beta-binomial --n 395 --alpha 1.0 --beta 1.0 --label diffuse_betabin
# → diffuse_betabin = bayes.BetaBinomial(n=395, alpha=1.0, beta=1.0)

gaia bayes normal --mu 0 --sigma 1 --label standard_normal
# → standard_normal = bayes.Normal(mu=0, sigma=1)
```

The envelope's `payload.distribution_kind` field carries the
distribution name (e.g. `"Binomial"`) so an agent consumer can dispatch
without parsing the rendered source.

## `gaia bayes model`

```bash
gaia bayes model \
    --hypothesis mendelian_segregation_model \
    --observable f2_dominant_count \
    --distribution mendel_binomial \
    --background monohybrid_cross_setup,dominance_background \
    --rationale "Mendel predicts Binomial(N, 3/4) for F2 dominant counts." \
    --label mendel_count_model
```

Renders as:

```python
mendel_count_model = bayes.model(
    mendelian_segregation_model,
    observable=f2_dominant_count,
    distribution=mendel_binomial,
    background=[monohybrid_cross_setup, dominance_background],
    rationale='Mendel predicts Binomial(N, 3/4) for F2 dominant counts.',
    label='mendel_count_model',
)
```

The verb references three identifiers — `hypothesis`, `observable`,
`distribution` — all of which must resolve in module scope. Pre-write
fires `prewrite.reference_unresolved` (exit 3) for missing names.

## `gaia bayes likelihood`

```bash
gaia bayes likelihood \
    --data f2_count_observation \
    --model mendel_count_model \
    --against diffuse_count_model \
    --exclusivity none \
    --rationale "Compare Mendel vs diffuse on F2 counts." \
    --label mendel_count_likelihood
```

Renders as:

```python
mendel_count_likelihood = bayes.likelihood(
    f2_count_observation,
    model=mendel_count_model,
    against=[diffuse_count_model],
    rationale='Compare Mendel vs diffuse on F2 counts.',
    exclusivity='none',
    label='mendel_count_likelihood',
)
```

Multi-data observations: pass a comma-separated list to `--data`. The
cli renders them as a Python list literal:

```bash
gaia bayes likelihood --data obs_a,obs_b,obs_c --model M --label cmp
```

renders `bayes.likelihood([obs_a, obs_b, obs_c], model=M, ...)`.

`--exclusivity` accepts `none` / `pairwise_contradiction` (default) /
`exhaustive_pairwise_complement`; mismatched values exit 2 with a
syntax diagnostic. The default value is elided from the rendered
source for conciseness.

## Worked example — Mendel single-factor cross

The hand-authored [`examples/mendel-v0-5-gaia/`](https://github.com/SiliconEinstein/gaia/tree/main/examples/mendel-v0-5-gaia)
package compiles a Mendelian segregation analysis with Bayes
likelihood comparison. The cli sequence to reproduce its `bayes`
authoring slice:

```bash
# Scaffold (--import-name is derived from --name; no separate flag)
gaia pkg scaffold --target ./mendel-cli-mirror-gaia \
    --name mendel-v0-5-gaia --namespace example

# Declare typed variables for observables
gaia author variable --symbol n_f2 --domain Nat --value 395 \
    --label f2_total_count --target ./mendel-cli-mirror-gaia
gaia author variable --symbol k_dominant --domain Nat --value 295 \
    --label f2_dominant_count --target ./mendel-cli-mirror-gaia

# ... (claims + observations) ...

# Declare distributions
gaia bayes binomial --n 395 --p 0.75 \
    --label mendel_binomial --target ./mendel-cli-mirror-gaia
gaia bayes beta-binomial --n 395 --alpha 1.0 --beta 1.0 \
    --label diffuse_betabin --target ./mendel-cli-mirror-gaia

# Predictive models
gaia bayes model --hypothesis mendelian_segregation_model \
    --observable f2_dominant_count --distribution mendel_binomial \
    --label mendel_count_model --target ./mendel-cli-mirror-gaia

gaia bayes model --hypothesis blending_inheritance_model \
    --observable f2_dominant_count --distribution diffuse_betabin \
    --label diffuse_count_model --target ./mendel-cli-mirror-gaia

# Likelihood comparison
gaia bayes likelihood --data f2_count_observation \
    --model mendel_count_model --against diffuse_count_model \
    --exclusivity none --label mendel_count_likelihood \
    --target ./mendel-cli-mirror-gaia
```

## See also

- [`docs/reference/cli/author.md`](author.md) — the full agent-first authoring CLI.
- [`docs/reference/cli/pkg.md`](pkg.md) — `gaia pkg scaffold` + `add-module`.
- Engine reference: [`gaia.engine.bayes`](https://github.com/SiliconEinstein/gaia/tree/main/gaia/engine/bayes).
