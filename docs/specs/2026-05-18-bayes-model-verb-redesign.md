# Bayes `model` verb — collapse onto `lang.derive` + metadata

| Field        | Value |
|--------------|-------|
| Status       | **implemented** — landed via #657 (`feat/bayes-unified-design`), promoted to `main` in #671 |
| Date         | 2026-05-18 |
| Base PR      | #657 (`feat/bayes-unified-design` → `v0.5`) — must merge first, or this lands as a nested PR onto it |
| Working branch | `feat/bayes-model-verb-redesign` |
| Authors      | Kun Chen + assistant |
| Supersedes part of | `docs/specs/2026-05-17-bayes-unified-design.md` §3.1 / §3.4 |

> **Scope.** Replace `bayes.predict(hypothesis, target=..., distribution=...)` with `bayes.model(content, *, target, distribution, given=...)`. The verb collapses onto the existing `lang.derive(...)` flow — the model Claim is just a derived Claim whose `metadata["model"]` carries the bayes-specific payload (target + distribution). No new Action class, no `hypothesis` concept, no auto-`Equal`.

---

## 0. Why this is a separate PR

#657 already replaced the v0.4 trio (`bayes.model` / `bayes.data` / `bayes.likelihood`) and shipped the unified schema, the flipped `exclusivity` default, and the `compare()` dedup contract. Folding this verb redesign into the same PR would re-open all of that for review. The redesign therefore lives on `feat/bayes-model-verb-redesign`, branching off `feat/bayes-unified-design`. The corresponding GitHub PR is targeted at `feat/bayes-unified-design` (a "nested" PR) so its diff stays focused on the verb change. Once #657 merges into `v0.5`, GitHub will automatically re-target this PR onto `v0.5`.

---

## 1. What changes in one table

| # | Topic | Today (`predict`, on #657) | After (`model`, this PR) |
|---|---|---|---|
| 1 | Verb name | `bayes.predict(hypothesis, *, target, distribution)` | `bayes.model(content, *, target, distribution, given=...)` |
| 2 | First positional argument | `Claim` (the "hypothesis") — required | `str` (content of the model Claim itself) — required |
| 3 | Antecedents / conditional inputs | The `hypothesis` Claim, **implicitly** | `given=[c1, c2, ...]` — explicit reviewable list, threaded through `lang.derive()` |
| 4 | Internal Action class | `Prediction(BayesInference(Reasoning))` | **removed**; the model Claim's reasoning record is the existing `Derive(Support(Directed(Reasoning)))` action emitted by `lang.derive(...)` |
| 5 | Helper / hypothesis coupling | helper Claim + hypothesis Claim, related only via `from_actions` | no separate concepts — the model Claim **is** the conclusion of the derive flow |
| 6 | Metadata key on the model Claim | `metadata["prediction"]` (or `metadata["model"]` in the v0.4 alpha) | `metadata["model"]` — see §4 |

The key architectural move is **#4**: `bayes.model` does not introduce a new Action subclass. It uses `lang.derive(...)` to create the Claim and the reasoning record, then decorates the Claim's metadata with `model`-specific data. This means everything `gaia render`, `gaia build check`, and the IR lowering already do for derived Claims applies to model Claims without bespoke handling.

---

## 2. Verb name — `predict` → `model`

`predict` (the #657 spec's pick, justified as "PPL `predictive distribution` terminology") read fine for a one-shot probabilistic action, but the verb is invoked once per (content, target, distribution) triple and the *artefact* it produces is the **model**, not the **prediction**. The new verb name is the noun the helper Claim represents:

```python
mendel_model = bayes.model(
    "F2 显性计数在孟德尔分离模型下服从 Binomial(n=395, p=3/4)。",
    target=f2_dominant_count,
    distribution=Binomial(n=395, p=3/4),
    given=[mendelian_segregation_model, monohybrid_cross_setup],
)
```

Reads as: "declare a model whose content is `<content>`, with `target` ~ `distribution`, given `<antecedents>`."

---

## 3. First positional argument — string content

The first positional argument is the **model Claim's content** — a `str`, not a `Claim`. There is no "hypothesis" parameter; the model Claim is itself the proposition being asserted, and the `given=` list (§5) names the Claims this model is derived from.

This deletes three pieces of accidental complexity that the previous draft of this spec carried:

- The `Claim`-vs-`str` first-argument dispatch. There is only one shape.
- The "hypothesis" concept. Gaia does not have a `Hypothesis` type or role — `hypothesis` appears in the codebase only as a `CandidateRelation.status` literal string and as a field name on `Infer`. The previous spec invented a Bayes-specific notion of "hypothesis Claim" that did not exist anywhere else, and forced authors to write `bayes.predict(some_existing_claim, ...)` even when the existing Claim was just standing in for the model itself.
- The auto-`Equal(hypothesis, helper)` machinery. With no separate hypothesis there is nothing to equate the model Claim with — and the compare-dedup transitivity problem the previous spec spent a section solving simply does not arise.

Authors who *want* an upstream Claim to "drive" the model — e.g. an existing `claim("孟德尔分离模型...")` they want the model to be derived from — list it in `given=` (§5), exactly the same way they would for any other `lang.derive` call.

---

## 4. Internal shape — no new Action class

`bayes.model` is essentially this:

```python
def model(
    content: str,
    *,
    target: Variable | Distribution,
    distribution: Distribution,
    given: Claim | tuple[Claim, ...] | list[Claim] | None = (),
    background: list[Knowledge] | None = None,
    rationale: str = "",
    label: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> Claim:
    """Declare a Bayes model: target ~ distribution, derived from given Claims."""
    _validate_target_and_distribution(target, distribution)
    model_claim = derive(
        content,                       # the model Claim's content
        given=given,
        background=background,
        rationale=rationale,
        label=label,
    )
    model_claim.metadata.update(_model_metadata(target, distribution, metadata))
    return model_claim
```

— literally `lang.derive(...)` plus a one-key metadata patch. Concretely:

- The model Claim is the conclusion of a `Derive` action with `given=` as its premises. `Derive` is already part of `Support`, so it picks up the existing structural-relation lowering, the existing `gaia render` treatment, and the existing review surface.
- `Prediction` (the bayes-specific Action subclass) and `BayesInference` (its marker base class) are **removed**. The only remaining bayes-specific Action class is `ModelComparison` (the action `bayes.compare` emits), which retains its current shape — see §6.
- The model Claim's `metadata["model"]` key carries the bayes payload that `bayes.compare` and the bayes IR lowering need:

```json
{
  "model": {
    "kind": "model",
    "target": <Variable | Distribution descriptor>,
    "distribution": <Distribution descriptor>
  }
}
```

The `metadata["prediction"]` key on #657 is renamed to `metadata["model"]` for consistency with the verb name and the new class-free design.

---

## 5. `given=` — explicit antecedent list, threaded through `lang.derive`

`given=` is the existing `lang.derive(...)` kwarg, threaded through. Three cases:

- **`given=()` (default).** The model Claim is an axiomatic statement of the form `target ~ distribution`. `lang.derive` still emits a `Derive` action, but with an empty premises list — same shape as `lang.derive("...", given=[])` produces today. The model Claim's prior is whatever the author specifies (or the default 1 − CROMWELL_EPS, inherited from `lang.derive`).
- **`given=[c]`.** Single antecedent. BP-wise this becomes the standard `Support` factor `lang.derive` lowers to today: the premise's belief flows into the conclusion through the existing lowering path.
- **`given=[c1, c2, ...]`.** Multiple antecedents. The semantics are the conjunction handled by `lang.derive` (and downstream by `Support` lowering): the model Claim is asserted *given all of them*.

There is no new BP factor type to invent — `bayes.model` does not encode the `target ~ distribution` declaration as a BP edge. The predictive distribution becomes a BP factor only when a downstream `bayes.compare(data, models=[m1, m2, ...])` lowers it into an `Infer` strategy (existing behaviour; see #657 §5).

This is the natural reading. The model Claim says: "this is a model" — its truth is a statement about whether the parametric form is right. Whether the data actually fits the distribution is what `bayes.compare` evaluates; what flows into the model Claim's belief from `given=` is whether the upstream antecedents (e.g. the scientific theory you derived the parametric form from) hold.

---

## 6. `bayes.compare` — only a small adjustment

`bayes.compare(data, models=[...], exclusivity=...)` keeps the surface shipped in #657. Two small adjustments:

1. The lookup that reads the model's `target` and `distribution` shifts from `claim.metadata["prediction"]` to `claim.metadata["model"]`.
2. The current `_comparison_prediction_actions` helper that walks `helper.from_actions` for a `Prediction` action is replaced with a helper that walks `helper.from_actions` for the `Derive` action emitted by `bayes.model` (identified by the presence of `metadata["model"]` on the conclusion, since `Derive` actions in the wild are not all `bayes.model` outputs).

The dedup contract, the exclusivity defaults, the `precomputed=` shape, the `ModelComparison` Action class, and the IR lowering of the comparison itself are unchanged.

The previous spec's §6 ("compare-dedup transitivity") is **entirely removed**. Without auto-`Equal` there is no transitive equivalence class to chase. The Mendel example's external `Exclusive(mendelian_segregation, blending_inheritance)` and `bayes.compare`'s auto-emitted `Exclusive(mendel_model, blending_model)` simply coexist as two structural actions over two different Claim pairs — they are linked only via the `Derive` chain (`mendel_model` derived from `mendelian_segregation` and friends, `blending_model` likewise), which BP propagates through naturally. The IR's existing D2 / consistency checks govern any actual conflict, exactly as in #657.

---

## 7. Migration

`bayes.predict` is removed from the public surface. Each call site rewrites mechanically:

```python
# Before (v0.5, on #657)
mendel_pred = bayes.predict(
    mendelian_segregation_model,
    target=f2_dominant_count,
    distribution=Binomial("F2 dominant count under Mendel 3:1", n=395, p=3/4),
    rationale="...",
    label="mendel_pred",
)

# After (this PR)
mendel_model = bayes.model(
    "F2 显性计数在孟德尔分离模型下服从 Binomial(n=395, p=3/4)。",
    target=f2_dominant_count,
    distribution=Binomial(n=395, p=3/4),
    given=[mendelian_segregation_model],     # what used to be the "hypothesis" arg
    rationale="...",
    label="mendel_model",
)
```

Two cosmetic differences worth flagging:

- The `Binomial`/`BetaBinomial` factories no longer need a separate `name`/`content` first argument either — the model Claim's content (the verb's first arg) is the canonical place to say what the model means. (Open question Q3.)
- Where the author previously had **no** upstream Claim to feed in (typical of one-shot scripts in `scripts/demo_v06_pymc_integration.py`), they can simply omit `given=` — the model Claim becomes axiomatic.

Call sites to migrate (from current `feat/bayes-unified-design`):

- `examples/mendel-v0-5-gaia/src/mendel_v0_5/__init__.py`
- `scripts/demo_v06_pymc_integration.py`
- `tests/gaia/bayes/test_runtime_and_lowering.py`
- `tests/gaia/bayes/test_v06_numeric_equivalence.py`
- `tests/gaia/bayes/test_v06_external_solver_integration.py`
- `tests/gaia/bayes/check/test_gaia_check_bayes.py`
- `tests/gaia/bayes/check/test_gaia_check_precomputed_diagnostics.py`
- `tests/gaia/lang/test_action_hierarchy.py`
- `tests/gaia/lang/test_compiler_actions.py`
- `tests/gaia/lang/test_composition.py`
- `tests/gaia/lang/test_reasoning_claim_reference_boundary.py`
- `tests/gaia/lang/test_public_surface_milestone_a.py`
- `tests/gaia/lang/compiler/test_extension_lowering.py`
- `tests/test_mendel_v05_example.py`
- `tests/baseline/test_l2_facade.py` (`gaia.engine.bayes` facade count drops as `Prediction`/`BayesInference` go)
- `docs/foundations/gaia-lang/bayes.md`
- `docs/foundations/gaia-lang/knowledge-and-reasoning.md`
- `docs/for-users/language-reference.md`
- `docs/specs/2026-05-17-bayes-unified-design.md` (cross-reference cleanup)

---

## 8. Open questions

Marked **Q**: — please mark each ✅ / ❌ / pick alternative.

- **Q1.** `Prediction` Action class and the `BayesInference` marker — drop both, or keep `BayesInference` as a marker base class for `ModelComparison` so the bayes Action surface stays discoverable via `isinstance(..., BayesInference)`? **Default:** keep `BayesInference` (since `ModelComparison` still benefits from being marked Bayes-family), drop `Prediction`.
- **Q2.** Verb name — `bayes.model` (singular, this spec) or `bayes.models` (plural, as the original conversation read suggests)? **Default:** `bayes.model` (verbs in Gaia are singular: `claim`, `observe`, `derive`, `note`, `compare`).
- **Q3.** Distribution factory content — the previous design had `Binomial("F2 dominant count under Mendel 3:1", n=395, p=3/4)` where the first arg is a content string for the *Distribution* Knowledge node. With `bayes.model("<content>", ..., distribution=Binomial(...))`, the Distribution's content is now duplicative with the model Claim's content. Should `Binomial(...)` keep requiring a content first arg, or should the factories accept it as optional (auto-derive from the model Claim's content when used inside `bayes.model`)? **Default:** keep the Distribution factory signature unchanged (still requires a content string); this PR does not touch the Distribution surface. Authors will sometimes repeat themselves; that is fine.
- **Q4.** Metadata key — `metadata["model"]` (this spec) vs `metadata["bayes"]["model"]` (nested under a Bayes namespace, matching some other Bayes-specific metadata)? **Default:** flat `metadata["model"]`, mirroring `metadata["observation"]` and `metadata["comparison"]` from #657.
- **Q5.** Helper Claim flags — `bayes.model` produces a Claim that the author wrote the content of. Should we still flag it `metadata["generated"] = True` (like the previous `predict` did, treating it as an auto-helper) or `metadata["generated"] = False` (since the author actually wrote the content)? **Default:** `False` — the content is author-written, not generated. This affects how `gaia render` displays it.
- **Q6.** `bayes.predict` — keep as a deprecation alias for one release cycle, or hard-remove? **Default:** hard-remove (per Q6 of the previous round, confirmed in this round's user message).
- **Q7.** When `given=()` (empty), `lang.derive` still emits a `Derive` action with an empty premises list. Is that the right shape for "axiomatic model", or should `bayes.model` short-circuit and emit just the Claim with no `Derive` reasoning record? **Default:** emit the empty `Derive` — keeps the model Claim's `from_actions` populated consistently and lets `gaia render` show "model declaration, no antecedents" rather than a bare Claim.

---

## 9. Acceptance checklist (filled in during implementation)

```
[ ] gaia.engine.bayes.__init__ removes `predict`, adds `model`
[ ] gaia.engine.bayes.runtime.actions removes Prediction; BayesInference kept iff Q1=keep
[ ] gaia/engine/bayes/dsl/predict.py removed; gaia/engine/bayes/dsl/model.py added
[ ] metadata["prediction"] key renamed to metadata["model"] everywhere it appears
[ ] bayes.compare reads metadata["model"]; comparison helper reader switches
    from "find Prediction action" to "find Derive action with metadata['model']"
[ ] bayes IR lowering reads metadata["model"]; emits the same infer-strategy
    pattern it does today; structural-action handling unchanged
[ ] All callsites in §7 migrated (rename verb, lift the old `hypothesis` Claim into `given=[...]`)
[ ] New regression tests:
      - bayes.model("...", target=v, distribution=D) without `given=` emits an
        axiomatic Derive action (or skips Derive — depends on Q7)
      - bayes.model("...", given=[c]) emits a Derive action with c as premise
      - bayes.compare reads the new metadata["model"] payload correctly
      - bayes.predict raises AttributeError with a remediation hint pointing to
        bayes.model
[ ] gaia.engine.bayes facade count updated in tests/baseline/test_l2_facade.py
[ ] docs/for-users/language-reference.md, foundations/gaia-lang/bayes.md,
    foundations/gaia-lang/knowledge-and-reasoning.md regenerated
[ ] docs/specs/2026-05-17-bayes-unified-design.md cross-reference updated to point
    here for the verb redesign
[ ] CI clean (ruff + pytest); no regressions outside the migration
[ ] PR base = feat/bayes-unified-design, body links to this spec
```

---

## 10. Out of scope for this PR

- N-ary `Exclusive` operator for `compare(exclusivity="exhaustive_pairwise_complement", models=[m1, m2, m3, ...])` — still tracked in #661.
- Distribution Knowledge factory surface (`gaia.engine.lang.Normal` / `Binomial` / `BetaBinomial`) — Q3 leaves it untouched.
- Any change to `bayes.compare` exclusivity semantics or `bayes.observe` schema.
- `ModelComparison` Action class — unchanged.
