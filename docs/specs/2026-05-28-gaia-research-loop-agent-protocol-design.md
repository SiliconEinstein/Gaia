# Gaia Research Loop Agent Protocol Design

> **Status:** Draft
>
> **Date:** 2026-05-28
>
> **Related specs:**
>
> - [Gaia LKM Explore and Evidence Assess Design](2026-05-25-gaia-lkm-explore-assess-design.md)
> - [LKM Explore Artifact MVP Design](2026-05-26-lkm-explore-artifact-mvp-design.md)
> - [LKM Explore Iterative Landscape Design](2026-05-27-lkm-explore-iterative-landscape-design.md)
>
> **Scope:** Define a unified agent-facing protocol and CLI for the first two
> stages of the larger Gaia research loop: `Explore -> Assess`. The protocol
> lets a generic coding agent run the loop with a thin in-repo skill, a CLI, and
> self-contained task envelopes.

## 1. Goal

The current `gaia-lkm-explore` work has established the right research method:
start with a breadth-first paper landscape, synthesize assessment focuses, then
enter evidence assessment only for selected focuses. The missing layer is a
single protocol that tells an external agent what to do next, what output shape
to produce, how to submit it, and how to recover from validation failures.

This spec proposes a new top-level CLI:

```bash
gaia-research-loop next <pkg>
gaia-research-loop submit <pkg> <candidate.json>
gaia-research-loop gate <pkg>
gaia-research-loop status <pkg>
```

The MVP is LKM-backed, but the name deliberately does not include `explore`.
Explore is one stage inside the loop, not the whole loop.

The protocol boundary is:

```text
agent / LLM:
  research judgment, query planning, focus synthesis, evidence diagnosis

Gaia kernel:
  task envelopes, contracts, validation, persistence, gates, next-step routing
```

Gaia does not need an embedded LLM provider in the MVP. The agent uses its own
model and reasoning, reads a task envelope, writes a candidate JSON file, and
submits it through the CLI.

## 2. Non-goals

This spec does not:

- replace the full future loop `Explore -> Assess -> Propose -> Discover ->
  Merge`;
- implement `Propose`, `Discover`, `Merge`, wet-lab execution, or experiment
  automation;
- require a Gaia-hosted LLM client;
- require automatic installation of a Codex/Claude/Cursor skill;
- require backward compatibility with `.gaia/exploration/` as the canonical
  storage location;
- formalize every retrieved paper into claims during Explore;
- adjudicate final truth during Assess;
- merge assessed claims back into Gaia or LKM.

The MVP should keep old `gaia-lkm-explore` artifacts readable where practical,
but new protocol artifacts should use the canonical `research_loop` layout
defined below.

## 3. Research Model

The loop has two implemented stages in the MVP:

```text
Explore:
  build and iterate a paper-level landscape until useful focuses emerge

Assess:
  diagnose the evidence around one selected focus and map remaining gaps
```

The important separation is:

```text
Paper level  ->  Focus level  ->  Claim level
landscape        questions       propositions and evidence relations
```

Explore operates primarily at paper and focus level. It should not eagerly turn
every paper into a global claim frontier. Assess starts from one or more
selected focuses and may then read, pull, or formalize evidence more deeply.

Explore-to-Assess handoff happens at the focus level, not at the whole-domain
level. A broad landscape may contain many focuses; only ready selected focuses
enter Assess.

## 4. Canonical Layout

New loop state lives under:

```text
<pkg>/.gaia/research_loop/
  state.json
  events.jsonl
  explore/
    tasks/
    candidates/
    artifacts/
  assess/
    tasks/
    candidates/
    artifacts/
```

`state.json` is a navigation index and cache, not the source of truth. The
source of truth is the set of task, candidate, artifact, gate, and event files.
If `state.json` is missing or stale, `gaia-research-loop status` and `next`
should be able to rebuild it by scanning artifacts.

`events.jsonl` records append-only audit events such as:

- `task_emitted`
- `candidate_submitted`
- `validation_failed`
- `artifact_written`
- `gate_passed`
- `gate_revised`
- `state_rebuilt`

## 5. CLI Semantics

### 5.1 `next`

`next` inspects the package and emits the next recommended task envelope. It
also writes that envelope to the appropriate `tasks/` directory.

It returns:

- `recommended_action`: the Gaia kernel's preferred next action;
- `allowed_actions`: a small set of legal alternatives;
- `task_path`: the written task envelope path;
- `submit_command`: the exact command the agent should run after producing a
  candidate;
- `rationale`: why the kernel recommends this action.

The agent may choose an allowed alternative, but must record an override
rationale in its submitted candidate.

### 5.2 `submit`

`submit` validates a candidate JSON against its task envelope. The candidate
must include `task_id`; Gaia uses that id to load the matching task from the
stage `tasks/` directory. On success it writes or updates the corresponding
artifact. On failure it records the validation error and leaves the loop on the
same task.

Validation checks include:

- JSON schema validity;
- required fields;
- allowed action membership;
- allowed reference grounding;
- candidate/task id match;
- stage-specific invariants.

### 5.3 `gate`

`gate` validates the current stage boundary. For Explore it checks whether at
least one selected focus is ready for assessment, or whether the loop has a
valid reason to continue landscape expansion or stop. For Assess it checks that
the evidence diagnosis, gap map, and next tests are grounded and complete enough
for downstream proposal work.

### 5.4 `status`

`status` summarizes current state, latest tasks, latest artifacts, validation
failures, available focuses, and recommended next actions. It should be useful
to both humans and agents.

## 6. Task Envelope

Every semantic agent step is represented by a self-contained task envelope.
The envelope is the main protocol object.

Required fields:

```json
{
  "schema": "gaia.research_loop.task.v1",
  "task_id": "task-...",
  "stage": "explore",
  "kind": "query_plan",
  "objective": "...",
  "inputs": {},
  "instructions": [],
  "allowed_actions": [],
  "recommended_action": "...",
  "output_contract": {},
  "allowed_refs": [],
  "minimal_example": {},
  "submit_command": "gaia-research-loop submit ...",
  "validation": {},
  "repair_context": null
}
```

The task envelope must be sufficient for a generic coding agent to proceed
without reading implementation code. It should not depend on hidden prompt
state.

Every candidate submitted for a task must include the matching `task_id`,
`stage`, `kind`, and `selected_action`. `selected_action` must equal the
recommended action or one of the task's allowed alternatives. If it differs from
the recommendation, the candidate must include `override_rationale`.

`minimal_example` is intentionally tiny. It demonstrates JSON shape and
reference syntax, but must not contain realistic domain content that would tempt
the agent to copy it.

`output_contract` is the authoritative machine-readable JSON schema. The
example is illustrative only.

## 7. Repair Loop

Validation failure does not create a separate repair task. Instead, `next`
returns the same task with `repair_context` populated.

`repair_context` includes:

- the failed candidate path;
- structured validation errors;
- a short repair instruction;
- any fields that passed validation and can be preserved;
- the same `submit_command`.

This keeps the agent loop simple:

```text
read task -> write candidate -> submit
  if valid: advance
  if invalid: next returns same task with repair_context
```

## 8. State Flow

The MVP state flow is:

```text
scope
-> query_plan
-> search_execution
-> landscape
-> focus_synthesis
-> explore_gate
-> assessment_context
-> evidence_diagnosis
-> assess_gate
-> done
```

The Explore portion is iterative:

```text
query_plan -> search_execution -> landscape -> focus_synthesis -> explore_gate
       ^                                                       |
       |                                                       |
       +------------- needs_more_landscape --------------------+
```

Stop conditions include:

- at least one selected focus is ready for assessment;
- search budget is exhausted;
- no materially new papers or evidence families are found;
- required scope dimensions are sufficiently covered;
- the agent chooses an allowed stop action with rationale;
- a human stops the run.

## 9. Explore Tasks

### 9.1 Scope

`scope` turns a seed question into a structured exploration scope. In the MVP,
scope may be user-authored or agent-authored, but the submitted scope must be
validated and persisted.

Typical fields:

- seed question;
- domain profile;
- population, system, material, model, or regime dimensions;
- outcomes or observables;
- comparators or alternative explanations;
- decision context;
- search budget.

### 9.2 Query Planning

`query_plan` is an LLM/agent task. It is not a fixed deterministic recipe.

Inputs include:

- current scope;
- prior landscape summaries;
- existing focuses;
- coverage gaps;
- remaining budget;
- allowed LKM search command template.

Output includes a small set of planned queries with purpose, source focus or
gap, expected evidence family, and budget. Gaia validates mechanical properties
such as non-empty query strings, duplicate removal, budget bounds, and valid
source references.

### 9.3 Search Execution

`search_execution` is a mechanical agent task. Gaia emits exact commands and
expected output paths. The agent runs those commands, saves raw LKM JSON, and
submits the paths.

The agent should not transform raw LKM output into paper leads. Gaia parses raw
search envelopes into landscape artifacts so the process remains reproducible.

### 9.4 Landscape

`landscape` is a Gaia artifact produced from raw search results. It contains:

- search provenance;
- paper leads;
- LKM node refs when available;
- evidence families;
- deduplicated contacts;
- coarse coverage of scope dimensions;
- missing or weakly covered dimensions.

### 9.5 Focus Synthesis

`focus_synthesis` is an LLM/agent task. Deterministic rules may assemble
grounding packets, but the scientific focus itself is semantic and should be
generated by an LLM-assisted or human research agent.

Each focus should include:

- `focus_id`;
- `research_question`;
- `why_it_matters`;
- supporting refs;
- conflicting, limiting, or missing refs;
- covered scope dimensions;
- missing dimensions;
- `coverage_status`;
- `ready_for_assess`;
- recommended assessment mode;
- next landscape queries if more coverage is needed.

A paper cluster is not automatically a focus. It is grounding material from
which the agent may synthesize one or more focuses.

### 9.6 Explore Gate

The Explore gate checks whether the loop can enter Assess. It should pass when
there is at least one selected focus with enough grounded evidence for
assessment. It should revise when the loop needs more landscape, has no selected
focus, or has ungrounded references.

Focus selection is hybrid:

- Gaia recommends focuses;
- the agent may select one or more recommended focuses;
- the agent may choose to continue landscape expansion;
- overrides require `selection_rationale`.

## 10. Assess Tasks

### 10.1 Assessment Context

`assessment_context` packages the selected focus for deeper evaluation. It
should include:

- selected focus;
- supporting and opposing refs;
- relevant paper leads;
- relevant LKM nodes or claims;
- scope dimensions;
- known gaps;
- assessment mode;
- allowed evidence refs.

### 10.2 Evidence Diagnosis

`evidence_diagnosis` is an LLM/agent task. The MVP output is an evidence table
and gap map, not final adjudication.

Output includes:

- evidence items;
- candidate claims;
- contradictions or tensions;
- limitations;
- missing evidence;
- gap map;
- next tests or next searches;
- confidence notes;
- provenance refs.

Gaia validates schema and grounding. It does not decide whether the scientific
conclusion is true.

### 10.3 Assess Gate

The Assess gate passes when the evidence diagnosis is coherent, grounded, and
useful as input to future `Propose`. It should check:

- each evidence item has allowed refs;
- each contradiction links at least two evidence items or claims;
- limitations are explicit;
- gap map entries identify what evidence would reduce uncertainty;
- next tests are tied to gaps;
- selected focus id is preserved.

## 11. Thin Skill Contract

The in-repo skill should be thin. It should teach a generic agent the loop
algorithm, not encode scientific schemas.

The skill should say:

```text
1. Run `gaia-research-loop next <pkg>`.
2. Open the returned task envelope.
3. Follow `instructions`.
4. If the task requires reasoning, use your own model.
5. Write candidate JSON matching `output_contract`.
6. Run `submit_command`.
7. If validation fails, run `next` again and repair the same task.
8. Repeat until `status` or `gate` reports done.
```

The skill must not hardcode query planning, focus synthesis, or assessment
schemas. Those belong in task envelopes.

## 12. Relationship to Existing `gaia-lkm-explore`

The existing `gaia-lkm-explore` implementation remains valuable as an Explore
stage engine. The new protocol should initially reuse its internals where that
reduces risk:

- landscape parsing;
- focus context generation;
- focus validation;
- artifact and gate logic;
- provenance checks.

Conceptually, however, `gaia-research-loop` is the parent interface:

```text
gaia-research-loop
  explore stage
    may call or reuse lkm explorer internals
  assess stage
    will add evidence diagnosis artifacts
```

The new canonical storage is `.gaia/research_loop/`. A later migration may copy
or index old `.gaia/exploration/` artifacts, but the MVP does not need to keep
writing new artifacts there.

## 13. Schema and Validation

All task, candidate, artifact, and gate objects should have versioned schemas:

```text
gaia.research_loop.task.v1
gaia.research_loop.candidate.v1
gaia.research_loop.artifact.v1
gaia.research_loop.gate.v1
```

Pydantic models should be the Python source of truth. Task envelopes should
embed the JSON schema for the expected candidate output.

Grounding rules are stage-specific, but the common rule is:

```text
Any evidence or source reference in a candidate must appear in the task's
allowed_refs or in an artifact explicitly listed by the task inputs.
```

## 14. Testing Strategy

The implementation should be driven by tests at three levels:

- model tests for task/candidate schema validation;
- CLI tests for `next`, `submit`, `status`, and `gate`;
- smoke tests with a tiny synthetic package and one realistic saved LKM search
  fixture.

PR-gate tests should cover user-facing CLI behavior and schema compatibility.
Lower-level helper tests can remain in the nightly slice unless they protect a
public artifact contract.

## 15. Open Implementation Slices

Suggested implementation order:

1. Add shared research-loop storage, event log, and schema models.
2. Add `gaia-research-loop status` and state rebuild.
3. Add `next` for `scope` and `query_plan`.
4. Add `submit` validation and repair context.
5. Add mechanical `search_execution` tasks from accepted query plans.
6. Reuse or adapt LKM landscape generation under `.gaia/research_loop/explore`.
7. Add LLM/agent `focus_synthesis` task envelopes and validators.
8. Add Explore gate and focus selection.
9. Add Assess context and `evidence_diagnosis` task envelopes.
10. Add Assess gate and final loop status.

This order preserves the central idea: every intelligent step is mediated by a
self-contained task envelope, and every transition is validated by Gaia.
