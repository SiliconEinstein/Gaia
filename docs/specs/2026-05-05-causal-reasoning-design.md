# Causal Reasoning Design — Predicate Claims + Mechanism Actions + Intervention

> **Status:** Target design (proposal)
> **Branch:** `codex/v05-causal-docs-refresh` (off `v0.5`)
> **Target release:** v0.6 (built on the v0.5 lifted Lang, role/decompose, and Bayes foundations)
> **Date:** 2026-05-05
> **Scope:** Separate predicate-level causal propositions from action-level causal mechanisms, then add DAG semantics, d-separation, `do(X=x)` interventions, numeric answers via existing Gaia BP, and optional symbolic do-calculus identification via y0.
> **Depends on:** PR #505 (Variable / Domain / Formula AST with `Causes` predicate), PR #510 (formula metadata lowering), PR #524 (current Action families + `decompose`), and PR #523/#526 (Bayes distribution/action surface).
> **Non-goals:** Counterfactual reasoning (Pearl level 3); structure learning from data; data-driven effect estimation.

---

## 0. Background and Motivation

### 0.1 Where v0.5 left `Causes`

PR #505 introduced `Causes(X, Y)` as a **marker predicate** in the formula AST (`gaia/lang/formula/predicate.py:129`) and added `Claim.formula` / `Claim.kind`. PR #510 then lowered atomic formulas into IR metadata: a fresh-compiled `Claim(formula=Causes(...), kind=CAUSAL)` now carries `metadata.causal = {"cause": ..., "effect": ...}`.

Today this marker is still **structurally inert**: compiled artifacts have the authored cause/effect descriptors, but no compiled mechanism record, nothing reads `metadata.causal` as an interventional edge, nothing enforces acyclicity, nothing distinguishes `Causes(X, Y)` from `Causes(Y, X)` structurally, and there is no DSL for asking a causal question.

### 0.2 What v0.6 needs to deliver

Four concrete capabilities, ordered by dependency:

1. **Causal propositions** — keep `Causes(X, Y)` as a formula predicate inside an ordinary truth-bearing `Claim`. A causal proposition can be reviewed, supported, contradicted, quantified, or used as a warrant, but by itself it is not a BP factor and not an intervention target.
2. **Causal mechanisms** — add an action-level declaration that promotes a causal proposition into an interventional mechanism edge with CPD parameters. This is the only authoring surface that creates DAG edges.
3. **Interventions** — a `do(X=x)` query primitive that produces a numeric answer `P(Y | do(X=x))` using Gaia's existing BP engine. This is the primitive that distinguishes causal reasoning from conditional probability.
4. **Symbolic identification** (optional extra) — `identify(P(Y | do(X)))` returns either an identifiable expression (back-door / front-door / ID algorithm) or "not identifiable from observational data" — delegated to [y0](https://pypi.org/project/y0/), lazy-imported from an optional adapter.

This spec covers all four. Counterfactual reasoning (Pearl level 3) is **out of scope** — see §11.

### 0.3 First-principles position

We adopt the `gaia.stats` / `gaia.lang.bayes` pattern:

- **Kernel layers declare what; they do not compute heavy statistics.** Lang/IR represent causal structure as metadata + schema; they never import scientific computing libraries.
- **Adapters live outside the kernel.** Heavy or narrow-use dependencies ship in `project.optional-dependencies`.
- **Gaia's own BP engine is the default numeric backend.** If the answer can be produced by a graph rewrite plus existing BP, we do that rather than bolting on a second inference library.

Concretely:

| Layer | What it owns | Dependencies |
|---|---|---|
| `gaia.lang.formula.predicate.Causes` | Predicate-level AST marker inside a `Claim.formula` (exists today via PR #505) | none |
| existing `gaia.lang.dsl.sugar.causal` re-exported by `gaia.lang` / `gaia.lang.dsl` | Claim helper for authoring a causal proposition. It returns `Claim(formula=Causes(...), kind=CAUSAL)` and does **not** declare a mechanism edge. | none |
| `gaia.lang.dsl.causal.mechanism` (NEW) | Action-level mechanism declaration. This is the surface that owns CPD parameters and creates DAG edges. | none |
| `gaia.causal.dag` (NEW, kernel) | `CausalDAG` view over a `CollectedPackage` | `networkx` |
| `gaia.causal.intervene` (NEW, kernel) | `do(X=x)` rewrite + `.query(Y)` | reuses `gaia.bp` |
| `gaia.causal.adapters.y0` (NEW, extra) | Symbolic do-calculus identification | `y0` (extra: `gaia[causal-do]`) |

`networkx` is promoted to a kernel dependency (pure Python, ~3MB, no native extensions, widely trusted). `y0` is not — its base install pulls pandas + scikit-learn + statsmodels, which violates the "kernel stays light" rule, and Gaia only uses its symbolic identifier, not its data-driven parts.

The current v0.5 Action hierarchy is `Support`, `Structural`, `Probabilistic`, `Scaffold`, and `Compose`. Causal mechanisms should not be smuggled into formula metadata or reintroduce the older `Relate` / `Correlate` taxonomy. `causal()` stays a Claim/formula authoring helper; v0.6 adds a distinct `Mechanism` action family with its own lowering contract.

### 0.4 Layering and naming convention

This spec keeps the existing formula surface intact and adds a separate action helper. The names are deliberately layered:

```python
from gaia.lang import Causes, causes, causal, mechanism

f1 = Causes(X, Y)                         # formula AST dataclass
f2 = causes(X, Y)                         # existing formula helper
c  = causal(cause=X, effect=Y, prior=0.8) # causal proposition Claim
m  = mechanism(                           # action-level mechanism edge
    cause=X,
    effect=Y,
    backing_claim=c,
    p_effect_given_cause=0.85,
    p_effect_given_not_cause=0.05,
)
```

`Causes(...)` and `causes(...)` are formula-layer constructs: they express the causal predicate but do not carry CPD parameters. `causal(...)` is claim sugar: it creates the underlying `Claim(formula=Causes(...), kind=CAUSAL, prior=...)` and is the object reviewers argue about. `mechanism(...)` is the propositional/action-layer declaration: it creates the interventional edge and carries the CPD parameters needed by D₂. No public `cause()` helper is introduced; `causes()` remains exported from `gaia.lang` and `gaia.lang.dsl` for compatibility.

The compiler must not infer a mechanism from a bare `CAUSAL` claim. Promotion is explicit: no `mechanism(...)`, no DAG edge, no BP causal factor, and no valid `do()` target.

---

## 1. Architectural Position

```
┌────────────────────────────────────────────────────────────┐
│  Gaia Lang predicate layer                                  │
│  ────────────────────────                                    │
│  Causes(X, Y) inside Claim.formula                           │
│  causal(...) -> a truth-bearing CAUSAL Claim                  │
└────────────────────────┬───────────────────────────────────┘
                         │  formula lowering: predicate metadata only
                         ▼
┌────────────────────────────────────────────────────────────┐
│  Gaia Lang action layer                                     │
│  ─────────────────────                                      │
│  mechanism(cause, effect, backing_claim, CPD)                │
│  the only source of interventional mechanism edges           │
└────────────────────────┬───────────────────────────────────┘
                         │  compiler emits causal-mechanism records (§7)
                         ▼
┌────────────────────────────────────────────────────────────┐
│  Gaia IR  (unchanged schema — only metadata enriched)      │
│  ──────────                                                  │
│  Claims may carry predicate metadata                         │
│  Mechanism actions emit metadata.causal_mechanism records     │
└────────────────────────┬───────────────────────────────────┘
                         │  gaia.causal (NEW)
          ┌──────────────┼────────────────────────────┐
          ▼              ▼                            ▼
   gaia.causal.dag  gaia.causal.intervene      gaia.causal.adapters.y0
   ──────────────  ──────────────────────      ───────────────────────
   (kernel)        (kernel, via gaia.bp)       (extra: gaia[causal-do])
   NetworkX DAG    mutilate + Gaia BP           symbolic do-calculus
   d-separation    numeric P(Y|do(X=x))          identification
```

Four surfaces are involved, with strict ownership: predicate claims say what the author believes, mechanism actions say which propositions/variables enter an interventional graph, `gaia.causal` reads that graph, and the y0 adapter performs optional symbolic identification. **IR schema is unchanged** — only well-known metadata keys are added, consistent with how `gaia.stats` evolved.

### 1.1 Two metadata contracts

PR #510 introduced compiler-owned `metadata.causal` operand descriptors on causal formula claims. This spec keeps that metadata predicate-scoped:

```python
# On a Claim whose formula is Causes(X, Y), or a generated instance of one:
{
    "causal": {
        "predicate": {
            "cause":  {"kind": "variable" | "knowledge", ...},
            "effect": {"kind": "variable" | "knowledge", ...},
        }
    }
}
```

The compatibility shape already emitted by v0.5, `metadata.causal = {"cause": ..., "effect": ...}`, is accepted as a predicate descriptor and should be normalized to the nested `predicate` shape on recompile. It is **not** a mechanism edge.

`mechanism(...)` actions compile to a separate mechanism record:

```python
{
    "causal_mechanism": {
        "action_label": "x_causes_y_mechanism",
        "backing_claim_qid": "<QID of the causal proposition Claim>",
        "cause_id": "<QID or CNID>",
        "effect_id": "<QID or CNID>",
        "endpoint_kind": "variable" | "claim",
        "policy": "structural",          # build_dag includes authored mechanisms
        # Present when numeric intervention lowering is requested:
        "cpd": {
            "kind": "binary_edge",
            "p_effect_given_cause": 0.85,
            "p_effect_given_not_cause": 0.05,
        },
    }
}
```

`cause_id` / `effect_id` are either compiled QIDs (for Claim endpoints) or synthesized CNIDs (for Variable endpoints — see §3.1). Consumers distinguish them with `gaia.ir.knowledge.is_qid()`.

`metadata.causal_mechanism.cpd` is intentionally separate from both `metadata.causal.predicate` and `metadata.bayes`. The CPD is a structural mechanism parameter used by intervention lowering; it is not an observational likelihood, a Bayes model-comparison record, or an observation noise payload. D₂.5 stochastic interventions may reuse the `gaia.lang.bayes` distribution protocol for authored distributions, but compiled mechanism parameters remain under `metadata.causal_mechanism`.

The invariant is simple:

```python
if "causal_mechanism" not in metadata:
    # Review/render the causal proposition if present, but do not add a DAG edge.
    pass
```

For factor-level provenance, D₂ copies the mechanism record into `Factor.metadata`:

```python
Factor(
    ...,
    metadata={
        "modality": "causal",
        "causal_mechanism": {
            "action_label": "...",
            "backing_claim_qid": "...",
            "cause_id": "...",
            "effect_id": "...",
        },
        "cpd": {
            "kind": "binary_edge",
            "p_effect_given_cause": 0.85,
            "p_effect_given_not_cause": 0.05,
        },
    },
)
```

### 1.2 `gaia.bp` additions

One public helper is added to `gaia.bp`:

```python
# gaia/bp/factor_graph.py
def mutilate(fg: FactorGraph, intervened: set[str]) -> FactorGraph:
    """Return a new FactorGraph with **causal** factors whose `conclusion` is
    in `intervened` removed. Logical/structural factors (deduction-derived
    SOFT_ENTAILMENT, Decompose-generated helpers, and
    IMPLICATION/EQUIVALENCE/CONJUNCTION/DISJUNCTION operator factors) are
    preserved regardless of their conclusion — see §4.4 for the
    first-principles justification.

    The caller follows up with fg.observe(x, value) for each intervened var."""
```

For this to be implementable after lowering, D₂ extends `Factor` / `add_factor(...)` with a small metadata field:

```python
Factor(
    ...,
    metadata={
        "modality": "causal",               # or absent / "logical"
        "causal_mechanism": {
            "action_label": "<label>",
            "backing_claim_qid": "<QID>",
            "cause_id": "...",
            "effect_id": "...",
        },
    },
)
```

The modality test (causal vs. logical) reads `factor.metadata["modality"]`, not the original predicate claim. The `causal_mechanism` record is emitted only from `mechanism(...)` actions. The companion CNID variable registration is performed during normal lowering of mechanism actions; no separate `gaia.causal.lowering` module is required (§4.3).

### 1.3 Dependency layout in `pyproject.toml`

```toml
dependencies = [
    # existing...
    "networkx>=3",
]

[project.optional-dependencies]
# existing dev extra...
causal-do = ["y0>=0.2"]
```

No `causal-bn` / pgmpy extra. We do not need it — numeric intervention answers go through Gaia's own BP (§4).

---

## 2. Module Code Layout

```
gaia/
├── bp/
│   └── factor_graph.py          # + modality-aware mutilate() helper (§1.2)
├── causal/                      # NEW
│   ├── __init__.py              # public surface
│   ├── dag.py                   # CausalDAG, build_dag()
│   ├── queries.py               # d_sep(), ancestors(), descendants(),
│   │                            #   adjustment_sets()
│   ├── intervene.py             # Intervention, do(), .query(), ate()
│   ├── errors.py                # CausalCycleError, CausalMetadataMissingError,
│   │                            #   InterventionUndefinedError, NotIdentifiable
│   └── adapters/
│       ├── __init__.py          # (empty — extras are opt-in)
│       └── y0.py                # identify(); lazy imports y0
├── lang/
│   └── dsl/
│       ├── sugar.py             # existing causal() Claim helper (predicate layer)
│       └── causal.py            # NEW: mechanism() action helper
└── lang/
    └── compiler/
        ├── compile.py           # + compile Mechanism actions into causal_mechanism records
        └── lower_formula.py     # keeps Causes(...) predicate metadata scoped to claims
```

### 2.1 Boundaries

- `gaia.causal.dag` **reads** a `CollectedPackage` (or equivalent) and produces a `CausalDAG`. It does not write IR.
- `gaia.causal.queries` operates on a `CausalDAG`. Pure graph algorithms, no IR awareness.
- `gaia.causal.intervene` **reads** a compiled IR artifact, lowers it through the standard `gaia.bp.lowering` path (which now handles `mechanism()` actions and per-instance grounding), rewrites the resulting `FactorGraph` (`mutilate`), and runs BP. It does not write IR. **No separate causal lowering module is needed** — compiled mechanism records and CPD parameters carry enough information that ordinary lowering can register CNID variables and emit the causal CPT factor.
- `gaia.causal.adapters.y0` **reads** a `CausalDAG` and a symbolic query; returns an expression or a `NotIdentifiable` diagnosis. It does not touch `FactorGraph`.
- `gaia.lang.dsl.sugar.causal` remains the authored-side `causal()` Claim helper, already re-exported by `gaia.lang` and `gaia.lang.dsl`. It stays predicate-only.
- `gaia.lang.dsl.causal.mechanism` is the authored-side action helper that promotes a causal proposition into a mechanism edge.
- `gaia.causal` is the runtime query surface for `do()`, `query()`, and `ate()`. A `gaia.lang.dsl.causal` compatibility re-export can be added later if the broader DSL wants all verbs in `gaia.lang.dsl`, but it is not required for the core implementation.

This partitions the work so each module is independently testable and no file grows oversized.

---

## 3. Causal Structure Layer (Spec 1)

### 3.1 `CausalDAG` — view constructed from a package

```python
# gaia/causal/dag.py
from dataclasses import dataclass
import networkx as nx

@dataclass(frozen=True)
class CausalEdge:
    cause_id: str        # QID or CNID (see §3.1)
    effect_id: str       # QID or CNID
    source_action_label: str           # which mechanism action declared this edge
    backing_claim_qid: str | None      # causal proposition used as warrant/provenance
    backing_claim_prior: float | None  # belief that the backing proposition is true

@dataclass
class CausalDAG:
    nodes: frozenset[str]              # CNIDs for Variables, QIDs for Claims if supported
    edges: tuple[CausalEdge, ...]
    # Internal NetworkX view (not part of public API; rebuildable from edges):
    _graph: nx.DiGraph
```

Construction:

```python
def build_dag(pkg_or_graph) -> CausalDAG:
    """Walk compiled causal_mechanism records and assemble a DAG.

    Bare Claim(formula=Causes(...)) nodes are causal propositions, not
    mechanism edges, and are ignored unless a mechanism action promotes them.
    """
```

The node identifier is a **string ID** — not a Python object — so `CausalDAG` is picklable, diffable, and consumable by the JSON renderer. Two kinds of node IDs coexist in a DAG:

- **Claim endpoints**: use the compiled Claim **QID** directly (`{namespace}:{package}::{label}` per `gaia.ir.knowledge.is_qid`). This is the propositional/action layer: one Claim's truth causally changes another Claim's truth.
- **Variable endpoints**: use a synthesized **causal node ID** (`CNID`). Variables have no IR Knowledge per PR #505 §2.4, so they have no QID; we mint a stable synthetic ID with a visually distinct prefix: `@var:{namespace}:{package_name}:{symbol}`. The `@` prefix makes `is_qid()` return False, so no consumer confuses a CNID with a QID. The CNID is deterministic — identical inputs produce identical IDs across compilations, satisfying the audit-hash requirements of §4.8.

Current PR #505 code accepts `Causes(Term, Term)`, so predicate-level causal claims are term-level today. Claim-to-claim causation is not represented by `Causes(ClaimAtom(A), ClaimAtom(B))`; it is represented by the `mechanism(...)` action with Claim endpoints.

See Open Question 2 (§12) on the declaring-vs-using package question for cross-package Variable references.

### 3.2 Acyclicity is enforced at build time

`build_dag()` runs `nx.is_directed_acyclic_graph(self._graph)` before returning. Failure raises `CausalCycleError` listing the cycle; this plugs into `gaia check causal` (§8).

### 3.3 Queries

```python
# gaia/causal/queries.py
def ancestors(dag: CausalDAG, node: str) -> frozenset[str]: ...
def descendants(dag: CausalDAG, node: str) -> frozenset[str]: ...
def parents(dag: CausalDAG, node: str) -> frozenset[str]: ...
def children(dag: CausalDAG, node: str) -> frozenset[str]: ...

def d_separated(
    dag: CausalDAG, x: str, y: str, given: frozenset[str] = frozenset()
) -> bool:
    """Pearl d-separation. Wrap nx.d_separated if available, fall back
    to an in-house implementation for NetworkX versions that lack it."""

def adjustment_sets(
    dag: CausalDAG, cause: str, effect: str
) -> list[frozenset[str]]:
    """All back-door adjustment sets for P(effect | do(cause)).
    Returned list is sorted by cardinality (smaller first)."""
```

`d_separated` is the **one** semantic query the reviewer pipeline will lean on — it detects unblocked confounder paths. `adjustment_sets` is convenience sugar frequently asked about back-door identification.

### 3.4 Rendering hooks

The Obsidian wiki renderer gets two distinct sections:

- On causal proposition Claims: "**Causal proposition:** Causes(A, B)" plus formula metadata.
- On mechanism actions / backing claims: "**Causal mechanism:** A → B" plus action label, CPD, and intervention status.
- "**Ancestors:** …"
- "**D-separated from:** … given { … }" (when nontrivial)

These wire into `gaia render` through a tiny `render_causal_block(dag, node_or_action_id)` helper in `gaia.causal.dag` module. The SVG renderer uses directed edges with arrowheads only for mechanism actions, not for every `Causes(...)` predicate claim.

### 3.5 Prior on a causal proposition — what it means and what it is not

The `prior` on a causal proposition Claim is the agent's confidence that **the proposition "X causes Y" is true**. This is the same semantics PR #505 §4 gives to any claim with a formula: `prior = P(claim is true before evidence)`.

The numeric strength of a promoted mechanism — `P(effect=1 | cause=1)` and `P(effect=1 | cause=0)` — is a **separate quantity**, supplied through the `mechanism()` action's `p_effect_given_cause` and `p_effect_given_not_cause` parameters (§4.1). These two parameters are independent of the backing claim's `prior`:

- `prior = 0.9, p_effect_given_cause = 0.15, p_effect_given_not_cause = 0.05` — "I'm 90% sure smoking causes lung cancer; the mechanism kicks in 15% of the time among smokers, baseline 5% otherwise"
- `prior = 0.5, p_effect_given_cause = 0.99, p_effect_given_not_cause = 0.01` — "Coin-flip belief that this mechanism exists; if it does, it's nearly deterministic"

Conflating belief and strength into one number (e.g., reusing `prior` as the noisy-OR leak parameter) is a documented pitfall — see §12 Q4 for the rationale.

For v0.6, DAG-build treats every authored mechanism action as **structurally present regardless of backing-claim `prior`**; see §3.5.1.

#### 3.5.1 Soft edges, MAP structure, and the v0.6 default

A mechanism backed by a causal proposition with `prior < 1` is a **softly believed mechanism**, not a fuzzy DAG edge. The structure exists at the DAG level because the author explicitly wrote a mechanism action; the numeric mechanism is supplied by CPD parameters (`p_effect_given_cause`, `p_effect_given_not_cause`, or an explicit CPT). D₂ does **not** reuse `prior` as a CPD entry. Future ensemble semantics may decide how posterior mechanism belief modulates graph structure or model averaging, but that is outside v0.6.

Whether DAG-build should also filter edges by `prior > threshold` (MAP semantics) is **deferred** — see §12 Q1.

### 3.6 Independent Variables and isolated sub-DAGs

A variable never used as a `mechanism(...)` endpoint is not a DAG node, even if it appears in a bare `Causes(...)` predicate claim. A package can host multiple disconnected causal sub-DAGs — `CausalDAG` records components; `gaia check causal` warns if a `do()` target is on an isolated component and the user queries a disconnected effect.

---

## 4. Intervention Layer (Spec 2)

The centerpiece. `do(X=x)` is the primitive that separates causal from conditional reasoning.

### 4.1 Authored DSL — `mechanism()` action helper

`mechanism(...)` is the v0.6 surface for declaring a causal mechanism. It promotes a causal proposition into the interventional graph and is parameterized by **two independent quantities**:

- `backing_claim.prior` — the agent's belief that the causal proposition is true (semantics shared with all `Claim` priors per §3.5)
- `(p_effect_given_cause, p_effect_given_not_cause)` — the single-parent CPD entries `P(effect=1 | cause=1)` and `P(effect=1 | cause=0)`, structurally identical to `infer()`'s `(p_e_given_h, p_e_given_not_h)` and `support()`'s deprecated `(p1, p2)` (see §12 Q4 for the choice of separate parameters)

Runtime shape:

```python
# gaia/lang/runtime/action.py
@dataclass
class Mechanism(Action):
    """Interventional mechanism edge. Parallel to Support/Structural/Probabilistic."""

    cause: Claim | Variable | None = None
    effect: Claim | Variable | None = None
    backing_claim: Claim | None = None
    p_effect_given_cause: float | None = None
    p_effect_given_not_cause: float | None = None
```

`Mechanism` is intentionally not a `Support` or `Probabilistic` subclass. `infer()` says evidence updates belief in a hypothesis; `mechanism()` says intervening on one node changes the production of another node. They may use similar binary CPT numbers, but `mutilate()` must distinguish their modalities.

Authored shape:

```python
from gaia.lang import Bool, Variable, causal, mechanism
from gaia.causal import do, query

co2  = Variable(symbol="co2_level", domain=Bool)
temp = Variable(symbol="temperature", domain=Bool)
G    = Variable(symbol="greenhouse_gas_other", domain=Bool)

g_causes_co2 = causal(
    cause=G, effect=co2,
    prior=0.8,
    rationale="Other greenhouse gases drive CO₂ via shared industrial sources.",
    label="g_causes_co2_claim",
)
mechanism(
    cause=G,
    effect=co2,
    backing_claim=g_causes_co2,
    p_effect_given_cause=0.7,
    p_effect_given_not_cause=0.05,
    label="g_causes_co2_mechanism",
)

g_causes_temp = causal(cause=G, effect=temp, prior=0.7, label="g_causes_temp_claim")
co2_causes_temp = causal(cause=co2, effect=temp, prior=0.9, label="co2_causes_temp_claim")
mechanism(cause=G, effect=temp, backing_claim=g_causes_temp, p_effect_given_cause=0.6, p_effect_given_not_cause=0.05)
mechanism(cause=co2, effect=temp, backing_claim=co2_causes_temp, p_effect_given_cause=0.85, p_effect_given_not_cause=0.05)

# Query at runtime (invoked by `gaia infer --causal` or in an action body):
result = do(co2=1).query(temp)              # numeric P(temp=1 | do(co2=1))
result = query(temp, given_do={co2: 1})     # equivalent long form
```

`causal()` returns the underlying `Claim(formula=Causes(cause, effect), kind=ClaimKind.CAUSAL, prior=prior)` and records no CPD. The existing lowercase `causes()` formula helper remains available when an author needs only the formula AST and no Claim. `mechanism()` returns/registers a `Mechanism` Action and records CPD parameters for compiler/lowering. The v0.6 compiler normalizes those action parameters into `metadata.causal_mechanism.cpd` (§1.1).

#### 4.1.1 Default strengths (omitted parameters)

If the author omits `p_effect_given_cause` / `p_effect_given_not_cause`, the mechanism lowering uses the v0.5 deduction default — `(1 − ε, 0.5)` — making the edge a **hard causal implication** equivalent in BP behavior to `deduction([cause], effect)` plus a causal-modality tag. This makes hard causation and soft causation traverse the same lowering path with different parameters.

#### 4.1.2 Multi-parent effect: noisy-OR composition (default)

When an effect node has multiple `mechanism()` parents, each edge supplies its single-parent absolute CPD entries. The compiler groups incoming mechanism actions by effect and composes them into the effect node's canonical CPT using **leak-aware noisy-OR** by default.

First choose the effect-level leak:

- if all incoming edges agree on `p_effect_given_not_cause`, that shared value is the leak;
- otherwise the author must provide an explicit effect-level leak (or a full CPT once the authoring escape hatch ships); v0.6 must not silently use `max` or `mean` because either choice changes the baseline model.

For each active edge:

```
strength_i = (p_effect_given_cause_i - leak) / (1 - leak)
```

The compiler rejects `p_effect_given_cause_i < leak` for noisy-OR because that is inhibitory rather than activating. The CPT entry for a parent assignment is:

```
P(effect = 1 | active parents A) =
    1 − (1 − leak) * ∏_{i in A} (1 − strength_i)
```

With no active parents (`A = ∅`), this returns `leak`, so `P(effect=1 | all causes=0)` is preserved.

The machine contract is still a full binary `CONDITIONAL` CPT; noisy-OR is only an authoring/lowering transform. Authors who need inhibition, synergy, or any other non-noisy-OR interaction need the full-CPT authoring escape hatch discussed in §12 Q4.

#### 4.1.3 Soft `do()` deferred to D₂.5

`do(X = Distribution(...))` and other stochastic-intervention forms are scoped to a follow-up milestone D₂.5 — see §10 and §12 Q5 for the rationale. The authored distribution type should reuse the current `gaia.lang.bayes.distributions.protocol.Distribution` contract (`model_dump`, `logpmf` / `logpdf`, `support`) instead of inventing a second `DistributionSpec`. For binary soft interventions, v0.6 can either use the existing `Binomial(n=1, p=p)` literal or add a thin `Bernoulli(p)` alias in `gaia.lang.bayes`; both compile to the same unary intervention distribution.

### 4.2 Intervention object

```python
# gaia/causal/intervene.py
@dataclass(frozen=True)
class Intervention:
    assignments: dict[str, int]   # QID or CNID -> {0, 1}

    def query(self, target: str | VarRef) -> CausalQueryResult: ...
    def query_all(self, targets: Iterable) -> dict[str, CausalQueryResult]: ...

@dataclass(frozen=True)
class CausalQueryResult:
    target_id: str                 # QID or CNID
    intervention: dict[str, int]
    belief: float                  # P(target=1 | do(assignments))
    dag_snapshot: CausalDAG        # DAG used (for audit)
    factor_graph_digest: str       # sha256 of the mutilated FG (for audit)
    identified: bool | None = None   # True / False / None if y0 not consulted
    id_expression_latex: str | None = None # symbolic identifier, if computed
    id_node_map: dict[str, str] | None = None # display symbol -> Gaia QID/CNID
```

`belief` is always numerically produced by Gaia BP (it is always *computable* — whether or not it is *identifiable from data alone* is a separate question answered by the optional adapter).

#### 4.2.1 Average causal effect helper — `ate()`

A thin DSL wrapper over two `do()` queries:

```python
from gaia.causal import ate

ate_co2_to_temp = ate(co2, temp)
# Equivalent to:
#   do(co2=1).query(temp).belief - do(co2=0).query(temp).belief
```

`ate()` returns a `CausalATEResult(..., belief_diff: float, do1: CausalQueryResult, do0: CausalQueryResult)`. **Semantics:** the average causal effect on a *per-instance* DAG node — not a population ATE (Gaia is per-instance grounded; see §5). Population-level ATE / CATE is deferred (§11).

### 4.3 Numeric computation — mutilate + BP

```python
# gaia/causal/intervene.py, conceptual pseudo-code
from gaia.bp.factor_graph import mutilate                 # §1.2
from gaia.bp.lowering import lower_local_graph            # existing
from gaia.bp.engine import InferenceEngine                # existing

def _compute(
    pkg_artifact,
    intervention: dict[str, int],
    target: str,
) -> CausalQueryResult:
    dag = build_dag(pkg_artifact)
    # 1. Lower the compiled local graph normally. Mechanism actions have already
    #    been compiled to causal CONDITIONAL factors; the
    #    multi-parent noisy-OR composition (§4.1.2) is performed here at lower
    #    time, producing one provenance-tagged CONDITIONAL factor per causal effect node.
    fg  = lower_local_graph(pkg_artifact.local_canonical_graph)
    # 2. Mutilate: drop *causal* factors whose conclusion ∈ intervened set
    #    (see §4.4 — logical SOFT_ENTAILMENT factors are NOT mutilated).
    fg2 = mutilate(fg, set(intervention))
    # 3. Clamp intervened vars to their assigned values.
    for qid, val in intervention.items():
        fg2.observe(qid, val)
    # 4. Run BP via the existing engine and read off target marginal.
    beliefs = InferenceEngine().run(fg2).beliefs          # uses JT exact when treewidth allows
    return CausalQueryResult(
        target_id=target,
        intervention=dict(intervention),
        belief=beliefs[target],
        dag_snapshot=dag,
        factor_graph_digest=_canonical_digest(fg2),       # see §4.8
    )
```

**Why this is correct.** For a DAG with factorization `P(V) = ∏ᵢ P(vᵢ | pa(vᵢ))`, Pearl's truncated factorization for `P(V | do(X=x))` is identical to `P(V)` with every `P(xᵢ | pa(xᵢ))` replaced by the point mass on `xᵢ = x`. In Gaia v0.6 this is realised by:

1. Each `mechanism()` action contributes explicit CPD parameters. Multi-parent effects compose via noisy-OR (§4.1.2) into one canonical `CONDITIONAL` factor per effect node.
2. CNID variables (Variables, per PR #505 §2.4 they have no IR Knowledge) are registered as BP variables during causal lowering inside the standard `gaia.bp.lowering` path.
3. The generated causal factor carries `metadata={"modality": "causal", "causal_mechanism": {...}}` copied from the compiled mechanism action metadata (§1.2).
4. `mutilate(fg, intervened)` identifies and drops only the factor whose conclusion ∈ intervened **and** whose factor metadata says `modality == "causal"` (see §4.4). Logical and structural factors (`deduction`, `decompose`, IMPLICATION/EQUIVALENCE operator helpers) are preserved.
5. `observe()` clamps the intervened variable to its target value.

This yields exactly the truncated factorization for the per-instance DAG.

### 4.4 Mutilation respects modality — first-principles boundary

The `mutilate()` helper distinguishes **causal** factors from **logical** factors. Only the former are removed under `do()`. This is not a convention — it is forced by the meaning of `do()`:

> `do(X = x)` is an **intervention on the world**. Causal edges describe how the world produces effects from causes; intervening severs that production. Logical edges describe how *statements about* the world are related (entailment, definition, identity); intervention has no purchase on them.

A short tour of the thought experiments motivating this rule:

| # | Setup | `do()` query | Pearl-correct behavior | Implication for Gaia |
|---|---|---|---|---|
| 1 | "All men are mortal; Socrates is a man." | `do(¬"all men are mortal")` | Ill-defined. You cannot intervene on a logical truth. | **Logical edges admit no `do()` semantics**; they are preserved under mutilation. |
| 2 | Fire → Smoke (causal) | `do(Smoke = 1)` (smoke machine) | `P(Fire) = P(Fire)` — base rate, unchanged. | Causal edges are **severed**; intervened node loses its causal parents. |
| 3 | "Bachelor" ↔ "unmarried man" (definitional) | `do(¬"unmarried")` | Both flip together — they are the same fact. | Use EQUIVALENCE operator, not Causes / deduction. EQUIVALENCE is **not mutilated** (it's a structural identity, not a mechanism). |
| 4 | F = ma (physical law) | `do(a = 0)` | Ambiguous — depends on whether F=ma is read as constraint (then F→0) or mechanism (then F unchanged, supported by counter-force). | **Author must choose** — declare F→a with `mechanism()` (mechanism, F preserved) or as `deduction([F, m], a)` (constraint, F follows). Engine will not guess. |
| 5 | Temperature ⇄ Evaporation | `do(Evap = 0)` (sealed bucket) | Temperature unchanged at the mutilation step. | Direction matters; each direction is a separate cause. |
| 6 | Whole claim decomposed via `decompose(C, [A, B], A & B)` | `do(C = 0)` | The decomposition remains a structural identity; it is not a production mechanism. | `Decompose` is a `Structural` action in current v0.5, so generated factors are **not mutilated**. |
| 7 | Mixed: Hot → Cooked (causal); Cooked ↔ "not raw" (logical) | `do(Hot = 0)` | Cuts only the (empty) causal in-edges of `Hot`; `Cooked` propagates normally; logical "not raw" follows. | **Mixed graphs work cleanly** as long as each edge declares its modality. |
| 8 | (Generalization) Node has both causal and logical/structural incoming edges. | `do(node = v)` | Cuts only the causal in-edges; logical/structural edges remain live and propagate. | Implementation: filter on factor metadata `modality == "causal"`. |
| 9 | Same fact authored as both `causal()` and a logical/structural relation | — | Engine cannot disambiguate. | `gaia check causal` raises a warning when an effect node has both modalities incoming (§8.1, new rule). |

Concretely the rule is:

> **`mutilate(fg, intervened)` drops factor `f` iff:**
> 1. **`f.conclusion ∈ intervened`** — standard truncation condition; AND
> 2. **`f` is causal** — i.e., `f.metadata.get("modality") == "causal"`.
>
> Logical SOFT_ENTAILMENT (deduction-derived), `decompose()`-generated structural helpers, IMPLICATION operator factors, and EQUIVALENCE / CONJUNCTION / DISJUNCTION / CONTRADICTION operator factors are **never** mutilated.

This rule matches Pearl's standard mutilation when the graph is purely causal, and degrades gracefully when logical edges are present.

#### 4.4.1 Definitional escape hatch — not needed

Earlier drafts of this spec proposed a `definitional=True` flag on deduction edges to mark them "do-resistant". The first-principles analysis above makes the flag redundant: deduction edges are already do-resistant by virtue of being logical. No new author-facing flag is introduced.

### 4.5 Interaction with strategy-embedded operators (`FormalExpr`)

A `FormalStrategy` may embed multiple `Operator`s inside a `FormalExpr`. When lowered to `FactorGraph`, each embedded operator produces its own factor. `Decompose` similarly generates structural helper/formula factors from an action-level decomposition. `mutilate` walks the resulting factor list and applies the §4.4 rule uniformly — embedded operators and decomposition helpers are logical/structural by origin, so they pass through mutilation unchanged.

### 4.6 Only causally authored intervention is permitted

An intervention is only well-defined over nodes that are **DAG nodes** — i.e., participate in at least one `mechanism()` edge. Attempting `do(X = 1)` on a node that has no causal in-edges raises `InterventionUndefinedError` with a message pointing the author at `mechanism(...)`.

This is a deliberate restriction motivated by thought experiment 1 (§4.4): `do()` on a node with only logical parents has no Pearl-style semantics. The error message must surface this rationale rather than say "node not found."

### 4.7 Target types

`query(target)` accepts:

- A `Variable` reference (compiled to its synthesized CNID) — the common case.
- A `Claim` reference (compiled QID) — useful for `do(X=1).query(some_claim)` where the author wants to see the claim's belief under intervention.
- A string QID — the machine-friendly form.

The result's `target_id` is always the compiled QID (for Knowledge targets) or CNID (for Variable targets) regardless of input form.

### 4.8 Deterministic auditability

Every `CausalQueryResult` carries:

- `dag_snapshot` — the causal DAG used.
- `factor_graph_digest` — sha256 of the post-mutilation factor graph (canonicalized per §3.2 of `strategy.py`).

These let a reviewer re-run the query and verify bit-equality. The digest is the primary audit hash; the DAG snapshot is for human inspection.

---

## 5. Predicate Claims and Mechanism Grounding

Gaia Lang is **predicate-level** (PR #505: Variables, Domains, quantifiers, Causes); Gaia BP is **propositional** (Boolean Knowledge nodes + factors). The grounding rule has two stages:

1. Formula lowering grounds causal **propositions** exactly like other quantified formulas. This creates reviewable Knowledge nodes and deduction links, but no mechanism factors.
2. Mechanism lowering grounds only authored `mechanism(...)` **actions** into DAG nodes and causal `CONDITIONAL` factors.

This section fixes the grounding contract for causal propositions and mechanism actions under universal quantification, in **strict duality with the v0.5 logical-quantifier grounding** already implemented in `gaia/lang/compiler/lower_formula.py:107-192`.

### 5.1 The v0.5 baseline: how `forall` is grounded today

For a logical universal `forall(x: D, P(x))`, the v0.5 lowerer (commit a1f8c319, PR #510) emits:

- One **universal claim** Knowledge node (the source claim).
- For each `v ∈ D.members`: one **instance claim** `P_v` and one `deduction` strategy `universal_claim ⇒ P_v`.

There is **no NOISY_AND** linking the instances back to the universal — the universal is the deductive *parent*, and instances inherit truth from it through standard SOFT_ENTAILMENT / weak-syllogism flow.

In BP: `universal = true` ⇒ each `P_v` ≈ 1; `universal = false` ⇒ each `P_v` retreats to base rate. Evidence on any `P_v` weakly raises the universal via reverse syllogism.

**This is the model we mirror for causal proposition universals.** Mechanism factors are an additional action-layer lowering step, not a side effect of the formula lowerer.

### 5.2 The causal universal: proposition grounding plus mechanism grounding

For a causal universal `forall(p: D, Causes(X(p), Y(p)))`, the compiler emits:

- One **universal causal claim** Knowledge node — same node the author wrote.
- For each `v ∈ D.members`:
  - Instance causal claim Knowledge — the per-instance assertion that "X_v causes Y_v".
  - `deduction` strategy: `universal_causal_claim ⇒ instance_causal_claim` — exactly as the logical case.
  - Predicate metadata on the instance claim records the instantiated `cause` / `effect` descriptors.

If, and only if, the author also writes a `mechanism(...)` action whose `backing_claim` is this universal causal claim, the mechanism lowering additionally emits for each `v ∈ D.members`:

- Instance CNID variables `X_v`, `Y_v` — generated causal node IDs such as `@var:{namespace}:{package}:{symbol}_{digest}`. These are BP/DAG variables, **not** IR Knowledge nodes.
- One `metadata.causal_mechanism` record with `cause_id = X_v`, `effect_id = Y_v`, `backing_claim_qid = instance_causal_claim`.
- One provenance-tagged `CONDITIONAL` factor on `(X_v, Y_v)`, with CPT parameters taken from the `mechanism(...)` action and normalized into the mechanism record.

The proposition part is **structurally dual** to the v0.5 logical lowering: each instance gets a propositional copy, the universal claim is the deductive parent, and BP propagates exactly as it does today for universal logical claims. The mechanism part is action-layer promotion: it reads those grounded proposition nodes as provenance and emits causal factors only where the author explicitly asked for an interventional mechanism.

```
                   ┌────────────────────────────┐
                   │  universal_causal_claim    │ (Knowledge)
	                   └────────────┬───────────────┘
	                  deduction     │     deduction
        ┌──────────────────┐    │   ┌──────────────────┐
        ▼                  │    │   ▼                  │
	 instance_v₁_causal    instance_v₂_causal     ...        (per-instance Knowledge)
	        │                                │
	        │ mechanism action lowers         │ mechanism action lowers
	        │ this proposition into           │ this proposition into
	        │ CONDITIONAL (causal, CPT)       │ CONDITIONAL (causal, CPT)
	        ▼                                ▼
	 X_v₁ ──→ Y_v₁                    X_v₂ ──→ Y_v₂              (propositional CNIDs)
```

`do(X_v₁ = 1)` operates on a **specific instance** only if the corresponding mechanism action exists — Pearl-correct semantics, no ambiguity about which person/particle is being intervened on. `do(universal_causal_claim = 1)` is rejected because the universal claim is a proposition, not a causal DAG node; authors who want to assert the universal should use `observe(universal_causal_claim, 1)`.

### 5.3 Why per-instance grounding (not single-representative or population-parameter)

We considered three grounding strategies during design (recorded for posterity):

| Strategy | What it does | Why rejected for v0.6 |
|---|---|---|
| **A. Full individual grounding** *(adopted — §5.2)* | One instance per Domain member, exactly mirroring v0.5 logical-quantifier grounding. | Adopted. |
| B. Single representative | One pair `(X_template, Y_template)` per causal universal regardless of Domain size. | Asymmetric with logical `forall` lowering; loses the per-instance addressability that makes per-individual evidence and reviewer queries possible. |
| C. Population-parameter grounding | Introduce a "rate" / continuous-valued parameter node summarising the population. | Requires hierarchical SCM and continuous-valued nodes — not v0.5/v0.6 BP. Deferred to v0.7+ (§11). |

Strategy A is correct because it preserves the cleanest property of Pearl's framework: every node in the DAG is a concrete event whose `do()` semantics is unambiguous.

### 5.4 What this grounding does **not** support

- **Population-level intervention.** "What happens if 30% of the population is intervened on `X`?" requires marginalising over instance choice — out of scope. Authors who need this should run a population study externally (DoWhy/EconML) and feed the result back as evidence on the universal claim.
- **Heterogeneous treatment effects (CATE).** Per-instance grounding gives one effect strength per universal — variation across subgroups requires multiple universals partitioned by subgroup, which the author can express manually but the engine does not synthesise.
- **Counterfactual reasoning at the universal.** Counterfactuals at the per-instance level *do* compose under §4 mutilation; counterfactuals at the universal-claim level (e.g. "what if this universal had not held") are not given a special treatment — they reduce to instance-level counterfactuals.

These limits are recorded in §11 (out of scope).

### 5.5 Naming and identifier discipline

Per-instance grounded Knowledge nodes follow the synthesizer used by `gaia/lang/compiler/lower_formula.py:973` for logical instances — labels of the form `__forall_{symbol}_{digest}`. CNID synthesis for instance Variables follows §3.1 (`@var:{namespace}:{package}:{symbol}_{digest}`) so the same Variable used in two distinct universals produces two distinct CNIDs.

---

## 6. Symbolic Identification (Spec 3, optional)

### 6.1 Adapter contract

```python
# gaia/causal/adapters/y0.py
def identify(
    dag: CausalDAG,
    target: str,
    intervention: dict[str, int],
) -> IdentificationResult:
    """Ask y0 whether P(target | do(intervention)) is identifiable from
    observational data under the given DAG. Returns the symbolic expression
    if yes, or a NotIdentifiable with the obstruction witness if no.

    Imports y0 lazily; raises MissingDependencyError if y0 is not installed.
    """

@dataclass(frozen=True)
class IdentificationResult:
    identifiable: bool
    expression_latex: str | None # y0's rendered Expression.to_latex()
    node_map: dict[str, str]     # display symbol -> Gaia QID/CNID
    obstruction: str | None      # human-readable witness when not

class MissingDependencyError(ImportError): ...
class NotIdentifiable(Exception): ...
```

### 6.2 Opt-in call site

Identification runs **only on explicit request** — either through a `gaia check causal --identify` CLI flag or a keyword `do(co2=1).query(temp, identify=True)`. When requested and y0 is installed, the `CausalQueryResult` is populated with `identified`, `id_expression_latex`, and `id_node_map`.

This keeps the default path (`do().query()`) dependency-free.

### 6.3 Lazy import pattern

The adapter imports y0 inside the function body; `ImportError` is translated to `MissingDependencyError("install gaia[causal-do] to use do-calculus identification")`. This is the same pattern `gaia.stats.adapters` uses for scipy.

### 6.4 What identification does and does not provide

- ✅ Symbolic guarantee that the numeric answer in `result.belief` **could** have been computed from purely observational data under the DAG.
- ✅ Witness obstruction (e.g., "unblocked back-door path through G") when the query is not identifiable.
- ❌ Estimation uncertainty — that requires real data and is out of scope.
- ❌ Automatic adjustment — Gaia BP already uses all the structure it has; identification is a **meta-assurance** layer on top of the numeric answer.

---

## 7. Compiler Changes

### 7.1 Normalize predicate metadata

```python
causal = claim.metadata.get("causal")
if not causal or "cause" not in causal or "effect" not in causal:
    raise CausalMetadataMissingError(
        "CAUSAL claim is missing predicate causal descriptors; "
        "recompile with the v0.6 formula-lowering compiler"
    )

claim.metadata["causal"] = {
    "predicate": {"cause": causal["cause"], "effect": causal["effect"]}
}
```

D1 builds on the v0.5 formula-lowering path. After QID assignment, the compiler walks Claims whose formula is a top-level `Causes(X, Y)` (`kind == CAUSAL`), quantified Claims whose grounded body is `Causes(...)` (`kind == QUANTIFIED`), or generated instances of either. It validates that formula lowering already populated predicate descriptors and normalizes them into `metadata.causal.predicate`.

This pass intentionally does **not** write `dag_edge` or `cpd`. Those are mechanism-action concepts.

### 7.2 Compile mechanism actions

The compiler separately walks `Mechanism` actions. For each action it:

1. Registers the `backing_claim` and endpoint Claims, if present, as normal Knowledge.
2. Resolves endpoint IDs:
   - Claim endpoints resolve to compiled QIDs.
   - Variable endpoints synthesize CNIDs using §3.1.
3. Validates that a backing causal proposition, if provided, is compatible with the action endpoints. A mismatch is an error; this prevents a claim saying `Causes(X, Y)` from backing a mechanism `Z → Y`.
4. Emits a `metadata.causal_mechanism` record (§1.1) that `build_dag` and BP lowering can consume.

For `Variable` operands, `resolve_causal_id` synthesizes a **CNID** with the format `@var:{namespace}:{package_name}:{symbol}` — visually distinct from QIDs and guaranteed to fail `is_qid()`. For Claim endpoints, it uses the compiled QID directly. No broadening of `Causes` is needed for claim-to-claim causation because that path lives in `mechanism(...)`, not in the formula predicate.

### 7.3 No new IR schema, no overloaded strategy type

All the new semantics live in metadata and in `gaia.causal`. IR `Operator`, `Strategy`, `StrategyType`, `OperatorType` enums — all unchanged. The compiler must not encode mechanism actions as ordinary `infer`, `support`, or `deduction` strategies without an explicit `metadata.causal_mechanism` record; doing so would lose the modality needed by `mutilate()`.

### 7.4 Migration concern: existing `CAUSAL` claims

Packages compiled after PR #510 but before v0.6 can already contain `metadata.causal.cause` / `.effect`. Handling:

- If `metadata.causal` is absent on a causal proposition claim, the artifact is malformed for v0.6 causal proposition tooling.
- If `metadata.causal` exists with top-level `cause` / `effect`, recompile normalizes it to `metadata.causal.predicate`.
- If a package has causal proposition Claims but no `mechanism(...)` actions, `build_dag` returns no edges and `do()` targets are undefined. This is intentional and should be explained by diagnostics rather than treated as missing metadata.

---

## 8. `gaia check causal`

A new CLI sub-check. Invoked as `gaia check causal <package>` or bundled into `gaia check` when a package contains any `CAUSAL` claim or `Mechanism` action.

### 8.1 Rules

| Rule | Severity | Triggered by |
|---|---|---|
| Acyclicity | Error | `CausalCycleError` from `build_dag` |
| Intervention target is a DAG node | Error | `InterventionUndefinedError` on any authored `do(...)` |
| Bare causal proposition | Info | A `Claim(formula=Causes(...), kind=CAUSAL)` or quantified causal proposition exists with no `mechanism(...)` action. It is reviewable as a proposition but does not enter DAG/intervention semantics. |
| Mechanism/backing mismatch | Error | A `mechanism(...)` action's endpoints disagree with its backing causal proposition. |
| Open back-door path | Warning | For every mechanism edge `X → Y`, inspect paths from `X` to `Y` that enter `X` after removing outgoing edges from `X`. If any path remains open under the declared observed covariates, surface the minimal candidate adjustment sets from `adjustment_sets(...)` or report that no valid set is available. Never condition on `X` or `Y` themselves. |
| Mixed-modality incoming edges | Warning (Error under `--strict`) | Effect node has both `mechanism()` and logical/structural incoming factors (`deduction()`, `decompose()`, EQUIVALENCE, etc.). Author should clarify whether the non-causal edge is a definitional consequence (then mutilation will preserve it correctly per §4.4) or actually a mis-typed causal mechanism (then re-author as `mechanism()`). See §4.4 thought experiment 9. |
| Identification (opt-in) | Info / Warning | Requires `--identify`; emits obstruction witness per non-identifiable authored `do()` |
| Variable reuse across sub-DAGs | Warning | The same Variable appearing in disconnected components — likely an authoring error |

### 8.2 Output format

JSON, keyed by rule. Fits into the existing `gaia check` aggregated report so reviewers get one unified view.

---

## 9. DSL Surface Summary

```python
# Authoring — separate causal proposition from mechanism action
from gaia.lang import Bool, Variable, causal, mechanism

X = Variable(symbol="X", domain=Bool)
Y = Variable(symbol="Y", domain=Bool)

c = causal(
    cause=X, effect=Y,
    prior=0.9,
    rationale="…",
    label="x_causes_y_claim",
)
m = mechanism(
    cause=X,
    effect=Y,
    backing_claim=c,
    p_effect_given_cause=0.85,
    p_effect_given_not_cause=0.05,
    label="x_causes_y_mechanism",
)
# `c` is the reviewable CAUSAL Claim. `m` is the mechanism edge.
# The lowercase causes() formula helper remains available when you only need the AST node.
```

```python
# Queries
from gaia.causal import do, query, ate

result = do(X=1).query(Y)                            # numeric, hard intervention
result = do(X=1).query(Y, identify=True)             # numeric + symbolic (needs extra)
result = query(Y, given_do={X: 1})                   # long form
result = ate(X, Y)                                   # do(X=1).Y - do(X=0).Y

# D₂.5 (separate milestone): stochastic intervention
from gaia.lang.bayes import Binomial
result = do(X=Binomial(n=1, p=0.1)).query(Y)
```

```python
# Library (for tool authors / reviewers)
from gaia.causal import build_dag, d_separated, ancestors, adjustment_sets

dag = build_dag(compiled_artifact)
dag.nodes          # frozenset[str]
dag.edges          # tuple[CausalEdge, ...]
d_separated(dag, "@var:github:pkg:X", "@var:github:pkg:Y", frozenset({"@var:github:pkg:Z"}))
ancestors(dag, "@var:github:pkg:Y")
adjustment_sets(dag, "@var:github:pkg:X", "@var:github:pkg:Y")       # list[frozenset[str]]
```

```python
# Optional symbolic identification (extra)
from gaia.causal.adapters.y0 import identify        # lazy y0 import

identify(dag, target="@var:github:pkg:temp",
         intervention={"@var:github:pkg:co2": 1})
# → IdentificationResult(identifiable=True, expression_latex="...", node_map={...})
# or IdentificationResult(identifiable=False, obstruction="back-door path via G")
```

---

## 10. Implementation Milestones

Five independent PR slices, strictly ordered.

### Milestone D₁ — Causal structure layer (Spec 1)

Depends on: PR #505 and PR #510 (merged to `v0.5`).

- **Compiler:** validate and normalize existing `metadata.causal` operand descriptors as predicate metadata; compile `Mechanism` actions into `metadata.causal_mechanism` records (§7.1, §7.2).
- **`gaia.causal.dag`:** `CausalDAG`, `CausalEdge`, `build_dag`. Cycle detection.
- **`gaia.causal.queries`:** `ancestors`, `descendants`, `parents`, `children`, `d_separated`, `adjustment_sets`.
- **`gaia.causal.errors`:** `CausalCycleError`, `CausalMetadataMissingError`, `InterventionUndefinedError`.
- **DSL:** keep existing `causal()` as Claim/formula sugar; add `mechanism()` action helper with CPD parameters (§4.1); keep `causes()` exported as formula sugar (§0.4).
- **`pyproject.toml`:** `networkx>=3` added to base dependencies.
- **Renderer hook:** separate "Causal proposition" and "Causal mechanism" sections in Obsidian wiki output.
- **Tests:** compiler preserves `metadata.causal.cause` / `.effect` from formula lowering as predicate metadata; bare `causal()` returns a `CAUSAL` Claim but does not create DAG edges; `mechanism()` emits a causal mechanism record and preserves CPD metadata for D₂; `causes()` remains importable; DAG construction, acyclicity, d-separation parity with textbook examples (confounder, chain, collider); adjustment-set enumeration on canonical DAGs.

Independently shippable: enables `gaia check causal`, makes renderings causal-aware, but does not yet execute interventions. Roughly 2–3 weeks.

### Milestone D₂ — Intervention primitive (Spec 2)

Depends on: D₁.

- **`gaia.bp.factor_graph.mutilate`:** modality-aware helper (§1.2, §4.3, §4.4). Drops only provenance-tagged causal `CONDITIONAL` factors; logical factors preserved.
- **Multi-parent noisy-OR composition:** lowering pass that combines multiple `mechanism()` edges into one provenance-tagged `CONDITIONAL` factor per effect node (§4.1.2). Sits inside the existing `gaia/bp/lowering.py` — no new `gaia.causal.lowering` module needed; the compiled mechanism records and CPD parameters carry enough information to register CNID variables and emit the canonical CPT factor at standard lower time.
- **Per-instance grounding for causal universals:** formula lowering emits per-instance causal proposition Knowledge nodes plus deduction edges from universal to instance; mechanism lowering emits generated CNID variables and one provenance-tagged causal `CONDITIONAL` factor per instance pair only when a `mechanism()` action promotes the universal (§5.2).
- **`gaia.causal.intervene`:** `Intervention`, `CausalQueryResult`, `_compute` using `mutilate` + Gaia BP (no separate causal lowering module).
- **`gaia.causal`:** `do()`, `query()`, `ate()` surface (§4.1, §4.2.1); keep `causal()` itself on the existing `gaia.lang` / `gaia.lang.dsl` export path.
- **`gaia check causal`:** acyclicity, intervention-target, bare-proposition, mechanism/backing mismatch, and mixed-modality rules (§8.1).
- **Tests:** `mechanism()` lowers to a provenance-tagged causal `CONDITIONAL` factor with the expected CPT; bare `causal()` does not; smoked against canonical SCMs (confounder, front-door, chain, collider); belief values compared against hand-computed truncated factorizations; thought-experiment 1–9 (§4.4) regression coverage; per-instance grounding parity with logical-quantifier grounding; ATE round-trip.

Independently shippable: Gaia answers `P(Y | do(X))` and `ATE(X, Y)` numerically. Roughly 3–4 weeks (most of the work is tests, multi-parent noisy-OR composition, and per-instance grounding parity; `mutilate` itself is a small filter-and-rebuild pass).

### Milestone D₂.5 — Stochastic intervention (`do(X ~ dist)`)

Depends on: D₂.

- **Authored DSL:** `do(X = Binomial(n=1, p=p))` and equivalent shorthand for stochastic / soft interventions (§4.1.3). A `Bernoulli(p)` alias may be added in `gaia.lang.bayes` for ergonomics, but it must share the existing Distribution protocol.
- **`mutilate` extension:** instead of clamping intervened nodes via `observe`, install a unary likelihood factor matching the intervention distribution.
- **`Intervention.assignments`:** widen type from `dict[str, int]` to `dict[str, int | Distribution]` where `Distribution` is the current `gaia.lang.bayes` protocol.
- **Tests:** stochastic-do parity against analytic Bernoulli-equivalent examples; `do(X = Binomial(n=1, p=0.0))` and `do(X = Binomial(n=1, p=1.0))` collapse to hard-do behaviour.

Roughly 1 week. Carved out separately because the semantics warrant focused review (Pearl-stochastic vs. Pearl-deterministic interventions are documented differently in the literature) and to keep D₂'s footprint small.

### Milestone D₃ — y0 identification adapter (Spec 3)

Depends on: D₁ (D₂ not required — identification is numeric-agnostic).

- **`gaia.causal.adapters.y0`:** `identify`, `IdentificationResult`, `NotIdentifiable`, `MissingDependencyError`.
- **`pyproject.toml`:** `causal-do` extra with `y0>=0.2`.
- **`gaia check causal --identify`:** opt-in CLI rule.
- **Docs:** installation note for the extra.
- **Tests:** pin y0 version, verify identifiable / non-identifiable canonical DAGs (back-door, front-door, ID algorithm base cases) produce the expected classification. Skip-marker for environments without the extra installed.

Independently shippable. Roughly 1–2 weeks (mostly glue + tests).

### Milestone D₄ — Package migrations and doc refresh

Depends on: D₁, D₂ (D₃ optional).

- Update `docs/foundations/` — add a `causal/` sub-page reflecting the new primitives; link into the existing structure without redefining. Remove the "v0.6 interventional factor" placeholder from PR #505 §10.
- `gaia-lang` docs: `causal()`, `causes()`, `mechanism()`, `do()`, `query()`, `ate()` reference; worked examples (Pearl's smoking/genetics, Simpson's paradox).
- Audit first-party packages (Mendel, Galileo, Superconductivity) for any claim that would benefit from an explicit causal-claim rewrite — do not force, but list candidates in a follow-up issue.

---

## 11. Out of Scope / Deferred

| Item | Why deferred |
|---|---|
| **Counterfactual queries (Pearl level 3)** | Requires explicit exogenous noise variables, parameterized structural equations, and a different inference mode (abduction–action–prediction or twin networks). Gaia's propositional claim + prior model is not a structural causal model; promoting it would be a major world-view surgery. We will reopen this conversation only when a concrete scientific-reasoning use case demands it. |
| **Population-level intervention and heterogeneous treatment effects (CATE)** | §5 grounds causal universals **per instance**. Population-level queries ("intervene on 30% of the population") and CATE ("effect varies by subgroup") require either marginalising over instance choice or hierarchical SCM with subgroup-conditioned strengths — neither is supported by v0.5/v0.6 BP. Authors who need population effects should run a study externally and feed the result back as evidence on the universal claim. |
| **Causal discovery from data** | Gaia is a symbolic / prior-based reasoning system; DAG structure is authored, not learned. Tools like `causal-learn` or `causalnex` exist for that purpose and are external to our scope. |
| **Continuous / parameterized structural equations** | Gaia claims are Boolean; numeric values live in Variables with priors, not as draws from a structural equation. Promoting Gaia to continuous SCMs is equivalent to replacing the BP engine with pyro/numpyro — out of scope. |
| **`pgmpy` adapter** | Gaia BP answers the numeric intervention question once D₂ ships. Adding pgmpy would be a second inference engine with no additional capability. |
| **Front-door / back-door automatic adjustment in numeric BP** | Numeric BP runs on Gaia's authored causal factor graph, not on an observational dataset requiring covariate adjustment. `adjustment_sets()` in §3.3 is for *reviewer* use (auditing which covariates would need to be observed if working from data). |
| **Hidden confounders / ADMGs / Ananke integration** | v0.7 topic — requires lattice of bidirectional edges. |
| **Conditional / policy interventions (`do(X = g(Z))`)** | Single-atomic and stochastic interventions cover the core v0.6 use cases. Conditional interventions add notational complexity without comparable demand. v0.7+ if a use case appears. |
| **Custom multi-parent composition rules** | v0.6 ships leak-aware noisy-OR as the default authoring transform (§4.1.2). The internal machine contract is still a full CPT; author-facing full-CPT input is left to §12 Q4, and `noisy_and` remains v0.7+. |

---

## 12. Open Questions

1. **MAP vs. ensemble causal structure.** §3.5 states that DAG-build treats every authored `mechanism(...)` action as structurally present regardless of backing-claim prior. Is there a use case (reviewer workflow?) where the user wants `d_separated` computed against the *MAP* DAG (mechanisms with backing-claim belief > 0.5 only)? If yes, we add a `build_dag(..., policy="map" | "structural")` knob — otherwise, leave it out of v0.6.
2. **Variable CNID synthesis.** §3.1 proposes `@var:{namespace}:{package_name}:{symbol}`. Conflict to resolve: when a Variable is declared in package A but used in a `mechanism(...)` action in package B, do we stamp the CNID with the *declaring* package or the *using* package? Proposal: declaring package — matches how PR #505 proposes cross-package Variable lookups. The `@` prefix ensures `is_qid()` returns False so no consumer confuses a CNID with a Knowledge QID.
3. **Default stance on `do()` target that is not a DAG node.** §4.6 raises an error. An alternative is a warning + fall through to conditioning. Recommendation: error — silent "meaningless intervention" is the exact footgun the causal layer is meant to prevent.
4. **Full-CPT authoring timing.** §4.1.2 fixes the v0.6 machine contract as a canonical full binary CPT and uses leak-aware noisy-OR as the default authoring transform. Open question: should v0.6 also expose an advanced `mechanism_cpt(...)` authoring helper, or should D₂ only implement noisy-OR authoring and keep full-CPT authoring for v0.7?
5. **Soft-do timing.** §10 carves D₂.5 as a separate milestone after D₂ to keep `do()` semantics review-able piece by piece. Alternative: bundle stochastic intervention into D₂ for a single "intervention" PR. Recommendation: separate (more reviewable). Open to revisiting if reviewers prefer one combined PR.
6. **Mixed-modality warning level.** §4.4 thought experiment 9 says when an effect node has both `mechanism()` and logical/structural incoming factors, `gaia check causal` warns. Should this be a hard error in `gaia check causal --strict` mode? When does the situation actually represent author intent (e.g. "the structural relation is a derived consequence, the cause is the mechanism") vs. an authoring mistake?
7. **Identification output format.** Raw y0 `Expression.to_latex()` vs. a Gaia-normalized string with QIDs. Recommendation: LaTeX for v0.6 plus a `node_map` from display symbols to QID/CNID; a fully Gaia-native symbolic expression can come later.

---

## 13. Examples

### 13.1 Pearl's smoking / genetics (confounding)

```python
from gaia.lang import Bool, Variable, causal, mechanism
from gaia.causal import do, query, ate

G = Variable(symbol="G", domain=Bool)   # genetic predisposition
X = Variable(symbol="X", domain=Bool)   # smoking
Z = Variable(symbol="Z", domain=Bool)   # yellow fingers
Y = Variable(symbol="Y", domain=Bool)   # lung cancer

g_causes_x = causal(cause=G, effect=X, prior=0.6, label="g_causes_x_claim")
g_causes_y = causal(cause=G, effect=Y, prior=0.7, label="g_causes_y_claim")
x_causes_z = causal(cause=X, effect=Z, prior=0.9, label="x_causes_z_claim")

mechanism(cause=G, effect=X, backing_claim=g_causes_x, p_effect_given_cause=0.55, p_effect_given_not_cause=0.20)
mechanism(cause=G, effect=Y, backing_claim=g_causes_y, p_effect_given_cause=0.30, p_effect_given_not_cause=0.05)
mechanism(cause=X, effect=Z, backing_claim=x_causes_z, p_effect_given_cause=0.85, p_effect_given_not_cause=0.05)
# No X → Y edge — smoking does not directly cause cancer in this toy model.

from gaia.causal import build_dag, d_separated, adjustment_sets
dag = build_dag(pkg)
assert not d_separated(dag, "@var:github:pkg:X", "@var:github:pkg:Y")                            # observed assoc
assert     d_separated(dag, "@var:github:pkg:X", "@var:github:pkg:Y", {"@var:github:pkg:G"})     # controlled for G
print(adjustment_sets(dag, "@var:github:pkg:X", "@var:github:pkg:Y"))                            # [{G}]

r1 = do(X=1).query(Y)          # P(Y | do(X=1)) — ≈ base rate of cancer
r2 = query(Y, given={X: 1})    # P(Y | X=1)     — elevated by confounding
# r1.belief < r2.belief — the exact effect that disappears under intervention.

eff = ate(X, Y)                # do(X=1).Y - do(X=0).Y; ≈ 0 in this DAG
```

### 13.2 Simpson's paradox (Gaia surfaces it automatically)

Given a DAG where `X → Y`, `Z → X`, `Z → Y`, authored via `mechanism()` actions backed by causal proposition Claims, `do(X).query(Y)` gives the unconfounded effect while `query(Y, given={X: 1})` aggregates over `Z` and can reverse direction. `gaia check causal` (no flags) reports the mechanism DAG and any bare causal propositions separately; with `--identify`, y0 confirms `P(Y | do(X))` is identifiable via back-door over `Z`.

### 13.3 Multi-step intervention with mixed causal+logical edges

```python
from gaia.lang import Bool, Variable, causal, mechanism
from gaia.causal import do
from gaia.lang.dsl import deduction

T = Variable(symbol="T", domain=Bool)   # treatment
S = Variable(symbol="S", domain=Bool)   # side-effect mitigation
R = Variable(symbol="R", domain=Bool)   # recovery
L = Variable(symbol="L", domain=Bool)   # logged-as-recovered

# Causal mechanisms
t_causes_s = causal(cause=T, effect=S, prior=0.7, label="t_causes_s_claim")
t_causes_r = causal(cause=T, effect=R, prior=0.6, label="t_causes_r_claim")
s_causes_r = causal(cause=S, effect=R, prior=0.5, label="s_causes_r_claim")
mechanism(cause=T, effect=S, backing_claim=t_causes_s, p_effect_given_cause=0.8, p_effect_given_not_cause=0.1)
mechanism(cause=T, effect=R, backing_claim=t_causes_r, p_effect_given_cause=0.7, p_effect_given_not_cause=0.2)
mechanism(cause=S, effect=R, backing_claim=s_causes_r, p_effect_given_cause=0.6, p_effect_given_not_cause=0.3)

# Pure logical edge: "logged-as-recovered" follows recovery deductively (definitional)
deduction([R], L)

# Compound intervention: force treatment and mitigation simultaneously
do(T=1, S=1).query(R)
# `mutilate` drops the causal CONDITIONAL factors with conclusion in {T, S}.
# The deduction([R], L) factor is preserved (logical modality, §4.4 thought experiment 6).
```

### 13.4 Per-instance grounding for a causal universal

```python
from gaia.lang import Bool, Causes, Claim, ClaimKind, Domain, Variable, forall, mechanism
from gaia.causal import do, ate

Person = Domain(name="Person", members=["alice", "bob", "carol"])
p = Variable(symbol="p", domain=Person)
Smokes = Variable(symbol="Smokes", domain=Bool)
Cancer = Variable(symbol="Cancer", domain=Bool)

# Universal causal claim — grounded per-instance per §5.2
smoking_causes_cancer = Claim(
    "Smoking causes lung cancer (universal)",
    formula=forall(p, Causes(Smokes, Cancer)),
    kind=ClaimKind.QUANTIFIED,
    prior=0.85,
    label="smoking_causes_cancer",
)

mechanism(
    cause=Smokes,
    effect=Cancer,
    backing_claim=smoking_causes_cancer,
    p_effect_given_cause=0.15,
    p_effect_given_not_cause=0.05,
    label="smoking_causes_cancer_mechanism",
)

# Formula lowering emits per-instance causal proposition claims for alice/bob/carol.
# Mechanism lowering emits per-instance CNID variables and causal factors.
# do() and ate() operate on a chosen instance.
ate_alice = ate(target_instance="alice", cause_var=Smokes, effect_var=Cancer)
# Population-level ATE is NOT supported (§11) — this is the per-instance ATE.
```

The universal Claim carries the reviewable proposition. The `mechanism(...)` action carries the CPD. The compiler grounds the proposition first, then grounds the mechanism action against those instances; no CPD is stored on the causal Claim itself.

---

## 14. Prior-Art Anchors

- Pearl, *Causality* (2nd ed., 2009) — DAG semantics, do-operator, back-door / front-door.
- Pearl & Mackenzie, *The Book of Why* (2018) — levels of the causal ladder.
- Shpitser & Pearl, "Identification of Conditional Interventional Distributions" (2006) — IDC algorithm y0 implements.
- [y0](https://github.com/y0-causal-inference/y0) — symbolic do-calculus implementation (adapter target).
- [NetworkX](https://networkx.org/) — DAG infrastructure (promoted to kernel dep).
- PR #505 — claim formula schema (supplies `Causes`, `Variable`, `Domain`).
- PR #510 — formula lowering into IR metadata (supplies `metadata.causal.cause` / `.effect`).
- `docs/superpowers/specs/2026-04-25-unit-stats-constants-design.md` — kernel-vs-adapter separation template.
