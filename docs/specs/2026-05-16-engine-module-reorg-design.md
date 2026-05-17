# `gaia.engine` Module Reorganization Design

**Status:** Design proposal for v0.5 follow-up
**Date:** 2026-05-16
**Branch:** off `v0.5`
**Related PRs:** TBD (reorg PR a + reorg PR b)
**Builds on:** alpha-0 engine facade split (PR #607); BayesInference shape decision in `docs/specs/2026-05-15-causal-cleanup-reasoning-shapes.md` is one of several catalysts but not the only one.
**Scope:** Coordinated reorganization of first- and second-level modules under `gaia.engine`, sequenced as two PRs:
  1. **PR a (small, low-risk)** — consolidate single-file packages and demote `engine.logic/` to `engine.ir.logic/`
  2. **PR b (medium)** — promote `engine.lang.bayes/` to peer `engine.bayes/` and align the Bayes verb directory name with the lang convention

**Non-goals:** Do not flatten the entire engine into a single layer. Do not rename `engine.lang/` to `engine.core/`. Do not move `lang.runtime/`, `lang.dsl/`, `lang.compiler/` out of `lang/`. Do not introduce a new IR data model. Do not change BP, inquiry, or trace top-level layout. Do not add a post-v0.5 deprecation layer for the pre-release `lang -> bayes` public shortcut.

> **PR #630 update:** Because v0.5 has not shipped, PR b now uses a clean break for Bayes import paths: remove the old `gaia.engine.lang.bayes` namespace and the `gaia.engine.lang` bayes shortcut instead of tombstoning or aliasing them. The canonical public import is `import gaia.engine.bayes as bayes`; the remaining `lang -> bayes` references are internal implementation hooks until the compiler-extension registry lands.

## 1. Goal

Align the `gaia.engine` module layout with the conceptual structure of the engine — applying cohesion, dependency direction, API surface, and evolution-pressure criteria (§3) — and set explicit precedents for future extension modules so they don't inherit accidental decisions.

Since alpha-0 (PR #607) split engine code into `gaia.engine.{bp, ir, lang, logic, inquiry, trace, packaging}` sub-facades, four organizational issues have accumulated. They are independent in cause but share the same diagnostic framework:

| # | Issue | Affected path | Criterion violated |
|---|---|---|---|
| 1 | Single-file package shell with one file and no second contributor | `engine.lang.types/primitives.py` | Cohesion (§3 criterion 1) |
| 2 | Top-level peer with no Gaia-native abstractions — pure sympy-on-IR adapter | `engine.logic/propositional.py` | Cohesion + dependency direction (§3 criteria 1, 2) |
| 3 | Module path inconsistent with the runtime-class hierarchy | Bayes nested 5 levels deep at `engine.lang.bayes/*` despite `BayesInference(Reasoning)` being a first-class shape | Evolution pressure (§3 criterion 4) |
| 4 | Naming asymmetry between core and extension verb directories | `engine.lang.dsl/` vs `engine.lang.bayes.verbs/` | API surface (§3 criterion 3) |

None of these resolve themselves through normal feature work. Issue 3 in particular has accumulating cost — every future reasoning family (the speculative `CausalEdge` from `2026-05-15-causal-cleanup-reasoning-shapes.md` §6, potential statistics/frequentist extensions, ML / latent-variable extensions) will inherit either the deep-nesting precedent or get a one-off carve-out, neither of which is good.

The spec groups the four issues into two coordinated PRs by code-touch shape:

- **PR a** (issues 1 + 2) — both are removals of top-level / sub-package shells. Pure path moves with tombstone shims; ~120 LoC; one ImportError test per old path.
- **PR b** (issues 3 + 4) — both involve the Bayes subtree. PR b is the larger change because it touches every Bayes-using import in the repo plus the two surviving internal `lang -> bayes` reverse-import sites at `lang/compiler/compile.py` and `lang/runtime/distribution.py`, while the pre-release public shortcut is removed (see §6.2).

The motivation is **structural, not feature-driven**. Issue 3 is the largest in code-touch and creates the most pressure because the runtime/module mismatch is the most explicit, but issues 1, 2, and 4 are independent organizational debts that this spec resolves in the same window because they share the diagnostic framework and tooling (tombstone machinery, facade contract test, doc reference layer).

## 2. Current Code Facts

(based on current `origin/v0.5`, i.e. v0.5 after PR #606 and PR #609)

```
gaia/engine/
├── _stale_check.py
├── packaging.py
├── bp/                        # 10 modules — Belief Propagation engine
├── inquiry/                   # 13 modules — goal-tree analysis
├── ir/                        # 12 modules — Intermediate Representation
├── lang/
│   ├── runtime/               # 11 modules — Knowledge / Reasoning / Scaffold dataclasses
│   ├── compiler/              # 5 modules — lang AST → IR
│   ├── dsl/                   # 15 modules — public verbs (derive, equal, ...)
│   ├── formula/               # 5 modules — predicate logic AST
│   ├── bayes/                 # ← extension nested inside lang
│   │   ├── runtime/
│   │   ├── verbs/             # ← naming inconsistent with lang.dsl/
│   │   ├── compiler/
│   │   ├── distributions/
│   │   └── adapters/
│   ├── refs/                  # 6 modules — @label resolution
│   ├── review/                # 3 modules — review manifest gen
│   └── types/                 # ← single file (primitives.py)
├── logic/                     # ← single file (propositional.py); only top-level peer with no own abstraction
└── trace/                     # 9 modules
```

Tombstone infrastructure (`gaia/_legacy_imports.py`) is already in place for the alpha-0 `gaia.<old> → gaia.engine.<new>` migration:

- `_tombstoned_namespace_getattr(old, new)` redirects attribute access
- `TOMBSTONED_NAMESPACES` dict registers the redirects; meta-path finder picks them up for `import gaia.<old>.<sub>` style imports
- `tests/baseline/test_l2_tombstones.py` enforces the registry contract

This spec reuses that machinery for new tombstones.

## 3. First-Principles Criteria

A module organization is judged by how much it lowers three costs:

- **Cognitive cost** — how much effort to find the right file
- **Coupling cost** — how many files change together for one feature
- **Boundary cost** — cross-module import / cyclic risk / dependency direction

Four objective tests:

1. **Cohesion** — files that change together must live together
2. **Dependency direction** — imports form an acyclic, single-direction graph
3. **API surface** — short, stable public import paths
4. **Evolution pressure** — where does the next thing naturally go

This spec applies these criteria to each diagnosed issue.

## 4. Diagnosis

### 4.1 Bayes nested under `lang/` violates evolution pressure (criterion 4)

PR #606 + #609 established `BayesInference(Reasoning)` as a first-class runtime category (a sibling of `Directed`/`Relation`/`Decompose`/`Compose`). When future extensions land — e.g., causal (the speculative `CausalEdge` from `2026-05-15-causal-cleanup-reasoning-shapes.md` §6), or statistics — they should follow the same precedent. With the current layout that precedent says: nest under `engine.lang/`. That makes `engine.lang/` a perpetual junk drawer of "everything authoring-related" and implicitly contradicts the BayesInference decision (which carved Bayes out as runtime-first-class).

The fix: promote `bayes/` to be a peer module under `engine/`. This sets a clean precedent — new reasoning families land as `engine.<family>/`, not `engine.lang.<family>/`.

### 4.2 `engine.logic/` has no own abstraction; it is an IR consumer (criterion 1, 2)

By the cohesion + dependency-direction criterion, top-level engine peers are characterized by owning their own data model:

| Top-level peer | Own abstractions | Files |
|---|---|---|
| `engine.bp/` | `FactorGraph` / `Potential` / `JunctionTree` / `MeanFieldEngine` | 10 |
| `engine.inquiry/` | `ProofState` / goal-tree / `ReviewTarget` / `Anchor` / `Snapshot` | 13 |
| `engine.lang/` | `Knowledge` / `Reasoning` / `Scaffold` / formula AST | 50+ |
| `engine.ir/` | (the data hub itself) | 12 |
| `engine.trace/` | trace records / ranking / hashing | 9 |
| `engine.logic/` | **none** — pure sympy-on-IR adapter | 1 |

`engine.logic/` is the outlier. Its public functions all have signature `(graph: LocalCanonicalGraph, knowledge_id: str) → sympy.Expr`. It defines no Gaia data classes, persists nothing, and consumes IR exclusively. Structurally it is the same kind of module as `engine.ir.coarsen`, `engine.ir.linearize`, `engine.ir.validator` — IR analysis utilities — except it uses an external solver (sympy) as backend.

The fix: demote `engine.logic/` to `engine.ir.logic/` (sub-package). The IR-consumer relationship becomes explicit; future solver backends (Z3, CVC5, ATP) join the same sub-package. If logic ever grows substantial own abstractions (e.g., a unified `Theory` data model spanning solvers, with caching and proof certificates), it can be promoted back to a top-level peer at that point. YAGNI says don't anticipate.

### 4.3 `engine.lang.types/` is single-file over-structure (criterion 1)

Contents: `primitives.py` exporting `Bool`, `Nat`, `Real`, `Probability`, `PrimitiveType`. These are formula-domain primitive types — used by `lang.formula.term.Variable.domain`, by `lang.formula.predicate` for term type checking, and by `Claim.formula` payloads. They have no second contributor in the package and no theoretical reason to sit in their own namespace.

The fix: merge into `lang.formula/primitives.py`.

### 4.4 `lang.dsl/` vs `bayes.verbs/` naming inconsistency (criterion 3)

Both directories serve the same role: public verb entry. The current names diverge because `lang.dsl/` has historically held more than verbs (formula factories, sugar, legacy strategies) while `bayes.verbs/` has only `model.py` and `likelihood.py`. After Bayes promotes to peer, the asymmetry becomes visible in import paths:

```python
from gaia.engine.lang.dsl import derive
from gaia.engine.bayes.verbs import model       # ← inconsistent
```

The fix: rename `bayes.verbs/` → `bayes.dsl/`. Future Bayes-side sugar/factories land in `bayes.dsl/sugar.py` etc., matching the lang convention.

### 4.5 What is NOT diagnosed as a problem

- **`lang.runtime/`, `lang.dsl/`, `lang.compiler/` placement under `lang/`**: these form a tight cohesion triangle. Adding any new core reasoning verb requires touching all three. They must stay together. Promoting them to engine top-level breaks the triangle and increases coupling cost.

- **`lang/` name as host module**: in the runtime-class hierarchy `bayes` extensions inherit from `lang.runtime` base classes and reuse `lang.compiler` / `lang.formula` / `lang.refs` / `lang.review` services. The `lang -> bayes` module-import graph keeps only limited internal reverse imports (§6.2), while the runtime-class direction is host-to-extension, not peer-to-peer. Renaming `lang` to `core` would imply a flat peer relation, which the runtime-class hierarchy does not have. Keep the `lang` name; §6 documents both the runtime-class host/extension semantics and the module-import reality.

- **`compiler` co-location**: `lang.compiler/` and `bayes.compiler/` (post-promotion) stay separate per current code; they are cohesive within their own authoring layers and do not benefit from forced unification.

## 5. Logic Layer Architecture

The `engine.logic` demotion in §4.2 motivates an explicit articulation of how logical analysis is split across module boundaries. Three scopes coexist; they are not redundant.

### 5.1 Three scopes of logical structure

| Scope | What it is | Where the structure lives | Where the analysis goes |
|---|---|---|---|
| **A. Within-claim** | one-claim predicate logic: quantifiers, predicates, terms, arithmetic (`Forall(x, Greater(f(x), 0))` inside a single `Claim.formula`) | `lang.formula` AST + IR `formula_atom` metadata after lowering | (none today) — `engine.ir.logic.predicate` (future Z3-backed) |
| **B. Between-claim** | propositional connectives linking claims (`claim_a ∧ claim_b → helper`), produced by IR Operator nodes | IR `LocalCanonicalGraph.operators` | `engine.ir.logic.propositional` (current sympy backend) |
| **C. Cross-cutting** | analysis spanning A + B (e.g., `Forall(x, P(x))` claim contradicts `Lnot(P(b))` claim — needs both formula metadata and Operator graph) | both | (none today) — `engine.ir.logic.predicate` or `engine.ir.logic.smt` (future) |

### 5.2 What the IR preserves vs collapses

When `lang.compiler.lower_formula` lowers a `Claim` with `formula = Forall(x in Real, Greater(f(x), 0))`:

- top-level connectives (`Land/Lor/Lnot/Implies/Iff` at the formula root) → lowered to IR `Operator` nodes between knowledge nodes (B-scope structure)
- top-level quantifiers / predicates / arithmetic (`Forall/Exists/Equals/Greater/UserPredicate` at the root) → preserved as JSON metadata on the Knowledge node (`metadata["formula_atom"]`, `metadata["formula_bindings"]`); the Knowledge becomes opaque from the Operator graph's perspective (A-scope structure preserved but not active)

The IR therefore contains **all the information needed for A and C scope analysis** — the metadata is complete. What is missing is the **active analyzer** that reads `formula_atom` metadata and feeds it to a first-order / SMT solver.

The current `engine.logic.propositional` only walks `graph.operators` and ignores metadata. It covers scope B exhaustively and scope A/C not at all.

### 5.3 Why all three scopes belong in `engine.ir.logic/`

Scope A might naively appear to belong with `lang.formula/` (since `Forall/Equals/...` are formula AST nodes). But the analyzer's input is **not** the AST — by the time analysis runs, the formulas have been lowered to IR with metadata. The analyzer takes IR + metadata, not raw AST. Putting it in `lang.formula/` would force `lang.formula/` to depend on IR (wrong direction) and on Z3 (heavy dep on a data layer).

Scope C inherently combines IR Operator graph with claim-internal metadata; it has nowhere to live except IR-level.

Therefore: all three logic scopes' analyzers belong under `engine.ir.logic/` as additional backends. The current sympy `propositional.py` is the first; future FOL/SMT backends are siblings.

### 5.4 What `lang.formula/` retains

Pure AST utilities, not "logic analysis":

- `is_formula(x)` (type check)
- atom collection (walk `ClaimAtom` nodes)
- variable binding extraction (used during lowering)
- well-formedness checks (`_check_term`, decompose validation)

These are syntactic helpers tied to AST structure. They do not need solvers; they live close to their callers (`lang.formula.predicate`, `lang.dsl.decompose`, `lang.compiler.lower_formula`).

## 6. Host vs Extension — Two Layers, Different Today's Realities

After PR b lands, `engine.lang/` and `engine.bayes/` are **not symmetric peers** in the runtime-class hierarchy, but **today's module-import graph is bidirectional**, not unidirectional. This section is precise about which layer carries the host/extension semantics and which layer does not, because PR b only addresses one of the two.

### 6.1 Runtime-class layer (clean host/extension)

`bayes.* → lang.*` (extension built on host):

- `bayes.runtime.actions.BayesInference` inherits `lang.runtime.action.Reasoning`
- `bayes.runtime.actions.PredictiveModel / Likelihood` inherit `BayesInference`
- `bayes.compiler.*` uses helpers from `lang.compiler.*`
- `bayes.runtime.actions.Likelihood` constructs `lang.runtime.action.Contradict / Exclusive` via the auto-structural mechanism
- `bayes.*` consumes the formula AST in `lang.formula.*`

This is what the BayesInference shape decision (`2026-05-15-causal-cleanup-reasoning-shapes.md` §4.2) sets up: a runtime-class hierarchy where Bayes records are formal extensions of the base `Reasoning` hierarchy. Nothing in `lang.runtime.action` inherits from anything in `bayes`.

### 6.2 Module-import layer (limited internal reverse imports)

`lang.* -> bayes.*` still exists only where the host needs extension implementations:

| Site | What it does |
|---|---|
| `gaia/engine/lang/compiler/compile.py::_lower_bayes_actions` | Calls `from gaia.engine.bayes.compiler import lower_bayes_claims` inside the core compile pipeline |
| `gaia/engine/lang/runtime/distribution.py` (10+ sites) | Top-level distribution factories `Normal / LogNormal / Beta / Exponential / Gamma / StudentT / Cauchy / ChiSquared / Binomial / Poisson` lazy-import their backing implementations from `bayes.distributions.*` and `bayes.adapters.scipy_backend` |

The pre-release `lang.__init__` public shortcut was removed in PR #630 because v0.5 has not shipped yet. Users should import Bayes from `gaia.engine.bayes`; `gaia.engine.lang.__all__` does not include `bayes`.

So the import graph is:

```
bayes.runtime -> lang.runtime           (extension extends host runtime classes)
bayes.compiler -> lang.compiler          (extension reuses host compile helpers)
bayes.* -> lang.formula / lang.refs / lang.review   (shared services)
bayes.* -> engine.ir / engine.bp        (downstream)

lang.compiler.compile -> bayes.compiler  (Bayes lowering hook)
lang.runtime.distribution -> bayes.distributions / bayes.adapters
                                      (top-level Distribution factories
                                       delegate to Bayes implementations)
```

### 6.3 What PR b does (and does not) about the bidirectional layer

PR b scope is path migration plus clean-break removal of the pre-release public alias:

- move the directory tree `engine/lang/bayes/` -> `engine/bayes/`
- update the two surviving internal reverse-import sites above to point at the new path:
  - `lang/compiler/compile.py::_lower_bayes_actions` `from gaia.engine.lang.bayes.compiler import ...` -> `from gaia.engine.bayes.compiler import ...`
  - all `lang/runtime/distribution.py` `from gaia.engine.lang.bayes.{distributions,adapters} import ...` -> `from gaia.engine.bayes.{distributions,adapters} import ...`
- remove the `lang/__init__.py` bayes shortcut and delete the old `engine/lang/bayes/` package instead of installing a tombstone

PR b does **not** eliminate the remaining internal reverse imports. The reasons:

1. v0.5 has not shipped, so the pre-release public Bayes shortcut can be removed without a deprecation cycle.
2. Top-level distribution factories `Normal / Beta / ...` under `lang.runtime.distribution` are part of the v0.5 documented surface; relocating them is its own Bayes-API design question.
3. `compile._lower_bayes_actions` is a hard-coded lowering hook into Bayes. Cleanly replacing it with a lang-only contract requires designing a plugin/registry mechanism — substantial follow-up work.

PR b therefore preserves the runtime-class host/extension structure while leaving only the necessary internal module-import reverse links. The path migration is justified by the precedent argument in §4.1 (BayesInference is runtime-first-class; its module path should match) without overloading PR b with a decoupling refactor.

### 6.4 Naming questions answered

1. *"Should `lang/` be renamed `core/` for symmetry with `bayes/`?"* — No. The runtime-class direction is host/extension (§6.1) and `lang` accurately names the host. The limited internal reverse imports (§6.2) do not turn `lang/` into a peer of `bayes/`; lang is still the host that consumes the few extension-implemented services retained for distribution factories and Bayes lowering.

2. *"Why does `bayes.runtime` mirror `lang.runtime` while `lang.runtime` does not have a `bayes/` subdirectory?"* — Because each extension owns its own Reasoning subclasses and verbs but reuses the host's base hierarchy. The mirror is structural, not hierarchical.

### 6.5 Future-extension contract

> Any new reasoning family that introduces its own runtime classes (e.g., `CausalEdge` per `2026-05-15-causal-cleanup-reasoning-shapes.md` §6) lands as a peer module under `gaia.engine.<family>/`, not under `gaia.engine.lang.<family>/`. The peer module follows the same internal layout as `gaia.engine.bayes/`: at minimum `runtime/` + `dsl/`; optionally `compiler/`, `distributions/`, `adapters/` as needed. The peer extension freely imports from `gaia.engine.lang.*` (host) and `gaia.engine.ir/` / `engine.bp/` (downstream).
>
> Whether the host imports back from the new extension (mirroring today's limited `lang -> bayes` reverse imports for distribution factories and compile hooks) is a per-extension decision, not a default; it should be flagged explicitly when the extension's design spec is written, and a follow-up to §13's "Lang/Bayes import isolation" should consider the new extension's reverse-import sites.

## 7. Target State

After both PRs land:

```
gaia/engine/
├── _stale_check.py
├── packaging.py
├── lang/                          # host: core authoring + shared services
│   ├── runtime/
│   ├── dsl/
│   ├── compiler/
│   ├── formula/
│   │   ├── connective.py
│   │   ├── predicate.py
│   │   ├── primitives.py          # ← merged from engine.lang.types/
│   │   ├── quantifier.py
│   │   ├── symbols.py
│   │   └── term.py
│   ├── refs/
│   └── review/
├── bayes/                         # peer extension (promoted from engine.lang.bayes)
│   ├── runtime/
│   ├── dsl/                       # ← renamed from verbs/
│   ├── compiler/
│   ├── distributions/
│   ├── adapters/
│   └── README.md
├── ir/
│   ├── coarsen.py / linearize.py / validator.py / formalize.py / ...
│   └── logic/                     # ← demoted from engine.logic/
│       ├── __init__.py
│       └── propositional.py       # current sympy backend; siblings (predicate/smt/...) added later
├── bp/
├── inquiry/
└── trace/
```

**Disappearing as canonical implementation namespaces:** `engine.lang.types/`, `engine.logic/`, `engine.lang.bayes/`. PR-a old directories remain as tombstone shims where needed; the pre-release `engine.lang.bayes/` package is deleted.
**Appearing:** `engine.bayes/`, `engine.ir.logic/`.
**Renamed inside `bayes/`:** `verbs/` → `dsl/`.
**Untouched:** `lang.runtime/`, `lang.dsl/`, `lang.compiler/`, `lang.refs/`, `lang.review/`, `ir/*` other than the new `logic/` subdir, `bp/`, `inquiry/`, `trace/`, `_stale_check.py`, `packaging.py`.

## 8. Migration Plan

Two sequenced PRs to minimize blast radius and let reviewers focus on one structural argument at a time.

### 8.1 PR a — Single-file consolidation + logic demotion

**Scope:** Two file moves, two new tombstone shims, two new namespace registry entries, no semantic changes.

| File | Action |
|---|---|
| `gaia/engine/lang/types/primitives.py` | Move to `gaia/engine/lang/formula/primitives.py` |
| `gaia/engine/lang/types/__init__.py` | **Replace contents** with the 4-line tombstone shim (see below) — directory kept |
| `gaia/engine/logic/propositional.py` | Move to `gaia/engine/ir/logic/propositional.py` |
| `gaia/engine/logic/__init__.py` | **Replace contents** with the 4-line tombstone shim — directory kept |
| `gaia/engine/ir/logic/__init__.py` | **New file** with explicit scope notes (see below) |
| `gaia/logic/__init__.py` | **Retarget existing alpha-0 shim** from `gaia.engine.logic` to `gaia.engine.ir.logic` |

The tombstone shim follows the alpha-0 convention used by `gaia/bp/__init__.py`, `gaia/lang/__init__.py`, etc.:

```python
"""Alpha 0 tombstone — gaia.engine.lang.types relocated to gaia.engine.lang.formula."""

from gaia._legacy_imports import _tombstoned_namespace_getattr

__getattr__ = _tombstoned_namespace_getattr(
    "gaia.engine.lang.types", "gaia.engine.lang.formula"
)
```

Tombstones added to `TOMBSTONED_NAMESPACES`:

```python
"gaia.engine.lang.types": "gaia.engine.lang.formula",
"gaia.engine.logic": "gaia.engine.ir.logic",
```

Existing entry updated:

```python
# old: "gaia.logic": "gaia.engine.logic"
"gaia.logic": "gaia.engine.ir.logic",
```

Existing top-level tombstone shim updated:

```python
# old: _tombstoned_namespace_getattr("gaia.logic", "gaia.engine.logic")
__getattr__ = _tombstoned_namespace_getattr("gaia.logic", "gaia.engine.ir.logic")
```

`gaia/engine/lang/__init__.py`: continue re-exporting `Bool, Nat, Real, Probability, PrimitiveType` so user-facing import `from gaia.engine.lang import Bool` keeps working unchanged.

Update `gaia/engine/ir/logic/__init__.py` (new file) with explicit scope notes per §5:

```python
"""Logic backends for compiled Gaia IR.

Provides solver-backed analysis of the IR's logical structure. Backends use
external libraries (sympy, future Z3/CVC5) while keeping `gaia.engine.ir`
data classes free of solver dependencies.

Current scope:
    propositional — sympy-based analysis of claim-level Operator graphs
        (NEGATION/CONJUNCTION/DISJUNCTION/IMPLICATION/EQUIVALENCE/
        CONTRADICTION/COMPLEMENT). Treats Knowledge nodes as atoms; does
        not look inside Claim.formula metadata.

Future (out of scope for this PR; tracked separately):
    predicate — first-order / SMT backends consuming `formula_atom` metadata
        for claim-internal predicate / quantifier / arithmetic analysis.
    smt — cross-cutting analysis combining Operator graph with claim-internal
        formula metadata.

See docs/specs/2026-05-16-engine-module-reorg-design.md §5 for the three-scope
taxonomy.
"""
```

Estimated diff: ~120 lines (file moves + tombstone updates + new `__init__.py` + path rewrites in tests / examples / docs that use the old paths).

### 8.2 PR b — Bayes promotion + verbs/dsl rename

**Scope:** One subtree move, one internal rename, repo-wide import-path updates, and clean-break deletion of the pre-release old Bayes namespace. The two surviving reverse-import sites are internal implementation hooks in `lang/`.

| File / Directory | Action |
|---|---|
| `gaia/engine/lang/bayes/` (entire subtree) | Move to `gaia/engine/bayes/`; delete the old package path |
| `gaia/engine/bayes/verbs/` (post-move) | Rename to `gaia/engine/bayes/dsl/` |

No `TOMBSTONED_NAMESPACES` entry is added for `gaia.engine.lang.bayes`: v0.5 has not shipped, so old pre-release Bayes paths are removed instead of redirected.

Repo-wide import-path rewrites — three categories:

1. **External callers** (tests, examples, package code, docs):
   - `from gaia.engine.lang import bayes` -> `import gaia.engine.bayes as bayes`
   - `from gaia.engine.lang.bayes import ...` -> `from gaia.engine.bayes import ...`
   - `from gaia.engine.lang.bayes.runtime import ...` -> `from gaia.engine.bayes.runtime import ...`
   - `from gaia.engine.lang.bayes.verbs import ...` -> `from gaia.engine.bayes.dsl import ...`

2. **Internal cross-imports inside the moved subtree** — paths inside `bayes/*` referring to siblings need rewriting from `gaia.engine.lang.bayes.X` to `gaia.engine.bayes.X`.

3. **Two internal `lang -> bayes` reverse-import sites** (per §6.2) — these continue to exist after PR b but the path is updated:
   - `gaia/engine/lang/compiler/compile.py::_lower_bayes_actions` `from gaia.engine.lang.bayes.compiler import lower_bayes_claims` -> `from gaia.engine.bayes.compiler import lower_bayes_claims`
   - all `gaia/engine/lang/runtime/distribution.py` lazy imports — for example `from gaia.engine.lang.bayes.distributions.base import _BaseDistribution` -> `from gaia.engine.bayes.distributions.base import _BaseDistribution`; same for `bayes.adapters.scipy_backend` and the 10 distribution factories `Normal / LogNormal / Beta / Exponential / Gamma / StudentT / Cauchy / ChiSquared / Binomial / Poisson`

Note: the `verbs/ -> dsl/` rename inside `bayes/` does not require its own namespace tombstone because `engine.lang.bayes.verbs` was an internal pre-release sub-package; the public `bayes.dsl/__init__.py` re-exports the same names (`model`, `likelihood`).

Doc updates (see §11).

Estimated diff: ~400-500 lines (mostly mechanical import path updates including the two internal reverse imports + docs sync).

### 8.3 Sequencing rationale

PR a first because it is contained, has minimal blast radius, and resolves unambiguous over-structure with no naming debate. Reviewers focus on the demotion argument (criterion 4.2) without being distracted by the Bayes promotion.

PR b second because it depends on the BayesInference decision being settled (which happened in PR #606+#609) and has wider repo-touch. With PR a already merged, PR b's change set is purely the bayes-related moves.

## 9. Tombstone Strategy

Reuse the existing `gaia/_legacy_imports.py` machinery, but be careful about which import form the meta-path finder actually intercepts. The finder logic is:

```python
# gaia/_legacy_imports.py:91-107 (paraphrased)
def find_spec(self, fullname, path, target=None):
    for old_ns, new_ns in TOMBSTONED_NAMESPACES.items():
        prefix = f"{old_ns}."
        if fullname.startswith(prefix):           # ← exact match excluded
            ...
            return ModuleSpec(...)
    return None
```

So the finder only intercepts **strict-prefix** submodule imports (`import gaia.engine.logic.propositional`). It does **not** intercept the bare namespace import (`import gaia.engine.logic`) because `fullname == "gaia.engine.logic"` does not pass `startswith("gaia.engine.logic.")`.

The way alpha-0 covers all three import forms is by also keeping the old directory's `__init__.py` as a 4-line shim that installs a module-level `__getattr__`:

```python
# gaia/bp/__init__.py — alpha-0 reference shim
"""Alpha 0 tombstone — gaia.bp relocated to gaia.engine.bp."""

from gaia._legacy_imports import _tombstoned_namespace_getattr

__getattr__ = _tombstoned_namespace_getattr("gaia.bp", "gaia.engine.bp")
```

With both pieces in place, the three import forms are all covered:

| Import form | Mechanism | Result |
|---|---|---|
| `from gaia.engine.logic import X` | shim `__getattr__("X")` | `ImportError(... has moved to gaia.engine.ir.logic ...)` |
| `import gaia.engine.logic.propositional` | `_TombstonedSubmoduleFinder.find_spec` matches prefix | `ImportError(... has moved to gaia.engine.ir.logic.propositional ...)` |
| `import gaia.engine.logic` (exact) | resolves to the shim module (which is empty except for `__getattr__`) — subsequent attribute access raises | `ImportError` on first attribute access |

This is why §8.1 keeps the old PR-a directories and **replaces** their `__init__.py` with shim contents. PR b is the explicit exception: because the Bayes path was pre-release, the old `engine/lang/bayes/` package is deleted instead of tombstoned.

For PR a: two new tombstone shims (`engine/lang/types/`, `engine/logic/`); two new `TOMBSTONED_NAMESPACES` entries (`gaia.engine.lang.types`, `gaia.engine.logic`); one existing registry entry updated (`gaia.logic` retargeted to `gaia.engine.ir.logic`); one existing top-level shim retargeted (`gaia/logic/__init__.py` points to `gaia.engine.ir.logic`).

For PR b: no tombstone shim and no `TOMBSTONED_NAMESPACES` entry for `gaia.engine.lang.bayes`; the pre-release path is deleted before v0.5 ships.

The `verbs/ -> dsl/` rename inside `bayes/` does not need a separate tombstone because `engine.lang.bayes.verbs` only ever existed as an internal pre-release sub-package; `bayes.dsl/__init__.py` re-exports the same names (`model`, `likelihood`).

`tests/baseline/test_l2_tombstones.py` enforces that every entry in `TOMBSTONED_NAMESPACES` actually raises an `ImportError` with the right redirect; it must be extended to cover the new entries (or, if it auto-discovers from the registry, will pick them up automatically — confirm during PR a implementation).

## 10. Test Plan

### PR a tests

Smoke imports (must pass):

```python
from gaia.engine.lang import Bool, Nat, Real, Probability, PrimitiveType    # public API unchanged
from gaia.engine.lang.formula.primitives import Bool                          # new direct path
from gaia.engine.ir.logic.propositional import is_satisfiable, are_equivalent # new direct path
```

Tombstone redirects (must raise ImportError):

```python
import pytest

with pytest.raises(ImportError, match="moved to gaia.engine.lang.formula"):
    from gaia.engine.lang.types.primitives import Bool

with pytest.raises(ImportError, match="moved to gaia.engine.ir.logic"):
    from gaia.engine.logic.propositional import is_satisfiable

with pytest.raises(ImportError, match="moved to gaia.engine.ir.logic"):
    import gaia.engine.logic.propositional
```

Existing test suites must continue to pass without changes:

- `tests/baseline/test_l2_tombstones.py` (extended automatically when `TOMBSTONED_NAMESPACES` is updated)
- `tests/gaia/lang/formula/test_predicate.py`
- any test that exercises propositional analysis on compiled packages

### PR b tests

Smoke imports — new canonical paths:

```python
from gaia.engine.bayes import model, likelihood                       # new public path
from gaia.engine.bayes.runtime import BayesInference, PredictiveModel, Likelihood
from gaia.engine.bayes.dsl import model                               # renamed verbs → dsl
from gaia.engine.lang.runtime.action import Reasoning
from gaia.engine.bayes.runtime.actions import BayesInference

assert issubclass(BayesInference, Reasoning)                           # cross-module subclass
```

Smoke imports -- canonical Bayes path plus surviving internal reverse-import sites:

```python
# 1. Public Bayes entry point
import gaia.engine.bayes as bayes
assert bayes.__name__ == "gaia.engine.bayes"

# 2. Top-level Distribution factories -- proxy to the new bayes.distributions
from gaia.engine.lang.runtime.distribution import Normal, Beta, Binomial
n = Normal("x", mu=0.0, sigma=1.0)
b = Beta("p", alpha=1.0, beta=1.0)
bn = Binomial("k", n=10, p=0.5)
# accessing them must not raise; their backing classes resolve from gaia.engine.bayes.distributions

# 3. _lower_bayes_actions code path -- exercise via end-to-end compile
from gaia.engine.lang.runtime.package import CollectedPackage
from gaia.engine.lang import claim
from gaia.engine.lang.compiler import compile_package_artifact
import gaia.engine.bayes as bayes_module

with CollectedPackage("smoke_bayes") as pkg:
    h = claim("Hypothesis.", prior=0.5)
    obs = ...  # build a tiny bayes_module.model + bayes_module.likelihood
artifact = compile_package_artifact(pkg)
# compile must complete without ImportError on the internal Bayes lowering path
```

Removed pre-release paths:

```python
import importlib

with pytest.raises(ModuleNotFoundError, match=r"gaia\.engine\.lang\.bayes"):
    importlib.import_module("gaia.engine.lang.bayes")

with pytest.raises(ModuleNotFoundError, match=r"gaia\.engine\.lang\.bayes"):
    importlib.import_module("gaia.engine.lang.bayes.compiler")
```

Existing test suites must pass without semantic regressions:

- `tests/gaia/bayes/*` — Bayes runtime + dsl + lowering tests
- `tests/gaia/lang/test_action_hierarchy.py::test_bayes_action_shapes_follow_reasoning_taxonomy` — verifies `BayesInference / PredictiveModel / Likelihood` subclass relations across module boundaries
- `tests/baseline/test_l2_facade.py` — facade contract; `EXPECTED` must include the new `gaia.engine.bayes` entry and the total updated

### Cross-PR test

IR hash stability: compile a sample Gaia package (e.g., one of the existing `*-gaia` examples) before each PR and after; the resulting `.gaia/ir.json` and `.gaia/ir_hash` must be byte-identical. Module path changes must not perturb compiled IR.

## 11. Doc Updates

### PR a

User / foundations docs:

- update `docs/foundations/gaia-lang/predicate-logic.md` — fix any direct references to `gaia.engine.lang.types` import paths
- update `docs/foundations/gaia-lang/knowledge-and-reasoning.md` — fix any references to `engine.logic.propositional`
- new `gaia/engine/ir/logic/__init__.py` docstring per §8.1

Reference / facade docs (engine reference layer):

- update `docs/reference/engine/index.md` — facade table (the current top-level engine surface): remove `gaia.engine.logic` from the top-level list; the demoted `engine.ir.logic` lives under the existing `gaia.engine.ir` reference page
- delete or redirect `docs/reference/engine/logic.md` — its content moves to a sub-section under `docs/reference/engine/ir.md` (or a new `docs/reference/engine/ir/logic.md` if the per-page convention prefers a separate page)
- update `docs/reference/engine/ir.md` (or `lang/formula.md` / `lang/types.md`) — note that `Bool / Nat / Real / Probability / PrimitiveType` now canonically live at `gaia.engine.lang.formula.primitives`

Facade contract test:

- update `tests/baseline/test_l2_facade.py` — the `EXPECTED` dict is currently:
  ```python
  EXPECTED = {
      "gaia.engine.bp": 17,
      "gaia.engine.ir": 32,
      "gaia.engine.lang": 130,
      "gaia.engine.logic": 7,         # ← remove (logic demoted under ir)
      "gaia.engine.inquiry": 45,
      "gaia.engine.trace": 7,
      "gaia.engine.packaging": 9,
  }
  ```
  The current pre-reorg grand total is 247. Decide whether the 7 logic symbols are re-exported from `gaia.engine.ir` (so `gaia.engine.ir`'s count rises from 32 to ~39 and the total stays near 247) or made internal-only under `gaia.engine.ir.logic` (so the `gaia.engine.ir` `__all__` is unchanged and the 7 symbols disappear from the locked facade total). This is a small but explicit policy decision the implementing PR has to make; update `tests/baseline/test_l2_facade.py` and its module docstring/header counts accordingly.

### PR b

User / foundations docs:

- update `docs/specs/2026-05-15-causal-cleanup-reasoning-shapes.md` §4.2 — replace `gaia.engine.lang.bayes.runtime` references with `gaia.engine.bayes.runtime`; add a paragraph cross-referencing §6 of this spec for the runtime-class vs module-import distinction
- update `docs/foundations/gaia-lang/bayes.md` — update import examples to `from gaia.engine.bayes import ...`
- update `docs/foundations/gaia-lang/knowledge-and-reasoning.md` §6 (Bayes Module) — update path references
- update `docs/for-users/language-reference.md` import-block example — update Bayes import
- update `README.md` — update any Bayes-related import snippets
- move `gaia/engine/lang/bayes/README.md` → `gaia/engine/bayes/README.md`; update its import examples
- remove the pre-release `gaia.engine.lang` bayes shortcut from docs; canonical examples use `import gaia.engine.bayes as bayes`

Reference / facade docs:

- new `docs/reference/engine/bayes.md` (or `bayes/index.md` if the existing convention prefers package-style with sub-pages mirroring `docs/reference/engine/lang/*.md`) — Bayes facade reference page
- update `docs/reference/engine/index.md` — facade table: add `gaia.engine.bayes` row
- update `docs/reference/engine/lang/*.md` if any sub-page references `engine.lang.bayes` directly

Facade contract test:

- update `tests/baseline/test_l2_facade.py` — add `gaia.engine.bayes` to `EXPECTED` with its `__all__` count; the post-PR-a total will change again; sync the docstring header counts

### Both PRs

- a paragraph in `docs/foundations/gaia-lang/package.md` (or a new `engine-architecture.md`) framing the runtime-class / module-import two-layer distinction per §6 of this spec, so future contributors reading the layout know why `lang/` is the host on the runtime-class layer but still imports back from `bayes/` on the module layer.

## 12. Validation

For each PR:

```bash
git diff --check
uv run --extra dev ruff check .
uv run --extra dev ruff format --check .
uv run --extra dev pytest tests/ --no-cov
uv run --extra dev pytest tests/baseline/test_l2_tombstones.py -v
uv run --extra docs mkdocs build --strict
```

Smoke compile on a known package:

```bash
gaia build compile <some-existing-package>
gaia build check <some-existing-package>
diff <package>/.gaia/ir.json <reference-ir.json>
```

## 13. Future Work

Tracked separately, not part of this spec:

- **Lang/Bayes import isolation** — design a plugin/registry hook so `lang.compiler` does not directly import `bayes.compiler` (replacing today's `_lower_bayes_actions` direct import with a registered hook); decide where the top-level `Normal / LogNormal / Beta / Exponential / Gamma / StudentT / Cauchy / ChiSquared / Binomial / Poisson` distribution factories live (under `lang.runtime.distribution` as today, or relocated to `bayes.runtime.distribution`, or split between user-facing wrappers in `lang` and implementations in `bayes`). Independent of the path migration in this spec; landing requires its own design spec because it touches public API surface.

- **First-order / SMT logic backends** — implement `engine.ir.logic.predicate` (Z3-backed) consuming `formula_atom` metadata for scope A and C analysis (§5.1). Promote `engine.ir.logic/` to top-level `engine.logic/` only if a unified `Theory` data model emerges (Gaia-native abstractions over multiple solvers).

- **Causal extension module** — when the `CausalEdge` GaiaGraph record from `2026-05-15-causal-cleanup-reasoning-shapes.md` §6 is implemented, land it as `gaia.engine.causal/` per the precedent in §6 of this spec. Per §6.5, decide explicitly whether `lang/` will reverse-import any causal-specific service (mirroring today's limited `lang -> bayes` reverse imports) or whether the new extension is fully decoupled from day one.

- **Compose review consolidation** — `engine.lang.review/` (manifest gen), `engine.inquiry/` (consume manifest), `engine.trace/review.py` (post-execution review) all carry "review" but operate at different lifecycle stages. Worth a separate spec to clarify whether these should consolidate, rename, or stay split.

- **`Action` alias retirement** — track in `2026-05-15-reasoning-claim-reference-boundary.md` §9 deferred work. Independent of this reorg.

## 14. Out of Scope (Explicit)

Items considered and deliberately rejected for this spec:

- **Full hierarchy flattening** (promoting `lang.runtime` / `lang.dsl` / `lang.compiler` to engine top-level): rejected per §4.5. Cohesion triangle is real; flattening breaks it.

- **Renaming `lang/` → `core/`**: rejected per §4.5 + §6. Code-fact dependency direction is host/extension, not peer.

- **Splitting `lang.dsl/` into `verbs/`, `factories/`, `legacy/`**: orthogonal nesting, no current consumer. YAGNI.

- **Promoting Bayes out of `engine/`** (e.g., to top-level `gaia.bayes/`): out of scope for v0.5; alpha-0 layout already commits engine code under `gaia.engine/` and Bayes is engine code.

- **Adding `engine.causal/` / `engine.statistics/` as part of this PR**: the spec sets the precedent (§6) but does not implement extensions that don't yet exist. They land as separate PRs when the feature work is ready.

- **Removing tombstones**: post-deprecation cleanup is independent of this reorg. Tombstones are alpha-0 hard-error redirects, not soft deprecation; they stay in place indefinitely as long as `gaia.<old>` paths could plausibly appear in user code.

---

## 15. Post-launch update (v0.5.x)

The alpha-0 tombstones described throughout this spec (namespace shims
under `gaia/{bp,ir,lang,logic,inquiry,trace}/`, per-symbol shims under
`gaia/cli/*`, flat-verb stubs in `gaia/cli/commands/_flat_tombstones.py`,
plus the `gaia/_legacy_imports.py` machinery and the
`tests/baseline/test_l2_tombstones.py` / `test_flat_verb_death.py`
contract tests) were removed in a follow-up branch off `v0.5` after
external callers migrated. The spec body above is preserved as a
point-in-time record; current behavior for old paths is plain
`ModuleNotFoundError` (Python imports) and typer's standard
`No such command` usage error (CLI invocations).
