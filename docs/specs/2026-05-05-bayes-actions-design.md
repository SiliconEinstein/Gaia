# Bayes Actions Design — v6 Action-aligned revision

> **Status:** Target design (proposal)
> **Branch:** `feat/bayes-impl-milestone-a` (off `main`)
> **Target release:** v0.6
> **Date:** 2026-05-05
> **Scope:** Re-shape the `gaia.lang.bayes` module (from PR #523's spec) so that Bayes verbs are first-class **Actions** in the v6 Action runtime, instead of `Claim`-with-metadata artifacts.
> **Supersedes:** `docs/specs/2026-05-04-bayes-module-design.md` (PR #523) on the questions of: how Bayes verbs sit in the runtime, what they return, and where multi-H comparison is aggregated. The distribution module (Milestone A), `gaia check` rules, BP lowering shape, and exclusivity policy from #523 are retained.
> **Depends on:**
>   - PR #505 (claim formula schema — `Variable` / `Domain` / `Formula AST` / `parameter()` / `observation()` sugar)
>   - PR #524 (v0.5 Action hierarchy refactor — `Relate`/`Correlate` removed; `Structural`/`Probabilistic` are the public categories; `Decompose` added; new `roles.py` projection system). See `docs/specs/2026-05-05-role-on-action-graph-design.md` and `docs/specs/2026-05-05-decompose-action-design.md`.
> **Implementation note (2026-05-13, updated 2026-05-18):** The current v0.5 implementation removed the proposed core `Predict` action, core `predict()` verb, and deprecated `bayes.predict(...)` alias. Treat the sections below that describe those APIs as historical rejected design; current authoring uses `derive / observe / compute` in core and `bayes.model(...) / bayes.compare(...)` for Bayes.

---

## 0. Why this revision

PR #523 was authored before the v6 Action runtime was canonical. It modeled `predict()` and `likelihood()` as **`Claim`-returning verbs** whose reasoning step lived implicitly in the `Claim`'s `metadata["bayes"]["role"]`, and let the compiler expand that into IR strategies + auto-generated `CONTRADICTION` operators.

In v0.5 (`gaia/lang/runtime/action.py` after PR #524), reasoning is no longer hidden in Claim metadata. It is an explicit `Action` class hierarchy with four public categories — `Support` / `Structural` / `Probabilistic` / `Scaffold` (plus `Compose`) — and existing verbs like `derive() / observe() / compute() / infer()` all return their conclusion (or evidence) Claim while constructing an Action behind the scenes that carries `rationale / background / warrants / helper`.

If Bayes verbs stay as Claim-with-metadata, they will:

- Be invisible to `gaia review` (review traverses Actions and the new `roles.py` projection, not Claim metadata).
- Lack a place to put `rationale / background / warrants` for the Bayes step itself.
- Diverge structurally from `infer / associate`, which are already proper Probabilistic Actions.
- Not appear in `roles_for_claim()` / `roles_for_package()` projections, so prior policies and review tooling cannot reason about Bayes-step participation.
- Force the compiler to special-case "auto-generate operators from Claim metadata" instead of treating Bayes the same as any other Action.

This revision aligns Bayes with v0.5: each Bayes verb constructs an Action, and the cite-able Claim each verb returns is the **helper Claim** of that Action — exactly the pattern `infer()` already uses (`gaia/lang/dsl/infer_verb.py:96-104`). Roles for Bayes Actions are registered in `gaia/lang/runtime/roles.py` so the projection sees them.

---

## 1. Architectural Position

```
┌────────────────────────────────────────────────────────────────────┐
│  Gaia Lang  (v0.5, lifted)                                          │
│  ─────────                                                           │
│  CORE:  gaia/lang/runtime/action.py     (Bayes-free)                │
│         Action ├ Support       (Derive/Observe/Compute/Predict[NEW])│
│                ├ Structural    (Equal/Contradict/Exclusive/Decompose)│
│                ├ Probabilistic (Infer/Associate)                    │
│                ├ Scaffold      (DependsOn) / Compose                │
│                                                                     │
│  OPT-IN: gaia/lang/bayes/runtime/actions.py                         │
│         PredictiveModel  (Action subclass — NEW)                    │
│         Likelihood       (Probabilistic subclass — NEW)             │
└──────────────────────────────────────┬─────────────────────────────┘
                                       │ Compiler (existing v0.5 path)
                                       ▼
┌────────────────────────────────────────────────────────────────────┐
│  Gaia IR  (grounded)                                                │
│  ────────                                                            │
│  No new Knowledge node types. No new FactorType. No new OperatorType │
│  Bayes Actions lower to existing infer strategies + Structural      │
│  Contradict operators per #523 §4 (lowering body retained).         │
└────────────────────────────────────────────────────────────────────┘
```

### 1.1 Module boundary (consistent with #523, sharpened)

- **Bayes is opt-in at every layer.** Do not import `gaia.lang.bayes` and you see no Bayes types — neither at the DSL surface, nor in the Action class tree, nor in `gaia/lang/runtime/`.
- Core `gaia/lang/runtime/action.py` does **not** import scipy, does **not** know what `Distribution` is, does **not** import `gaia.lang.bayes`.
- All Bayes-specific Action classes live in `gaia/lang/bayes/runtime/actions.py` and are imported only by users who opt into the bayes module.
- Compiler dispatch on Bayes Action types is done via a registration mechanism inside `gaia/lang/bayes/compiler/lower.py`; the core compiler dispatcher is not modified to know about Bayes types.

### 1.2 Predict (core) vs Derive — the falsifiability boundary

`Predict` joins the core Support family (alongside `Derive / Observe / Compute`). The boundary against `Derive` is:

| Verb | Use when |
|---|---|
| `derive` | Logical/mathematical step from premises. Conclusion has the same epistemic status as premises. ("From the Lagrangian we derive the equations of motion.") |
| `predict` | Model-driven, falsifiable claim about an observable. Conclusion is contingent on the model and meant to be checked. ("We predict that light is deflected by 1.75″ near the Sun.") |
| `compute` | Deterministic algorithmic computation with a `fn`. (Existing v6.) |
| `observe` | Empirical measurement. (Existing v6.) |

`Predict` adds no new fields beyond `Support`; the difference vs `Derive` is the class identity (which review uses to pick a different review prompt) and the `action_type="predict"` warrant tag.

This boundary is principled but soft. A future `gaia check` rule may flag clearly-mathematical conclusions wrapped in `predict()` as a style finding; v0.6 does not enforce it.

---

## 2. Action Classes

### 2.1 Core: `Predict`

```python
# gaia/lang/runtime/action.py

@dataclass
class Predict(Support):
    """Falsifiable model output. Distinct from Derive in that it points at empirical comparison."""
```

No new fields. Inherits `conclusion: Claim | None`, `given: tuple[Claim, ...]`, plus the Action base fields (`label / rationale / background / warrants / metadata`).

### 2.2 Bayes opt-in: `PredictiveModel`

```python
# gaia/lang/bayes/runtime/actions.py
from gaia.lang.runtime.action import Action

@dataclass
class PredictiveModel(Action):
    """Declares: 'under hypothesis H, observable X follows distribution D'."""
    hypothesis: Claim | None = None
    observable: Variable | None = None
    distribution: Distribution | None = None
    helper: Claim | None = None    # cite-able "X ~ D under H" judgment
```

**Why direct `Action` subclass and not `Structural` / `Probabilistic`:**

- Not `Structural`: that family is for **hard** constraints (Equal/Contradict/Exclusive/Decompose). PredictiveModel makes a **probabilistic** statement.
- Not `Probabilistic`: that family lowers to **soft factors** by itself (Infer / Associate emit BP factors directly). PredictiveModel does **not** emit a factor on its own — it's a structured declaration that `Likelihood` reads to compute the factor. Putting it under `Probabilistic` would mislead readers about which actions contribute factors.
- Direct `Action` subclass: signals "this is a model declaration that doesn't fit the standard factor-emitting categories", consistent with how `Compose` is also a direct `Action` subclass for similar "doesn't fit the categories" reasons.

**Single-H per PredictiveModel.** Multi-hypothesis aggregation happens at `Likelihood`, not here. (See §4.)

### 2.3 Bayes opt-in: `Likelihood`

```python
# gaia/lang/bayes/runtime/actions.py
from gaia.lang.runtime.action import Probabilistic

@dataclass
class Likelihood(Probabilistic):
    """Compute log-likelihood of data under model, optionally compared against alternatives."""
    model: Claim | None = None                    # helper Claim of the advocated PredictiveModel
    against: tuple[Claim, ...] = ()               # helper Claims of alternative PredictiveModels
    data: tuple[Claim, ...] = ()
    exclusivity: str = "pairwise_contradiction"
    log_likelihoods: dict[str, float] = field(default_factory=dict)  # populated at compile
    # helper: Claim | None  inherited from Probabilistic
```

`helper` (inherited from `Probabilistic`) carries the Bayes judgment: `"Given <data summary>, <model.label> is preferred over <against labels> (BF≈…)"`. Its `metadata["helper_kind"] = "model_preference"` and `metadata["relation"]` carry the structured comparison record (per-model log-likelihoods, pairwise BFs, exclusivity mode). This mirrors `infer()`'s helper convention exactly.

**Field types are `Claim`, not `PredictiveModel`.** Following `Infer`'s storage pattern (which stores `hypothesis: Claim`, `evidence: Claim`), `Likelihood` stores the **helper Claims** returned by `bayes.model(...)`. The owning `PredictiveModel` Action is reachable via `Claim.from_actions`. This keeps the `roles.py` projection uniform — Bayes fields are Claim references like every other Action — and lets `roles_for_claim(M_3to1_helper, pkg)` naturally surface its `compared_model` role inside `Likelihood`.

---

## 3. DSL Surface

### 3.1 Core verbs (unchanged + new `predict`)

```python
from gaia.lang import derive, observe, compute, predict   # all four are core, Bayes-free

predict(
    conclusion: Claim | str,
    *,
    given: Claim | tuple[Claim, ...] | list[Claim] | None = (),
    background: list[Knowledge] | None = None,
    rationale: str = "",
    label: str | None = None,
) -> Claim       # returns conclusion
```

Body mirrors `derive()` (`gaia/lang/dsl/support.py`); only differences are `action_type="predict"` in the warrant and constructing `Predict()` instead of `Derive()`.

Implementation note: `Predict` must not fall through to the generic `Support`
path in compiler or review code. The compiler records `pattern="prediction"`
for `Predict`, `generate_review_manifest()` maps that pattern to
`action_type="predict"`, and `gaia/lang/review/templates.py` has a dedicated
`predict` audit prompt. Otherwise the new class identity is lost and `predict`
is indistinguishable from `derive` at review time.

### 3.2 Bayes verbs

```python
from gaia.lang import bayes
from gaia.lang.bayes import Binomial, Normal, ...   # distributions

bayes.model(
    hypothesis: Claim,
    *,
    observable: Variable,
    distribution: Distribution,
    background: list[Knowledge] | None = None,
    rationale: str = "",
    label: str | None = None,
) -> Claim       # returns helper Claim ("X ~ D under H")

bayes.likelihood(
    data: Claim | tuple[Claim, ...] | list[Claim],
    *,
    model: Claim,                                 # helper of a PredictiveModel Action
    against: tuple[Claim, ...] | list[Claim] = (),
    exclusivity: str = "pairwise_contradiction",  # | "exhaustive_pairwise_complement" | "none"
    background: list[Knowledge] | None = None,
    rationale: str = "",
    label: str | None = None,
    precomputed: dict[Claim, float] | None = None,
) -> Claim       # returns helper Claim ("M_a is preferred over M_b given D")
```

Note: `model=` and `against=` are typed as `Claim` because what the user passes is the **return value** of `bayes.model(...)` — which is the PredictiveModel Action's helper Claim. The Likelihood lowering walks back from the helper Claim to its owning `PredictiveModel` Action via `Claim.from_actions`. Type-checking that this Claim was produced by a `PredictiveModel` (and not, say, a plain `Predict`) is enforced at compile time, not by Python's static type system.

`precomputed=` is still keyed by the original **hypothesis Claims**, not by the
model-helper Claims passed through `model=` / `against=`. The new Action shape
changes the authoring surface, but lowering still emits one likelihood factor
per hypothesis `H_i`. Passing helper Claims as keys is a compile-time error.

### 3.3 Why `bayes.model` and not `bayes.predict`

The interface deviates from core `predict()` (hypothesis is the first positional, conclusion is auto-generated from the distribution). Forcing the same name `predict` in two namespaces with different shapes is a documentation problem. `model` is the natural English verb for "specify a probability distribution that the observable follows under H" and aligns with the class name `PredictiveModel`. Non-Bayes users see `predict()`; Bayes users see `bayes.model()` — distinct verbs, distinct semantics.

### 3.4 Top-level export migration from #523

PR #523 exposed Bayes symbols directly from `gaia.lang`:
`predict`, `likelihood`, and distribution literals such as `Binomial`. This
conflicts with the opt-in boundary in §1.1 and with the new core
`from gaia.lang import predict` API.

Milestone B therefore owns the public export migration:

- `from gaia.lang import predict` becomes the core Bayes-free `Predict` verb.
- `from gaia.lang import bayes` remains the only top-level Bayes entrypoint.
  Implement it lazily (for example with module `__getattr__`) so importing
  `gaia.lang` alone does not import scipy or `gaia.lang.bayes`.
- Remove direct top-level Bayes aliases from `gaia.lang.__all__`
  (`Binomial`, `Normal`, `likelihood`, the #523 Bayes `predict`, etc.).
- Keep `gaia.lang.bayes.predict` as a one-release deprecated alias for
  `gaia.lang.bayes.model` if compatibility is desired, but do not re-export it
  as `gaia.lang.predict`.

---

## 4. Multi-Hypothesis Aggregation: at Likelihood (走法 B)

Each `bayes.model(...)` call declares **one** PredictiveModel for **one** hypothesis. Multi-H comparison is composed at `bayes.likelihood(...)` via `model=` + `against=[...]`:

```python
M_3to1 = bayes.model(H_3to1, observable=k, distribution=Binomial(n=395, p=theta_3to1))
M_null = bayes.model(H_null, observable=k, distribution=Binomial(n=395, p=theta_null))
data   = observe(formula=Equals(k, 295), rationale="Mendel 1866 dominant phenotype count")

cmp = bayes.likelihood(
    data,
    model=M_3to1,
    against=[M_null],
    rationale="3:1 vs 1:1 segregation comparison",
)
```

### 4.1 Why aggregate at Likelihood, not at PredictiveModel

- Each PredictiveModel becomes a single, independently reviewable scientific claim ("under H_3to1, k follows Binomial(395, 0.75)"). A reviewer can accept M_3to1 and reject M_null without re-touching the comparison.
- Cross-package model reuse becomes natural: another package can `import M_3to1 from upstream_pkg` and call `bayes.likelihood(my_data, model=M_3to1, against=[my_M_null])`.
- The asymmetry between `model=` (the model the author is advocating) and `against=[...]` (alternatives) records the **authorial stance**, which is what reviewers and downstream readers actually want to see. The Bayesian math is symmetric, but the narrative is not.

### 4.2 What lowering produces

Per #523 §4.2 (retained on CPT/BP semantics, adapted to the new Action shape):

```
Step 1: For each model M_i ∈ {model} ∪ against:
    a. Read M_i.hypothesis.formula, extract Variable bindings.
    b. Apply bindings to M_i.distribution, yielding concrete distribution D_i.
    c. logL_i = Σ D_i.logpmf(d) over data points (Σ logpdf for continuous).
       (Noise model handling per #523 §4.5.)

Step 2: Build the helper Claim ("M_a preferred over M_b given D"), populate
        helper.metadata["relation"] with all log-likelihoods and pairwise BFs.
        helper.metadata["helper_kind"] = "model_preference".

Step 3: Construct the Likelihood Action with helper, model, against, data,
        log_likelihoods. Append to data[0].from_actions (and to the package).

Step 4: Per H_i, emit an IR `infer` strategy with
        StrategyParamRecord.conditional_probabilities = [0.5, p1_i]
        (CPT shape unchanged from #523 §4.2 / §4.3).

Step 5: Per exclusivity policy, consume the Structural Actions generated by
        bayes.likelihood(...) for H_i pairs (see §5). These Actions compile to
        existing `contradiction` / `complement` operators.
```

The CPT shape, Cromwell clamp, exclusivity table, noise model handling, and `precomputed=` escape hatch are **all unchanged from #523** and not repeated here. This document covers only the v6 Action-shape changes.

---

## 5. Auto-Generated Contradict: Independent `Structural` Actions

When `exclusivity != "none"` and there are 2+ hypotheses, `bayes.likelihood(...)`
creates `Contradict` (or `Exclusive` / a `Decompose`-helped `Disjunction`)
Actions for hypothesis pairs at DSL construction time. They are real package
Actions, not compiler-only side effects. This timing is required because
`roles_for_package()` projects from `pkg.actions`, and `ReviewManifest` is built
from compiled targets that carry `action_label` metadata.

These are **independent `Structural` Actions**, not nested children of the
`Likelihood` Action. They carry an audit marker:

```python
helper = Claim(
    "Bayes likelihood comparison implies H_3to1 and H_null cannot both hold.",
    metadata={"generated": True, "review": True, "helper_kind": "contradiction"},
)
auto = Contradict(
    a=H_3to1,
    b=H_null,
    helper=helper,
    rationale="auto-generated by likelihood comparison",
    metadata={
        "auto_generated_by": f"likelihood:{likelihood_action.label or likelihood_action.id}",
    },
)
```

If an implementation cannot create a generated structural commitment until
compiler time (for example because one model helper is imported from another
package), it must synthesize the same review surface: a stable action label,
compiled operator metadata with that action label, and a `ReviewManifest` entry
for the generated structural commitment. A bare IR operator with only
`metadata["bayes"]["auto_generated_by"]` is not enough.

### 5.1 Why independent and not nested

- Preserves the **flat Action tree**: every Action is a sibling under the package, none is a child of another. Compose is the only mechanism for hierarchy in v6, and Likelihood is not a Compose.
- Review tooling already iterates over the flat package action list; nested children would require a new traversal mode.
- `Contradict` already exists with the right shape. Adding a `metadata["auto_generated_by"]` marker is a zero-cost extension.
- Authors who write their own `contradict(H_i, H_j)` are deduplicated against auto-generated ones by pair-hash (per #523 §4.6, retained).

### 5.2 What review sees

A reviewer auditing `likelihood(...)` can inspect the package action list or
ReviewManifest for `metadata["auto_generated_by"] == "likelihood:<this_label>"`
and see the implied exclusivity commitments. This is more transparent than
#523's compile-time-only metadata trail because the commitments are real review
targets, not just markers on operators.

---

## 6. Return-Value Convention

| Action | Returns | Why |
|---|---|---|
| `Derive`, `Observe`, `Compute`, **`Predict`** | conclusion Claim | Support family — given→conclusion, the conclusion is what upstream cites. |
| `Infer` | evidence Claim | Single-H/single-E update; evidence is the Claim whose belief is updated. |
| **`PredictiveModel`** | helper Claim | The "X ~ D under H" judgment is what upstream cites. No single conclusion to return. |
| **`Likelihood`** | helper Claim | Multi-H comparison has no single Claim being updated; the cite-able artifact is the "M_a preferred over M_b" judgment. |

The deviation from Support's "return conclusion" is principled: PredictiveModel and Likelihood don't have a single conclusion Claim — they produce a relational judgment. The helper Claim is exactly the v6 mechanism for this (per `infer()` precedent).

---

## 7. What Changes vs PR #523

| Aspect | PR #523 | This revision |
|---|---|---|
| Bayes verb runtime | Returns `Claim` with `metadata["bayes"]["role"]` | Returns helper `Claim`; constructs `PredictiveModel` / `Likelihood` Action |
| Where reasoning lives | Implicit (Claim metadata read by compiler) | Explicit (Action with rationale / warrants / helper); visible in `roles_for_package()` |
| `predict()` verb name | `bayes.predict(...)` | `bayes.model(...)` (core gets its own `predict` for non-Bayes use) |
| Multi-H input | `predict({H_a, H_b}, ...)` set-style | `bayes.likelihood(model=M_a, against=[M_b, ...])` |
| ComparisonResult | Standalone Claim with metadata bookkeeping | `Likelihood.helper` Claim with `helper_kind="model_preference"` and structured `relation` metadata |
| Auto-generated exclusivity | IR-level operator with metadata trail | Real `Structural.Contradict` / `Structural.Exclusive` commitment with `auto_generated_by` marker |
| `bayes.likelihood(via=...)` | `via=` parameter name | `model=` parameter name |
| Action-tree categories | (predates v0.5 PR #524) | Aligned with `Structural`/`Probabilistic` rename; `Likelihood` extends `Probabilistic` |
| Distribution module (Milestone A) | spec | retained as-is |
| BP lowering / CPT shape / exclusivity policy | spec §4.2-4.6 | retained as-is |
| `gaia check` rules | spec §6.3 | retained as-is |
| `evidence()` deletion (Milestone C) | retained | retained |

What is **not** changing: the IR contract (no new node/factor/operator types), BP semantics, distribution backend protocol, or gaia check rules. The Mendel example keeps the #523 likelihood semantics; this revision only makes the illustrative BF≈49 case and the real Binomial clamp-limited case explicit.

---

## 8. DSL Examples

### 8.1 Non-Bayes user (Newton's law of gravitation)

```python
F_law = claim("Force = G m1 m2 / r²", label="newton_gravitation")

derive(
    formula=Equals(F, G * m1 * m2 / r**2),
    given=F_law,
    rationale="direct algebraic specialization",
)

predict(
    "in two-body orbits, period T satisfies Kepler's third law T² ∝ a³",
    given=F_law,
    rationale="follows from energy conservation under gravity",
)
```

No bayes import. No Distribution. No likelihood machinery anywhere in scope.

### 8.2 Bayes user (Mendel 3:1 segregation)

```python
from gaia.lang import claim, observe, bayes
from gaia.lang.bayes import Binomial

n     = variable("n", Nat, value=395)
k     = variable("k", Nat)
theta = variable("theta", Probability)

H_3to1 = parameter(theta, 0.75, label="H_3to1", rationale="dominant:recessive 3:1")
H_null = parameter(theta, 0.5,  label="H_null", rationale="dominant:recessive 1:1")

M_3to1 = bayes.model(H_3to1, observable=k, distribution=Binomial(n=n, p=theta))
M_null = bayes.model(H_null, observable=k, distribution=Binomial(n=n, p=theta))

data = observe(formula=Equals(k, 295), rationale="Mendel 1866 F2 dominant count")

cmp = bayes.likelihood(
    data,
    model=M_3to1,
    against=[M_null],
    exclusivity="exhaustive_pairwise_complement",
    rationale="3:1 vs 1:1 segregation comparison under an exhaustive binary framing",
)

# cmp is a Claim. Its content is approximately:
#   "Given F2 dominant count k=295 of n=395, H_3to1 is preferred over H_null."
# Raw metadata records logL_3to1≈-3.087 and logL_null≈-53.384
# (unclamped BF≈7e21); the existing BP CPT clamp yields posterior odds≈498.
# cmp.metadata["helper_kind"] == "model_preference"
# cmp.metadata["relation"]    == { log_likelihoods, pairwise_bf, exclusivity, ... }
# cmp.from_actions           == [Likelihood Action]
```

Auto-generated `Exclusive` between H_3to1 and H_null is appended to the package
as an independent Action with
`metadata["auto_generated_by"] = "likelihood:<cmp.label>"`. If the example
instead wants the illustrative BF≈49 from #523 §4.3, it must pass
`precomputed={H_3to1: -1.2, H_null: -5.1}` explicitly; the real Binomial
likelihood is far more decisive and therefore clamp-limited in BP.

---

## 9. Roles Registration

PR #524 added `gaia/lang/runtime/roles.py` — a projection that, given the package action graph, returns `RoleOccurrence(claim, role, action, ...)` tuples for every Claim referenced as a typed field on any Action. The projection is consumed by prior policies and `gaia check --hole`, and may inform review planning. ReviewManifest generation itself still works from compiled targets with stable `action_label` metadata.

### 9.1 Core: `Predict` roles (added to `roles.py` directly)

`Predict` is a core Action, so its role mapping is added to `_collect_action_roles()` alongside `Derive` / `Observe` / `Compute`. If left unregistered, the dispatch chain falls through to the `Support` fallback and assigns the generic `"conclusion"` / `"premise"` roles — identical to `Derive`. That defeats the entire reason for splitting Predict from Derive. Distinct role names:

| Action | Field | Role name |
|---|---|---|
| `Predict` | `conclusion` | `"prediction"` |
| `Predict` | `given` (each) | `"prediction_basis"` |

Dispatch placement: insert the `Predict` branch **before** the `Support` fallback at `roles.py:186`, so the more-specific class is matched first (matching the existing Observe/Compute/Derive/DependsOn ordering at lines 125-140).

### 9.2 Bayes: `PredictiveModel` and `Likelihood` roles (opt-in, registered out of tree)

| Action | Field | Role name |
|---|---|---|
| `PredictiveModel` | `hypothesis` | `"hypothesis"` |
| `PredictiveModel` | `helper` | `"model_helper"` |
| `Likelihood` | `model` | `"compared_model"` |
| `Likelihood` | `against` (each) | `"compared_alternative"` |
| `Likelihood` | `data` (each) | `"likelihood_data"` |
| `Likelihood` | `helper` | `"model_preference_helper"` |

`PredictiveModel.observable` and `PredictiveModel.distribution` are not Claims (Variable and Distribution respectively), so they do not produce role occurrences.

### 9.3 Registration mechanism for opt-in handlers — open implementation choice

The current `_collect_action_roles()` in `roles.py` is a hardcoded `if/elif` chain that imports every Action subclass directly. For Predict (core) this is fine — just add a branch. For `PredictiveModel` / `Likelihood` it conflicts with the "Bayes is opt-in, core is Bayes-free" principle from §1.1.

Two ways to handle the Bayes case in Milestone B:

- **(a) Modify `roles.py` directly** — add `elif isinstance(action, PredictiveModel)` / `elif isinstance(action, Likelihood)` branches. Simplest, but core file imports from `gaia.lang.bayes`. Violates opt-in.
- **(b) Refactor to a registration table** — `roles.py` exposes `register_role_handler(action_type, handler_fn)`; bayes module registers handlers on import. Core stays Bayes-free; cost is a one-time refactor of the dispatch chain into a table.

This spec recommends **(b)**. The refactor is small (the existing chain is ~70 lines) and the benefit (preserving the opt-in invariant for core) is exactly the same property the v0.5 design doc cited as a reason to keep `Structural` / `Probabilistic` as conceptual layers. Milestone B's plan should land the refactor as its first task, then add Bayes handlers as a follow-up. Predict's core branch is added in either world (it's not opt-in).

---

## 10. Implementation Milestones

The three milestones from #523 §9 carry over with B re-scoped to the new Action shape:

### Milestone A — Distribution module + protocol (already in flight on `feat/bayes-impl-milestone-a`)

Unchanged from #523 §9. Distribution Protocol, scipy backend, `_BaseDistribution` Pydantic model. No Action work.

### Milestone B — Action classes + DSL verbs + lowering (re-scoped)

- Add `Predict` to `gaia/lang/runtime/action.py` (no new fields).
- Add `predict()` to `gaia/lang/dsl/support.py` (or new sibling file).
- Update `gaia/lang/__init__.py` so top-level `predict` is the core verb,
  Bayes direct aliases are removed from `__all__`, and `bayes` remains lazy
  opt-in.
- Update compiler/review dispatch for `Predict`: `pattern="prediction"`,
  ReviewManifest `action_type="predict"`, a dedicated audit template, and tests
  proving it is not rendered as `derive`.
- Add `gaia/lang/bayes/runtime/actions.py` with `PredictiveModel` and `Likelihood`.
- Add `gaia/lang/bayes/verbs/model.py` (`bayes.model`) and `gaia/lang/bayes/verbs/likelihood.py` (`bayes.likelihood`).
- Add `gaia/lang/bayes/compiler/lower.py` — register lowering for `PredictiveModel` and `Likelihood` Action types; emit IR per #523 §4.
- Generate exclusivity Structural Actions at DSL construction time, or synthesize
  equivalent stable action labels and ReviewManifest entries if compiler-time
  generation is unavoidable.
- Extend `observation()` (PR 505) with `noise=` parameter (per #523 §3.3).
- Tests: distribution unit tests (Milestone A), Action construction tests,
  lowering tests, Predict review-manifest tests, Bayes export migration tests,
  auto-structural review-surface tests, Mendel golden integration test.

### Milestone C — `evidence()` deletion + docs (unchanged from #523)

- Delete `gaia/lang/dsl/evidence_verb.py` and tests.
- Close PR #506.
- Write `docs/foundations/gaia-lang/bayes.md` aligned with this revision (helper-Claim semantics, `bayes.model` verb name, multi-H at Likelihood).
- Mark PR #523's spec as superseded by this document.

Each milestone goes through `writing-plans` independently.

---

## 11. Acceptance Criteria

The design is implemented when:

1. `from gaia.lang import predict` exposes the core falsifiable-prediction verb (Bayes-free).
2. `from gaia.lang import bayes` exposes `bayes.model`, `bayes.likelihood`, and the distribution literals, while importing `gaia.lang` alone does not eagerly import `gaia.lang.bayes` or scipy.
3. `gaia.lang.runtime.action.Predict` exists; `gaia.lang.runtime.action` imports nothing from `gaia.lang.bayes`.
4. `gaia.lang.bayes.runtime.actions.PredictiveModel` and `Likelihood` exist and pass `isinstance(_, Action)` checks; `Likelihood` additionally passes `isinstance(_, Probabilistic)`.
5. `bayes.model(...)` returns a Claim whose `.from_actions` contains a `PredictiveModel` Action with populated `hypothesis / observable / distribution / helper`.
6. `bayes.likelihood(...)` returns a Claim whose `.metadata["helper_kind"] == "model_preference"` and whose `.from_actions` contains a `Likelihood` Action with populated `model / against / data / log_likelihoods`.
7. `Predict` compiles with `pattern="prediction"` and the generated review prompt is a prediction-specific prompt, not the derive prompt.
8. `roles_for_package(pkg)` surfaces all six Bayes role names from §9 for the canonical Mendel package.
9. The Mendel golden pipeline (per #523 §7.4) passes in both documented modes: illustrative `precomputed={H_a: -1.2, H_b: -5.1}` recovers odds≈47, and the real Binomial(395, p) pipeline records raw log-likelihoods in metadata while BP posterior odds are clamp-limited around 498.
10. Auto-generated `Structural.Contradict` / `Structural.Exclusive` commitments appear in the package action list or in an equivalent compiled review surface with stable action labels and `metadata["auto_generated_by"]` markers.
11. PR #506 is closed and `gaia.lang.dsl.evidence_verb` is removed.
12. `docs/foundations/gaia-lang/bayes.md` exists and reflects this revision (helper-Claim shape, `bayes.model` verb, multi-H at Likelihood).
13. No new `FactorType` in `gaia/bp/factor_graph.py`; no new `OperatorType` in `gaia/ir/operator.py`; no `gaia.stats` shim.

---

## 12. Open Questions

1. **PredictiveModel as `Action` vs `Probabilistic` subclass.** PredictiveModel doesn't itself emit a soft factor (Likelihood does, by reading the distribution). §2.2 keeps it as a direct `Action` subclass. Revisit if compiler/review treats `Probabilistic` uniformly and PredictiveModel awkwardly stands apart.

2. **Symmetric multi-model API.** `model=M_a, against=[M_b, M_c]` privileges M_a authorially. A symmetric `models=[M_a, M_b, M_c]` form is mathematically equally valid. v0.6 ships only the asymmetric form (matches paper narrative); revisit if multi-way tournaments become common.

3. **`bayes.model(conclusion=...)` override.** Should authors be able to supply a custom helper text instead of letting it be auto-rendered from the distribution? Probably yes (rationale: distribution literals don't always read well in narrative). v0.6 punts; document the auto-render template, add `conclusion=` later if requested.

4. **Cross-package PredictiveModel reuse compile-checking.** When a downstream package imports `M_3to1` and writes `likelihood(my_data, model=M_3to1)`, the Variable bindings in `M_3to1.distribution` resolve in the upstream package. Need a check that the downstream `data` Variable is the same `observable` (object identity vs label match). v0.6 may be conservative (require local data); lift in v0.7 if cross-package likelihood becomes a real ask.

5. **Compiler dispatcher registration.** `gaia/lang/compiler/compile.py` dispatches on Action subclass. Bayes lowering is registered out-of-tree (in `gaia.lang.bayes`). Same registration question as roles.py §9.1; ideally the compiler and roles dispatchers share the same out-of-tree registration mechanism. Detail to nail down in Milestone B's plan.

---

## 13. References

- PR #523 spec (superseded on Action shape, retained on lowering): `docs/specs/2026-05-04-bayes-module-design.md`
- PR #524 — Action hierarchy refactor: `docs/specs/2026-05-05-role-on-action-graph-design.md`, `docs/specs/2026-05-05-decompose-action-design.md`
- PR #505 (claim formula schema): `docs/specs/2026-05-04-claim-formula-schema-design.md`
- v0.5 Action runtime: `gaia/lang/runtime/action.py`
- v0.5 roles projection: `gaia/lang/runtime/roles.py`
- v0.5 helper-Claim convention: `gaia/lang/dsl/infer_verb.py:96-104`
- v0.5 Support DSL template: `gaia/lang/dsl/support.py`
- IR factor types: `gaia/bp/factor_graph.py:26`
- BP lowering: `gaia/bp/lowering.py:317`
