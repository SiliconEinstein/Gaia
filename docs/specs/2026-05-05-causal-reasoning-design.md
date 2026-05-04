# Causal Reasoning Design — Structure + Intervention

> **Status:** Target design (proposal)
> **Branch:** `docs/causal-reasoning-design` (off `v0.5`)
> **Target release:** v0.6 (built on v0.5 foundation + PR #505 lifted Lang)
> **Date:** 2026-05-05
> **Scope:** Promote `Causes(X, Y)` from a v0.5 marker to first-class causal reasoning — DAG semantics, d-separation, `do(X=x)` interventions, numeric answers via existing Gaia BP, and optional symbolic do-calculus identification via y0.
> **Depends on:** PR #505 (Variable / Domain / Formula AST with `Causes` predicate).
> **Non-goals:** Counterfactual reasoning (Pearl level 3); structure learning from data; data-driven effect estimation.

---

## 0. Background and Motivation

### 0.1 Where v0.5 left `Causes`

PR #505 introduced `Causes(X, Y)` as a **marker predicate** in the formula AST (`gaia/lang/formula/predicate.py:129`). The spec's §7.3 commits to:

> In v0.5, `Causes(X, Y)` lowers to a propositional atom Knowledge with `metadata.causal` set to a serializable descriptor. BP in v0.5 treats the resulting claim as a regular Boolean atom. v0.6 introduces an interventional factor type that consumes `metadata.causal`.

Today this marker is **inert**: nothing reads `metadata.causal`, nothing enforces acyclicity, nothing distinguishes `Causes(X, Y)` from `Causes(Y, X)` structurally, and there is no DSL for asking a causal question.

### 0.2 What v0.6 needs to deliver

Three concrete capabilities, ordered by dependency:

1. **Causal structure** — a real DAG built from `Causes()` calls, with acyclicity enforcement, ancestor / descendant / parent queries, and d-separation. Surfaced in rendering and review.
2. **Interventions** — a `do(X=x)` DSL action that produces a numeric answer `P(Y | do(X=x))` using Gaia's existing BP engine. This is the primitive that distinguishes causal reasoning from conditional probability.
3. **Symbolic identification** (optional extra) — `identify(P(Y | do(X)))` returns either an identifiable expression (back-door / front-door / ID algorithm) or "not identifiable from observational data" — delegated to [y0](https://pypi.org/project/y0/), lazy-imported from an optional adapter.

This spec covers all three. Counterfactual reasoning (Pearl level 3) is **out of scope** — see §10.

### 0.3 First-principles position

We adopt the `gaia.stats` pattern (`docs/superpowers/specs/2026-04-25-unit-stats-constants-design.md`):

- **Kernel layers declare what; they do not compute heavy statistics.** Lang/IR represent causal structure as metadata + schema; they never import scientific computing libraries.
- **Adapters live outside the kernel.** Heavy or narrow-use dependencies ship in `project.optional-dependencies`.
- **Gaia's own BP engine is the default numeric backend.** If the answer can be produced by a graph rewrite plus existing BP, we do that rather than bolting on a second inference library.

Concretely:

| Layer | What it owns | Dependencies |
|---|---|---|
| `gaia.lang.formula.predicate.Causes` | AST marker (exists today via PR #505) | none |
| `gaia.causal.dag` (NEW, kernel) | `CausalDAG` view over a `CollectedPackage` | `networkx` |
| `gaia.causal.intervene` (NEW, kernel) | `do(X=x)` rewrite + `.query(Y)` | reuses `gaia.bp` |
| `gaia.causal.adapters.y0` (NEW, extra) | Symbolic do-calculus identification | `y0` (extra: `gaia[causal-do]`) |

`networkx` is promoted to a kernel dependency (pure Python, ~3MB, no native extensions, widely trusted). `y0` is not — its base install pulls pandas + scikit-learn + statsmodels, which violates the "kernel stays light" rule, and Gaia only uses its symbolic identifier, not its data-driven parts.

---

## 1. Architectural Position

```
┌────────────────────────────────────────────────────────────┐
│  Gaia Lang  (unchanged by this spec — already has Causes)  │
│  ──────────                                                  │
│  PR #505: Variable, Domain, Causes(X, Y), formula AST        │
└────────────────────────┬───────────────────────────────────┘
                         │  Compiler (+ causal lowering §4)
                         ▼
┌────────────────────────────────────────────────────────────┐
│  Gaia IR  (unchanged schema — only metadata enriched)      │
│  ──────────                                                  │
│  Causal claims carry metadata.causal (already in PR #505)    │
│  plus metadata.causal.dag_edge = (cause_id, effect_id)       │
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

Three write surfaces are introduced: a DAG view, an intervention primitive, and an identification adapter. **IR schema is unchanged** — only a new well-known metadata key is added, consistent with how `gaia.stats` evolved.

### 1.1 New `metadata.causal` contract

PR #505 §7.3 reserved `metadata.causal` with shape:

```python
{
    "cause":  {"kind": "variable" | "knowledge", ...},
    "effect": {"kind": "variable" | "knowledge", ...},
}
```

This spec extends it (strictly additively) with the compiled edge identifiers:

```python
{
    "cause":  {...},                            # PR #505
    "effect": {...},                            # PR #505
    # NEW in this spec — populated after compile, used by gaia.causal:
    "dag_edge": {
        "cause_id":  "<QID or CNID>",           # always present
        "effect_id": "<QID or CNID>",           # always present
    },
}
```

`cause_id` / `effect_id` are either compiled QIDs (for Knowledge-typed operands) or synthesized CNIDs (for Variable operands — see §3.1). They coexist in the same field; consumers distinguish them with `gaia.ir.knowledge.is_qid()`.

`dag_edge` is populated by the compiler **after** QID assignment (the same pass that resolves `ClaimAtom` references). Lang runtime never sets it — consumers that need to read the DAG use `dag_edge`; consumers that need provenance back to authored Variables read the original `cause` / `effect`.

### 1.2 `gaia.bp` additions

One public helper is added to `gaia.bp`:

```python
# gaia/bp/factor_graph.py
def mutilate(fg: FactorGraph, intervened: set[str]) -> FactorGraph:
    """Return a new FactorGraph with all factors whose `conclusion` is in
    `intervened` removed. Variables are preserved (priors untouched).
    The caller follows up with fg.observe(x, value) for each intervened var."""
```

This is ~15 lines. It is the only BP-layer change required for the intervention primitive.

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
│   └── factor_graph.py          # + mutilate() helper (§1.2)
├── causal/                      # NEW
│   ├── __init__.py              # public surface
│   ├── dag.py                   # CausalDAG, build_dag()
│   ├── queries.py               # d_sep(), ancestors(), descendants(),
│   │                            #   adjustment_sets()
│   ├── intervene.py             # Intervention, do(), .query()
│   ├── errors.py                # CausalCycleError, NotIdentifiable
│   └── adapters/
│       ├── __init__.py          # (empty — extras are opt-in)
│       └── y0.py                # identify(); lazy imports y0
├── lang/
│   └── dsl/
│       └── causal.py            # NEW: do() DSL, authored in Lang packages
└── lang/
    └── compiler/
        └── compile.py           # + populate metadata.causal.dag_edge
```

### 2.1 Boundaries

- `gaia.causal.dag` **reads** a `CollectedPackage` (or equivalent) and produces a `CausalDAG`. It does not write IR.
- `gaia.causal.queries` operates on a `CausalDAG`. Pure graph algorithms, no IR awareness.
- `gaia.causal.intervene` **reads** a compiled IR artifact, builds a `FactorGraph`, rewrites it (`mutilate`), and runs BP. It does not write IR.
- `gaia.causal.adapters.y0` **reads** a `CausalDAG` and a symbolic query; returns an expression or a `NotIdentifiable` diagnosis. It does not touch `FactorGraph`.
- `gaia.lang.dsl.causal` is the authored-side surface: `do()`, `query()`, thin ergonomic wrappers.

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
    source_claim_qid: str              # which causal claim declared this edge
    prior: float | None                # the claim's prior (strength / agent confidence)

@dataclass
class CausalDAG:
    nodes: frozenset[str]              # QIDs of participating Variables / Claims
    edges: tuple[CausalEdge, ...]
    # Internal NetworkX view (not part of public API; rebuildable from edges):
    _graph: nx.DiGraph
```

Construction:

```python
def build_dag(pkg_or_graph) -> CausalDAG:
    """Walk the compiled artifact's knowledge nodes, pick up every claim
    whose metadata.causal.dag_edge is populated, and assemble a DAG.

    Variables appearing as cause/effect become DAG nodes (they have no
    IR Knowledge — their QID is synthesized from symbol+domain per PR 505 §2.4).
    Knowledge-typed endpoints become DAG nodes under their compiled QID.
    """
```

The node identifier is a **string ID** — not a Python object — so `CausalDAG` is picklable, diffable, and consumable by the JSON renderer. Two kinds of node IDs coexist in a DAG:

- **Knowledge-typed endpoints** (a `ClaimAtom`-based cause/effect): use the compiled Knowledge **QID** directly (`{namespace}:{package}::{label}` per `gaia.ir.knowledge.is_qid`).
- **Variable endpoints**: use a synthesized **causal node ID** (`CNID`). Variables have no IR Knowledge per PR #505 §2.4, so they have no QID; we mint a stable synthetic ID with a visually distinct prefix: `@var:{namespace}:{package_name}:{symbol}`. The `@` prefix makes `is_qid()` return False, so no consumer confuses a CNID with a QID. The CNID is deterministic — identical inputs produce identical IDs across compilations, satisfying the audit-hash requirements of §4.8.

See Open Question 2 (§11) on the declaring-vs-using package question for cross-package Variable references.

### 3.2 Acyclicity is enforced at build time

`build_dag()` runs `nx.is_directed_acyclic_graph(self._graph)` before returning. Failure raises `CausalCycleError` listing the cycle; this plugs into `gaia check causal` (§7).

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

The Obsidian wiki renderer gets a new section per causal claim:

- "**Causal role:** A → B"
- "**Ancestors:** …"
- "**D-separated from:** … given { … }" (when nontrivial)

These wire into `gaia render` through a tiny `render_causal_block(dag, claim_qid)` helper in `gaia.causal.dag` module. The SVG renderer uses directed edges with arrowheads for `Causes`, which visually distinguishes them from `deduction` / `support` edges.

### 3.5 Prior interpretation for a causal claim

The `prior` on a `causal(...)` claim (sugar from PR #505 §5.3) is the agent's confidence that **the causal relation actually holds** — not the marginal of the effect. This is consistent with how PR #505 §4 lowers any claim with a formula: prior = "how much do I believe this claim is true before evidence updates." It means:

- A causal edge can itself be contested / updated by `evidence()` or `infer()` — the DAG has **soft edges** (edge present ⇔ claim true with probability `prior`).
- When downstream causal queries need a definite structure, they use the **MAP structure** (edge retained if its claim's belief > 0.5) unless the caller explicitly asks for ensemble semantics. This is out-of-scope here; the default for v0.6 is: at DAG-build time, every causal claim is treated as structurally present regardless of prior. The prior flows only to the mutilated BP in §4.

### 3.6 Independent Variables and isolated sub-DAGs

A variable never mentioned in any `Causes(...)` is not a DAG node. A package can host multiple disconnected causal sub-DAGs — `CausalDAG` records components; `gaia check causal` warns if a `do()` target is on an isolated component and the user queries a disconnected effect.

---

## 4. Intervention Layer (Spec 2)

The centerpiece. `do(X=x)` is the primitive that separates causal from conditional reasoning.

### 4.1 Authored DSL

```python
# gaia/lang/dsl/causal.py (authored surface)
from gaia.lang.dsl import variable, causal
from gaia.lang.dsl.causal import do, query

co2  = variable("co2_level", Real)
temp = variable("temperature", Real)
G    = variable("greenhouse_gas_other", Real)

causal(G,   co2,  prior=0.8)
causal(G,   temp, prior=0.7)
causal(co2, temp, prior=0.9, describe="...")

# Query at runtime (invoked by `gaia infer --causal` or in an action body):
result = do(co2=1).query(temp)        # numeric P(temp=1 | do(co2=1))
result = query(temp, given_do={co2: 1})   # equivalent long form
```

`do(**assignments)` returns an `Intervention` object; `.query(target)` returns a `CausalQueryResult` carrying the marginal belief.

### 4.2 Intervention object

```python
# gaia/causal/intervene.py
@dataclass(frozen=True)
class Intervention:
    assignments: dict[str, int]   # QID -> {0, 1}

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
    id_expression: str | None = None # symbolic identifier, if computed
```

`belief` is always numerically produced by Gaia BP (it is always *computable* — whether or not it is *identifiable from data alone* is a separate question answered by the optional adapter).

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
    # 1. Lower the compiled local canonical graph to a FactorGraph.
    fg  = lower_local_graph(pkg_artifact.local_canonical_graph)
    # 2. Mutilate: drop all factors whose conclusion ∈ intervened set.
    fg2 = mutilate(fg, set(intervention))
    # 3. Clamp intervened vars to their assigned values.
    for qid, val in intervention.items():
        fg2.observe(qid, val)
    # 4. Run BP via the existing engine and read off target marginal.
    beliefs = InferenceEngine(fg2).run()                  # uses JT exact when treewidth allows
    return CausalQueryResult(
        target_id=target,
        intervention=dict(intervention),
        belief=beliefs[target],
        dag_snapshot=dag,
        factor_graph_digest=_canonical_digest(fg2),       # see §4.8
    )
```

**Why this is correct.** For a DAG with factorization `P(V) = ∏_i P(v_i | pa(v_i))`, Pearl's truncated factorization for `P(V | do(X=x))` is identical to `P(V)` with every `P(x_i | pa(x_i))` replaced by the point mass on `x_i = x`. In Gaia's factor-graph representation, each `P(v_i | pa(v_i))` is exactly one factor whose `conclusion` is `v_i`; removing it and clamping `v_i` via `observe` yields the correct truncated factorization. See §4.5 for the edge case of operator-helper factors.

### 4.4 Integration with existing `Operator` and `Strategy` factors

Claims authored today produce a mix of factor types:

- `CONJUNCTION` / `DISJUNCTION` / `IMPLICATION` / etc. (operator helpers from logical formulas)
- `SOFT_ENTAILMENT` / `CONDITIONAL` (from `deduction` / `infer` strategies)

For the **intervention primitive** to be defined, we need to identify "the factor that encodes `P(v | pa(v))`" for an intervened `v`. The rule:

> `mutilate(fg, intervened)` drops factor `f` iff `f.conclusion ∈ intervened`.

This covers both operator helpers (where `conclusion` is the Knowledge that the operator produces) and strategy factors (where `conclusion` is the strategy's conclusion Knowledge). It correctly handles the common case that a variable is simultaneously the conclusion of a deduction factor and an operand of a downstream operator — only the incoming factor is removed; outgoing factors that use `v` as an input are preserved.

### 4.5 Interaction with strategy-embedded operators (`FormalExpr`)

A `FormalStrategy` may embed multiple `Operator`s inside a `FormalExpr`. When lowered to `FactorGraph` today, each embedded operator produces its own factor with its own helper conclusion. `mutilate` treats them uniformly — any factor whose conclusion is intervened is removed. No special casing is needed at this layer.

### 4.6 Only causally authored intervention is permitted

An intervention is only well-defined over variables that are **DAG nodes** — i.e., participate in at least one `Causes(...)` edge. Attempting `do(X=1)` on a variable that is not a causal DAG node raises `InterventionUndefinedError` with a message pointing the author at `causal(...)` or `Causes(...)`.

This is a deliberate restriction: it prevents users from silently "intervening" on a claim that has only logical / deductive parents, which would be semantically meaningless (you cannot intervene on `(A ∧ B)`).

### 4.7 Target types

`query(target)` accepts:

- A `Variable` reference (compiled to its synthesized QID) — the common case.
- A `Claim` reference (compiled QID) — useful for `do(X=1).query(some_claim)` where the author wants to see the claim's belief under intervention.
- A string QID — the machine-friendly form.

The result's `target_id` is always the compiled QID (for Knowledge targets) or CNID (for Variable targets) regardless of input form.

### 4.8 Deterministic auditability

Every `CausalQueryResult` carries:

- `dag_snapshot` — the causal DAG used.
- `factor_graph_digest` — sha256 of the post-mutilation factor graph (canonicalized per §3.2 of `strategy.py`).

These let a reviewer re-run the query and verify bit-equality. The digest is the primary audit hash; the DAG snapshot is for human inspection.

---

## 5. Symbolic Identification (Spec 3, optional)

### 5.1 Adapter contract

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
    expression: str | None       # y0's rendered Expression when identifiable
    obstruction: str | None      # human-readable witness when not

class MissingDependencyError(ImportError): ...
class NotIdentifiable(Exception): ...
```

### 5.2 Opt-in call site

Identification runs **only on explicit request** — either through a `gaia check causal --identify` CLI flag or a keyword `do(co2=1).query(temp, identify=True)`. When requested and y0 is installed, the `CausalQueryResult` is populated with `identified` and `id_expression`.

This keeps the default path (`do().query()`) dependency-free.

### 5.3 Lazy import pattern

The adapter imports y0 inside the function body; `ImportError` is translated to `MissingDependencyError("install gaia[causal-do] to use do-calculus identification")`. This is the same pattern `gaia.stats.adapters` uses for scipy.

### 5.4 What identification does and does not provide

- ✅ Symbolic guarantee that the numeric answer in `result.belief` **could** have been computed from purely observational data under the DAG.
- ✅ Witness obstruction (e.g., "unblocked back-door path through G") when the query is not identifiable.
- ❌ Estimation uncertainty — that requires real data and is out of scope.
- ❌ Automatic adjustment — Gaia BP already uses all the structure it has; identification is a **meta-assurance** layer on top of the numeric answer.

---

## 6. Compiler Changes

### 6.1 Populate `metadata.causal.dag_edge`

After QID assignment, the compiler walks claims whose formula is a top-level `Causes(X, Y)` (i.e., `kind == CAUSAL`) and writes:

```python
claim.metadata["causal"]["dag_edge"] = {
    "cause_id":  resolve_causal_id(claim.formula.cause),
    "effect_id": resolve_causal_id(claim.formula.effect),
}
```

`resolve_causal_id` is a new helper. For `Knowledge` operands (e.g. a `ClaimAtom` lifted cause) it returns the compiled QID. For `Variable` operands it synthesizes a **CNID** (see §3.1) with the format `@var:{namespace}:{package_name}:{symbol}` — visually distinct from QIDs and guaranteed to fail `is_qid()`.

This is ~20 lines added to `gaia/lang/compiler/compile.py`; no other compiler pass changes.

### 6.2 No new IR schema, no new strategy type

All the new semantics live in metadata and in `gaia.causal`. IR `Operator`, `Strategy`, `StrategyType`, `OperatorType` enums — all unchanged. This is deliberate: IR is the CLI↔LKM protocol contract, and the project policy (CLAUDE.md "Protected Layers") requires a separate PR for any IR schema change.

### 6.3 Migration concern: existing `CAUSAL` claims

Any package authored against PR #505 that declares `causal(...)` claims today produces IR artifacts without `metadata.causal.dag_edge`. Handling:

- `build_dag` tolerates missing `dag_edge` by falling back to `metadata.causal.cause` / `.effect` — rereading the pre-QID descriptor and resolving QIDs at DAG-build time. This pays a small cost per build but removes a migration step.
- Re-compiling a package with v0.6 populates `dag_edge` definitively; the reviewer prefers `dag_edge` when present.

---

## 7. `gaia check causal`

A new CLI sub-check. Invoked as `gaia check causal <package>` or bundled into `gaia check` when a package contains any `CAUSAL` claim.

### 7.1 Rules

| Rule | Severity | Triggered by |
|---|---|---|
| Acyclicity | Error | `CausalCycleError` from `build_dag` |
| Intervention target is a DAG node | Error | `InterventionUndefinedError` on any authored `do(...)` |
| Confounded causal claim | Warning | For every `Causes(X, Y)` claim, `!d_separated(X, Y, given=∅)` is expected; but if the observed condition `d_separated(X, Y, given=ancestors(X) ∪ ancestors(Y))` also fails, surface "this causal claim does not imply conditional independence of X, Y given observed confounders — clarify the underlying SCM assumptions" |
| Identification (opt-in) | Info / Warning | Requires `--identify`; emits obstruction witness per non-identifiable authored `do()` |
| Variable reuse across sub-DAGs | Warning | The same Variable appearing in disconnected components — likely an authoring error |

### 7.2 Output format

JSON, keyed by rule. Fits into the existing `gaia check` aggregated report so reviewers get one unified view.

---

## 8. DSL Surface Summary

```python
# Authoring (unchanged from PR #505)
c = causal(X, Y, prior=0.9, describe="...")          # already shipped

# Queries (NEW)
from gaia.lang.dsl.causal import do, query

result = do(co2=1).query(temp)                       # numeric
result = do(co2=1).query(temp, identify=True)        # numeric + symbolic (needs extra)
result = query(temp, given_do={co2: 1})              # long form
```

```python
# Library (NEW, for tool authors / reviewers)
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
# → IdentificationResult(identifiable=True, expression="...")
# or IdentificationResult(identifiable=False, obstruction="back-door path via G")
```

---

## 9. Implementation Milestones

Four independent PR slices, strictly ordered.

### Milestone D₁ — Causal structure layer (Spec 1)

Depends on: PR #505 (merged).

- **Compiler:** populate `metadata.causal.dag_edge` for `CAUSAL` claims (§6.1).
- **`gaia.causal.dag`:** `CausalDAG`, `CausalEdge`, `build_dag`. Cycle detection.
- **`gaia.causal.queries`:** `ancestors`, `descendants`, `parents`, `children`, `d_separated`, `adjustment_sets`.
- **`gaia.causal.errors`:** `CausalCycleError`, `InterventionUndefinedError`.
- **`pyproject.toml`:** `networkx>=3` added to base dependencies.
- **Renderer hook:** per-claim "Causal role" section in Obsidian wiki output.
- **Tests:** DAG construction, acyclicity, d-separation parity with textbook examples (confounder, chain, collider), adjustment-set enumeration on canonical DAGs.

Independently shippable: enables `gaia check causal`, makes renderings causal-aware, but does not yet execute interventions. Roughly 2–3 weeks.

### Milestone D₂ — Intervention primitive (Spec 2)

Depends on: D₁.

- **`gaia.bp.factor_graph.mutilate`:** helper function (§1.2, §4.3).
- **`gaia.causal.intervene`:** `Intervention`, `CausalQueryResult`, `_compute` using `mutilate` + Gaia BP.
- **`gaia.lang.dsl.causal`:** `do()`, `query()` surface.
- **`gaia check causal`:** acyclicity, intervention-target, variable-reuse rules (§7.1).
- **Tests:** smoked against canonical SCMs (confounder, front-door, chain, collider); belief values compared against hand-computed truncated factorizations; audit digests reproducible.

Independently shippable: Gaia can answer `P(Y | do(X))` numerically for any DAG. Roughly 3–4 weeks (much of the work is tests and edge cases, not algorithm — `mutilate` is ~15 lines).

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
- `gaia-lang` docs: `do()` / `query()` reference; worked examples (Pearl's smoking/genetics, Simpson's paradox).
- Audit first-party packages (Mendel, Galileo, Superconductivity) for any claim that would benefit from a `causal(...)` rewrite — do not force, but list candidates in a follow-up issue.

---

## 10. Out of Scope / Deferred

| Item | Why deferred |
|---|---|
| **Counterfactual queries (Pearl level 3)** | Requires explicit exogenous noise variables, parameterized structural equations, and a different inference mode (abduction–action–prediction or twin networks). Gaia's propositional claim + prior model is not a structural causal model; promoting it would be a major world-view surgery. We will reopen this conversation only when a concrete scientific-reasoning use case demands it. |
| **Causal discovery from data** | Gaia is a symbolic / prior-based reasoning system; DAG structure is authored, not learned. Tools like `causal-learn` or `causalnex` exist for that purpose and are external to our scope. |
| **Continuous / parameterized structural equations** | Gaia claims are Boolean; numeric values live in Variables with priors, not as draws from a structural equation. Promoting Gaia to continuous SCMs is equivalent to replacing the BP engine with pyro/numpyro — out of scope. |
| **`pgmpy` adapter** | Gaia BP already answers the numeric intervention question. Adding pgmpy would be a second inference engine with no additional capability. |
| **Front-door / back-door automatic adjustment in numeric BP** | Gaia BP already marginalizes over unobserved confounders that are DAG-connected — no additional "automatic adjustment" is needed or defined. `adjustment_sets()` in §3.3 is for *reviewer* use (auditing which covariates would need to be observed if working from data). |
| **Hidden confounders / ADMGs / Ananke integration** | v0.7 topic — requires lattice of bidirectional edges. |
| **Multi-world / soft interventions (shift / conditional do-operators)** | Out of scope — single-atomic intervention covers the core use case. |

---

## 11. Open Questions

1. **MAP vs. ensemble causal structure.** §3.5 states that DAG-build treats every `CAUSAL` claim as structurally present regardless of prior. Is there a use case (reviewer workflow?) where the user wants `d_separated` computed against the *MAP* DAG (edges with belief > 0.5 only)? If yes, we add a `build_dag(..., policy="map" | "structural")` knob — otherwise, leave it out of v0.6.
2. **Variable CNID synthesis.** §3.1 proposes `@var:{namespace}:{package_name}:{symbol}`. Conflict to resolve: when a Variable is declared in package A but used in a `Causes(...)` claim in package B, do we stamp the CNID with the *declaring* package or the *using* package? Proposal: declaring package — matches how PR #505 proposes cross-package Variable lookups. The `@` prefix ensures `is_qid()` returns False so no consumer confuses a CNID with a Knowledge QID.
3. **Default stance on `do()` target that is not a DAG node.** §4.6 raises an error. An alternative is a warning + fall through to conditioning. Recommendation: error — silent "meaningless intervention" is the exact footgun the causal layer is meant to prevent.
4. **Does `causal()` sugar need a `noise` parameter now?** For Gaia BP to treat a `Causes(X, Y)` as a proper conditional `P(Y | X=x, pa(Y) \ {X})`, we eventually need a CPT or at least a noisy-OR-style parameter on the edge. **Proposal for v0.6:** reuse the existing `prior` field as the noisy-OR leak parameter; `causal(X, Y, prior=0.9)` means `P(Y=1 | X=1, other_causes=0) ≈ 0.9`. Document this as a simplification, flag for re-examination if users need full CPTs.
5. **Identification output format.** Raw y0 `Expression.to_latex()` vs. a Gaia-normalized string with QIDs. Recommendation: LaTeX for v0.6 (copy-paste into paper / wiki); a Gaia-native form can come later.

---

## 12. Examples

### 12.1 Pearl's smoking / genetics (confounding)

```python
from gaia.lang.dsl import variable, causal, Real, Bool
from gaia.lang.dsl.causal import do

G = variable("G", Bool,  describe="Genetic predisposition")
X = variable("X", Bool,  describe="Smoking")
Z = variable("Z", Bool,  describe="Yellow fingers")
Y = variable("Y", Bool,  describe="Lung cancer")

causal(G, X, prior=0.6)
causal(G, Y, prior=0.7)
causal(X, Z, prior=0.9)
# No X → Y edge — smoking does not directly cause cancer in this toy model.

from gaia.causal import build_dag, d_separated, adjustment_sets
dag = build_dag(pkg)
assert not d_separated(dag, "@var:github:pkg:X", "@var:github:pkg:Y")                            # observed assoc
assert     d_separated(dag, "@var:github:pkg:X", "@var:github:pkg:Y", {"@var:github:pkg:G"})     # controlled for G
print(adjustment_sets(dag, "@var:github:pkg:X", "@var:github:pkg:Y"))                            # [{G}]

r1 = do(X=1).query(Y)          # P(Y | do(X=1)) — ≈ base rate of cancer
r2 = query(Y, given={X: 1})    # P(Y | X=1)     — elevated by confounding
# r1.belief < r2.belief — the exact effect that disappears under intervention.
```

### 12.2 Simpson's paradox (Gaia surfaces it automatically)

Given a DAG where `X → Y`, `Z → X`, `Z → Y`, authored claims naturally allow `do(X).query(Y)` to give the unconfounded effect, while `query(Y, given={X: 1})` aggregates over `Z` and can reverse direction. `gaia check causal` (no flags) simply reports the DAG; with `--identify`, y0 confirms `P(Y | do(X))` is identifiable via back-door over `Z`.

### 12.3 Multi-step intervention

```python
T = variable("T", Bool, describe="Treatment")
S = variable("S", Bool, describe="Side effect mitigation")
R = variable("R", Bool, describe="Recovery")

causal(T, S, prior=0.7)
causal(T, R, prior=0.6)
causal(S, R, prior=0.5)

do(T=1, S=1).query(R)         # compound intervention: force treatment and mitigation
```

---

## 13. Prior-Art Anchors

- Pearl, *Causality* (2nd ed., 2009) — DAG semantics, do-operator, back-door / front-door.
- Pearl & Mackenzie, *The Book of Why* (2018) — levels of the causal ladder.
- Shpitser & Pearl, "Identification of Conditional Interventional Distributions" (2006) — IDC algorithm y0 implements.
- [y0](https://github.com/y0-causal-inference/y0) — symbolic do-calculus implementation (adapter target).
- [NetworkX](https://networkx.org/) — DAG infrastructure (promoted to kernel dep).
- PR #505 — claim formula schema (immediate predecessor; supplies `Causes`, `Variable`, `Domain`).
- `docs/superpowers/specs/2026-04-25-unit-stats-constants-design.md` — kernel-vs-adapter separation template.
