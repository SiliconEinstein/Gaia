# Research Reference Identity Bug Report

> **Status:** current repair note for package-native research actions.
>
> **Date:** 2026-06-05
>
> **Context:** live end-to-end trace for deconfined criticality after N1
> `gaia research propose`.

## Summary

The interrupted live E2E run exposed one core design bug: research artifacts used
artifact-local `item_0`, `item_1`, ... identifiers as grounding references even though
the underlying search result already had stable LKM variable ids, paper ids, and package
refs. This made the workflow hard for an agent to follow and allowed an invalid
`candidate_relation(...)` scaffold to be written with a `Question` input.

The fix is to make research references stable and typed:

- use `variable:<id>` for LKM variables;
- use `paper:<paper_id>` for papers;
- use `package_ref:<namespace:module::symbol>` for local Gaia package objects;
- use `chain:<id>` for reasoning-chain materialization;
- keep display-only sequence numbers as `display_index`, not as grounding ids.

Row numbers may remain only as `display_index` for UI/table presentation. `item_N` must
not appear in `source_refs`, review inline citations, or relation grounding.

## Bugs Found

### B1. Illegal `promotion_hint` Values Produced Tracebacks

The agent-written assessment analysis used illegal hint combinations:

- `qualifies + candidate_relation`;
- `opposes + candidate_relation`.

The schema correctly rejected them, but the CLI surfaced a Python traceback instead of a
short user-facing error.

Repair:

- catch `AssessmentSchemaError` in `gaia research assess`;
- print the invalid field and allowed values without a traceback;
- keep schema validation strict.

### B2. Local `item_N` Grounding Confused LKM Variable Identity

The assessment builder renumbered landscape items into `item_0`, `item_1`, ... and
expected review citations to use those ids. The agent naturally cited stable LKM ids such
as `gcn_...`, causing errors like:

```text
item:gcn_... is not grounded in evidence_packet
```

Repair:

- keep `items[*].item_id` stable, preferring LKM variable id, paper id, or existing item
  id;
- add `display_index` for UI order;
- allow inline review refs such as `[variable:gcn_...]` and `[paper:<paper_id>]`;
- do not require agents to know generated row numbers.

### B3. Package Ref Payload Misleadingly Said `package_claim`

Explore materializes shallow search results into local Gaia source packages. Depending on
the LKM variable type, a source item can become:

- `claim(...)`;
- `question(...)`;
- `note(...)`.

The attached ref was named `source_package_ref` with `kind: package_claim`, even when the
referenced symbol was not a claim.

Repair:

- rename the field to `package_ref`;
- set `package_ref.kind` to `package_ref`;
- add `value_type: claim | question | note`;
- document that only `value_type == "claim"` refs may be used in `claim_refs`.

### B4. `candidate_relation(...)` Was Written With a Question Ref

The assessment analysis used a package ref that pointed to a generated
`question(...)`. `gaia research assess` wrote a `candidate_relation(...)` scaffold anyway,
and `gaia build check` later failed:

```text
candidate_relation() expected Claim ... got Question
```

Repair:

- before writing `candidate_relation(...)`, validate each `claim_refs` entry against
  visible evidence packet `package_ref` metadata when possible;
- skip or reject non-claim package refs before mutating package source;
- record skipped relation ids in the event payload;
- keep `gaia build check` as a final guardrail, not the first place the bug appears.

## Slow Points Observed

The trace did not yet have precise timings, but the slow path was visible:

- LKM search queries were run serially;
- source-writing commands often triggered package checks;
- `explore` materialized shallow source packages and local dependencies;
- analysis JSON was written and corrected manually rather than by a contract-aware runner.

Repair direction:

- add an E2E runner later that records command, wall time, stdout/stderr, package diff,
  inquiry diff, and trace-artifact diff;
- let the runner parallelize independent LKM searches;
- run `gaia build check` at explicit checkpoints and after source-writing actions.
- track the fast/batch author path in
  [#745](https://github.com/dptech-corp/Gaia/issues/745) so workflows can write
  multiple package statements and run one explicit check at the end.

## Gaia CLI Capability Gaps

Immediate CLI-layer gaps:

- `gaia research assess` should catch assessment schema errors;
- `gaia research assess` should preflight `claim_refs`;
- `gaia research assess` should support stable `--out` for assessment artifacts in
  a later slice;
- `gaia research report` should render stable inline refs such as `[variable:...]`,
  `[paper:...]`, and `[package_ref:...]`;
- trace/viewer tooling should expose `variable_id -> package_ref -> value_type` mapping;
- authoring should have a fast mode or batch mode for E2E/agent workflows that need many
  source writes without paying the default post-write validation cost each time
  ([#745](https://github.com/dptech-corp/Gaia/issues/745)).

These do not require Gaia language changes. The existing language behavior is correct:
`candidate_relation(...)` should accept claims or boolean-valued expressions, not
questions. This bug is a research CLI contract and validation problem.

## Workflow Mistakes

The workflow was also wrong in several places:

- assessment analysis was written without first constraining output by
  `gaia research contract assess`;
- relation `claim_refs` were assumed to be any package refs, but they must be
  claim-compatible package refs;
- review citations used local `item_N` ids, which are hard for agents to know;
- package validity was checked after a later step instead of immediately after `assess`.

## Success Criteria For This Repair

- assessment evidence packets use stable ids for `items[*].item_id`;
- review citations can use `[variable:gcn_...]` and render to numbered citations;
- source package refs include `value_type`;
- `claim_refs` pointing to a non-claim package ref are skipped before source mutation;
- `gaia build check` passes after a clean E2E `explore -> focus -> assess -> propose`
  package run;
- no Gaia language issue is opened unless implementation reveals a genuine need to
  extend language primitives.
