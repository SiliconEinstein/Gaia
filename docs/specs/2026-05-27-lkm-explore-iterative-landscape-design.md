# LKM Explore Iterative Landscape Design

> **状态：** Experimental / historical reference。
>
> **当前 canonical 验收标准：**
> [Research Module Split Acceptance](2026-06-13-research-module-split-acceptance.md)
>
> **当前执行计划：**
> [Research Report Workflow Parity Migration Plan](../plans/2026-06-13-research-report-workflow-parity-migration.md)
>
> **Prior-art context：**
> [Research Actions Package-Native Overview](2026-06-01-research-actions-package-native-overview.md)
> 和
> [Research Actions Implementation Roadmap](2026-06-01-research-actions-implementation-roadmap.md).
>
> **适合用于：** iterative landscape 和 breadth-first exploration 经验。
>
> **不要作为：** 当前 `gaia research explore` implementation contract。
>
> **Date:** 2026-05-27
>
> **Related specs:**
>
> - [Gaia LKM Explore and Evidence Assess Design](2026-05-25-gaia-lkm-explore-assess-design.md)
> - [LKM Explore Artifact MVP Design](2026-05-26-lkm-explore-artifact-mvp-design.md)
>
> **Scope:** Refine the core research-survey method behind `gaia-lkm-explore`.
> This spec replaces a one-pass `landscape -> focuses -> assess` mental model
> with an iterative paper-level landscape loop that repeatedly synthesizes and
> covers focuses before entering evidence assessment.

## 0. Relationship to the Artifact MVP

This spec is a v2 evolution of the artifact MVP in
[LKM Explore Artifact MVP Design](2026-05-26-lkm-explore-artifact-mvp-design.md).
The MVP remains the default implementation until this v2 work lands.

The relationship is intentionally evolutionary:

- MVP `paper_lead_cluster` focuses are temporary deterministic placeholders.
  In v2 they become grounding bundles for LLM/human focus synthesis, not final
  assessment focuses.
- MVP `artifact.json` uses `gaia.sop.artifact.v1` and links a single
  `artifacts.landscape`. V2 should introduce a schema bump and link all
  landscape rounds or a stable aggregate.
- MVP `gate` checks structural readiness for the v1 artifact. V2 gate extends
  that contract with focus status, coverage, and grounding checks.
- Until v2 is implemented, v1 artifacts remain readable and valid. New v2
  producers should not rewrite existing v1 artifacts in place.

## 1. Core Idea

Research exploration should not jump directly from a seed question into
claim-level graph expansion. The first job is to understand the paper and
evidence landscape well enough to know which questions are worth assessing.

The recommended high-level flow is:

```text
Scope
  -> iterative paper-level landscape loop
       search / gather papers
       synthesize or update focuses
       diagnose coverage gaps
       plan the next landscape round
     until core focuses are assessable or budget is exhausted
  -> select focus(es)
  -> evidence assessment
  -> claim-level formalization only where needed
```

This is intentionally not a single linear pass. A first broad search often only
reveals the shape of the field. The important assessment questions usually
emerge after seeing the first batch of papers, and those provisional focuses
should drive the next round of paper-level search.

For example:

- In aspirin primary prevention, the first landscape may reveal RCTs,
  meta-analyses, and guidelines. Only then does the central focus become
  benefit versus major bleeding, subgroup net benefit, or guideline-threshold
  disagreement.
- In Hubble tension, the first landscape identifies early- and late-universe
  measurement families. Only then does the focus become new physics versus
  systematics, local distance ladder disagreement, or global-fit side effects.
- In SEI dendrite suppression, the first landscape may collect supportive
  interphase papers. Only after opposing or boundary evidence appears does the
  focus become short-term morphology suppression versus long-term PLI/dead-Li
  prevention or pouch/full-cell scaling.

## 2. Three Levels

The workflow has three different levels. They must not be collapsed.

```text
Paper level  <-->  Focus level  -->  Claim level
materials          questions         formalized propositions

round N papers     synthesize        only after focus selection
drive focuses      next queries      and assessment
```

### 2.1 Paper Level

The paper level asks:

```text
What papers, guidelines, datasets, benchmarks, models, or evidence families
exist around this topic?
```

Outputs should include:

- paper leads;
- evidence families;
- search queries and provenance;
- representative papers per family;
- coarse coverage of populations, outcomes, mechanisms, regimes, methods, or
  model families;
- missing evidence families.

The paper level should not eagerly formalize every claim. It should avoid
turning every retrieved paper into a claim frontier. Its main artifact is a
landscape, not a Gaia graph.

### 2.2 Focus Level

The focus level asks:

```text
Which questions, tensions, gaps, or assessment targets are worth deeper
evaluation?
```

A focus is not a paper cluster and not yet a formal Gaia claim. It is a
research question grounded in the paper landscape.

Examples:

```text
Does aspirin's reduction in first cardiovascular events outweigh major bleeding
risk in primary prevention?

Can early dark energy reduce the H0 tension without degrading BAO, SNe, S8, or
CMB fit quality?

Does SEI-mediated dendrite suppression address only short-term morphology, or
also long-term PLI/dead-Li prevention under practical full-cell regimes?
```

Focus synthesis is a semantic task and should be performed by an LLM-assisted or
human research agent. Deterministic rules may gather grounding packets, but they
should not pretend to generate scientific focuses by themselves.

Every focus must carry provenance:

- paper refs;
- query refs;
- LKM node or claim refs when available;
- scope dimensions it covers;
- missing dimensions or uncertainty;
- whether it is ready for assessment.

### 2.3 Claim Level

The claim level asks:

```text
For one selected focus, what concrete propositions, evidence relations, limits,
and contradictions should be represented or assessed?
```

This is where papers may be pulled, read in detail, decomposed into claims, and
linked into Gaia. It is downstream of focus selection. Claim-level expansion
should be targeted, not a global default immediately after the seed.

`frontier` belongs here as an internal graph-expansion worklist. It should not be
the user's primary model for early-stage research exploration.

## 3. Iterative Landscape Loop

The core loop is:

```text
Landscape round N:
  1. Start from scope and current focuses.
  2. Generate or accept a query plan.
  3. Search and gather paper-level results.
  4. Deduplicate and cluster paper leads.
  5. LLM/human synthesizes or revises focuses.
  6. Diagnose focus coverage.
  7. Either stop or plan round N+1.
```

The loop is paper-level until a focus is selected for assessment. It can run for
one round for small questions, or several rounds for broad domains.

### 3.1 Round 0

Round 0 should be intentionally broad:

- cover likely evidence families;
- include obvious positive, negative, review, guideline, and methods queries;
- avoid pulling full papers unless necessary for disambiguation;
- preserve raw search provenance.

Round 0 produces provisional focuses, not final conclusions.

### 3.2 Later Rounds

Later rounds are focus-driven. They search for what is missing:

- opposing or limiting evidence;
- subgroup or regime evidence;
- guideline or consensus statements;
- model-family alternatives;
- methods papers or benchmark papers;
- long-term, scaling, or failure-mode evidence.

The loop should update existing focuses instead of creating a fresh unrelated
list every round. A focus may move through states such as:

```text
provisional -> needs_more_landscape -> ready_for_assess -> deferred
```

`deferred` is a parking state, not necessarily a permanent rejection. A user or
LLM planner may move a deferred focus back to `needs_more_landscape` in a later
run if the research scope, budget, or evidence availability changes.

### 3.3 Query Planning

Query planning is also a semantic task, but its requirements vary by round.

Round 0 may use deterministic expansion from the scope:

- seed text;
- scope dimensions;
- broad review, guideline, methods, positive, and negative queries;
- domain-neutral alternates such as "systematic review", "controversy",
  "failure mode", or "benchmark".

Round N >= 1 should be LLM/human planned from `coverage_gaps`,
`existing_focuses`, and each focus's `next_landscape_queries`. The engine should
validate only mechanical properties:

- query strings are non-empty;
- duplicate queries are removed;
- each query records its source focus or gap when known;
- the planner cannot delete prior round provenance.

## 4. LLM Role

LLM synthesis is not an optional enhancement. It is the central step that turns a
paper landscape into research focuses.

The deterministic engine should provide the LLM with a grounded context packet:

```json
{
  "scope": {},
  "landscape_rounds": [
    {
      "round": 0,
      "path": ".gaia/exploration/landscape-0.json",
      "purpose": "broad_initial_survey"
    }
  ],
  "paper_leads": [],
  "queries": [],
  "existing_focuses": [],
  "coverage_gaps": [],
  "instructions": [
    "Propose only focuses grounded in evidence refs.",
    "Prefer 2-5 assessment questions.",
    "Separate paper-level material from claim-level conclusions.",
    "Do not state a tension as established unless the refs support it.",
    "For each focus, list missing evidence needed before assessment."
  ]
}
```

The LLM or human agent should return structured focuses:

```json
{
  "focuses": [
    {
      "id": "focus_benefit_harm",
      "level": "focus",
      "kind": "benefit_harm_tradeoff",
      "question": "Does aspirin's cardiovascular benefit outweigh major bleeding risk in primary prevention?",
      "candidate_claims": [
        "Aspirin reduces first cardiovascular events in some primary-prevention populations.",
        "Aspirin increases major bleeding risk."
      ],
      "evidence_refs": [],
      "coverage": {
        "status": "needs_more_landscape",
        "missing_dimensions": ["older adults", "guideline thresholds"]
      },
      "next_landscape_queries": []
    }
  ]
}
```

The engine then validates the structure. It should not silently accept beautiful
but ungrounded questions.

Mandatory grounding validation:

- every `evidence_refs[].id` must resolve to a paper id from one of the
  landscape rounds or to an LKM node id present in a landscape paper lead;
- every focus marked `ready_for_assess` must have at least one grounded evidence
  ref;
- ungrounded refs are copied into a validation warning such as
  `ungrounded_refs`, and the focus status is downgraded to `provisional` unless
  a human explicitly overrides it;
- the gate report must surface ungrounded refs so assessment does not inherit
  hallucinated provenance.

## 5. Coverage and Stop Criteria

The landscape loop stops when at least one selected focus is assessable, not
when search results are exhausted.

A focus is assessable when it has enough paper-level coverage for the next stage
to evaluate it without restarting broad exploration.

Common coverage dimensions:

- supporting evidence;
- opposing or harm evidence;
- limiting or conditional evidence;
- review or meta-analysis evidence;
- guideline or consensus evidence;
- relevant populations, regimes, model families, or experimental conditions;
- high-signal representative papers.

These dimensions are defaults, not a closed canonical ontology. Domains may add
their own axes, such as cosmological probe families, battery test regimes,
animal-model transfer, benchmark suites, or clinical endpoint types.

Coverage thresholds are also domain-tunable. Counts in examples are illustrative
defaults, not universal truth. The v2 engine should support a simple policy
object such as:

```json
{
  "min_support_refs": 1,
  "min_opposing_or_limiting_refs": 1,
  "required_families": ["review_or_overview"],
  "required_grounded_refs": true
}
```

LLM/human synthesis may propose `coverage_status`, but the engine should
deterministically verify the minimum policy it knows how to check. If the
minimum policy fails, the focus cannot be `ready_for_assess` without an explicit
human override recorded in provenance.

Example focus coverage:

```json
{
  "focus_id": "focus_benefit_harm",
  "coverage_status": "ready_for_assess",
  "evidence_families": ["RCT", "meta_analysis", "guideline"],
  "support_refs": 3,
  "oppose_or_harm_refs": 3,
  "limitation_refs": 2,
  "missing_dimensions": [],
  "stop_reason": "major evidence families represented"
}
```

If coverage is insufficient:

```json
{
  "focus_id": "focus_benefit_harm",
  "coverage_status": "needs_more_landscape",
  "missing_dimensions": ["older adults", "major bleeding", "guidelines"],
  "next_queries": [
    "ASPREE aspirin primary prevention older adults bleeding mortality",
    "USPSTF aspirin primary prevention major bleeding recommendation"
  ]
}
```

Budget can also stop the loop. In that case the artifact should say
`budget_exhausted`, record known limitations, and gate the affected focuses as
`revise` or `deferred`, not as ready.

## 6. Relationship to Existing Concepts

### 6.1 Landscape

`landscape` is the paper-level artifact. It may have multiple rounds:

```text
landscape-0.json
landscape-1.json
landscape-2.json
```

The combined exploration artifact should point to all landscape rounds or to a
stable aggregate, not only the latest file.

### 6.2 Focuses

`focuses` are focus-level artifacts. They should be LLM/human synthesized from
the landscape and then validated by the engine.

`paper_lead_cluster` should not be treated as a real focus. It is at most an
evidence bundle used to support focus synthesis.

### 6.3 Frontier

`frontier` is a claim-level graph-expansion worklist. It answers:

```text
Given a partially materialized Gaia graph, what unmaterialized claim or paper
contact could be expanded next?
```

It should be internal to claim-level assessment or legacy graph expansion. It is
not the right abstraction for deciding what the field's core questions are.

### 6.4 Turn

`turn` is the legacy/global frontier loop. It overlaps with evidence assessment
because both involve reading evidence, extracting claims, and updating graph
context.

Going forward, the main user-facing workflow should not require users to learn
`turn` as a separate research stage. Short term, `turn` remains backward
compatible and unchanged. Long term, its useful mechanics should become an
internal iteration mechanism inside assessment rather than a separate public
stage in the Explore SOP.

### 6.5 Assess

`assess` is the selected-focus deep dive. It consumes a ready focus and evaluates
the evidence around it. It may internally use frontier-like worklists, but its
public contract is focus-centered:

```text
Given this focus, what does the evidence say, what remains unresolved, and what
next test or proposal follows?
```

## 7. Suggested User-Facing Workflow

Short form:

```bash
gaia-lkm-explore scope ./pkg --seed "..."

# Repeat until coverage is sufficient:
gaia-lkm-explore landscape ./pkg --search-json round-0-a.json --search-json round-0-b.json
gaia-lkm-explore focuses ./pkg
gaia-lkm-explore gate ./pkg

gaia-evidence assess \
  --exploration ./pkg/.gaia/exploration/artifact.json \
  --focus <focus-id>
```

The current MVP already accepts repeated `--search-json` values within one
landscape command. V2 should additionally distinguish multiple landscape rounds
and preserve each round's query plan.

Longer-term, the repeated loop can be wrapped by a single orchestrating command:

```bash
gaia-lkm-explore run-landscape ./pkg \
  --seed "..." \
  --max-rounds 3 \
  --coverage-target assessable
```

Internally that command would run:

```text
query planning
  -> search
  -> landscape update
  -> focus synthesis
  -> coverage check
  -> next query planning
```

The artifact trail should remain explicit even if the user uses a single
orchestrating command.

## 8. Artifact Contract Changes

This design implies several changes to the current artifact MVP.

### 8.1 Landscape Rounds

Record multiple landscape rounds:

```json
{
  "landscape_rounds": [
    {
      "round": 0,
      "path": ".gaia/exploration/landscape-0.json",
      "purpose": "broad_initial_survey"
    },
    {
      "round": 1,
      "path": ".gaia/exploration/landscape-1.json",
      "purpose": "focus_gap_followup"
    }
  ]
}
```

### 8.2 Focus Status

Focus records should include:

```json
{
  "level": "focus",
  "question": "...",
  "status": "provisional | needs_more_landscape | ready_for_assess | deferred",
  "coverage": {},
  "next_landscape_queries": [],
  "evidence_refs": [],
  "candidate_claims": []
}
```

### 8.3 Gate Semantics

Explore gate should check:

- at least one focus is `ready_for_assess`;
- ready focuses have evidence refs;
- ready focus refs are grounded in known landscape paper ids or LKM node ids;
- ready focuses have a question, coverage summary, and provenance;
- unready focuses have missing dimensions or next queries;
- known limitations distinguish paper-level gaps from claim-level gaps;
- budget exhaustion is recorded honestly.

Gate should not require all focuses to be ready. A domain can have several
deferred focuses while one selected focus proceeds to assessment.

### 8.4 Schema Version Bump and Migration

V2 should use a new schema identifier, for example `gaia.sop.artifact.v2`.

Migration policy:

- v1 artifacts are kept read-only and remain accepted by v1-compatible commands;
- v2 producers write new artifacts instead of rewriting existing v1 files in
  place;
- `schema_versions_supported` should accept v1 for legacy structural checks and
  v2 for iterative landscape checks;
- examples that contain v1 exploration artifacts do not need migration unless
  they are being used to test v2 behavior;
- a v1-to-v2 adapter may synthesize `landscape_rounds` from the single
  `artifacts.landscape` path, but it must mark the result as migrated and
  preserve known limitations.

## 9. Minimal Next Implementation Slice

The next implementation should not try to build the whole research loop. The
smallest useful slice is:

1. Add an aggregate landscape-round index.
   This extends `build_exploration_artifact` from the MVP, which currently links
   only the latest landscape path.
2. Make `focuses` consume all landscape rounds, not only the latest file.
   This replaces the MVP `build_focuses_artifact` input model, where the latest
   landscape is the sole source.
3. Add an LLM/human synthesis handoff artifact, such as
   `focus_context.json`, that contains the grounded packet for focus synthesis.
4. Validate synthesized focuses with deterministic gate checks.
   This extends the MVP `build_gate_report` with focus status, coverage policy,
   and grounding validation.
5. Update `artifact.json` to link landscape rounds, focus statuses, and assess
   handoff commands.
6. Keep `turn` and `frontier` backward compatible, but remove them from the main
   recommended research-survey path.
   The minimal slice should not change `turn` behavior.

This keeps the core method simple:

```text
Find papers broadly.
Use LLM/human synthesis to name the real questions.
Search again to cover those questions.
Assess only when coverage is good enough.
Formalize claims only after a focus has been selected.
```

## 10. Minimal In-Repo Example: Galileo

The `examples/galileo-v0-5-gaia` package can serve as the smallest reproducible
shape for this loop, even though its content is much smaller than a real
literature survey.

Illustrative v2 flow:

```text
Round 0 paper level:
  seed: example:galileo_v0_5::aristotle_model
  landscape-0.json: broad leads about falling bodies, Galileo, and Aristotelian
  mechanics

Focus synthesis:
  focus_question: What evidence distinguishes the Aristotelian weight-speed
  model from Galileo's equal-acceleration account?
  evidence_refs: paper ids or LKM node ids from landscape-0.json
  status: ready_for_assess if both model families and discriminating evidence
  are grounded; otherwise needs_more_landscape

Assessment:
  assess only that focus, then formalize or inspect claim-level relations such
  as contradiction, support, or experimental premise links.
```

This example should not require broad automatic web search. It is useful because
the repo already compiles and infers the fixture in CLI tests, so future v2 tests
can assert the artifact shape without depending on external LKM availability.

## 11. Non-Goals

This spec does not require:

- automatic LKM search execution inside the engine;
- full paper reading or PDF parsing;
- complete evidence assessment;
- automatic Gaia source writing;
- full Propose / Discover / Merge implementation;
- deprecating existing `turn` behavior immediately.

The goal is to simplify the research workflow model before adding more
automation.
