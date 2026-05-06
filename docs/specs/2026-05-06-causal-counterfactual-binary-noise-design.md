# Causal Extension B — Counterfactual Queries via Binary Exogenous Noise

> **Status:** Target design (proposal)
> **Date:** 2026-05-06
> **Scope:** Add Pearl-level-3 counterfactual queries `P(Y_{x'} | E)` to `gaia.causal`, computed in three steps (abduction → action → prediction) over the existing binary FactorGraph by automatically materializing one binary exogenous-noise variable per binary_directed mechanism.
> **Depends on:** `docs/specs/2026-05-06-causal-mechanism-first-class-design.md` (Mechanism as first-class Knowledge type).
> **Non-goals:** Continuous exogenous noise; counterfactuals over categorical or linear-Gaussian mechanisms (waiting on `Mechanism.kind` expansion per Mech §13 Q3); structural identifiability of counterfactuals (we always *compute* a numeric answer; identifiability via twin-network y0 is a follow-up).

---

## 0. Why this is feasible now and not deferred to v0.7+

The Mechanism spec (Mech) §12 lists "Counterfactual reasoning (Pearl level 3)" as out of scope and says it "requires a different inference mode (abduction–action–prediction or twin networks)". That assessment was correct under the assumption that exogenous noise needs continuous random variables.

**For binary mechanisms, exogenous noise can itself be binary**, and Gaia BP already handles binary variables. A `binary_directed` mechanism

```
P(E=1 | C=1) = α
P(E=1 | C=0) = β
```

is exactly the marginal of the structural-equation form

```
E = (C ∧ U_active) ∨ U_leak
P(U_active = 1) = (α − β) / (1 − β)            # only meaningful when α > β
P(U_leak   = 1) = β
```

with `U_active` and `U_leak` independent. This is the noisy-OR canonical form (and matches Mech §6.2 multi-parent composition). The two `U_*` variables are **the** exogenous noise for this mechanism — they fully determine `E` given `C`.

Once those `U_*` exist as BP variables, Pearl's three-step counterfactual computation reduces to three standard BP queries on the same FactorGraph. **No new inference engine needed; no continuous variables; no twin network in the structural sense.**

This spec materializes the `U_*` variables as Gaia BP variables under synthesized CNIDs, defines the three-step query API, and integrates with Mech's existing `mutilate()` and `compute()` primitives.

---

## 1. Architectural Position

```
Mech §6.1   CausalFactor over (cause, effect)
              ↓ this spec rewrites lowering to
            CausalFactor over (cause, U_active, U_leak, effect)
            with deterministic CPT enforcing
              effect = (cause ∧ U_active) ∨ U_leak

  Author writes:
      do(X = x').counterfactual(observed={X: x, Y: y}).query(Y)
                              │
                              ▼
  gaia.causal.counterfactual.compute_counterfactual()
    1. Abduction: BP on observed FG → posterior over all U_*
    2. Action:    mutilate by CausalFactor type, do(X = x'),
                  install U_* posteriors as unary factors
    3. Prediction: BP → P(Y | counterfactual world)
```

This spec adds:
- Lowering-level: noise-variable materialization (§3) — modifies how `binary_directed` mechanisms lower.
- Runtime-level: `gaia/causal/counterfactual.py` (§4) — new module.
- DSL-level: `.counterfactual()` chained method on `Intervention` (§5) — new authoring surface.

It does **not** add new IR. It does **not** add new `KnowledgeType`. It does **not** add new BP variable types. The only IR-visible change is one boolean flag controlling whether noise materialization is active for a mechanism.

---

## 2. The Mathematics — Why This Is Correct, in 30 Lines

A binary_directed mechanism with leak β and effect-given-cause α is equivalent (in terms of marginals over `(C, E)`) to:

```
E = f(C, U_active, U_leak) = (C ∧ U_active) ∨ U_leak
```

where `U_active` and `U_leak` are independent Bernoullis with parameters chosen such that:

```
P(E = 1 | C = 0) = P(U_leak = 1)                           = β
P(E = 1 | C = 1) = 1 − P(U_active = 0) · P(U_leak = 0)
                 = 1 − (1 − s) · (1 − β)                   = α
                                       ⇒  s = (α − β) / (1 − β)
```

where `s = P(U_active = 1)`. Multi-parent effects compose by additional `U_active_i` per parent edge, with the same noisy-OR formula already specified in Mech §6.2 — the lowering pass is unchanged in its CPT output, but it now exposes `U_active` and `U_leak` as visible BP variables instead of marginalizing them analytically.

**Counterfactual `P(Y_{x'} | C = c, E = e)` (Pearl, *Causality* 2nd ed §7.1):**

1. **Abduction.** Compute `P(U | C = c, E = e)` by BP on the observed factor graph. For each mechanism's `U_*`, this is the BP marginal posterior.
2. **Action.** Construct the counterfactual factor graph by mutilating causal factors whose conclusion is in the do-set, clamping those variables to the do-values, and **installing the abducted `U` posteriors as unary factors** on the noise variables.
3. **Prediction.** Compute `P(Y | counterfactual FG)` by BP.

Edge case: when `α ≤ β` (cause inhibits or has zero effect), `s ≤ 0` is not a valid Bernoulli. v0.6 noisy-OR composition (Mech §6.2) already rejects this as `MechanismInhibitoryError` at lowering time; this spec does not weaken that — counterfactuals over inhibitory mechanisms wait for a sign-aware noise model in v0.7.

**Constancy of U across world-versions** is automatic: abducted posterior is the same `U` distribution; the counterfactual world inherits it. Pearl's twin-network construction is one way to *visualize* this; we don't need to build a literal twin graph because the U variables are shared between the factual and counterfactual computations by construction.

---

## 3. IR & Lowering Changes

### 3.1 IR — one optional flag on `Mechanism`

```python
# gaia/ir/mechanism.py — extension to the model defined in Mech §2.2
class Mechanism(BaseModel):
    kind: Literal["binary_directed"] = "binary_directed"
    cause: MechanismRef
    effect: MechanismRef
    cpd: BinaryCPT | None = None
    quantified_over: tuple[str, ...] = ()
    domain_ref: str | None = None
    materialize_noise: bool = False             # NEW (this spec)
```

`materialize_noise = True` instructs lowering to expose `U_active` and `U_leak` as BP variables. Default is `False` for backward compatibility with packages that don't care about counterfactuals.

`materialize_noise` is a per-mechanism flag, not a package-wide setting, because:
- Mixed packages exist — only some mechanisms in a package may need counterfactual queries.
- BP cost grows linearly with materialized noise variables; turning it off where unused keeps factor graphs lean.

### 3.2 Lowering — variable expansion

Lowering pass for `binary_directed` mechanisms with `materialize_noise = True`:

| Before (Mech §6.1) | After (this spec, when flag is on) |
|---|---|
| One `CausalFactor` over `(cause, effect)` with CPT `[(1−β, β, 1−α, α)]` | Two BP variables `@noise_active:{mech_qid}` and `@noise_leak:{mech_qid}`; one unary factor on each (priors `s` and `β`); one **deterministic** `CausalFactor` over `(cause, U_active, U_leak, effect)` with CPT enforcing `effect = (cause ∧ U_active) ∨ U_leak` |

Multi-parent: each parent edge contributes its own `U_active_i`, plus one shared `U_leak` per effect node. The deterministic CPT becomes `effect = (∨_i (cause_i ∧ U_active_i)) ∨ U_leak`. This matches Mech §6.2 multi-parent semantics; the marginal CPT is identical when the U variables are summed out.

### 3.3 CNID convention for noise

```
@noise_active:{namespace}:{package}:{mechanism_label}        # one per mechanism
@noise_leak:{namespace}:{package}:{effect_cnid}              # one per effect node
                                                              # (shared across mechanisms
                                                              #  into the same effect)
```

The `:` prefix differentiates from `@var:` so neither `is_qid()` nor `is_cnid()` (per Mech §2.6) gives false positives. New helper:

```python
def is_noise_cnid(id_: str) -> bool:
    return id_.startswith("@noise_active:") or id_.startswith("@noise_leak:")
```

### 3.4 No change for `materialize_noise = False`

When the flag is off, lowering is exactly Mech §6.2 — analytic noisy-OR collapses U variables into a marginal CPT. This is the v0.6 default behavior and remains unchanged. Authors opt in only when they need counterfactuals.

---

## 4. Runtime — `gaia/causal/counterfactual.py`

### 4.1 Public surface

```python
from gaia.causal.intervene import Intervention, CausalQueryResult
from gaia.bp.factor_graph import FactorGraph

@dataclass(frozen=True)
class CounterfactualQueryResult(CausalQueryResult):
    """Result of a counterfactual query, extending CausalQueryResult.

    Adds the abduction step's audit fields. Because counterfactual
    semantics depends on every U posterior, the audit hash incorporates
    them.
    """
    observed: dict[str, int]                   # the factual evidence
    intervention_counterfactual: dict[str, int]  # the do-set in the cf world
    abduction_digest: str                      # sha256 of the post-abduction FG
    counterfactual_factor_graph_digest: str    # sha256 of the post-action+prediction FG

@dataclass(frozen=True)
class CounterfactualIntervention(Intervention):
    """Lazy builder: holds the do-set; .counterfactual(observed=...) finalises."""

    def counterfactual(
        self,
        observed: dict[str, int],
    ) -> "CounterfactualBuilder":
        return CounterfactualBuilder(
            do=self.assignments,
            observed=observed,
        )

@dataclass(frozen=True)
class CounterfactualBuilder:
    do: dict[str, int]
    observed: dict[str, int]

    def query(self, target) -> CounterfactualQueryResult: ...
```

### 4.2 Joint Posterior API Requirement

**Blocking dependency:** Counterfactual queries require a joint posterior API that current Gaia BP does not expose. `InferenceEngine().run(fg)` returns `InferenceResult` with a `beliefs: dict[str, float]` field — one marginal posterior per variable. But Pearl's abduction step needs the **joint posterior** `P(U_1, U_2, ..., U_k | evidence)` over all exogenous noise variables, not the product of marginals.

**Why marginals are insufficient.** Observing an effect generally correlates the exogenous noise variables. Concrete example:

```
E = U1 ∨ U2
U1, U2 independent before evidence
observe E = 1
```

After observing `E=1`, the posterior forbids `(U1=0, U2=0)`. But if we store only `P(U1 | E=1)` and `P(U2 | E=1)` as independent unary factors, the counterfactual graph assigns nonzero probability to `(U1=0, U2=0)` again — that factual world was ruled out by the evidence, so later counterfactual predictions can be wrong.

The same issue appears in binary mechanisms `E = (C ∧ U_active) ∨ U_leak`: observing `E=1` with `C=1` correlates `U_active` and `U_leak`. For multi-parent effects, observing the effect correlates all `U_active_i` plus the shared leak.

**Required API extension.** Add to `InferenceResult`:

```python
# gaia/bp/engine.py
@dataclass(frozen=True)
class InferenceResult:
    beliefs: dict[str, float]                    # existing marginals
    treewidth: int
    # NEW (this spec):
    def joint_belief(self, variables: Iterable[str]) -> JointDistribution:
        """Return the joint posterior over the specified variables.
        
        For binary variables, this is a 2^n CPT. The implementation extracts
        the joint from the JunctionTree clique that contains all variables
        (if using JT inference), or computes it via variable elimination
        (if using GBP/loopy BP).
        """
        ...

@dataclass(frozen=True)
class JointDistribution:
    """A joint probability distribution over a set of binary variables."""
    variables: tuple[str, ...]                   # variable order
    table: tuple[float, ...]                     # 2^n entries, row-major
                                                 # table[i] = P(assignment i)
                                                 # where i is binary encoding
    
    def as_factor(self) -> Factor:
        """Convert to a Factor for installation in a FactorGraph."""
        ...
```

**Implementation notes:**
- For JunctionTree inference, `joint_belief(vars)` finds the clique containing all `vars` and marginalizes out the rest. If no single clique contains all `vars`, run variable elimination to compute the joint.
- For GBP/loopy BP, always use variable elimination (the region graph doesn't guarantee a single region contains all `vars`).
- Binary variables only in v0.6; categorical extension is straightforward when BP supports non-Bool.

**Milestone split.** This API is a **BP engine extension**, not a causal-specific change. Implementation milestones (§11) are split into:
- **PR B1** (1 week): Add `InferenceResult.joint_belief()` + `JointDistribution` to `gaia/bp/engine.py`. Tests: hand-computed joint on a 3-variable chain; verify it differs from product-of-marginals when variables are correlated.
- **PR B2** (2 weeks, depends on B1): Counterfactual implementation using `joint_belief()`.

### 4.3 The three-step compute (depends on §4.2 joint posterior API)

```python
# gaia/causal/counterfactual.py
def compute_counterfactual(
    pkg,
    do: dict[str, int],
    observed: dict[str, int],
    target: str,
) -> CounterfactualQueryResult:
    dag = build_dag(pkg)
    _assert_intervention_targets_are_dag_nodes(dag, do)

    # Step 1: ABDUCTION.
    fg_obs = lower_to_fg(pkg, materialize_noise=True)
    for var, val in observed.items():
        fg_obs.observe(var, val)
    abduction_result = InferenceEngine().run(fg_obs)
    
    # Collect all noise variables
    noise_vars = [v for v in fg_obs.variables if is_noise_cnid(v)]
    
    # Extract JOINT posterior over all noise variables (not marginals!)
    noise_joint = abduction_result.joint_belief(noise_vars)
    abduction_digest = _canonical_digest(fg_obs)

    # Step 2: ACTION.
    fg_cf = lower_to_fg(pkg, materialize_noise=True)
    fg_cf = mutilate(fg_cf, set(do))
    for var, val in do.items():
        fg_cf.observe(var, val)
    
    # Install the joint posterior as a single factor over all noise variables.
    # This preserves the correlations induced by the factual evidence.
    noise_joint_factor = noise_joint.as_factor()
    fg_cf.add_factor(noise_joint_factor)

    # Step 3: PREDICTION.
    cf_beliefs = InferenceEngine().run(fg_cf).beliefs
    cf_digest = _canonical_digest(fg_cf)

    return CounterfactualQueryResult(
        target_id=_resolve_target(target),
        intervention=dict(do),
        belief=cf_beliefs[_resolve_target(target)],
        dag_snapshot=dag,
        factor_graph_digest=cf_digest,
        observed=dict(observed),
        intervention_counterfactual=dict(do),
        abduction_digest=abduction_digest,
        counterfactual_factor_graph_digest=cf_digest,
    )
```

### 4.3 What `materialize_noise` requires of a package

Authors must opt in per mechanism. To make this ergonomic, `mechanism()` (Mech §4.1) gains a kwarg:

```python
mechanism(
    cause=X, effect=Y, cpd=(0.85, 0.05),
    counterfactual=True,                 # equivalent to materialize_noise=True
)
```

`counterfactual=` is the author-facing alias. v0.6.x default is `False` for non-breaking adoption; first-party packages that want to support counterfactual queries set it explicitly.

A package-wide shortcut:

```python
# In package metadata (top-level package config)
gaia.causal.counterfactual_default = True   # all mechanisms in this package
                                              # get materialize_noise=True
```

Compiler emits a clear error when a counterfactual query targets a mechanism with `materialize_noise = False`:

```
CounterfactualNotMaterializedError:
    Mechanism 'smoking_causes_cancer' was lowered without exogenous noise.
    To enable counterfactual queries, add `counterfactual=True` to the
    mechanism() declaration, or set
    `gaia.causal.counterfactual_default = True` for the whole package,
    then recompile.
```

---

## 5. DSL Surface

### 5.1 Authoring

```python
mechanism(cause=X, effect=Y, cpd=(0.85, 0.05), counterfactual=True)
```

### 5.2 Querying

```python
from gaia.lang.dsl.causal import do

# Pearl's classic example: "Given Joe smoked and got cancer, what is the
# probability he would have gotten cancer had he not smoked?"
result = (
    do(Smokes=0)                          # the counterfactual intervention
        .counterfactual(observed={Smokes: 1, Cancer: 1})
        .query(Cancer)
)

print(result.belief)
# P(Cancer_{Smokes=0} | Smokes=1, Cancer=1)
```

`.counterfactual(observed=...)` is the **only** new chain method. Without `.counterfactual(...)`, `do().query()` is the standard interventional query (Mech §7.4) — unchanged.

### 5.3 Effect of treatment on the treated (ETT)

A common counterfactual quantity:

```python
from gaia.causal import ett

ett_value = ett(
    pkg,
    cause=Smokes, cause_factual=1, cause_counterfactual=0,
    effect=Cancer, effect_factual=1,
)
# = P(Cancer_{Smokes=0} = 1 | Smokes = 1, Cancer = 1)
#   – P(Cancer_{Smokes=0} = 1 | Smokes = 1)
```

Convenience function in `gaia/causal/counterfactual.py`. One call, two `compute_counterfactual` invocations under the hood.

### 5.4 Universal-mechanism counterfactual

Per-instance addressability comes through Mech §5.2 grounding. The DSL accepts instance CNIDs:

```python
result = (
    do(Smokes_at("alice")=0)
        .counterfactual(observed={Smokes_at("alice"): 1, Cancer_at("alice"): 1})
        .query(Cancer_at("alice"))
)
```

`Smokes_at(member)` resolves to the instance CNID per Mech §4.4.

---

## 6. Errors

```python
# gaia/causal/errors.py (additions)
class CounterfactualNotMaterializedError(Exception):
    """Counterfactual query targets a mechanism that was lowered without
    materialize_noise=True. Tells the author exactly which mechanism
    and how to enable it."""

class CounterfactualEvidenceContradictionError(Exception):
    """observed = {...} contradicts the factual model (BP returns belief 0
    for the observation set). Counterfactual semantics is undefined when
    the factual world has zero probability."""

class CounterfactualInhibitoryMechanismError(Exception):
    """Mechanism on the path between the do-set and target has α ≤ β
    (inhibitory or null effect). Binary-noise canonical form requires
    α > β. Wait for v0.7 sign-aware noise model."""
```

---

## 7. `gaia check causal --counterfactual`

A new opt-in check rule:

| Rule | Severity | Triggered by |
|---|---|---|
| Counterfactual reachability | Warning | An authored `.counterfactual(...)` query path traverses a mechanism that lacks `materialize_noise = True`. Hint: enable `counterfactual=True` on that mechanism. |
| Inhibitory mechanism on counterfactual path | Error | Any mechanism with `α ≤ β` is on a path from the do-set to the target in a counterfactual query. |
| Counterfactual evidence consistency | Warning | Observed evidence has unusually low likelihood (< 1e-6) under the factual model. Hint at upstream conflict. |

Activated by `gaia check causal --counterfactual` — silent in default `gaia check causal` to avoid spamming users not using counterfactuals.

---

## 8. Audit & Determinism

`CounterfactualQueryResult` carries two digests:
- `abduction_digest` — sha256 of the post-observation FG (the abduction step's input).
- `counterfactual_factor_graph_digest` — sha256 of the post-action+prediction FG.

Reviewers can re-run either step independently. The U-posterior values themselves are reproducible from `abduction_digest` plus the `pkg`, so they need not be stored separately.

---

## 9. Out of Scope

- **Continuous noise** — needs a different BP engine. Mech §12 covers this.
- **Sign-aware noise** (`α ≤ β` mechanisms) — requires a four-Bernoulli decomposition or a different canonical form; v0.7+ topic.
- **Twin-network identifiability** — y0 supports counterfactual identification (Shpitser, Pearl 2008). Adding a y0 adapter wrapper for counterfactual queries is a follow-up to Extension C.
- **Path-specific counterfactuals** (`P(Y_{x'} | path-via-Z = ...)`) — needs path-counterfactual semantics; v0.8+ candidate.
- **Multi-world counterfactuals** (more than two worlds: factual, cf1, cf2, …) — same machinery extends, but DSL ergonomics need design; not in scope for first PR.
- **Continuous outcomes** — same blocker as Mech §12.

---

## 10. Implementation Milestones

**Two PRs, strictly ordered.** Total estimated 3–4 weeks.

### PR B1 — Joint Posterior API (1 week, depends on nothing)

BP engine extension. No causal-specific code.

- `gaia/bp/engine.py`: Add `InferenceResult.joint_belief(variables)` method and `JointDistribution` dataclass.
- `gaia/bp/exact.py` (JunctionTreeInference): Implement `joint_belief()` by finding the clique containing all variables and marginalizing out the rest. If no single clique contains all variables, run variable elimination.
- `gaia/bp/gbp.py` (GBP): Implement `joint_belief()` via variable elimination (region graph doesn't guarantee a single region contains all variables).
- `gaia/bp/bp.py` (loopy BP): Implement `joint_belief()` via variable elimination.
- Tests:
  - Hand-computed joint on a 3-variable chain `A → B → C` with evidence `C=1`. Verify `P(A, B | C=1)` differs from `P(A | C=1) × P(B | C=1)`.
  - Noisy-OR example: `E = U1 ∨ U2`, observe `E=1`, verify `P(U1=0, U2=0 | E=1) = 0` but `P(U1=0 | E=1) × P(U2=0 | E=1) > 0`.
  - `JointDistribution.as_factor()` round-trip: convert to Factor, add to FG, run BP, verify marginals match.
- Docs: API reference for `joint_belief()` in `docs/foundations/bp/`.

**Shippable independently.** This API is useful beyond counterfactuals (e.g., future multi-variable queries, correlation analysis).

### PR B2 — Counterfactual Implementation (2–3 weeks, depends on B1)

- `gaia/ir/mechanism.py`: `materialize_noise: bool = False`. IR validator unchanged otherwise.
- `gaia/lang/runtime/causal.py` / `gaia/lang/dsl/causal.py`: `counterfactual=` kwarg on `mechanism()`, package-wide default switch.
- `gaia/lang/compiler/lower_mechanism.py`: when `materialize_noise = True`, emit `@noise_active:…` and `@noise_leak:…` BP variables and the deterministic effect CPT; otherwise unchanged.
- `gaia/causal/counterfactual.py`: `compute_counterfactual` (using `joint_belief()` from B1), `ett`, builder classes.
- `gaia/causal/errors.py`: three new exception types.
- `gaia/causal/__init__.py`: re-export `compute_counterfactual`, `ett`, `CounterfactualQueryResult`.
- `gaia/cli/check_causal.py`: three new rules under `--counterfactual` flag.
- Tests:
  - Hand-computed counterfactual on a 3-node DAG (Pearl §7 textbook example).
  - `ett` matches direct calculation on a confounder DAG.
  - `materialize_noise = False` rejects counterfactual query with helpful error.
  - Multi-parent counterfactual: noise variables compose, joint posterior preserves correlations, marginals match noisy-OR.
  - Audit digests stable across runs.
  - Universal-mechanism counterfactual on a 3-member Person Domain.
- Docs: counterfactual-queries chapter under `docs/foundations/causal/`.

No new IR `KnowledgeType`. No new BP variable types beyond what B1 provides.

---

## 11. Prior-Art Anchors

- Pearl, *Causality* 2nd ed., Chapter 7 — abduction-action-prediction algorithm; the textbook this spec implements verbatim for the binary case.
- Pearl & Mackenzie, *The Book of Why*, Chapter 8 — counterfactual intuition and worked examples.
- Shpitser & Pearl (2008), "Complete Identification Methods for the Causal Hierarchy" — counterfactual identifiability theorems (deferred to a future y0 adapter follow-up).
- Heckerman & Breese (1996) on noisy-OR canonical form — the binary U decomposition this spec relies on.
- `docs/specs/2026-05-06-causal-mechanism-first-class-design.md` — Mech (this spec depends on §2.2 / §4.1 / §5 / §6.1 / §6.2 / §7.4).
- `docs/specs/2026-05-06-causal-population-api-design.md` — Extension A (sibling spec; counterfactual + Population composes — `pop.ate_counterfactual(...)` is a natural future helper).
- y0's counterfactual-identifiability support — explicitly out of scope for this spec but a clean follow-up adapter target.
