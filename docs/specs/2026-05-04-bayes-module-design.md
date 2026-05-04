# Bayes Module Design — Hypothesis–Data Inference Subsystem

> **Status:** Target design (proposal)
> **Branch:** `feat/bayes-module-design` (off `main`)
> **Target release:** v0.6 (built on v0.5 foundation + PR 505 lifted Lang)
> **Date:** 2026-05-04
> **Scope:** Replacement of the Correlate `evidence()` verb with a structured `gaia.lang.bayes` module exposing `predict / likelihood` plus distribution literals.
> **Supersedes:** PR #506 (`evidence()` verb). PR #506 will be closed without merge.
> **Depends on:** PR #505 (claim formula schema — Variable / Domain / Formula AST / `parameter()` / `observation()` sugar).

---

## 0. Background and Motivation

### 0.1 What's wrong with `evidence()` (PR #506)

`evidence(D, hypothesis=H, model=M, null_model=M0, observed=v)` collapses five distinct conceptual atoms of scientific reasoning into a single verb:

1. The *internal structure* of the hypothesis (what parameter, what value)
2. The *predictive model* connecting H to the observable
3. The *observation* (measured value, noise model)
4. The *likelihood* P(D|H) computation
5. The *belief update* on H

This collapse forces every variation of "use data to evaluate a hypothesis" to be a new verb (`evidence` for Binomial, future `model_compare` for multi-H, `gaussian_evidence` for measurement, …) and prevents `gaia review` from inspecting individual atoms. PR #506's review surfaces two soundness gaps as a direct consequence:

- `model.kind / params.n` mismatch between `model` and `null_model` is silently accepted (likelihoods computed on different probability spaces).
- IR consumer contract for `evidence`-emitted strategies is implicit and undocumented (only distinguished from `infer` by `metadata["pattern"]`).

The deeper problem is that `evidence()` covers a narrow slice (point H vs point ¬H, Binomial-only) of what scientific papers actually do.

### 0.2 What scientific writing actually decomposes into

A Bayesian-flavoured paper section reads:

> "We hypothesise that θ = 0.75 (Mendelian segregation). Under this hypothesis, the dominant phenotype count k follows Binomial(n=395, p=0.75). We observed k=295. The likelihood under the 3:1 model is 0.30, vs 0.04 under the null 1:1 model — a Bayes factor of ≈7."

Five atoms, each independently expressible:

| Atom | Authoring artifact | Knowledge node? |
|---|---|---|
| Hypothesis with internal structure | `parameter(theta, 0.75)` (PR 505) | yes — PARAMETER claim |
| Predictive model | `predict(H, k, distribution=Binomial(n, p=theta))` | yes — PredictiveModel claim |
| Observation with optional noise | `observation(k=295, noise=...)` (PR 505) | yes — OBSERVATION claim |
| Likelihood computation | `likelihood(data, via=M)` | yes — ComparisonResult claim |
| Belief update | (lowering produces BP factors) | no — structural |

This spec defines a `gaia.lang.bayes` module with two new verbs (`predict`, `likelihood`) plus distribution literals, reusing PR 505's `parameter()` / `observation()` for the hypothesis/observation atoms.

### 0.3 First-principles position

| Principle | How it lands |
|---|---|
| **DSL surface mirrors paper narrative.** | `predict / observation / likelihood` is the standard three-step paper method. |
| **Each atom is a structured Claim, reviewable in isolation.** | All four user-facing artifacts are Knowledge nodes carrying typed metadata. |
| **Composite hypotheses, multi-H, parameter priors are special cases of the same framework, not new verbs.** | Composite H is a formula-shape change (PR 505 grounding pass). Multi-H = expanding the H set passed to `predict`. Parameter prior = backend extension on Distribution. |
| **Mature ecosystems plug in via Distribution backend.** | scipy.stats is the v1 default backend; PyMC / Stan / NumPyro are v2+ adapter slots that extend `Distribution.logpmf/logpdf` without changing the DSL. |
| **IR is grounded propositional. Bayes module is lifted.** | Variables (PR 505) carry parameter identity; bayes verbs lower to existing IR `infer` strategies + `CONTRADICTION` operators. **No new FactorType.** |

---

## 1. Architectural Position

```
┌──────────────────────────────────────────────────────────────────┐
│  Gaia Lang  (lifted)                                              │
│  ────────────                                                      │
│  PR 505:  Variable, Domain, Formula AST, parameter()/observation() │
│           ↑                                                        │
│  NEW:     gaia.lang.bayes                                          │
│             distributions/  (scipy-backed, Variable-aware)         │
│             predict()       → PredictiveModel Knowledge            │
│             likelihood()    → ComparisonResult Knowledge           │
└──────────────────────────────────────┬───────────────────────────┘
                                       │ Compiler (grounding pass)
                                       ▼
┌──────────────────────────────────────────────────────────────────┐
│  Gaia IR  (grounded)                                              │
│  ─────────                                                         │
│  Knowledge atoms (PARAMETER / OBSERVATION / PredictiveModel /     │
│                   ComparisonResult)                                │
│  Operator:  CONTRADICTION (auto-generated for multi-H exclusion)  │
│  Strategy:  infer (per H, with conditional_probabilities)         │
└──────────────────────────────────────────────────────────────────┘
```

### 1.1 Module boundary

- **Replaces** `evidence()` from PR #506 (deleted, not deprecated; user count = 0).
- **Coexists with** `infer()` (low-level escape hatch, hand-written CPT) and `associate()` (symmetric correlation — orthogonal problem).
- **Depends on** PR 505's Variable / Formula AST / `parameter()` / `observation()`.
- **Single new hard dependency:** `scipy` (must be added as a direct runtime dependency; do not rely on optional transitive dependencies).
- **No IR schema changes. No new FactorType.**

### 1.2 New `metadata` well-known keys

| Key | Carrier | Value |
|---|---|---|
| `metadata["bayes"]["role"]` | Knowledge | `"prediction" | "comparison"` |
| `metadata["bayes"]["distribution"]` | PredictiveModel Knowledge | `{"kind": "binomial", "params": {...}}` (DistributionLiteral dump) |
| `metadata["bayes"]["likelihoods"]` | ComparisonResult Knowledge | `{H_qid: log_likelihood}` |
| `metadata["bayes"]["data"]` | ComparisonResult Knowledge | `[obs_qid, ...]` |
| `metadata["bayes"]["model"]` | ComparisonResult Knowledge | `predictive_model_qid` |
| `metadata["bayes"]["log_likelihood"]` | infer Strategy | scalar — for trace inspection |
| `metadata["bayes"]["auto_generated_by"]` | CONTRADICTION Operator | `"likelihood:<cmp_result_qid>"` (audit trail for auto-added exclusion) |
| `metadata["bayes"]["noise"]` | OBSERVATION Knowledge | DistributionLiteral dump (optional) |

These ride existing `metadata: dict[str, Any]` channels; no Pydantic schema change.

---

## 2. Module Code Layout

```
gaia/lang/bayes/
├── __init__.py              # public API: predict, likelihood, distributions
├── verbs/
│   ├── predict.py           # predict() DSL
│   └── likelihood.py        # likelihood() DSL
├── distributions/
│   ├── __init__.py          # re-export Binomial, Normal, Beta, Poisson, ...
│   ├── protocol.py          # Distribution Protocol (.logpmf / .logpdf / .support)
│   ├── discrete.py
│   └── continuous.py
├── adapters/
│   ├── scipy_backend.py     # v1 default
│   └── README.md            # PyMC / Stan adapter contract (v2+)
├── runtime/
│   ├── prediction.py        # PredictiveModel Knowledge subclass
│   └── comparison.py        # ComparisonResult Knowledge subclass
├── compiler/
│   └── lower.py             # Lang→IR lowering (per §4)
└── README.md                # module overview & extension points

# Re-exports for convenience (matches existing `from gaia.lang import claim` style):
gaia/lang/__init__.py:
   from gaia.lang.bayes import predict, likelihood, Binomial, Normal, ...
```

Recommended import style is **namespace**:

```python
from gaia.lang import bayes
bayes.predict(...)
bayes.likelihood(...)
bayes.Binomial(n=n, p=theta)
```

`from gaia.lang import predict, likelihood` also works.

### 2.1 Module boundaries with existing code

| Existing | Action |
|---|---|
| Distribution literals | Implement directly in `gaia.lang.bayes.distributions`. Do **not** add a `gaia.stats` compatibility shim: PR #506 is unmerged and current `main` has no public `gaia.stats` API to migrate. |
| PR 505's `parameter()` / `observation()` sugar | Stay at `gaia.lang.dsl` root; bayes module imports and uses them. |
| Correlate `infer` / `associate` | Stay. `infer` = "I hand-wrote the CPT"; `bayes.likelihood` = "I have a model and observed value, kernel computes the CPT". |
| Correlate `evidence` (PR 506) | **Delete in same PR as bayes module.** PR #506 closes without merge. |

---

## 3. Core DSL

### 3.1 `Distribution` (Lang-side typed value)

Distributions are *recipes*, not propositions — they don't have truth values, so they are not Knowledge nodes. They are typed values that may reference Variables.

```python
from gaia.lang.bayes import Binomial, Normal, Beta, Poisson, ...

n = variable("n", Nat, value=395)
theta = variable("theta", Probability)

Binomial(n=n, p=theta)         # n, p: Variable | DistributionParam
Normal(mu=mu_h, sigma=0.5)     # mu_h: Variable, sigma: float
```

Internally backed by `scipy.stats`. Each distribution implements:

```python
class Distribution(Protocol):
    kind: str
    params: dict[str, Variable | float]

    def logpmf(self, x: int) -> float: ...        # discrete
    def logpdf(self, x: float) -> float: ...      # continuous
    def support(self) -> tuple[float, float]: ...
```

For the v1 release, `Binomial / Normal / Beta / Poisson / Exponential / LogNormal / StudentT / Cauchy / Gamma / ChiSquared` are sufficient (covers ≥90% of cited scientific use).

### 3.2 `predict()` — produce a PredictiveModel claim

```python
M = bayes.predict(
    hypothesis,        # Claim or set[Claim]
    observable,        # Variable
    distribution,      # Distribution literal (may reference Variables)
    background=None,
    rationale="",
    label=None,
) -> Claim
```

Returns a Knowledge node with `metadata["bayes"]["role"] = "prediction"` and `metadata["bayes"]["distribution"]` carrying the serialized distribution literal. Semantically asserts: *"under each H_i in the hypothesis set, the observable variable follows this distribution."*

The distribution literal's parameters that are Variables are resolved at compile time by reading each H_i's `formula` (PR 505's PARAMETER claim shape: `Equals(var, const)`).

Multi-H syntax is **set** — `predict({H_3_1, H_null}, k, distribution=...)` indicates "alternative models for the same observable."

### 3.3 Observation with optional noise — extends PR 505's `observation()`

PR 505 already provides `observation(var=value, ...)` returning an OBSERVATION claim with `formula = Equals(var, value)`. The bayes module adds an optional `noise=` parameter:

```python
data = observation(
    k=295,
    prior=1.0,
    noise=Normal(mu=0, sigma=2.5),   # NEW: optional measurement noise model
    rationale="...",
    label=None,
)
```

`noise` is stored at `metadata["bayes"]["noise"]`. `likelihood()` reads it during likelihood computation (§4.5).

`observe()` is **not** a new verb. The PR 505 `observation()` function gains a `noise=` kwarg.

### 3.4 `likelihood()` — produce a ComparisonResult claim + connect BP factor

```python
result = bayes.likelihood(
    data,                    # OBSERVATION claim or list (multi-data accumulation)
    via,                     # PredictiveModel claim from predict()
    background=None,
    rationale="",
    label=None,
    exclusivity="pairwise_contradiction",  # | "none" | "exhaustive_pairwise_complement"
    precomputed=None,        # escape hatch: dict[H_qid, log_likelihood] — bypasses scipy
) -> Claim
```

Returns a Knowledge node with:

- `prior = 1 - ε` (clamped to True — likelihood is tautologically observed once computed)
- `metadata["bayes"]["role"] = "comparison"`
- `metadata["bayes"]["likelihoods"] = {H_qid: log_likelihood}`
- `metadata["bayes"]["data"] = [obs_qid, ...]`
- `metadata["bayes"]["model"] = predictive_model_qid`

This is the artifact upstream reasoning can cite: *"based on this comparison-result, we conclude…"*.

---

## 4. Compiler / Lowering

### 4.1 Lower paths

```
predict()      → PredictiveModel Knowledge atom (no factor by itself)
observation()  → PR 505's existing OBSERVATION lowering, plus noise metadata
likelihood()   → ComparisonResult Knowledge atom
                 + N IR `infer` strategies (one per H_i in the H set)
                 + auto-generated CONTRADICTION operators (multi-H exclusivity)
```

**No new FactorType.** All factors land in existing `IMPLICATION / CONJUNCTION / DISJUNCTION / EQUIVALENCE / CONTRADICTION / COMPLEMENT / SOFT_ENTAILMENT / CONDITIONAL` — verified against `gaia/bp/factor_graph.py:26`.

### 4.2 `likelihood()` lowering steps

Inputs: `data` (one or more OBSERVATION claims), `via=M` (PredictiveModel containing H set `{H_1, ..., H_N}`, distribution `D`, observable variable `X`).

```
Step 1: For each H_i:
    a. Read H_i.formula, extract Variable bindings (e.g. theta=0.75).
    b. Apply bindings to D, yielding concrete distribution D_i.
    c. logL_i = Σ_g D_i.logpmf(d_g) or Σ_g D_i.logpdf(d_g)
       (for noise model, see §4.5)

Step 2: Create ComparisonResult Knowledge:
    prior = 1 - ε
    metadata["bayes"]["likelihoods"] = {H_i.qid: logL_i}
    formula = None

Step 3: Normalise log-likelihoods into CPT entries:
    logL_max = max_i(logL_i)
    LR_i     = exp(logL_i - logL_max)              # ∈ (0, 1]
    p0_i     = 0.5                                 # shared neutral baseline
    p1_i     = clamp((1 - ε) · LR_i)               # ∈ [ε, 1-ε]

Step 4: For each H_i, emit an IR `infer` strategy plus its parameter record:
    premises                  = [H_i.qid]
    conclusion                = ComparisonResult.qid
    StrategyParamRecord.conditional_probabilities = [p0_i, p1_i]
    metadata["bayes"]["log_likelihood"] = logL_i

Step 5: If |H| ≥ 2 and exclusivity == "pairwise_contradiction":
    For each unordered pair (H_i, H_j):
        if no existing contradict(H_i, H_j) operator: emit one
        metadata["bayes"]["auto_generated_by"] = "likelihood:<cmp_qid>"
```

The CPT shape `[p0_i, p1_i]` is passed through the existing parameterization channel (`StrategyParamRecord.conditional_probabilities`, or the runtime `strategy_conditional_params` map) and is read by existing `gaia/bp/lowering.py:317` (`StrategyType.INFER` branch), which emits a `CONDITIONAL` factor with this CPT. Do not store this numeric CPT only in `Strategy.metadata`; current lowering does not read strategy metadata for infer parameters. No new lowering code is needed at the BP layer.

### 4.3 Why `[p0_i, p1_i]` is the right CPT

- `cpt[0] = P(cmp_result=1 | H_i=0) = p0_i = 0.5` — shared neutral baseline. When H_i is false, this factor contributes the same constant for every hypothesis.
- `cpt[1] = P(cmp_result=1 | H_i=1) = p1_i` — proportional to `LR_i = exp(logL_i - logL_max)`, Cromwell-clamped.

With cmp_result clamped to True (its `prior = 1-ε` enters BP via `gaia/bp/factor_graph.py:63` `add_variable` with the Cromwell-bounded prior, equivalent to a soft hard-evidence delta — see `gaia/bp/factor_graph.py:66` `observe()` runtime path for reference), the shared `p0_i=0.5` terms cancel when comparing mutually exclusive alternatives. Under an exhaustive two-H comparison, posterior odds obey:

```
posterior(H_a) / posterior(H_b)
  ≈ prior(H_a) / prior(H_b) · p1_a / p1_b
  ≈ prior(H_a) / prior(H_b) · exp(logL_a - logL_b)
```

within Cromwell clamp. The default `pairwise_contradiction` mode is weaker ("at most one true") and can leave residual mass on "none of the above"; it preserves pairwise odds among the listed alternatives but is not a strict normalized model-comparison posterior over only those alternatives. Authors who need posterior marginals to sum over an exhaustive H set should use `exclusivity="exhaustive_pairwise_complement"` when the H set is exhaustive.

**⚠️ Default exclusivity caveat — empirically verified.** Running the Mendel example (logL_3:1 = −1.2, logL_null = −5.1, true BF ≈ 49) against the current `gaia.bp` engine yields:

| `exclusivity` mode | exact posterior(H_3:1) | exact posterior(H_null) | exact posterior odds | BF odds? |
|---|---|---|---|---|
| `"pairwise_contradiction"` (default) | 0.657 | 0.014 | **≈ 46.9** | **Yes — within Cromwell clamp** |
| `"exhaustive_pairwise_complement"` | 0.978 | 0.021 | **≈ 46.9** | **Yes — within Cromwell clamp** |

The difference under the default mode is in the marginal probabilities, not in the pairwise odds: "at most one true" leaves residual belief mass on "neither H explains the data", which lowers both H marginals while the shared `p0` factors cancel in their ratio. Textbook Bayes-factor posterior odds are still recovered up to Cromwell clamp; exhaustive mode is needed when the H set should consume the full posterior mass over the compared alternatives.

**Guidance for authors:**

- If you are comparing a small number of point hypotheses and do **not** believe the set is exhaustive (the most scientifically cautious default), keep `"pairwise_contradiction"`. Report pairwise odds or ordering among H's, but do not describe the listed H marginals as a normalized exhaustive posterior.
- If your H set is genuinely exhaustive (e.g., Mendel 3:1 vs 1:1 segregation under a binary-mechanism framing), pass `exclusivity="exhaustive_pairwise_complement"` explicitly. The spec intentionally requires this to be opt-in so authors do not accidentally misstate epistemic coverage.
- The `gaia check` rule `bayes:hypothesis-prior-coherence` (§6.3) already enforces prior-sum invariants per mode; reviewers should treat a comparison with normalized-posterior claims and no explicit `exclusivity=` as a finding.

**Worked example (Mendel).** With logL_3:1 = −1.2 and logL_null = −5.1: logL_max = −1.2, LR_3:1 = 1.0, LR_null = exp(−3.9) ≈ 0.020. CPT entries: `p1_3:1 ≈ 1 − ε`, `p1_null ≈ 0.020`. Two `infer` strategies are emitted, both feeding cmp_result, with a shared `p0=0.5`. Under exhaustive two-H comparison, the posterior odds are ≈47.5 after Cromwell clamp (unclamped Bayes factor ≈49), which matches the intended likelihood-ratio semantics up to clamp.

**Information loss caveats.**
- This mapping preserves likelihood *ratios* across H but loses absolute likelihood scale. For v1 this is acceptable — the visible quantity in scientific writing is the Bayes factor (ratio), not the absolute likelihood. Authors needing absolute scale can read `metadata["bayes"]["likelihoods"]` directly off the ComparisonResult.
- Cromwell clamp caps extreme Bayes factors at roughly `(1-ε)/ε` per comparison. The raw log-likelihoods remain available in metadata for trace inspection and future exact backends.

### 4.4 Multi-data accumulation

`likelihood([d_A, d_B], via=M)` sums logL across data points (independence assumption). This is correct for genuinely independent observations. Authors needing joint likelihood (e.g., correlated A/B test) build the joint distribution into the `predict()` distribution — `likelihood()` does not attempt to model correlation.

### 4.5 Noise model handling

If the OBSERVATION carries `metadata["bayes"]["noise"] = Normal(0, σ)`, Step 1c becomes a convolution of D_i with the noise density:

```
continuous D_i:  P(observed | H_i) = ∫ D_i.pdf(x) · Normal(observed; x, σ).pdf dx
                                   (scipy.integrate.quad over D_i.support())

discrete D_i:    P(observed | H_i) = Σ_{x ∈ D_i.support()} D_i.pmf(x) · Normal(observed; x, σ).pdf
                                   (finite sum — Binomial, Poisson all have bounded effective support)
```

For v1: only `Normal` additive noise is supported. For other noise shapes, authors use the `precomputed=` escape hatch on `likelihood()`:

```python
my_logL = {H_3_1.qid: -2.34, H_null.qid: -57.2}
likelihood(data, via=M, precomputed=my_logL)   # bypasses scipy entirely
```

### 4.6 Auto-exclusivity policy

`likelihood()` defaults to `exclusivity="pairwise_contradiction"`. Other values:

| Value | Behaviour |
|---|---|
| `"pairwise_contradiction"` (default) | Auto-emit CONTRADICTION pairwise for |H| ≥ 2. "At most one true" — fits typical model-comparison semantics. |
| `"exhaustive_pairwise_complement"` | Auto-emit COMPLEMENT for |H| = 2 (XOR — exactly one true). For |H| ≥ 3, emit pairwise CONTRADICTION + a DISJUNCTION clamped True. |
| `"none"` | Emit no exclusivity factors. Author has full responsibility for inter-H constraints. |

Auto-emitted operators carry `metadata["bayes"]["auto_generated_by"]` for reviewer traceability and for `gaia migrate-` tooling.

If the author has already written `contradict(H_i, H_j)` (or `equal()`, etc.), the lowering deduplicates by pair-hash before emitting.

---

## 5. Extension Points (v2+)

The following are **out of v1 scope** but the v1 architecture preserves clean extension slots for them:

### 5.1 Composite (range) hypotheses

PR 505's grounding pass already supports `forall(theta_i ∈ grid, body)`. v2 reuses it:

```python
H_range = claim(formula=And(theta > 0.5, theta < 0.9), grid=np.linspace(0.5, 0.9, 20))
likelihood(data, via=predict({H_range, H_null}, ...))
```

The compiler grounds H_range into 20 atomic point hypotheses, each running through v1's path, then aggregates their belief via DISJUNCTION. **DSL surface unchanged.**

v1 raises `NotYetSupportedError` if a non-PARAMETER `formula` is encountered, with a "this requires v2 grounding extension" hint.

### 5.2 Posterior backends (PyMC / Stan / NumPyro)

`gaia.lang.bayes.adapters/` is the slot. The Distribution Protocol's `.logpmf/.logpdf` is the swappable surface — a `pymc_backend` can override these to perform NUTS/HMC posterior integration internally. The DSL never sees the backend choice; it appears as `Distribution.backend` config.

### 5.3 Custom noise models

`observation(noise=...)` accepts arbitrary `Distribution` objects in v2. v1 only supports Normal additive; authors needing more route through `likelihood(precomputed=...)`.

### 5.4 Hierarchical / latent-variable models

PR 505's quantifier (`forall`) + Variable mechanism already expresses hierarchy at the lifted layer. v2 adds `predict(latent=...)` to mark variables as marginalisation targets; the grounding pass then expands them.

### 5.5 Multi-observation accumulation across packages

Already supported in v1 — author writes multiple `likelihood()` calls referencing the same H set, each producing a separate ComparisonResult. BP composes the evidence automatically.

### 5.6 Out-of-scope in any release

- Decision-theoretic primitives (utility, action selection)
- Frequentist hypothesis testing (p-values, CIs, NHST) — Gaia is Bayesian-native
- Causal interventions (do-calculus, counterfactuals) — PR 505 reserves `causes()` predicate; semantics in v0.6+

---

## 6. Error Handling and `gaia check` Integration

### 6.1 Compile-time hard errors

| Trigger | Error | Source |
|---|---|---|
| Distribution param Variable unbound under H | `BindingError: <var.symbol> is unbound under <H.qid>` | `predict.lower()` |
| H's `formula` is not a PARAMETER shape (`Equals(var, const)`) | `HypothesisShapeError` | `likelihood.lower()` Step 1 |
| `observation()` value type mismatches Variable domain | `DomainTypeError` | PR 505's existing type check |
| Distribution param physically out of range (e.g. Binomial.p > 1) | `ValueError` | `Distribution.__init__` |
| Empty H set passed to `predict()` or `likelihood()` | `ValueError: empty hypothesis set` | `predict.__init__` |

### 6.2 Compile-time warnings (non-blocking)

- `predict({H1, H2})` without explicit `contradict()`: warn + auto-emit (per §4.6).
- `observation(noise=Normal(0, σ))` with σ ≫ predict's distribution scale: warn `"noise dominates signal — likelihood may be uninformative"`.
- Some `logL_i = -inf`: warn + force `p1_i = ε` after normalization. If all `logL_i = -inf`, raise a hard error because no model assigns support to the data.

### 6.3 New `gaia check` rules

| Rule | Description |
|---|---|
| `bayes:dangling-prediction` | A `predict()` PredictiveModel never referenced by `likelihood()`. |
| `bayes:unobserved-prediction-target` | `predict()` observable has no matching `observation()` and is not imported from another package. |
| `bayes:hypothesis-prior-coherence` | Dispatch on `exclusivity` mode: for `pairwise_contradiction`, error if Σ prior(H_i) > 1; for `exhaustive_pairwise_complement`, error if Σ prior(H_i) ≠ 1 (within ε). |
| `bayes:likelihood-without-data` | `likelihood()` references an OBSERVATION with no value bound. |

Existing `gaia check` machinery (factor coherence, double-prior conflict) remains unchanged.

### 6.4 Error message standard

Every bayes-module error MUST include:

1. The Knowledge label / qid involved.
2. The Variable symbol involved (where applicable).
3. A "fix hint" subclause naming the missing or conflicting construct.

Example: `BindingError: Variable 'theta' (gaia.bayes:mendel::theta) is unbound under hypothesis 'gaia.bayes:mendel::H_3_1'. Fix: add 'parameter(theta, <value>)' before the predict() call.`

---

## 7. Testing Strategy

### 7.1 Test layout

```
tests/gaia/lang/bayes/
├── unit/
│   ├── test_distributions.py      # logpmf/logpdf vs scipy.stats reference
│   ├── test_predict.py            # PredictiveModel construction, binding resolution
│   ├── test_observe.py            # OBSERVATION + noise metadata
│   └── test_likelihood.py         # logL, StrategyParamRecord CPTs, exclusivity policies
├── compiler/
│   ├── test_lower_predict.py      # PredictiveModel → IR atom
│   ├── test_lower_likelihood.py   # ComparisonResult + N infer strategies/params + auto-CONTRADICTION
│   └── test_likelihood_to_bp.py   # IR → factor graph end-to-end
├── integration/
│   ├── test_mendel_3to1.py        # Canonical full-pipeline reference
│   ├── test_galileo_lunar.py      # Normal(μ, σ) measurement scenario
│   ├── test_multi_h.py            # 3+ H comparison, exclusivity enforced
│   ├── test_ab_test.py            # Multi-data logL accumulation
│   └── test_external_h_import.py  # Cross-package H reference
└── check/
    └── test_gaia_check_bayes.py   # Each §6.3 rule's positive/negative cases
```

### 7.2 Property-based invariants

| Invariant | Verification |
|---|---|
| With equal priors and exhaustive H, `argmax_i(posterior_i)` == `argmax_i(logL_i)` after BP | Random N H + random data, hypothesis library |
| `likelihood([d_A]) + likelihood([d_B])` ≡ `likelihood([d_A, d_B])` (up to ε) | Two-path equivalence test |
| All BP outputs ∈ (ε, 1-ε) (Cromwell) | Iterate over integration cases |
| Posterior monotonic with iter count, eventually stable | BP convergence smoke test |

### 7.3 What **not** to test

- scipy.stats numerical correctness (not our concern).
- Exact iteration counts for BP convergence (fragile).
- Error message string contents (only error class).

### 7.4 Mendel as the golden reference

`test_mendel_3to1` is the canonical end-to-end test. Failing it = bayes module is broken. Doubles as the executable example in `docs/foundations/gaia-lang/bayes.md`.

```python
def test_mendel_full_pipeline():
    pkg = build_mendel_package()
    ir = compile(pkg)
    fg = lower(ir)
    beliefs = run_bp(fg)
    assert beliefs[H_3_1.qid] > 0.99
    assert beliefs[H_null.qid] < 0.01
    assert beliefs[cmp_result.qid] > 0.99
```

### 7.5 Performance smoke

- N=10 H, 10 data points: BP converges <100 ms on dev hardware.
- 100 OBSERVATION claims, 10 H: full compile + BP <1 s.

Not a benchmark, just regression detection for the auto-exclusivity O(N²) factor count.

---

## 8. Migration and Coexistence

### 8.1 `evidence()` → deletion

PR #506 has not merged and no first-party package consumes `evidence()`. **The bayes module PR includes evidence-verb deletion** — no deprecation alias.

PR #506 will be closed with the disposition:

> Superseded by `gaia.lang.bayes` module (spec: `docs/specs/2026-05-04-bayes-module-design.md`). The module subsumes `evidence()`'s role with a structurally cleaner `predict / likelihood` decomposition.

### 8.2 Distribution import path

- v0.6: New canonical location is `gaia.lang.bayes.distributions` and convenience re-exports from `gaia.lang.bayes`.
- No `gaia.stats` shim is introduced. PR #506 is unmerged, current `main` has no `gaia.stats`, and the stated migration policy for `evidence()` is deletion without deprecation.

No `gaia migrate-bayes` command is required for v1 unless a later release creates a public import path that actually needs migration.

### 8.3 Documentation migration

| Doc | Action |
|---|---|
| `docs/foundations/gaia-lang/dsl.md` `evidence` / `infer` sections | Replace `evidence` text with bayes-module overview pointer; keep `infer` (low-level escape hatch). |
| `docs/foundations/gaia-lang/bayes.md` | **NEW** — canonical foundation document for the bayes module. Mirrors §3–§4 of this spec, scaled to authoring tutorial. |
| `docs/specs/2026-04-23-gaia-foundation-spec.md` §11.3 (evidence) | Mark `[superseded by bayes module]`, redirect to this spec. |
| `docs/foundations/bp/potentials.md` | No change — BP layer untouched. |

### 8.4 Coexistence with `infer` and `associate`

`gaia check` adds a lint:

> `bayes:infer-likelihood-overlap`: An (H, observable) pair has both an `infer()` strategy and a `bayes.likelihood()` factor. Pick one; they are not additive.

`associate()` is orthogonal (symmetric correlation) and untouched.

---

## 9. Implementation Milestones

Three independent PR slices, ordered by dependency. Each independently shippable.

### Milestone A — Distribution module + protocol

- Add `gaia/lang/bayes/distributions/`.
- Add `Distribution` Protocol + scipy backend.
- Add `scipy` as a direct runtime dependency in `pyproject.toml`.
- Tests: distribution literals, logpmf/logpdf parity with scipy.

### Milestone B — `predict()` + `likelihood()` + lowering

- `gaia/lang/bayes/runtime/prediction.py`, `comparison.py` — Knowledge subclasses.
- `gaia/lang/bayes/verbs/predict.py`, `likelihood.py` — DSL surface.
- `gaia/lang/bayes/compiler/lower.py` — Lang→IR lowering per §4.
- Extend `observation()` (PR 505) with `noise=` parameter.
- Tests: §7.1 unit + compiler + integration.

### Milestone C — `evidence()` deletion + docs + migration tool

- Delete `gaia.lang.dsl.evidence_verb` and tests.
- Close PR #506.
- Write `docs/foundations/gaia-lang/bayes.md`.
- Update `docs/foundations/gaia-lang/dsl.md` evidence section.

Each milestone goes through `writing-plans` skill independently for detailed task breakdown.

**Cross-milestone reminder:** because no `gaia.stats` shim is created, there is no v0.7 cleanup ticket for that path. Keep migration work limited to actual public APIs.

---

## 10. Open Questions

These are not blocking the design but flagged for implementation discussion:

1. **`likelihood(..., exclusivity=...)` parameter shape.** Should it accept a string enum (proposed) or be split into multiple kwargs (`exclusive=True`, `exhaustive=False`)? String is more compact; kwargs is more discoverable in IDEs.

2. **Naming: `observation()` vs `observe()`.** PR 505 introduces `observation()` (noun). Some authors may prefer the verb `observe()`. Both can coexist as aliases; default in docs to be decided.

3. **Cross-package PredictiveModel reuse.** A package can `import M from upstream_pkg` and write `likelihood(my_data, via=M)`. The Variable bindings on M's distribution come from upstream — needs a check that those bindings resolve in the consuming package's H set. v1 may be conservative (require all H to be local) and lift in v2.

4. **`exclusivity="exhaustive"` for |H|=3+.** Pairwise CONTRADICTION + clamped DISJUNCTION is correct but emits `O(N²)` factors. A multi-variable "exactly-one" Operator would be cleaner but is a new IR primitive. Defer until N=10+ scenarios actually appear.

5. **Backend selection ergonomics for v2+.** Per-Distribution `.backend = "pymc"` vs a global `gaia.bayes.set_backend("pymc")` config. Punt to v2.

---

## 11. Acceptance Criteria

The design is implemented when:

1. `from gaia.lang import bayes` exposes `predict / likelihood / Binomial / Normal / Beta / Poisson / ...`.
2. The Mendel pipeline test (§7.4) passes with H_3_1 posterior > 0.99.
3. PR #506 is closed and `gaia.lang.dsl.evidence_verb` is removed.
4. `gaia check` reports each of the four `bayes:*` rules in `tests/gaia/lang/bayes/check/`.
5. `docs/foundations/gaia-lang/bayes.md` exists and its code examples are exercised in CI.
6. No new `FactorType` is added to `gaia/bp/factor_graph.py`.
7. No new `OperatorType` is added to `gaia/ir/operator.py`.
8. `gaia.stats` is not introduced as a compatibility shim unless a real merged public API later requires it.
9. With equal priors and exhaustive H, the property `argmax_i(posterior_i) == argmax_i(logL_i)` holds across the property-based test suite (random N H + random data).

---

## 12. References

- PR 505 (claim formula schema design): `docs/specs/2026-05-04-claim-formula-schema-design.md`
- PR 506 (evidence verb — superseded): `gaia/lang/dsl/evidence_verb.py` on branch `codex/evidence-verb`
- BP factor types: `gaia/bp/factor_graph.py:26`
- IR operators: `gaia/ir/operator.py:14`
- IR strategies: `gaia/ir/strategy.py`
- BP lowering: `gaia/bp/lowering.py`
- Foundation spec: `docs/specs/2026-04-23-gaia-foundation-spec.md` §11
