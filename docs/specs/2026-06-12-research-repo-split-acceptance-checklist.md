# Research Repo Split Acceptance Checklist

> Status: active acceptance checklist.
>
> Date started: 2026-06-12
>
> Companion specs:
> [Research Repo Split Plan](2026-06-11-research-repo-split-plan.md) and
> [Research Repo Split Execution Record](2026-06-12-research-repo-split-execution-record.md).
> Implementation plan:
> [Research Repo Split Implementation Plan](../superpowers/plans/2026-06-12-research-repo-split-implementation.md).

This checklist defines the evidence required before the research split can be
called complete. It is intentionally stricter than "the code moved": every item
must be proven by files, tests, commands, PR/issue state, or runtime artifacts.

## 1. Completion Requirements

| ID | Requirement | Required evidence |
| --- | --- | --- |
| A1 | A new `gaia-research` git repository exists and contains the migrated research implementation. | Repository URL, commit hash, `pyproject.toml` with `name = "gaia-research"`, and preserved history or documented import commit. |
| A2 | Gaia core no longer owns research implementation code after the removal phase. | Core release branch lacks `gaia/engine/research/**`, `gaia/cli/commands/research*.py`, and bundled research skill code; `gaia research` resolves via plugin or prints an install hint. |
| A3 | Dependency direction is one-way: `gaia-research -> gaia core`. | Import check in both repos proves Gaia core does not import `gaia_research`; contract CI installs `gaia-research` as a downstream package. |
| A4 | Review run mode supports product/skill use for evidence-backed reports. | SDK/CLI/skill smoke test creates a package-local run, performs mocked explore/assessment/report phases, and emits observable state/events/report paths. |
| A5 | Graph session mode supports resumable long-running expansion without requiring a final report. | SDK/CLI smoke test opens a session, submits multiple frontier batches, writes nodes/edges/focus/field-map records, pauses, resumes, and continues without report generation. |
| A6 | Normal graph-session continuation is incremental. | Performance/complexity regression test proves continuation reads the new frontier/input batch and cursor/index files, not all historical node/edge records. |
| A7 | `.gaia/research/**` is the only canonical research namespace. | Tests assert review runs and graph sessions write under `.gaia/research/**`; docs and code do not create canonical `.gaia/research_loop/**` state. |
| A8 | Research artifacts and graph-session records are not automatically stable Gaia source. | Promotion tests show source writes require explicit sync/promotion calls; default run/session steps leave `src/<pkg>/` unchanged unless a sync gate is requested. |
| A9 | #745, #761, #762, and #764 are closed or re-homed with release-blocking owners. | Issue tracker links from release checklist; phase gates in PR descriptions; no open silent-skip or batch-author correctness gap remains unowned. |
| A10 | New-user readiness is first-class. | `gaia-research doctor` / `gaia research doctor` tests cover missing credentials, missing provider config, invalid package shape, profile resolution, and output paths without leaking secrets. |

## 2. Review Run Mode Acceptance

Review run mode is accepted only when all of these pass:

| Check | Evidence command or artifact | Failure condition |
| --- | --- | --- |
| Run envelope | `tests/review/test_run_state_contract.py::test_review_run_writes_state_events_and_report_paths` | Missing `schema_version`, missing `run.failed` failure path, or state cannot be read through SDK. |
| Skill path | `tests/skills/test_research_skill.py::test_skill_invokes_short_review_profile` | Skill requires long flag recipes, writes secrets, or bypasses SDK. |
| Product SDK path | `tests/sdk/test_review_client.py::test_run_review_returns_observable_handles` | Product caller must parse CLI text to find run id, events, checkpoints, or report path. |
| Report grounding | `tests/review/test_report_grounding.py::test_report_citations_do_not_leak_internal_refs` | Reader-facing report contains unresolved internal refs such as `[variable:...]` or duplicate unresolved citations shadow resolved metadata. |
| Failure observability | `tests/review/test_failure_state.py::test_provider_failure_marks_run_failed` | Any normal provider/search/sync failure leaves `state.json` as `running`. |

Minimum live-readiness evidence for the first release:

```text
gaia-research doctor <pkg>
gaia-research run-review <pkg> --topic "<topic>" --profile quick
gaia-research status <pkg> --run-id <run-id>
```

The release checklist must include one mocked CI run and one manually recorded
live or staging run. The live/staging record may use a small topic, but it must
exercise real provider/search configuration and produce a final report path.

## 3. Graph Session Mode Acceptance

Graph session mode is accepted only when all of these pass:

| Check | Evidence command or artifact | Failure condition |
| --- | --- | --- |
| Session envelope | `tests/session/test_session_state_contract.py::test_open_session_writes_state_and_schema_version` | Session has no `schema_version`, state cannot be rebuilt, or records are not under `.gaia/research/sessions/<id>/`. |
| Frontier append | `tests/session/test_frontier_append.py::test_submit_frontier_batch_appends_nodes_edges_and_cursor` | Submitting a new batch rewrites the whole node/edge log or loses cursor position. |
| Pause/resume | `tests/session/test_pause_resume.py::test_resume_continues_from_saved_cursor` | Resume reprocesses already accepted frontier records or requires a final report artifact. |
| Field map delta | `tests/session/test_field_map_delta.py::test_field_map_updates_from_delta_records` | Normal continuation scans all historical nodes/edges to update the field map. |
| Task contract | `tests/session/test_task_contract.py::test_candidate_validation_produces_repair_context` | Invalid candidate advances the session, lacks repair context, or creates a second protocol namespace. |
| Promotion boundary | `tests/session/test_promotion_boundary.py::test_session_records_do_not_write_gaia_source_by_default` | Opening or continuing a session writes stable `claim(...)`, `derive(...)`, or `contradict(...)` without explicit promotion. |

The key complexity check must use an instrumented storage adapter. It should
seed a session with a large historical log, then submit a small frontier batch
and assert that normal continuation reads only:

```text
state.json
frontier cursor / index files
the new frontier/input batch
the necessary delta index files
```

It must fail if continuation opens every historical node/edge record in
`nodes.jsonl` or `edges.jsonl`. Full rebuild commands may scan history, but
they must be named and tested separately.

## 4. Core Repo Acceptance

Gaia core is accepted only when these contracts are stable:

| Surface | Required evidence |
| --- | --- |
| Public LKM client | `gaia/lkm/client.py` or equivalent public module, typed transport/permission/not-found errors, CLI translates errors without leaking exit-code semantics into research engine. |
| Public authoring API | `gaia/engine/authoring/` or equivalent public module, batch write mode for #745, final validation gate, and no swallowed `SyntaxError`. |
| Public materialization API | `gaia/engine/materialize.py` or equivalent public module, chain package naming includes a content digest to avoid PR #755 finding-4 collisions. |
| Public inquiry state | Docs and tests declare the subset of `gaia.engine.inquiry.state` that `gaia-research` may consume. |
| CLI plugin mechanism | `gaia.cli_plugins` entry point group, installed `gaia-research` registers `gaia research`; absent plugin produces a clear install hint. |
| Skill plugin mechanism | Installed distributions can expose `gaia.skills` or equivalent metadata; research skill is no longer hardcoded in Gaia core. |

Core removal is not accepted until contract CI proves:

```text
install gaia core from the candidate branch
install gaia-research from its compatible branch
run gaia-research contract smoke tests
run gaia research --help through the plugin path
```

## 5. Issue and PR Gates

| Gate | Required issue state before advancing |
| --- | --- |
| Phase 0 to Phase 1 | PR #755 landed or superseded; #761 high-risk follow-ups either fixed or listed in gaia-research tracker with owners. |
| Phase 1 to Phase 2 | #745 public batch author mode exists; #764 relation skip/validation/compile gate is closed; materialization collision fix is present. |
| Phase 2 to Phase 3 | New repo bootstrapped; PR #726 lessons imported as historical/spec input only; no canonical `.gaia/research_loop/**` writes. |
| Phase 3 release | #762 doctor/profile/readiness acceptance checks pass; graph-session contract tests pass; review-run smoke tests pass. |
| Phase 4 removal | Gaia core has downstream contract CI; open research-side issues are transferred or closed with forwarding links. |

If any issue remains open past its phase gate, the release checklist must name
the new owner repo, blocking label, and exact acceptance test that will close it.

## 6. Drift Audit Before Completion

Before marking the split goal complete, run this audit against current state:

1. Inspect both repositories' file trees and confirm the stay/move boundary from
   the split plan.
2. Inspect `pyproject.toml` and package metadata in both repositories.
3. Run core contract CI or the local equivalent.
4. Run gaia-research unit, contract, SDK, CLI, and skill smoke tests.
5. Run the graph-session incremental continuation test with an instrumented
   storage adapter.
6. Run or inspect one product-style review run that produces a report.
7. Inspect GitHub issue state for #745, #761, #762, and #764.
8. Inspect docs for accidental canonical `.gaia/research_loop/**` state.
9. Confirm no completion claim relies only on intent, partial migration, or
   narrow tests that do not cover the original objective.

The goal is complete only if every requirement in section 1 is proven by the
current-state evidence above.
