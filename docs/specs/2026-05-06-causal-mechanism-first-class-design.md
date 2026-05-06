# Causal Reasoning Design — Mechanism as First-Class Knowledge

> **Status:** Target design (proposal)
> **Date:** 2026-05-06
> **Scope:** Introduce `Mechanism` as a first-class `KnowledgeType` in Gaia IR; build DAG queries, `do()` interventions, and optional symbolic identification on top of it.
> **Supersedes:** PR #531 (`docs/specs/2026-05-05-causal-reasoning-design.md`). This spec keeps PR #531's §4.4 (modality-aware mutilation), §6 (y0 adapter), §4.8 (auditability), and §8 (`gaia check causal`) contributions verbatim where referenced; it replaces §0/§1/§3/§4.1/§5/§9 (the parts built on `Claim(kind=CAUSAL) + Cause Action`).
> **Depends on:** PR #505 (Variable/Domain/Formula AST), PR #510 (formula lowering into IR metadata), PR #524 (role-on-action-graph + decompose).
> **Non-goals:** Counterfactual reasoning (Pearl level 3); structure learning from data; continuous SCMs; population-level ATE / CATE.

---

## 0. Why Mechanism Is Not a Claim

PR #531 modelled a causal edge as `Claim(kind=CAUSAL, formula=Causes(X, Y))` plus a `Cause` Action carrying CPD parameters. Reviewers surfaced several symptoms showing that this conflates three different kinds of thing:

| Ontological kind | Examples | What it is |
|---|---|---|
| **Proposition** | `Claim` | A truth-bearing statement about the world. Has a `prior` = P(statement is true). |
| **Reasoning step** | `Action` (Infer / Associate / Decompose / Equal / …) | A move in the reasoning graph relating claims. |
| **World structure** | *the missing category* | A fact about how the world generates values from other values. Has no truth value; it either is or isn't the structural story. |

A causal mechanism `X → Y` belongs to the third category. Forcing it into `Claim`:

1. Overloads `prior` — PR #531 §3.5 needed a dedicated subsection to explain that `prior` means "confidence the mechanism exists", not "probability the effect fires". The explanation is a correctness patch against the type confusion, not a design feature.
2. Strands CPD parameters on a `Cause` Action, which the compiler then copies back into claim metadata so downstream consumers can read them. The metadata round-trip is the type system telling us the parameters belong on the mechanism itself.
3. Requires a `factor.metadata["modality"] == "causal"` tag for `mutilate()` to work correctly (PR #531 §1.2, §4.4). Factors lose their origin type during lowering and have to re-announce it.
4. Forces five overlapping names — `Causes` / `causes` / `causal` / `Cause` / `cause` — across Formula, Claim, and Action layers (PR #531 §0.4's disambiguation table).
5. Makes `decompose(whole=causal_claim, …)` a legal-looking but semantically murky construction, because at the type level nothing distinguishes a causal claim from a regular claim.

This spec makes `Mechanism` a **first-class Knowledge type** in `gaia.ir`, alongside `Claim`, `Note`, and `Composition`. The round-tripped metadata, the `modality` tag, the five-name table, and the `Cause` Action all disappear.

---

## 1. Architectural Position

```
┌────────────────────────────────────────────────────────────────┐
│  Gaia Lang                                                       │
│  ──────────                                                       │
│  mechanism(cause=X, effect=Y, cpd=(0.85, 0.05))                  │
│  mechanism(cause=X(p), effect=Y(p), forall=p,                    │
│            domain=Person, …)    ← universal (option b, §5)       │
└─────────────────────────────┬──────────────────────────────────┘
                              │  Compiler
                              ▼
┌────────────────────────────────────────────────────────────────┐
│  Gaia IR                                                         │
│  ──────────                                                       │
│  KnowledgeType.MECHANISM (NEW — first-class)                     │
│  Mechanism { cause_id, effect_id, cpd, … }                        │
└────────────────┬──────────────────────────┬────────────────────┘
                 │                          │
       build_dag │                          │ lower_to_fg
                 ▼                          ▼
        CausalDAG (NEW)            FactorGraph
        ────────────               ──────────
        nx.DiGraph                 CausalFactor + logical factors
        d-separation               mutilate() by factor type
        adjustment sets            BP inference
        identify() via y0          numeric P(Y | do(X=x))
```

The DAG and the FactorGraph are **sibling views** of the mechanism set — neither derives from the other, both derive from IR. See §7 for the consumer wiring.

### 1.1 Replaced / removed pieces

Relative to PR #531, this spec removes:

- `Claim(kind=CAUSAL)` — `ClaimKind.CAUSAL` goes away. Legacy CAUSAL claims in shipped packages are migrated by a one-shot `gaia migrate causal` tool (§11).
- `Cause(Probabilistic)` Action class and the associated role-table entries.
- `metadata.causal.cause` / `.effect` / `.dag_edge` / `.cpd` — all move onto the `Mechanism` dataclass fields.
- `factor.metadata["modality"]` — replaced by `isinstance(f, CausalFactor)` / `FactorKind.CAUSAL`.
- Five-name disambiguation table. Author-visible surface is a single `mechanism()` verb (§4).

Relative to PR #531, this spec keeps:

- **§4.4 modality-aware mutilation** with the eight-thought-experiment rationale, reinterpreted as "mutilate() filters by factor type" (§6.3).
- **§6 y0 adapter** as `gaia.causal.adapters.y0` (§8).
- **§4.8 auditability** — `CausalQueryResult.factor_graph_digest` and `dag_snapshot` fields (§7.4).
- **§8 `gaia check causal`** rule set (§9).
- **§4.1.2 multi-parent noisy-OR composition** with the H3 fix from review (§6.2).

### 1.2 What we externalize vs. what stays in Gaia

A guiding question during design was "can we offload causal computation to a mature library (pgmpy, DoWhy, EconML, Ananke, causal-learn)?" The answer is two-part: **the parts that can be externalized are externalized; the parts that cannot are <100 LoC of Gaia-specific glue.**

| Capability | Source | Why this choice |
|---|---|---|
| DAG algorithms (cycle detection, ancestors, d-separation, adjustment sets) | NetworkX (kernel dep) | Pure-Python DAG library, no native deps; `nx.d_separated` is stable since 3.1. |
| Symbolic do-calculus identification (ID/IDC algorithm) | y0 (`gaia[causal-do]` extra) | Avoids re-implementing Shpitser-Pearl; y0 already has `NxMixedGraph` for ADMG (§13 Q3). |
| Numeric `P(Y \| do(X=x))` | **Gaia BP** | See discussion below — outsourcing this means outsourcing *all* of Gaia BP, which is a separate architectural decision. |
| Mutilation by modality | **Gaia** (~15 LoC, §6.3) | The causal/logical factor split is Gaia-specific; pgmpy's `do()` operates on its own BN model, not on Gaia's mixed-modality FactorGraph. |
| Multi-parent leak-aware noisy-OR | **Gaia** (~30 LoC lowering pass, §6.2) | An authoring-time CPT-composition transform, not a query-time library call. |
| Per-instance grounding for universal mechanisms | **Gaia** (reuses `_lower_forall`, §5) | Mirrors v0.5 logical-quantifier grounding; no external equivalent. |

**Why we do not delegate numeric `do().query()` to pgmpy.** PR #533 §6.3 (and PR #531 §4.4 before it) makes mutilation modality-aware: only `CausalFactor` instances are removed under `do()`; `LOGICAL` factors (deduction, IMPLICATION operator, EQUIVALENCE, …) are preserved because intervening on the world does not sever statements *about* the world. This means the mutilated FactorGraph contains a mix of causal and logical factors that share variables. Routing only the causal factors to pgmpy is incoherent (factors share variables); routing everything to pgmpy means translating Gaia's entire IR-to-FG lowering into pgmpy CPDs — i.e., abandoning Gaia BP. That is a v0.7+ architectural decision affecting `infer()` / `associate()` / `decompose()` and the entire BP engine, not a per-feature outsourcing question.

**Data-driven libraries are out of scope.** DoWhy, EconML, CausalNex, Ananke, and causal-learn all require an observational dataset. Gaia is a prior-/author-driven reasoning system; mechanisms and CPDs are declared, not learned. These libraries solve a different problem.

The remaining Gaia-specific causal code totals roughly 50–100 LoC across `gaia/bp/factor_graph.py` (mutilate), `gaia/bp/lowering/` (noisy-OR), and `gaia/causal/intervene.py` (compute glue). This is below the maintenance threshold for taking on a third-party dependency wrapper.

---

## 2. IR Schema Change (Protected Layer — requires separate approval)

Per `CLAUDE.md`, `gaia/ir/` is a protected layer; this PR is the IR-schema PR and is itself the approval artifact.

### 2.1 `KnowledgeType.MECHANISM`

```python
# gaia/ir/knowledge.py
class KnowledgeType(StrEnum):
    CLAIM = "claim"
    NOTE = "note"
    COMPOSITION = "composition"
    MECHANISM = "mechanism"        # NEW
    # Legacy non-probabilistic types kept for back-compat.
    SETTING = "setting"
    QUESTION = "question"
    CONTEXT = "context"
```

### 2.2 `Mechanism` knowledge payload

```python
# gaia/ir/mechanism.py  (NEW)
from pydantic import BaseModel

class MechanismRef(BaseModel):
    """Reference to one endpoint of a mechanism — Variable (CNID) or Claim (QID)."""
    id: str                              # QID for Claim, CNID for Variable
    kind: Literal["variable", "claim"]
    symbol: str | None = None            # original author symbol (audit-only)

class BinaryCPT(BaseModel):
    """Conditional probability table for a Bool→Bool mechanism (the v0.6 form)."""
    p_effect_given_cause: float          # P(effect=1 | cause=1)
    p_effect_given_not_cause: float      # P(effect=1 | cause=0)

class Mechanism(BaseModel):
    """A causal mechanism — a first-class Knowledge payload.

    A Mechanism is stored as a Knowledge with type=MECHANISM; the Mechanism
    model is attached to Knowledge.payload (a new typed field, parallel to
    how Claim-typed Knowledge carries its claim model today).

    The `kind` field is a discriminator for future expansion (categorical
    endpoints, linear-Gaussian, ADMG bidirected edges, …); v0.6 ships
    a single concrete form, "binary_directed". See §13 Q3 for the
    expansion roadmap and §14 for the alignment with y0's NxMixedGraph.
    """
    kind: Literal["binary_directed"] = "binary_directed"
    cause: MechanismRef
    effect: MechanismRef
    cpd: BinaryCPT | None = None         # None = structure-only (§6.1)
    # For universal mechanisms (§5):
    quantified_over: tuple[str, ...] = ()   # Variable symbols bound by forall
    domain_ref: str | None = None           # QID of the Domain Knowledge (if quantified)
```

`Mechanism` deliberately carries **no `prior` field, no `helper` field, no posterior belief**. A mechanism is structural — its existence is asserted by the author and consumed by DAG / BP machinery as such. Adding belief over mechanisms (ensemble structure averaging, structure learning) is a v0.7+ topic; introducing the field now would be designing for hypothetical future requirements. See §13 for the deferred questions.

### 2.3 What `Mechanism` represents — function interface

A `Mechanism` is **one directed, parameterized edge in a causal DAG**, not a full conditional distribution at the effect node.

**Mathematical reading.** A mechanism represents the conditional-distribution slice

```
P(effect | cause)
```

where both endpoints are binary in v0.6. Two scalars fully determine the slice; complements follow from normalization:

| Authored field | Symbol | Meaning |
|---|---|---|
| `p_effect_given_cause` | `P(E=1 \| C=1)` | probability the effect fires when the cause is present |
| `p_effect_given_not_cause` | `P(E=1 \| C=0)` | leak / baseline rate when the cause is absent |

**Granularity choice — edge, not node.** An effect node with *k* causal parents is authored as *k* Mechanisms sharing the same `effect`. Lowering composes them via leak-aware noisy-OR (§6.2) into the effect's full 2ᵏ-entry CPT. Authors never write the multi-parent CPT directly in v0.6.

Rationale for edge granularity over node granularity:

1. Natural language is edge-shaped — "smoking causes cancer" and "genetics causes cancer" are two assertions, not one.
2. DAG diagrams are drawn one arrow at a time.
3. Multi-parent CPT semantics (independence vs. synergy vs. inhibition) is itself a design knob; deferring it to a v0.7 escape hatch keeps v0.6 small.
4. Edge-shaped DSL keeps `mechanism()` parallel to `infer()` / `associate()` — both are single-pair verbs with two CPD scalars.

**What Mechanism is NOT:**

- Not a Pearl structural equation `Y = f_Y(pa(Y), U_Y)`. We do not materialize exogenous noise variables; the implicit `U_Y` is folded into the CPD parameters. This is exactly why counterfactuals (Pearl level 3) are out of scope (§12) — counterfactuals require explicit noise to evaluate "what would Y have been under a different cause".
- Not a multi-parent CPT. Authors who need a non-noisy-OR multi-parent shape (synergy, inhibition, deterministic AND/XOR) wait for v0.7.
- Not a Python callable. The CPD is two floats; runtime semantics are fixed at lowering time, not at query time.

**Behavior table — what lowering produces:**

| Authored shape | Lowering output |
|---|---|
| `cpd is None` (structure-only) | DAG edge; **no** `CausalFactor` |
| `cpd` set, single mechanism into effect | One binary `CausalFactor` over `(cause, effect)` with potential `Φ(c, e) = P(e \| c)` |
| `cpd` set, multiple mechanisms into same effect | Leak-aware noisy-OR composition (§6.2) → one `CausalFactor` over `(c₁, …, c_k, effect)` with the composed CPT |

### 2.4 Validation

The existing `Knowledge` model validator (`gaia/ir/knowledge.py:133`) is extended:

- A `Knowledge` with `type == MECHANISM` **must** carry a `Mechanism` payload.
- `metadata["prior"]` is rejected on MECHANISM knowledge — Mechanism has no truth value, so prior is not meaningful (§2.2 note). This is parallel in shape to the existing rule that prior is gated to CLAIM knowledge.
- `cause.id` and `effect.id` must both be either compiled QIDs or synthesized CNIDs (`@var:…`, see §3). Unresolved author symbols are a compiler error.
- If `cpd is not None`, both `p_effect_given_cause` and `p_effect_given_not_cause` must be set (giving only one is rejected; this is enforced both in the IR validator and earlier in the DSL — §4.6).

### 2.5 Migration from `Claim(kind=CAUSAL)`

`ClaimKind.CAUSAL` is removed. A one-shot `gaia migrate causal` (§11) rewrites any package containing `Claim(kind=CAUSAL)` into `Knowledge(type=MECHANISM, payload=Mechanism(...))`. Packages that were relying on PR #510's `metadata.causal.{cause,effect}` stop carrying those fields — the data moves onto `Mechanism` directly. The `prior` field on the migrated CAUSAL claim is **dropped**, not preserved on the Mechanism — see §2.2 / §11.

### 2.6 `is_qid` / `is_cnid`

CNIDs use a `@var:` prefix and are disjoint from QIDs (the `@` prefix fails `_QID_RE`). Introduced helper:

```python
def is_cnid(id_: str) -> bool:
    return id_.startswith("@var:")
```

Placed next to `is_qid` in `gaia/ir/knowledge.py`. Anywhere the codebase accepts "a node identifier" it must accept either.

---

## 3. Variable CNIDs

`Variable` objects (PR #505 §2.4) have no IR Knowledge. Mechanisms need stable string identifiers for their endpoints, so the compiler mints a **Causal Node ID** (CNID) for each Variable that appears in any mechanism:

```
@var:{namespace}:{package_name}:{symbol}
```

For per-instance grounded Variables (§5), the CNID carries an instance digest:

```
@var:{namespace}:{package_name}:{symbol}_{digest}
```

where `{digest}` is the first 8 hex chars of `sha256(domain_member_id || symbol)`, matching the convention in `gaia/lang/compiler/lower_formula.py:983` for universal logical instances. CNIDs are deterministic — recompiling a package produces the same CNIDs.

**Open question 1** (§13): when a Variable declared in package A is used in a mechanism in package B, the CNID uses package A's namespace. This mirrors PR #505's cross-package Variable lookup convention.

---

## 4. Authoring DSL — `mechanism()`

A single verb. No `Cause` Action, no `Causes`/`causes`/`causal` helpers in the authoring surface (the `Causes` formula predicate still exists inside formula AST for quantification, §5, but authors don't construct it directly).

### 4.1 Top-level mechanism

```python
# gaia/lang/dsl/causal.py
from gaia.lang import Bool, Variable
from gaia.lang.dsl.causal import mechanism, do, query, ate

co2  = Variable(symbol="co2_level",           domain=Bool)
temp = Variable(symbol="temperature",         domain=Bool)
G    = Variable(symbol="greenhouse_gas_other", domain=Bool)

mechanism(cause=G,   effect=co2,  cpd=(0.70, 0.05),
          rationale="Other greenhouse gases drive CO₂ via shared industrial sources.",
          label="g_causes_co2")
mechanism(cause=G,   effect=temp, cpd=(0.60, 0.05))
mechanism(cause=co2, effect=temp, cpd=(0.85, 0.05))
```

`mechanism(...)` returns a `MechanismHandle` (a thin Lang-runtime object wrapping the IR `Mechanism`). The handle supports `.label =` binding.

### 4.2 Structure-only mechanisms (no CPD)

```python
mechanism(cause=G, effect=co2)   # cpd=None
```

A mechanism with `cpd=None` contributes to the DAG (so `d_separated`, `adjustment_sets`, and symbolic `identify()` all work) but does **not** produce a `CausalFactor`. 

**Numeric queries require numeric parameters.** If `do().query(target)` depends on an effect node whose incoming causal mechanisms do not all have CPDs, the query raises `MissingCausalCPDError` with a diagnostic listing which mechanisms lack CPDs. Gaia will not invent a default CPD from a missing parameter — that would produce a precise-looking but unreviewed causal effect.

Structure-only mechanisms are useful for:
- Declaring DAG structure for graphical queries (`d_separated`, `adjustment_sets`)
- Symbolic identification via y0 (§8) — the identifying functional shape depends only on graph structure
- Placeholder edges during incremental package authoring (author adds structure first, CPDs later)

This replaces PR #531's tangled bare-`causal()`-vs-`cause()` distinction with a clean boundary: DAG structure can exist without numeric parameters, but numeric intervention requires numeric causal information.

### 4.3 Universal mechanism (option b — decision 3)

```python
from gaia.lang import Domain

Person = Domain(name="Person", members=["alice", "bob", "carol"])
Smokes = Variable(symbol="Smokes", domain=Bool)
Cancer = Variable(symbol="Cancer", domain=Bool)

mechanism(
    cause=Smokes, effect=Cancer,
    forall="p", domain=Person,
    cpd=(0.15, 0.05),
    label="smoking_causes_cancer",
)
```

When `forall=...` is supplied, the compiler grounds per-instance: for each `v ∈ Person.members` it emits an instance `Mechanism` with CNIDs `@var:…:Smokes_{digest(v)}`, `@var:…:Cancer_{digest(v)}`. 

**The universal mechanism is a compile-time template, not a BP variable.** The universal `Mechanism` record is stored in IR (with `quantified_over=("p",)`) for provenance and audit, but it does **not** produce a BP variable, does not produce a factor, and is not updated by evidence. This keeps `Mechanism` structural: it has no `prior`, no truth value, and no posterior.

If authors want to express uncertainty or support for a universal causal law (e.g., "smoking causes cancer" as a reviewable proposition), that belongs in a separate `Claim` or future causal-support action, not on the `Mechanism` itself. The `Mechanism` records the structure and parameters; belief about whether the mechanism holds is a meta-level concern.

This mirrors v0.5's logical-`forall` lowering in `gaia/lang/compiler/lower_formula.py:107–192`, which also expands universal quantifiers into per-instance ground terms without creating a "universal claim" BP variable.

**Why not reuse `forall(p, Causes(X(p), Y(p)))` (option a)?** It would make authors face two causal entry points (formula-side `Causes` for quantification, runtime-side `mechanism()` otherwise). With option b, `mechanism()` owns quantification natively. The `Causes` formula predicate is kept as an internal AST node used by the compiler during lowering, but is no longer an author-facing construct.

### 4.4 Query DSL

```python
from gaia.lang.dsl.causal import do, query, ate

r = do(co2=1).query(temp)                 # numeric P(temp=1 | do(co2=1))
r = query(temp, given_do={co2: 1})        # equivalent long form
r = ate(co2, temp)                        # do(co2=1).temp − do(co2=0).temp
r = do(co2=1).query(temp, identify=True)  # numeric + symbolic identifiability (needs extra)

# Universal-grounded mechanism: do() targets a specific instance.
r = do(Smokes_at("alice")=1).query(Cancer_at("alice"))
```

`do()` accepts Variable references or their CNID strings. Targets accept Variable references, Claim QIDs, or strings. `Smokes_at(...)` / `Cancer_at(...)` is sugar for "the instance CNID"; exact form TBD in implementation.

### 4.5 What the role-on-action-graph table loses

PR #524's role projection table gets no new entries for mechanisms. `Cause` Action is not introduced, so there are no `cause`, `effect`, `causal_strength_parameter`, or `causal_helper` role labels. Role projection remains a pure Action-graph concern.

---

## 5. Compiler Changes

### 5.1 `gaia/lang/compiler/`

- **New `lower_mechanism.py`**: walks Lang-runtime `MechanismHandle` registrations, synthesizes CNIDs for Variable endpoints via §3, resolves Claim endpoints to QIDs, and emits `Knowledge(type=MECHANISM, payload=Mechanism(...))`.
- **Universal grounding**: when `MechanismHandle.forall` is set, iterate `domain.members` and emit one instance Mechanism per member. Also emit one `universal` Mechanism knowledge with `quantified_over=(symbol,)` **for provenance only** — it does not produce a BP variable or factor. Per-instance mechanisms are the only ones that lower to `CausalFactor`s. This is the structural dual of `_lower_forall` in `gaia/lang/compiler/lower_formula.py:107`, which also expands universal quantifiers into ground instances without creating a "universal claim" variable.
- **Formula lowering unchanged for non-causal formulas.** The compiler no longer writes `metadata.causal.*` — that contract is retired.

### 5.2 No `Claim(kind=CAUSAL)` path

`ClaimKind.CAUSAL` is removed. `gaia.lang.dsl.sugar.causal()` is removed (it was the old top-level factory). The formula predicate `Causes` remains only as an internal AST node used inside `lower_mechanism` to bridge Formula-layer reuse; it is no longer exported from `gaia.lang` or `gaia.lang.dsl`. `causes()` formula sugar is removed from `gaia.lang.dsl.formula`.

### 5.3 Errors

- `MechanismCycleError` — DAG built from `Mechanism` knowledges is not acyclic.
- `MechanismEndpointUnresolvedError` — author referenced a Variable/Claim symbol that cannot be resolved at compile time.
- `MechanismMigrationRequired` — package contains `Claim(kind=CAUSAL)`; user must run `gaia migrate causal`.
- `MissingCausalCPDError` — numeric `do().query(target)` depends on an effect node whose incoming mechanisms do not all have CPDs. The error message lists which mechanisms lack CPDs and suggests adding `cpd=(...)` to each.

---

## 6. BP Lowering

### 6.1 `CausalFactor`

```python
# gaia/bp/factor.py
class FactorKind(StrEnum):
    LOGICAL = "logical"          # deduction, operator helpers
    CAUSAL = "causal"            # NEW

@dataclass(frozen=True)
class CausalFactor(Factor):
    kind: FactorKind = FactorKind.CAUSAL
    source_mechanism_qid: str    # provenance → Mechanism Knowledge
```

`mutilate()` filters by `isinstance(f, CausalFactor)` (or `f.kind == FactorKind.CAUSAL`). No `metadata["modality"]` tag.

**Structure-only mechanisms (`cpd=None`) do not produce `CausalFactor`s.** They contribute to the DAG (§7.2) but not to the FactorGraph. Numeric `do().query()` that depends on such a mechanism raises `MissingCausalCPDError` (§5.3).

### 6.2 Multi-parent composition — leak-aware noisy-OR (single rule)

When an effect node has multiple incoming Mechanisms **with CPDs**, the lowering pass groups them by effect and produces one `CausalFactor` per effect node via leak-aware noisy-OR. This is the **only** multi-parent composition rule in v0.6; PR #531 §4.1.2's fix for the H3 review issue is incorporated:

1. **All incoming mechanisms must have CPDs.** If any incoming mechanism has `cpd=None`, the effect node cannot be lowered to a `CausalFactor`. Numeric `do().query()` targeting this effect raises `MissingCausalCPDError` listing which mechanisms lack CPDs.
2. If every incoming mechanism has a CPD and they all agree on `p_effect_given_not_cause`, that shared value is the leak.
3. Otherwise, mixed leaks across mechanisms are an author error — the compiler rejects with `MechanismInconsistentLeakError` and requires either an explicit per-effect leak (via a future `leak=...` kwarg on `mechanism()`, v0.7) or author-normalized CPDs.

The per-parent strength is `strength_i = (p_effect_given_cause_i − leak) / (1 − leak)`; the effect CPT is `P(effect=1 | active A) = 1 − (1 − leak) * ∏_{i ∈ A} (1 − strength_i)`.

The **machine contract is always a full binary CPT** on the effect. Noisy-OR is an authoring transform inside lowering.

### 6.3 `mutilate()` — modality-aware, first-principles preserved

```python
# gaia/bp/factor_graph.py
def mutilate(fg: FactorGraph, intervened: set[str]) -> FactorGraph:
    """Return a new FactorGraph with CausalFactor instances whose conclusion
    is in `intervened` removed. LOGICAL factors (deduction-derived
    SOFT_ENTAILMENT, IMPLICATION / EQUIVALENCE / CONJUNCTION / DISJUNCTION
    operator factors) are preserved regardless of their conclusion."""
```

The eight thought experiments from PR #531 §4.4 (logical truths, fire/smoke, bachelor/unmarried, F=ma, temperature/evaporation, hot/cooked-not-raw, mixed incoming, double-declared) carry over without modification — the only change is that "is this factor causal?" is answered by type dispatch, not by metadata read. PR #531 §4.4.1's "no definitional flag needed" conclusion stands.

### 6.4 `InterventionUndefinedError`

`do(X=1)` on a node with no incoming `CausalFactor` raises `InterventionUndefinedError`. The error message points the author at `mechanism(cause=..., effect=X, ...)`.

---

## 7. `gaia.causal` — the consumer package

Pure consumer of compiled IR; writes nothing back to IR.

### 7.1 Layout

```
gaia/causal/                    # NEW
├── __init__.py                 # public surface
├── dag.py                      # CausalDAG, build_dag()
├── queries.py                  # d_separated, ancestors, descendants,
│                               #   parents, children, adjustment_sets
├── intervene.py                # Intervention, CausalQueryResult, compute(), ate()
├── errors.py                   # MechanismCycleError, InterventionUndefinedError,
│                               #   NotIdentifiable, MissingDependencyError
└── adapters/
    ├── __init__.py             # empty — extras are opt-in
    └── y0.py                   # identify(); lazy imports y0
```

### 7.2 `CausalDAG` — NetworkX-backed structural view

```python
@dataclass(frozen=True)
class CausalEdge:
    cause_id: str                # QID or CNID
    effect_id: str
    source_mechanism_qid: str    # provenance → Mechanism Knowledge

@dataclass
class CausalDAG:
    nodes: frozenset[str]
    edges: tuple[CausalEdge, ...]
    _graph: nx.DiGraph           # internal; rebuildable from edges

def build_dag(pkg_or_artifact) -> CausalDAG:
    """Walk Knowledge nodes of type MECHANISM; one edge per mechanism."""
```

Acyclicity is enforced at build time via `nx.is_directed_acyclic_graph`; failure raises `MechanismCycleError` listing the cycle.

### 7.3 Structural queries — `gaia/causal/queries.py`

```python
def ancestors(dag, node) -> frozenset[str]: ...
def descendants(dag, node) -> frozenset[str]: ...
def parents(dag, node) -> frozenset[str]: ...
def children(dag, node) -> frozenset[str]: ...
def d_separated(dag, x, y, given=frozenset()) -> bool: ...
def adjustment_sets(dag, cause, effect) -> list[frozenset[str]]: ...
```

Implementation delegates to NetworkX where available (`nx.d_separated` is stable since NetworkX 3.1); the in-house fallback is avoided by pinning `networkx>=3.1` as a kernel dependency.

### 7.4 Intervention — `gaia/causal/intervene.py`

```python
@dataclass(frozen=True)
class Intervention:
    assignments: dict[str, int]   # QID or CNID → {0, 1}

    def query(self, target, *, identify: bool = False) -> CausalQueryResult: ...
    def query_all(self, targets) -> dict[str, CausalQueryResult]: ...

@dataclass(frozen=True)
class CausalQueryResult:
    target_id: str                 # QID or CNID
    intervention: dict[str, int]
    belief: float                  # P(target=1 | do(assignments))
    dag_snapshot: CausalDAG
    factor_graph_digest: str       # sha256 of post-mutilation FG (canonicalized)
    identified: bool | None = None
    id_expression_latex: str | None = None
    id_node_map: dict[str, str] | None = None
```

`compute()` is the standard wiring:

```python
def compute(pkg, intervention, target, *, identify=False):
    dag = build_dag(pkg)                     # validates DAG node membership
    _assert_intervention_targets_are_dag_nodes(dag, intervention)
    fg  = lower_to_fg(pkg)                   # existing BP lowering + CausalFactor
    fg2 = mutilate(fg, set(intervention))
    for var, val in intervention.items():
        fg2.observe(var, val)
    beliefs = InferenceEngine().run(fg2).beliefs
    result = CausalQueryResult(
        target_id=_resolve_target(target),
        intervention=dict(intervention),
        belief=beliefs[_resolve_target(target)],
        dag_snapshot=dag,
        factor_graph_digest=_canonical_digest(fg2),
    )
    if identify:
        result = _attach_identification(result, dag, target, intervention)
    return result
```

`ate(cause, effect)` is a thin wrapper over two `compute()` calls; semantics are **per-instance** (not population) — universal mechanisms require specifying an instance CNID.

### 7.5 Auditability

Unchanged from PR #531 §4.8: every `CausalQueryResult` carries `dag_snapshot` + `factor_graph_digest`. The digest is computed from the post-mutilation `FactorGraph` via the canonical serialization already defined for BP audit.

---

## 8. Symbolic Identification — `gaia/causal/adapters/y0.py`

Unchanged in substance from PR #531 §6. Surface:

```python
def identify(dag, target, intervention) -> IdentificationResult: ...

@dataclass(frozen=True)
class IdentificationResult:
    identifiable: bool
    expression_latex: str | None
    node_map: dict[str, str]        # y0 display symbol → Gaia QID/CNID
    obstruction: str | None
```

Lazy-imports `y0`; missing dep raises `MissingDependencyError("install gaia[causal-do]")`. `pyproject.toml` gains a `causal-do` optional-dependencies entry with `y0>=0.2`.

---

## 9. `gaia check causal`

Rules (unchanged in intent from PR #531 §8; language updated for mechanism vocabulary):

| Rule | Severity | Triggered by |
|---|---|---|
| Acyclicity | Error | `MechanismCycleError` from `build_dag` |
| Intervention target is DAG node | Error | `InterventionUndefinedError` on any authored `do(...)` |
| Open back-door path | Warning | For every mechanism `X → Y`, check open back-door paths; report minimal adjustment sets or "none available" |
| Mixed-modality incoming edges | Warning (Error under `--strict`) | Effect has both a `mechanism()` and a `deduction(..., effect)` strategy. Authors should clarify whether the deduction is definitional (then §6.3 preserves it under `do()`) or actually a mis-typed mechanism. |
| Inconsistent multi-parent leak | Error | `MechanismInconsistentLeakError` at lowering time (§6.2) |
| Identification (opt-in) | Info / Warning | `--identify`; emits obstruction witness per non-identifiable authored `do()` |
| Variable reuse across sub-DAGs | Warning | Same Variable appears in disconnected components |

Output is JSON keyed by rule, integrated into the existing `gaia check` aggregated report.

---

## 10. Implementation Milestones

Four PRs, strictly ordered. Each independently shippable.

### D₁ — IR + Authoring + Structure (2–3 weeks)

- `gaia/ir/`: `KnowledgeType.MECHANISM`, `Mechanism` / `MechanismRef` / `BinaryCPT` models, validator updates, `is_cnid` helper.
- `gaia/lang/runtime/`: `MechanismHandle`.
- `gaia/lang/dsl/causal.py`: `mechanism()` verb (top-level + `forall=` universal form).
- `gaia/lang/compiler/lower_mechanism.py`: CNID synthesis, universal grounding parity with `_lower_forall`.
- `gaia/causal/{dag,queries,errors}.py`: `CausalDAG`, `build_dag`, `d_separated`, adjustment sets.
- `pyproject.toml`: `networkx>=3.1` as kernel dependency.
- Renderer: per-mechanism section in Obsidian wiki output (directed-edge SVG).
- Tests: IR validator accepts MECHANISM and rejects `metadata["prior"]` on it; `mechanism()` round-trips through compile; DAG build + cycle detection + d-separation parity with textbook confounder/chain/collider; universal grounding parity with logical-forall tests.

### D₂ — BP + Interventions (3–4 weeks)

- `gaia/bp/factor.py`: `FactorKind`, `CausalFactor`.
- `gaia/bp/factor_graph.py`: `mutilate()` by factor type.
- `gaia/bp/lowering/`: multi-parent leak-aware noisy-OR composition (§6.2).
- `gaia/causal/intervene.py`: `Intervention`, `CausalQueryResult`, `compute()`, `ate()`.
- `gaia/lang/dsl/causal.py`: `do()`, `query()`, `ate()`.
- `gaia check causal`: acyclicity, intervention-target, mixed-modality, inconsistent-leak rules.
- Tests: single-parent and multi-parent mechanism lowering; eight thought-experiment regression suite from PR #531 §4.4; hand-computed truncated factorization equalities on canonical SCMs (confounder, front-door, chain, collider); per-instance `do()` and `ate()` on universal-grounded mechanisms; audit-digest stability.

### D₃ — y0 adapter (1–2 weeks)

- `gaia/causal/adapters/y0.py`.
- `pyproject.toml`: `causal-do` optional extra with `y0>=0.2`.
- `gaia check causal --identify`.
- Tests: pin y0; identifiable/non-identifiable canonical DAGs; skip-marker for envs without extra.

### D₄ — Migration + Docs (1 week)

- `gaia migrate causal`: rewrites `Claim(kind=CAUSAL)` into `Knowledge(type=MECHANISM)`. Idempotent; refuses to run if any consumer code still imports `ClaimKind.CAUSAL`.
- Update first-party packages (Mendel, Galileo, Superconductivity) that currently author causal claims.
- Remove `gaia.lang.dsl.sugar.causal`, `gaia.lang.dsl.formula.causes`, `ClaimKind.CAUSAL` — these were transient and have no deprecation window because v0.5 is not yet released.
- `docs/foundations/causal/` user guide + `docs/specs/2026-05-06-causal-mechanism-first-class-design.md` (this doc).

---

## 11. Migration Strategy

**Assumption**: v0.5 is pre-release; no external consumers depend on the `Claim(kind=CAUSAL)` wire format. The one-shot `gaia migrate causal` tool is a convenience for first-party packages, not a compatibility bridge.

Behavior:

1. Scan package source files for `causal(...)` / `Claim(..., kind=CAUSAL, ...)`.
2. Rewrite each call site to `mechanism(cause=..., effect=..., cpd=...)` preserving CPD parameters that existed in PR #531-era sugar. The CAUSAL claim's `prior` is **dropped** — Mechanism has no prior (§2.2). If a migrated package relied on a non-default `prior`, the migration tool flags it with `MIGRATION-REVIEW` comments for author attention; the default migration is lossy on `prior` by design.
3. Re-compile; verify IR produces the same DAG structure (node set, edge set) as the pre-migration build.
4. Emit a git-ready patch; authors review and commit.

Migration runs once per package; after D₄ all first-party packages ship mechanism-first.

---

## 12. Out of Scope

Unchanged from PR #531 §11:

- Counterfactual reasoning (Pearl level 3).
- Population-level / CATE.
- Causal discovery from data.
- Continuous / parameterized SCMs.
- `pgmpy` adapter.
- Hidden confounders / ADMGs / Ananke.
- Conditional / policy interventions `do(X = g(Z))`.
- Full-CPT authoring escape hatch (deferred behind §6.2 noisy-OR default).
- `decompose(whole=mechanism)` — Mechanism is not a Claim, so `decompose` refuses it at the type level. Decomposing a mechanism as a concept (e.g. "smoking causes cancer because tar causes cell damage because …") is expressed by authoring the sub-mechanisms directly and optionally declaring an `Equal(top_mechanism, sub_mechanism_chain)` relation — future spec.

---

## 13. Open Questions

1. **CNID namespace for cross-package Variables.** §3 uses the declaring package's namespace. Alternative: stamp with the using package. Recommendation: declaring package (matches PR #505's Variable lookup semantics).
2. **Universal-mechanism `forall` syntax.** §4.3 uses `forall="p", domain=Person`. A more fluent alternative is `mechanism.forall(Person).that(cause=..., effect=...)`. Recommendation: kwarg form for D₁; revisit after first-party packages show real usage.
3. **`Mechanism.kind` expansion roadmap.** v0.6 ships a single value `"binary_directed"`. The discriminator is added now (§2.2) so future expansion is non-breaking. Two extension axes are anticipated:

   | Axis | New `kind` values | Adds | Earliest target |
   |---|---|---|---|
   | Function form | `categorical_directed`, `linear_gaussian_directed`, `deterministic_directed` | `CategoricalCPT`, `LinearGaussianCPD`, `DeterministicMap` payload variants; corresponding `CausalFactor` lowering | v0.7 (depends on BP supporting non-Bool variables) |
   | Graph structure | `binary_bidirected` (ADMG latent confounder), `selection_edge` | DAG builder accepts mixed graphs; `gaia.causal.adapters.y0` already speaks this dialect via `NxMixedGraph` | v0.7 (depends on BP marginalizing latents) |

   Per CLAUDE.md "don't design for hypothetical futures", v0.6 ships only `binary_directed` concretely. The `kind` field is the **smallest** schema commitment that keeps the door open without writing dead code.
4. **Identification output format.** Raw y0 `Expression.to_latex()` plus `node_map`, matching PR #531 §6. Gaia-native symbolic expression deferred.

---

## 14. Prior-Art Anchors

- Pearl, *Causality* (2nd ed., 2009) — DAG semantics, do-operator, back-door / front-door.
- Pearl & Mackenzie, *The Book of Why* (2018) — causal ladder.
- Shpitser & Pearl, "Identification of Conditional Interventional Distributions" (2006) — IDC algorithm y0 implements.
- PR #505 — Variable/Domain/Formula AST.
- PR #510 — formula lowering into IR metadata.
- PR #524 — role-on-action-graph + decompose.
- PR #531 — prior causal design (this spec supersedes; preserves §4.4 / §4.8 / §6 / §8 contributions).
- `docs/specs/2026-05-05-role-on-action-graph-design.md`.
- `docs/specs/2026-05-05-decompose-action-design.md`.
- `docs/superpowers/specs/2026-04-25-unit-stats-constants-design.md` — kernel-vs-adapter template.
- [y0](https://github.com/y0-causal-inference/y0) — symbolic do-calculus (optional adapter target). Beyond serving as the identification backend (§8), y0's interface informs three Gaia design choices: (1) `Mechanism.kind` discriminator (§2.2) leaves room for ADMG bidirected edges that y0's `NxMixedGraph` natively expresses; (2) `do(X=x).query(Y, identify=True)` mirrors y0's `identify_outcomes(graph, treatments, outcomes)` shape, wrapping the symbolic result with a numeric belief from Gaia BP; (3) explicit non-goals from y0 we do **not** import — counterfactual operators (Pearl level 3) and the Population/Distribution split — are recorded in §12 to keep v0.6 scope contained.
- [NetworkX](https://networkx.org/) — DAG infrastructure (promoted to kernel dep).
