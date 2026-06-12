# Research Repo Split Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Split Gaia's research module into an independent `gaia-research` repository with first-class review-run and graph-session modes.

**Architecture:** Gaia core keeps public language/package/search/authoring/materialization primitives and plugin hooks. `gaia-research` owns the shared research kernel, versioned `.gaia/research/**` contracts, SDK, providers, CLI, skill assets, review-run orchestration, and long-running graph-session orchestration. Contract CI proves the one-way dependency `gaia-research -> gaia core`.

**Tech Stack:** Python 3.12, uv, Typer, Pydantic v2, pytest, ruff, mypy strict, GitHub Actions, Gaia package/check tooling, optional LiteLLM behind a `llm` extra.

---

## Source Specs

- Design: `docs/specs/2026-06-11-research-repo-split-plan.md`
- Execution record: `docs/specs/2026-06-12-research-repo-split-execution-record.md`
- Acceptance checklist: `docs/specs/2026-06-12-research-repo-split-acceptance-checklist.md`

Before starting any task, update the execution record with the verifier set for
that task. After finishing any task, add the evidence command/output summary to
the execution record.

## Phase Map

| Phase | Purpose | Exit gate |
| --- | --- | --- |
| 0 | Make monorepo research movable by closing correctness/coupling blockers. | PR #755 landed/superseded; #761 high-risk items owned; #764 closed or fixed before bootstrap. |
| 1 | Extract Gaia core public APIs used by research. | Public LKM, authoring, materialization, inquiry, credentials, plugin surfaces exist and pass contract tests. |
| 2 | Bootstrap `gaia-research` repo and preserve/import history. | New repo has package metadata, migrated code/tests/docs/skills, and no canonical `.gaia/research_loop/**` writes. |
| 3 | Build `gaia-research` shared contracts and SDK. | Review-run and graph-session contracts are typed and SDK-accessible. |
| 4 | Re-enable review-run mode in the new repo. | Product/skill smoke tests produce observable state/events/report paths. |
| 5 | Implement graph-session mode. | Incremental continuation, pause/resume, node/edge/focus/field-map records pass instrumented tests. |
| 6 | Product readiness, skills, and doctor. | #762 acceptance checks pass and short happy paths are documented. |
| 7 | Contract CI, release, and Gaia core removal. | Core installs downstream `gaia-research`, plugin path works, core no longer owns research implementation. |

## Phase 0: Make Monorepo Research Movable

**Files likely modified in Gaia core worktree:**

- `gaia/engine/research/sync.py`
- `gaia/engine/research/orchestrator.py`
- `gaia/engine/research/orchestrator_ports.py`
- `gaia/engine/research/report.py`
- `gaia/engine/research/run.py`
- `gaia/engine/research/benchmark.py`
- `gaia/cli/commands/research*.py`
- `gaia/cli/commands/pkg/lkm_materialize.py`
- `tests/gaia/test_research_*.py`
- `tests/cli/test_research.py`
- `tests/cli/search/test_lkm_package_e2e.py`

### Task 0.1: Rebase and Re-verify PR #755 Head

- [ ] Fetch the current branch and PR state.

  ```bash
  gh pr view 755 --json number,state,headRefName,mergeable,commits,files,reviews,comments
  git fetch origin codex/research-actions-pkg-contract
  git switch codex/research-actions-pkg-contract
  git status --short
  ```

- [ ] Re-run the PR's stated test plan.

  ```bash
  uv run pytest tests/cli/test_research.py tests/gaia/test_research_report.py tests/gaia/test_research_evidence_selection.py tests/gaia/test_research_assessment.py -q
  uv run ruff check gaia/cli/commands/research.py gaia/engine/research/report.py gaia/engine/research/__init__.py tests/cli/test_research.py
  uv run ruff format --check gaia/cli/commands/research.py gaia/engine/research/report.py gaia/engine/research/__init__.py tests/cli/test_research.py
  uv run mypy gaia/cli/commands/research.py gaia/engine/research/report.py gaia/engine/research/__init__.py
  git diff --check
  ```

- [ ] Record any changed PR findings in the execution record before editing.

**Acceptance evidence:** The execution record lists the verified PR #755 head
commit and any remaining blockers tied to #761/#764.

### Task 0.2: Close #764 Relation Sync Correctness Gap

- [ ] Add tests that assert relation skip diagnostics are user-visible and
  machine-readable.

  Target tests:

  ```text
  tests/gaia/test_research_sync.py::test_question_typed_relation_ref_reports_visible_skip
  tests/gaia/test_research_sync.py::test_claim_typed_relation_ref_writes_candidate_relation
  tests/gaia/test_research_sync.py::test_unknown_claim_ref_is_rejected_before_sync_write
  tests/gaia/test_research_sync.py::test_sync_compile_gate_rejects_invalid_authored_python
  ```

- [ ] Update `gaia/engine/research/sync.py` so `claim_refs` are validated
  against evidence packet refs with `value_type == "claim"` before writing.
- [ ] Surface skipped relations in CLI summary output and structured events.
- [ ] Add a post-write compile/import or AST gate so invalid authored source
  cannot remain silent.
- [ ] Run:

  ```bash
  uv run pytest tests/gaia/test_research_sync.py -q
  uv run pytest tests/cli/test_research.py -q -k "sync or candidate_relation"
  uv run ruff check gaia/engine/research/sync.py tests/gaia/test_research_sync.py
  uv run mypy gaia/engine/research/sync.py
  ```

**Acceptance evidence:** #764 is closed by PR or re-homed with a blocking label;
the acceptance checklist A9 points to the closing PR.

### Task 0.3: Finish #761 High-Risk Follow-Ups Needed Before Split

- [ ] Move remaining orchestration logic out of CLI support modules and into
  engine services.
- [ ] Replace `typer.Exit` and `ResearchOrchestratorError(exit_code=0)` pause
  signaling with typed engine exceptions or return objects.
- [ ] Make multi-focus checkpoint/resume either per-focus or rejected with a
  clear validation error.
- [ ] Fix explicit CLI override handling with `None` sentinels.
- [ ] Ensure failed provider/search/sync paths write `status: "failed"` and a
  `run.failed` event.
- [ ] Run:

  ```bash
  uv run pytest tests/gaia/test_research_run_config.py tests/gaia/test_research_stop.py tests/gaia/test_research_report.py -q
  uv run pytest tests/cli/test_research.py -q -k "checkpoint or failed or override or report"
  uv run ruff check gaia/engine/research gaia/cli/commands/research*.py tests/gaia/test_research_*.py tests/cli/test_research.py
  uv run mypy gaia/engine/research gaia/cli/commands/research.py
  ```

**Acceptance evidence:** #761 checkboxes are either closed or transferred to
the future `gaia-research` repo with phase and owner.

## Phase 1: Extract Gaia Core Public APIs

**Files likely modified in Gaia core worktree:**

- `gaia/lkm/client.py`
- `gaia/lkm/__init__.py`
- `gaia/engine/authoring/`
- `gaia/engine/materialize.py`
- `gaia/engine/packaging.py`
- `gaia/engine/inquiry/state.py`
- `gaia/cli/main.py`
- `gaia/cli/_credentials.py`
- `gaia/cli/commands/search/lkm/*.py`
- `gaia/cli/commands/author/*.py`
- `tests/cli/search/test_lkm_auth.py`
- `tests/gaia/test_authoring_api.py`
- `tests/gaia/test_materialize_api.py`
- `tests/cli/test_cli_plugins.py`

### Task 1.1: Public LKM Client and Credential Surface

- [ ] Create `gaia/lkm/client.py` as the public LKM client facade.
- [ ] Define typed errors:

  ```text
  LKMTransportError
  LKMPermissionError
  LKMNotFoundError
  LKMCredentialError
  ```

- [ ] Move or expose `read_lkm_key()` through the public LKM/readiness surface.
- [ ] Keep CLI exit-code translation in CLI modules only.
- [ ] Run:

  ```bash
  uv run pytest tests/cli/search/test_lkm_auth.py tests/cli/search/test_lkm_package_e2e.py -q
  uv run pytest tests/gaia/test_lkm_client.py -q
  uv run ruff check gaia/lkm gaia/cli/commands/search/lkm tests/gaia/test_lkm_client.py
  uv run mypy gaia/lkm gaia/cli/commands/search/lkm
  ```

**Acceptance evidence:** Research-side retry logic can distinguish transport
errors from permission/not-found errors without inspecting Typer exit codes.

### Task 1.2: Public Authoring API With Batch Mode (#745)

- [ ] Create `gaia/engine/authoring/` public API.
- [ ] Move stable helpers from private CLI modules into the public package.
- [ ] Add batch write API with one explicit final validation pass.
- [ ] Ensure invalid authored Python raises a typed error and cannot be
  swallowed.
- [ ] Run:

  ```bash
  uv run pytest tests/gaia/test_authoring_api.py -q
  uv run pytest tests/cli/author -q
  uv run ruff check gaia/engine/authoring gaia/cli/commands/author tests/gaia/test_authoring_api.py
  uv run mypy gaia/engine/authoring gaia/cli/commands/author
  ```

**Acceptance evidence:** #745 closes through this API; `gaia-research` never
imports `gaia.cli.commands.author._*`.

### Task 1.3: Public Materialization and Installer APIs

- [ ] Expose package dependency installer functions under
  `gaia/engine/packaging.py` or an equivalent public module.
- [ ] Expose LKM materialization under `gaia/engine/materialize.py` or an
  equivalent public module.
- [ ] Add content digest to LKM chain package names so sibling claims cannot
  collide.
- [ ] Run:

  ```bash
  uv run pytest tests/cli/search/test_lkm_package_e2e.py tests/gaia/test_materialize_api.py -q
  uv run ruff check gaia/engine/materialize.py gaia/engine/packaging tests/gaia/test_materialize_api.py
  uv run mypy gaia/engine/materialize.py gaia/engine/packaging
  ```

**Acceptance evidence:** PR #755 finding-4 collision test passes and the public
API is documented for downstream research.

### Task 1.4: Core Plugin Entry Points

- [ ] Add `gaia.cli_plugins` discovery to `gaia/cli/main.py`.
- [ ] Add an absent-plugin hint for `gaia research`.
- [ ] Add installed-plugin test using a tiny fixture package entry point.
- [ ] Add skill discovery entry point, such as `gaia.skills`, for installed
  distributions.
- [ ] Run:

  ```bash
  uv run pytest tests/cli/test_cli_plugins.py tests/cli/test_skill_plugins.py -q
  uv run ruff check gaia/cli/main.py tests/cli/test_cli_plugins.py tests/cli/test_skill_plugins.py
  uv run mypy gaia/cli/main.py
  ```

**Acceptance evidence:** `gaia research --help` is served by plugin when
`gaia-research` is installed and otherwise prints a clear install hint.

## Phase 2: Bootstrap the `gaia-research` Repository

**New repository files:**

- `pyproject.toml`
- `README.md`
- `src/gaia_research/__init__.py`
- `src/gaia_research/engine/`
- `src/gaia_research/contracts/`
- `src/gaia_research/sdk/`
- `src/gaia_research/providers/`
- `src/gaia_research/cli/`
- `src/gaia_research/skills/`
- `tests/`
- `.github/workflows/ci.yml`
- `docs/`

### Task 2.1: Create Repository and Import History

- [ ] Create the new repository.
- [ ] Import paths with history preservation:

  ```bash
  git filter-repo \
    --path gaia/engine/research \
    --path gaia/cli/commands/research.py \
    --path gaia/cli/commands/research_materialization.py \
    --path gaia/cli/commands/research_orchestrator.py \
    --path gaia/cli/commands/research_providers.py \
    --path gaia/cli/commands/research_report_writing.py \
    --path gaia/cli/commands/research_runtime.py \
    --path gaia/_skills/gaia-research-loop \
    --path tests/gaia/test_research_artifacts.py \
    --path tests/gaia/test_research_assessment.py \
    --path tests/gaia/test_research_contracts.py \
    --path tests/gaia/test_research_evidence_selection.py \
    --path tests/gaia/test_research_field_map.py \
    --path tests/gaia/test_research_focus.py \
    --path tests/gaia/test_research_landscape.py \
    --path tests/gaia/test_research_orchestrator.py \
    --path tests/gaia/test_research_proposal.py \
    --path tests/gaia/test_research_report.py \
    --path tests/gaia/test_research_run_config.py \
    --path tests/gaia/test_research_stop.py \
    --path tests/cli/test_research.py
  ```

- [ ] Import PR #726 docs/tests as historical references, not canonical runtime
  state.
- [ ] Record the import commit and source Gaia commit in the acceptance
  checklist evidence section.

**Acceptance evidence:** New repository URL and import commit satisfy checklist
A1.

### Task 2.2: Rename Package and Establish Metadata

- [ ] Move modules from `gaia/engine/research/**` to
  `src/gaia_research/engine/**`.
- [ ] Move CLI modules under `src/gaia_research/cli/**`.
- [ ] Create `pyproject.toml` with:

  ```toml
  [project]
  name = "gaia-research"
  dependencies = ["gaia-lang>=0.6,<0.8", "pydantic>=2"]

  [project.optional-dependencies]
  llm = ["litellm"]

  [project.scripts]
  gaia-research = "gaia_research.cli.main:app"

  [project.entry-points."gaia.cli_plugins"]
  research = "gaia_research.cli.plugin:research_app"

  [project.entry-points."gaia.skills"]
  gaia-research-loop = "gaia_research.skills:skill_manifest"
  ```

- [ ] Run:

  ```bash
  uv sync --extra dev
  uv run python -c "import gaia_research; print(gaia_research.__name__)"
  uv run gaia-research --help
  uv run pytest -q
  uv run ruff check src tests
  uv run mypy src tests
  ```

**Acceptance evidence:** Package metadata proves the new repo is installable and
entry points load.

## Phase 3: Shared Contracts and SDK

**Files likely created or modified in `gaia-research`:**

- `src/gaia_research/contracts/run.py`
- `src/gaia_research/contracts/session.py`
- `src/gaia_research/contracts/events.py`
- `src/gaia_research/contracts/tasks.py`
- `src/gaia_research/contracts/artifacts.py`
- `src/gaia_research/sdk/client.py`
- `src/gaia_research/engine/storage.py`
- `tests/contracts/`
- `tests/sdk/`

### Task 3.1: Versioned Disk Contract Models

- [ ] Define pydantic models for run state, session state, events, checkpoints,
  frontier records, node records, edge records, focus records, obligation
  records, task envelopes, candidates, and repair context.
- [ ] Require `schema_version` on every JSON/JSONL record.
- [ ] Add rebuild semantics for compact `state.json` indexes.
- [ ] Run:

  ```bash
  uv run pytest tests/contracts -q
  uv run ruff check src/gaia_research/contracts tests/contracts
  uv run mypy src/gaia_research/contracts tests/contracts
  ```

**Acceptance evidence:** Checklist A7 and the contract sections for both modes
are represented by tests.

### Task 3.2: ResearchClient Facade

- [ ] Implement `ResearchClient(package_dir)` with:

  ```text
  run_review(...)
  read_state(...)
  iter_events(...)
  open_session(...)
  resume_session(...)
  next_task(...)
  submit_candidate(...)
  build_landscape(...)
  assess_focus(...)
  write_report(...)
  ```

- [ ] Ensure CLI and skill paths call this SDK rather than duplicating workflow
  logic.
- [ ] Run:

  ```bash
  uv run pytest tests/sdk/test_review_client.py tests/sdk/test_session_client.py -q
  uv run ruff check src/gaia_research/sdk tests/sdk
  uv run mypy src/gaia_research/sdk tests/sdk
  ```

**Acceptance evidence:** Product and agent framework callers never need to parse
CLI output for core handles.

## Phase 4: Review Run Mode

**Files likely modified in `gaia-research`:**

- `src/gaia_research/engine/review_run.py`
- `src/gaia_research/engine/orchestrator.py`
- `src/gaia_research/engine/report.py`
- `src/gaia_research/providers/litellm.py`
- `src/gaia_research/providers/command.py`
- `src/gaia_research/cli/review.py`
- `tests/review/`
- `tests/skills/test_research_skill.py`

### Task 4.1: Port PR #755 Review Sequence

- [ ] Port the PR #755 sequence into `run_review`:

  ```text
  query_plan -> broad_search -> field_map -> focus -> selected_evidence ->
  assess -> stop -> report
  ```

- [ ] Ensure every failure path writes `status: "failed"` and `run.failed`.
- [ ] Ensure reader-facing reports do not leak internal refs.
- [ ] Run:

  ```bash
  uv run pytest tests/review -q
  uv run pytest tests/sdk/test_review_client.py -q
  uv run ruff check src/gaia_research/engine src/gaia_research/providers tests/review
  uv run mypy src/gaia_research/engine src/gaia_research/providers
  ```

**Acceptance evidence:** Checklist A4 and review-run acceptance checks pass.

### Task 4.2: Skill and Short Profile Path

- [ ] Move the research skill to `src/gaia_research/skills/`.
- [ ] Update skill instructions to use short profile-based SDK/CLI paths.
- [ ] Add test proving the skill does not require long flag recipes.
- [ ] Run:

  ```bash
  uv run pytest tests/skills/test_research_skill.py -q
  uv run gaia-research run-review --help
  ```

**Acceptance evidence:** Product/skill path is usable without copying long PR
commands.

## Phase 5: Graph Session Mode

**Files likely created or modified in `gaia-research`:**

- `src/gaia_research/engine/session.py`
- `src/gaia_research/engine/frontier.py`
- `src/gaia_research/engine/session_storage.py`
- `src/gaia_research/engine/field_map_delta.py`
- `src/gaia_research/engine/task_protocol.py`
- `src/gaia_research/cli/session.py`
- `tests/session/`

### Task 5.1: Session Storage and Append-Only Records

- [ ] Implement `.gaia/research/sessions/<session-id>/` storage:

  ```text
  state.json
  events.ndjson
  frontier.jsonl
  nodes.jsonl
  edges.jsonl
  focuses.jsonl
  obligations.jsonl
  field_map.json
  checkpoints/
  ```

- [ ] Add cursor/index files required for normal continuation.
- [ ] Run:

  ```bash
  uv run pytest tests/session/test_session_state_contract.py tests/session/test_frontier_append.py -q
  uv run ruff check src/gaia_research/engine/session*.py src/gaia_research/engine/frontier.py tests/session
  uv run mypy src/gaia_research/engine/session.py src/gaia_research/engine/frontier.py
  ```

**Acceptance evidence:** Checklist A5 and A7 pass.

### Task 5.2: Incremental Continuation Complexity Gate

- [ ] Add an instrumented storage adapter that records every file open/read.
- [ ] Seed a session with a large historical node/edge log.
- [ ] Submit a small new frontier batch.
- [ ] Assert normal continuation reads only:

  ```text
  state.json
  cursor/index files
  new frontier/input batch
  delta index files
  ```

- [ ] Add a separate full-rebuild command/test that is allowed to scan history.
- [ ] Run:

  ```bash
  uv run pytest tests/session/test_incremental_continuation.py -q
  uv run pytest tests/session/test_full_rebuild.py -q
  ```

**Acceptance evidence:** Checklist A6 is proven by test, not by code review.

### Task 5.3: Task Envelope, Candidate Repair, Pause/Resume

- [ ] Implement versioned task envelopes and candidate validation from PR #726
  lessons under `.gaia/research/**`.
- [ ] Reject invalid candidates without advancing the session.
- [ ] Produce repair context for the same task.
- [ ] Implement pause/resume from saved cursor without requiring a report.
- [ ] Run:

  ```bash
  uv run pytest tests/session/test_task_contract.py tests/session/test_pause_resume.py -q
  ```

**Acceptance evidence:** Agent framework integration can use deterministic
tasks while semantic judgment remains outside Gaia Research.

### Task 5.4: Promotion Boundary

- [ ] Ensure session continuation writes graph-session records only by default.
- [ ] Add explicit promotion/sync methods and tests for writing Gaia source.
- [ ] Run:

  ```bash
  uv run pytest tests/session/test_promotion_boundary.py -q
  ```

**Acceptance evidence:** Checklist A8 passes for long graph sessions.

## Phase 6: Product Readiness and Doctor

**Files likely created or modified in `gaia-research`:**

- `src/gaia_research/cli/doctor.py`
- `src/gaia_research/engine/readiness.py`
- `src/gaia_research/profiles.py`
- `docs/quickstart.md`
- `docs/sdk.md`
- `tests/doctor/`
- `tests/profiles/`

### Task 6.1: Doctor Command (#762)

- [ ] Implement `gaia-research doctor <pkg>`.
- [ ] Through plugin path, expose `gaia research doctor <pkg>`.
- [ ] Check package shape, `.gaia/research` writability, LKM credential
  readiness, provider/model config, profile resolution, run/session paths, and
  schema compatibility.
- [ ] Redact secrets from all output.
- [ ] Run:

  ```bash
  uv run pytest tests/doctor -q
  uv run gaia-research doctor --help
  ```

**Acceptance evidence:** #762 doctor/readiness checks pass.

### Task 6.2: Profiles and Docs

- [ ] Define `quick`, `review`, `deep`, and one graph-session profile.
- [ ] Document short commands:

  ```bash
  gaia-research doctor "$PKG"
  gaia-research run-review "$PKG" --topic "..." --profile quick
  gaia-research session open "$PKG" --topic "..." --profile graph
  ```

- [ ] Add docs smoke tests for command examples where feasible.
- [ ] Run:

  ```bash
  uv run pytest tests/profiles -q
  uv run pytest tests/docs -q
  ```

**Acceptance evidence:** Product and skill users do not need long flag recipes.

## Phase 7: Contract CI, Release, and Core Removal

**Files likely modified across repos:**

- Gaia core `.github/workflows/ci.yml`
- Gaia core `gaia/cli/main.py`
- Gaia core `pyproject.toml`
- Gaia core docs/release notes
- `gaia-research/.github/workflows/ci.yml`
- `gaia-research/README.md`
- `gaia-research/docs/release.md`

### Task 7.1: Downstream Contract CI

- [ ] Add Gaia core workflow that installs candidate Gaia core and compatible
  `gaia-research`.
- [ ] Run `gaia-research` smoke tests through both standalone and plugin paths.
- [ ] Run:

  ```bash
  gaia-research contract-smoke
  gaia research --help
  ```

**Acceptance evidence:** Checklist A3 and core removal gate pass.

### Task 7.2: Remove Research Implementation From Gaia Core

- [ ] Delete core-owned research implementation after `gaia-research` release
  candidate is available:

  ```text
  gaia/engine/research/**
  gaia/cli/commands/research*.py
  bundled research skill code
  core-owned research tests moved to gaia-research
  ```

- [ ] Keep plugin hint path and public core APIs.
- [ ] Update help snapshots and release notes.
- [ ] Run:

  ```bash
  make check
  uv run pytest tests/cli/test_cli_plugins.py -q
  ```

**Acceptance evidence:** Checklist A2 passes.

### Task 7.3: Final Completion Audit

- [ ] Run the acceptance checklist section 6 audit against current state.
- [ ] Inspect GitHub issue state for #745, #761, #762, and #764.
- [ ] Confirm every completion requirement A1-A10 has direct evidence.
- [ ] Only then mark the long-running goal complete.

**Acceptance evidence:** The final audit cites commands, PRs, issues, and
artifact paths for every requirement.

## Self-Review Notes

- This plan covers both short review runs and long graph sessions.
- It keeps `.gaia/research/**` as the only canonical research namespace.
- It assigns #745, #761, #762, and #764 to phase gates.
- It requires an instrumented storage test for the O(N) continuation claim.
- It separates full rebuild from normal continuation.
- It leaves stable Gaia source writes behind explicit promotion/sync gates.
