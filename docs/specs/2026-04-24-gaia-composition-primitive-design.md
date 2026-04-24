# Gaia Composition Primitive — Design Spec

> **Status:** Target design — companion to `2026-04-23-gaia-foundation-spec.md` §12
> **Date:** 2026-04-24
> **Scope:** The `ComposedAction` Knowledge subtype, the `@composition` authoring decorator, `CompositeStrategy` → `ComposedAction` migration, the `gaia.evidence` canonical template set, and all implementation-level mechanics the foundation defers to this document.
> **Relationship to foundation spec:** Foundation §12 commits to six invariants (ComposedAction is a Knowledge subtype, deterministic identity, sub-Knowledge universality, hierarchical-with-override review, R4 at composition level, CallableRef-as-provenance survives compositions). This spec specifies **how** those invariants are realised. Mechanics here may iterate without re-editing foundation.

---

## 0. Design goals

1. Give scientific authors a single, uniform primitive for naming multi-step reasoning workflows.
2. Subsume the earlier "evidence adapter" proposal entirely — one decorator (`@composition`), not two.
3. Preserve `CompositeStrategy`'s deterministic-identity semantics (`_structure_hash` over sorted sub-IDs).
4. Produce a flat IR: `ComposedAction` references sub-Knowledge by QID; sub-Knowledge are ordinary package-level Knowledge with reverse pointers.
5. Land in v0.5 (not parked v1.x+).

---

## 1. `ComposedAction` schema

### 1.1 Kernel pydantic

```python
class ComposedAction(Knowledge):
    """A named composition of sub-Knowledge, acting as one reviewable unit."""
    kind: Literal["composed_action"] = "composed_action"

    template_name: str                      # QID-style, e.g. "gaia:evidence:gaussian_measurement"
    template_version: str                   # semver string, e.g. "1.0"

    sub_knowledge: list[str]                # flat list of sub-Knowledge QIDs, execution order
    conclusion: str | None = None           # QID of the public output of the composition

    # inherited from Knowledge: knowledge_id, content, metadata, provenance,
    # review_status (optional)
```

### 1.2 Identity

```text
knowledge_id = QID_prefix(template_name, template_version) + "::" + _structure_hash()

_structure_hash = SHA-256(canonical_json({
    "template_name":    template_name,
    "template_version": template_version,
    "conclusion":       conclusion,       # may be None
    "sub_knowledge":    sub_knowledge,    # execution order preserved, NOT sorted
}))
```

Two expansions collide on the same `knowledge_id` iff all four fields are identical. The hash covers semantic output (`conclusion`) and execution order (`sub_knowledge` as a list), not just the unordered set of sub-IDs — this differs from v5 `CompositeStrategy._structure_hash`, which sorted sub-IDs and omitted the output. Under the richer ComposedAction semantics, both are needed:

- Two workflows with the same sub-actions but different public outputs are different workflows (different `conclusion` → different identity).
- Two workflows that execute the same sub-actions in different orders may produce different factor-graph structures (different `sub_knowledge` order → different identity).

Canonical JSON rules: keys sorted, no whitespace, UTF-8; `None` serialised as JSON `null`.

### 1.3 Sub-Knowledge field

`sub_knowledge: list[str]` accepts **any** Knowledge QID — Claim / Note / Question / Strategy (Derive / Observe / Compute / Infer) / Operator (Equal / Contradict / … / and_ / or_) / nested ComposedAction. The kernel compiler validates each QID resolves to a registered Knowledge in the package or a declared dependency.

Order is semantic: the list represents execution order, and the `_structure_hash` preserves it (§1.2). Compositions that reorder sub-actions are not the same composition.

### 1.4 Conclusion field

`conclusion: str` — QID of the Claim that the composition produces as its public output.

The v6 Support-verb pattern (`gaia/lang/dsl/support.py`) has `derive()` / `observe()` / `compute()` each return the **conclusion Claim** of the action they declare. `infer()` follows the same pattern: it returns the **evidence Claim** (the "conclusion" of an Infer action in BP-graph terms: premise = H, conclusion = E). `equal()` / `contradict()` / `exclusive()` return the helper Claim they generate.

Every primitive reasoning verb in v6 therefore returns a Claim. A composition's `conclusion` is whichever Claim the terminal action returned — typically captured as the decorated function's `return` value. No `terminal_action` field is needed; the conclusion Claim already references its producing action through the reasoning graph.

**Edge cases:**
- **Pure evidence compositions** (e.g., `gaussian_measurement`, Kepler `transit_bls_evidence`): terminal action is `infer(...)`, which returns the evidence Claim. `conclusion = evidence_qid`.
- **Compute-chain compositions** (e.g., deriving a density from temperature and pressure): terminal action is `compute(...)`, returning a derived Claim. `conclusion = derived_claim_qid`.
- **Multi-verb compositions** (e.g., ending in `equal()` or `derive()`): terminal action returns the helper / derived Claim. `conclusion = that_qid`.

`conclusion` is **required** — every composition must commit to a single public output Claim. See §10 for the multi-output open point.

**Prerequisite (v0.5 bug fix):** the v0.5 `gaia/lang/dsl/strategies.py:infer()` currently returns a `Strategy`, not a Claim. That is inconsistent with the Support-verb pattern and blocks the `conclusion = evidence_qid` rule above. Foundation §17 item 11b tracks the fix; it must land before composition mechanics can depend on `infer()` returning a Claim.

### 1.5 Reverse pointer on sub-Knowledge

Every `Knowledge` registered inside a composition scope gets `metadata["composition_id"] = <ComposedAction QID>` injected at compile time. This lets IR tools navigate from a sub-action back to its enclosing composition without rebuilding the containment index.

A Knowledge may belong to **at most one** ComposedAction. Registering the same Knowledge object through two composition scopes is a compile error (would create aliasing and break identity guarantees).

---

## 2. The `@composition` decorator

### 2.1 Signature

```python
from gaia.lang import composition

@composition(
    name: str,                          # QID-style template name (required)
    version: str,                       # semver (required)
    purity: Literal["pure", "deterministic", "impure"] = "pure",
)
def my_template(...) -> Knowledge:
    ...
```

`purity` tags the composition the same way `CallableRef.purity` tags an embedded callable (see foundation §4.8). The composition itself is **not** an execution pointer — this tag applies to the sub-actions contained, and propagates from the decorator's metadata to each `@compute` call inside the scope.

### 2.2 Scope capture semantics

When `my_template(...)` is called:

1. The decorator enters a `contextvars`-based scoped context. Until the context exits, every `claim(...)`, `observe(...)`, `compute(...)`, `derive(...)`, `infer(...)`, `equal(...)`, `contradict(...)`, `exclusive(...)`, `not_(...)`, `and_(...)`, `or_(...)`, and nested `@composition` call **defers** its produced `Knowledge`'s package registration, holding the Knowledge in the scope's capture list instead.
2. The decorated function runs; sub-Knowledge accumulate in the scope's capture list in call order. None have been registered with the enclosing package yet.
3. The function returns; its return value is recorded as the composition's `conclusion` (must be one of the captured Knowledge — usually the last action's return, a Claim).
4. On scope exit, the decorator performs a **flush pass** that registers everything with the enclosing package, in this order:
   - Build the `ComposedAction`: `ComposedAction(template_name=name, template_version=version, sub_knowledge=[k.knowledge_id for k in captured], conclusion=return_value.knowledge_id)`. Compute its `knowledge_id` via §1.2.
   - Inject `metadata["composition_id"] = <ComposedAction QID>` into each captured sub-Knowledge.
   - Register each captured sub-Knowledge with the enclosing package (they become ordinary package-level IR nodes, each carrying the reverse pointer).
   - Register the `ComposedAction` itself with the enclosing package.
5. The call site receives back the **conclusion** Claim object (not the `ComposedAction`). Authors treat the composition call like any ordinary reasoning-verb call — it looks and behaves like `derive(...)` / `compute(...)` / `infer(...)` to downstream code.

**IR outcome:** after flush, the package holds N + 1 Knowledge nodes (N sub-Knowledge + 1 ComposedAction), all with their own QIDs, all independently serialisable. The reverse pointer (`metadata["composition_id"]`) on each sub-Knowledge makes the containment relation navigable without any extra index. There are **no hidden Knowledge** — everything captured inside a scope becomes a visible IR node after flush.

### 2.3 Nested compositions

`@composition`-decorated functions may call each other. The inner composition's `ComposedAction` is registered as a sub-Knowledge of the outer composition's scope; it appears in the outer's `sub_knowledge` list.

```python
@composition(name="gaia:evidence:gaussian_measurement", version="1.0")
def gaussian_measurement(evidence, hypothesis, *, mu_h, mu_not_h, noise):
    ...

@composition(name="my_pkg:multi_instrument_average", version="1.0")
def multi_instrument_average(hypothesis, readings, mu_h, mu_not_h, noise):
    # Each gaussian_measurement call becomes a nested ComposedAction sub-Knowledge
    evidences = [
        gaussian_measurement(r, hypothesis, mu_h=mu_h, mu_not_h=mu_not_h, noise=noise)
        for r in readings
    ]
    return combine(...)
```

Nesting depth is not limited by the kernel; identity is preserved recursively via `_structure_hash`.

### 2.4 Decorator-only registration

Composition templates are registered **only** by the `@composition` decorator's side effect at function-call time. There is no central Gaia template registry — no `TEMPLATE_REGISTRY` dict, no registration file. Python's import system handles discovery: downstream packages `from some_pkg import my_template` and call it.

The `name` + `version` pair is the template's global identity. Name collisions across packages are undefined behaviour — authors are expected to prefix `name` with their package namespace (`"my_pkg:..."`), same convention as QIDs elsewhere.

---

## 3. The scalar-lifting mechanism

### 3.1 Problem

Author wants:

```python
p_h = compute(fn=_normal_density, inputs={...})   # returns a Claim whose value parameter is ~0.31
infer(evidence=e, hypothesis=h, p_e_given_h=p_h, p_e_given_not_h=p_not_h)
```

`infer()` expects `float` for `p_e_given_h`, but `p_h` is a Claim.

### 3.2 Rule

`infer()`'s DSL signature accepts `float | Claim` for `p_e_given_h` and `p_e_given_not_h`. Semantics:

- If a `float` is passed, it is used directly (matches foundation §11.1 author-writes-scalar case).
- If a `Claim` is passed, the compiler reads the Claim's numeric value parameter at compile time and substitutes the scalar. The Claim reference is **also retained** in the surrounding `ComposedAction.sub_knowledge` list for audit — so the downstream IR shows both the lifted scalar (in `IrStrategy.conditional_probabilities`) and the Claim that produced it (as a sibling sub-Knowledge).

### 3.3 Which parameter is "the value"?

The lifted Claim must be **parameterised** with a single numeric parameter conventionally named `value`. Compute helpers in `gaia.evidence` (and any author-written `@compute`) follow this convention. The compiler fails if the Claim passed to `infer()` has no `value` parameter or has multiple ambiguous numeric parameters.

### 3.4 What lifting does not do

- Lifting runs **at author's compile time**, not at downstream inference time. The Claim's `compute` callable is invoked once in the author's environment; the result is baked.
- Lifting does not create a runtime dependency: downstream BP never reads the Claim and never re-evaluates its compute. The Claim's retained presence in `sub_knowledge` is for provenance (§4.8 of foundation).

### 3.5 Cromwell clamp

The lifted scalar is Cromwell-clamped (`(ε, 1-ε)`) on write to `IrStrategy.conditional_probabilities`, same as author-supplied floats.

---

## 4. Review propagation — hierarchical with override

### 4.1 Rule

For a `ComposedAction` C and its sub-Knowledge K₁, …, Kₙ:

| C.review_status | Kᵢ.review_status | Effective status of C.conclusion |
|---|---|---|
| accepted | any accepted | active |
| accepted | any unreviewed | active (unreviewed sub-Knowledge defaults to inherited-accepted) |
| accepted | some Kⱼ = rejected | context-dependent — see §4.2 |
| rejected | any | inactive |
| unreviewed | any | inactive |

### 4.2 Sub-Knowledge explicit rejection

When C is accepted but some sub-Knowledge Kⱼ is explicitly rejected:

- If Kⱼ is on the **provenance path** to the conclusion (an input to a compute whose output reaches the conclusion), the conclusion is inactive.
- If Kⱼ is auxiliary (metadata, logging sub-actions not wired to the conclusion), the conclusion remains active.

The compiler determines provenance-path membership by tracing `sub_knowledge` → `(premises, background)` → … backward from `conclusion`. Kⱼ is on the path iff removing it would orphan the conclusion.

### 4.3 Cross-package (R4)

Per foundation §7.5, a foreign ComposedAction is `active` downstream iff:

```text
(upstream composition .review_status == accepted)
AND (local ReviewTarget for the composition == accepted
     OR a TrustDelegation covers this upstream)
```

Sub-Knowledge statuses travel with the composition but do not separately re-trigger R4 review. Trusting a foreign composition means trusting its sub-structure; if a reviewer wants finer control, they issue per-Knowledge local review instead of relying on `TrustDelegation`.

---

## 5. IR-level realisation — migration from `CompositeStrategy`

### 5.1 Current v0.5 state

`gaia/ir/strategy.py:CompositeStrategy` is a Strategy subtype with:

```python
class CompositeStrategy(Strategy):
    sub_strategies: list[str]                # strategy_id references only

    def _structure_hash(self) -> str:
        return _sha256_hex(str(sorted(self.sub_strategies)))
```

### 5.2 Migration

- **Promote**: from `Strategy` subclass to `Knowledge` subclass, sibling of Strategy / Operator.
- **Rename class**: `CompositeStrategy` → `ComposedAction`.
- **Rename field**: `sub_strategies: list[str]` → `sub_knowledge: list[str]`.
- **Generalise field**: accept any Knowledge QID, not only strategy IDs.
- **Add fields**: `template_name`, `template_version`, `conclusion`.
- **Preserve**: `_structure_hash` mechanism (sorted sub-IDs → SHA-256).

v5 `CompositeStrategy` is deprecated; no parallel classes. A migrator (separate migrator spec) rewrites v5 IR producing `CompositeStrategy` into `ComposedAction` with derived `template_name` ("legacy:unnamed") for packages compiled before the foundation lands.

### 5.3 Relationship to U1 — sequenced, not bundled

Promoting `CompositeStrategy` to a Knowledge-subtype only makes sense once `Strategy` and `Operator` are themselves Knowledge subtypes. So the composition primitive depends on the U1 runtime refactor (foundation §16.2.1).

**Staging rule (aligned with foundation §16.2.1):** U1 is a **dedicated PR**, completed first. The composition primitive is a **separate PR**, opened after U1 lands. The two must not be bundled. The U1 PR touches enough surface — `gaia/lang/runtime/action.py`, `gaia/lang/runtime/knowledge.py`, `gaia/ir/strategy.py`, `gaia/ir/operator.py`, plus extensive test updates — that adding composition logic on top would make review impractical. Foundation's "must not be bundled with a functional change" rule takes precedence.

Order of PRs (also reflected in §9 implementation plan):

1. **U1 runtime refactor** (foundation item 10 + 11) — dedicated PR.
2. **v0.5 `infer()` DSL bug fix** (foundation item 11b) — small, independent, can land before or after U1 but should land before composition.
3. **Composition primitive** (foundation item 11a) — builds on U1. Opens once U1 is merged.

---

## 6. `gaia.evidence` — canonical composition templates

### 6.1 Scope

A small curated set of `@composition`-decorated functions shipped in `gaia/evidence.py` as part of gaia-lang core. scipy is lazy-imported inside each template's `@compute` sub-calls; templates import without scipy, but calling them requires `gaia-lang[stats]` extras.

### 6.2 Templates

| Template | Purpose | Key params |
|---|---|---|
| `gaussian_measurement` | Point-hypothesis Gaussian measurement evidence | `mu_h`, `mu_not_h`, `noise` (DistributionSpec) |
| `threshold_measurement` | Threshold hypothesis (H = "true > threshold") Gaussian evidence | `threshold`, `direction` ("above" / "below"), `noise` |
| `two_sample_comparison` | Two-group count / mean comparison | `control`, `treatment` dicts, `null_delta`, `alt_delta`, `method` |
| `from_bayes_factor` | Literature BF citation with author anchor | `bf`, `p_e_given_h` (anchor, required), `rationale` (required) |

Each template ends in an `infer(...)` call whose CPT pair comes from `compute(...)` sub-actions (via §3 lifting). Each template is a `@composition`-decorated function, so calling it produces a `ComposedAction` with the sub-compute and sub-infer visible in `sub_knowledge`.

### 6.3 Signatures (illustrative, non-authoritative)

```python
@composition(name="gaia:evidence:gaussian_measurement", version="1.0")
def gaussian_measurement(evidence, hypothesis, *, mu_h, mu_not_h, noise=None):
    ...

@composition(name="gaia:evidence:threshold_measurement", version="1.0")
def threshold_measurement(evidence, hypothesis, *,
                          threshold, direction="above", noise=None):
    ...

@composition(name="gaia:evidence:two_sample_comparison", version="1.0")
def two_sample_comparison(evidence, hypothesis, *,
                          control, treatment,
                          null_delta=0, alt_delta, method="beta_binomial"):
    ...

@composition(name="gaia:evidence:from_bayes_factor", version="1.0")
def from_bayes_factor(evidence, hypothesis, *,
                      bf, p_e_given_h, rationale):
    ...
```

Final signatures subject to review during implementation. Templates beyond these four are left to domain packages.

---

## 7. Worked example — Kepler transit

A bespoke scientific evidence pipeline that canonical templates do not cover, illustrating the `@composition` escape hatch pattern.

```python
from gaia.lang import composition, observe, compute, infer
from gaia.stats import DistributionSpec
from gaia.ir.schemas import CallableRef

@composition(name="exoplanet:transit_bls", version="1.0", purity="deterministic")
def transit_bls_evidence(
    evidence, hypothesis, *,
    light_curve_hash, period_days, depth, duration_hours, stellar_noise_model,
):
    observe(evidence)                                    # sub-action 1
    bls_power = compute(fn=_bls_power,                   # sub-action 2
                        inputs={"lc": evidence, "period": period_days,
                                "duration": duration_hours})
    expected_h = compute(fn=_expected_bls,               # sub-action 3
                         inputs={"depth": depth, "duration": duration_hours})
    p_h = compute(fn=_normal_density,                    # sub-action 4
                  inputs={"x": bls_power, "mu": expected_h, "sigma": ...})
    p_not_h = compute(fn=_null_bls_density,              # sub-action 5
                      inputs={"x": bls_power, "noise": stellar_noise_model})
    return infer(                                        # sub-action 6 (conclusion)
        evidence=evidence, hypothesis=hypothesis,
        p_e_given_h=p_h, p_e_given_not_h=p_not_h,
    )
```

IR:

```text
ComposedAction(exoplanet_gaia:transit_bls::<structure_hash>)
    template_name     = "exoplanet:transit_bls"
    template_version  = "1.0"
    sub_knowledge     = [observe_kepler_lightcurve_qid,   # execution order
                         compute_bls_power_qid,            # preserved
                         compute_expected_bls_h_qid,
                         compute_p_h_qid,
                         compute_p_not_h_qid,
                         infer_transit_qid]
    conclusion        = evidence_claim_qid          # the lightcurve Claim
                                                    # (infer() returns evidence Claim)

+ 6 independent Knowledge nodes in the IR, each flushed to the
  package during scope exit with metadata["composition_id"]
  pointing back to the ComposedAction.
```

The composition call `transit_bls_evidence(evidence=kepler_lightcurve, hypothesis=kepler_87b_exists, ...)` returns the `kepler_lightcurve` Claim (because `infer()` returns the evidence Claim), letting downstream code chain further reasoning off the evidence Claim if needed.

Downstream packages import `kepler_87b_exists` and read its baked inference output. No astropy, no BLS recomputation, no light-curve data access — just the `IrStrategy.conditional_probabilities` that `compute_p_h_qid` / `compute_p_not_h_qid` populated at author's time.

---

## 8. v5 compositional strategies — disposition

v5 strategy types that were really compositions (`case_analysis`, `induction`, `composite`, `mathematical_induction`) are **not** reintroduced as named kernel primitives under the foundation. They are **patterns**, not schemas:

- An author wanting "case analysis" reasoning writes `@composition(name="my_pkg:case_analysis")` and implements the sub-structure they want.
- Community domain packages may publish well-tested case-analysis / induction compositions.
- Foundation kernel provides the composition primitive; which patterns emerge from the ecosystem is a separate question.

The `gaia.evidence` canonical set (§6) does not include these v5 patterns because they are not evidence-generation patterns. They may warrant their own canonical module (`gaia.reasoning`? name TBD) only if ecosystem demand consolidates; until then, domain packages own them.

---

## 9. Implementation plan (summary)

This spec does not replace an implementation plan; an implementation plan for the composition primitive will be a separate document under `docs/plans/`. The composition primitive is a foundation-§17 work item (item 11a); implementation is expected to land as a small number of PRs:

1. **PR-A**: `gaia/lang/runtime/composition.py` — `@composition` decorator + scope capture (`contextvars`-based) + `ComposedAction` runtime class.
2. **PR-B**: `gaia/ir/strategy.py` — rename `CompositeStrategy` → `ComposedAction`, promote to Knowledge subtype, generalise `sub_strategies` → `sub_knowledge`, preserve `_structure_hash`.
3. **PR-C**: `gaia/lang/compiler/compile.py` — sub-Knowledge QID validation, reverse-pointer injection, scalar-lifting for `infer()`.
4. **PR-D**: `gaia/bp/lowering.py` — hierarchical-with-override review propagation.
5. **PR-E**: `gaia/evidence.py` — 4 canonical composition templates with scipy lazy-import.

PR-A and PR-B must be co-ordinated with the U1 runtime refactor (foundation §16.2.1). PR-C through PR-E are independent follow-ups.

---

## 10. Open points

- **`purity` cascading**: if a composition is tagged `purity="pure"`, should the decorator validate that all captured sub-Knowledge (especially `@compute` sub-actions) also have `purity="pure"` CallableRefs? Currently the spec silently accepts mismatches; the implementation may choose to warn or error.
- **Signatures of `gaia.evidence` canonicals (§6.3)**: the four templates' exact parameter lists need review and concrete prototyping before v0.5 release. Expect signature iteration.
- **Composition with cross-package sub-Knowledge**: the current spec permits foreign QIDs in `sub_knowledge`, but this means a composition's `_structure_hash` depends on foreign QIDs that may differ across dependency versions. Might need a rule: compositions should reference local sub-Knowledge only, and foreign references go through wrapper Claims.
- **Migrator for legacy `CompositeStrategy` IR**: format for derived `template_name` when reading pre-foundation IR. Covered in the migrator spec, not here.
- **Multi-output compositions**: §1.4 currently requires a single `conclusion` Claim. Some scientific workflows produce multiple outputs (compute density AND viscosity from temperature AND pressure, as one bundled step). Three future approaches if this becomes a real need:
  - Require authors to decompose into single-output compositions (current default — accept for v0.5).
  - Allow `conclusion: list[str] | str` and extend review semantics for per-output acceptance.
  - Introduce "tuple Claim" subtype whose parameters bundle multiple named numeric fields; composition remains single-output at the `conclusion` level but the Claim carries the bundle.
  
  Not resolved; decision deferred until a concrete user need emerges.

---

## 11. Acceptance of this design

This design is ready when:

- All 6 foundation §12.2 invariants are preserved by the implementation.
- v5 `CompositeStrategy` is fully migrated; no parallel classes in `gaia/ir/`.
- `@composition` decorator works with Python's standard testing tools (no special harness).
- `gaia.evidence` ships all 4 canonical templates with scipy lazy-imported.
- Worked example (§7 Kepler transit) compiles and runs on a test package.
- IR golden snapshots demonstrate hierarchical review propagation.
- Cross-package reference to a foreign ComposedAction works end-to-end (R4-gated).
