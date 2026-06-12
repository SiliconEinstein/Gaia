# Research Repo Split Execution Record

> Status: active execution record.
>
> Date started: 2026-06-12
>
> Companion plan: [Research Repo Split Plan](2026-06-11-research-repo-split-plan.md)

## 1. Fixed Goal

**Current goal: Goal A.** Split Gaia's research module into a new git
repository and keep it connected to Gaia through public core APIs, plugin entry
points, contract CI, and migrated review-run parity.

Goal A includes:

1. A standalone `gaia-research` repository with migrated implementation,
   tests, docs, package metadata, and skill assets.
2. Public Gaia core surfaces needed by research, with dependency direction
   `gaia-research -> gaia core`.
3. `gaia research` connected back through plugin entry points when
   `gaia-research` is installed.
4. Review-run parity for the current package-native evidence-report workflow.
5. Clear `.gaia/research/**` namespace ownership.

Large-scale graph-session execution is a follow-up capability tracked in
[#767](https://github.com/SiliconEinstein/Gaia/issues/767). It must not block
Goal A. Goal A should only preserve extension points and avoid conflicting
protocol choices.

The split must incorporate the current Gaia research PRs and issues, especially
PR #755, PR #763, the lessons from closed PR #726, and issues #745, #761, #762,
and #764. Issue #767 is the graph-session follow-up handoff.

## 2. Non-Negotiable Invariants

- Do not let "move PR #755 to another repo" replace Goal A. The new repo must
  be a connected, tested downstream package, not a code dump.
- Do not create two parallel canonical research protocols. Lessons from the old
  `gaia-research-loop` task-envelope design may be absorbed, but the target
  on-disk contract should be unified under `.gaia/research/**`.
- Do not carry known correctness bugs across the repo split without either
  fixing them first or explicitly re-homing them with an owner and phase gate.
- Keep Gaia core as the language/package/build substrate. Research depends on
  Gaia core; Gaia core must not depend on research.
- Preserve package-native promotion discipline: research artifacts and graph
  session records are not automatically stable Gaia source.
- Do not implement or partially specify `.gaia/research/sessions/**` inside
  Goal A unless that work explicitly moves into the #767 follow-up scope.

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
| Issue #767 | Large-scale graph-session design follow-up | Created 2026-06-12 |

Recheck this table whenever more than one day has passed, a PR is updated, or
the implementation phase changes.

## 4. Verifier Cadence

Before each substantive step, run the relevant verifier block and append a row
to section 7.

### V1. Goal Verifier

- Does the step serve the new `gaia-research` repo split?
- Does it preserve review-run parity and Gaia connection?
- Does it avoid pulling #767 graph-session implementation back into Goal A?
- Does it mention the relevant PR/issue constraints when they apply?

### V2. Architecture Verifier

- Is the boundary still `gaia-research -> gaia core`, never the reverse?
- Are SDK, CLI, provider, skill, and disk-contract responsibilities separated?
- Is `.gaia/research/**` the unified research artifact/session namespace?
- Are package promotion and formal Gaia source writes still explicit gates?

### V3. Graph Follow-up Boundary Verifier

- Is large-scale graph-session work linked to #767 when mentioned?
- Does Goal A avoid creating canonical `.gaia/research_loop/**` state?
- Does Goal A reserve, but not prematurely define, `.gaia/research/sessions/**`?
- Does the split preserve public extension points needed by future sessions?

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

- The design expands from repo split/review-run parity into implementing
  graph-session mechanics without explicitly moving into #767.
- The implementation adds new `.gaia/research_loop/**` canonical state.
- The split plan relies on private CLI modules as stable cross-repo APIs.
- A correctness issue is deferred without a target repo, phase, or acceptance
  criterion.
- Product/skill usage requires long command recipes rather than profiles,
  config, SDK calls, or a doctor command.

## 6. Decision Log

Rows before the 2026-06-12 Goal A narrowing are historical context. The active
goal and phase map are the Goal A definitions in sections 1-5; graph-session
execution is re-homed to #767.

| Date | Decision | Rationale | Verifier |
| --- | --- | --- | --- |
| 2026-06-12 | Treat PR #763 as the split-plan baseline, not the final design. | It covers the extraction boundary well, but needs explicit dual-mode kernel and graph-session contract. | V1, V3 |
| 2026-06-12 | Absorb PR #726 task-envelope lessons into `.gaia/research/**` rather than preserving `.gaia/research_loop/**`. | The task/candidate/gate pattern helps agent frameworks, but a second canonical namespace would split state and confuse migration. | V2, V3 |
| 2026-06-12 | Make `gaia-research` a single shared kernel with two first-class modes: review runs and graph sessions. | The product skill path and long-running agent-framework path share providers, refs, provenance, and promotion discipline, but need different orchestration defaults and disk records. | V1-V4 |
| 2026-06-12 | Add a completion acceptance checklist before implementation begins. | The split needs evidence-based gates for repository extraction, product review runs, graph-session incrementality, pause/resume, and issue closure rather than relying on implementation intent. | V1-V5 |
| 2026-06-12 | Add a phase-by-phase implementation plan only after the dual-mode contract and acceptance evidence were explicit. | This was the pre-Goal-A-narrowing phase map; it has since been superseded by the Goal A 0-6 map and #767 graph-session follow-up. | V1-V5 |
| 2026-06-12 | Narrow the active goal to Goal A and re-home large-scale graph sessions to #767. | Repo extraction/connection and graph-session scalability are both large goals. Keeping graph execution inside split acceptance would make PR scope and completion evidence drift. | V1, V3 |

## 7. Checkpoint Log

| Time | Step | Verifier run | Result | Next action |
| --- | --- | --- | --- | --- |
| 2026-06-12 | Initial discovery over PRs, issues, and worktrees | V1, V2, V5 | Current split plan is viable but under-specifies long graph-session mode. | Amend split plan with dual-mode architecture and graph-session contract. |
| 2026-06-12 | Add execution record and drift-control loop | V1-V5 | Process guardrails are now explicit and should be updated before each major step. | Use this record before editing the companion split plan. |
| 2026-06-12 | Amend split plan with product goal, dual-mode architecture, unified disk contract, graph-session incremental contract, SDK shape, #762 release gate, and PR #726 absorption rule | V1-V5 | Split plan now states that moving PR #755 alone is insufficient; `.gaia/research/**` remains unified; graph sessions require frontier cursors and no normal full-history scan; #745/#761/#762/#764 all have phase gates. | Add acceptance checks/tests for graph-session contract and product doctor/readiness in the implementation plan. |
| 2026-06-12 | Add acceptance checklist for split completion evidence, review-run smoke tests, graph-session incremental tests, core API gates, and issue phase gates | V1-V5 | This was the pre-Goal-A-narrowing checklist; graph-session incremental tests are now re-homed to #767. | Use the Goal A checklist as the handoff for writing detailed implementation tasks or bootstrapping the new repo. |
| 2026-06-12 | Add implementation plan with phases 0-7 and concrete evidence commands | V1-V5 | This was the pre-Goal-A-narrowing implementation plan; it is now superseded by the Goal A 0-6 plan. | Use the Goal A implementation plan to continue from public core surfaces, skill plugin discovery, repo bootstrap, and review-run parity gates. |
| 2026-06-12 | Execute Phase 0 slice for #764 on branch `codex/research-actions-pkg-contract`; pushed commit `55046adb` (`fix(research): surface relation sync skips`). | V1, V5 | Explicit non-claim `claim_refs` are rejected during assessment validation, inferred non-claim package refs produce visible sync skip reasons, and CLI sync summaries now surface `candidate_relations_skipped`. Verified with `uv run pytest tests/gaia/test_research_assessment.py -q`, `uv run pytest tests/cli/test_research.py -q -k candidate_relation`, targeted `ruff`, targeted `mypy`, and `git diff --check`. This is a #764 hardening slice, not split completion. | Continue Phase 0 with the remaining #761/#764 gates, then move to Phase 1 public core APIs only after the verifier table still passes. |
| 2026-06-12 | Execute second Phase 0 slice for #764 on branch `codex/research-actions-pkg-contract`; pushed commit `177a8755` (`fix(research): reject unparseable sync writes`). | V1, V5 | Research sync now parse-checks `authored/__init__.py` after source writes, restores the prior authored source on parse failure, exposes `ResearchSyncSourceError`, and has CLI exit-2 handling without traceback. Verified with `uv run pytest tests/gaia/test_research_artifacts.py tests/gaia/test_research_assessment.py -q`, `uv run pytest tests/cli/test_research.py -q -k "candidate_relation or unparseable_sync_source or schema_errors"`, targeted `ruff`, targeted `mypy`, and `git diff --check`. This closes another #764 correctness hole while leaving broader repo split work open. | Re-run PR #755 CI/review state, then continue Phase 0 #761 items or move only the completed #764 slice forward for review. |
| 2026-06-12 | Execute Phase 0 slice for #761 on branch `codex/research-actions-pkg-contract`; pushed commit `4cd5b21f` (`refactor(research): share assessment review rendering`). | V1, V5 | Sync no longer carries a separate review-to-markdown renderer. Package-authored assessment review notes now use the report renderer path, cover abstract, key points, summary, sections, evidence table, limitations, and next queries, and strip reader-facing unresolved internal refs. Verified with `uv run pytest tests/gaia/test_research_artifacts.py tests/gaia/test_research_report.py -q`, `uv run pytest tests/cli/test_research.py -q -k "accepts_analysis_json_with_review or unparseable_sync_source or candidate_relation"`, targeted `ruff`, targeted `mypy`, and `git diff --check`. This addresses the #761 rendering-consolidation slice only. | Check PR #755 CI/review threads, then decide whether to continue remaining #761 robustness items or split remaining follow-ups into smaller PRs. |
| 2026-06-12 | Execute Phase 0 slice for #761 explicit config override handling on branch `codex/research-actions-pkg-contract`; pushed commit `e9db83d9` (`fix(research): preserve explicit default run overrides`). | V1, V4, V5 | `gaia research run` legacy override flags now use `None` sentinels so explicitly supplied default-valued flags such as `--search-index bohrium`, `--search-limit 20`, and `--reasoning-only` can override config/profile values. Verified with a red-green CLI regression plus `uv run pytest tests/gaia/test_research_run_config.py -q`, `uv run pytest tests/cli/test_research.py -q`, targeted `ruff`, targeted `mypy`, and `git diff --check`. This improves product/skill profile ergonomics but does not complete the repo split. | Continue remaining #761 Phase 0 gates: checkpoint/resume semantics, provider/search failure observability, retry/error contracts, and engine-service extraction boundaries. |
| 2026-06-12 | Execute Phase 0 slice for #761 checkpoint multi-focus semantics on branch `codex/research-actions-pkg-contract`; pushed commit `1954329e` (`fix(research): reject checkpoint multi-focus runs`). | V1, V4, V5 | `gaia research run` now rejects `analysis_provider=checkpoint` with `focus_count > 1` before creating a run, avoiding ambiguous checkpoint/resume state for multiple assessment focuses. Verified red-green with `tests/cli/test_research.py::test_research_run_rejects_checkpoint_provider_multi_focus`, then `uv run pytest tests/cli/test_research.py -q`, `uv run pytest tests/gaia/test_research_run_config.py -q`, targeted `ruff`, targeted `mypy`, and `git diff --check`. This chooses the explicit-rejection branch of the #761 checkpoint/resume acceptance option. | Continue Phase 0 with provider/search failure observability and engine-service extraction boundaries, or re-home lower-risk #761 items before Phase 1. |
| 2026-06-12 | Execute Phase 0 slice for #761 failed live-search observability on branch `codex/research-actions-pkg-contract`; pushed commit `0d2a095a` (`fix(research): trace failed live searches`). | V1, V4, V5 | Live LKM search failures now write a failed `search.lkm.<prefix>` trace record with query, index, limit, reasoning flag, error type, and error message before marking the run failed. Benchmark summary rebuilds can include that failed search step. Verified red-green with `tests/cli/test_research.py::test_research_run_records_failed_live_search_trace`, then `uv run pytest tests/cli/test_research.py -q` (59 passed), targeted `ruff`, targeted `mypy`, and `git diff --check`. This improves product/skill failure observability but does not complete orchestration extraction. | Continue remaining #761 items: retry/error contracts, materialization/provider typed errors, report failure/concurrency cleanup, and engine-service extraction boundaries. |
| 2026-06-12 | Follow up on PR #755 remote CI failure after failed live-search trace slice; pushed commit `699a355f` (`test(research): align fake runtime trace signature`). | V1, V4, V5 | Remote `uv run mypy` failed because a CLI test fake runtime did not accept the new `record_trace(..., status=...)` interface. The fake now matches the runtime port contract. Verified locally with `uv run mypy`, `uv run pytest tests/cli/test_research.py -q` (59 passed), targeted `ruff`, and `git diff --check`; pushed the fix to `codex/research-actions-pkg-contract`. This is a CI-contract cleanup for #761 observability, not new split scope. | Re-check PR #755 CI and review state, then continue only the remaining Phase 0 #761 hardening gates once the branch is green. |
| 2026-06-12 | Re-check remote CI for PR #755 and PR #763 after the failed-search follow-up. | V1, V5 | `gh pr checks 755` reported build, commit-lint, and test passing; `gh pr checks 763` reported build, commit-lint, and test passing. The active code and planning branches are ready for the next Phase 0 slice, with existing unrelated dirty/untracked files left untouched. | Select the next #761 hardening item that improves the extraction boundary without reopening completed #764 or docs-only work. |
| 2026-06-12 | Execute Phase 0 slice for #761 typed checkpoint pause signaling on branch `codex/research-actions-pkg-contract`; pushed commit `85b623a1` (`fix(research): type checkpoint pause signal`). | V1, V2, V4, V5 | Engine orchestration now raises `ResearchOrchestratorPaused` for checkpoint waits instead of encoding a normal pause as `ResearchOrchestratorError(exit_code=0)`, and the CLI translates that typed pause to exit 0. Verified red-green with `tests/gaia/test_research_orchestrator.py::test_checkpoint_assess_pause_uses_typed_engine_signal`, then `uv run pytest tests/gaia/test_research_run_config.py tests/gaia/test_research_stop.py tests/gaia/test_research_report.py tests/gaia/test_research_orchestrator.py -q`, `uv run pytest tests/cli/test_research.py -q -k "checkpoint or failed or override or report"`, targeted `ruff`, targeted `mypy`, `uv run ruff format --check gaia/engine/research gaia/cli/commands/research.py tests/gaia/test_research_orchestrator.py`, `git diff --check`, and `rg "exit_code=0|ResearchOrchestratorError\\(exit_code=0\\)" ...` with no matches. This strengthens the future SDK/agent-framework boundary without changing checkpoint user-facing CLI behavior. | Re-check PR #755 remote CI, then continue remaining #761 hardening around typed provider/materialization errors or report failure/concurrency cleanup. |
| 2026-06-12 | Re-check remote CI after typed checkpoint pause slice. | V1, V5 | `gh pr checks 755` reported build, commit-lint, and test passing for commit `85b623a1`; `gh pr checks 763` reported build, commit-lint, and test passing after the execution-record update. Both active PR branches are green again. | Continue Phase 0 #761 with typed provider/materialization errors or report failure/concurrency cleanup; do not start Phase 1 until remaining high-risk #761 ownership is explicit. |
| 2026-06-12 | Execute Phase 0 slice for #761 command-provider failure observability on branch `codex/research-actions-pkg-contract`; pushed commit `5fc6e72c` (`fix(research): trace failed command providers`). | V1, V4, V5 | Command-backed provider failures now write failed `provider.command.<phase>` trace records before CLI exit, including provider phase, return code, stdout/stderr sizes, and error text; missing output and invalid JSON outputs also mark state failed and emit `run.failed`. Verified red-green with `tests/cli/test_research.py::test_research_run_records_failed_command_provider_trace` (initial failure showed the last trace was still `explore.scan`), then `uv run pytest tests/cli/test_research.py -q -k "checkpoint or failed or override or report or provider"`, `uv run pytest tests/gaia/test_research_run_config.py tests/gaia/test_research_stop.py tests/gaia/test_research_report.py tests/gaia/test_research_orchestrator.py -q`, targeted `ruff`, targeted `mypy`, `uv run ruff format --check gaia/cli/commands/research_providers.py tests/cli/test_research.py`, and `git diff --check`. This closes another provider failure observability gap for product/skill callers without changing successful provider behavior. | Re-check PR #755 remote CI, then continue remaining #761 hardening around materialization typed errors or report failure/concurrency cleanup. |
| 2026-06-12 | Re-check remote CI after command-provider failure trace slice. | V1, V5 | `gh pr checks 755` reported build, commit-lint, and test passing for commit `5fc6e72c`; `gh pr checks 763` reported build, commit-lint, and test passing after the execution-record update. Both active PR branches are green after this provider observability slice. | Continue Phase 0 #761 with materialization typed errors or report failure/concurrency cleanup; keep graph-session/O(N) requirements reserved for the later extraction phases rather than folding them into CLI-only fixes. |
| 2026-06-12 | Execute Phase 0 slice for #761 materialization runtime-port error translation on branch `codex/research-actions-pkg-contract`; pushed commit `5d500f5c` (`fix(research): translate materialization exits`). | V1, V2, V5 | `CliResearchOrchestratorRuntime` now translates `typer.Exit` from CLI-only materialization helpers into `ResearchOrchestratorError`, preserving the exit code while keeping engine workflow ports free of CLI exception types. Verified red-green with `tests/cli/test_research.py::test_cli_orchestrator_runtime_translates_materialization_exit` (initial failure leaked `click.exceptions.Exit: 1`), then `uv run pytest tests/cli/test_research.py -q -k "checkpoint or failed or override or report or provider or materialization"`, `uv run pytest tests/gaia/test_research_orchestrator.py tests/gaia/test_research_report.py tests/gaia/test_research_run_config.py tests/gaia/test_research_stop.py -q`, targeted `ruff`, targeted `mypy`, `uv run ruff format --check gaia/cli/commands/research_orchestrator.py tests/cli/test_research.py`, and `git diff --check`. This reduces CLI coupling before extraction; it does not yet create the public Gaia core materialization API planned for Phase 1. | Re-check PR #755 remote CI, then continue remaining #761 report failure/concurrency cleanup or move to Phase 1 public materialization/authoring APIs once high-risk ownership is explicit. |
| 2026-06-12 | Execute first Phase 1 slice for public Gaia core materialization APIs on branch `codex/research-actions-pkg-contract`; pushed commit `06678bbd` (`feat(materialize): expose public LKM APIs`). | V1, V2, V5 | Added `gaia.engine.materialize` as a public facade for LKM paper and reasoning-chain materialization so downstream `gaia-research` code can import engine-level APIs instead of `gaia.cli.commands.pkg.lkm_materialize`. Verified red-green with `tests/gaia/test_materialize_api.py` (initial failure: `ModuleNotFoundError: No module named 'gaia.engine.materialize'`), then `uv run pytest tests/cli/search/test_lkm_package_e2e.py tests/gaia/test_materialize_api.py -q`, targeted `ruff`, targeted `mypy`, `uv run ruff format --check gaia/engine/materialize.py tests/gaia/test_materialize_api.py`, and `git diff --check`. This is a facade/API-stability step only; dependency installer APIs and deeper CLI implementation movement remain open. | Re-check PR #755 remote CI, then continue Phase 1 materialization installer APIs or Phase 1 authoring API (#745), keeping the split goal centered on `gaia-research -> gaia core` one-way dependency. |
| 2026-06-12 | Execute second Phase 1 slice for public Gaia core package installer APIs on branch `codex/research-actions-pkg-contract`. | V1, V2, V5 | Added `gaia.engine.packaging.add_editable_package_dependency`, `resolve_gaia_package_root`, and `is_gaia_package_dir` so downstream `gaia-research` code can add generated local Gaia packages through an engine-level API instead of importing CLI command modules. `gaia pkg add` now reuses the public package-root resolver while preserving its CLI-specific `uv` runner seam and error text. Verified red-green with `tests/gaia/test_packaging_installer_api.py` (initial failure: `ImportError: cannot import name 'add_editable_package_dependency'`); the new public API test is marked `pr_gate`. Then ran `uv run pytest tests/cli/search/test_lkm_package_e2e.py tests/gaia/test_materialize_api.py tests/gaia/test_packaging_installer_api.py tests/cli/test_add.py -q` (58 passed), targeted `ruff`, targeted `mypy`, `uv run ruff format --check gaia/engine/packaging.py gaia/cli/commands/add.py tests/gaia/test_packaging_installer_api.py`, and `git diff --check`. This is the local editable dependency installer API slice only; registry install and LKM network fetch APIs remain CLI-owned until separate Phase 1 work. | Commit and push this code slice, then re-check PR #755 CI before deciding between Phase 1 authoring API (#745) and core plugin entry points. |
| 2026-06-12 | Execute first Phase 1.2 slice for public Gaia core authoring APIs on branch `codex/research-actions-pkg-contract`. | V1, V2, V5 | Added `gaia.engine.authoring` with public `ProposedAuthorOp`, `run_author_batch`, structured batch result types, and compatibility exports for the stable authored-submodule/write helpers used by research. Batch authoring writes operations in order, supports later operations referencing earlier labels, runs one final `postwrite_check`, and rolls back source files on later prewrite/postwrite failure. `gaia.cli.commands.author._proposed_op` now re-exports the engine model, and `gaia.engine.research.sync` imports authoring helpers through the public engine facade instead of directly importing `gaia.cli.commands.author._*`. Verified red-green with `tests/gaia/test_authoring_api.py` (initial failure: `ModuleNotFoundError: No module named 'gaia.engine.authoring'`), then fixed an import-cycle caught by `uv run pytest tests/cli/author -q`. Final local evidence: `uv run pytest tests/gaia/test_authoring_api.py tests/gaia/test_research_artifacts.py tests/gaia/test_research_assessment.py -q` (21 passed), `uv run pytest tests/cli/author -q` (343 passed), `uv run pytest tests/cli/test_research.py -q -k "sync or candidate_relation or unparseable_sync_source"` (3 passed, 58 deselected), targeted `ruff`, targeted `mypy`, `uv run ruff format --check ...`, and `git diff --check`. This is not full #745 closure: the remaining work is to move more CLI author implementation/helpers behind the public engine API and wire CLI verbs onto the public batch/write surface where appropriate. | Commit and push this code slice, re-check PR #755/#763 CI, then continue Phase 1.2 or move to public LKM client depending on the next highest coupling blocker. |
| 2026-06-12 | Execute Phase 1.1 slice for public Gaia core LKM client/index/error APIs on branch `codex/research-actions-pkg-contract`. | V1, V2, V4, V5 | Added `gaia.lkm.client` and `gaia.lkm.indexes` as public import surfaces for LKM access, index normalization, and typed error handling. CLI-private `gaia.cli.commands.search.lkm._client` and `_indexes` now compatibility re-export the public modules, while CLI `_shared.run_request` translates `LKMPermissionError` and `LKMNotFoundError` into CLI exit codes. The public error surface includes `LKMCredentialError`, `NoAccessKeyError`, `LKMTransportError`, `LKMPermissionError`, `LKMNotFoundError`, and envelope `LKMError`, so downstream `gaia-research` can distinguish transport, permission, not-found, credential, and business-envelope failures without importing Typer or CLI modules. Verified red-green with `tests/gaia/test_lkm_client.py` (initial failure: `ModuleNotFoundError: No module named 'gaia.lkm'`), then fixed an import-cycle by moving index helpers to `gaia.lkm.indexes`. Fresh local evidence: `uv run pytest tests/gaia/test_lkm_client.py tests/cli/search/test_lkm_auth.py tests/cli/search/test_lkm_verbs.py -q` (99 passed), `uv run pytest tests/cli/search/test_lkm_package_e2e.py tests/gaia/test_materialize_api.py -q` (24 passed), targeted `ruff`, targeted `mypy`, `uv run ruff format --check ...`, and `git diff --check`. This is a public client/error slice only; public credential/readiness APIs remain a separate Phase 1.1 slice. | Commit and push this code slice, update PR #755 evidence, then continue Phase 1.1 credential/readiness or Phase 1 plugin entry points based on the highest remaining extraction blocker. |
| 2026-06-12 | Follow up on PR #755 wheel-smoke failure after the public LKM client slice. | V1, V2, V5 | Remote `gh pr checks 755` showed build and commit-lint passing, `Run tests` passing, but the wheel smoke step failed because the built wheel omitted the new `gaia.lkm` package (`ModuleNotFoundError: No module named 'gaia.lkm'` during installed `gaia --help`). Added `gaia.lkm*` to setuptools package discovery, added a packaging contract test for the public LKM namespace, and extended the wheel-smoke facade import list to include `gaia.lkm`. Verified the red test first with `uv run pytest tests/test_alpha0_packaging.py -q` (failed on missing `gaia.lkm*`), then final local evidence: `uv run pytest tests/test_alpha0_packaging.py tests/gaia/test_lkm_client.py tests/cli/search/test_lkm_auth.py tests/cli/search/test_lkm_verbs.py -q` (101 passed), `uv run pytest tests/cli/search/test_lkm_package_e2e.py tests/gaia/test_materialize_api.py -q` (24 passed), targeted `ruff`, targeted `mypy`, YAML parse for `.github/actions/wheel-smoke/action.yml`, `git diff --check`, `uv build --wheel --out-dir /tmp/gaia-lkm-wheel-check-c2e066e0`, zipfile check for `gaia/lkm/{__init__,client,indexes}.py`, and direct `import gaia.lkm` from the built wheel path. | Commit and push the wheel packaging fix, then re-check PR #755 remote CI until build, commit-lint, and test are all green. |
| 2026-06-12 | Address PR #763 review findings after PR #755 merged into main. | V1, V2, V5 | Made the then-current 0-7 phase map consistent across the split plan and acceptance checklist; that map is now superseded by Goal A 0-6. Also changed `gaia-research` dependency guidance to `gaia-lang>=0.6,<0.8`, added the missing `tests/gaia/test_research_orchestrator.py` import path, and replaced stale path references. | Re-run doc consistency greps and push the #763 review-fix commit. |
| 2026-06-12 | Create #767 and realign split docs around Goal A. | V1, V3, V5 | Large-scale graph-session implementation notes now live in #767. Goal A docs should require repo split, Gaia connection, review-run parity, readiness, contract CI, and core removal; they should not require graph-session execution or O(N) tests. | Continue Goal A execution from public core surfaces, skill plugin discovery, repo bootstrap, and review-run parity gates. |
| 2026-06-12 | Execute Goal A namespace ownership slice on branch `codex/research-namespace-contract`. | V1, V2, V3 | Added a public `.gaia` namespace registry in `gaia.engine.namespaces` that reserves `.gaia/research/**` for `gaia-research` and deliberately does not register legacy `.gaia/research_loop/**`. Verified red-green with `tests/gaia/test_namespace_contracts.py` (initial failure: `ModuleNotFoundError: No module named 'gaia.engine.namespaces'`), then `uv run pytest tests/gaia/test_namespace_contracts.py tests/test_alpha0_packaging.py -q` (5 passed), targeted `ruff`, targeted `mypy`, `uv run ruff format --check ...`, suppression budget, `git diff --check`, `uv build --wheel --out-dir /tmp/gaia-namespace-wheel-check`, and direct wheel import of `gaia.engine.namespaces`. This declares ownership only; it does not implement graph sessions or write research state. | Push the PR, then continue toward repo bootstrap or remaining public API surfaces. |
| 2026-06-12 | Execute Phase 1 public inquiry-state API contract slice on branch `codex/inquiry-public-api`. | V1, V2, V5 | Added `RESEARCH_PUBLIC_STATE_API`, re-exported it from `gaia.engine.inquiry`, documented the semver-governed inquiry-state subset that future `gaia-research` may import, and pinned it with a `pr_gate` contract test. Verified red-green with `tests/inquiry/test_public_state_api.py` (initial failure: missing `RESEARCH_PUBLIC_STATE_API`), then `uv run pytest tests/inquiry/test_public_state_api.py tests/inquiry/test_state.py -q` (10 passed), `uv run pytest tests/inquiry -q` (147 passed), targeted `ruff`, targeted `mypy`, `uv run ruff format --check ...`, suppression budget, and `git diff --check`. This declares an existing Gaia core surface public; it does not implement graph sessions or move research code. | Push this small PR, then continue Goal A Phase 1 with the next remaining public core surface or repo-bootstrap gate. |
| 2026-06-12 | Execute Goal A Phase 1 slice for installed skill discovery on branch `codex/skill-plugin-discovery`. | V1, V2, V5 | Added `gaia.skills` entry point discovery so installed distributions can expose Gaia-compatible skill trees. `gaia skill register/list` still materialize into the existing `.gaia-skills/` registry and agent-surface symlinks, while plugin skill trees merge with bundled skills without letting plugins shadow core skill names. Verified red-green with `tests/cli/test_skill.py::TestRegisterIntegration::test_register_materializes_installed_skill_entry_points`, then `uv run pytest tests/cli/test_skill.py -q`, targeted `ruff`, targeted `mypy`, and `git diff --check`. This advances the Goal A connection surface needed before moving research skills out of Gaia core; it does not implement graph sessions. | Push the skill discovery PR, then continue Goal A with repo bootstrap or review-run parity after #768 lands. |

## 8. Process Learnings and PR Operating Rules

These rules were added after PR #755 merged and the follow-up PRs were
reviewed. They are process guardrails for the remaining split work, not new
product requirements.

### 8.1 PR Scope Boundaries

- Treat PR #755 as a merged extraction-prep base, not as the container for new
  research split work. New core surfaces, skill discovery, repo bootstrap,
  session contracts, and product readiness should land as separate PRs.
- Keep each new PR tied to one acceptance slice from the checklist. A PR may
  mention the broader split goal, but its own success criteria should be small
  enough to review and revert independently.
- Do not let a docs PR become the only place where implementation status is
  tracked. Code PRs should carry their own scope, verifier commands, and issue
  links in their PR bodies.
- Keep the split-plan PR as the stable design and acceptance baseline. Use this
  execution record as the single home for future cross-PR tracking, phase
  transitions, merge boundaries, and process learnings. Avoid turning it into a
  step-by-step live diary for every implementation detail.
- After this baseline lands, execution PRs should update this file in the same
  PR when they advance a phase, change merge order, close or re-home a tracked
  issue, or produce a process learning. Do not create separate docs-only
  tracking PRs just to record what an execution PR did.

### 8.2 Multi-PR Tracking

When the split is spread across multiple PRs, every PR should answer four
questions in its body:

1. Which acceptance item does this PR advance?
2. Which open issue or phase gate does it close, narrow, or re-home?
3. Which local verifier commands prove the slice?
4. What remains explicitly out of scope?

This execution record is the canonical place for future PR learnings and
tracking that matter across PRs. It should capture phase transitions, merge
boundaries, cross-PR decisions, merge-order changes, and learning that changes
how the rest of the work should be managed. Fine-grained verifier output should
stay in the relevant PR body unless it changes the global plan.

When an implementation PR changes any of those global facts, that same PR should
include the concise execution-record update. The PR body remains the detailed
review surface; this file remains the durable cross-PR memory.

### 8.3 Merge Order After PR #755

After PR #755 merged, the follow-up order should prefer dependency boundaries
before new research behavior:

1. Update and merge the CLI plugin entrypoint PR, so Gaia core can delegate
   `gaia research` to an installed downstream package.
2. Update and merge the credential/readiness public API PR, so
   `gaia-research doctor` can depend on a public core surface.
3. Update and merge the split-plan PR as the stable acceptance baseline.
4. Add the missing skill plugin discovery surface, such as `gaia.skills`, before
   moving bundled research skills out of Gaia core.
5. Treat #767 as the graph-session design handoff; do not implement
   `.gaia/research/sessions/**` as part of Goal A unless the goal is explicitly
   expanded again.

### 8.4 Design Gate Discipline

- Use explicit design approval gates only for long-lived contracts, protocol
  shapes, repo boundaries, and irreversible migration decisions.
- Do not block routine implementation slices on repeated approval prompts once
  the governing spec and acceptance checklist are already approved.
- If a design gate is waiting on user approval, record the blocked item clearly
  and stop changing code for that slice. Continue only with read-only review or
  unrelated already-approved work.
- The graph-session disk contract remains such a design-gated item in #767
  because it determines the O(N) continuation verifier, pause/resume semantics,
  repair context, and promotion boundary.

### 8.5 Worktree Hygiene

- Use the main worktree for read-only status checks only when it has unrelated
  dirty or untracked files.
- Put each implementation slice in a dedicated worktree/branch.
- Before editing, verify `git status --short --branch` in the target worktree
  and avoid touching unrelated dirty files.
- After #755, do not reuse its worktree for new implementation slices unless the
  change is a direct follow-up to that merged branch and the worktree is clean.
