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

This spec resolves that ambiguity. It picks a concrete scope (§2), draws the kernel boundary (§3), defines the three-layer probability semantics that keeps the kernel honest (§4), enumerates the kernel object set (§5), and records per-topic decisions (§6–§13) that were previously floating across multiple drafts.

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

Kernel is organised around **a single unified `Knowledge` type hierarchy**. Every declarable, QID-identified, cross-package-referenceable, reviewable object is a `Knowledge`. Prior-holding (`Claim`), annotative (`Note`, `Question`), reasoning-move (`Strategy` and its subtypes), and relational (`Operator` and its subtypes) objects are **subtypes of `Knowledge`**, not parallel hierarchies.

This unification is normative at both the **Gaia Lang (runtime)** layer and the **Gaia IR (serialisation)** layer. See §5 for the full inventory and §17 for the runtime/IR refactor this implies.

**Knowledge hierarchy**

```text
Knowledge                (QID + provenance + metadata + optional review_status)
  ├── Claim              (prior-bearing; binary BP variable; parameterised via class-as-predicate)
  ├── Note               (text annotation; not in BP)
  ├── Question           (inquiry lens; not in BP)
  ├── Strategy           (organising category for reasoning moves; §11 groups by family)
  │   │
  │   │   ── Support family (directional; deterministic / empirical)
  │   ├── DeriveStrategy
  │   ├── ObserveStrategy
  │   ├── ComputeStrategy
  │   │
  │   │   ── Correlate family (probabilistic; soft constraints on 2-Claim factors)
  │   ├── InferStrategy           (directional likelihood)
  │   └── AssociateStrategy       (symmetric correlation)
  │
  ├── Operator           (Relate family — symmetric, hard logical)
  │   ├── EqualOperator
  │   ├── ContradictOperator
  │   ├── ExclusiveOperator
  │   ├── NegationOperator        (not_)
  │   ├── ConjunctionOperator     (and_)
  │   └── DisjunctionOperator     (or_)
  │
  └── ComposedAction     (named composition of sub-Knowledge; see §12)
```

**Action families (organising labels, not new classes).** The Strategy subtypes group into two semantic families:
- **Support family** — directional, deterministic or empirical: `derive` / `observe` / `compute`.
- **Correlate family** — probabilistic, soft constraints on 2-Claim factors: `infer` (directional) / `associate` (symmetric). Runtime has a `Correlate(Action)` abstract base class shared by both, so future Correlate additions and shared concerns (parameter validation, `gaia check` hooks, audit conventions) have a natural home.

The `Relate` family (symmetric, hard logical) consists of the Operators. A fourth **Causal** family — for interventional / counterfactual reasoning — is parked as a future extension (§18); it would add `cause`, `intervene`, `counterfactual` verbs with do-calculus semantics.

**Belief** lives only on `Claim` (via `PriorSpec`, see §6). Strategy, Operator, and ComposedAction do not carry prior; they are declared reasoning / relational / compositional structure, not propositions about the world. **Review status** (`accepted / unreviewed / rejected`) is an optional field on any `Knowledge`.

**Review layer (the qualitative gate)**

- `ReviewManifest` — collection of `ReviewTarget`s keyed by `knowledge_id` (QID). Supports single-knowledge targets and relation-level targets (e.g., `IndependenceDeclaration`, see §7).
- `ReviewStatus` — `accepted / unreviewed / rejected`. Never a probability.

**Context layer (the information state)**

- `BeliefContext` — information state `I` used by inference; carries `context_id` (canonical SHA-256 over inputs).
- `BeliefState` — posterior output `P(Claim | I)` plus provenance. Published artefact at `.gaia/belief_state.json` — see §15 publish-time contract.
- `ContextLock` — reproducibility artefact.

**Evidence / measurement schema (the bridge to the world)**

- Correlate family IR fields (§11):
  - **`InferStrategy`** — `p_e_given_h`, `p_e_given_not_h` (both required), plus provenance `source_id` / `data_id` / `data_hash`. IR: `type="infer"`, `conditional_probabilities=[p_e_given_not_h, p_e_given_h]` inline.
  - **`AssociateStrategy`** — `p_a_given_b`, `p_b_given_a` (both required), plus same provenance fields. IR: `type="associate"`. Factor parameters are computed from the two conditionals plus marginals supplied via graph closure (Claim priors or other actions); `gaia check` validates coherence (§15.1).
- `MeasurementRecord` — schema for observed-value + noise specification.
- `DistributionSpec` — structured probability-distribution spec (`kind`, `params`, optional `CallableRef`). Used wherever a distribution enters IR (measurement noise, future prior shapes, etc.). Replaces the previously-named `ErrorModelSpec`.

**Note on the v0.5 inline-only parameter model.** Gaia kernel stores both Claim priors and Strategy CPTs **inline** on the Knowledge / Strategy objects themselves, not in sidecar records:

- `Knowledge.metadata["prior"]` — author's declared prior, injected at compile time by the `priors.py` authoring convenience (discovers a package-level `priors.py`, reads its `PRIORS` dict, writes values into Knowledge metadata before IR emission).
- `IrStrategy.conditional_probabilities` — author's declared CPT, inlined at compile time from the `Infer` action's `p_e_given_h` / `p_e_given_not_h` attributes.

The older sidecar mechanism (`PriorRecord`, `StrategyParamRecord`, `ParameterizationSource`, `ResolutionPolicy`) that supported review-sidecar-driven parameter updates is **deprecated since 0.4.2** (see `gaia/cli/_reviews.py` module docstring). Foundation does not re-introduce a sidecar record mechanism; any future "multi-source parameterisation" capability will be a separate design decision, not a continuation of the deprecated sidecar.

**Callable abstraction (the embedded-function escape)**

- `CallableRef` — registered name + signature + source hash + purity declaration. Shared by `ComputeStrategy`, `DistributionSpec`, and adapter hooks. **Always a provenance pointer, never a routine-execution pointer** — see §4.8.

**Prior schema**

- `PriorSpec` — `value`, `source_id`, `policy`, `justification`. Wraps the scalar with audit-relevant provenance. See §6.

### 3.2 Below the semantic line (ecosystem / adapters)

Everything delegated:

| Capability | Ecosystem tool | Integration style |
|---|---|---|
| Unit algebra | Pint | `gaia.unit` core module (thin facade, see §4.5) |
| Distribution specs + registry | — | `gaia.stats` core module (no runtime dep; see §4.6) |
| Distribution computation (logpdf / pmf / sampling) | scipy.stats | optional extras `gaia-lang[stats]`, lazy-imported in adapters |
| Physical constants | Pint's registry (CODATA) | `gaia.constants` core module (thin re-export; see §4.7) |
| Graph analysis | NetworkX | `GraphViewAdapter` (read-only views; optional) |
| Backend alternatives | pgmpy / pyAgrum / PyMC / NumPyro | `BackendAdapter` (optional extras) |
| Symbolic math | SymPy | optional |
| Hard-logic SAT/SMT | Z3 | optional, future |
| Ontology | RDFLib / Owlready2 | optional, future |
| Tabular / multidim data | pandas / xarray | `DatasetRef` (no inline storage; optional) |

**Pint is the one exception to the "optional adapter" rule.** Units are foundational to scientific claims; nearly every real Gaia package uses them. Gaia therefore ships a thin wrapper module `gaia.unit` that makes Pint a core dependency of `gaia-lang`. The Gaia kernel itself still does not depend on Pint — kernel schemas use the 2-field `QuantityLiteral` carrier (§4.5) — but the user-facing DSL does. Rationale:

- Pint's transitive closure is small (~500 KB, no numpy required).
- Gaia is a scientific reasoning framework; non-scientific use of Gaia is an edge case.
- A shared `gaia.unit` registry gives cross-package consistency (a unit registered by one package is visible to all).

**Hard rule (unchanged):** external objects **must not** appear in Gaia kernel semantic interfaces (`BeliefState`, `InferStrategy`, `MeasurementRecord`, etc.). Adapters normalise results into Gaia-native types at the adapter boundary. `gaia.unit` respects this: runtime quantities are Pint objects; everything crossing into IR becomes `QuantityLiteral`.

### 3.3 Rationale — why this boundary

- **Parameterised Claim stays in the kernel.** Gaia Lang v6 already ships class-as-predicate with typed parameters; removing it would force a design reversal.
- **Unit algebra goes to Pint, via a `gaia.unit` facade.** Pint is mature; Gaia reimplementing unit algebra would be a maintainer-time sink. The facade gives Gaia one place to absorb Pint-version drift and to configure Gaia-wide unit conventions.
- **MeasurementRecord stays in the kernel as schema.** Audit requires it to be structured (§10); schema is small; kernel does not compute on it.
- **Distribution computation goes to scipy.** Gaia kernel does not call `logpdf` / `logpmf` directly. Adapters do.

---

## 4. The three-layer probability semantics

The single most important idea in this spec. Without it, `Claim.prior`, `MeasurementRecord.noise`, and `InferStrategy`'s CPT get conflated, and audit cannot tell them apart.

### 4.1 The three layers

| Layer | Object | Probability type | Dimension | Computed by |
|---|---|---|---|---|
| **Proposition** | `Claim.prior` | Jaynesian belief `P(Claim \| I)` over a binary proposition | dimensionless, `[0, 1]` | Gaia kernel (BP) |
| **Measurement** | `MeasurementRecord.noise` | continuous density `p(obs \| true, params)` | has units (observation space; density has inverse units) | Adapter (scipy) |
| **Bridge** | `InferStrategy.p_e_given_h / p_e_given_not_h` (IR-level `IrStrategy.conditional_probabilities`) | binary likelihood pair `P(E \| H)` / `P(E \| ¬H)` | dimensionless | Adapter or author (§11) |

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
from gaia.unit import q
from gaia.stats import Normal
from gaia.evidence import gaussian_measurement    # §12 composition template

reading = measurement_claim(
    "Spectrometer produced reading 5120 K",
    observed_value=q(5120, "K"),
    noise=Normal(sigma=q(80, "K")),
)

# Proposition layer — belief on a binary claim
temp_high = Claim("TrueTemperature > 5000 K", prior=0.5)

# Bridge: a composition (§12) wires two compute sub-actions + one infer
# sub-action together. The composition runs scipy at author's compile time
# and bakes the CPT pair into the InferStrategy's conditional_probabilities.
gaussian_measurement(
    evidence=reading, hypothesis=temp_high,
    mu_h=q(5200, "K"),
    mu_not_h=q(4800, "K"),
    noise=Normal(sigma=q(80, "K")),     # may default-pull from reading's measurement record
)
# Composition expansion (at author's compile time):
#   sub-action compute_p_h:     scipy → density(5120 | μ=5200, σ=80) · dx  ≈ 0.31
#   sub-action compute_p_not_h: scipy → density(5120 | μ=4800, σ=80) · dx  ≈ 4.1e-5
#   sub-action infer:           takes those two as CPT pair
#
# Kernel stores in IR:
#   ComposedAction(
#       template_name="gaia:evidence:gaussian_measurement", template_version="1.0",
#       sub_knowledge=[compute_p_h_qid, compute_p_not_h_qid, infer_qid],
#       conclusion=reading_qid,        # infer returns the evidence Claim
#   )
#   InferStrategy(type="infer", conditional_probabilities=[4.1e-5, 0.31])  # [¬H, H]
#   + the 2 compute sub-strategies
#
# Downstream reads the baked conditional_probabilities; no scipy invocation.
# Layer-1 output: belief(temp_high) goes from 0.5 to ≈ 0.9999.
```

`q(80, "K")` is layer 2. `0.5` and `0.9999` are layer 1. `[4.1e-5, 0.31]` is layer 3. Three layers, three units, three semantics.

### 4.5 Unit handling policy

**Gaia does not reimplement a unit system.** Unit semantics — the registry of known unit names, unit equivalence, conversion, dimensional analysis, arithmetic — belongs entirely to **Pint** (the mature community package). But because units are foundational to scientific claims, Gaia ships a thin wrapper module `gaia.unit` so that every Gaia package sees the same configured Pint registry and uses a stable user-facing API.

The design has three cleanly separated pieces:

**1. `gaia.unit` — user-facing runtime (thin Pint facade; core module)**

```python
# gaia/unit.py   (~30 lines of real code)
from pint import UnitRegistry as _UR
from gaia.ir.schemas import QuantityLiteral

ureg = _UR()
# Gaia configures shared conventions here:
# - register domain units (e.g., "ppm", "pH")
# - enable common contexts (e.g., spectroscopy)
# - declare default preferred unit system (SI)

Quantity = ureg.Quantity  # re-export; runtime quantities are Pint objects

def q(value: float, unit: str) -> Quantity:
    return ureg.Quantity(value, unit)

def to_literal(qty: Quantity) -> QuantityLiteral:
    return QuantityLiteral(value=float(qty.magnitude), unit=str(qty.units))

def from_literal(lit: QuantityLiteral) -> Quantity:
    return ureg.Quantity(lit.value, lit.unit)
```

`gaia.unit.Quantity` is Pint's `Quantity` — users get Pint's full capability (`.to()`, arithmetic, dimensional checks). The wrapper's value is the shared `ureg` singleton and the serialisation bridge.

**2. `QuantityLiteral` — kernel IR carrier (2-field pydantic)**

```python
# gaia/ir/schemas.py
class QuantityLiteral(BaseModel):
    schema_version: Literal["gaia.quantity_literal.v1"] = "gaia.quantity_literal.v1"
    value: float
    unit: str
```

No methods. No arithmetic. No conversion. This is the only form of "quantity" the kernel ever sees — every `MeasurementRecord`, `DistributionSpec`, parameterised `Claim` parameter that carries a unit stores a `QuantityLiteral`. Hash is literal `{value, unit}` bytes.

**3. Adapter boundary: `to_literal` / `from_literal`**

Every point where a `gaia.unit.Quantity` enters IR (compilation, serialisation), it passes through `to_literal` and becomes a `QuantityLiteral`. Every point IR content is reconstructed at runtime, `from_literal` rehydrates a `gaia.unit.Quantity`. Kernel code reads `QuantityLiteral` only; user code reads `gaia.unit.Quantity` only.

**Split summary:**

| Concern | Owner |
|---|---|
| Shared `UnitRegistry` singleton + Gaia conventions | `gaia.unit` module (core) |
| User-facing `Quantity`, `q()`, arithmetic, conversion | `gaia.unit` (wraps Pint) |
| IR serialisation / identity / hash carrier | `QuantityLiteral` (kernel pydantic) |
| `QuantityLiteral` participation in Claim identity and `context_id` hash | Kernel, as literal `{value, unit}` bytes |
| Unit parsing, conversion, dimensional analysis, arithmetic | **Pint** (via `gaia.unit`) |
| Physical constants | `gaia.constants` re-exporting Pint registry; see §4.7 |

**Why kernel uses `QuantityLiteral` instead of Pint's `Quantity` directly:**

- **Hash stability.** Pint's native `Quantity` repr varies across library versions (`"5000 kelvin"` vs `"5000 K"` vs `"5000 degK"`). Hashing Pint's repr would let `context_id` drift across Pint versions, breaking reproducibility. `QuantityLiteral` is deterministic literal JSON.
- **Kernel-adapter separation.** The Gaia kernel itself never imports Pint. Only `gaia.unit` does. This keeps kernel tests runnable without Pint and keeps the kernel's type universe minimal.

`gaia-lang` takes Pint as a core dependency because `gaia.unit` is a core module; Gaia kernel code does not. This is consistent with §3.2's single exception to the optional-adapter rule.

**Hash invariant (normative):**

> Claim identity and `context_id` hash the literal `{value, unit}` of every `QuantityLiteral`. The kernel performs **no** unit canonicalisation or dimensional conversion at hash time.

Consequence: `q(5000, "K")` and `q(4726.85, "C")` produce **different** Claim identities even though they denote the same physical quantity. This is intentional.

**Rationale — why canonicalisation must not enter identity:**

- **Floating-point rounding.** Conversion introduces representation noise (`4726.85 "C" → "K"` rarely lands exactly on `5000.0`). Identity derived from converted values is non-deterministic across libraries and CPUs.
- **Offset units.** Temperature (`C ↔ K`), pressure (`barg ↔ bar`), and similar affine-transform units violate the assumption that conversion is multiplicative. `q(4727, "C")` and `q(5000, "K")` differ by `0.15 K` after conversion — is that author rounding or genuine inequality? The kernel cannot know.
- **Ratio-unit ambiguity.** `1/s` vs `Hz`, `rad/s` vs `Hz` — sometimes domain-identified, sometimes not. Registry-version-dependent.
- **Unit aliasing.** `"atm"` / `"atmosphere"` / `"standard_atmosphere"` canonicalise to the same unit in some Pint versions, not in others.

If the kernel canonicalised at hash time, all of the above would leak into Claim identity. The same package compiled against different Pint versions — or on different architectures — would produce different Claim IDs. Context reproducibility would break.

**Where equivalence checks belong:**

Equivalence is a **soft, audit-level** concern:

- `gaia audit` may use `gaia.unit` to detect Claims whose `QuantityLiteral` parameters appear equivalent after Pint conversion, and emit a soft warning (`"claim A and claim B may refer to the same physical quantity"`).
- `gaia explain` may display both the literal and a canonical-unit rendering for human comparison.
- Packages agree on a unit convention (typically SI) through documentation, not through kernel enforcement.

Both audit-level paths go through `gaia.unit`. Neither changes any Claim's identity or any context's hash.

### 4.6 Distribution handling policy

**Gaia does not reimplement a statistics library.** Distribution computations (logpdf, logpmf, sampling, moments) belong to **scipy.stats**. But because distribution specifications are used pervasively across Gaia (measurement noise, future prior shapes, future posterior predictives, evidence adapters), Gaia ships a core module `gaia.stats` that owns the distribution **spec side** — the named registry, the user-facing constructors, and the IR serialisation. Runtime computation stays in an optional scipy-backed adapter.

The design parallels §4.5, with one deliberate asymmetry: **scipy remains an optional extras dependency**. Authors constructing distribution specs in `gaia.stats` do not need scipy installed; only running evidence adapters that evaluate those specs requires scipy.

**1. `gaia.stats` — user-facing spec constructors (core module; no scipy import at load time)**

```python
# gaia/stats.py
from gaia.ir.schemas import DistributionSpec, CallableRef
from gaia.unit import Quantity

# Built-in distribution registry — metadata only (param schema + dispatch tag)
_REGISTRY = {
    "normal":       {"params": {"mu": "Quantity", "sigma": "Quantity"}},
    "lognormal":    {"params": {"mu": "Quantity", "sigma": "Quantity"}},
    "student_t":    {"params": {"df": "float",    "mu": "Quantity", "sigma": "Quantity"}},
    "cauchy":       {"params": {"mu": "Quantity", "gamma": "Quantity"}},
    "binomial":     {"params": {"n": "int",       "p": "float"}},
    "poisson":      {"params": {"rate": "Quantity"}},
    "exponential":  {"params": {"rate": "Quantity"}},
    "beta":         {"params": {"alpha": "float", "beta": "float"}},
}

def Normal(*, mu: Quantity | float = 0, sigma: Quantity) -> DistributionSpec:
    return DistributionSpec(kind="normal", params={"mu": ..., "sigma": ...})

def Binomial(*, n: int, p: float) -> DistributionSpec:
    return DistributionSpec(kind="binomial", params={"n": n, "p": p})

# ... six more constructors, one per registered kind

def from_callable(fn, *, name: str, version: str, params: dict | None = None) -> DistributionSpec:
    """Build an inline custom DistributionSpec backed by a CallableRef."""
    return DistributionSpec(
        kind="custom",
        params=params or {},
        callable_ref=CallableRef(name=name, version=version, ...),
    )
```

**2. `DistributionSpec` — kernel IR carrier (pydantic)**

```python
# gaia/ir/schemas.py
class DistributionSpec(BaseModel):
    schema_version: Literal["gaia.distribution.v1"] = "gaia.distribution.v1"
    kind: Literal[
        "normal", "lognormal", "student_t", "cauchy",
        "binomial", "poisson", "exponential", "beta",
        "custom",
    ]
    params: dict[str, QuantityLiteral | float | int]
    callable_ref: CallableRef | None = None
```

**Validator invariant (normative):**

> If `kind` is a registered built-in, `callable_ref` MUST be `None` (dispatch goes through the scipy adapter by `kind`). If `kind == "custom"`, `callable_ref` MUST be non-`None` (runtime resolution goes through the CallableRef).

**3. `gaia-lang[stats]` extras — scipy-backed adapter (optional)**

```python
# gaia/adapters/stats/scipy_adapter.py   (lazy-loaded)
import scipy.stats

def logpdf(spec: DistributionSpec, x: float) -> float:
    if spec.kind == "normal":
        return scipy.stats.norm.logpdf(x, ...)
    elif spec.kind == "custom":
        return spec.callable_ref.resolve()(x, ...)
    # ...
```

Evidence adapters (Gaussian measurement evidence, Binomial evidence, etc.) lazy-import this module when they need to evaluate a spec. Tests that only exercise spec construction do not need scipy.

**User-extensibility (normative):**

> The built-in registry of 8 kinds is the Gaia-shipped default. Authors add custom distributions through `gaia.stats.from_callable(...)` or equivalent decorator-based helpers, producing a `DistributionSpec(kind="custom", callable_ref=...)`. No kernel extension is required; no new schema is required; the existing `CallableRef` machinery (§5) handles naming, versioning, source hashing, and cross-package import review.

**Why scipy is not a core dependency (unlike Pint for `gaia.unit`):**

- **Weight.** scipy + numpy ≈ 70 MB installed; Pint ≈ 500 KB. The core-dep promotion argument that worked for Pint does not carry over.
- **Interaction pattern.** Pint objects are manipulated by user code (arithmetic, conversion). Distribution evaluation happens almost exclusively inside adapters, not in user code. Users construct specs; adapters evaluate them.
- **Testing.** Kernel and `gaia.stats` spec tests run without scipy installed, keeping CI light.

The asymmetry is intentional: architectural pattern is shared (facade over mature package, kernel owns schema, adapter owns compute), dependency policy differs because dependency weight and usage pattern differ.

### 4.7 Physical constants

Physical constants (`c`, `h`, `k_B`, `G`, `N_A`, particle masses, etc.) recur across scientific claims. Gaia ships a core module `gaia.constants` that is a **thin curated re-export** of Pint's built-in constant registry — no new schema, no new dependency, no new kernel object.

```python
# gaia/constants.py
"""Gaia-blessed physical constants. Values sourced from Pint's registry (CODATA-based)."""

from gaia.unit import ureg

# Fundamental
speed_of_light = c = ureg.speed_of_light
planck = h = ureg.planck_constant
hbar = ureg.hbar
boltzmann = k_B = ureg.boltzmann_constant
elementary_charge = e = ureg.elementary_charge

# Gravitation
gravitational_constant = G = ureg.gravitational_constant
standard_gravity = g_0 = ureg.standard_gravity

# Thermodynamics
avogadro = N_A = ureg.avogadro_number
molar_gas_constant = R = ureg.molar_gas_constant
stefan_boltzmann = sigma_SB = ureg.stefan_boltzmann_constant

# Electromagnetism
vacuum_permittivity = eps_0 = ureg.vacuum_permittivity
vacuum_permeability = mu_0 = ureg.vacuum_permeability

# Particle masses
electron_mass = m_e = ureg.electron_mass
proton_mass = m_p = ureg.proton_mass
neutron_mass = m_n = ureg.neutron_mass
# ... etc.
```

Each constant is a `gaia.unit.Quantity` (= Pint Quantity with units attached). Crossing into IR via `to_literal` follows the standard §4.5 path.

**Design points:**

- **No new kernel schema.** Constants are named `Quantity` instances; the existing `QuantityLiteral` carrier handles IR serialisation.
- **No new dependency.** Pint is already core (§4.5); `gaia.constants` adds nothing transitively.
- **Double naming (short + long).** `c` and `speed_of_light` both resolve to the same value. Authors choose per context; a formula-dense file reads better with `c`, a narrative-heavy docstring reads better with `speed_of_light`.
- **CODATA version tracks Pint.** When Pint incorporates a new CODATA release, Gaia packages pick up the new values on upgrade. If version pinning of constant values becomes a reproducibility concern (similar to unit registry versioning, §17), that is a future extension, not a v0.x requirement.
- **User-extensibility.** Authors can add their own constants at package level (`my_pkg/constants.py`) using `gaia.unit.q(...)` — no Gaia mechanism required. `gaia.constants` is a Gaia-blessed default set, not an enumeration ceiling.

### 4.8 `CallableRef` is provenance, not an execution pointer

**Normative invariant** (the most important rule governing cross-package safety and reproducibility in Gaia):

> Every `CallableRef` in a Gaia IR is a **provenance pointer** — a record of which function computed a particular result, pinned by name + version + source hash. It is **not** a routine-execution pointer. The expected execution of any `CallableRef` happens in the **declaring package** at its author's compile / infer time; the resulting value (a derived Claim's parameter, a likelihood scalar, a baked CPT) is then stored in the IR / published `beliefs.json` / future `belief_state.json` as the authoritative result. Downstream packages consume the stored result and **do not invoke upstream `CallableRef`s** during any default inference flow, at any `--depth`.

The invariant applies to all three places `CallableRef` appears in the kernel (see §5):

- **`ComputeStrategy.callable_ref`** — when the author calls a `@compute`-decorated function in their package, the function runs in the author's Python context and returns a derived `Claim` with parameters already bound. The returned Claim enters the IR with values inlined (parameters in `Claim.parameters`, participating in §4.5 literal-hash identity). The `CallableRef` is retained on the `ComputeStrategy` for provenance: "this derived Claim was produced by `pkg:my_fn@1.0` at source hash `sha256:…`". Downstream reads the derived Claim; the callable is never resolved or invoked downstream.
- **`DistributionSpec.callable_ref`** (when `kind == "custom"`) — the adapter that consumes the `DistributionSpec` (e.g., `gaussian_measurement_evidence`) invokes the callable at the author's compile / infer time to evaluate `logpdf` / compute a likelihood ratio, baking the resulting scalar into `IrStrategy.conditional_probabilities`. The `CallableRef` stays on the `DistributionSpec` for audit and recompute; downstream BP reads the baked CPT only.
- **Adapter hooks** — distribution-evaluation adapters (scipy-backed `gaia/adapters/stats/scipy_adapter.py`, etc.) register their own `CallableRef` on the `@compute` sub-action they are invoked from (inside a composition template). This records which adapter produced the scalar via the composition's own `sub_knowledge` trace; the adapter runs in the author's context and not again downstream. Foundation does not carry a separate sidecar record for adapter provenance — the composition's sub-knowledge trace IS the provenance (§12).

**The only operation that invokes a `CallableRef` at all** — in the entire kernel — is the explicitly-named re-execution path `gaia recompute` (§15.3). That command is opt-in, R4-gated (§7.5), version-pinned, and defaults to abort-on-unreviewed. Everything else uses baked results.

**Consequences:**

- Cross-package code safety is not a day-to-day concern. Downstream `gaia infer` runs only kernel math on baked numeric factors; it never imports upstream author code.
- `--depth N` (joint-graph) is **not a re-execution mode**. It merges upstream IR and upstream's baked factor parameters into the local factor graph; BP propagates over the merged graph using the merged values. No upstream `CallableRef` is invoked at any depth.
- `purity` declarations on `CallableRef` (pure / deterministic / impure) are author-assertion metadata consumed by optional audits (`gaia audit callable-purity`) and by the `gaia recompute` scheduler. They are never load-bearing at default inference time, because default inference does not execute callables.
- Pint / scipy version drift upstream cannot change downstream belief results, because the values those libraries produce were baked at upstream compile time and are shipped verbatim.

Any future kernel extension that proposes "downstream invokes an upstream callable during default inference" must first amend this invariant. Under the current foundation, no such path exists.

---

## 5. Kernel object inventory

Canonical set (pydantic schemas). Versioned via `schema_version: Literal["gaia.<name>.v1"]`.

**Knowledge hierarchy** — every declarable QID-identified object is a `Knowledge`. Belief-bearing is only `Claim`; reasoning moves are `Strategy` subtypes; relational / propositional combinators are `Operator` subtypes. Same hierarchy at Gaia Lang (runtime) and Gaia IR (serialisation) layers; see §5.x "Lang ↔ IR mapping" below.

```text
Knowledge (base — QID + provenance + metadata + optional review_status)
  ├── Claim              (prior-bearing; binary BP variable; parameterisable)
  ├── Note               (free text; no BP)
  ├── Question           (inquiry lens; no BP; may carry targets)
  │
  ├── Strategy           (reasoning move; premises + conclusion + background)
  │   │
  │   │   ── Support family (directional; deterministic / empirical)
  │   ├── DeriveStrategy       (type="deduction")
  │   ├── ObserveStrategy      (type="deduction", pattern="observation")
  │   ├── ComputeStrategy      (type="deduction", compute={...} + CallableRef)
  │   │
  │   │   ── Correlate family (probabilistic; soft constraint on 2-Claim factor)
  │   │       — runtime Correlate(Action) abstract base (§11.1)
  │   ├── InferStrategy        (type="infer";     p_e_given_h, p_e_given_not_h; §11.2)
  │   └── AssociateStrategy    (type="associate"; p_a_given_b, p_b_given_a; §11.4)
  │
  ├── Operator           (Relate family — symmetric hard logical)
  │   ├── EqualOperator
  │   ├── ContradictOperator
  │   ├── ExclusiveOperator
  │   ├── NegationOperator         (not_)
  │   ├── ConjunctionOperator      (and_)
  │   └── DisjunctionOperator      (or_)
  │
  └── ComposedAction     (named, reviewable composition of sub-Knowledge; see §12)
```

**`ComposedAction` is a Knowledge subtype**, sibling of `Strategy` and `Operator`. It bundles a list of sub-Knowledge references (`sub_knowledge: list[str]` — QIDs) into a single reviewable unit with stable identity via a template name + version. IR-level it replaces v5's `CompositeStrategy` (same `_structure_hash` mechanism, promoted from Strategy-subtype to Knowledge-subtype and with the sub-list generalised to any Knowledge kind, not just strategies).

**Inline parameters (no sidecar records)** — Gaia kernel holds Claim priors and Strategy CPTs inline on the Knowledge / Strategy objects at IR emission time. There is no kernel-level sidecar record for parameters in v0.5+; the `priors.py` authoring convenience is a DSL-layer ergonomics feature, not a kernel object.

```text
Knowledge.metadata["prior"]           — author's declared prior, injected at compile time
                                        by the priors.py authoring convenience
IrStrategy.conditional_probabilities  — author's declared CPT, inlined at compile time from
                                        the Infer action's p_e_given_h / p_e_given_not_h
                                        (for infer: [p_e_given_not_h, p_e_given_h];
                                         for noisy_and: one value)
```

Legacy sidecar records (`PriorRecord`, `StrategyParamRecord`, `ParameterizationSource`, `ResolutionPolicy`) are **deprecated since 0.4.2** in favour of this inline model. They remain in the codebase for backward compatibility (see `gaia/cli/_reviews.py` DEPRECATED header) but **are not part of the foundation-level kernel**. A future "multi-source parameterisation" capability, if needed, would be a separate design decision, not a re-adoption of the deprecated sidecar.

**Review layer**

```text
ReviewManifest           — collection of ReviewTarget's keyed by knowledge_id (QID)
ReviewTarget             — single-Knowledge target; status = accepted | unreviewed | rejected
IndependenceDeclaration  — relation-level target (§7); kind ∈ {identical, independent, correlated, partial}
TrustDelegation          — relation-level target (§7.5); bulk-trust a foreign package@version
```

**Context layer**

```text
BeliefContext            — information state I; carries context_id (canonical SHA-256 of inputs)
BeliefState              — posterior output P(Claim | I); published artefact per §15
ContextLock              — reproducibility artefact
```

**Measurement / Distribution / Quantity carriers**

```text
MeasurementRecord        — observed-value + noise spec + instrument/protocol/data IDs
DistributionSpec         — kind + params + optional CallableRef; used for noise, future priors
QuantityLiteral          — 2-field {value, unit}; IR serialisation carrier (§4.5)
```

**Callable / Prior schemas**

```text
CallableRef              — {name, version, source_hash, signature, purity}; provenance-only (§4.8)
PriorSpec                — value + source_id + policy + justification (§6)
```

**`EvidenceMetadata` is not in this list** — its fields are inlined into `InferStrategy` (§11). The previously-named `ErrorModelSpec` is now `DistributionSpec` (§4.6).

**`gaia.unit.Quantity`, `gaia.stats.Normal/Binomial/...`, `gaia.constants.*`** — runtime user-facing helpers in the `gaia.unit` / `gaia.stats` / `gaia.constants` core modules (§4.5 / §4.6 / §4.7). **Not** kernel IR objects.

### 5.x Lang ↔ IR mapping

Same `Knowledge` hierarchy exists at both layers, with different shapes:

| Aspect | Gaia Lang (runtime) | Gaia IR (serialisation) |
|---|---|---|
| References | real Python object references | QID strings |
| Identity | assigned by package registration | canonical QID `github:pkg::kind::label` |
| `Claim.prior` | `float` or `PriorSpec` (auto-wrapped) | `PriorSpec` |
| `Strategy.premises` / `conclusion` | `list[Knowledge]` / `Knowledge` (objects) | `list[str]` / `str` (QIDs) |
| `Strategy.background` | `list[Knowledge]` | `list[str]` |
| Parameters | `Quantity` (Pint), float, int, str | `QuantityLiteral`, primitive |
| Subtype discriminator | Python class | pydantic `Literal[...]` / `kind:` field |

The compiler (`gaia/lang/compiler/compile.py`) transforms Lang → IR, resolving object references to QIDs and wrapping scalars into schema objects.

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

`ReviewManifest` carries `ReviewTarget`s keyed by `knowledge_id` (QID). Under U1 (§3.1, §5) all reviewable objects — claims, strategies, operators — share this QID namespace, so a single target-identity scheme covers everything. The manifest also carries **relation-level targets**, keyed by their own QID, that constrain how N existing `Knowledge` objects relate:

```python
class ReviewTarget(BaseModel):
    schema_version: Literal["gaia.review_target.v1"] = "gaia.review_target.v1"
    target_id: str                       # QID
    status: Literal["accepted", "unreviewed", "rejected"]
    rationale: str | None = None

class IndependenceDeclaration(ReviewTarget):
    schema_version: Literal["gaia.independence.v1"] = "gaia.independence.v1"
    factors: list[str]                   # knowledge_ids (QIDs) of the N InferStrategies
    kind: Literal["identical", "independent", "correlated", "partial"]
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

### 7.5 Cross-package review authority — R4

When downstream package B references a foreign `Knowledge K` from upstream package A, two independent `ReviewStatus`s exist: A's (authored by A's maintainers) and B's (authored by B's maintainers in B's own `ReviewManifest`). The foundation picks **additive with bulk-trust delegation** (R4) as the default authority model.

**Normative effective-status rule.** For a foreign `Knowledge K` referenced by downstream B:

```text
upstream_status = K.review_status in A's package
local_status    = B's ReviewManifest entry for K (default "unreviewed" if absent)
delegation      = B's accepted TrustDelegation covering "A@<version>", if any

effective(K for B) = "active"  iff   upstream_status == "accepted"
                                  AND (local_status == "accepted"
                                       OR delegation applies to K)
                   = "inactive" otherwise
```

Two hard constraints:

- **Upstream reject cannot be bypassed.** If `upstream_status == "rejected"`, K is inactive in B regardless of B's manifest or any delegation. A's maintainers declaring a piece of reasoning as unsound is a scientific-integrity commitment; downstream cannot override.
- **Local unreviewed is inactive.** Silence in B's manifest is not consent. To activate a foreign K, B either reviews it directly or covers it via a `TrustDelegation`.

**`TrustDelegation` — bulk trust target.** To avoid forcing downstream packages to review every foreign `Knowledge` one by one (impractical when importing large upstream libraries), B may accept a `TrustDelegation` as a single review target that covers all of A's Knowledge at a pinned version:

```python
class TrustDelegation(ReviewTarget):
    schema_version: Literal["gaia.trust_delegation.v1"] = "gaia.trust_delegation.v1"
    package: str                         # upstream package name (e.g., "github:galileo")
    version: str                         # specific version, not a range
    scope: Literal["all_knowledge", "exclude_compute", "claims_only"] = "all_knowledge"
    rationale: str
    # inherits: status (accepted | unreviewed | rejected)
```

Key rules:

- **Version-pinned only.** `TrustDelegation` binds to a specific version string (`"1.2.3"`), never a range. A new upstream version (`"1.2.4"`) creates a fresh upstream artefact and does not inherit trust. Authors can issue a new `TrustDelegation` per version.
- **Author-only scope.** Delegating to a package author across all versions (`trust_author("alice")`) or across all packages (`trust_all`) is **not** supported. Both patterns let an upstream change silently acquire downstream activation, which violates the integrity goals of R4.
- **The delegation itself is a review target.** It appears in B's manifest and requires B's explicit accept. That accept is a judgment ("I've examined `A@1.2.3` enough to trust it"), not a formality.
- **`scope` lets downstream narrow trust.** `"claims_only"` activates only foreign Claims, refusing foreign Strategies / Operators and deferring those to per-knowledge review. Useful when downstream trusts A's data/claims but wants to review A's reasoning independently.

**Why additive, not a simpler rule.** The pure-upstream-authority option (R1) makes the registry a one-hop trust chain where any submitted package can flow its reviews downstream unchecked; that removes downstream scientific judgment and effectively gives upstream maintainers unilateral write access to downstream beliefs. The pure-independent-review option (R2) is scientifically clean but collapses under registry scale: every Gaia package transitively imports dozens of others, and reviewing every foreign Knowledge is infeasible. R4 threads the needle by defaulting to independence (safe baseline) and permitting bulk trust as an **explicit**, **version-pinned**, **itself-reviewed** shortcut for the common case of "I trust this upstream".

---

## 8. Model comparison

**Decision: Binary-claim wrapping. No first-class `Model` object in the v0.x kernel.**

### 8.1 How it works

Model comparison is expressed at the proposition layer:

- "M1 is adequate for dataset D" → a `Claim`.
- "M1 explains D better than M2" → a `Claim`.
- Three candidates → `exclusive(M1_best, M2_best, M3_best)` plus pairwise likelihood evidence.

Authors citing a published Bayes factor do not write a `bayes_factor()` or `likelihood_ratio()` helper — Gaia does not ship those (§11). Authors commit to a concrete `(p_e_given_h, p_e_given_not_h)` pair and record the derivation from the literature BF in the `rationale` field of the `Infer` action. See §11 for the reasoning behind requiring CPT commitment rather than bare ratios.

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
- Wrap the setup in a `@composition` template (§12) if the external computation steps should be captured as explicit sub-actions (e.g., `@compute` calls that load the PPL result file). The composition's `sub_knowledge` trace is the canonical provenance.

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

## 11. Correlate family — `infer` and `associate`

**Decision: Gaia kernel groups the probabilistic 2-Claim relations into a single `Correlate` family with two members — `infer` (directional likelihood) and `associate` (symmetric correlation). Both return helper Claims with distinct semantic content. Both contribute soft constraints on 2×2 factors; `gaia check` validates coherence (hole / redundant / conflict).**

### 11.1 The four action families at a glance

| Family | Character | Members | Helper Claim kinds |
|---|---|---|---|
| **Support** | Directional, deterministic / empirical | `derive`, `observe`, `compute` | (return conclusion Claim directly) |
| **Relate** | Symmetric, hard logical | `equal`, `contradict`, `exclusive`, `not_`, `and_`, `or_` | `equivalence_result`, `contradiction_result`, `complement_result`, `negation_result`, `conjunction_result`, `disjunction_result` |
| **Correlate** | Probabilistic, soft constraint (**new organising label**) | `infer`, `associate` | `likelihood`, `association` |
| **Causal** | Interventional (do-calculus, counterfactuals) | — (not in v0.x; see §18 open points) | — |

The `Correlate` family is the natural home for probabilistic 2-Claim relations. `infer` asserts that evidence E supports hypothesis H in a specific direction (a likelihood factor that updates belief on H given observation of E). `associate` asserts that A and B are statistically related without privileging a direction (observational correlation, no causal claim).

Runtime class hierarchy (`gaia/lang/runtime/action.py`) grows a new abstract base:

```python
@dataclass
class Correlate(Action):
    """Probabilistic 2-Claim relation. Base for Infer and Associate."""
    ...

@dataclass
class Infer(Correlate):
    hypothesis: Claim | None = None
    evidence: Claim | None = None
    p_e_given_h: float = 0.5
    p_e_given_not_h: float = 0.5
    helper: Claim | None = None

@dataclass
class Associate(Correlate):
    a: Claim | None = None
    b: Claim | None = None
    p_a_given_b: float = 0.5
    p_b_given_a: float = 0.5
    helper: Claim | None = None
```

`Correlate` is abstract — authors use `Infer` or `Associate` concretely, not the base directly. The base class is the natural home for shared concerns (parameter validation, `gaia check` hooks, audit metadata conventions).

### 11.2 `infer` — directional likelihood evidence

Authors write:

```python
from gaia.lang import Claim, infer

evidence_positive = Claim("Diagnostic test T returned positive.")
disease = Claim("Patient has disease D.")

support_claim = infer(
    evidence=evidence_positive,
    hypothesis=disease,
    p_e_given_h=0.95,           # REQUIRED. Cromwell-clamped.
    p_e_given_not_h=0.10,       # REQUIRED. Cromwell-clamped.
    prior_hypothesis=0.10,      # OPTIONAL. Population prevalence of disease in this context.
    prior_evidence=None,        # OPTIONAL. Rarely needed — usually closes from the factor.
    background=[assumption_a, assumption_b],   # §13
    source_id="lab:test_T",
    data_id="patient_001.test_T.pass_1",
    data_hash="sha256:…",
    rationale=(
        "Test T: sensitivity 95% / false-positive 10% per ADA 2024 diagnostic criteria. "
        "Prior 10% from NHANES adult prevalence."
    ),
)
# support_claim is a helper Claim with metadata["helper_kind"] = "likelihood".
# Its content: "evidence_positive statistically supports disease with P(E|H)=0.95, P(E|¬H)=0.10."
```

**Required arguments:** `p_e_given_h`, `p_e_given_not_h`. Cromwell clamp `(ε, 1-ε)` applies at compile time.

**Optional prior arguments** (`prior_hypothesis`, `prior_evidence`). Authors writing an `infer` are often in the same epistemic context where the hypothesis's prior is being estimated — the paper, the cohort, the domain-expert judgment that justifies the CPT pair usually justifies the marginal too. Co-locating these numbers at the `infer` call site keeps related judgments together in the IR and in the reviewer's view.

These are **constraint contributions**, not overrides. Under the soft-constraint framework, a prior can be provided by any of:

- the Claim declaration (`Claim("disease", prior=0.10)`)
- `priors.py` at package level
- the `infer(..., prior_hypothesis=...)` argument
- an earlier action whose output pins the marginal

`gaia check` (§17 item 11e) reports the outcome across all providers:

- **Hole** — no provider → BP cannot close the factor.
- **Redundant** — multiple providers agreeing → informational; author confirms intentional over-specification.
- **Conflict** — multiple providers disagreeing → hard error.

Redundancy is **not a risk** — it is a natural consequence of authors capturing their reasoning in the most convenient place. Where convenience and rigour coincide, Gaia does not force a choice.

**Return value:** `infer()` returns a generated helper Claim whose `helper_kind` is `"likelihood"`. This is the object `ComposedAction.conclusion` points at when a composition ends in `infer(...)`. Review targets the helper Claim — "do you accept that evidence E statistically supports hypothesis H with these conditionals?"

IR lowering follows the v0.5 shape — `type="infer"`, `premises=[H_qid]`, `conclusion=E_qid`, `conditional_probabilities=[P(E|¬H), P(E|H)]` inline. Well-known metadata keys remain under `metadata["evidence"] = {source_id, data_id, data_hash, rationale}`. The optional priors, when provided, become additional entries in the package's prior-provider graph for `hypothesis` / `evidence`, with `source_id = "from:{infer_action_qid}"` so `gaia check` can attribute them.

### 11.3 Why forced CPT pair, no LR-only path

The likelihood-ratio-only shortcut fails two tests.

**Scientific-rigour test.** A scientist who knows "the Bayes factor is 8.7" but cannot commit to specific values of `P(E|H)` and `P(E|¬H)` is skipping the harder question. `P(E|H)` is concrete: *given the world where H is true, what probability do I assign to observing E?* An author who cannot answer that has not done the modelling work the Infer action is supposed to record. Requiring the pair forces that work to happen and to be reviewable.

**BP-correctness test.** When the evidence claim `E` is not pinned true (has its own prior, is reached by other factors, is itself a hypothesis), BP propagates messages that depend on the **absolute** values of `P(E|H)` and `P(E|¬H)`, not only their ratio:

```text
P(E = true | I)  =  P(E | H, I) · P(H | I)  +  P(E | ¬H, I) · P(¬H | I)
```

Different absolute CPTs with the same ratio yield different `E` posteriors, which propagate onward through the factor graph. Any "LR → CPT" normalisation the kernel might pick is **arbitrary** — no scientific justification, and would produce author-unrecognisable results. By forcing the pair, Gaia makes the author own the numerical commitment.

### 11.4 `associate` — symmetric statistical correlation

Authors write:

```python
from gaia.lang import Claim, associate

smoking = Claim("Subject is a regular smoker.")
lung_cancer = Claim("Subject develops lung cancer.")
# Background information state (e.g., subject is in a cohort study)
cohort = Claim("Subject is in observational cohort C, adult, followed 10 years.")

assoc_claim = associate(
    smoking, lung_cancer,
    p_a_given_b=0.75,           # P(smoker | lung_cancer, I)
    p_b_given_a=0.20,           # P(lung_cancer | smoker, I)
    prior_a=0.25,               # OPTIONAL. P(smoker | I) — cohort-derived marginal.
    prior_b=None,               # OPTIONAL. If None, closed from A's marginal + Bayes.
    background=[cohort],        # I
    rationale=(
        "From cohort study C, Table 2: in diagnosed cases, 75% were smokers; "
        "in smokers, 20% developed lung cancer over 10y follow-up. "
        "Smoking prevalence in cohort adults ≈ 25%. "
        "Observational data; no causal claim implied."
    ),
)
# assoc_claim is a helper Claim with metadata["helper_kind"] = "association".
# Its content: "smoking and lung_cancer are statistically associated under I
#  with P(A|B,I)=0.75, P(B|A,I)=0.20."
```

**Return value:** a helper Claim with `helper_kind="association"`. Distinct from `"likelihood"`: reviewer accepting this claim accepts **correlation under I**, not a directional "A supports B" reading.

**Why both `p_a_given_b` and `p_b_given_a`, not just one?** Under Jaynesian framework, each of these is a legitimate conditional probability the author might have from data. Observational studies routinely report both directions (e.g., "in cases, 75% had exposure; in exposed, 20% developed outcome"). The data is symmetric in presentation; the signature reflects that.

**Optional marginal priors (`prior_a`, `prior_b`).** The same context that provides the two conditionals often also provides marginal prevalences — the cohort paper that reports "75% of cases were smokers" usually also reports "25% smoking prevalence in the cohort". Authors can record that marginal at the `associate` call site, co-locating all related probabilistic context in one IR node.

**Soft-constraint semantics (auto + `gaia check`):** `associate` contributes two conditional constraints on the joint `φ(A, B | I)`, which has 3 free parameters (4 entries summing to 1). One more constraint — A's marginal, B's marginal, or one joint entry — closes the factor. That closing constraint can come from:

- the optional `prior_a` / `prior_b` arguments on this call,
- the Claim declaration (`Claim("smoking", prior=0.25)`),
- `priors.py` at package level,
- other actions whose outputs pin the marginals.

`gaia check` (§17 item 11e) reports the outcome across all providers:

- **Hole** — no path provides the missing marginal; BP cannot form the factor. Hard error.
- **Redundant** — multiple sources agree (e.g., `associate(..., prior_a=0.25)` plus `Claim("smoking", prior=0.25)`). Informational; author confirms intentional over-specification. **Not a risk** — the extra source is audit-friendly context, not a conflict.
- **Conflict** — multiple sources disagree (Bayes-violation). Hard error.

These three categories apply to **any** probabilistic factor — not just `associate`. `gaia check` is the kernel's factor-graph coherence tool (§15.1 audit role).

**BP factor lowering contract (normative).** To avoid ambiguity and double-counting, `associate` lowers to a **pairwise association potential**, not a full joint factor. The construction is:

1. **`gaia check` resolves one consistent marginal for each of A and B** from the prior-provider graph (Claim declaration, `priors.py`, `prior_a`/`prior_b` args on this or other actions, outputs of other actions). Let the resolved values be `P(A|I) = π_a`, `P(B|I) = π_b`. If more than one provider is consistent, any one is used (redundancy already reported). If `π_b` is missing, it is derived via Bayes: `π_b = π_a · p_b_given_a / p_a_given_b` (and vice versa).
2. **Derive the full joint distribution** under I:
    ```
    P(A=1, B=1 | I) = p_a_given_b · π_b    # = p_b_given_a · π_a (Bayes-consistent)
    P(A=0, B=1 | I) = (1 - p_a_given_b) · π_b
    P(A=1, B=0 | I) = (1 - p_b_given_a) · π_a / ??? — derived from marginal constraints
    P(A=0, B=0 | I) = 1 - [above three]
    ```
    Exact algebra: use `π_a`, `π_b`, and the two conditionals as four linearly dependent constraints on the four joint entries; Bayes consistency must hold (else conflict, §11.4).
3. **Compute the association potential** `ψ(A, B | I)` that makes the pairwise factor independent of the marginals:
    ```
    ψ(A=a, B=b | I) = P(A=a, B=b | I) / [P(A=a | I) · P(B=b | I)]
    ```
    Four values, computed at all four (A, B) combinations.
4. **Insert `ψ` as a pairwise factor** in the BP graph. The unary prior factors `P(A|I)` and `P(B|I)` come from the **resolved marginal providers** (Claim declaration / `priors.py` / etc.) and are added to BP separately — exactly once each, via the standard unary-prior pathway.
5. **No double-counting invariant**: `associate`'s factor contributes only the **normalised pairwise interaction**, not any marginal mass. The joint that BP reconstructs is `P(A, B | I) = P(A|I) · P(B|I) · ψ(A, B | I)`, which by construction equals the author's intended joint.

This rule has two consequences worth calling out:

- **`prior_a` / `prior_b` on the `associate` call contribute to the prior-provider graph like any other prior source** — they are resolved through the same `gaia check` path as `Claim.prior` / `priors.py`, not injected directly into BP as a second unary factor. Any one resolved provider is consumed by step 1 above; additional consistent providers show up as `redundant`.
- **Two `associate` actions sharing a Claim do not double-count that Claim's marginal** — each uses the resolved `π_a` from the prior-provider graph for its own ψ computation. Multiple pairwise ψ factors and one unary prior factor per Claim is the canonical BP decomposition.

Future **Causal family** verbs (§18 open point) will use an analogous lowering contract with do-calculus / interventional semantics, factored through unary priors and interventional pairwise factors to preserve the same no-double-counting invariant.

### 11.5 Literature Bayes-factor citations

Common authoring case: a paper reports "Bayes factor for E on H is 8.7". Gaia does **not** ship a `bayes_factor()` or `likelihood_ratio()` DSL helper. The author does their own conversion:

```python
# Author's judgment:
#   Per trial X, published BF(E on H) = 8.7.
#   Anchor P(E|H) ≈ 0.87 based on domain judgment.
#   Then P(E|¬H) = 0.87 / 8.7 = 0.10.
infer(
    evidence=e, hypothesis=h,
    p_e_given_h=0.87,
    p_e_given_not_h=0.10,
    source_id="paper:smith2024:table3",
    rationale=(
        "Source: Smith 2024, Table 3 reports BF=8.7 for this endpoint. "
        "Anchor P(E|H)=0.87 chosen based on domain judgment; P(E|¬H) "
        "derived by division to preserve the reported ratio."
    ),
)
```

The derivation lives in `rationale` — a reviewable audit record. Kernel normalisations are never invoked.

### 11.6 Correlate patterns in compositions

Multi-step scientific pipelines — load a light curve, compute BLS power, compare to null model, then `infer(...)` — use compositions (§12), not a separate "evidence adapter" primitive. The composition ends in a Correlate verb (usually `infer`); its `conclusion` is that verb's helper Claim.

Example (full worked version in composition spec §7):

```python
@composition(name="gaia:evidence:gaussian_measurement", version="1.0")
def gaussian_measurement(evidence, hypothesis, *, mu_h, mu_not_h, noise):
    p_h     = compute(fn=_normal_density, inputs={"x": evidence, "mu": mu_h,     "noise": noise})
    p_not_h = compute(fn=_normal_density, inputs={"x": evidence, "mu": mu_not_h, "noise": noise})
    return infer(evidence=evidence, hypothesis=hypothesis,
                 p_e_given_h=p_h, p_e_given_not_h=p_not_h)
    # returns the infer's infer helper Claim
```

`associate` is symmetric in inputs and does not naturally appear at the *terminal* position of evidence-shaped compositions, but it can appear in observational-data compositions that wrap `@compute`-driven correlation analyses and conclude with `associate(...)`.

### 11.7 Provenance field set (final)

Kernel-consumed fields on any Correlate action (stored in `metadata` of the corresponding IR strategy):

- `source_id` — citation-level (paper, database, author)
- `data_id` — specific data instance
- `data_hash` — bytes-level hash; participates in `context_id` hashing
- `rationale` — human-readable justification, especially for literature-derived CPTs or association claims

**Not** kernel-consumed (unverifiable author assertions go to free `metadata` dict or to `IndependenceDeclaration.rationale`):

- `instrument_id` / `cohort_id` / `model_id` / `experiment_id` / `analysis_id` — authors may place them in `metadata` if desired; kernel does not interpret them.
- `assumptions: list[str]` — removed entirely. Assumptions become first-class Claims referenced via `background` (§13).
- `evidence_kind` discriminator — removed; only the CPT-pair path exists.
- `likelihood_ratio` / `bayes_factor` — removed; no LR-only storage.

When a Correlate action is the conclusion of a composition (§12), the multi-step computation that produced the numeric parameters is fully visible as the composition's `sub_knowledge` list; a separate `EvidenceComputationRecord` is not required.

### 11.8 Retired DSL helpers

Explicitly **not** part of the foundation kernel:

- `likelihood_ratio(evidence, hypothesis, lr=...)` — removed
- `bayes_factor(evidence, hypothesis, bf=...)` — removed
- `@evidence_adapter` as a separate decorator — **subsumed by `@composition` (§12)**
- A canonical evidence-adapter library (`gaussian_measurement_evidence`, `binomial_count`, etc., as free functions) — **subsumed by named composition templates**

Any author-facing tooling that accepts an LR / BF scalar must compile down to the `(p_e_given_h, p_e_given_not_h)` pair via explicit author-supplied anchoring (as in §11.5) — it cannot emit an LR-only IR node.

---

## 12. Composition — `ComposedAction` as a kernel primitive

**Decision: Gaia kernel establishes `ComposedAction` as a Knowledge subtype and commits to `@composition` as the single authoring mechanism for multi-step scientific reasoning. Concrete mechanics are defined in a dedicated design document:**

> **See `docs/specs/2026-04-24-gaia-composition-primitive-design.md`** for the full composition primitive design — `@composition` decorator semantics, sub-Knowledge namespace rules, `compute` → `infer` scalar-lifting mechanism, review-propagation rules, `CompositeStrategy` migration path, canonical `gaia.evidence` template set, and worked examples.

### 12.1 Why composition is a kernel primitive

Without a composition primitive, every scientific package flattens its natural multi-step workflows into an unnamed list of sibling actions. A "Gaussian measurement evidence" calculation is, structurally, `observe + compute(density|H) + compute(density|¬H) + infer`. Flattened, those four sub-actions lose their identity as a coherent unit: they cannot be reused under a name across packages, reviewers cannot accept/reject the workflow as a whole, and the kernel cannot tell a scientific pipeline apart from four unrelated actions.

Composition fixes this by letting authors declare: "this specific ordered graph of sub-actions is a named unit, identified by a template QID + version, reviewable as a whole or piecewise." v5's `CompositeStrategy` had the right IR shape for this but the DSL never exposed it cleanly. Pre-this-spec v6 dropped the compositional layer entirely. Foundation reintroduces it as a first-class Knowledge subtype.

The bar for "kernel primitive": **every scientific package will use composition** (every package has workflows) and **cross-package composability requires stable composition identity** (R4 review of a foreign composition needs to know what the composition is, not just what its flattened actions are). Both hold.

### 12.2 Foundation-level invariants

The detailed mechanics live in the companion composition-primitive design spec. Foundation commits to the following invariants about any implementation:

1. **`ComposedAction` is a Knowledge subtype**, sibling of `Strategy` and `Operator` in the §3.1 / §5 hierarchy — not a Strategy subtype.
2. **Identity is deterministic from contents, including output and execution order**: the composition's `_structure_hash` hashes `{template_name, template_version, conclusion, sub_knowledge}` where `sub_knowledge` preserves **execution order** (not sorted away). Two expansions with identical `(template_name, template_version, conclusion, ordered sub_knowledge)` collide on the same `knowledge_id` — correct behaviour for pure composition templates. Two expansions with same sub-set but different conclusions or different ordering produce different identities, which is also correct.
3. **Sub-Knowledge is any Knowledge kind**: `sub_knowledge: list[str]` accepts QIDs of Claims, Strategies, Operators, or nested ComposedActions. Not limited to strategies (unlike v5 `CompositeStrategy.sub_strategies`).
4. **Review propagation is hierarchical with override** (D2b): composition `accepted` defaults sub-Knowledge to accepted; sub-Knowledge may be individually rejected and that explicit rejection wins; composition `rejected` disables the whole.
5. **Cross-package R4 applies at composition level**: a foreign `ComposedAction` is `active` downstream iff (upstream accepted) AND (downstream accepted OR covered by a `TrustDelegation`), per §7.5. Sub-Knowledge statuses travel with the composition; downstream does not re-run R4 on each sub-action.
6. **Compositions honour the CallableRef-as-provenance invariant** (§4.8): sub-Knowledge `CallableRef`s are never invoked during default downstream inference, regardless of `--depth`. Only `gaia recompute` (§15.3) re-invokes them, point-by-point, under R4 review.

### 12.3 IR-level realisation

v5's `gaia/ir/strategy.py:CompositeStrategy` is **migrated** to `ComposedAction` as a Knowledge subtype (rename + promotion). The `_structure_hash` mechanism is preserved **in principle** (deterministic SHA-256 over canonical contents) but **updated in form**: the new hash includes `template_name` / `template_version` / `conclusion` and preserves `sub_knowledge` execution order — v5's sorted-sub-strategies convention was a convenience that under-specified composition identity. Migration details live in the composition spec (§3 of that document); foundation item §17 tracks it as a to-refactor work item.

### 12.4 Deprecated parallel concepts

- `@evidence_adapter` as a separate decorator — subsumed by `@composition`.
- A canonical evidence-adapter library as free functions — subsumed by `@composition`-decorated templates shipped in `gaia.evidence`.
- v5 compositional strategies (`case_analysis`, `induction`, `composite`, `mathematical_induction`) — become `@composition`-authored patterns, not new kernel primitives.

See §14.5 and §14.6 for the retraction statements.

## 13. Background premises on strategies

**Decision: `Derive`, `Compute`, and `Infer` all carry `background: list[str]`.**

### 13.1 What `background` is

`background` references Claims whose truth conditions the strategy depends on without their being the primary reasoning subject. For Infer: the `background` Claims are conditions under which the declared likelihood is valid.

BP lowering treats `background` Claims as conjoined conditions on the strategy's factor, i.e. the factor is active only when all `background` Claims are in their "true" state (Cromwell-clamped). In likelihood terms:

```text
P(E | H, B1, B2, …, I)  instead of  P(E | H, I)
```

### 13.2 Why this matters

Previously drafts proposed an `assumptions: list[str]` free-text field on `InferStrategy`. That field has four deficiencies:

- **Not reviewable** — free text has no ReviewTarget identity.
- **Not supportable by evidence** — no Claim-level ID to attach evidence to.
- **Not shareable** — 20 Infer actions repeating "Gaussian noise" each have 20 private strings.
- **Not traceable** — belief attribution cannot decompose by assumption.

Representing assumptions as Claims + `background` reference fixes all four. "Noise is Gaussian for run 042" becomes a Claim with its own `PriorSpec`, its own review target, and its own evidence chain. A package's shared assumptions (SI units, i.i.d. samples in trial 001, SIR model adequacy) live as package-level Claims that many strategies reference.

### 13.3 Relation to `Claim.background`

`Claim.background` (already in v6) and `Strategy.background` are distinct:

- `Claim.background` — context Claims that scope how the Claim's proposition is constructed.
- `Strategy.background` — context Claims that the specific reasoning act requires.

They do not merge. Both can be present on the same package.

---

## 14. Deprecations

### 14.1 `Setting`

`Setting` (v5 Knowledge type) is **deprecated from v0.5**. Its "formalised background, no probability" semantics is indistinguishable from a Claim with high prior and accepted `Observe`. Existing uses of `setting()` migrate to Claims or to Notes depending on whether they carry epistemic weight. Kernel type system drops the `"setting"` value from `Knowledge.type` enum in a migration step.

### 14.2 v5 reasoning strategies

The v5 strategy verbs (`deduction`, `abduction`, `elimination`, `case_analysis`, `induction`, `noisy_and`, `analogy`, `extrapolation`, `mathematical_induction`, `composite`) are **deprecated from v0.5**. The v6 verb set (`Derive`, `Observe`, `Compute`, `Infer`, `Equal`, `Contradict`, `Exclusive`, `not_`, `and_`, `or_`) plus the new `ComposedAction` composition primitive (§12) is the stable surface. Deprecation follows the standard schedule: warnings now, removal after one full minor release with the migrator shipped. v5 compositional strategies (`case_analysis`, `induction`, `composite`, `mathematical_induction`) are replaced by `@composition`-decorated user functions (§12.9), not by new kernel primitives.

### 14.3 `EvidenceMetadata.independence_group`

Removed. Use `IndependenceDeclaration` (§7).

### 14.4 `EvidenceMetadata` class

Dissolved into `InferStrategy` (§11). The *name* "EvidenceMetadata" is no longer a kernel type; the evidence contract is now a field set on `InferStrategy`.

### 14.5 `@evidence_adapter` decorator and the canonical evidence-adapter library

Earlier drafts of this foundation proposed a separate `@evidence_adapter` decorator and a library of canonical adapter functions (`gaussian_measurement_evidence`, `binomial_count`, `two_sample_comparison`, `from_bayes_factor`, `threshold_measurement`). These are **subsumed by `@composition` and the `gaia.evidence` composition-template library** (§12.7). There is exactly one composition decorator; evidence templates are one category of its use.

### 14.6 `CompositeStrategy` as a Strategy subtype

v5's `CompositeStrategy` in `gaia/ir/strategy.py` is **migrated to `ComposedAction` as a Knowledge subtype** (§12.8). Semantics preserved (`_structure_hash` mechanism, sub-list identity); position in the type hierarchy promoted from Strategy-subtype to Knowledge-subtype; field renamed `sub_strategies` → `sub_knowledge` with generalised QID acceptance.

---

## 15. Ecosystem integration rule

Restated from §3.2 as a named invariant:

> **Gaia owns scientific semantics; external Python packages provide computation below the semantic line through explicit adapters.**

```text
Libraries compute.
Gaia defines what the computation means.
```

Concrete rules:

- **Pint is the one exception** and enters via the `gaia.unit` core module (§3.2, §4.5). Every other ecosystem package is an optional adapter.
- Heavy ecosystem dependencies (PyMC, NumPyro, pyAgrum, Owlready2, Z3, scipy for distribution computation) are **never** imported at Gaia core load time. They are lazy-imported inside adapter functions.
- Adapter results are normalised into Gaia-native objects (`BeliefState`, `InferStrategy`, `MeasurementRecord`, `QuantityLiteral`) before crossing the kernel boundary.
- Adapter callables register as `CallableRef` so context reproducibility is maintained.
- `BeliefContext` records adapter identity (name, version) when an adapter produces results that end up in a `BeliefState`.

### 15.1 What the official registry already enforces

The `SiliconEinstein/gaia-registry` repository and its `register.yml` CI workflow (`https://github.com/SiliconEinstein/gaia-registry/.github/workflows/register.yml`) already implement a significant portion of what this foundation calls the publish-time contract. Any spec language that reads as "we will build X" should be interpreted against this baseline — much of it exists.

Enforced today by the registry CI on every PR that touches `packages/**`:

- **IR-hash integrity by recompile.** CI clones the upstream source at the declared `git_sha`, installs the pinned Gaia dependencies, runs `gaia compile .` in a clean sandbox, and fails the PR if the recomputed `ir_hash` disagrees with the `Versions.toml`-declared hash. Because the `CallableRef.source_hash` of every `ComputeStrategy` participates in `ir_hash`, any change to an author's Python callable body changes `ir_hash` and is caught here.
- **Tag-to-SHA pinning.** `Versions.toml` records `git_tag` and `git_sha`; CI verifies the tag still points to the pinned SHA.
- **Dependency closure.** Every Gaia dependency declared in `[project].dependencies` must already be registered in the registry; unregistered transitive dependencies block the PR.
- **Namespace.** Submitted packages must have `namespace == "github"` in their compiled IR.
- **UUID uniqueness.** The `trusted-gate` job refuses a PR whose `Package.toml` `uuid` is already claimed by a different package name.

Artefacts the registry currently ships per version:

```text
packages/<name>/Package.toml         (uuid, pypi_name, repo, description)
packages/<name>/Versions.toml        (per-version: ir_hash, git_tag, git_sha, registered_at,
                                      gaia_lang_version)
packages/<name>/Deps.toml            (per-version dependency edges)
packages/<name>/releases/<version>/  (release manifests including beliefs.json —
                                      exported-claim beliefs computed by `gaia register`)
```

The `beliefs.json` manifest is the current minimal form of what this foundation calls `BeliefState`. It carries `ir_hash` and the exported claims' posterior beliefs, and it is what downstream `collect_foreign_node_priors()` reads when injecting foreign priors under `gaia infer --depth 0`.

### 15.2 Publish-time contract (foundation-level)

Foundation extends the existing registry mechanism with normative additions rather than replacing it. Not all of these are enforced yet; where a gap exists, it is flagged as a registry-CI extension work item (§17).

**Invariant 1 — Upstream must ship computed results.** (α-hard.)
A registered package must ship not only its source and IR but also the inference results its own `gaia register` produced. The `beliefs.json` manifest satisfies this for exported Claims today; the foundation target is to extend it into a `belief_state.json` that carries the full `BeliefState` schema (context_id, diagnostics, generated_at, belief_state_hash, method).

**Invariant 2 — Registry CI verifies IR-result consistency.**
The current registry CI verifies `ir_hash` via recompile but does not re-run inference to verify the shipped beliefs. Foundation extends this:
- Registry CI should additionally re-run `gaia infer` in the sandbox and confirm the recomputed `belief_state.context_id` matches the declared one (registry-CI extension, §17).
- Because `ir_hash` determines the inference inputs (IR + prior records + review manifest), the `context_id` should be a deterministic function of them; mismatch indicates author-side tampering or a non-determinism bug in the inference engine.

**Invariant 3 — Downstream consumes results, does not re-execute.** (Default path.)
Downstream `gaia infer` (any `--depth`) consumes the upstream-shipped `beliefs.json` / `belief_state.json` as authoritative. Upstream `CallableRef`s are **not invoked** during downstream inference; their role is provenance only (§4.8).

- `--depth 0` (`flat_beliefs`): downstream uses upstream Claim posteriors as priors for foreign node references.
- `--depth N` (`joint_graph`, N ≥ 1): downstream merges upstream IR topology and upstream's **already-baked** factor parameters (the inline `IrStrategy.conditional_probabilities` on each merged Strategy, plus each foreign Claim's `metadata["prior"]`) into its own factor graph. BP propagates over the merged graph using the baked values. No upstream `CallableRef` is invoked.

**Invariant 4 — Stale upstream is refused, not silently tolerated.**
When downstream reads an upstream artefact whose `ir_hash` disagrees with the Versions.toml-declared hash, downstream `gaia infer` fails rather than proceeding with stale data. No escape hatch. The only way to proceed is to resolve the inconsistency upstream (re-register the package after fixing) or explicitly bump to a newer version.

### 15.3 The replication path — `gaia recompute`

Re-executing upstream `CallableRef`s — re-running a `@compute` function, re-evaluating an adapter hook, re-invoking a custom `DistributionSpec` — is an **explicit, opt-in, point-by-point** operation, scoped into its own CLI command that will be introduced separately:

```bash
gaia recompute --callable github:pkgA::action::density_fn
gaia recompute --package github:pkgA@1.2.3 --callable-kind compute
```

This is where the actual cross-package code-safety review model lives. Under R4 (§7.5), each re-executed `CallableRef` requires a per-callable accepted `ReviewTarget` in the downstream package's manifest. A `TrustDelegation` covering the upstream package may cover it in bulk, subject to the delegation's own review.

Default behaviour on unreviewed callable during recompute: **abort**. Recompute is a strict, scripted operation; silent skipping is wrong for an operation whose whole purpose is re-verification. Day-to-day `gaia infer` (the default path) is unaffected and runs no upstream code regardless of review status (§15.2, Invariant 3).

`gaia recompute` is expected to be expensive (scientific `@compute` may require supercomputers), rare (replication studies are the exception, not the rule), and risky (remote code execution). The design accordingly keeps it out of any default flow.

---

## 16. Relationship to existing documents

### 16.1 Supersedes

- `docs/ideas/foundation-specs/scientific-formal-language-foundation-spec.md` — scope too broad; Gaia does not aim to be a full scientific formal language.
- `docs/ideas/foundation-specs/jaynes-probability-logic-backend-foundation-spec.md` — scope close but missed the three-layer distinction and mismapped several objects to kernel vs adapter.

These drafts should be moved to `docs/archive/` or marked clearly as historical.

### 16.2 Consistent with

- `docs/specs/2026-04-21-gaia-lang-v6-design.md` — foundation is compatible with the v6 DSL's objects and verbs. This foundation's changes are primarily additive (PriorSpec, IndependenceDeclaration, TrustDelegation, `Strategy.background`) or clarifying (three-layer probability semantics, CallableRef-as-provenance invariant, inline-only parameter model).
- `docs/specs/2026-04-21-gaia-ir-v6-design.md` — IR changes required by this spec are listed in §17.
- `docs/foundations/theory/` — theory layer untouched.
- `docs/foundations/gaia-ir/` — protected layer; any IR schema change flows through a separate change-controlled PR (per CLAUDE.md rules).

### 16.2.1 U1 runtime refactor — independent work item

v0.5 HEAD's `gaia/lang/runtime/action.py` declares `Action` as **parallel to `Knowledge`, not a subclass of it**. The U1 decision in this foundation — that `Strategy` and `Operator` are subtypes of `Knowledge` — is a **reversal of that choice**.

This reversal is a scoped runtime refactor, not a side-effect of any functional PR:

- `gaia/lang/runtime/action.py` rewrites `Action`, `Strategy`, `Operator` as `Knowledge` subclasses.
- `gaia/lang/runtime/knowledge.py` adds `review_status: ReviewStatus | None` to the base.
- `gaia/ir/strategy.py` and `gaia/ir/operator.py` adjust discriminated-union tagging to share the `Knowledge.kind` field.
- `gaia/lang/compiler/compile.py` consolidates the action-vs-knowledge dispatch.
- Extensive test updates across `tests/gaia/lang/` and `tests/gaia/ir/`.

The release plan **MUST** allocate a dedicated PR for this refactor. Mixing it into a functional PR is prohibited — the change touches enough surface that bundling would make review impractical.

### 16.3 Partially supersedes

- `docs/ideas/gaia-upgrade-specs/` — several idea-stage release specs under this directory proposed designs that diverge from the decisions here (notably the sidecar `EvidenceMetadata`, string-tag `independence_group`, and first-class `ExperimentRef`). Those release specs need rewriting against this foundation before they can be promoted out of `docs/ideas/`.

---

## 17. Summary of required IR / schema / runtime changes

Not an implementation plan, but the concrete diffs this spec implies. Each item is tagged against **v0.5 HEAD** reality:

- `[implemented]` — the item is already present in v0.5; foundation spec merely names / normatively describes it.
- `[to-refactor]` — partial v0.5 support; needs restructuring or extension.
- `[new]` — nothing in v0.5 corresponds; fresh schema / module / CLI.
- `[retracted]` — listed in earlier drafts of this §17 but never existed in v0.5 in the assumed form; foundation no longer requires the change.

IR schema changes belong in change-controlled PRs against `docs/foundations/gaia-ir/` (protected layer per CLAUDE.md).

### 17.1 Kernel schema

1. **`[new]`** Add `PriorSpec` schema (§6). `Claim.prior` accepts `PriorSpec | float | None`; float auto-wraps to `PriorSpec(value=..., policy="default")`. v0.5 currently stores a bare float in `Knowledge.metadata["prior"]`.
2. **`[to-refactor]`** `Knowledge.type == "setting"` is still a supported value in v0.5 (`gaia/lang/dsl/knowledge.py:setting()` is live; IR accepts `type="setting"`). Deprecate from v0.5, drop from the enum after migrator ships.
3. **`[implemented]`** `background: list[str] | None` is already on `Strategy` at IR layer (`gaia/ir/strategy.py:146`) and on `Action` at runtime. Foundation adds a normative description (§13) but no schema change.
4. **`[new]`** Add `MeasurementRecord`, `DistributionSpec`, `CallableRef` pydantic schemas (§4.5 / §4.6 / §4.8). Attach `MeasurementRecord` via `Knowledge.metadata["measurement"]` with schema-validated read.
5. **`[new]`** Add `QuantityLiteral` schema (`{value: float, unit: str}`) as the IR serialisation carrier for unit-bearing values. Record the literal-hash invariant (§4.5): Claim identity and `context_id` hash the literal `{value, unit}` bytes; no unit canonicalisation at hash time. Every IR site that carries a unit (`MeasurementRecord.observed_value`, `DistributionSpec.params`, parameterised `Claim` parameters) uses `QuantityLiteral`.
6. **`[new]`** Define foundation-level well-known key on `IrStrategy.metadata` for `type == "infer"` (§11.1, §11.7):
   - `metadata["evidence"]` = `{source_id, data_id, data_hash, rationale}`

   No new top-level fields on `IrStrategy` itself; the existing inline `conditional_probabilities` already carries `[P(E|¬H), P(E|H)]`. **No separate `EvidenceComputationRecord` sidecar**: when an Infer's CPT is adapter-produced (e.g., from a `gaussian_measurement` composition), the adapter sits inside a `@compute` sub-action of the enclosing `ComposedAction`, and its `CallableRef` lives on that sub-action — the composition's `sub_knowledge` trace IS the adapter provenance.
7. **`[retracted]`** ~~Dissolve `EvidenceMetadata` pydantic class. Inline fields into `InferStrategy` (discriminated union).~~ The class never existed in v0.5 (it was proposed in GPT Pro's v0.6 idea draft). The foundation's final §11 model is CPT-pair-only with no discriminator; v0.5's inline `conditional_probabilities` is the kernel shape.
8. **`[retracted]`** ~~Remove `EvidenceMetadata.independence_group`.~~ Never existed in v0.5. Independence is expressed via `IndependenceDeclaration` in the review layer (§7).
9. **`[retracted]`** ~~Remove free-text `assumptions` from strategies.~~ v0.5's `Infer` action has no `assumptions` field; `background` is the only assumption-carrying mechanism and it is already Claim-list-based.

### 17.2 U1 — unified Knowledge hierarchy

10. **`[to-refactor]`** U1 runtime refactor (see §16.2.1). v0.5's `gaia/lang/runtime/action.py` declares `Action` as "parallel to Knowledge, not a Knowledge subclass". U1 reverses this: `Action` (and therefore `Strategy`, `Operator` and all their subtypes) become subtypes of `Knowledge`. Adds `review_status: ReviewStatus | None` as an optional field on the base. Dedicated refactor PR; must not be bundled with a functional change.
11. **`[to-refactor]`** IR-side U1: `gaia/ir/strategy.py` and `gaia/ir/operator.py` adjust their pydantic shape so `Strategy` and `Operator` share the `Knowledge.kind` discriminator. No field removal; add `kind` tagging so serialised IR distinguishes subtypes via a single field.

### 17.2a Composition primitive — v0.5 landing

11a. **`[new]` / `[to-refactor]`** Implement the composition primitive per **`docs/specs/2026-04-24-gaia-composition-primitive-design.md`**. Scope (summary, not authoritative — see that doc):
    - Add `ComposedAction` as a Knowledge subtype (runtime + IR).
    - Migrate v5 `CompositeStrategy` → `ComposedAction` (promote from Strategy-subtype to Knowledge-subtype; rename `sub_strategies` → `sub_knowledge`; accept any Knowledge QID; replace sorted-sub-strategies hash with `{template_name, template_version, conclusion, ordered sub_knowledge}` hash).
    - Add `@composition` decorator with scoped capture semantics.
    - Allow `infer()` to accept `float | Claim` for CPT fields; compiler lifts Claim.value at compile time.
    - Compiler validation of sub-Knowledge references; reverse-pointer `metadata["composition_id"]` on each sub-Knowledge.
    - BP lowering hierarchical-with-override review propagation.
    - Ship `gaia.evidence` core module with the agreed canonical template set.

    Composition is a **v0.5 deliverable**, not a parked v1.x extension. Specific schemas, decorator runtime behaviour, validator rules, canonical template signatures, migration steps, and worked examples all live in the composition design doc; foundation tracks the overall work item here.

11b. **`[to-refactor]`** Fix the `infer()` DSL return value. v0.5 HEAD's canonical v6-style implementation in `gaia/lang/dsl/infer_verb.py` already generates a helper Claim — currently tagged `helper_kind="statistical_support"`, foundation now specifies `"likelihood"` (§11.2, matching the Relate-family naming convention of using the *relation noun* as the kind tag) — and attaches it to the `Infer` action's `helper` field (present in `gaia/lang/runtime/action.py:Infer`). But the function **returns `evidence` instead of `helper`** (see `infer_verb.py:88`). The fix: rename `helper_kind` to `"likelihood"` in `infer_verb.py:74`, and change the return value to `helper` on `infer_verb.py:88`. The legacy v5-style `infer()` in `gaia/lang/dsl/strategies.py` stays as it is (it is already marked deprecated via the v5-strategy-deprecation work item). The Relate-verb pattern — not the Support-verb pattern — is the right analogy for `infer`'s semantics: both inputs (E and H) are pre-existing, so the action's semantic output is the generated relation helper, not one of the inputs. This is a prerequisite for the composition primitive (item 11a) and for the Correlate family unification (items 11c / 11d).

11c. **`[new]`** Introduce the Correlate action family per §11. Add abstract base class `Correlate(Action)` in `gaia/lang/runtime/action.py`. Migrate `Infer` to subclass `Correlate` (from current direct `Action` subclass). This creates a shared home for shared concerns across probabilistic 2-Claim actions — parameter validation, `gaia check` hooks, audit metadata conventions — without altering existing Infer semantics.

11d. **`[new]`** Add `associate()` DSL function + `Associate(Correlate)` runtime dataclass + `AssociateStrategy` IR node (§11.4). DSL: `associate(a, b, *, p_a_given_b, p_b_given_a, prior_a=None, prior_b=None, background, rationale, label) -> Claim`. Runtime: `Associate` inherits from `Correlate` with `a`, `b`, `p_a_given_b`, `p_b_given_a`, `prior_a`, `prior_b`, `helper` fields. DSL returns a generated helper Claim with `metadata["helper_kind"] = "association"`. IR lowering: `type="associate"`, `premises=[A_qid, B_qid]` (no directional premise/conclusion split — both symmetric premises), the two conditionals stored in a dedicated schema field. BP factor lowering: 2×2 symmetric factor, parameters derived from `(p_a_given_b, p_b_given_a)` plus marginals obtained via graph closure (`gaia check` validates coherence; see item 11e). Optional `prior_a` / `prior_b` contribute to the prior-provider graph for A and B as additional sources, source-tagged `"from:{associate_action_qid}"`. Similarly, `infer()` accepts optional `prior_hypothesis` / `prior_evidence` arguments that contribute to the hypothesis's / evidence's prior-provider graph (§11.2); this is an authoring ergonomics feature, not a separate mechanism — the soft-constraint model treats all prior providers uniformly.

11e. **`[new]`** Extend `gaia check` to report factor-graph coherence for any probabilistic factor (Infer, Associate, and future Correlate / Causal members). Three outcomes to surface:
    - **Hole** — factor parameter has no provider (no constraint path supplies the needed marginal or joint entry). Hard error.
    - **Redundant** — factor parameter has multiple providers whose values agree (Bayes-consistent). Informational: author should confirm intentional over-specification.
    - **Conflict** — factor parameter has multiple providers whose values disagree (Bayes-violation or numerical conflict). Hard error.

    This is a **general** responsibility, not `associate`-specific — the same three categories apply to any factor where multiple constraints may collide (two `infer` actions on the same hypothesis pair, explicit `prior=` plus implied marginal from a correlate action, etc.).

### 17.3 Review / R4

12. **`[to-refactor]`** v0.5 `ReviewManifest` (`gaia/ir/review.py`) already supports `target_kind ∈ {"strategy", "operator", "knowledge"}` and keys by `target_id` (QID). Under U1 (item 10), collapse `target_kind` so all targets are `knowledge` (since strategies and operators are now Knowledge subtypes). Existing `Review` schema otherwise stays.
13. **`[new]`** Add `IndependenceDeclaration` as a relation-level `ReviewTarget` (§7.2). Fields: `target_id` (QID), `factors: list[str]` (knowledge_ids of N InferStrategies), `kind ∈ {identical, independent, correlated, partial}`, `rationale`, inherited `status`. v1.x-only BP handling for `correlated` / `partial`; v0.x implements `identical` and `independent`.
14. **`[new]`** Add `TrustDelegation` as a relation-level `ReviewTarget` (§7.5). Fields: `package`, `version` (single pinned string, no ranges), `scope ∈ {all_knowledge, exclude_compute, claims_only}`, `rationale`, inherited `status`. Cross-author / cross-version bulk trust is not supported.
15. **`[new]`** Implement the R4 effective-status resolver (§7.5): for foreign Knowledge references, compute `effective(K for B)` from `upstream_status`, `local_status`, and any applicable `TrustDelegation`. Upstream `rejected` is a hard veto; downstream silence is `inactive`.

### 17.4 `gaia.unit` / `gaia.stats` / `gaia.constants` core modules

16. **`[new]`** Add `gaia.unit` as a core module wrapping Pint with a shared `UnitRegistry` singleton plus `to_literal` / `from_literal` bridges to `QuantityLiteral` (§4.5). Pint becomes a core dependency of `gaia-lang` (update `pyproject.toml`). Kernel code itself still does not import Pint — the dependency is scoped to `gaia.unit`.
17. **`[new]`** Add `gaia.stats` as a core module (§4.6): (a) named constructors for the 8 built-in distributions (`Normal`, `Lognormal`, `StudentT`, `Cauchy`, `Binomial`, `Poisson`, `Exponential`, `Beta`) returning `DistributionSpec`; (b) registry metadata (param schemas); (c) `from_callable(...)` helper producing `DistributionSpec(kind="custom", callable_ref=...)`. Does **not** import scipy at load time.
18. **`[new]`** Add `gaia-lang[stats]` optional-extras dependency group that pulls scipy. Provide `gaia/adapters/stats/scipy_adapter.py` that dispatches `DistributionSpec` by `kind` to `scipy.stats`, or resolves `CallableRef` for `kind="custom"`. Evidence adapters (Gaussian measurement, Binomial, etc.) lazy-import this.
19. **`[new]`** Add `gaia.constants` as a core module re-exporting Pint's built-in physical constants with Gaia-preferred names and short aliases (`c`, `h`, `k_B`, `G`, `N_A`, etc.). No new schema, no new dependency.
20. **`[new]`** Add `DistributionSpec` validator: built-in `kind` disallows `callable_ref`; `kind="custom"` requires it.

### 17.5 CLI / registry

21. **`[new]`** Introduce `gaia recompute` CLI (§15.3) — explicit, opt-in, point-by-point re-execution of `CallableRef`s. R4-gated; default abort on unreviewed; version-pinned. This is the **only** operation that resolves a `CallableRef` in the entire system (§4.8).
22. **`[implemented]`** Registry `ir_hash` recompile verification (§15.1). Already performed by `SiliconEinstein/gaia-registry/.github/workflows/register.yml`; foundation names it, does not build it.
23. **`[implemented]`** `beliefs.json` manifest per release with exported-claim beliefs and `ir_hash` (§15.1). Produced by `gaia register` (`gaia/cli/commands/register.py`), shipped to registry, consumed by downstream `collect_foreign_node_priors()`.
24. **`[new]`** Extend `beliefs.json` to the full `belief_state.json` schema (§15.2, Invariant 1): add `context_id`, `diagnostics`, `generated_at`, `belief_state_hash`, `method`. Existing consumers keep reading the subset they need; new fields are additive.
25. **`[new]`** Registry CI extension (§15.2, Invariant 2): re-run `gaia infer` in the sandbox after the existing recompile step; confirm recomputed `context_id` matches the declared one. Reject PRs on mismatch.
26. **`[new]`** Downstream `gaia infer` rejects stale upstream (§15.2, Invariant 4): when reading a foreign `beliefs.json` / `belief_state.json`, compare declared `ir_hash` to the upstream-shipped `ir_hash`; abort with no escape hatch if inconsistent.

### 17.6 Deprecations (documentation-only; mechanism already deprecated in code)

27. **`[implemented]`** `gaia/cli/_reviews.py` (review sidecar) marked deprecated since 0.4.2. Foundation does not re-introduce sidecar records; the replacement is the inline-only model (§3.1, §5). Legacy types `PriorRecord` / `StrategyParamRecord` / `ParameterizationSource` / `ResolutionPolicy` stay for backward compatibility, do not appear in foundation inventory.
28. **`[implemented]`** `gaia/ir/validator.py:validate_parameterization` is never called in the active code path. Foundation does not rely on it. A cleanup PR may remove it, but that is not a foundation-level requirement.

---

## 18. Open points for follow-up design

These are intentionally unresolved; the foundation records them as out-of-scope for the current round and names where they will be picked up.

- **Migration details for v5 → v6 strategies and `Setting`.** Handled by a separate migrator spec. §17 item 2 names the schema-level drop; the actual rewrite tool is out of scope here.
- **Multi-source parameterisation.** Gaia v0.5 went inline-only after deprecating the sidecar record mechanism. If real users later need "this prior was computed by A, refined by B, curated by C" with timestamped history, that is a fresh design decision — not a continuation of the deprecated `PriorRecord` / `StrategyParamRecord` sidecar.
- **Categorical / continuous latent variables.** Parked at v1.x+; requires BP-layer extension.
- **First-class `ModelRecord`, `DatasetRef`, `ExperimentRef`.** Parked at v1.x+; triggered by real-user audit needs. Currently authors capture this in `rationale` text and `metadata` dict entries.
- **MaxEnt solver adapter.** Parked at v1.x+; `PriorSpec.policy="maxent"` tag is the present-day contract (§6).
- **External theorem prover integration (Z3 / Lean).** Parked at v1.x+; requires Claim-proposition structuralisation first (§10).
- **PPL adapter (PyMC / NumPyro).** Parked at v1.x+; predictive enters via `PriorSpec.policy="external_predictive"` tag in the meantime (§9).
- **`TrustDelegation` revocation.** §7.5 defines delegation acceptance and scope but does not specify revocation behaviour when a previously-trusted upstream version is later compromised. Likely follow-up: a `revoke` entry in the downstream manifest that disables a prior `TrustDelegation`'s effect. Revocation is registry-layer work and parked until the registry has a signing / attestation story.
- **Unit registry versioning in `context_id`.** §4.5 hashes `{value, unit}` literally and does not encode the Pint version that interpreted the unit names. If cross-Pint-version reproducibility becomes a concern, extend `QuantityLiteral` to carry `unit_registry` and `unit_registry_version` per the CallableRef pattern (foreshadowed in earlier design discussion; not required now).
- **Physical-constants versioning.** §4.7 lets `gaia.constants` track Pint's CODATA release passively. If constant-value drift across CODATA revisions needs to be pinnable for replication, this becomes the same version-tag extension as above.
- **Causal action family (v1.x+).** Gaia's current probabilistic kernel (Correlate family, §11) handles **observational** relations only: `infer` for directional likelihood, `associate` for symmetric correlation. **Interventional** semantics — Pearl's do-calculus, counterfactual reasoning, causal-graph inference — would form a fourth Causal family with its own helper Claim kinds (`do_intervention_result`, `counterfactual_result`, etc.) and its own BP factor semantics. Under the current binary-claim factor-graph BP, interventional inference requires additional machinery (causal graph structure beyond factor graphs, do-notation). Parked until (a) a concrete scientific package requests it, and (b) the causal-graph machinery design is worked out. Expected to parallel Correlate architecturally: `Causal(Action)` abstract base with named causal verbs as subclasses, each returning a dedicated helper Claim kind.

---

## 19. Acceptance of this foundation

This spec is considered the canonical foundation when:

- All kernel objects in §5 have pydantic schemas with versioned `schema_version`.
- The three-layer naming discipline (§4.3) is reflected in code, docs, and audit output.
- The IR changes in §17 are either implemented or tracked as explicit work items.
- The idea-stage foundation drafts under `docs/ideas/foundation-specs/` are archived.
- The release plan (a separate document) is rewritten against this foundation.

---

## 20. One-line invariant, restated

> **Gaia evaluates `P(Claim | Context)` on binary-proposition factor graphs, with evidence entering through reviewed likelihood factors, measurement noise handled in adapter space, and every ambition beyond that boundary kept outside the kernel.**
