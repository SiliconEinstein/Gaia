# Gaia Foundation Spec

> **Status:** Target design — consolidated foundation
> **Date:** 2026-04-23
> **Scope:** Gaia kernel identity — what Gaia is, what belongs in the kernel vs the ecosystem, semantic layering, and topic-by-topic foundation decisions that gate the post-v0.5 roadmap
> **Supersedes:** `docs/ideas/foundation-specs/scientific-formal-language-foundation-spec.md`, `docs/ideas/foundation-specs/jaynes-probability-logic-backend-foundation-spec.md` (both idea-stage drafts)
> **Companion:** `docs/specs/2026-04-21-gaia-lang-v6-design.md`, `docs/specs/2026-04-21-gaia-ir-v6-design.md`
> **Non-goal:** Release plan, implementation schedule, migration details. This document is about **what Gaia is**, not when pieces ship.

---

## 0. One-line invariant

> **Gaia is a Jaynesian propositional reasoning kernel with extension points: it owns Claim, Action, Review, Context, Evidence, and the minimal schema needed to reach out to scientific ecosystems. Everything beyond that — units, distributions, measurement physics, graph algorithms, data systems, symbolic math — is delegated to adapters below the semantic line.**

This document defines the semantic line.

---

## 1. Why this document exists

The `docs/ideas/foundation-specs/` bundle drafted two parallel north-stars — one painting Gaia as a full scientific formal language, the other as a Jaynesian probability backend. The scope gap between them is roughly an order of magnitude. Every post-v0.5 decision (what goes in v0.6, what the kernel looks like, which adapters are mandatory) depends on which north-star is canonical.

This spec resolves that ambiguity. It picks a concrete scope (§2), draws the kernel boundary (§3), defines the three-layer probability semantics that keeps the kernel honest (§4), enumerates the kernel object set (§5), and records per-topic decisions (§6–§12) that were previously floating across multiple drafts.

The spec does **not** define a release plan. It defines the target shape the releases walk toward.

---

## 2. North star — what Gaia is

Gaia is:

```text
A claim-centered, action-backed, review-gated, context-indexed,
Jaynesian propositional reasoning kernel, with explicit extension
points for the scientific ecosystem to plug in units, distributions,
measurements, graph algorithms, and specialised backends.
```

Gaia is **not**:

- A full scientific formal language à la Lean / Coq / SBML.
- A probabilistic programming language.
- A unit algebra system.
- A theorem prover.
- An experiment / dataset / analysis registry.
- A causal inference engine.

The kernel is deliberately narrow. Breadth comes from the ecosystem.

---

## 3. Kernel boundary

The kernel owns what is either (a) semantically constitutive of the reasoning act, or (b) necessary for auditability / reproducibility / cross-package coherence.

### 3.1 In the kernel

**Knowledge layer (the vocabulary)**

- `Claim` — the only belief-carrying variable. Parameterised via class-as-predicate (Gaia Lang v6 §2).
- `Note` — plain-text annotation, does not enter BP.
- `Question` — inquiry lens, does not enter BP.

**Action layer (the verbs)**

- `Derive` — directional deduction with warrant review.
- `Observe` — evidence-placement act.
- `Compute` — deterministic functional relationship.
- `Infer` — likelihood evidence act.

**Relate layer (the logical operators)**

- `Equal`, `Contradict`, `Exclusive` — relational operators with BP factor lowering.
- `not_`, `and_`, `or_` — propositional operators producing helper claims.

**Review layer (the qualitative gate)**

- `ReviewManifest` — collection of `ReviewTarget`s keyed by `action_label` **or** by relation identity (see §7).
- `ReviewStatus` — accepted / unreviewed / rejected. Never a probability.

**Context layer (the information state)**

- `BeliefContext` — information state `I` used by inference; carries `context_id` (canonical SHA-256 over inputs).
- `BeliefState` — posterior output `P(Claim | I)` plus provenance.
- `ContextLock` — reproducibility artefact.

**Evidence / measurement schema (the bridge to the world)**

- `InferStrategy` fields — `evidence_kind`, `likelihood_ratio` or `p_e_given_h`/`p_e_given_not_h`, `source_id`, `data_id`, `data_hash`. (See §11 for field inventory; no separate `EvidenceMetadata` class.)
- `MeasurementRecord` — schema for observed-value + noise specification.
- `ErrorModelSpec` — structured noise spec (`kind`, `params`, optional `CallableRef`).

**Callable abstraction (the embedded-function escape)**

- `CallableRef` — registered name + signature + source hash + purity declaration. Shared by `Compute`, `ErrorModelSpec`, and adapter hooks.

**Prior schema**

- `PriorSpec` — `value`, `source_id`, `policy`, `justification`. Wraps the scalar with audit-relevant provenance. (See §6.)

### 3.2 Below the semantic line (ecosystem / adapters)

Everything delegated:

| Capability | Ecosystem tool | Adapter protocol |
|---|---|---|
| Unit algebra | Pint | `UnitAdapter` |
| Distribution computation | scipy.stats | `noise registry` |
| Graph analysis | NetworkX | `GraphViewAdapter` (read-only views) |
| Backend alternatives | pgmpy / pyAgrum / PyMC / NumPyro | `BackendAdapter` |
| Symbolic math | SymPy | optional |
| Hard-logic SAT/SMT | Z3 | optional, future |
| Ontology | RDFLib / Owlready2 | optional, future |
| Tabular / multidim data | pandas / xarray | `DatasetRef` (no inline storage) |

**Hard rule:** external objects **must not** appear in Gaia-semantic interfaces (`BeliefState`, `InferStrategy`, `MeasurementRecord`, etc.). Adapters normalise results into Gaia-native types at their boundary.

### 3.3 Rationale — why this boundary

- **Parameterised Claim stays in the kernel.** Gaia Lang v6 already ships class-as-predicate with typed parameters; removing it would force a design reversal.
- **Quantity / Unit goes to Pint.** Pint is mature. Gaia reimplementing a unit algebra would be a maintainer-time sink, and "yet another unit system" hurts interoperability.
- **MeasurementRecord stays in the kernel as schema.** Audit requires it to be structured (§10); schema is small; kernel does not compute on it.
- **Distribution computation goes to scipy.** Gaia kernel does not call `logpdf` / `logpmf` directly. Adapters do.

---

## 4. The three-layer probability semantics

The single most important idea in this spec. Without it, `Claim.prior`, `MeasurementRecord.noise`, and `InferStrategy.likelihood_ratio` get conflated, and audit cannot tell them apart.

### 4.1 The three layers

| Layer | Object | Probability type | Dimension | Computed by |
|---|---|---|---|---|
| **Proposition** | `Claim.prior` | Jaynesian belief `P(Claim \| I)` over a binary proposition | dimensionless, `[0, 1]` | Gaia kernel (BP) |
| **Measurement** | `MeasurementRecord.noise` | continuous density `p(obs \| true, params)` | has units (observation space; density has inverse units) | Adapter (scipy) |
| **Bridge** | `InferStrategy.p_e_given_h / p_e_given_not_h / likelihood_ratio` | binary likelihood `P(E \| H)` / `P(E \| ¬H)` or ratio | dimensionless | Adapter (produces), kernel (stores) |

### 4.2 Why they cannot be mixed

- `Claim.prior` lives on binary propositions. It is never a density.
- `MeasurementRecord.noise` lives in observation space (kelvins, grams, counts). The kernel does not integrate, differentiate, or sample it.
- `InferStrategy` scalars are the **bridge**: the adapter has already marginalised / evaluated the noise model against two point hypotheses, producing dimensionless scalars that the kernel stores.

### 4.3 Naming discipline

In code, docs, error messages, and audit output:

- `belief` for layer 1 — `P(Claim | I)`.
- `noise` for layer 2 — measurement-layer error spec.
- `likelihood` for layer 3 — bridge-layer scalar.

Never say "probability" without qualifying which layer.

### 4.4 Concrete example

```python
# Measurement layer — noise spec, has units
reading = measurement_claim(
    "Spectrometer produced reading 5120 K",
    observed_value=q(5120, "K"),
    noise=ErrorModel(
        kind="normal",
        sigma=q(80, "K"),
        systematic_component=q(60, "K"),   # optional, for audit
        random_component=q(50, "K"),
    ),
)

# Proposition layer — belief on a binary claim
temp_high = Claim("TrueTemperature > 5000 K", prior=0.5)

# Bridge: adapter evaluates layer-2 noise against two point hypotheses,
# produces layer-3 scalars. Kernel stores LR only.
gaussian_measurement_evidence(
    reading, hypothesis=temp_high,
    mean_under_h=q(5200, "K"),
    mean_under_not_h=q(4800, "K"),
    observed=True,
)
# adapter internally:
#   p(5120 | mu=5200, σ=80) / p(5120 | mu=4800, σ=80) → LR ≈ 7500
# kernel stores:
#   InferStrategy.evidence_kind = "likelihood_ratio"
#   InferStrategy.likelihood_ratio = 7500
# Layer-1 output:
#   belief(temp_high) goes from 0.5 to ≈ 0.9999
```

`q(80, "K")` is layer 2. `0.5` and `0.9999` are layer 1. `7500` is layer 3. Three layers, three units, three semantics.

---

## 5. Kernel object inventory

Canonical set (pydantic schemas). Versioned via `schema_version: Literal["gaia.<name>.v1"]`.

```text
Knowledge
  ├── Claim          (bearer of prior; parameterisable)
  ├── Note           (free text; no BP)
  └── Question       (inquiry; no BP)

Action (IrStrategy base)
  ├── DeriveStrategy      (type="deduction")
  ├── ObserveStrategy     (type="deduction", pattern="observation")
  ├── ComputeStrategy     (type="deduction", compute={...})
  └── InferStrategy       (type="infer")                  — §11 for full field set

Operator
  ├── Equal
  ├── Contradict
  ├── Exclusive
  ├── Negation        (not_)
  ├── Conjunction     (and_)
  └── Disjunction     (or_)

Review
  ├── ReviewManifest
  ├── ReviewTarget            (action-level, keyed by action_label)
  └── IndependenceDeclaration (relation-level, keyed by relation_label) — §7

Context
  ├── BeliefContext     (carries context_id)
  ├── BeliefState       (carries belief_state_hash)
  └── ContextLock       (reproducibility artefact)

Measurement
  ├── MeasurementRecord
  └── ErrorModelSpec

Callable
  └── CallableRef       (compute / noise / adapter hook)

Prior
  └── PriorSpec         (value + source + policy + justification) — §6
```

`EvidenceMetadata` is **not** in this list. Its fields are inlined into `InferStrategy` via pydantic discriminated union (§11).

---

## 6. Prior semantics

**Decision: `PriorSpec` with `policy` enum reserved for future MaxEnt integration.**

### 6.1 Schema

```python
class PriorSpec(BaseModel):
    schema_version: Literal["gaia.prior.v1"] = "gaia.prior.v1"

    value: float                    # Bernoulli(p) for binary Claim

    source_id: str | None = None    # "elicited:expert_A", "maxent:ctx_X",
                                    # "external_predictive:pymc_run_123", etc.
    policy: Literal[
        "elicited",                 # hand-assigned by author / expert
        "conjugate",                # derived from a conjugate update
        "maxent",                   # computed by MaxEnt (external for now)
        "external_predictive",      # posterior predictive from external PPL
        "default",                  # package default
        "unknown",                  # not declared
    ] = "unknown"

    justification: str | None = None
```

`Claim.prior: PriorSpec | float | None`. A bare `float` is auto-wrapped with `policy="default"`.

### 6.2 What the kernel does with it

- `prior_hash` (in `BeliefContext.prior_resolution`) hashes the full `PriorSpec`, so changing `source_id` or `policy` invalidates context reproducibility even when `value` is unchanged.
- Audit rules (§10) fire on:
  - `policy="unknown"` on non-default Claims.
  - `value ∈ {0, 1}` without logical necessity.
  - `value` near 0 or 1 without justification.
  - Inconsistent `source_id` across packages claiming the same prior.

### 6.3 What the kernel does not do

- No MaxEnt solver in kernel. `policy="maxent"` is a label — the author records that a MaxEnt procedure (external) produced the value.
- No distribution family beyond Bernoulli. Continuous / categorical priors are out of scope for the v0.x kernel; foundation acknowledges them as v1.x+ extension via an expanded `PriorSpec` (optional `distribution`, `support`, `base_measure`, `constraints` fields).
- No automatic prior elicitation.

---

## 7. Independence as a review concern

**Decision: Independence is a review-layer judgement, not an EvidenceMetadata fact.**

### 7.1 Why

Whether two pieces of evidence are independent is a **scientific integrity judgement**. Two authors can disagree. The system cannot verify it from metadata alone. The honest architectural placement is in the review layer (qualitative gate), alongside per-action review targets.

### 7.2 Schema

Extend `ReviewManifest` to carry both action-level and relation-level targets:

```python
class IndependenceDeclaration(ReviewTarget):
    schema_version: Literal["gaia.independence.v1"] = "gaia.independence.v1"
    relation_label: str
    factors: list[str]                   # action_labels of the N evidence factors
    kind: Literal["identical", "independent", "correlated", "partial"]
    rationale: str
    # inherits: status (accepted | unreviewed | rejected)
```

Semantics at BP lowering time:

- `kind="identical" + accepted` → only one of the N factors remains active (hard dedup).
- `kind="independent" + accepted` → all N active, audit warnings about suspicious shared metadata are suppressed.
- `kind="correlated"` / `kind="partial"` — **reserved for v1.x+**. For now: warn but no BP change; BP treats the factors as independent (current behaviour).

### 7.3 Auto-suggestion scope

Compile-time auto-suggestion is bounded to what is actually verifiable:

- Shared `data_id` + matching `data_hash` → auto-suggest `IndependenceDeclaration(kind="identical")` as `unreviewed`.
- Anything else (same author-assertion tags like instrument / cohort) → **no** auto-suggestion. Authors must write the declaration explicitly with rationale.

This keeps the kernel from fabricating independence structure from unreliable signals.

### 7.4 Consequence — removal of `independence_group`

The free-string `EvidenceMetadata.independence_group` field (v0.6 draft) is **removed**. Its responsibilities move entirely to `IndependenceDeclaration`.

---

## 8. Model comparison

**Decision: Binary-claim wrapping. No first-class `Model` object in the v0.x kernel.**

### 8.1 How it works

Model comparison is expressed at the proposition layer:

- "M1 is adequate for dataset D" → a `Claim`.
- "M1 explains D better than M2" → a `Claim`.
- Three candidates → `exclusive(M1_best, M2_best, M3_best)` plus pairwise `bayes_factor()` evidence.

Bayes factors compile through the **E variant**: `InferStrategy.evidence_kind = "likelihood_ratio"`, `InferStrategy.likelihood_ratio = <BF>`. The CPT is **not persisted** — it is computed at lowering time using any canonical normalisation (e.g. `p_h = lr / (1 + lr)`, `p_not_h = 1 / (1 + lr)`). The IR carries only the ratio, which is the semantically meaningful quantity.

### 8.2 What the foundation does not commit to

- First-class `ModelRecord` schema (parameters / equations / validity / residual) — v1.x extension at the earliest.
- Categorical variables / categorical BP — not in v0.x.
- Marginal-likelihood computation / Occam factor — ecosystem (PyMC / NumPyro) via `BackendAdapter`.

---

## 9. Predictive distributions

**Decision: Predictive results enter Gaia as externally-computed values on Claims.**

Gaia kernel does not evaluate `∫ P(new | θ, I) P(θ | old, I) dθ`. When authors have a posterior predictive from an external tool:

- Create a `Claim` representing the predicted proposition.
- Attach `PriorSpec(policy="external_predictive", source_id="pymc:model_X:run_123", justification=...)`.
- Optionally attach an `EvidenceComputationRecord` in metadata to preserve the computation trace.

No `PredictiveQuery` kernel object. No DSL verb. Future v1.x with PPL adapter may promote the above to a first-class construct; for now the `policy` tag is the entire contract.

---

## 10. Hard logic

**Decision: No Z3 or other theorem-prover interface in the kernel.**

Gaia's existing mechanisms cover the common hard-logic needs of scientific reasoning:

- `Equal` / `Contradict` / `Exclusive` — hard relational constraints, Cromwell-clamped in BP lowering.
- `Compute` — deterministic functional relationships (BMI = m / h², etc.).
- `Derive` — author-declared deductions with warrant review.
- `not_` / `and_` / `or_` — propositional operators with factor lowering.

What Gaia does not attempt:

- Automatic entailment proving (`I ⊢ A`).
- Consistency checking (`I ⊢ ⊥`).
- First-order / SMT solving.

These are legitimately the province of external solvers (Z3, Lean, Coq). Foundation spec declares this boundary explicitly. Future integration is an ecosystem concern and is only meaningful once Claim propositions become structured enough for external consumption (v1.x+).

---

## 11. Evidence inlined into InferStrategy

**Decision: `EvidenceMetadata` is dissolved into `InferStrategy` fields via pydantic discriminated union.**

### 11.1 Schema

```python
class IrStrategy(BaseModel):
    type: Literal["infer", "deduction", ...]
    premises: list[str]
    conclusion: str
    background: list[str] = []          # §12
    metadata: dict[str, Any] = {}

class InferStrategy(IrStrategy):
    type: Literal["infer"] = "infer"

    # evidence kind discriminator
    evidence_kind: Literal["raw_likelihood", "likelihood_ratio"]

    # raw_likelihood fields
    p_e_given_h: float | None = None
    p_e_given_not_h: float | None = None

    # likelihood_ratio fields (also used for Bayes-factor helper)
    likelihood_ratio: float | None = None

    # provenance (kernel-consumed)
    source_id: str | None = None
    data_id: str | None = None
    data_hash: str | None = None

    @model_validator(mode="after")
    def check_kind_fields(self):
        if self.evidence_kind == "raw_likelihood":
            assert self.p_e_given_h is not None and self.p_e_given_not_h is not None
        elif self.evidence_kind == "likelihood_ratio":
            assert self.likelihood_ratio is not None
        return self
```

### 11.2 Why no separate class

`EvidenceMetadata` as a sidecar pydantic object (v0.6 draft) is a fragment of `InferStrategy`, not a separable concept. An `Infer` action without evidence fields is incoherent; evidence fields without an `Infer` action have nowhere to live. Inlining preserves the "evidence contract" foundation talks about — the contract is now stated as field-set-and-invariants on `InferStrategy`.

### 11.3 `EvidenceComputationRecord`

Distinct from `InferStrategy` and kept alive. It records what adapter produced the scalars (e.g. "scipy-gaussian-adapter-v1 with inputs …"). It is attached to `InferStrategy.metadata["evidence_computation"]`. This is reproducibility provenance, not evidence semantics.

### 11.4 Provenance field set (final)

Kernel-consumed:

- `source_id` — citation-level (paper, database, author).
- `data_id` — specific data instance.
- `data_hash` — bytes-level hash. Participates in `context_id` hashing.

**Not** kernel-consumed (per §10 / §6 rationale — unverifiable assertions go to `metadata` dict or to `IndependenceDeclaration.rationale`):

- `instrument_id` / `cohort_id` / `model_id` / `experiment_id` / `analysis_id` — removed from one-class fields; authors may place them in `metadata` if desired.
- `assumptions: list[str]` — removed entirely. Assumptions become first-class Claims referenced via `background` (§12).

---

## 12. Background premises on strategies

**Decision: `Derive`, `Compute`, and `Infer` all carry `background: list[str]`.**

### 12.1 What `background` is

`background` references Claims whose truth conditions the strategy depends on without their being the primary reasoning subject. For Infer: the `background` Claims are conditions under which the declared likelihood is valid.

BP lowering treats `background` Claims as conjoined conditions on the strategy's factor, i.e. the factor is active only when all `background` Claims are in their "true" state (Cromwell-clamped). In likelihood terms:

```text
P(E | H, B1, B2, …, I)  instead of  P(E | H, I)
```

### 12.2 Why this matters

Previously drafts proposed an `assumptions: list[str]` free-text field on `InferStrategy`. That field has four deficiencies:

- **Not reviewable** — free text has no ReviewTarget identity.
- **Not supportable by evidence** — no Claim-level ID to attach evidence to.
- **Not shareable** — 20 Infer actions repeating "Gaussian noise" each have 20 private strings.
- **Not traceable** — belief attribution cannot decompose by assumption.

Representing assumptions as Claims + `background` reference fixes all four. "Noise is Gaussian for run 042" becomes a Claim with its own `PriorSpec`, its own review target, and its own evidence chain. A package's shared assumptions (SI units, i.i.d. samples in trial 001, SIR model adequacy) live as package-level Claims that many strategies reference.

### 12.3 Relation to `Claim.background`

`Claim.background` (already in v6) and `Strategy.background` are distinct:

- `Claim.background` — context Claims that scope how the Claim's proposition is constructed.
- `Strategy.background` — context Claims that the specific reasoning act requires.

They do not merge. Both can be present on the same package.

---

## 13. Deprecations

### 13.1 `Setting`

`Setting` (v5 Knowledge type) is **deprecated from v0.5**. Its "formalised background, no probability" semantics is indistinguishable from a Claim with high prior and accepted `Observe`. Existing uses of `setting()` migrate to Claims or to Notes depending on whether they carry epistemic weight. Kernel type system drops the `"setting"` value from `Knowledge.type` enum in a migration step.

### 13.2 v5 reasoning strategies

The v5 strategy verbs (`deduction`, `abduction`, `elimination`, `case_analysis`, `induction`, `noisy_and`, `analogy`, `extrapolation`, `mathematical_induction`, `composite`) are **deprecated from v0.5**. The v6 verb set (`Derive`, `Observe`, `Compute`, `Infer`, `Equal`, `Contradict`, `Exclusive`, `not_`, `and_`, `or_`) is the stable surface. Deprecation follows the standard schedule: warnings now, removal after one full minor release with the migrator shipped.

### 13.3 `EvidenceMetadata.independence_group`

Removed. Use `IndependenceDeclaration` (§7).

### 13.4 `EvidenceMetadata` class

Dissolved into `InferStrategy` (§11). The *name* "EvidenceMetadata" is no longer a kernel type; the evidence contract is now a field set on `InferStrategy`.

---

## 14. Ecosystem integration rule

Restated from §3.2 as a named invariant:

> **Gaia owns scientific semantics; external Python packages provide computation below the semantic line through explicit adapters.**

```text
Libraries compute.
Gaia defines what the computation means.
```

Concrete rules:

- Heavy ecosystem dependencies (PyMC, NumPyro, pyAgrum, Owlready2, Z3) are **never** imported at Gaia core load time. They are lazy-imported inside adapter functions.
- Adapter results are normalised into Gaia-native objects (`BeliefState`, `InferStrategy`, `MeasurementRecord`, `Quantity`) before crossing the boundary.
- Adapter callables register as `CallableRef` so context reproducibility is maintained.
- `BeliefContext` records adapter identity (name, version) when an adapter produces results that end up in a `BeliefState`.

---

## 15. Relationship to existing documents

### 15.1 Supersedes

- `docs/ideas/foundation-specs/scientific-formal-language-foundation-spec.md` — scope too broad; Gaia does not aim to be a full scientific formal language.
- `docs/ideas/foundation-specs/jaynes-probability-logic-backend-foundation-spec.md` — scope close but missed the three-layer distinction and mismapped several objects to kernel vs adapter.

These drafts should be moved to `docs/archive/` or marked clearly as historical.

### 15.2 Consistent with

- `docs/specs/2026-04-21-gaia-lang-v6-design.md` — foundation is compatible with the v6 DSL; the changes this spec adds (PriorSpec, IndependenceDeclaration, InferStrategy field inlining, `Strategy.background`) are additive or clarifying, not contradictory.
- `docs/specs/2026-04-21-gaia-ir-v6-design.md` — IR changes required by this spec are listed in §16.
- `docs/foundations/theory/` — theory layer untouched.
- `docs/foundations/gaia-ir/` — protected layer; any IR schema change flows through a separate change-controlled PR (per CLAUDE.md rules).

### 15.3 Partially supersedes

- `docs/ideas/gaia-upgrade-specs/` — several idea-stage release specs under this directory proposed designs that diverge from the decisions here (notably the sidecar `EvidenceMetadata`, string-tag `independence_group`, and first-class `ExperimentRef`). Those release specs need rewriting against this foundation before they can be promoted out of `docs/ideas/`.

---

## 16. Summary of required IR / schema changes

Not an implementation plan, but the concrete diffs this spec implies for the IR layer. These belong in follow-up change-controlled PRs against `docs/foundations/gaia-ir/`.

1. Add `PriorSpec` schema. `Claim.prior` accepts `PriorSpec | float | None`; float is auto-wrapped.
2. Drop `Knowledge.type == "setting"` (post-migration).
3. Dissolve `EvidenceMetadata` pydantic class. Inline fields into `InferStrategy` (discriminated union).
4. Add `background: list[str]` to `IrStrategy` base (affects `DeriveStrategy`, `ComputeStrategy`, `InferStrategy`).
5. Add `MeasurementRecord` / `ErrorModelSpec` / `CallableRef` schemas. Attach `MeasurementRecord` via `Knowledge.metadata["measurement"]` with schema-validated read.
6. Extend `ReviewManifest` to support relation-level targets (`IndependenceDeclaration`). Schema migrates from `{action_label: status}` to `{target_id: {kind, action_labels, status, rationale}}`.
7. Remove `EvidenceMetadata.independence_group`.
8. Remove free-text `assumptions` anywhere it appears on strategies.

---

## 17. Open points for follow-up design

These are intentionally unresolved; the foundation records them as out-of-scope for the current round and names where they will be picked up.

- **Migration details for v5 → v6 strategies and `Setting`.** Handled by the migrator spec (separate document).
- **Categorical / continuous latent variables.** Parked at v1.x+; requires BP-layer extension.
- **First-class `ModelRecord`, `DatasetRef`, `ExperimentRef`.** Parked at v1.x+; triggered by real-user audit needs.
- **MaxEnt solver adapter.** Parked at v1.x+; `PriorSpec.policy="maxent"` tag is the present-day contract.
- **External theorem prover integration (Z3 / Lean).** Parked at v1.x+; requires Claim-proposition structuralisation first.
- **PPL adapter (PyMC / NumPyro).** Parked at v1.x+; predictive enters via `PriorSpec.policy="external_predictive"` tag in the meantime.

---

## 18. Acceptance of this foundation

This spec is considered the canonical foundation when:

- All kernel objects in §5 have pydantic schemas with versioned `schema_version`.
- The three-layer naming discipline (§4.3) is reflected in code, docs, and audit output.
- The IR changes in §16 are either implemented or tracked as explicit work items.
- The idea-stage foundation drafts under `docs/ideas/foundation-specs/` are archived.
- The release plan (a separate document) is rewritten against this foundation.

---

## 19. One-line invariant, restated

> **Gaia evaluates `P(Claim | Context)` on binary-proposition factor graphs, with evidence entering through reviewed likelihood factors, measurement noise handled in adapter space, and every ambition beyond that boundary kept outside the kernel.**
