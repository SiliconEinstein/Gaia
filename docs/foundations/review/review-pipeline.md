---
status: current-canonical
layer: review
since: v0.5
---

# Review Pipeline

Gaia separates **structural compilation** (objective, deterministic) from
**review** (qualitative judgment about whether an authored action's warrant is
acceptable for publication-quality workflows). Review is a per-action decision:
a reviewer reads each action's audit question and accepts, rejects, defers, or
asks for more inputs. It is not a numeric prior.

In v0.5 review is fully local. The CLI generates a **review manifest** at compile time, an inquiry loop guides the author through outstanding actions, and the trace produced by `gaia run infer` can be independently audited. There is no central review server today.

This document covers the local review surface. The legacy LLM-driven `pipeline_review()` / `cli/llm_client.py` path described in earlier versions of this file is removed and superseded.

## 1. Review Targets

Every authored Action that survives lowering produces at least one **review target**:

| Action family | Target kind | Audit question pattern |
|---|---|---|
| `Derive / Compute`, plus premise-backed `Observe` (`Directed`) | `strategy` | "Does the warrant for &lt;action_label&gt; correctly entail &lt;conclusion&gt; from the listed premises?" |
| Zero-premise `Observe` | `action` | "Is the observation for &lt;conclusion&gt; reliable?" |
| `Infer` / `Associate` | `strategy` | "Are the supplied conditional probabilities for &lt;action_label&gt; defensible?" |
| `Equal / Contradict / Exclusive` (`Relation`) and `Decompose` | `operator` | "Is the declared relation or decomposition from &lt;action_label&gt; correct?" |
| `Compose` | `compose` | "Is the composed workflow &lt;action_label&gt; well-formed and faithful to its child actions?" |
| Reviewable helper claims (e.g. `bayes` likelihood comparison) | `knowledge` | "Does the helper claim &lt;label&gt; correctly summarize the underlying lifted likelihood update?" |

`DependsOn` and `CandidateRelation` (`Scaffold`) are intentionally not reviewable — they are authoring metadata only and never enter the IR. Structural-expression helpers from the deprecated `~A` / `A & B` / `A | B` shortcuts carry `metadata["review"] = false` and are also skipped.

## 2. Data Model

Source: `gaia/engine/ir/review.py`.

```python
class ReviewStatus(StrEnum):
    UNREVIEWED   = "unreviewed"
    ACCEPTED     = "accepted"
    REJECTED     = "rejected"
    NEEDS_INPUTS = "needs_inputs"

class Review(BaseModel):
    review_id: str                              # deterministic per (target_kind, target_id)
    action_label: str                           # e.g. "github:foo::derive_x"
    target_kind: Literal["strategy", "operator", "knowledge", "compose"]
    target_id: str                              # IR QID of the lowered target
    status: ReviewStatus
    audit_question: str
    reviewer_notes: str | None = None
    timestamp: str | None = None
    round: int = 1                              # supports multiple review rounds

class ReviewManifest(BaseModel):
    reviews: list[Review] = []

    def latest_status(self, target_id: str) -> ReviewStatus | None: ...
```

`Review.round` lets a target accumulate a history; `latest_status(target_id)` returns the highest-round status. The persisted manifest is a JSON file at `.gaia/review_manifest.json`; the auto-generated baseline manifest carries `status = UNREVIEWED` for every target the compiler emitted.

## 3. Manifest Generation

Source: `gaia/engine/lang/review/manifest.py:generate_review_manifest`, called from `compile_package_artifact()` at the end of compilation.

For each compiled action target, the manifest builder:

1. Resolves the action label from the package-wide `action_label_map`.
2. Picks the target kind by inspecting the action subclass (`_strategy_action_type`, `_operator_action_type`, etc.).
3. Builds a templated audit question via `gaia.engine.lang.review.templates.generate_audit_question(action_type, **labels)`.
4. Mints a deterministic `review_id` per `(target_kind, target_id)` so re-compiles do not invalidate stored reviews of unchanged targets.

The result is attached to the `CompiledPackage`. `gaia inquiry review` and
review/gate commands later merge it with the package's persisted
`.gaia/review_manifest.json` (see §5). `gaia run infer` does not read the persisted
manifest; it previews the compiled graph numerically.

## 4. CLI: `gaia inquiry review`

Source: `gaia/cli/commands/inquiry.py`, `gaia/engine/inquiry/review.py:run_review`.

`gaia inquiry review` runs the local review loop in a single step:

```
1. ensure_package_env()             — set up sys.path for the package
2. load_gaia_package() + apply_package_priors()
3. compile_loaded_package_artifact()
4. validate_local_graph()           — structural validation
5. load_or_generate_review_manifest()
6. resolve_focus_target()           — current focus claim, if any
7. analyze_knowledge_breakdown()    — what kinds of nodes exist
8. analyze inquiry tree, prior holes, belief diagnostics
9. publish_blockers()               — list NEEDS_INPUTS / REJECTED items
10. snapshot to .gaia/inquiry/reviews/<review_id>.json for diffing
```

The output is a `ReviewReport` dataclass that the CLI prints in text or markdown form (`render_text` / `render_markdown`). Public surface:

```python
from gaia.engine.inquiry.review import (
    ReviewReport, run_review, render_text, render_markdown,
    publish_blockers, resolve_graph,
)
```

Companion sub-commands persist focus / obligation / hypothesis state in `.gaia/inquiry/state.json` and tactics in `.gaia/inquiry/tactics.jsonl` so that subsequent reviews stay aligned with where the author last left off:

| Sub-command | Purpose |
|---|---|
| `gaia inquiry focus [target]` | set / clear / push / pop / inspect the current focus claim |
| `gaia inquiry obligation add / list / close` | track synthetic proof obligations attached to claims |
| `gaia inquiry hypothesis add / list / remove` | working-hypothesis ledger (does not enter IR) |
| `gaia inquiry reject` | mark a focus path as rejected |
| `gaia inquiry tactics log` | view the tactic event log |
| `gaia inquiry review` | full review loop (above) |

None of these sub-commands mutate `.py` source, IR, priors, or beliefs — they are pure inquiry-state operations.

## 5. Manifest Merging

Source: `gaia/engine/inquiry/review_manifest.py`. `gaia inquiry review` and
`gaia build check` import these helpers from
`gaia.engine.inquiry.review_manifest`; `gaia/cli/commands/_review_manifest.py`
is a tombstone left in place to redirect any pre-alpha-0 callers.

```python
def load_or_generate_review_manifest(pkg_path: Path | str, compiled) -> ReviewManifest
def merge_review_manifests(generated: ReviewManifest, stored: ReviewManifest) -> ReviewManifest
def latest_reviews(manifest: ReviewManifest) -> list[Review]
```

`load_or_generate_review_manifest()` reads `.gaia/review_manifest.json` if it
exists, then merges stored entries with the generated baseline. Exact
`review_id` matches are preserved. When target IDs churn because compilation
changed a generated helper ID, Gaia can reattach by stable review keys such as
`(action_label, target_kind, audit_question)` or the fallback action key. New
targets appear as `UNREVIEWED`; targets that disappeared from the IR are
dropped on the next compile. `latest_reviews()` returns the highest-round
status per target, suitable for downstream gating.

The merged manifest is what `gaia inquiry review`, `gaia build check --gate`, and
publish/register quality checks consult when deciding whether an authored
warrant has passed review. `gaia run infer` is deliberately more permissive: it
lowers the compiled graph for a local numerical preview regardless of manifest
status. Accepted, rejected, and unreviewed are qualitative states, not hidden
probability parameters.

### Quality Gate Criteria

`gaia build check --gate` is the current publish-quality gate. By default it fails on:

- exported structural holes without a warrant chain;
- unformalized scaffold dependencies from `depends_on(...)`;
- reachable reviewable warrants whose latest status is not `ACCEPTED`;
- optional low posterior checks when `[tool.gaia.quality].min_posterior` is set.

`[tool.gaia.quality]` can explicitly allow holes or unformalized dependencies
for draft workflows, but those settings do not change `gaia run infer`; they only
change the gate result.

## 6. CLI: `gaia trace verify / review / show`

Source: `gaia/cli/commands/trace.py`, `gaia/engine/trace/review.py:run_trace_review`. Spec: `docs/specs/2026-...` ARM Trace Reviewer (PR #491).

The trace pipeline records every reasoning event emitted during `gaia run infer` and other agent-side workflows into a hash-chained `.json` / `.jsonl` file. The trace is independent of the inference numerical result — its purpose is to make the *reasoning process* itself auditable.

| Sub-command | Purpose | Exit codes |
|---|---|---|
| `gaia trace verify <path>` | schema + hash chain validation | 0 clean / 1 chain mismatch / 2 schema error |
| `gaia trace review <path> [--mode trace\|publish]` | full eight-section trace review (manifest, hash chain, causal health, references, tampering, execution stats, ranking, recommendations) | 0 clean / 1 error diagnostic (or `--strict` warning) / 2 invalid CLI |
| `gaia trace show <path> [--kind ... --limit N]` | filtered event-by-event dump | 0 / 2 |

`run_trace_review()` produces a `TraceReviewReport` with:

```
manifest_section, hash_chain_section, causal_health_section,
reference_section, tampering_section, execution_stats,
diagnostics, next_edits, next_edits_structured
```

The `--mode publish` ranking weighs diagnostics differently: it is meant to gate a release-grade trace review (e.g. before promoting a package to the registry), while the default `--mode trace` is the authoring-time view.

`--package <pkg>` lets the trace reviewer cross-reference `claim_ref` events against the package's compiled `Review` records, so that the reviewer can flag tampering or missing reviews at trace time.

## 7. Where Review Lives in the Pipeline

```
   gaia build compile
         │  emits LocalCanonicalGraph + CompiledPackage.review
         ▼
   gaia inquiry review                gaia trace verify / review / show
         │                                       │
         │ merges stored .gaia/review_manifest.json │ audits a recorded
         │ produces ReviewReport                 │ inference trace
         │ guides next-edit obligations          │
         ▼                                       ▼
   .gaia/review_manifest.json (per package)  trace snapshots in .gaia/trace/

         ↓ feeds ↓

        review/gate and publish/register checks
        (ACCEPTED warrants pass; rejected or missing reviews block release)

   gaia run infer is parallel to this gate: it lowers the compiled graph for a
   local numerical preview and writes `.gaia/beliefs.json` without requiring
   accepted reviews.
```

For BP lowering and prior semantics see [../bp/inference.md](../bp/inference.md)
and the [Gaia IR parameterization contract](../gaia-ir/06-parameterization.md).

## 8. Code Map

| Component | Location |
|---|---|
| `Review` / `ReviewManifest` / `ReviewStatus` schema | `gaia/engine/ir/review.py` |
| Manifest generator (per-action audit questions) | `gaia/engine/lang/review/manifest.py` |
| Audit-question templates | `gaia/engine/lang/review/templates.py` |
| Manifest load / merge helpers | `gaia/engine/inquiry/review_manifest.py` |
| `gaia inquiry` CLI sub-app | `gaia/cli/commands/inquiry.py` |
| Inquiry review loop | `gaia/engine/inquiry/review.py` |
| Inquiry state, focus, obligations | `gaia/engine/inquiry/state.py`, `focus.py`, `proof_state.py` |
| `gaia trace` CLI sub-app | `gaia/cli/commands/trace.py` |
| Trace review (eight sections + diagnostics) | `gaia/engine/trace/review.py` |
| Trace schema and hash chain | `gaia/engine/trace/schema.py`, `gaia/engine/trace/hashing.py` |

## 9. Future Work

The local review pipeline above is the current canonical surface. Three forward-looking pieces remain explicit non-goals for v0.5 and live in dedicated specs:

- **Server-side ReviewService** — multi-agent peer review with rebuttal cycles. See `docs/foundations/contracts/review-report.md` for the data contract that a future service would emit.
- **Cross-package warrant gating** — propagating accepted reviews from a dependency into the local information set. Today the merged manifest is package-local.
- **Automated LLM reviewers** — a deprecated v5 implementation existed in `cli/llm_client.py`. The replacement architecture is captured in the curation specs (`docs/specs/2026-03-17-curation-service-design.md`, etc.) and is owned by the LKM workstream rather than by `gaia-lang`.
