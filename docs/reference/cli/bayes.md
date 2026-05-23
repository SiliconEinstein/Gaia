# `gaia bayes`

> **Status:** Reference for the Bayesian-modelling cli surface (v0.5).

The `gaia bayes` subcommand group exposes the engine's
[`gaia.engine.bayes`](https://github.com/SiliconEinstein/gaia/tree/main/gaia/engine/bayes)
authoring surface through structured cli verbs. It mirrors the engine's
organisation: `model` + `compare` + one verb per shipping
Distribution class.

Output is **JSON-by-default** through the same uniform envelope as
[`gaia author`](author.md); see [Envelope shape](author.md#envelope-shape)
for the contract.

## Verb inventory — 13 verbs

| Layer | Verb | DSL signature |
|---|---|---|
| Structural | `model` | `bayes.model(hypothesis, *, observable, distribution, background=…, rationale="", label=…)` |
| Structural | `compare` | `bayes.compare(data, *, models=[…], background=…, rationale="", label=…, exclusivity=…)` with at least two models |
| Discrete dist | `binomial` | `Binomial(content, n=…, p=…)` |
| Discrete dist | `beta-binomial` | `BetaBinomial(content, n=…, alpha=…, beta=…)` |
| Discrete dist | `poisson` | `Poisson(content, rate=…)` |
| Continuous dist | `normal` | `Normal(content, mu=…, sigma=…)` |
| Continuous dist | `log-normal` | `LogNormal(content, mu=…, sigma=…)` |
| Continuous dist | `beta` | `Beta(content, alpha=…, beta=…)` |
| Continuous dist | `exponential` | `Exponential(content, rate=…)` |
| Continuous dist | `gamma` | `Gamma(content, alpha=…, rate=…)` |
| Continuous dist | `student-t` | `StudentT(content, df=…, mu=0.0, sigma=1.0)` |
| Continuous dist | `cauchy` | `Cauchy(content, mu=…, gamma=…)` |
| Continuous dist | `chi-squared` | `ChiSquared(content, df=…)` |

Every verb shares the statement-writing flags `--target`, `--file`, `--label`,
`--check / --no-check`, `--human`, `--interactive`, and `--metadata`.
`model` and `compare` also expose the explicit `--json / --no-json`
courtesy switch used by `gaia author`; the distribution-literal verbs keep
JSON output as their default contract without surfacing that alias. Distribution
verbs forward their parameter values verbatim; pre-write parses the rendered
statement as Python to catch obvious malformations, and the engine's Pydantic
validators surface out-of-range values at engine-load time.

## Distribution-literal verbs

Each verb binds a Distribution instance to a module-scope identifier
that subsequent `bayes model` / `observe` calls can reference by name.

```bash
gaia bayes binomial --n 395 --p 0.75 --label mendel_binomial
# → mendel_binomial = Binomial('mendel_binomial', n=395, p=0.75)

gaia bayes beta-binomial --n 395 --alpha 1.0 --beta 1.0 --label diffuse_betabin
# → diffuse_betabin = BetaBinomial('diffuse_betabin', n=395, alpha=1.0, beta=1.0)

gaia bayes normal --mu 0 --sigma 1 --label standard_normal
# → standard_normal = Normal('standard_normal', mu=0, sigma=1)
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

## `gaia bayes compare`

```bash
gaia bayes compare \
    --data f2_count_observation \
    --model mendel_count_model \
    --against diffuse_count_model \
    --rationale "Compare Mendel vs diffuse on F2 counts." \
    --label mendel_count_comparison
```

Renders as:

```python
mendel_count_comparison = bayes.compare(
    f2_count_observation,
    models=[mendel_count_model, diffuse_count_model],
    rationale='Compare Mendel vs diffuse on F2 counts.',
    label='mendel_count_comparison',
)
```

Multi-data observations: pass a comma-separated list to `--data`. The
cli renders them as a Python list literal:

```bash
gaia bayes compare --data obs_a,obs_b,obs_c --model M --against M_alt --label cmp
```

renders `bayes.compare([obs_a, obs_b, obs_c], models=[M, M_alt], ...)`.

`--exclusivity` accepts `exhaustive_pairwise_complement` (default) /
`pairwise_contradiction`; mismatched values exit 2 with a syntax
diagnostic. The default value is elided from the rendered source for
conciseness.

## Worked example — Mendel single-factor cross

The hand-authored [`examples/mendel-v0-5-gaia/`](https://github.com/SiliconEinstein/gaia/tree/main/examples/mendel-v0-5-gaia)
package compiles a Mendelian segregation analysis with Bayes
model comparison. The cli sequence to reproduce its `bayes`
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

# Model comparison
gaia bayes compare --data f2_count_observation \
    --model mendel_count_model --against diffuse_count_model \
    --label mendel_count_comparison \
    --target ./mendel-cli-mirror-gaia
```

## See also

- [`docs/reference/cli/author.md`](author.md) — the optional authoring-helper CLI (primary path: direct SDK authoring).
- [`docs/reference/cli/pkg.md`](pkg.md) — `gaia pkg scaffold` + `add-module`.
- Engine reference: [`gaia.engine.bayes`](https://github.com/SiliconEinstein/gaia/tree/main/gaia/engine/bayes).
