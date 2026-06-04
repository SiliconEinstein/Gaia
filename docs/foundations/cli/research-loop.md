---
status: current-canonical
layer: cli
since: v0.6
---

# Research Loop CLI

`gaia research` is the package-native workflow for broad exploration, focus
synthesis, targeted expansion, and evidence assessment. Its canonical state
lives in Gaia package source and Gaia inquiry state; research JSON exists only
as trace, cache, or audit output.

The guiding rule is:

> Do not create a second research data model when Gaia package primitives or
> `gaia inquiry` can express the same state.

## State Model

Research state has three layers.

| Layer | Canonical? | Examples | Purpose |
|-------|------------|----------|---------|
| Package source | yes | `question(...)`, `note(...)`, `candidate_relation(...)`, `claim(...)`, `derive(...)`, `materialize(...)`, package dependencies | Durable knowledge and scaffolded knowledge |
| Inquiry state | yes | current focus, open obligations, hypotheses, rejections, tactic log | Mutable research process state |
| Research trace | no | raw search JSON, LLM analysis JSON, command events, rendered reports, timing, stop metrics | Reproducibility, debugging, meeting review |

The package and inquiry state are what later compilation, review, inference,
publication, and LKM ingestion should consume. Trace files should be readable and
auditable, but they are not the source of truth for scientific knowledge.

## Loop Shape

The loop remains breadth-first at the start and narrows only after the field
landscape is visible:

```text
broad explore
  -> focus synthesis
  -> targeted expand
  -> assess one focus
  -> promote mature scaffold
  -> continue expand / assess / publish
```

Early exploration should map model families, probe families, methods,
systematics, and missing coverage. Assessment can then inspect paper graphs,
reasoning chains, and selected LKM-backed packages for a specific focus.

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

Expansion does not pull papers. It fills coverage around a focus or obligation
without letting a few early papers dominate the map.

### `gaia research assess`

Assess one focus against selected evidence.

Canonical writes:

- unresolved issues become inquiry obligations;
- tentative interpretations become inquiry hypotheses or `note(...)`;
- weak relations become `candidate_relation(...)` scaffolds;
- selected papers or claim packages may be pulled when deeper evidence is needed
  in the next implementation milestone.

Trace writes:

- assessment LLM input/output;
- evidence table or citation cache;
- readable mini-review;
- stop/review metrics.

Assessment should not normally write formal `claim(...)`, `contradict(...)`,
`equal(...)`, or `derive(...)` records. Those require a later scaffold-promotion
gate.

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
  --analysis-json "$RUN/analysis/assess-analysis.json"

gaia research promote "$PKG" \
  --scaffold cand_h0_distance_ladder_vs_sound_horizon \
  --by formal_h0_tension_relation
```

Opt-out flags are for evaluation and debugging:

- `--artifact-only`: write trace artifacts only;
- `--dry-run`: show planned writes without applying them;

Future assessment expansion should add `--pull-budget N` once paper/package
pulling is wired into the assess boundary.

## Mapping From Old Artifacts

| Old artifact concept | Canonical home | Trace role |
|----------------------|----------------|------------|
| focus artifact | `question(...)`, inquiry focus, inquiry obligations | record LLM synthesis and ranking |
| coverage gap | inquiry obligation | keep original explanation |
| assessment relation | `candidate_relation(...)` until promoted | preserve evidence snippets and citation anchors |
| candidate obligation | inquiry obligation | preserve assessment rationale |
| search item | shallow local source package added through `gaia pkg add --local` semantics | keep raw row for trace and LLM contract |
| paper lead | deep `gaia pkg add --lkm-paper` only when selected | keep raw search/cache row and pull candidate command |
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
- `focus` writes at most 3 accepted focuses as package `question(...)`
  statements and sets the first as the inquiry focus;
- `assess` writes review notes, inquiry hypotheses/obligations, and
  `candidate_relation(...)` only when concrete claim references are supplied;
- `promote` writes an explicit `materialize(...)` link from scaffold to formal
  records.

Known remaining gaps:

- assessment does not yet call deep `gaia pkg add --lkm-paper` or reasoning-chain
  pull primitives directly;
- `promote` records materialization links but does not synthesize formal
  `claim(...)` or relation statements;
- LLM prompt templates and report rendering still need iteration around review
  quality, citation style, and stop criteria.
