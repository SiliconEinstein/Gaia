# Evidence Factor — Design Spec

> **Status:** Target design
> **Date:** 2026-04-25
> **Scope:** A new `evidence()` DSL verb, a new `EvidenceFactor` Action IR entity, a small initial library of pluggable `LikelihoodModel` classes, and the BP lowering that ties these together with Claim priors and methodological-assumption gates.
> **Relationship to other docs:**
> - Subsumes the narrow `associate.prior_* ↔ PRIORS` field-collision fix tracked in **issue #485** by making the `prior_*` kwargs unnecessary rather than renaming them.
> - Implements a v0.5-compatible subset of the `EvidenceFactor` direction proposed in **issue #448**; defers the full "remove probabilistic warrant" rework.
> - Extends (does not replace) the `gaia.evidence` canonical template direction discussed in `2026-04-24-gaia-composition-primitive-design.md` §1.3 / §11.4 — `evidence()` plays the same role in the Correlate family that `compute()` plays in the Support family.

---

## 0. Motivation

### 0.1 The concrete failure

The v0.5 Mendel example (PR #482) reaches a hard collision in the inference engine:

```
ValueError: associate strategy lcs_...: conflicting marginal providers for
'...:f2_count_observation': metadata.prior=0.95, associate prior=0.024
```

The two numbers are not conflicting estimates of the same quantity:

| 0.95 | 0.024 |
|---|---|
| `P(R = 1)` — marginal that the reporter (Mendel) recorded the count accurately | `P(O = 1 \| R = 1) = Σ_M P(O=1 \| M) P(M)` — marginal of the specific count event under the hypothesis mixture, conditional on an accurate report |

Both are legitimate marginals of the same underlying joint `P(M, R, O)` — but along **different axes**. Gaia v0.5 currently has a single `metadata.prior` slot per Claim that is asked to carry both, so when a package supplies them from two different authoring sites (`PRIORS` dict and `associate(..., prior_b=...)`), the inference engine sees them as an inconsistency and refuses to compile.

### 0.2 Why `associate` / `infer` can't solve this cleanly

`associate` and `infer` pass a small number of opaque scalars (`p_e_given_h`, `p_e_given_not_h`, `prior_a`, `prior_b`) through to the IR. These scalars are computed by the user outside the framework (see `examples/mendel-v0-5-gaia/src/mendel_v0_5/probabilities.py` for a typical case). The framework has no view into the underlying statistical model, so it cannot:

1. Introspect the likelihood family (e.g., "this is Binomial(N, 3/4)") for review tooling or sensitivity analysis.
2. Consume structured data off the observation Claim (e.g., `metadata.dominant = 295`) — the Claim content is natural-language text and the scalar has to be pre-computed externally.
3. Treat methodological assumptions (independence, measurement validity, stopping rules) as first-class Claims that gate the factor's strength.
4. Compose multiple independent observations of the same hypothesis without duplicating user arithmetic.
5. Swap the alternative hypothesis (e.g., diffuse prior vs. coin-flip null vs. specific alternative) without rewriting every scalar.

### 0.3 What this spec changes

Introduces **one new DSL verb**, **one new Action subclass**, and **a small `LikelihoodModel` protocol** with a starter library. The existing `infer()` and `associate()` verbs are retained as thin shorthands over the new verb and remain source-compatible.

---

## 1. DSL surface: `evidence()`

### 1.1 Signature

```python
def evidence(
    conclusion: Claim | list[Claim],
    *,
    data: Claim | list[Claim],
    model: LikelihoodModel,
    assumptions: list[Claim] | None = None,
    query: str | dict | None = None,
    background: list[Knowledge] | None = None,
    rationale: str = "",
    label: str | None = None,
) -> Claim:
    """Statistical evidence: an observation Claim updates one or more hypothesis
    Claims through a pluggable likelihood model. Returns a generated helper Claim
    with ``metadata.helper_kind = "evidence"``.
    """
```

### 1.2 Parameters

| Name | Type | Meaning |
|---|---|---|
| `conclusion` | `Claim \| list[Claim]` | The hypothesis (or hypotheses, for model comparison) whose belief is updated by the evidence. Must already exist as a `Claim` before the call. |
| `data` | `Claim \| list[Claim]` | The observation Claim(s). Each must have `metadata` fields matching what `model` expects (see §3.2). `prior` on `data` retains its reliability semantics (§5.1) and is **not** touched by `evidence()`. |
| `model` | `LikelihoodModel` | A pluggable statistical model. Owns the likelihood computation for H and for the alternative, plus the mapping from `data.metadata` → model inputs. See §3. |
| `assumptions` | `list[Claim] \| None` | Validity gates. Claims whose posterior belief multiplicatively scales the evidence factor's strength (§5.2). If any gate's posterior approaches 0, the factor loses force; if all are near 1, the factor operates at full strength. |
| `query` | `str \| dict \| None` | An optional structured description of what quantity the user cares about (e.g., `"theta_B > theta_A"`). Consumed by `model.factor_potential` for parametric queries; stored on the helper Claim's metadata for review tooling. |
| `background` | `list[Knowledge] \| None` | Contextual notes, as with other Actions. Non-probabilistic. |
| `rationale`, `label` | `str`, `str \| None` | Standard Action metadata. |

### 1.3 Return value

Following the Correlate-family convention established by `infer()` and `associate()` in v0.5 (`helper_kind = "likelihood"` / `"association"`), `evidence()` returns a **generated helper Claim** with:

```python
helper.metadata = {
    "generated": True,
    "helper_kind": "evidence",
    "review": True,
    "model_class": model.__class__.__name__,
    "model_params": model.serialise_params(),
    "query": query,
    "relation": {
        "type": "evidence",
        "conclusion": conclusion,
        "data": data,
        "assumptions": assumptions or [],
    },
}
```

The helper is attached to each target Claim's `supports` list (one helper per target, sharing identity via `_structure_hash` of the evidence factor — see §2.3).

### 1.4 Invariants

- `evidence()` **never writes `claim.prior`** on any input Claim. All inference output flows through the BP lowering into posteriors (`claim.belief`).
- `evidence()` **does not accept `prior_*` kwargs**. The Bayesian marginal that was exposed as `prior_b` in `associate()` is now computed inside `model.factor_potential` and stored transiently in the BP factor, never on a Claim.
- `assumptions` entries must be `Claim` objects (they must have a `prior` themselves so they can gate the factor). `background` is for non-probabilistic `Knowledge` (typically `Note`).

---

## 2. IR layer: `EvidenceFactor` Action

### 2.1 Class hierarchy placement

```python
# gaia/lang/runtime/action.py
@dataclass
class Correlate(Action):
    """Probabilistic soft constraint between Claims."""
    helper: Claim | None = None

@dataclass
class Infer(Correlate): ...       # unchanged
@dataclass
class Associate(Correlate): ...   # unchanged

# NEW:
@dataclass
class EvidenceFactor(Correlate):
    """Statistical evidence via pluggable likelihood model."""
    conclusion: tuple[Claim, ...] = ()
    data: tuple[Claim, ...] = ()
    assumptions: tuple[Claim, ...] = ()
    model: LikelihoodModel | None = None
    query: str | dict | None = None
```

### 2.2 Compiled IR strategy

`EvidenceFactor` compiles to a new IR strategy type:

```python
IrStrategy(
    scope="local",
    type="evidence",
    premises=[knowledge_map[id(c)] for c in action.conclusion],
    conclusion=knowledge_map[id(action.helper)],
    background=[...],
    metadata={
        "model_class": action.model.__class__.__name__,
        "model_params": action.model.serialise_params(),
        "query": action.query,
        "data_refs": [knowledge_map[id(d)] for d in action.data],
        "assumption_refs": [knowledge_map[id(a)] for a in action.assumptions],
        "factor_potential": action.model.compile_potential(
            data=[d.metadata for d in action.data],
            query=action.query,
        ),  # serialised numeric form; see §3.3
    },
)
```

Note that individual scalar likelihoods are **not** stored at the IR top level (as `p_a_given_b`, `prior_a`, etc. are for `associate`). Instead the numerical content is encapsulated in `metadata.factor_potential`, a model-specific serialised form (e.g. a tuple `(log_lik_h, log_lik_not_h)` for two-hypothesis cases, or a general table for K hypotheses — see §3.3).

### 2.3 Identity / structure hash

Following v0.5 precedent:

```python
structure_hash = SHA-256(canonical_json({
    "type": "evidence",
    "conclusion": sorted([c.claim_id for c in conclusion]),
    "data": sorted([d.claim_id for d in data]),
    "assumptions": sorted([a.claim_id for a in assumptions]),
    "model_class": model.__class__.__name__,
    "model_params": model.serialise_params(),
    "query": query,
}))
```

Two `evidence()` calls with the same model, same data, same gates, and same query deduplicate to the same helper Claim and the same IR strategy.

---

## 3. Model protocol: `LikelihoodModel`

### 3.1 Abstract base

```python
# gaia/lang/runtime/likelihood.py (new module)

from abc import ABC, abstractmethod
from typing import Any

class LikelihoodModel(ABC):
    """A pluggable statistical model consumed by ``evidence()``."""

    @abstractmethod
    def expected_fields(self) -> list[str]:
        """Names of ``data.metadata`` keys this model reads."""

    @abstractmethod
    def log_likelihood(
        self,
        *,
        hypothesis_index: int,          # 0-based index into conclusion tuple
        data_values: list[dict],        # one dict per ``data`` Claim
        query: str | dict | None,
    ) -> float:
        """Log P(data | hypothesis_index, query)."""

    def log_likelihood_alternative(
        self,
        *,
        data_values: list[dict],
        query: str | dict | None,
    ) -> float | None:
        """Log of the alternative / baseline likelihood, for two-hypothesis models.
        Returning ``None`` means 'no built-in alternative'; the BP engine will then
        need multiple entries in ``conclusion`` to form the Bayes factor."""
        return None

    def compile_potential(
        self,
        *,
        data: list[dict],
        query: str | dict | None,
    ) -> dict[str, Any]:
        """Return a serialisable summary of the factor potential sufficient for
        BP lowering. Default: ``{"log_lik_h": ..., "log_lik_not_h": ...}`` for the
        binary case. Override for K-ary models."""
        ...

    def serialise_params(self) -> dict[str, Any]:
        """Emit a JSON-serialisable view of the model's own constructor parameters
        for IR storage. Default: shallow ``__dict__``."""
        return {k: v for k, v in vars(self).items() if not k.startswith("_")}
```

### 3.2 Contract with `data.metadata`

For each `data` Claim in an `evidence()` call, the framework:

1. Reads `model.expected_fields()`.
2. Looks up each expected field on `data.metadata`.
3. Builds a single `dict` of that Claim's inputs.
4. Passes the list of these dicts as `data_values`.

A compile-time check raises a clear error if a required field is missing:

```
EvidenceModelContractError: BinomialAgainstDiffusePrior expects fields
['dominant', 'total'] on data Claim 'f2_count_observation' but only
['dominant'] is present.
```

### 3.3 Factor potential encoding

For the two-hypothesis case (one conclusion Claim, a built-in alternative), the potential is stored as:

```python
{
    "kind": "binary_bayes_factor",
    "log_lik_h": -3.065,          # e.g. log Binomial(395, 3/4).pmf(295)
    "log_lik_not_h": -5.981,      # e.g. log(1 / (395 + 1))
    "log_bayes_factor": 2.916,    # redundant but stored for review convenience
}
```

For K conclusions without a built-in alternative:

```python
{
    "kind": "k_way_likelihood",
    "log_likelihoods": [-3.065, -7.412, -9.109],  # one per conclusion
}
```

Additional `kind` values MAY be added as new model families are introduced; the IR schema treats `metadata.factor_potential` as an open, model-owned record.

---

## 4. Initial model library

The spec commits to shipping the following concrete models in the same PR that lands `evidence()`. Others can follow.

### 4.1 `ScalarBayesFactor`

The degenerate compatibility model. Wraps a pair of scalars exactly as `infer()` does today.

```python
class ScalarBayesFactor(LikelihoodModel):
    def __init__(self, *, p_h: float, p_not_h: float): ...

    def expected_fields(self): return []
    def log_likelihood(self, *, hypothesis_index, data_values, query):
        return log(self.p_h) if hypothesis_index == 0 else log(self.p_not_h)
    def log_likelihood_alternative(self, **_): return log(self.p_not_h)
```

Purpose: makes `infer()` implementable as a shorthand (§6.1) and gives users a migration escape hatch.

### 4.2 `BinomialPointLikelihood`

```python
class BinomialPointLikelihood(LikelihoodModel):
    def __init__(self, *, p: float, count_field: str = "dominant", total_field: str = "total"): ...
```

Returns only the point likelihood under `p`. No built-in alternative; users compose two of these via `PointwiseRatio` (§4.6) if they want an explicit Bayes factor.

### 4.3 `BinomialAgainstDiffusePrior`

```python
class BinomialAgainstDiffusePrior(LikelihoodModel):
    def __init__(self, *, p: float, count_field: str = "dominant", total_field: str = "total"): ...
```

Two hypotheses:

- **H**: `X ~ Binomial(N, p)` with supplied `p`.
- **¬H**: `X ~ Binomial(N, p')` with `p' ~ Uniform[0, 1]`. Marginal likelihood `1 / (N + 1)`, closed form.

This is the canonical "is this specific Mendelian ratio better than generic binomial chance?" model.

### 4.4 `BinomialVsBinomial`

```python
class BinomialVsBinomial(LikelihoodModel):
    def __init__(self, *, p_h: float, p_alt: float, ...): ...
```

Point-against-point for scenarios where the alternative is a specific binomial (e.g., coin-flip null at `p_alt = 0.5`).

### 4.5 `GaussianMeasurementModel`

```python
class GaussianMeasurementModel(LikelihoodModel):
    def __init__(self, *, sigma: float, value_field: str = "value"): ...
```

`X ~ Normal(mu_h, sigma)` under the hypothesis; alternative is either explicit (another `GaussianMeasurementModel` via `PointwiseRatio`) or a specified broad Gaussian prior on `mu`. Deferred details in §9.

### 4.6 `PointwiseRatio`

```python
class PointwiseRatio(LikelihoodModel):
    def __init__(self, *, numerator: LikelihoodModel, denominator: LikelihoodModel): ...
```

Composes two sub-models into a Bayes-factor model. Used when the user wants H vs. a hand-picked alternative that isn't the diffuse default.

### 4.7 (Future) `TwoBinomialModel`, `PoissonPointLikelihood`, `IndependentBinomialBatch`

Listed here for scoping — not part of the landing PR. `IndependentBinomialBatch` would take a list of `data` entries and multiply likelihoods, enabling the Mendel-with-seven-traits scenario.

---

## 5. BP lowering

### 5.1 Claim prior remains reliability

`claim.prior` (the value written by `PRIORS` or defaulted on `Claim(... prior=0.5)`) is treated **unambiguously as reliability / subjective prior**. It is the marginal P(claim is true) under the user's "report-accuracy" axis and is independent of any statistical likelihood.

`evidence()` never writes `claim.prior`. The inference engine reads `claim.prior` as the initial belief state for BP, as it always has.

### 5.2 Factor potential gated by assumptions

Each `EvidenceFactor` contributes a BP factor whose potential is the `LikelihoodModel`'s `log_likelihood` output, **scaled by a gating term derived from `assumptions`**:

```text
log φ_evidence(conclusion | data) =
    log_likelihood(hypothesis | data) · g(assumptions)
```

where the gating function `g` is:

```text
g(assumptions) = ∏_{A ∈ assumptions} claim_belief(A)
```

evaluated at each BP iteration using the current posterior of each gate Claim. This yields the intuitive behaviour:

- All gates at posterior 1 → factor at full strength (equivalent to `g = 1`).
- Any gate at posterior 0 → factor contributes 0 log-likelihood (effectively deleted from the graph).
- Gate posteriors in between scale the factor smoothly.

### 5.3 Composition with hypothesis prior and posterior

For a single-conclusion evidence factor with a binary bayes factor potential, the BP update on `conclusion.belief` is:

```text
posterior(H)        prior(H)         exp(log_lik_h · g)
─────────────── = ─────────────── · ──────────────────────
posterior(¬H)     prior(¬H)         exp(log_lik_not_h · g)
```

which reduces to standard Bayes when `g = 1`, and becomes a no-op when `g = 0`.

### 5.4 Interaction with `exclusive` and multi-target evidence

If `conclusion = [H1, H2, ...]` and the hypotheses are declared `exclusive(H1, H2, ...)`, BP enforces `Σ belief(H_i) = 1` after each evidence-factor update, giving standard K-way model comparison. If they are not exclusive, the K likelihoods enter independently and each H_i's belief moves only by its own BF against the reference (no cross-normalisation).

---

## 6. Relation to existing verbs

### 6.1 `infer()` becomes a shorthand

```python
def infer(evidence_claim, *, hypothesis, p_e_given_h, p_e_given_not_h,
          prior_hypothesis=None, prior_evidence=None, ...):
    if prior_hypothesis is not None or prior_evidence is not None:
        warnings.warn(
            "infer()'s prior_hypothesis / prior_evidence kwargs are deprecated. "
            "The reliability prior belongs on PRIORS; the Bayes marginal is "
            "computed inside evidence().model. See #485.",
            DeprecationWarning,
        )
    return evidence(
        conclusion=hypothesis,
        data=evidence_claim,
        model=ScalarBayesFactor(p_h=p_e_given_h, p_not_h=p_e_given_not_h),
        rationale=rationale,
        label=label,
    )
```

Semantics preserved for existing callers; `prior_*` kwargs accepted but ignored and warned about. The hard `ValueError` on PRIORS conflict is removed entirely because `evidence()` doesn't write `claim.prior`.

### 6.2 `associate()` becomes a shorthand

Analogous to `infer`, `associate(a, b, p_a_given_b, p_b_given_a, prior_a, prior_b)` is rewritten as a symmetric evidence factor:

```python
evidence(
    conclusion=[a, b],
    data=[],  # associate has no separate "data" Claim; both sides are hypotheses
    model=SymmetricScalarAssociation(p_a_given_b=..., p_b_given_a=...),
)
```

(A `SymmetricScalarAssociation` model is added to the starter library for this purpose.) `prior_a` / `prior_b` kwargs accepted with a deprecation warning; they do not participate in the BP factor and do not write to `claim.prior`.

### 6.3 Review manifest

`EvidenceFactor`'s helper Claim gets the same review lifecycle (`unreviewed` → `accepted` / `rejected`) as existing Correlate helpers. No changes to review infrastructure are required.

---

## 7. Worked example: Mendel

### 7.1 Before (current PR #482)

```python
# probabilities.py — user hand-computes ALL five scalars
association_parameters = mendel_count_association_parameters()

# __init__.py
f2_count_observation = observe("F2 counts 295:100 ...")               # PRIORS = 0.95

f2_dominant_count_specific = derive(                                  # workaround node
    "F2 dominant count = 295 of 395",
    given=f2_count_observation,
)

associate(
    mendelian_segregation_model,
    f2_dominant_count_specific,
    p_a_given_b=association_parameters.p_mendelian_given_count,
    p_b_given_a=association_parameters.p_count_given_mendelian,
    prior_a=0.5,
    prior_b=association_parameters.prior_count,
    rationale="...",
)
```

Drawbacks: 5 hand-computed scalars; a workaround `derive` node that exists only to dodge the `metadata.prior` collision; framework has no view into `BinomialModel(p=3/4)`; blending's `2/3` strawman used to previously live in the same `probabilities.py`.

### 7.2 After

```python
# probabilities.py — DELETED entirely; the model owns the computation

# __init__.py
f2_count_observation = Claim(                                         # PRIORS = 0.95 (reliability)
    "F2 counts 295 dominant / 100 recessive",
    role="observation",
    metadata={"dominant": 295, "total": 395},
)

mendelian_segregation_model = Claim(
    "Mendelian segregation: p(dominant) = 3/4 in F2.",
    prior=0.5,
    role="hypothesis",
)

independent_bernoulli_valid = Claim(
    "F2 individuals behave as independent Bernoulli trials with shared p.",
    prior=0.9,
)

evidence(
    conclusion=mendelian_segregation_model,
    data=f2_count_observation,
    assumptions=[independent_bernoulli_valid],
    model=BinomialAgainstDiffusePrior(p=3/4),
    rationale="Mendelian segregation predicts Binomial(N, 3/4); the diffuse "
              "alternative is p ~ Uniform[0, 1] with marginal 1/(N+1).",
)

# Blending still participates, but only qualitatively, through contradicts:
blending_predicts_f2_continuous = derive(...)
f2_discrete_classes_blending_conflict = contradict(
    blending_predicts_f2_continuous, f2_has_discrete_classes_observation,
)
# etc. — unchanged from PR #482's refactored form.
```

Gains:

- `probabilities.py` deleted — 100 lines of user-maintained numerical code replaced by `BinomialAgainstDiffusePrior(p=3/4)`.
- `f2_dominant_count_specific` workaround node deleted — `evidence()` targets the observation directly.
- No PRIORS collision — `evidence()` doesn't write `claim.prior`.
- `independent_bernoulli_valid` is now a first-class Claim whose posterior gates the evidence; a reviewer can change its prior to do methodological sensitivity analysis without touching any of the statistical code.
- Replacing `BinomialAgainstDiffusePrior(p=3/4)` with `BinomialVsBinomial(p_h=3/4, p_alt=1/2)` (the "Mendel vs coin-flip null" variant) is a one-line swap.

---

## 8. Migration plan

### Phase A — Landable in one PR (~1 week scope)

1. Add `LikelihoodModel` protocol and the starter library: `ScalarBayesFactor`, `BinomialPointLikelihood`, `BinomialAgainstDiffusePrior`, `BinomialVsBinomial`, `PointwiseRatio`, `SymmetricScalarAssociation`, `GaussianMeasurementModel`.
2. Add `EvidenceFactor` Action subclass and its compile rule.
3. Add `evidence()` DSL verb and export from `gaia.lang`.
4. Implement BP lowering for `evidence` strategies, including assumption gating (§5.2).
5. Rewrite `infer()` and `associate()` as shorthands over `evidence()` (§6). Remove the hard `ValueError` on PRIORS conflict.
6. Add a `test_evidence_verb.py` regression suite covering: basic binary factor, gate scaling, multi-target model comparison, deprecated-kwargs warnings.
7. Document in `docs/foundations/language/gaia-language-spec.md`.

### Phase B — Example migrations (~1 week scope)

1. Migrate `examples/mendel-v0-5-gaia/` to `evidence() + BinomialAgainstDiffusePrior`. Delete `probabilities.py` and the workaround `derive` node.
2. Audit `examples/galileo-v0-5-gaia/` — Galileo is currently purely qualitative, so likely unaffected; confirm.
3. Document the migration in `examples/` README and link from issue #485.

### Phase C — Extended model library (indefinite timeline)

Add `TwoBinomialModel` (AB test), `PoissonPointLikelihood`, `IndependentBinomialBatch` (multi-trait Mendel), `HierarchicalBinomial`. Driven by user demand from real packages.

### Backward compatibility guarantees

- All existing `infer()` and `associate()` calls in v0.5 packages continue to compile and produce the same BP factors.
- The `prior_hypothesis` / `prior_evidence` / `prior_a` / `prior_b` kwargs are accepted for one release, with a `DeprecationWarning` pointing to `evidence()` and this spec. Removal scheduled for the release after that.
- `metadata.prior` field on Claims is unchanged.

---

## 9. Open questions

### 9.1 Gating function

§5.2 uses `g = ∏ posterior(assumption_i)` (AND semantics). Alternatives include:

- A "noisy-AND" via the existing `noisy_and` operator, letting users declare failure-independence between gates explicitly.
- A configurable `gate_semantics` kwarg on `evidence()` for `"and"` vs `"or"` vs `"noisy_and"`.

Default AND is probably right for v0.5; noisy-AND is a plausible follow-up.

### 9.2 Continuous Gaussian alternative

`GaussianMeasurementModel` against a broad-Gaussian alternative on the mean parameter: analytic? Numeric integration? Discretised latent? Needs spec-level decision before landing. Deferring to Phase A.2 implementation choice.

### 9.3 `data` with unreliable reporter

Currently the spec lets `f2_count_observation.prior < 1` act as an authorship reliability. But this is not yet propagated into the evidence factor's potential (only `assumptions` entries are). Two options:

1. Treat the observation Claim itself as an implicit gate: `g_effective = data.prior · ∏ assumptions.posterior`.
2. Require users to lift reliability into an explicit `Claim("reporter accurate", ...)` and put it into `assumptions`. More verbose but more explicit about what's being modeled.

This spec currently leaves this as author convention — reliability lives on `data.prior` and is consulted by the BP engine as the Claim's marginal for the reliability axis, but the factor doesn't multiplicatively scale by it. Revisit once the Mendel migration is done.

### 9.4 Model identity and deterministic hashing

`serialise_params()` is the basis for structure-hash-level identity (§2.3). Need to commit that JSON-canonicalisation rules are identical to `ComposedAction` (`2026-04-24-gaia-composition-primitive-design.md` §1.2). Likely a shared utility.

### 9.5 Naming bikeshed

- `evidence()` vs `support_statistical()` vs `likelihood()` — we pick `evidence()` to match the verb-as-noun convention of `observe`/`derive`/`compute`/`infer`/`associate` and the `helper_kind = "evidence"` tag.
- `LikelihoodModel` vs `StatisticalModel` vs `EvidenceModel` — `LikelihoodModel` emphasises the mathematical role (it returns `log P(data | H)`), while `EvidenceModel` would emphasise the DSL role. Mild preference for `LikelihoodModel`; flag for reviewer feedback.

---

## 10. Acceptance criteria

Phase A is complete when:

- [ ] `evidence()` verb exists in `gaia.lang` and is exported from `gaia.lang.__init__`.
- [ ] `EvidenceFactor` Action subclass exists in `gaia.lang.runtime.action`.
- [ ] Six starter `LikelihoodModel` classes exist with unit tests verifying their `log_likelihood` math matches hand-computed references to 1e-9 relative.
- [ ] `test_evidence_verb.py` covers: binary BF, gate scaling, deprecated `infer`/`associate` paths, PRIORS non-conflict.
- [ ] Mendel example compiles without `probabilities.py`, without `f2_dominant_count_specific`, and produces `P(Mendel | data) > 0.9` and `P(blending | data) < 0.1` (the current directional assertions in `test_mendel_v05_example.py` continue to pass unchanged).
- [ ] `docs/foundations/language/gaia-language-spec.md` documents `evidence()` at spec level.
- [ ] Issue #485 can be closed with a reference to the merged PR.

---

## 11. Relation to issue #448

Issue #448 proposes a broader v6 rework that would also remove `Associate` / `Infer` entirely and reshape the `Strategy` IR. This spec:

- **Lands on v0.5** without a v6 rework, by keeping `Associate` / `Infer` as thin shorthands (§6).
- **Implements #448's core statistical move**: "statistical uncertainty is represented by explicit evidence / likelihood factors" — `EvidenceFactor` + `LikelihoodModel` is exactly that.
- **Defers #448's other moves**: removing probabilistic warrant entirely, reshaping `Strategy.type` to only `{support, deduction, definition, source_support, computation_support}`, moving Claim roles to metadata. These can follow in a later PR that takes `evidence()` as its starting point.

In other words, this spec is the **minimum viable subset of #448 that resolves the immediate Mendel failure and opens up model-swap / sensitivity / multi-observation capabilities**, without requiring v6's full re-authoring of the language surface.
