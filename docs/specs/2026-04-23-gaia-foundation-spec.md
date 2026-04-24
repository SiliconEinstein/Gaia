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

Kernel is organised around **a single unified `Knowledge` type hierarchy**. Every declarable, QID-identified, cross-package-referenceable, reviewable object is a `Knowledge`. Prior-holding (`Claim`), annotative (`Note`, `Question`), reasoning-move (`Strategy` and its subtypes), and relational (`Operator` and its subtypes) objects are **subtypes of `Knowledge`**, not parallel hierarchies.

This unification is normative at both the **Gaia Lang (runtime)** layer and the **Gaia IR (serialisation)** layer. See §5 for the full inventory and §16 for the runtime/IR refactor this implies.

**Knowledge hierarchy**

```text
Knowledge                (QID + provenance + metadata + optional review_status)
  ├── Claim              (prior-bearing; binary BP variable; parameterised via class-as-predicate)
  ├── Note               (text annotation; not in BP)
  ├── Question           (inquiry lens; not in BP)
  ├── Strategy           (directional reasoning move)
  │   ├── DeriveStrategy
  │   ├── ObserveStrategy
  │   ├── ComputeStrategy
  │   └── InferStrategy
  └── Operator           (relational constraint / propositional combinator)
      ├── EqualOperator
      ├── ContradictOperator
      ├── ExclusiveOperator
      ├── NegationOperator        (not_)
      ├── ConjunctionOperator     (and_)
      └── DisjunctionOperator     (or_)
```

**Belief** lives only on `Claim` (via `PriorSpec`, see §6). Strategy and Operator do not carry prior; they are declared reasoning or relational structure, not propositions about the world. **Review status** (`accepted / unreviewed / rejected`) is an optional field on any `Knowledge`.

**Review layer (the qualitative gate)**

- `ReviewManifest` — collection of `ReviewTarget`s keyed by `knowledge_id` (QID). Supports single-knowledge targets and relation-level targets (e.g., `IndependenceDeclaration`, see §7).
- `ReviewStatus` — `accepted / unreviewed / rejected`. Never a probability.

**Context layer (the information state)**

- `BeliefContext` — information state `I` used by inference; carries `context_id` (canonical SHA-256 over inputs).
- `BeliefState` — posterior output `P(Claim | I)` plus provenance. Published artefact at `.gaia/belief_state.json` — see §13 publish-time contract.
- `ContextLock` — reproducibility artefact.

**Evidence / measurement schema (the bridge to the world)**

- `InferStrategy` fields — `p_e_given_h`, `p_e_given_not_h` (both required), plus provenance `source_id` / `data_id` / `data_hash`. See §11 for the full field set and the reasoning behind requiring the CPT pair.
- `StrategyParamRecord` — optional sidecar for external parameter updates (adapter-computed, curation, review). Keyed by `strategy_id`; latest record wins. Parallels `PriorRecord` for claim priors.
- `MeasurementRecord` — schema for observed-value + noise specification.
- `DistributionSpec` — structured probability-distribution spec (`kind`, `params`, optional `CallableRef`). Used wherever a distribution enters IR (measurement noise, future prior shapes, etc.). Replaces the previously-named `ErrorModelSpec`.

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
from gaia.unit import q
from gaia.stats import Normal

reading = measurement_claim(
    "Spectrometer produced reading 5120 K",
    observed_value=q(5120, "K"),
    noise=Normal(sigma=q(80, "K")),
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

---

## 5. Kernel object inventory

Canonical set (pydantic schemas). Versioned via `schema_version: Literal["gaia.<name>.v1"]`.

**Knowledge hierarchy** — every declarable QID-identified object is a `Knowledge`. Belief-bearing is only `Claim`; reasoning moves are `Strategy` subtypes; relational / propositional combinators are `Operator` subtypes. Same hierarchy at Gaia Lang (runtime) and Gaia IR (serialisation) layers; see §5.x "Lang ↔ IR mapping" below.

```text
Knowledge (base — QID + provenance + metadata + optional review_status)
  ├── Claim              (prior-bearing; binary BP variable; parameterisable)
  ├── Note               (free text; no BP)
  ├── Question           (inquiry lens; no BP; may carry targets)
  ├── Strategy           (directional reasoning move; premises + conclusion + background)
  │   ├── DeriveStrategy       (type="deduction")
  │   ├── ObserveStrategy      (type="deduction", pattern="observation")
  │   ├── ComputeStrategy      (type="deduction", compute={...} + CallableRef)
  │   └── InferStrategy        (type="infer"; p_e_given_h + p_e_given_not_h; see §11)
  └── Operator           (relational / propositional combinator; variables + conclusion)
      ├── EqualOperator
      ├── ContradictOperator
      ├── ExclusiveOperator
      ├── NegationOperator         (not_)
      ├── ConjunctionOperator      (and_)
      └── DisjunctionOperator      (or_)
```

**Sidecar records** — parameterisation and prior updates live in separate records keyed by `knowledge_id` / `strategy_id`. Matches the established `priors.py` pattern; allows multi-source, timestamped parameter evolution without invalidating upstream Knowledge identity.

```text
PriorRecord            — per-Claim prior updates (value, source_id, justification, created_at)
StrategyParamRecord    — per-Strategy parameter updates
                         (for InferStrategy: [p_e_given_not_h, p_e_given_h])
                         (for noisy_and etc.: type-specific parameter lists)
```

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
BeliefState              — posterior output P(Claim | I); published artefact per §13
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

- **Pint is the one exception** and enters via the `gaia.unit` core module (§3.2, §4.5). Every other ecosystem package is an optional adapter.
- Heavy ecosystem dependencies (PyMC, NumPyro, pyAgrum, Owlready2, Z3, scipy for distribution computation) are **never** imported at Gaia core load time. They are lazy-imported inside adapter functions.
- Adapter results are normalised into Gaia-native objects (`BeliefState`, `InferStrategy`, `MeasurementRecord`, `QuantityLiteral`) before crossing the kernel boundary.
- Adapter callables register as `CallableRef` so context reproducibility is maintained.
- `BeliefContext` records adapter identity (name, version) when an adapter produces results that end up in a `BeliefState`.

---

## 15. Relationship to existing documents

### 15.1 Supersedes

- `docs/ideas/foundation-specs/scientific-formal-language-foundation-spec.md` — scope too broad; Gaia does not aim to be a full scientific formal language.
- `docs/ideas/foundation-specs/jaynes-probability-logic-backend-foundation-spec.md` — scope close but missed the three-layer distinction and mismapped several objects to kernel vs adapter.

These drafts should be moved to `docs/archive/` or marked clearly as historical.

### 15.2 Consistent with

- `docs/specs/2026-04-21-gaia-lang-v6-design.md` — foundation is compatible with the v6 DSL's objects and verbs. This foundation's changes are primarily additive (PriorSpec, IndependenceDeclaration, TrustDelegation, StrategyParamRecord formalisation, `Strategy.background`) or clarifying (three-layer probability semantics, CallableRef-as-provenance invariant).
- `docs/specs/2026-04-21-gaia-ir-v6-design.md` — IR changes required by this spec are listed in §16.
- `docs/foundations/theory/` — theory layer untouched.
- `docs/foundations/gaia-ir/` — protected layer; any IR schema change flows through a separate change-controlled PR (per CLAUDE.md rules).

### 15.2.1 U1 runtime refactor — independent work item

v0.5 HEAD's `gaia/lang/runtime/action.py` declares `Action` as **parallel to `Knowledge`, not a subclass of it**. The U1 decision in this foundation — that `Strategy` and `Operator` are subtypes of `Knowledge` — is a **reversal of that choice**.

This reversal is a scoped runtime refactor, not a side-effect of any functional PR:

- `gaia/lang/runtime/action.py` rewrites `Action`, `Strategy`, `Operator` as `Knowledge` subclasses.
- `gaia/lang/runtime/knowledge.py` adds `review_status: ReviewStatus | None` to the base.
- `gaia/ir/strategy.py` and `gaia/ir/operator.py` adjust discriminated-union tagging to share the `Knowledge.kind` field.
- `gaia/lang/compiler/compile.py` consolidates the action-vs-knowledge dispatch.
- Extensive test updates across `tests/gaia/lang/` and `tests/gaia/ir/`.

The release plan **MUST** allocate a dedicated PR for this refactor. Mixing it into a functional PR is prohibited — the change touches enough surface that bundling would make review impractical.

### 15.3 Partially supersedes

- `docs/ideas/gaia-upgrade-specs/` — several idea-stage release specs under this directory proposed designs that diverge from the decisions here (notably the sidecar `EvidenceMetadata`, string-tag `independence_group`, and first-class `ExperimentRef`). Those release specs need rewriting against this foundation before they can be promoted out of `docs/ideas/`.

---

## 16. Summary of required IR / schema changes

Not an implementation plan, but the concrete diffs this spec implies for the IR layer. These belong in follow-up change-controlled PRs against `docs/foundations/gaia-ir/`.

1. Add `PriorSpec` schema. `Claim.prior` accepts `PriorSpec | float | None`; float is auto-wrapped.
2. Drop `Knowledge.type == "setting"` (post-migration).
3. Dissolve `EvidenceMetadata` pydantic class. Inline fields into `InferStrategy` (discriminated union).
4. Add `background: list[str]` to `IrStrategy` base (affects `DeriveStrategy`, `ComputeStrategy`, `InferStrategy`).
5. Add `MeasurementRecord` / `DistributionSpec` / `CallableRef` schemas. Attach `MeasurementRecord` via `Knowledge.metadata["measurement"]` with schema-validated read. (`DistributionSpec` replaces the previously-named `ErrorModelSpec`; see §4.6.)
6. Extend `ReviewManifest` to support relation-level targets (`IndependenceDeclaration`). Schema migrates from `{action_label: status}` to `{target_id: {kind, action_labels, status, rationale}}`.
7. Remove `EvidenceMetadata.independence_group`.
8. Remove free-text `assumptions` anywhere it appears on strategies.
9. Add `QuantityLiteral` schema to the kernel (`{value: float, unit: str}`; 2-field pydantic carrier). Record the literal-hash invariant (§4.5): Claim identity and `context_id` hash the literal `{value, unit}` bytes; no unit canonicalisation at hash time. Every IR site that carries a unit (`MeasurementRecord.observed_value`, `DistributionSpec.params`, parameterised `Claim` parameters) uses `QuantityLiteral`.
10. Add `gaia.unit` as a core module of `gaia-lang`, wrapping Pint with a shared `UnitRegistry` singleton plus `to_literal` / `from_literal` bridges to `QuantityLiteral`. Pint becomes a core dependency (formerly listed as optional extras). Kernel code itself still does not import Pint — the dependency is scoped to `gaia.unit`. Update `pyproject.toml` accordingly.
11. Rename kernel schema `ErrorModelSpec` → `DistributionSpec` (§4.6). Generalise to be the IR carrier for any distribution, not only measurement noise. Add kind-vs-callable-ref validator: built-in `kind` disallows `callable_ref`; `kind="custom"` requires it.
12. Add `gaia.stats` as a core module of `gaia-lang`. Contains (a) named constructors for the 8 built-in distributions (`Normal`, `Lognormal`, `StudentT`, `Cauchy`, `Binomial`, `Poisson`, `Exponential`, `Beta`) that return `DistributionSpec`; (b) the registry metadata (param schemas); (c) `from_callable(...)` helper producing `DistributionSpec(kind="custom", callable_ref=...)`. `gaia.stats` does **not** import scipy at load time.
13. Add `gaia-lang[stats]` optional-extras dependency group that pulls scipy. Provide `gaia/adapters/stats/scipy_adapter.py` that dispatches `DistributionSpec` by `kind` to `scipy.stats`, or resolves `CallableRef` for `kind="custom"`. Evidence adapters (Gaussian measurement evidence, Binomial evidence, etc.) lazy-import this adapter when they need to evaluate a spec.
14. Add `gaia.constants` as a core module re-exporting Pint's built-in physical constants with Gaia-preferred names and the short-form aliases (`c`, `h`, `k_B`, `G`, `N_A`, etc.). No new schema, no new dependency (Pint already core); constants are named `Quantity` instances. See §4.7.

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
