# Research Module Split Acceptance

> **Status:** Canonical acceptance boundary for the `gaia-research` split.
>
> **Date:** 2026-06-13
>
> **Current implementation focus:** report workflow parity migration. Large
> graph-session expansion is explicitly future work.
>
> **Supersedes as canonical target:**
> [Research Actions Package-Native Overview](2026-06-01-research-actions-package-native-overview.md),
> [Research Actions Implementation Roadmap](2026-06-01-research-actions-implementation-roadmap.md),
> and [Research Actions Migration Notes](2026-06-01-research-actions-migration-notes.md).

## 1. Correction

The first `gaia-research` milestone split out a review/report runner, a package
local `.gaia/research/runs/**` envelope, and the Gaia CLI plugin handoff. That
milestone is useful, but it is not the completed research module split.

The completed split means Gaia core stops owning the upper research workflow.
`gaia-research` owns the workflow that starts from a research topic and drives
the current report path through landscape, field-map, focus, assessment,
materialization decisions, and report generation.

## 2. Ownership Boundary

Gaia core owns primitives:

- `gaia search lkm` and the LKM client/auth/docs substrate;
- `gaia add`;
- `gaia inquiry`;
- `gaia author`;
- package scaffolding, materialization, build, check, infer, and render;
- public Python surfaces needed by downstream workflow packages.

`gaia-research` owns research workflows:

- the replacement for `gaia research ...` upper-level workflow commands;
- the replacement for `gaia-lkm-explore ...`;
- topic-driven report workflows;
- landscape, field map, focus selection, assessment artifacts,
  materialization/promotion policy, and report orchestration;
- session state and agent-facing JSON artifacts under `.gaia/research/**`.

`gaia search lkm` is not part of the upper workflow split. It remains a Gaia
core primitive that `gaia-research` can call through a public interface.

## 3. Current Iteration Scope

This iteration focuses on moving the existing Gaia report workflow behavior into
`gaia-research` with parity. It must not expand into the future graph-session
work.

In scope:

- deprecate Gaia-core upper research workflow CLIs after replacements exist;
- deprecate `gaia-lkm-explore` as a product workflow surface;
- port or wrap the existing deterministic `gaia.lkm_explorer` workflow pieces
  needed for current report generation;
- expose a `gaia-research` engine API and CLI for report workflows;
- make `gaia research report ...` the user-facing command name;
- keep compatibility aliases only when needed for migration;
- verify parity against current Gaia report workflow behavior.

Out of scope for this iteration:

- thousands or tens of thousands of node graph sessions;
- O(N) large-scale expansion optimization;
- long-running graph-session memory beyond what current report parity needs;
- deep/broad continuous expansion policies;
- LKM writeback or public registry publication.

## 4. Report Workflow Contract

The current parity target is:

```text
topic
  -> landscape
  -> field map
  -> focus selection
  -> assess/report-ready artifact
  -> materialization decision
  -> report
```

The workflow may use Gaia core primitives, but the orchestration belongs in
`gaia-research`. The CLI must be a thin adapter over engine calls, not the place
where workflow state and transitions live.

The first-class engine API should be shaped around durable workflow state:

```python
run_report_workflow(topic, workspace, policy)
resume_report_workflow(run_id, workspace)
```

The exact Python names may change during implementation, but the boundary must
not: product CLIs, Gaia plugin handoff, and external agent skills should all call
the same engine workflow.

## 5. Artifact Boundary

`gaia-research` writes agent-facing workflow artifacts under:

```text
<package-or-workspace>/.gaia/research/
  runs/<run-id>/
  landscape/
  field_map/
  focuses/
  assessments/
  materialization/
  reports/
```

The exact layout can be refined by implementation, but the semantic rule is
fixed:

- raw search hits and paper leads remain research artifacts;
- candidate nodes and candidate relations remain research artifacts;
- obligations live in Gaia inquiry state when accepted as process work;
- stable truth-bearing content only enters Gaia source through an explicit
  materialization or promotion step;
- report output must cite the artifacts and Gaia package state it used.

## 6. Deprecation Acceptance

Gaia core is acceptable only when the upper workflow surfaces tell users and
agents to use `gaia-research`:

- `gaia-lkm-explore --help` is deprecated or removed after parity replacement;
- old Gaia-core `gaia research` workflow commands are deprecated or handed off
  to the installed `gaia-research` plugin;
- Gaia docs no longer present `gaia-lkm-explore` as the canonical research
  workflow;
- CI verifies the replacement through `gaia-research`, not through a hidden
  Gaia-core implementation path.

## 7. Parity Acceptance

This iteration is complete when the current report workflow can be run from
`gaia-research` and produces equivalent user-visible artifacts to the Gaia-core
workflow it replaces.

Required evidence:

- a topic-driven report command in `gaia-research`;
- engine-level tests for each deterministic transition;
- CLI tests for standalone `gaia-research report`;
- Gaia plugin tests for `gaia research report`;
- migration/deprecation tests in Gaia core;
- cross-repo smoke that installs Gaia core plus `gaia-research` and runs the
  report workflow;
- docs that describe `gaia-research` as the report workflow owner and Gaia core
  as primitive owner.

The bridge milestone remains useful evidence, but it is not sufficient evidence
for this acceptance target.
