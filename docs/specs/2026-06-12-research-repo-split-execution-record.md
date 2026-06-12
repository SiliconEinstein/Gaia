# Research Repo Split Execution Record

> Status: active execution record.
>
> Date started: 2026-06-12
>
> Companion plan: [Research Repo Split Plan](2026-06-11-research-repo-split-plan.md)

## 1. Fixed Goal

Split Gaia's research module into a new git repository while preserving and
making first-class two usage modes:

1. **Review run mode**: product/skill-facing workflow that explores, assesses,
   and writes an evidence-backed report for tens to hundreds of papers within a
   short interactive window.
2. **Graph session mode**: agent-framework-facing workflow that can keep
   expanding a research graph to thousands or tens of thousands of nodes, with
   runtime proportional to the newly explored area, durable node/relation/focus
   records, and pause/resume support. A final report is optional.

The split must incorporate the current Gaia research PRs and issues, especially
PR #755, PR #763, the lessons from closed PR #726, and issues #745, #761, #762,
and #764.

## 2. Non-Negotiable Invariants

- Do not let "move PR #755 to another repo" replace the broader goal. The new
  repo must support both short review runs and long graph sessions.
- Do not create two parallel canonical research protocols. Lessons from the old
  `gaia-research-loop` task-envelope design may be absorbed, but the target
  on-disk contract should be unified under `.gaia/research/**`.
- Do not carry known correctness bugs across the repo split without either
  fixing them first or explicitly re-homing them with an owner and phase gate.
- Keep Gaia core as the language/package/build substrate. Research depends on
  Gaia core; Gaia core must not depend on research.
- Preserve package-native promotion discipline: research artifacts and graph
  session records are not automatically stable Gaia source.
- Long graph-session operations must be incremental. Normal continuation should
  process only new frontier/input batches, not recompute the whole graph each
  turn.

## 3. Evidence Sources To Recheck

| Source | Why it matters | Status |
| --- | --- | --- |
| PR #755 | Current package-native research implementation body | Checked 2026-06-12 |
| PR #763 | Existing split-plan PR | Checked 2026-06-12 |
| PR #726 | Closed agent task-envelope prototype | Checked 2026-06-12 |
| PR #757 | LKM onboarding / credentials readiness | Checked 2026-06-12 |
| PR #687 | Embedded package layout and projector constraints | Checked 2026-06-12 |
| PR #693 | Skill modularization pattern, formalization skill boundary | Checked 2026-06-12 |
| Issue #745 | Batch author mode for responsive research writes | Checked 2026-06-12 |
| Issue #761 | PR #755 follow-up robustness and refactor list | Checked 2026-06-12 |
| Issue #762 | New-user product readiness for research workflows | Checked 2026-06-12 |
| Issue #764 | Candidate relation sync correctness hole | Checked 2026-06-12 |

Recheck this table whenever more than one day has passed, a PR is updated, or
the implementation phase changes.

## 4. Verifier Cadence

Before each substantive step, run the relevant verifier block and append a row
to section 7.

### V1. Goal Verifier

- Does the step serve the new `gaia-research` repo split?
- Does it preserve both Review Run Mode and Graph Session Mode?
- Does it avoid prematurely optimizing only for final reports?
- Does it mention the relevant PR/issue constraints when they apply?

### V2. Architecture Verifier

- Is the boundary still `gaia-research -> gaia core`, never the reverse?
- Are SDK, CLI, provider, skill, and disk-contract responsibilities separated?
- Is `.gaia/research/**` the unified research artifact/session namespace?
- Are package promotion and formal Gaia source writes still explicit gates?

### V3. Long-Run Graph Verifier

- Is graph-session state append-only or otherwise resumable?
- Does continuation process only newly added frontier/input records?
- Are node, edge, focus, obligation, and evidence references durable?
- Can a run be paused, inspected, rebuilt from logs, and resumed?

### V4. Product/Skill Verifier

- Is there a short happy path for product or skill usage?
- Are credentials, provider config, profile choice, and doctor/readiness checks
  covered?
- Are intermediate state, events, trace, and final report paths observable to UI
  callers?

### V5. Migration/Issue Verifier

- Are #745, #761, #762, and #764 either closed by the current plan or assigned
  to a specific repo/phase?
- Are PR #755 and PR #763 assumptions still current?
- Are closed/experimental PR #726 lessons absorbed without reviving a competing
  canonical workflow?
- Are shared Gaia-core surfaces stable enough for downstream contract CI?

## 5. Drift Triggers

Stop and re-check the fixed goal if any of these happen:

- The design mentions report writing but not graph-session continuation.
- The implementation adds new `.gaia/research_loop/**` canonical state.
- The split plan relies on private CLI modules as stable cross-repo APIs.
- A correctness issue is deferred without a target repo, phase, or acceptance
  criterion.
- A proposed graph expansion step requires scanning all historical nodes during
  normal continuation.
- Product/skill usage requires long command recipes rather than profiles,
  config, SDK calls, or a doctor command.

## 6. Decision Log

| Date | Decision | Rationale | Verifier |
| --- | --- | --- | --- |
| 2026-06-12 | Treat PR #763 as the split-plan baseline, not the final design. | It covers the extraction boundary well, but needs explicit dual-mode kernel and graph-session contract. | V1, V3 |
| 2026-06-12 | Absorb PR #726 task-envelope lessons into `.gaia/research/**` rather than preserving `.gaia/research_loop/**`. | The task/candidate/gate pattern helps agent frameworks, but a second canonical namespace would split state and confuse migration. | V2, V3 |
| 2026-06-12 | Make `gaia-research` a single shared kernel with two first-class modes: review runs and graph sessions. | The product skill path and long-running agent-framework path share providers, refs, provenance, and promotion discipline, but need different orchestration defaults and disk records. | V1-V4 |
| 2026-06-12 | Add a completion acceptance checklist before implementation begins. | The split needs evidence-based gates for repository extraction, product review runs, graph-session incrementality, pause/resume, and issue closure rather than relying on implementation intent. | V1-V5 |
| 2026-06-12 | Add a phase-by-phase implementation plan only after the dual-mode contract and acceptance evidence were explicit. | Implementation work now has ordered gates for monorepo hardening, core public APIs, repo bootstrap, review run, graph session, doctor/readiness, CI, and core removal. | V1-V5 |

## 7. Checkpoint Log

| Time | Step | Verifier run | Result | Next action |
| --- | --- | --- | --- | --- |
| 2026-06-12 | Initial discovery over PRs, issues, and worktrees | V1, V2, V5 | Current split plan is viable but under-specifies long graph-session mode. | Amend split plan with dual-mode architecture and graph-session contract. |
| 2026-06-12 | Add execution record and drift-control loop | V1-V5 | Process guardrails are now explicit and should be updated before each major step. | Use this record before editing the companion split plan. |
| 2026-06-12 | Amend split plan with product goal, dual-mode architecture, unified disk contract, graph-session incremental contract, SDK shape, #762 release gate, and PR #726 absorption rule | V1-V5 | Split plan now states that moving PR #755 alone is insufficient; `.gaia/research/**` remains unified; graph sessions require frontier cursors and no normal full-history scan; #745/#761/#762/#764 all have phase gates. | Add acceptance checks/tests for graph-session contract and product doctor/readiness in the implementation plan. |
| 2026-06-12 | Add acceptance checklist for split completion evidence, review-run smoke tests, graph-session incremental tests, core API gates, and issue phase gates | V1-V5 | Completion now has requirement-by-requirement proof targets, including instrumented storage checks for graph-session continuation and doctor/readiness checks for product usage. | Use the checklist as the handoff for writing detailed implementation tasks or bootstrapping the new repo. |
| 2026-06-12 | Add implementation plan with phases 0-7 and concrete evidence commands | V1-V5 | Plan covers PR #755 hardening, #764/#761 fixes, #745 core authoring API, new repo bootstrap, SDK contracts, review-run mode, graph-session O(N) tests, #762 doctor/readiness, contract CI, and Gaia core removal. | Use the implementation plan to execute Phase 0 in a clean worktree or delegate phase tasks to subagents with verifier checkpoints. |
| 2026-06-12 | Execute Phase 0 slice for #764 on branch `codex/research-actions-pkg-contract`; pushed commit `55046adb` (`fix(research): surface relation sync skips`). | V1, V5 | Explicit non-claim `claim_refs` are rejected during assessment validation, inferred non-claim package refs produce visible sync skip reasons, and CLI sync summaries now surface `candidate_relations_skipped`. Verified with `uv run pytest tests/gaia/test_research_assessment.py -q`, `uv run pytest tests/cli/test_research.py -q -k candidate_relation`, targeted `ruff`, targeted `mypy`, and `git diff --check`. This is a #764 hardening slice, not split completion. | Continue Phase 0 with the remaining #761/#764 gates, then move to Phase 1 public core APIs only after the verifier table still passes. |
| 2026-06-12 | Execute second Phase 0 slice for #764 on branch `codex/research-actions-pkg-contract`; pushed commit `177a8755` (`fix(research): reject unparseable sync writes`). | V1, V5 | Research sync now parse-checks `authored/__init__.py` after source writes, restores the prior authored source on parse failure, exposes `ResearchSyncSourceError`, and has CLI exit-2 handling without traceback. Verified with `uv run pytest tests/gaia/test_research_artifacts.py tests/gaia/test_research_assessment.py -q`, `uv run pytest tests/cli/test_research.py -q -k "candidate_relation or unparseable_sync_source or schema_errors"`, targeted `ruff`, targeted `mypy`, and `git diff --check`. This closes another #764 correctness hole while leaving broader repo split work open. | Re-run PR #755 CI/review state, then continue Phase 0 #761 items or move only the completed #764 slice forward for review. |
| 2026-06-12 | Execute Phase 0 slice for #761 on branch `codex/research-actions-pkg-contract`; pushed commit `4cd5b21f` (`refactor(research): share assessment review rendering`). | V1, V5 | Sync no longer carries a separate review-to-markdown renderer. Package-authored assessment review notes now use the report renderer path, cover abstract, key points, summary, sections, evidence table, limitations, and next queries, and strip reader-facing unresolved internal refs. Verified with `uv run pytest tests/gaia/test_research_artifacts.py tests/gaia/test_research_report.py -q`, `uv run pytest tests/cli/test_research.py -q -k "accepts_analysis_json_with_review or unparseable_sync_source or candidate_relation"`, targeted `ruff`, targeted `mypy`, and `git diff --check`. This addresses the #761 rendering-consolidation slice only. | Check PR #755 CI/review threads, then decide whether to continue remaining #761 robustness items or split remaining follow-ups into smaller PRs. |
| 2026-06-12 | Execute Phase 0 slice for #761 explicit config override handling on branch `codex/research-actions-pkg-contract`; pushed commit `e9db83d9` (`fix(research): preserve explicit default run overrides`). | V1, V4, V5 | `gaia research run` legacy override flags now use `None` sentinels so explicitly supplied default-valued flags such as `--search-index bohrium`, `--search-limit 20`, and `--reasoning-only` can override config/profile values. Verified with a red-green CLI regression plus `uv run pytest tests/gaia/test_research_run_config.py -q`, `uv run pytest tests/cli/test_research.py -q`, targeted `ruff`, targeted `mypy`, and `git diff --check`. This improves product/skill profile ergonomics but does not complete the repo split. | Continue remaining #761 Phase 0 gates: checkpoint/resume semantics, provider/search failure observability, retry/error contracts, and engine-service extraction boundaries. |
| 2026-06-12 | Execute Phase 0 slice for #761 checkpoint multi-focus semantics on branch `codex/research-actions-pkg-contract`; pushed commit `1954329e` (`fix(research): reject checkpoint multi-focus runs`). | V1, V4, V5 | `gaia research run` now rejects `analysis_provider=checkpoint` with `focus_count > 1` before creating a run, avoiding ambiguous checkpoint/resume state for multiple assessment focuses. Verified red-green with `tests/cli/test_research.py::test_research_run_rejects_checkpoint_provider_multi_focus`, then `uv run pytest tests/cli/test_research.py -q`, `uv run pytest tests/gaia/test_research_run_config.py -q`, targeted `ruff`, targeted `mypy`, and `git diff --check`. This chooses the explicit-rejection branch of the #761 checkpoint/resume acceptance option. | Continue Phase 0 with provider/search failure observability and engine-service extraction boundaries, or re-home lower-risk #761 items before Phase 1. |
