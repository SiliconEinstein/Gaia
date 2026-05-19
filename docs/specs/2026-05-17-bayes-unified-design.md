# Bayes Unified Design — One Distribution, One Observation Schema

> **Status:** Implemented in v0.5
> **Branch:** `feat/bayes-unified-design` (off `v0.5`)
> **Target release:** v0.5 — clean break replacing the earlier in-flight Bayes surface
> **Date:** 2026-05-17
> **Scope:** Replace the parallel `gaia.engine.bayes` typed-value distributions plus the in-flight `bayes.model` / `bayes.data` / `bayes.likelihood` verbs with a single Distribution-Knowledge-centred surface that unifies hypothesis comparison and the quantity-with-predicate surface. Also fix the heterogeneous read paths for predictive mean, observed value, and noise sigma.
> **Supersedes:**
>   - `docs/specs/2026-05-04-bayes-module-design.md` (PR #523) — kept for historical context, no longer authoritative.
>   - `docs/specs/2026-05-05-bayes-actions-design.md` (PR #530) — kept for historical context; the Action-as-first-class-citizen direction is retained, but the verb names and data flow change.
> **Depends on:**
>   - Lang Distribution Knowledge (`gaia/engine/lang/runtime/distribution.py`)
>   - Lifted Lang (`Variable`, `Domain`, `parameter`, `observe`)
>   - Action hierarchy (`Support` / `Structural` / `Probabilistic` / `Scaffold`)

---

## 0. Motivation: three concrete design fractures in the earlier surface

### 0.1 Two parallel Distribution types with the same factory names

```python
# Path A: typed value, no identity, used by bayes.model(distribution=...)
import gaia.engine.bayes as bayes
n_a = bayes.Normal(mu=200, sigma=50)             # pydantic _BaseDistribution
type(n_a).__mro__  # _ContinuousDistribution -> _BaseDistribution -> BaseModel

# Path B: Knowledge node with identity, used by claim("...", T_c > 77)
from gaia.engine.lang import Normal
n_b = Normal("T_c", mu=200, sigma=50)            # Distribution(Knowledge)
type(n_b).__mro__  # Distribution -> Knowledge -> ...
```

Both wrap the same scipy backend. Both are named `Normal`. They are not interchangeable. Authors must remember which import goes with which verb. `bayes.Binomial(n, p)` is fundamentally a different thing from `Binomial("k", n, p)`, despite reading identically in paper-form pseudocode.

### 0.2 Mean, observed value, and noise sigma live in three storage layers

For one `bayes.model` + `bayes.data` pair, the likelihood lowering ([gaia/engine/bayes/compiler/lower.py](../../gaia/engine/bayes/compiler/lower.py)) has to walk three different access paths:

| Quantity              | Storage                                                                       | Reader                              |
|-----------------------|-------------------------------------------------------------------------------|-------------------------------------|
| predictive mu         | `distribution.params["mu"]` (may be a deferred `Variable`)                    | `_bind_distribution()` resolves     |
| predictive sigma      | `distribution.params["sigma"]`                                                | same                                |
| observed value        | `claim.formula` → `Equals(observable, Constant(v))` → `Constant.value`        | `_observation_value()` walks AST    |
| observation noise σ   | `claim.metadata["bayes"]["noise"]["params"]["sigma"]`                         | `_log_likelihood()` reads dict      |

Observation value lives in the formula AST. Observation noise lives in a metadata dict. The compiler also serialises and re-instantiates the noise distribution via `model_dump()` → `Normal(**params)` on every likelihood evaluation. None of this is forced by the science.

### 0.3 Noise itself has two representations depending on which verb you used

- `bayes.data(x, value=v, error=0.2)` writes `error` as a **dict payload** at `metadata["bayes"]["noise"]`.
- `observe(T_c, value=v, error=noise_distribution)` writes `error` as a **Distribution Knowledge object** at `metadata["observation"]["error"]`.

Same concept ("measurement uncertainty"), two representations. Downstream consumers (review, explain, BP lowering) must handle both.

---

## 1. Architectural position

```
┌────────────────────────────────────────────────────────────────────────────┐
│  gaia.engine.lang   (Distribution = Knowledge, the only user-facing type)  │
│                                                                              │
│   Normal / Binomial / BetaBinomial / Beta / Poisson / Exponential / ...    │
│   parameter(variable, value)                                                │
│   observe(target, value=, error=)        target ∈ {Variable, Distribution, Claim} │
│                                                                              │
└────────────────────────────────────────────────────────────────────────────┘
                                       │
                                       ▼
┌────────────────────────────────────────────────────────────────────────────┐
│  gaia.engine.bayes  (hypothesis-comparison verbs)                          │
│                                                                              │
│   model(hypothesis, observable=, distribution=)     → predictive helper Claim │
│   compare(data, models=[...])  # len(models) ≥ 2  → comparison helper Claim │
│   PrecomputedLikelihoods                          (Claim subclass for      │
│                                                    external-solver results) │
│                                                                              │
└────────────────────────────────────────────────────────────────────────────┘
                                       │  shared compiler lowering
                                       ▼
┌────────────────────────────────────────────────────────────────────────────┐
│  gaia.engine.ir    (unchanged)                                              │
│   No new Knowledge / Operator / FactorType. Predictive comparisons lower    │
│   to existing infer Strategies + Structural Contradict / Exclusive Actions. │
└────────────────────────────────────────────────────────────────────────────┘
```

### 1.1 What is removed

- `gaia.engine.bayes.Normal` (and every other distribution alias on the bayes namespace).
- Earlier in-flight Bayes predict calls are replaced by
  `gaia.engine.bayes.model(...)` with `observable=Variable` (see §3).
- `gaia.engine.bayes.likelihood(...)` → renamed to `compare(...)`, signature changed (see §3).
- `gaia.engine.bayes.data(...)` → folded into `observe(...)` (`gaia.engine.lang`). Removed.
- Reading observation value from `claim.formula`. Lowering reads only `claim.metadata["observation"]`.
- `metadata["bayes"]["noise"]` dict payload form. Noise is always a Distribution Knowledge object.

### 1.2 What is preserved

- The three-step paper narrative (model → observe → compare).
- The `PredictiveModel` / `Likelihood` Action subclasses (renamed: `Model` / `ModelCompare`).
- Cromwell clamp semantics on emitted infer factor.
- Exclusivity policy for `"pairwise_contradiction"` / `"exhaustive_pairwise_complement"`;
  the earlier `"none"` escape hatch is removed.
- `precomputed=` escape hatch (now also accepts a `PrecomputedLikelihoods` Claim).
- The Distribution Knowledge wrapper, unit-aware parameter handling, predicate operator overloading — all of `gaia/engine/lang/runtime/distribution.py` is unchanged.

---

## 2. Unified data model

### 2.1 One Distribution type

The user-facing distribution factories are exactly the ones already in [gaia/engine/lang/runtime/distribution.py](../../gaia/engine/lang/runtime/distribution.py):

```python
Normal(content, *, mu, sigma, **knowledge_kwargs) -> Distribution
Binomial(content, *, n, p, **knowledge_kwargs) -> Distribution
BetaBinomial(content, *, n, alpha, beta, **knowledge_kwargs) -> Distribution
# ... and the rest already exported from gaia.engine.lang
```

The underlying scipy-backed `_BaseDistribution` lives at `Distribution._impl`. It is internal — users never construct it directly. The pydantic class hierarchy is preserved; only the user surface contracts on the typed-value alias.

Anonymous distributions (no `label`) are allowed and remain Knowledge nodes, but
the current factories still require a content string:

```python
noise = Normal("measurement noise Normal(mu=0, sigma=0.2)", mu=0, sigma=0.2)
```

Scalar `observe(..., error=0.2)` sugar creates that content internally. This
keeps Knowledge-style identity even for inline anonymous distributions and lets
`gaia review` reach them.

`BetaBinomial`, `Cauchy`, `Gamma`, `ChiSquared`, `StudentT`, `LogNormal` — every family currently in `gaia/engine/bayes/distributions/` gets a corresponding factory in `gaia/engine/lang/runtime/distribution.py`. (Most are already there; `BetaBinomial` is the one that needs to be added.)

### 2.2 Observation schema (one shape for all `observe(...)` calls)

`metadata["observation"]` is the canonical container:

```python
metadata["observation"] = {
    "target": Variable | Distribution,
    "value": float | int | Quantity,
    "noise": Distribution | None,
    "unit": str | None,                       # canonical unit if any
    "source_refs": list[str],                 # optional
    "kind": "observation",                    # discriminator
}
```

Rules:

1. `value` lives only at `metadata["observation"]["value"]`. The previous `claim.formula = Equals(target, Constant(v))` representation is dropped from `observe()` output. (Authors who want a formula-bearing claim for logical reasoning can still construct one explicitly with `claim(..., formula=equals(x, Constant(v)))` — but `observe()` no longer does this implicitly.)
2. `noise` is always either `None` or a `Distribution` Knowledge object. The scalar shorthand `error=0.2` is sugared at `observe()` entry into `Normal(mu=0, sigma=0.2)`.
3. `target` is the original `Variable` or `Distribution` passed in (not a copy, not a descriptor). This lets `Claim.from_actions` / `roles_for_claim` reach the target through normal Python identity.

`bayes.data(x, value=v, error=σ)` and the v0.5 `observe(Distribution, value=v, error=σ)` both unify on this schema. There is one writer (`observe()`), one reader.

### 2.3 Model schema (one shape for all `model(...)` calls)

`metadata["model"]` is the canonical container for the helper Claim returned by `model(...)`:

```python
metadata["model"] = {
    "hypothesis": Claim,
    "observable": Variable,
    "distribution": Distribution,             # Knowledge node
    "kind": "model",
}
```

Rules:

1. `distribution` is always a `Distribution` Knowledge object. Reading the predictive mean is `pred.metadata["model"]["distribution"].params["mu"]`.
2. `observable` is always a `Variable`, ensuring the comparator can match model-to-observation by Python identity of the observed Variable.

### 2.4 Unified reader

A single helper in the compiler reads any quantity that lives in this schema:

```python
def _dist_param(claim: Claim, *, ns: str, key: str, param: str) -> Any | None:
    """Read a parameter of a metadata-stored Distribution. None when absent."""
    container = (claim.metadata or {}).get(ns) or {}
    distribution = container.get(key)
    if isinstance(distribution, Distribution):
        return distribution.params.get(param)
    return None
```

Likelihood evaluation no longer walks a formula AST and no longer serialises a noise dict. It calls:

```python
mu     = _dist_param(pred,  ns="model",       key="distribution", param="mu")
sigma  = _dist_param(pred,  ns="model",       key="distribution", param="sigma")
value  = data.metadata["observation"]["value"]
nsig   = _dist_param(data,  ns="observation", key="noise",        param="sigma")
```

All four come from one namespace shape.

---

## 3. User-facing API

### 3.1 `model`

```python
def model(
    hypothesis: Claim,
    *,
    observable: Variable,
    distribution: Distribution,
    background: list[Knowledge] | None = None,
    rationale: str = "",
    label: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> Claim:
    """Declare a predictive distribution for one hypothesis."""
```

Returns the helper Claim. The helper carries `metadata["model"]` per §2.3. A `Model` Action attaches reasoning to the helper.

### 3.2 `observe` (extended)

```python
def observe(
    target: Variable | Distribution | Claim | str,
    *,
    value: Any = _SENTINEL,
    error: float | int | Distribution | None = None,
    given: Claim | tuple[Claim, ...] | list[Claim] | None = (),
    background: list[Knowledge] | None = None,
    source_refs: list[str] | None = None,
    rationale: str = "",
    label: str | None = None,
) -> Claim:
    """Empirical observation. Polymorphic on target type."""
```

Behaviour by target:

- `target` is a `Claim` (or `str`) **and** `value` is sentinel: classical discrete claim observation. Pins prior to `1 - CROMWELL_EPS`.
- `target` is a `Distribution`: continuous-quantity observation; writes the unified `metadata["observation"]` schema (§2.2).
- `target` is a `Variable`: measurement of the named random variable. Same schema. Replaces the legacy `bayes.data(...)` path.

`error=σ` (scalar) is sugared into `Normal(mu=0, sigma=σ)` at entry. `error=None` (default) means noise-free observation. `error=Distribution` is passed through.

### 3.3 `compare`

```python
def compare(
    data: Claim | tuple[Claim, ...] | list[Claim],
    *,
    models: list[Claim] | tuple[Claim, ...],
    exclusivity: str = "exhaustive_pairwise_complement",
    background: list[Knowledge] | None = None,
    rationale: str = "",
    label: str | None = None,
    precomputed: dict[Claim, float] | PrecomputedLikelihoods | None = None,
    metadata: dict[str, Any] | None = None,
) -> Claim:
    """Compare observed data against a list of equally-positioned predictive models."""
```

Differences from the legacy `bayes.likelihood` it replaces:

- `model=` + `against=[...]` becomes a single `models=[...]` list with at least two models. The first-position "advocated" model is no longer privileged — all hypotheses are equal. (Authorial preference is recorded via Claim prior, not API asymmetry.)
- `precomputed=` accepts either a `dict[Claim, float]` (back-of-the-envelope escape hatch) or a `PrecomputedLikelihoods` Claim (§4).
- Returns the comparison helper Claim, with `metadata["comparison"]` carrying the likelihood table and exclusivity contract.
- **Default exclusivity is `"exhaustive_pairwise_complement"`**, not `"pairwise_contradiction"`. The earlier default silently diluted Bayesian model-selection posteriors by the probability mass that the hardcoded `α=0.5` `infer`-factor anchor assigned to the "all-false" joint state — for the canonical Mendel 1000:1 likelihood ratio the posterior settled at ~0.667 instead of ~0.999. The new default matches strict Bayesian model selection for the 2-hypothesis case.
  - For 3+ hypotheses, `exhaustive_pairwise_complement` currently raises `NotImplementedError` (the N-ary Exclusive operator is a follow-up — see §10). Authors comparing more than two models must pass `exclusivity="pairwise_contradiction"` explicitly (at-most-one semantics; the posterior is no longer a strict normalised model-selection result).
  - **`exclusivity="none"` is removed.** The previous escape hatch ("skip auto-generation; I declared exclusivity externally") was redundant: `compare()` now deduplicates against any same-type external structural action over the same hypothesis pair, looking up the active package via both the `_current_package` ContextVar and `infer_package_from_callstack()` so the dedup works in both unit-test and `gaia build compile` flows. The canonical Mendel example package therefore drops the argument: its external `exclusive(mendelian_segregation_model, blending_inheritance_model)` is detected automatically.
  - **Cross-type external structural actions are allowed to coexist.** An external `contradict(m1, m2)` does not prevent `compare()` from auto-generating an `exclusive(m1, m2)` (or vice-versa); the two are logically consistent (Exclusive implies Contradict). The IR's existing structural-relation consistency checks (notably the D2 "same operator + same args + distinct conclusions" rule) are the authority on whether the combined graph is legal.

### 3.4 Action class names

| Legacy name        | Current name        | Reason                                                              |
|--------------------|---------------------|---------------------------------------------------------------------|
| `PredictiveModel`  | `Model`        | Aligns with the model verb; shorter; "predictive model" was overloaded |
| `Likelihood`       | `ModelCompare`   | Aligns with verb `compare`; `Likelihood` is too generic              |
| `BayesInference`   | `BayesInference`    | Unchanged. Marker base class                                         |

Action fields:

```python
@dataclass
class Model(BayesInference):
    hypothesis: Claim | None = None
    observable: Variable | None = None
    distribution: Distribution | None = None
    helper: Claim | None = None

@dataclass
class ModelCompare(BayesInference):
    helper: Claim | None = None
    models: tuple[Claim, ...] = ()
    data: tuple[Claim, ...] = ()
    exclusivity: str = "exhaustive_pairwise_complement"
    precomputed: PrecomputedLikelihoods | None = None
    log_likelihoods: dict[Claim, float] = field(default_factory=dict)
```

Note `Model` carries `observable: Variable`; Distribution objects can still be observed directly through `observe(distribution, ...)`, but they are not model observables.

---

## 4. External solvers: the compute-layer contract

Question 3 from the design discussion: external statistical languages (PyMC, Stan, NumPyro, custom MCMC) that compute likelihoods or log-marginals and feed them into Gaia. The answer is: **wrap through `compute()`, output a `PrecomputedLikelihoods` Claim, pass it to `compare(precomputed=...)`**.

### 4.1 `PrecomputedLikelihoods` Claim

```python
@dataclass(eq=False)
class PrecomputedLikelihoods(Claim):
    """Externally computed log-likelihoods, attached as a compute() output."""

    log_likelihoods: dict[Claim, float] = field(default_factory=dict)
    diagnostics: dict[str, Any] = field(default_factory=dict)
    solver: str = ""        # e.g. "pymc-nuts-4000", "stan-hmc", "custom"
```

- Keys of `log_likelihoods` are the original hypothesis Claims, matching the bare-`dict` shortcut shape.
- `diagnostics` is solver-specific but follows a recommended schema (see below). It is mirrored into `metadata["diagnostics"]` at construction time so the IR / `gaia build check` / `gaia explain` can introspect it without walking back to the runtime object.
- `solver` is a free-form label for review and explain output.

`PrecomputedLikelihoods` is deliberately Bayes-specific. It records a numeric
interpretation of external work as log-likelihoods over hypotheses; it is not
the common evidence abstraction for all solver output, clinical trial records,
benchmark traces, or simulation artifacts. A future `gaia.engine.evidence`
layer should keep raw artifacts, provenance, and domain-specific evidence
interpretations separate; this PR only installs the Bayes interpretation needed
by `compare(precomputed=...)`.

#### Recommended `diagnostics` schema

External solvers report different convergence and provenance information depending on their method (MCMC vs SMC vs quadrature vs deterministic). The contract does not dictate a single key vocabulary; instead it requires that **at least one audit-relevant field** be present. `gaia build check` recognises the following keys as evidence that the wrapper has recorded enough to make the run reproducible / auditable:

| Field | Solver category | What it records |
|---|---|---|
| `seed` | any stochastic solver | RNG seed for reproducibility |
| `solver_version` | any | e.g. `"pymc-6.0.0"` |
| `code_hash` | any | hash of the wrapper / model spec |
| `method` / `solver_method` | any | e.g. `"pymc.sample_smc"`, `"scipy.integrate.quad"` |
| `r_hat_max` | MCMC | maximum Gelman-Rubin statistic across chains |
| `ess_min` | MCMC | minimum effective sample size |
| `divergences` | HMC / NUTS | divergence count |
| `per_chain` (or any `per_*` key) | MCMC / SMC | per-chain log marginals or other per-chain stats |
| `draws`, `chains` | MCMC / SMC | sampler size knobs |
| `epsabs`, `epsrel`, `abs_error_estimate` | quadrature | tolerance and error bounds |

`gaia build check` flags `bayes:precomputed-solver-diagnostics-missing` (see §6) when none of the recognised keys is present (case-insensitive prefix match, so `r_hat`, `r_hat_max`, `ess`, `ess_bulk`, etc. all count). This is a warning, not an error: deterministic analytical wrappers without natural diagnostics can still be audited through the `Compute` Action's `code_hash`. The warning prompts authors to add at least a `seed` or `solver_version` rather than letting empty payloads slip through.

#### Worked example: PyMC diagnostics payload

The integration demo at [scripts/demo_v06_pymc_integration.py](../../scripts/demo_v06_pymc_integration.py) records:

```python
PrecomputedLikelihoods(
    "PyMC marginal-likelihood run on Mendel vs Diffuse.",
    log_likelihoods={mendel: log_marg_mendel, diffuse: log_marg_diffuse},
    diagnostics={
        "solver_method": {
            "mendel": "closed_form_binomial_logpmf",
            "diffuse": "pymc.sample_smc",
        },
        "smc_draws": SMC_DRAWS,
        "smc_chains": SMC_CHAINS,
        "seed": SMC_SEED,
        "diffuse_log_marginal_mean": mean_diffuse,
        "diffuse_log_marginal_std": std_diffuse,
        "diffuse_log_marginal_per_chain": per_chain,
        "pymc_version": pm.__version__,
    },
    solver=f"pymc-smc-{SMC_DRAWS}x{SMC_CHAINS}",
)
```

This covers `seed`, `method`, `draws`, `chains`, and a per-chain breakdown — far more than the minimum the check rule requires, and enough for a downstream auditor to spot a high-std-across-chains run or a non-reproducible seed-missing run.

### 4.2 Compute wrapper

```python
from gaia.engine.lang import compute
from gaia.engine.bayes import PrecomputedLikelihoods

@compute
def stan_mendel_likelihoods(
    data: Claim,
    *,
    hypotheses: tuple[Claim, ...],
) -> PrecomputedLikelihoods:
    """Run Stan NUTS on the hierarchical Mendel model, return log-marginals."""
    import stan
    fit = stan.build(STAN_MODEL, data={"k": ..., "n": ...}).sample(num_chains=4)
    return PrecomputedLikelihoods(
        log_likelihoods={hypotheses[0]: fit.log_marginal[0], hypotheses[1]: fit.log_marginal[1]},
        diagnostics={"r_hat_max": float(fit.r_hat.max()), "seed": 12345},
        solver="stan-nuts-4000",
    )

result = stan_mendel_likelihoods(f2_count_data, hypotheses=(mendel, blending))
cmp = compare(f2_count_data, models=[mendel_pred, diffuse_pred], precomputed=result)
```

### 4.3 Why `compute()` is the right hook

1. **Auditable.** The existing `Compute` Action (`gaia/engine/lang/runtime/action.py`) already records `fn` and `code_hash`. Review sees the wrapper, not the Stan internals.
2. **Deterministic by contract.** `compute()` returns a Claim subclass; the wrapper code is in version control; seeded solvers are reproducible.
3. **Diagnostics.** Solver convergence diagnostics ride along as part of the Claim. `gaia audit` can flag bad r_hat / low ESS.
4. **Compatible with the dict shortcut.** `compare(precomputed={h1: -1.2, h2: -5.1})` still works for back-of-the-envelope cases. `PrecomputedLikelihoods` is for when the computation deserves a citable record.

### 4.4 Wrapper pattern: dispatch on latent presence

External PPLs (PyMC, Stan, NumPyro, ...) handle "no free parameters" differently than "at least one free parameter". PyMC's `pm.sample_smc` for example raises `ValueError: Empty list of input variables` when the model has no latent RVs. Wrappers must handle both shapes:

```python
@compute
def mendel_log_marginals(
    data: Claim,
    point_hypothesis: Claim,
    distribution_hypothesis: Claim,
) -> PrecomputedLikelihoods:
    # 1. Point hypothesis: no latent parameters → closed-form analytic
    #    likelihood. Don't invoke the sampler.
    log_marg_point = float(stats.binom.logpmf(K, n=N, p=0.75))

    # 2. Distribution-marginalised hypothesis: latent p ~ Beta(α, β).
    #    SMC integrates it out. Sampler is justified.
    with pm.Model() as marginal_model:
        p = pm.Beta("p", alpha=1.0, beta=1.0)
        pm.Binomial("k", n=N, p=p, observed=K)
        trace = pm.sample_smc(draws=2000, chains=4, random_seed=42)
    log_marg_marginal = float(trace.sample_stats.log_marginal_likelihood.mean().item())

    return PrecomputedLikelihoods(
        ...
        log_likelihoods={
            point_hypothesis: log_marg_point,
            distribution_hypothesis: log_marg_marginal,
        },
        ...
    )
```

The rule: **if `model(...)` was called with a fully-specified Distribution (no deferred `Variable` parameters), the wrapper should evaluate it analytically; if the model distribution has deferred parameters bound to a prior in the hypothesis Claim, the wrapper should invoke the sampler.** Mixing both styles in one comparison is normal (Mendel: point hypothesis vs distribution-marginalised diffuse) and the wrapper's `if-else` is where the dispatch lives.

`gaia build check` does **not** detect this dispatch automatically — wrappers that accidentally feed a no-latent model to `pm.sample_smc` will fail at run time with the PPL's native error. That's an acceptable trade-off: the spec keeps Gaia out of the business of statically analysing external solver code.

### 4.5 Out of scope

- Gaia does not vendor PyMC / Stan / NumPyro. Authors install them per the existing `ppl` extra (`docs/ideas/gaia-upgrade-specs/09-python-ecosystem-integration-spec.md` §4.3).
- Gaia does not provide its own MCMC/HMC backend.
- Gaia does not turn `compare(precomputed=Claim)` into a sampling call — the Claim is opaque, only its `log_likelihoods` table flows into the infer factor.

---

## 5. Compiler lowering

### 5.1 Renamed registration

```python
# gaia/engine/bayes/compiler/lower.py
def register_bayes_lowerer() -> None:
    ...
```

The lowerer now dispatches on `Model` and `ModelCompare`. Internal helpers `_observation_value` / `_log_likelihood_with_noise` are replaced with the unified `_dist_param` reader of §2.4.

### 5.2 Likelihood evaluation

```python
def _log_likelihood(model: Model, data: Claim) -> float:
    obs = data.metadata["observation"]
    value = obs["value"]
    noise = obs.get("noise")
    distribution = _bind_distribution(model.distribution, model.hypothesis)

    if noise is None:
        return _logp(distribution, value)
    return _convolve_log_likelihood(distribution, value, noise)
```

`_convolve_log_likelihood` is unchanged in algorithm (discrete summation for PMF families, scipy `quad` for continuous), but takes `noise: Distribution` directly instead of reconstructing from a dict.

### 5.3 Compare → infer factors

One `Strategy(INFER)` per hypothesis with `conditional_probabilities = [0.5, clamp(LR_i)]`. Metadata key namespace:

```python
metadata = {
    "comparison": {
        "role": "comparison",
        "exclusivity": ...,
        "likelihoods": {h_id: logL},
        "models": [...],
        "data": [...],
        "hypotheses": [...],
    }
}
```

Old key `metadata["bayes"]` is gone. Authors and tools that previously read it now read `metadata["comparison"]` (for `compare` helpers) or `metadata["model"]` (for `model` helpers).

### 5.4 Structural Actions for exclusivity

Exclusivity emission: `Contradict` for `pairwise_contradiction`, `Exclusive` (or `Contradict` + clamped Disjunction operator for ≥3 hypotheses) for `exhaustive_pairwise_complement`. The auto-generated helper Claims and their idempotency check are unchanged from the legacy lowering.

---

## 6. Check rules

| Code                                          | Trigger                                                              |
|-----------------------------------------------|----------------------------------------------------------------------|
| `bayes:dangling-model`                   | Model helper never consumed by a `compare()`                         |
| `bayes:unobserved-model-observable`      | Model observable Variable has no `observe(...)`                      |
| `bayes:hypothesis-prior-coherence`            | Hypothesis priors don't sum sensibly given exclusivity                |
| `bayes:comparison-without-data`               | `compare()` got no data Claims                                       |
| `bayes:infer-comparison-overlap`              | Same hypothesis-evidence pair has both an `infer()` and a `compare()` |

All five rules read the unified metadata schema (`metadata["model"]`, `metadata["observation"]`, `metadata["comparison"]`). Codes `bayes:comparison-without-data` and `bayes:infer-comparison-overlap` are renamed from the earlier `bayes:likelihood-*` codes in lock-step with the verb rename.

A new rule, implemented in [gaia/cli/commands/check.py](../../gaia/cli/commands/check.py) under `_check_v06_precomputed_solver_diagnostics`:

| `bayes:precomputed-solver-diagnostics-missing` | `compare(precomputed=PrecomputedLikelihoods(...))` where the Claim's `diagnostics` payload is empty or carries only unrecognised keys | warning |

Recognised keys are listed in §4.1's recommended schema (`seed`, `solver_version`, `code_hash`, `method`, `r_hat_max`, `ess_min`, `divergences`, `per_chain*`, `draws`, `chains`, `epsabs`, `epsrel`, `abs_error_estimate`, ...). Case-insensitive prefix match so wrapper-specific names like `ess_bulk` / `r_hat` / `per_hypothesis` still count. Test coverage at [tests/gaia/bayes/check/test_gaia_check_precomputed_diagnostics.py](../../tests/gaia/bayes/check/test_gaia_check_precomputed_diagnostics.py).

The rule is intentionally a warning, not an error: deterministic analytical wrappers without natural diagnostics can still be audited through the `Compute` Action's `code_hash`. The warning prompts authors who plug PyMC/Stan in to record at least a seed and a convergence statistic, so reviewers and `gaia audit` rules can decide whether to trust the precomputed likelihoods.

---

## 7. Migration

v0.5 ships this as a clean break from the earlier in-flight Bayes alpha. The list below tracks the changes already landed in this PR.

### 7.1 Examples that touched the legacy Bayes verbs

- `examples/mendel-v0-5-gaia/src/mendel_v0_5/__init__.py` — quantitative comparison segment rewritten through `model / compare / observe(Variable, ...)` (see §8 below).
- (No other example uses Bayes verbs; Galileo is purely qualitative.)

### 7.2 Test suite

- `tests/gaia/bayes/test_runtime_and_lowering.py` — rewritten to the new verb shape.
- `tests/gaia/bayes/check/test_gaia_check_bayes.py` — rewritten + renamed codes.
- `tests/gaia/bayes/test_public_surface.py` — expected export list trimmed to `model` / `compare` / `PrecomputedLikelihoods`.
- `tests/gaia/lang/test_observe_continuous.py` — extended to cover the `observe(Variable, value=, error=)` path.
- `tests/gaia/bayes/test_v06_numeric_equivalence.py` — golden numeric tests (kept under the `v06` filename for git diff readability; the assertion content is "new surface == previous alpha surface").

### 7.3 Docs

- `docs/foundations/gaia-lang/bayes.md` — rewritten end-to-end through the new verbs.
- `docs/reference/engine/bayes.md` — regenerated from docstrings.

### 7.4 Breaking changes summary

For anyone using the in-flight alpha Bayes surface:

```diff
-from gaia.engine.bayes import Normal, Binomial, BetaBinomial
+from gaia.engine.lang  import Normal, Binomial, BetaBinomial

-model = bayes.model(h, observable=k, distribution=bayes.Binomial(n=n, p=p))
+model = bayes.model(h, observable=k, distribution=Binomial("k under H", n=n, p=p))

-data = bayes.data(k, value=v, error=σ)
+data = observe(k, value=v, error=σ)

-cmp = bayes.likelihood(data, model=a, against=[b], exclusivity="...")
+cmp = bayes.compare(data, models=[a, b], exclusivity="...")
```

There is no compatibility shim. v0.5 fails fast at import time on the removed names.

---

## 8. Mendel example, before / after

### 8.1 Earlier in-flight surface

```python
import gaia.engine.bayes as bayes

mendel_count_model = bayes.model(
    mendelian_segregation_model,
    observable=f2_dominant_count,
    distribution=bayes.Binomial(n=TOTAL_COUNT, p=MENDELIAN_DOMINANT_PROBABILITY),
    label="mendel_count_model",
)
diffuse_count_model = bayes.model(
    blending_inheritance_model,
    observable=f2_dominant_count,
    distribution=bayes.BetaBinomial(n=TOTAL_COUNT, alpha=1.0, beta=1.0),
    label="diffuse_count_model",
)
mendel_count_likelihood = bayes.likelihood(
    f2_count_observation,
    model=mendel_count_model,
    against=[diffuse_count_model],
    label="mendel_count_likelihood",
)
```

The earlier alpha briefly used `exclusivity="none"` as an escape hatch
to suppress auto-emitted structural relations. The current surface
rejects that value; declare the structural relation explicitly and let
`compare()` deduplicate same-type relations.

### 8.2 v0.5 unified surface

```python
from gaia.engine.lang import Binomial, BetaBinomial, observe
from gaia.engine.bayes import model, compare

f2_count_data = observe(
    f2_dominant_count,
    value=DOMINANT_COUNT,
    label="f2_count_observation",
    rationale="F2 dominant count = 295 out of 395.",
)

mendel_pred = model(
    mendelian_segregation_model,
    observable=f2_dominant_count,
    distribution=Binomial(
        "F2 dominant count under Mendel 3:1",
        n=TOTAL_COUNT, p=MENDELIAN_DOMINANT_PROBABILITY,
    ),
    label="mendel_pred",
)

diffuse_pred = model(
    blending_inheritance_model,
    observable=f2_dominant_count,
    distribution=BetaBinomial(
        "F2 dominant count under p ~ Uniform[0,1]",
        n=TOTAL_COUNT, alpha=1.0, beta=1.0,
    ),
    label="diffuse_pred",
)

cmp = compare(
    f2_count_data,
    models=[mendel_pred, diffuse_pred],
    # exclusivity defaults to "exhaustive_pairwise_complement"; the
    # external ``exclusive(mendelian_segregation_model,
    # blending_inheritance_model)`` declared elsewhere in the package
    # is detected via same-type dedup, so no second Exclusive helper
    # is emitted.
    label="f2_count_comparison",
)
```

Two visible improvements:

1. Each predictive distribution gets a human-readable content string ("F2 dominant count under Mendel 3:1") and a Knowledge identity. Review can comment on the distribution itself, not only on the wrapping Action.
2. `model()`, `observe()`, and `compare()` all expose the measured quantity explicitly: `model(..., observable=variable)` declares the predictive observable, and `observe(variable, value=...)` records the data.

---

## 9. Open decisions (with defaults)

These four points are listed as the spec's authoritative defaults. PR review can flip any of them without rewriting the spec.

1. **`bayes` namespace.** Model and compare live at `gaia.engine.bayes`, not promoted to `gaia.engine.lang`. Rationale: `derive` / `observe` / `compute` are universal verbs; `model` / `compare` are statistical, opt-in. (Default: **keep the namespace.**)
2. **`observed=` inline sugar on Distribution factories.** Not provided. Authors must call `observe()` explicitly so the Observe Action is review-visible. (Default: **no sugar.**)
3. **Noise convolution location.** Lowering-time convolution. Hierarchical-RV (`y_obs ~ Normal(y_true, σ_meas)`) is deferred to post-v0.5 because the BP backend is still discrete. (Default: **lowering-time convolve.**)
4. **`compare(models=[...])` symmetry.** Equal-positioned list, no `model=` + `against=[...]` asymmetry. Authorial advocacy lives in Claim prior, not in the API. (Default: **symmetric list.**)

---

## 10. Acceptance checklist

```
[x] gaia/engine/bayes/__init__.py exposes model, compare, PrecomputedLikelihoods only
[x] gaia/engine/bayes/distributions/ becomes a private implementation directory; no Normal / Binomial / ... exported
[x] gaia/engine/lang exports Normal, Binomial, BetaBinomial, ... (BetaBinomial added)
[x] observe(Variable, value=..., error=...) writes the unified metadata["observation"] schema
[x] model(...) writes the unified metadata["model"] schema
[x] compare(...) writes metadata["comparison"]; legacy metadata["bayes"] key on helpers removed
[x] PrecomputedLikelihoods Claim subclass implemented; compare(precomputed=) accepts it
[x] @compute decorator resolves PEP-563 string return annotations
[x] PrecomputedLikelihoods.diagnostics mirrors onto metadata["diagnostics"] for IR introspection
[x] bayes:precomputed-solver-diagnostics-missing check rule implemented
[x] All check rules read v0.5 unified schema (metadata["model"] / ["observation"] / ["comparison"])
[x] Lowering reads value / noise / distribution params through one helper (no formula-AST walk)
[x] examples/mendel-v0-5-gaia rewritten
[x] Numeric equivalence test passes (Mendel posterior, odds, comparison belief
    match the legacy alpha surface to within 1e-9)
[x] External-solver contract validated end-to-end:
      - tests/gaia/bayes/test_v06_external_solver_integration.py (scipy.integrate.quad)
      - scripts/demo_v06_pymc_integration.py (real PyMC SMC; not in CI, no PyMC dependency)
[x] Documentation regenerated (foundations/gaia-lang/bayes.md)
[x] Wrapper pattern §4.4 surfaced in foundations docs
[x] compare() default exclusivity flipped to exhaustive_pairwise_complement
    (was pairwise_contradiction; the old default silently diluted
    Bayes-factor posteriors via α=0.5 mass on the "all-false" state)
[x] compare() with 3+ models + exhaustive_pairwise_complement raises
    NotImplementedError until the N-ary Exclusive operator lands
[x] compare(exclusivity="none") removed; same-type dedup against
    external structural actions replaces the explicit escape hatch
[x] _existing_pair_relation falls back to infer_package_from_callstack
    so the dedup works in the gaia build compile flow (where
    _current_package is unset)
```

### 10.1 Follow-up issues

* **N-ary Exclusive operator.** Required to make
  `exclusivity="exhaustive_pairwise_complement"` work for 3+
  hypothesis comparisons. The current implementation raises
  `NotImplementedError` in that case rather than silently degrading to
  pairwise `Contradict` (at-most-one), which would dilute the
  posterior by the all-false joint state's mass. The fix needs a new
  IR `Operator` (or a generalisation of the existing `Exclusive`) and
  the corresponding BP factor-graph encoding for "exactly one of N is
  true".
