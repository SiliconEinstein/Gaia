---
status: current-canonical
layer: cli
since: v0.6
---

# Research Loop CLI

`gaia research` is the package-native workflow for broad exploration,
review-field mapping, focus synthesis, targeted expansion, and evidence
assessment. Its canonical state lives in Gaia package source and Gaia inquiry
state; research JSON exists only as trace, cache, or audit output.

The guiding rule is:

> Do not create a second research data model when Gaia package primitives or
> `gaia inquiry` can express the same state.

## State Model

Research state has three layers.

| Layer | Canonical? | Examples | Purpose |
|-------|------------|----------|---------|
| Package source | yes | `question(...)`, `note(...)`, `candidate_relation(...)`, `claim(...)`, `derive(...)`, `materialize(...)`, package dependencies | Durable knowledge and scaffolded knowledge |
| Inquiry state | yes | current focus, open obligations, hypotheses, rejections, tactic log | Mutable research process state |
| Research trace | no | raw search JSON, LLM analysis JSON, command events, final report, timing, stop metrics | Reproducibility, debugging, meeting review |

The package and inquiry state are what later compilation, review, inference,
publication, and LKM ingestion should consume. Trace files should be readable and
auditable, but they are not the source of truth for scientific knowledge.

## Loop Shape

The loop remains breadth-first at the start and narrows only after the field
landscape is visible:

```text
broad explore
  -> review field-map induction
  -> coverage expansion for thin review buckets
  -> focus synthesis
  -> targeted expand
  -> selected evidence + deep materialization
  -> assess one focus
  -> propose next open-ended research questions
  -> promote mature scaffold
  -> continue expand / assess / publish
```

Early exploration should map model families, probe families, methods,
systematics, and missing coverage. The field map turns that breadth into a
review taxonomy before the loop chooses assessable focuses. After targeted
expansion, the runner selects a compact evidence packet and deep-materializes
only the paper graphs or reasoning chains needed for the selected focus.
Assessment then reads that high-density packet instead of the full broad
landscape.

## Command Semantics

### `gaia research explore`

Broadly scan LKM results and update the package-local research process.

Canonical writes:

- materialize this scan's search items as a shallow local Gaia source package
  and attach it with the same local dependency contract as `gaia pkg add
  --local`;
- create or refresh inquiry hypotheses for promising directions;
- create inquiry obligations for obvious coverage gaps;
- keep selected paper leads as candidates for later expansion.

Trace writes:

- raw search result cache;
- landscape summary;
- command/event log.

Default guardrail: write only shallow source claims/notes from the already
available search output. Do not deep-pull paper graphs during the first broad
scan.

The landscape keeps artifact-local `items` for trace readability. When source
materialization succeeds, each item also gets `source_package_ref.ref`, a Gaia
package QID that assessment analysis can use in `claim_refs` for scaffolded
`candidate_relation(...)` writes.

### `gaia research focus`

Turn a landscape into a small set of assessable research questions.

Canonical writes:

- up to 3 accepted focuses become `question(...)` declarations in package source;
- the active focus is recorded with `gaia inquiry focus`;
- coverage gaps become `gaia inquiry obligation` records;
- tentative interpretations may become `gaia inquiry hypothesis` records.

Trace writes:

- LLM focus-analysis input/output;
- focus-selection rationale;
- human-readable focus report.

`focuses.json` is not a canonical focus registry. It is only an audit record of
one synthesis step.

### `gaia research expand`

Expand around a focus or obligation.

Canonical writes:

- selected paper leads stay as candidates for assessment;
- new gaps update inquiry obligations;
- new working interpretations update inquiry hypotheses.

Trace writes:

- targeted search cache;
- expansion summary;
- paper-candidate rationale.

Expansion does not materialize paper graphs. It fills coverage around a focus or
obligation without letting a few early papers dominate the map.

### `gaia research assess`

Assess one focus against selected evidence.

Canonical writes:

- optional `--materialize-paper <paper_id>` materializes a selected full LKM
  paper graph as a deep local evidence package;
- optional `--materialize-paper-from-claim <claim_id>` resolves a selected LKM
  claim to its backing paper graph, then materializes that full paper package;
- optional `--materialize-chain <claim_id>` materializes selected LKM claim
  reasoning chains as a focused local evidence package without pulling the
  whole paper graph;
- unresolved issues become inquiry obligations;
- tentative interpretations become inquiry hypotheses or `note(...)`;
- weak relations become `candidate_relation(...)` scaffolds;

Trace writes:

- assessment LLM input/output;
- evidence table or citation cache;
- readable mini-review;
- stop/review metrics.

Assessment should not normally write formal `claim(...)`, `contradict(...)`,
`equal(...)`, or `derive(...)` records. Those require a later scaffold-promotion
gate.

### `gaia research propose`

Turn an assessment into open-ended next research directions.

Canonical writes:

- by default, none; proposals are written as a reviewable trace artifact;
- with `--accept`, up to 3 accepted `research_question` proposals become package
  `question(...)` declarations;
- accepted proposal questions can become the active inquiry focus;
- tentative hypotheses become inquiry hypotheses;
- unresolved requirements become inquiry obligations.

Trace writes:

- proposal artifact with research questions, tentative hypotheses, candidate
  obligations, source refs, and notes;
- command/event log recording whether proposals were accepted.

Proposal is not a claim-writing step. It must not emit stable truth claims. It
is the handoff from evidence assessment to the next cycle of research,
simulation, experiment, proof, benchmark, or targeted evidence gathering.

### `gaia research promote`

Promote mature scaffolded package state into formal knowledge.

Canonical writes:

- `candidate_relation(...)` -> formal relation when evidence and obligations
  support the stronger commitment;
- tentative finding -> `claim(...)` when it is well scoped and grounded;
- reasoning chain -> `derive(...)` when premises and conclusion are explicit;
- scaffold link -> `materialize(...)` to record what formal record supersedes
  the scaffold.

Trace writes:

- promotion rationale;
- rejected or deferred candidates;
- review/check output.

Promotion is narrow. It is not the orchestrator for the whole research loop.
Formal source synthesis from assessment scaffolds remains deferred until a
separate promotion contract and review gate are designed.

## Minimal CLI Story

The user-facing commands should stay short because inquiry writes are the
default behavior:

```bash
gaia research explore "$PKG" --mode scan --search-json "$RUN/searches/01.json"

gaia research focus "$PKG" --analysis-json "$RUN/analysis/focus-analysis.json"

gaia research expand "$PKG" \
  --focus rq_h0_systematics_vs_new_physics \
  --search-json "$RUN/searches/targeted-01.json"

gaia research assess "$PKG" \
  --focus rq_h0_systematics_vs_new_physics \
  --materialize-paper 811827932371615744 \
  --materialize-chain gcn_selected_reasoning_claim \
  --analysis-json "$RUN/analysis/assess-analysis.json"

gaia research propose "$PKG" \
  --from-assessment "$RUN/artifacts/assessment.json" \
  --analysis-json "$RUN/analysis/proposal-analysis.json" \
  --accept

gaia research promote "$PKG" \
  --scaffold cand_h0_distance_ladder_vs_sound_horizon \
  --by formal_h0_tension_relation
```

Opt-out flags are for evaluation and debugging:

- `--artifact-only`: write trace artifacts only;
- `--dry-run`: show planned writes without applying them;

`--materialize-paper`, `--materialize-paper-from-claim`, and
`--materialize-chain` are the explicit deep paths. Use them after a focus,
paper lead, or claim lead is selected, not during the initial broad landscape
scan. Prefer `--materialize-chain` when the assessment needs the local
premise-conclusion chain for one claim but does not need the whole paper graph.

## Mapping From Old Artifacts

| Old artifact concept | Canonical home | Trace role |
|----------------------|----------------|------------|
| review field map | non-canonical review scaffold | record induced taxonomy, controversy axes, and coverage-expansion rationale |
| focus artifact | `question(...)`, inquiry focus, inquiry obligations | record LLM synthesis and ranking |
| review coverage gap | field-map/focus/assessment artifact unless it blocks the current focus | keep original explanation and suggested queries |
| blocking focus gap | inquiry obligation | preserve actionability rationale |
| assessment relation | `candidate_relation(...)` until promoted | preserve evidence snippets and citation anchors |
| candidate obligation | inquiry obligation | preserve assessment rationale |
| search item | shallow local source package added through `gaia pkg add --local` semantics | keep raw row for trace and LLM contract |
| paper lead | deep `gaia pkg add --lkm-paper` only when selected | keep raw search/cache row and pull candidate command |
| proposal | package `question(...)` only when accepted; otherwise inquiry hypothesis / obligation | keep proposal rationale and source refs |
| stable conclusion | `claim(...)` / `derive(...)` / formal relation | preserve review history |
| stop criteria | inquiry/review decision input | record metrics and timing |

Raw search results, command traces, timing, and LLM analysis JSON remain useful,
but they are non-canonical.

## Relationship To `gaia-lkm-explore`

The older `gaia-lkm-explore` workflow is a useful reference for three ideas:

- package-local state should steer the next round;
- open inquiry obligations should influence frontier selection;
- compile/review/infer checkpoints should happen between rounds.

The new research loop differs in one important way: broad landscape, focus
synthesis, targeted expansion, assessment, and scaffold promotion are separate
steps. This prevents the loop from narrowing too early around one frontier or
one paper cluster.

## Current Implementation Status

The current implementation follows the package/inquiry-centric direction for the
main loop:

- `explore` and `expand` write landscape artifacts, materialize shallow source
  packages from search items, attach those packages as local dependencies, and
  sync candidate focuses / coverage gaps into inquiry hypotheses and
  obligations;
- topic-only `run` with `--analysis-provider litellm` lets the runner generate
  broad queries, induce a field map, optionally search thin review buckets, and
  pass the scan, coverage landscape, and field map into focus synthesis, then
  select/deep-materialize a compact evidence packet for assessment;
- `focus` writes at most 3 accepted focuses as package `question(...)`
  statements and sets the first as the inquiry focus;
- `assess` writes review notes, inquiry hypotheses/obligations, and
  `candidate_relation(...)` only when concrete claim references are supplied;
  it can also materialize selected deep LKM evidence with
  `--materialize-paper`, `--materialize-paper-from-claim`, or
  `--materialize-chain`;
- `propose` writes proposal artifacts from assessments; with `--accept`, it
  writes accepted open-ended research questions as package `question(...)`
  statements and records related hypotheses/obligations in inquiry state;
- `promote` writes an explicit `materialize(...)` link from scaffold to formal
  records; formal source synthesis remains deferred.

Known remaining gaps:

- `promote` records materialization links but does not synthesize formal
  `claim(...)`, `derive(...)`, `infer(...)`, or relation statements yet. That
  requires a dedicated LKM-to-Gaia promotion contract and review-gate design
  first, and is intentionally marked deferred in the roadmap.
- legacy `.gaia/exploration/` import and `gaia-lkm-explore` deprecation are not
  implemented yet. Old artifacts may be provenance inputs, but must not become
  canonical semantic state.
- LKM public writeback, Propose -> external discovery/research -> Merge, and
  hosted/TUI product surfaces are explicitly later ecosystem work.

Current implementation order is defined in
[`../../specs/2026-06-01-research-actions-implementation-roadmap.md`](../../specs/2026-06-01-research-actions-implementation-roadmap.md).
Do not resurrect older milestone plans when implementing the next slice.
