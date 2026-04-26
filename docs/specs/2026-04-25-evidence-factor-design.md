# Correlate Family — Design Spec

> **Status:** Target design (rev2 of 2026-04-25)
> **Date:** 2026-04-26 (revised)
> **Scope:** A v0.5-compatible refactor of the three Correlate-family verbs:
>   1. **Add** a new `evidence()` verb for structured statistical models (consumes `gaia.stats.DistributionSpec` from PR #487).
>   2. **Add** a `given` kwarg to `infer()` and `associate()` for methodological-assumption gates (parallel to the `given` kwarg on Support-family verbs).
>   3. **Rename** `prior_*` kwargs to `marginal_*` to reflect their true Bayesian role — they are the joint-distribution marginals of the local factor, not observation priors.
>   4. **Remove** `infer.prior_evidence` entirely — it was mathematically redundant: `P(E)` is fully determined by `marginal_h`, `p_e_given_h`, and `p_e_given_not_h` via the law of total probability.
>
> **Relationship to other docs:**
>   - Resolves the narrow `associate.prior_* ↔ PRIORS` field collision tracked in **issue #485** by routing `marginal_*` to a separate Claim metadata slot and eliminating the naming overload.
>   - Builds directly on the `DistributionSpec` / `gaia.stats` foundation landed in **PR #487**. The `evidence()` verb's `model=` kwarg is exactly a `DistributionSpec`.
>   - Implements a v0.5-compatible slice of the statistical-evidence direction proposed in **issue #448**; defers #448's broader "remove probabilistic warrant" rework.
>
> **Revision note:** Rev1 (dated 2026-04-25) proposed a single-verb `evidence()` that would replace `infer` and `associate` via a unified `LikelihoodModel` protocol. Review feedback surfaced that (a) `infer` and `associate` exist for genuine LLM-authoring reasons — they capture two distinct cognitive postures on specifying Bayes factors; (b) a single-verb design with mutex kwargs is not Pythonic and is error-prone for both humans and LLMs. Rev2 preserves the three-verb structure, makes the naming semantically correct, and narrows new surface to what #485 and #487 together demand.

---

## 0. Motivation

### 0.1 The concrete failures

Two separate issues motivate this spec; both surface on the same PR:

**(a) Field collision between `PRIORS` and `associate.prior_*`.**

PR #482 (the Mendel example) reaches a hard collision at `gaia infer` time:

```
ValueError: associate strategy lcs_...: conflicting marginal providers for
'...:f2_count_observation': metadata.prior=0.95, associate prior=0.024
```

These two values are not inconsistent estimates of the same quantity — they are *different Bayesian quantities*:

| 0.95 | 0.024 |
|---|---|
| `P(R = 1)` — the **reliability** marginal (the observer / record is reliable), supplied via `PRIORS[observation_claim] = 0.95`. Independent of the observation's numerical content. | `P(O | R = 1) = Σ_M P(O | M) P(M)` — the **Bayesian marginal** of the specific numerical event under the hypothesis mixture, conditional on an accurate record. Supplied via `associate(..., prior_b=0.024)`. |

Both are legitimate marginals of the same underlying joint `P(M, R, O)`, but along **different axes**. v0.5 stores both in `claim.metadata["prior"]`, so a package that supplies both (via `PRIORS` and `associate` in the same file) gets a compile-time rejection.

**(b) The user-facing kwarg name `prior_*` is the language-level root of the collision.**

Even if the field routing were fixed, a `prior_a` / `prior_b` / `prior_hypothesis` / `prior_evidence` kwarg on a Correlate-family verb is **genuinely misleading**: authors read "prior" and understand it as "the claim's subjective prior belief" (matching `PRIORS`), while the kwarg's actual mathematical role is the **joint-distribution marginal** of the local 2×2 factor. Fixing the field collision without fixing the name leaves users confused about why their `PRIORS[claim] = 0.95` is ignored when `associate(claim, ..., prior_a=0.3)` is in scope.

### 0.2 Why `infer` / `associate` can't express methodological gates

Neither `infer` nor `associate` has a way to express "this evidence is only valid under methodological assumption A" — e.g., "independent Bernoulli trials," "randomization valid," "instrument calibrated." In v0.5 these typically land in `background=[Note(...)]`, which does not affect BP. A reviewer who doubts the methodology has no structural way to discount the evidence.

The Support family (`derive` / `observe` / `compute`) already has a `given=` kwarg that carries premises; they participate in BP. We can extend the same convention to the Correlate family.

### 0.3 What `evidence()` adds that `infer` / `associate` genuinely cannot

When a user has a **generative model** (Binomial, Gaussian, Poisson, …) with *structured data parameters*, `infer` and `associate` both require the user to pre-compute `P(E|H)` and `P(E|¬H)` as scalars outside the framework. This is the `examples/mendel-v0-5-gaia/src/mendel_v0_5/probabilities.py` pattern — 80+ lines of user-maintained numerical code for every statistical example.

With PR #487 having landed `gaia.stats.DistributionSpec`, the framework can consume the generative model directly. A new verb `evidence()` makes this the canonical path.

---

## 1. Design principles

From the conversation that produced rev2:

1. **Each verb corresponds to one LLM cognitive posture.** Three verbs, three Pythonic signatures, no mutex kwargs. Authors (human or LLM) choose the verb that matches how they are thinking about the problem:
   - `evidence` — "I have a generative model; framework compute the likelihood."
   - `infer` — "Given H vs ¬H, here are the two likelihoods I can estimate."
   - `associate` — "These two generic propositions have mutual conditionals I can estimate."

2. **Minimum parameter sets.** Each verb requires exactly the numbers mathematically needed to determine the factor potential. Over-specified kwargs (like `infer.prior_evidence`) are removed, not kept for compatibility.

3. **Reuse PR #487 infrastructure.** `evidence.model` is a `DistributionSpec`; no new `LikelihoodModel` protocol is introduced. `gaia.stats.Normal / Binomial / ...` constructors are the model authoring surface.

4. **Backward compatibility for `infer` / `associate`.** Existing packages continue to compile. Renamed kwargs are accepted via deprecated aliases for one release with `DeprecationWarning`. No hard break in v0.5.

5. **The PRIORS collision fix is a framework change, not a signature change.** `marginal_*` values write to `claim.metadata["bayes_marginal"]`, not `claim.metadata["prior"]`, so the collision disappears by construction regardless of which verb wrote them.

---

## 2. The three Correlate verbs

### 2.1 `evidence()` — NEW

**When to use:** the author has an identifiable structured generative model (binomial, Gaussian, Poisson, custom) and the data Claim carries enough structured metadata for the model to evaluate its likelihood.

**Signature:**

```python
def evidence(
    conclusion: Claim,                            # positional
    *,
    data: Claim,
    model: DistributionSpec,                      # from gaia.stats (PR #487)
    given: list[Claim] | None = None,             # methodological gates
    background: list[Knowledge] | None = None,
    rationale: str = "",
    label: str | None = None,
) -> Claim:                                       # returns helper Claim
    """Bayesian evidence update via a structured statistical model.

    The framework computes ``P(data | conclusion)`` and
    ``P(data | ¬conclusion)`` internally from ``model`` and
    ``data.metadata``. See §3.2 for gate semantics.

    Returns a generated helper Claim with ``helper_kind="evidence"``.
    ``conclusion.belief`` is updated via BP, not returned directly.
    """
```

**Example:**

```python
from gaia.stats import Binomial

evidence(
    mendelian_segregation_model,
    data=f2_count_observation,                    # metadata = {"dominant": 295, "total": 395}
    model=Binomial(n=395, p=3/4),
    given=[independent_bernoulli_valid],
)
```

**Mathematical specification:** `model` determines the likelihood `P(data | conclusion)` under the point hypothesis (conclusion is true). The framework derives the likelihood under `¬conclusion` from the `DistributionSpec` `kind` field (see §4.3 for the dispatch rules). `conclusion`'s belief is updated via the resulting Bayes factor, scaled by the gate function from §3.2.

### 2.2 `infer()` — modified

**When to use:** the author (typically an LLM or human expert) has counterfactual intuition about how likely the evidence would be under the hypothesis versus under its negation. No structured model is available.

**Signature (changes from v0.5 highlighted):**

```python
def infer(
    evidence: Claim,                              # positional (unchanged)
    *,
    hypothesis: Claim,                            # (unchanged)
    p_e_given_h: float | Claim,                   # (unchanged)
    p_e_given_not_h: float | Claim,               # (unchanged)
    marginal_h: float | None = None,              # RENAMED from prior_hypothesis
    given: list[Claim] | None = None,             # NEW
    background: list[Knowledge] | None = None,    # (unchanged)
    rationale: str = "",
    label: str | None = None,
    # prior_hypothesis kwarg accepted as deprecated alias for marginal_h
    # prior_evidence kwarg accepted but raises DeprecationWarning; its value is ignored
    #   (see §3.3 for migration guidance)
) -> Claim:
    """Bayesian evidence update via counterfactual scalar likelihoods.

    The caller supplies ``p_e_given_h`` = P(E | H) and
    ``p_e_given_not_h`` = P(E | ¬H), and optionally ``marginal_h`` = P(H).
    If ``marginal_h`` is None, the framework uses H's prior from ``PRIORS``
    or the framework default. ``P(E)`` is computed internally via the law of
    total probability; it is not a user-provided quantity.
    """
```

**Example (unchanged from v0.5 except for the new kwargs):**

```python
infer(
    observation_high_freq_spectrum_finite,
    hypothesis=hypothesis_planck_radiation_quantized,
    p_e_given_h=0.95,
    p_e_given_not_h=0.1,
    marginal_h=0.3,
    given=[experimental_setup_valid],
)
```

**Why `prior_evidence` is removed:** for a 2-way factor over H and E, the 2×2 joint distribution has 3 degrees of freedom. Specifying `p_e_given_h`, `p_e_given_not_h`, and `marginal_h` already determines all three. `P(E)` is then:

\[
P(E) = p_{e|h} \cdot P(H) + p_{e|\neg h} \cdot (1 - P(H))
\]

A user-supplied `prior_evidence` is either redundant (if Bayes-consistent with the other three) or dangerous (if inconsistent). Either way, the framework should compute it, not accept it. Migration of existing `prior_evidence` call sites is covered in §3.3.

### 2.3 `associate()` — modified

**When to use:** two propositions have mutual conditional dependencies with no natural "data / hypothesis" directional split — for example, two theoretical claims that imply each other, or two observational summaries.

**Signature (changes highlighted):**

```python
def associate(
    a: Claim,                                     # positional (unchanged)
    b: Claim,                                     # positional (unchanged)
    *,
    p_a_given_b: float | Claim,                   # (unchanged)
    p_b_given_a: float | Claim,                   # (unchanged)
    marginal_a: float | None = None,              # RENAMED from prior_a
    marginal_b: float | None = None,              # RENAMED from prior_b
    given: list[Claim] | None = None,             # NEW
    background: list[Knowledge] | None = None,    # (unchanged)
    rationale: str = "",
    label: str | None = None,
    # prior_a / prior_b accepted as deprecated aliases for marginal_a / marginal_b
) -> Claim:
    """Symmetric Bayesian factor between two Claims.

    The caller supplies ``p_a_given_b`` and ``p_b_given_a`` (required) and
    optionally either or both of ``marginal_a``, ``marginal_b``. The 2×2
    joint has 3 degrees of freedom; given both conditionals, exactly one
    marginal closes the system. When both marginals are provided they must
    satisfy ``p_a_given_b · marginal_b = p_b_given_a · marginal_a`` (Bayes
    coherence); the framework warns on inconsistency.
    """
```

**Why keep both marginal kwargs when only one is strictly needed:** `associate` is semantically symmetric — neither operand is privileged as "data" or "hypothesis." Forcing the author to choose which marginal to supply breaks that symmetry. Keeping both as `Optional` preserves the symmetric authoring experience while allowing minimal specification (one) or explicit closure (two, with coherence check).

---

## 3. Framework-level changes (shared by all three verbs)

### 3.1 `marginal_*` routes to `metadata["bayes_marginal"]`, not `metadata["prior"]`

Today, compile-time writes `associate.prior_a` → `claim.metadata["prior"]`, where it collides with PRIORS. Under this spec:

```python
# gaia/lang/compiler/compile.py, in _compile_associate_action (paraphrased):
if action.marginal_a is not None:
    claim_a.metadata.setdefault("bayes_marginal", {})[action_label] = action.marginal_a
# metadata["prior"] is never written by Correlate actions.
```

The per-label `bayes_marginal` dict allows multiple Correlate actions to coexist on the same Claim without collision. Inference reads whichever entry matches the currently-evaluated factor.

`metadata["prior"]` continues to be the single-valued **reliability** field set by `PRIORS`. Its meaning is unambiguous: pre-inference initial belief in the Claim, independent of any Bayes factor.

### 3.2 `given` gate semantics in BP lowering

Each Correlate factor's potential is multiplicatively scaled by the product of its gate Claims' current beliefs:

\[
\log \phi_{\text{factor}} \;=\; \log \phi_{\text{raw}} \;\cdot\; \prod_{g \in \text{given}} \text{belief}(g)
\]

Behaviour:

- All gates at belief 1 → factor at full strength (`∏ = 1`).
- Any gate at belief 0 → factor contributes 0 log-likelihood (effectively deleted).
- Gates in between → smooth multiplicative scaling.
- `given` Claims must themselves have `PRIORS` entries (they are belief variables), enforced at compile time.

This is the same gate semantics Support-family verbs already implicitly use for their `given` field.

### 3.3 Deprecation and migration

**Automatic alias (accepted for one release):**

| Old kwarg | New kwarg | Behaviour |
|---|---|---|
| `associate(prior_a=x)` | `associate(marginal_a=x)` | `DeprecationWarning`, forward value to new name |
| `associate(prior_b=x)` | `associate(marginal_b=x)` | same |
| `infer(prior_hypothesis=x)` | `infer(marginal_h=x)` | same |

**Removed without alias:**

- `infer(prior_evidence=x)` — emits `DeprecationWarning` explaining that `P(E)` is now computed internally. The passed value is ignored. Two migration targets:
  1. If the caller was expressing observation reliability (`"P(the observation record is correct)"`), lift it to an explicit `Claim` and pass it via `given=[reliability_claim]`.
  2. If the caller was pre-computing `P(E)` from `marginal_h` and the two likelihoods for Bayes closure, simply delete the argument; the framework now does this internally.

**One full release cycle:** deprecated aliases live for v0.5.x; removed in v0.6. Removal happens by a separate PR; this spec only lands the renames + warnings.

---

## 4. IR layer

### 4.1 Action field renames

```python
# gaia/lang/runtime/action.py

@dataclass
class Infer(Correlate):
    hypothesis: Claim | None = None
    evidence: Claim | None = None
    p_e_given_h: float | Claim = 0.5
    p_e_given_not_h: float | Claim = 0.5
    marginal_h: float | None = None                   # was prior_hypothesis
    given: tuple[Claim, ...] = ()                     # NEW
    # prior_evidence: REMOVED

@dataclass
class Associate(Correlate):
    a: Claim | None = None
    b: Claim | None = None
    p_a_given_b: float | Claim = 0.5
    p_b_given_a: float | Claim = 0.5
    marginal_a: float | None = None                   # was prior_a
    marginal_b: float | None = None                   # was prior_b
    given: tuple[Claim, ...] = ()                     # NEW
```

### 4.2 `EvidenceFactor` Action — new

```python
@dataclass
class EvidenceFactor(Correlate):
    conclusion: Claim | None = None
    data: Claim | None = None
    model: DistributionSpec | None = None             # from gaia.ir.schemas
    given: tuple[Claim, ...] = ()
```

### 4.3 Compile-time potential dispatch for `evidence()`

The compile phase resolves `model.kind` to a potential-construction function that reads `data.metadata` and produces `(log_lik_h, log_lik_not_h)`:

```
"binomial"      → binomial_pmf(data.metadata[count_field], data.metadata[total_field], p) / (1/(N+1))
"normal"        → gaussian_pdf(data.metadata[value_field], μ, σ) / reference_Gaussian(broad_μ_prior)
"poisson"       → poisson_pmf(data.metadata[count_field], rate) / exponential_reference
...
"custom"        → invoke model.callable_ref (requires scipy adapter, PR #487 later slice 2)
```

The reference measure (the "¬H" likelihood) for each built-in kind is documented in a table alongside the dispatcher. For `binomial`, the built-in reference is the uniform-over-p diffuse prior (closed form `1/(N+1)`), which is what the current Mendel example uses by hand.

Users who want a non-default reference construct the factor via `infer()` with explicit scalars, not `evidence()`.

### 4.4 IR strategy type

`EvidenceFactor` compiles to a new IR strategy type:

```python
IrStrategy(
    type="evidence",
    premises=[conclusion_id, data_id],
    conclusion=helper_id,
    metadata={
        "model": action.model.model_dump(mode="json"),   # JSON-native, from PR #487 schema
        "gates": [g_id for g in action.given],
        "log_lik_h": ...,                                # numeric, from dispatcher
        "log_lik_not_h": ...,
    },
)
```

### 4.5 Helper Claim (returned by all three verbs)

Consistent with the existing Correlate convention:

```python
helper.metadata = {
    "generated": True,
    "helper_kind": "evidence" | "likelihood" | "association",
    "review": True,
    "relation": {"type": <kind>, ...},
}
```

`infer()` keeps `helper_kind = "likelihood"`; `associate()` keeps `helper_kind = "association"`; `evidence()` uses `helper_kind = "evidence"`.

---

## 5. Relation to PR #487

PR #487 is the enabling foundation for this spec. Specifically:

- `gaia.ir.schemas.DistributionSpec` is the exact type of `evidence.model`. No wrapping, no adapter.
- `gaia.stats.{Normal, Binomial, LogNormal, StudentT, Cauchy, Poisson, Exponential, Beta, from_callable}` are the authoring constructors. No additional constructors need to be added by this spec.
- `gaia.ir.schemas.QuantityLiteral` handles unit-bearing `data.metadata` fields (e.g., `GaussianMeasurementModel` use cases). No compile-boundary work is duplicated.
- `gaia.unit.q()` lets authors write `data.metadata = {"value": q(80, "K")}` and have it normalised to `QuantityLiteral` at compile time.

#487's "Later Slices" list includes (slice 3) "A first evidence composition/template such as gaussian measurement." This spec is that slice, for all built-in `DistributionSpec.kind` values at once rather than one-model-at-a-time.

---

## 6. Relation to issue #448

#448's v6 direction proposes a more radical rework — removing probabilistic warrant from `Support`, reshaping `Strategy.type`, and moving Claim roles to metadata. This spec:

- **Implements the core statistical move** of #448: "statistical uncertainty is represented by explicit evidence factors." `EvidenceFactor` is exactly that, and it does not touch the Support family's `given` semantics (which v0.5 already gets right per #448's direction).
- **Preserves `Infer` and `Associate`** as first-class Correlate verbs. #448 proposed deprecating them, but in-conversation review with the user established that the two verbs serve genuinely distinct LLM-authoring cognitive postures (counterfactual-likelihood vs. mutual-conditional) that both deserve dedicated signatures. Rev2 keeps them.
- **Defers** the rest of #448 (warrant removal, strategy restructure, role metadata) to a later v6 rework. Nothing in this spec blocks or contradicts that direction.

---

## 7. Worked example: Mendel migration paths

After this spec lands (alongside #487), the Mendel example's current workaround node `f2_dominant_count_specific` can be eliminated. There are two equally-valid migration targets, depending on whether the author prefers `evidence()` with a structured model or keeps the existing `associate()` call.

### 7.1 Path A — migrate to `evidence()` (recommended for didactic clarity)

```python
from gaia.stats import Binomial

evidence(
    mendelian_segregation_model,
    data=f2_count_observation,
    model=Binomial(n=395, p=3/4),
    given=[independent_bernoulli_valid],
)
```

Changes relative to merged PR #482:

- `examples/mendel-v0-5-gaia/src/mendel_v0_5/probabilities.py` deleted entirely (all 98 lines).
- `f2_dominant_count_specific` derive node deleted.
- `mendel_data_association_parameters()` call deleted.
- `associate()` call replaced by the `evidence()` call above.

`independent_bernoulli_valid` becomes a first-class reviewable Claim (e.g., `Claim("F2 individuals are independent Bernoulli trials with shared p", prior=0.9)`). Reviewers who doubt the independence assumption can lower its prior and see the evidence factor's strength proportionally reduced, without touching any statistical code.

### 7.2 Path B — keep `associate()`, just rename kwargs and add `given`

```python
associate(
    mendelian_segregation_model,
    f2_dominant_count_specific,
    p_a_given_b=..., p_b_given_a=...,
    marginal_a=0.5, marginal_b=0.024,              # renamed from prior_a / prior_b
    given=[independent_bernoulli_valid],           # new
)
```

Changes relative to merged PR #482:

- `prior_a` / `prior_b` renamed to `marginal_a` / `marginal_b` (old names accepted as deprecated aliases).
- `given=[...]` added to express the Bernoulli independence gate.
- `probabilities.py` retained — user continues to hand-compute the four scalars.
- `f2_dominant_count_specific` retained.

This path is available to authors who specifically want LLM-direct-scalar authoring rather than framework-computed likelihood. It's not the *recommended* Mendel migration, but it's a valid pattern for other packages that lean on expert-estimated conditionals.

### 7.3 What happens to PR #482's workaround node

Path A deletes `f2_dominant_count_specific`. Path B retains it. Once this spec lands, the Mendel example's in-file docstring (currently pointing to #485) should be updated to either:

- Path A: remove the workaround explanation entirely.
- Path B: update the docstring to reflect the new kwarg names.

The docstring update is a separate follow-up PR to the Mendel example; it's not part of this spec's acceptance criteria.

---

## 8. Migration plan

### Phase A — land signatures + framework routing (~1 week scope)

1. Rename `prior_*` → `marginal_*` in `Infer` / `Associate` Action fields, DSL verbs, and IR strategy. Add deprecated alias accepting old names with `DeprecationWarning`.
2. Remove `infer.prior_evidence` kwarg. Add `DeprecationWarning` for old call sites explaining both migration targets (§3.3).
3. Add `given: tuple[Claim, ...]` field to `Infer` and `Associate` Actions; add `given` kwarg to both DSL verbs.
4. Add `EvidenceFactor` Action subclass and `evidence()` DSL verb. Compile rule reads `DistributionSpec.kind` and dispatches to a built-in potential-construction function for each built-in kind.
5. Framework routing: Correlate-family actions' `marginal_*` values write to `claim.metadata["bayes_marginal"]`, not `claim.metadata["prior"]`. Remove the "conflicting marginal providers" hard `ValueError`.
6. BP lowering: implement the gate semantics of §3.2 for all three Correlate verbs.
7. Tests:
   - `tests/gaia/lang/test_evidence_verb.py` — new.
   - `tests/gaia/lang/test_infer.py` — extend for `given`, `marginal_h` rename, removed `prior_evidence` warning.
   - `tests/gaia/lang/test_associate_verb.py` — extend for `given`, `marginal_a/b` rename.
   - `tests/cli/test_infer.py` — regression that Mendel-like configurations no longer raise the collision error.

### Phase B — example migrations (~1 week scope)

1. Migrate `examples/mendel-v0-5-gaia/` — Path A. Delete `probabilities.py` and `f2_dominant_count_specific`. Update `test_mendel_v05_example.py`.
2. Audit `examples/galileo-v0-5-gaia/` — Galileo is qualitative; confirm no change required.
3. Update `docs/foundations/gaia-lang/dsl.md` with the new verb and kwarg names.
4. Release note + skill file updates.

### Phase C — remove deprecated aliases (v0.6)

Separate PR, not part of this spec.

### Backward-compatibility guarantees

- All v0.5 packages that use `infer` / `associate` continue to compile. Only warnings are emitted.
- IR format continues to accept old field names for one version (reader-side back-compat).
- `claim.metadata["prior"]` field unchanged in shape and semantics.

---

## 9. Open questions

### 9.1 `given` gating function

§3.2 specifies `g = ∏ belief(g_i)` (multiplicative AND). Discussed alternatives:

- **Noisy-AND** via Gaia's existing `noisy_and` operator for explicitly-correlated gates.
- **Configurable** via a `gate_semantics=` kwarg.

Recommendation: AND default for v0.5; noisy-AND / configurability as a follow-up when a real package needs it. Correlated gates should be collapsed to a single explicit Claim rather than relying on the gating function to model their correlation.

### 9.2 Reference measure for non-binomial `evidence` kinds

`Binomial` has a canonical diffuse reference (`1 / (N+1)`). For `Normal`, `Poisson`, `Exponential`, etc., there is no single obvious diffuse reference measure. Three options:

- **Hard-code defaults per kind** (e.g., Gaussian → broad-Gaussian reference with `σ = 10 × σ_model`).
- **Require the author to supply an alternative** as a second `DistributionSpec`: `evidence(..., model=..., alternative=...)`.
- **Fall back to `infer()` for non-binomial cases in v0.5**; add `evidence(..., alternative=...)` in a later slice.

Leaning toward option 3 for the initial landing: ship `evidence()` with `Binomial` only (the PR #482 demand case), and expand built-in coverage incrementally.

### 9.3 `associate()` marginal-coherence check

When both `marginal_a` and `marginal_b` are provided and inconsistent (`p_a_given_b · marginal_b ≠ p_b_given_a · marginal_a` within float tolerance), should the framework:

- **Warn and pick one** (which?).
- **Hard error**.
- **Accept silently and use an implementation choice** (e.g., `marginal_a`, derive `marginal_b` from Bayes).

Recommendation: warn, use the geometric mean of the two implied `marginal_a` values as a tie-break. Revisit if it proves awkward in practice.

### 9.4 Validation: missing `data.metadata` fields for `evidence.model`

If `evidence(..., model=Binomial(n=395, p=3/4))` receives a `data` Claim whose `metadata` lacks `dominant` and `total`, compile should fail with a clear message naming both the expected and actually-present fields. Trivial to implement; flagged here as a UX acceptance bar.

---

## 10. Acceptance criteria

Phase A is complete when:

- [ ] `marginal_a` / `marginal_b` / `marginal_h` accepted by `associate()` / `associate()` / `infer()`. Old names accepted with `DeprecationWarning`.
- [ ] `infer(prior_evidence=...)` raises `DeprecationWarning` and ignores the value; docstring explains the two migration targets.
- [ ] `given: list[Claim]` accepted by all three Correlate DSL verbs.
- [ ] `evidence()` verb exported from `gaia.lang`.
- [ ] `EvidenceFactor` Action subclass compiles and lowers for `DistributionSpec.kind = "binomial"`.
- [ ] Correlate-family actions no longer write to `claim.metadata["prior"]`.
- [ ] "conflicting marginal providers" `ValueError` removed from `gaia.cli.main infer`.
- [ ] BP lowering applies `given` gate multiplier for all three Correlate verbs.
- [ ] `test_evidence_verb.py` covers: basic binary factor via Binomial, gate scaling, missing-metadata-field error, deprecated-kwargs warnings.
- [ ] Mendel example migrates to Path A, `test_mendel_v05_example.py` continues to assert `P(Mendel | data) > 0.8` and `P(blending | data) < 0.2`.
- [ ] Issue #485 can be closed; deprecated-alias removal (Phase C) tracked in a new follow-up issue.

---

## 11. What this spec does NOT propose

For clarity, items intentionally left out:

- **No removal of `infer` or `associate`** — they remain first-class with their distinct cognitive posture.
- **No unified-verb design** — rev1's single-verb `evidence()` with mutex kwargs is explicitly rejected as un-Pythonic and error-prone.
- **No `LikelihoodModel` protocol** — rev1's custom protocol is superseded by reusing PR #487's `DistributionSpec`.
- **No new model classes** — `gaia.stats.*` (from PR #487) is the complete authoring surface.
- **No continuous-parameter integration** — continuous latent-variable BP is out of scope; custom callable likelihoods go through `from_callable` + scipy adapter (PR #487's later slice 2).
- **No changes to Support family verbs** (`derive` / `observe` / `compute`) — they already have `given` and do not have the `prior_*` ↔ `PRIORS` collision.
- **No changes to relation helpers** (`equal` / `contradict` / `exclusive`) — they do not carry probabilities.
- **No v6-scale rework** — #448's broader direction is acknowledged in §6 but is not attempted here.
