# Research Report Workflow Parity Migration Plan

> **Status:** Current implementation plan for the next `gaia-research` split
> milestone.
>
> **Parent spec:**
> [Research Module Split Acceptance](../specs/2026-06-13-research-module-split-acceptance.md)
>
> **Scope:** Move the existing Gaia upper report workflow into `gaia-research`
> with parity. Do not implement graph-session expansion in this plan.

## 1. Goal

Make `gaia-research` own the current topic-to-report workflow that previously
lived across Gaia-core research and `gaia-lkm-explore` surfaces.

The target user flow is:

```bash
gaia research report \
  --topic "aspirin primary prevention cardiovascular disease" \
  --workspace ./runs/aspirin-fast-report \
  --profile fast \
  --json
```

The standalone equivalent is:

```bash
gaia-research report \
  --topic "aspirin primary prevention cardiovascular disease" \
  --workspace ./runs/aspirin-fast-report \
  --profile fast \
  --json
```

## 2. Non-Goals

This plan does not implement:

- large graph-session expansion;
- O(N) graph-session performance guarantees;
- indefinite pause/resume research memory;
- new deep/broad expansion strategies;
- LKM writeback;
- public registry publication.

It may preserve artifact hooks for those later capabilities, but they are not
acceptance criteria for this milestone.

## 3. Work Packages

### M0. Documentation Correction

Deliverables:

- add the canonical split acceptance spec;
- add this parity migration plan;
- mark older research-action and LKM-explore specs as historical/prior art;
- update `gaia-research` README and execution record so the bridge milestone is
  not described as completed research-module split.

Verification:

- no document still claims the review/report runner bridge is the completed
  research split;
- the current scope says report workflow parity only;
- graph-session expansion is marked future work.

### M0b. Documentation Ownership Migration

Deliverables:

- create `gaia-research/docs/foundations/` as the durable workflow design home;
- record in `gaia-research/README.md` or `gaia-research/AGENTS.md` that
  foundations docs must be updated in the same PR as code changes that alter
  workflow semantics, artifact schemas, CLI behavior, or engine boundaries;
- inventory Gaia-core research docs that should move or be rewritten into
  `gaia-research/docs/foundations/`;
- leave Gaia-core copies as historical pointers or deprecation/migration
  documents only;
- do not copy old Gaia docs verbatim into `gaia-research`; rewrite them against
  the current ownership boundary.

Verification:

- `gaia-research/docs/foundations/README.md` exists;
- `gaia-research/README.md` or `gaia-research/AGENTS.md` documents the update
  rule;
- Gaia-core specs point to the canonical split acceptance spec and do not claim
  ownership of current workflow design;
- future implementation plans treat documentation migration as part of report
  workflow parity, not as cleanup after the fact.

### M1. Gaia-Core Deprecation Inventory

Deliverables:

- inventory all Gaia-core upper workflow entry points:
  - `gaia research ...`;
  - `gaia-lkm-explore ...`;
  - docs that describe `gaia-lkm-explore` as canonical;
- classify each command as `handoff`, `deprecated alias`, or `remove after
  parity`.

Verification:

- test coverage lists every CLI surface that must change;
- `gaia search lkm` is explicitly excluded from deprecation because it is a
  primitive.

### M2. Port Report Workflow Engine Surface

Deliverables:

- create `gaia-research` engine modules for report workflow state and
  transitions;
- port the deterministic utilities needed from `gaia.lkm_explorer`:
  - landscape aggregation;
  - paper lead deduplication;
  - focus candidate extraction;
  - artifact provenance normalization;
- keep Gaia core imports behind declared public surfaces or subprocess
  adapters.

Verification:

- unit tests cover each deterministic transition;
- source-boundary tests still prove Gaia core does not import
  `gaia_research`;
- migrated artifacts write under `.gaia/research/**`, not
  `.gaia/exploration/**`.

### M3. Implement Topic-Driven Report Workflow

Deliverables:

- implement an engine function that starts from a topic and workspace;
- create or validate the working Gaia package/workspace;
- call Gaia LKM search as a primitive;
- produce landscape, field-map, focus, assessment, materialization-decision, and
  report artifacts;
- reuse the existing report rendering path where parity requires it.

Verification:

- a fixture topic produces all expected artifacts;
- the report cites the landscape/focus/assessment artifacts used;
- no stable Gaia source is written without an explicit materialization decision.

### M4. Rename User Command To `report`

Deliverables:

- add `gaia-research report`;
- add `gaia research report` through plugin handoff;
- keep `review` only as a deprecated compatibility alias if needed;
- update human-readable output to say `report completed`, not `review run
  completed`.

Verification:

- standalone CLI tests call `report`;
- Gaia plugin tests call `gaia research report`;
- compatibility tests cover the alias only if it is retained;
- README examples use `report`.

### M5. Deprecate Gaia-Core Upper Workflow Surfaces

Deliverables:

- mark `gaia-lkm-explore` deprecated after `gaia-research report` covers the
  parity workflow;
- ensure Gaia-core `gaia research` hands off to `gaia-research` for report;
- update Gaia docs to point users to `gaia-research`.

Verification:

- CLI help text points to `gaia-research`;
- tests prove `gaia search lkm` still works as a core primitive;
- tests prove upper workflow commands do not silently keep running Gaia-core
  implementations.

### M6. Cross-Repo Parity Audit

Deliverables:

- add a repeatable audit script that installs Gaia core and `gaia-research`;
- run a topic-driven report workflow through the Gaia plugin command;
- compare expected artifact presence and status with the legacy workflow.

Verification:

- CI runs the audit;
- audit output includes run id, status, artifact paths, report path, and event
  count;
- failure to find the `gaia-research` handoff fails hard.

## 4. Completion Criteria

The milestone is complete when:

- `gaia-research report --topic ...` works from a clean install;
- `gaia research report --topic ...` works through Gaia plugin handoff;
- Gaia-core upper workflow surfaces are deprecated or handed off;
- `gaia-lkm-explore` is no longer documented as canonical;
- cross-repo CI proves the report workflow from topic to report;
- documentation separates this parity milestone from future graph-session work.
