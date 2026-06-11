# Research Repo Split Plan

> **Status:** proposal.
>
> **Date:** 2026-06-11
>
> **Context:** based on dependency analysis of PR #755 branch
> `codex/research-actions-pkg-contract` (head `44a3e4e2`) and the PR #755 review
> findings. Goal: extract the research implementation into an independent
> **gaia-research** repository that ships its own engine / SDK / CLI to
> downstream applications.

## 0. Current State and Feasibility

**Conclusion: extractable, and the boundary is unexpectedly clean.** Key facts:

- **Size**: 18 engine modules, 8,402 LOC + 5 CLI files, 4,954 LOC + 5,934 LOC of
  tests + the `gaia-research-loop` skill (~52 KB docs) + docs.
- **Reverse dependency (core → research) is a single line**:
  `app.add_typer(research_app, name="research")` in `gaia/cli/main.py`. A grep
  over the repo finds no other non-research code importing research code.
- **Forward dependencies (research → core) concentrate in five surfaces**
  (section 1).
- **Known coupling debt** (from the PR #755 review; must be fixed before the
  split):
  - `gaia/engine/research/sync.py:20-22` imports CLI-layer modules
    `gaia.cli.commands.author._authored` / `._common` / `._writer` (engine
    purity violation).
  - `research_providers.py` raises `typer.Exit` on an engine call path, and
    `ResearchOrchestratorError(exit_code=0)` doubles as a pause signal (review
    finding 14) — the port layer has no documented error contract.
  - The four high-severity review findings (stop-heuristic field mismatch,
    dropped `limitations`/`next_queries`, failures leaving `state.json` at
    `running`, chain-package dist-name collision) were addressed at head
    `44a3e4e2`; the remaining medium-severity follow-ups are tracked in
    [#761](https://github.com/SiliconEinstein/Gaia/issues/761), and the
    research-sync relation validation holes in
    [#764](https://github.com/SiliconEinstein/Gaia/issues/764). Both must be
    resolved or explicitly re-homed before the split; carrying known-broken
    contracts across two repos doubles the repair cost (section 7).

## 1. Dependency Boundary (five core surfaces research consumes)

| # | Core surface | Current location | API used by research | Problem |
|---|--------------|------------------|----------------------|---------|
| 1 | LKM search client | `gaia/cli/commands/search/lkm/_client.py`, `_shared.py`, `_indexes.py` | `LKMClient`, `run_request()`, `DEFAULT_LKM_INDEX_ID`, `normalize_lkm_index_id` | Buried under the CLI package with underscore-private names; `run_request` expresses errors as exit codes (4xx and network errors both map to exit 2 — review finding 11) |
| 2 | Authoring writes | `gaia/cli/commands/author/_authored.py`, `_writer.py`, `_common.py` | `ensure_authored_submodule()`, `append_statement()`, `split_csv_refs()` | Engine `sync.py` imports CLI modules directly |
| 3 | pkg add machinery | `gaia/cli/commands/add.py` + `gaia/cli/commands/pkg/lkm_materialize.py` (1,109 LOC) | `add_lkm_paper_dependency` / `add_lkm_claim_dependency` / `add_lkm_chain_dependency` / `add_local_package_dependency`; all of `lkm_materialize` | `lkm_materialize` is **shared code** (`gaia pkg add` uses it too) and cannot move with research |
| 4 | Inquiry state | `gaia/engine/inquiry/state.py` | `load_state()`, `save_state()`, `mint_qid()`, `SyntheticHypothesis`, `SyntheticObligation`, `append_tactic_event()` | Already engine-level, but never declared a public stable API |
| 5 | Credentials / misc | `gaia/cli/_credentials.py` (`read_lkm_key()`), `gaia.engine.packaging.GaiaPackagingError` | — | Credential reading also lives under the CLI |

Third-party dependencies: the engine side needs only pydantic (nearly a pure
library); the CLI side needs typer + litellm (lazily imported, `llm` extra) +
httpx (indirectly via the LKM client).

## 2. Target Architecture

**New repository `gaia-research`: one distribution, three layers** (not three
distributions — the current size does not justify that):

```
gaia-research/
  src/gaia_research/
    engine/        # pure library: orchestrator, landscape, assessment, report, stop, sync, ...
                   # zero typer, zero CLI imports; I/O confined to package-dir conventions
    sdk/           # public facade for downstream apps (new; section 4, S2)
    providers/     # litellm / command / checkpoint providers (litellm behind [llm] extra)
    cli/           # typer app; console script `gaia-research`
  pyproject.toml   # name=gaia-research, requires gaia-lang>=0.6,<0.7; extras: llm
```

- Dependency direction: `gaia-research → gaia-lang` (core), never the reverse.
- `gaia research ...` keeps working through a core CLI plugin mechanism (R2),
  alongside the standalone `gaia-research` entry point.
- Ownership of the on-disk contract `.gaia/research/**` (`state.json`,
  `events.ndjson`, manifest, trace, benchmark) transfers to the research repo
  and is explicitly versioned — downstream UIs depend only on that contract
  plus the SDK, never on internal modules.

## 3. Refactors in the Gaia Core Repo (R1–R6, in order)

**R1. Extract a stable core SDK surface** (a prerequisite for the split that is
itself a behavior-preserving refactor):

- LKM client: `gaia/cli/commands/search/lkm/_client.py` → `gaia/lkm/client.py`
  (public module). Error model becomes typed exceptions (`LKMTransportError` /
  `LKMPermissionError` / `LKMNotFoundError`); the CLI layer translates to exit
  codes. Fixes review finding 11 (retry only on transport errors) in passing.
  `read_lkm_key()` moves with it.
- Authoring write API: `author/_authored.py`, `_writer.py`, `_common.py` →
  `gaia/engine/authoring/` (public); CLI author commands become thin shells.
  This also removes the `sync.py` purity violation. The public API design must
  fold in the fast/batch author mode requested by
  [#745](https://github.com/SiliconEinstein/Gaia/issues/745) (batch statement
  writes with one explicit validation pass at the end) and add the post-write
  compile gate from [#764](https://github.com/SiliconEinstein/Gaia/issues/764)
  — `append_statement` must stop swallowing `SyntaxError`, so a research-repo
  caller can never leave `authored/__init__.py` unparseable.
- Package dependency installer: the four `add_*_dependency` functions from
  `add.py` → `gaia/engine/packaging/installer.py` (public).
- `gaia.engine.inquiry.state`: declare public in place (docs + semver
  commitment) for the six symbols research uses.
- Old import paths keep deprecation shims for one minor release.

**R2. CLI plugin mechanism**: define the entry-point group `gaia.cli_plugins`;
`main.py` discovers registered apps via `importlib.metadata.entry_points()` and
`add_typer`s them. Without gaia-research installed, `gaia research` prints an
install hint. Core has no such mechanism today (`main.py` is a static, flat
registry), but the implementation is small and reusable for future splits.

**R3. `lkm_materialize.py` stays in core** (shared with `gaia pkg add`) but
gains a public import path (e.g. `gaia/engine/materialize.py`); the research
repo imports it instead of vendoring. **Fix review finding 4 before the split
freeze** (content hash of the full claim id in the dist name) — both repos
depend on this naming convention, and changing it after the split requires a
two-repo lockstep.

**R4. Document the `.gaia/` namespace allocation**: core declares
`.gaia/research/**` owned by gaia-research and never writes under that prefix.

**R5. Remove research from core**: delete `gaia/engine/research/`,
`gaia/cli/commands/research*.py`, the 12 test files, the `gaia-research-loop`
skill, and research docs; the `llm` extra moves out with litellm; update help
snapshots; release note (including the LKM read-timeout 60s→120s default
change). Core bumps to 0.7.0 (R1+R2 ship earlier as 0.6.0).

**R6. Contract CI**: core adds a downstream-compat job that installs
gaia-research (main branch) and runs its smoke tests, so core changes cannot
silently break the five surfaces in section 1. Research tests leave the
`pr_gate` slice together with the code.

## 4. Refactors on the Research Side (S1–S8)

**S1. Pre-split fixes (while still in the monorepo; PR #755 follow-up)**:

- Close out [#764](https://github.com/SiliconEinstein/Gaia/issues/764): surface
  silently skipped candidate relations as user-visible diagnostics, validate
  `claim_refs` against the evidence packet (reject unknown refs instead of
  passing them), and gate sync writes behind a compile check.
- Work through the [#761](https://github.com/SiliconEinstein/Gaia/issues/761)
  scope list — it overlaps S1 almost item-for-item: moving run orchestration
  out of CLI support modules into engine APIs, hardening multi-focus
  checkpoint/resume, `None`-sentinel CLI override flags, sectioned-report
  failure/concurrency behavior, citation-fallback dedup, and typed
  retry/error contracts.
- `sync.py` switches to the R1 `gaia.engine.authoring` API.
- Remove typer from the engine entirely: `typer.Exit(2)` in
  `research_providers.py` becomes a typed provider exception; the pause stops
  masquerading as `ResearchOrchestratorError(exit_code=0)` and becomes an
  explicit `CheckpointPause` signal/return; `orchestrator_ports.py` Protocols
  document the error contract (finding 14).
- The report pipeline (`research_report_writing.py`, 908 LOC) currently lives
  in the CLI layer but is engine logic (concurrent section writing, citation
  merging); push it down to the engine, leaving only argument parsing in the
  CLI.

**S2. New SDK facade layer** (the only official entry point for downstream
apps):

```python
from gaia_research import ResearchClient

client = ResearchClient(package_dir)
run = client.run(topic=..., profile="review")   # or expand/focus/assess/report/stop
state = client.read_state(run.run_id)            # typed RunState (pydantic)
for ev in client.iter_events(run.run_id):        # typed event stream
    ...
```

- Freeze the dict contracts of `state.json` / `events.ndjson` / artifacts into
  pydantic models (today `contracts.py` holds prompt/schema dicts, not typed
  models).
- The ports in `orchestrator_ports.py` become the documented extension point
  (custom analysis/search providers).

**S3. Provider layering**: litellm goes behind the `gaia-research[llm]` extra;
the command/checkpoint providers are built-in and dependency-free. Fix the
rate-limit retry per review finding 18 (typed `RateLimitError` + exponential
backoff with jitter) in the same pass.

**S4. Versioned disk contract**: every file under `.gaia/research/**` carries an
explicit `schema_version` and a published contract document; downstream UIs key
compatibility off the schema version. Fixing finding 3 (all failure paths write
`status: failed` plus a `run.failed` event) is a precondition for this contract
being trustworthy.

**S5. Dual CLI entry**: console script `gaia-research` (standalone) plus the
`gaia.cli_plugins` entry point (preserving the `gaia research ...` muscle
memory).

**S6. Tests and CI**: the 12 unit files and the 4,378-line CLI E2E move over;
establish its own `pr_gate`; contract tests run against a pinned
`gaia-lang==<floor>`, with a nightly matrix row against gaia-lang main. Close
the coverage gaps the review identified (live-search failure path,
command-provider failure branches, stop tests consuming a real landscape
artifact).

**S7. Skill moves over**: the `gaia-research-loop` skill ships as gaia-research
package data. Core's `gaia skill register` currently only copies the bundled
`gaia/_skills/` tree — it needs a small change to scan skills exposed by
installed distributions (reusable entry-point group, e.g. `gaia.skills`).

**S8. Independent versioning and releases**: own commitizen config, semver, and
changelog; first release `gaia-research 0.1.0` depending on
`gaia-lang>=0.6,<0.7`; replicate core's alpha/beta/rc/stable four-channel
`workflow_dispatch` release process.

## 5. Migration Order (five phases)

| Phase | Content | Output |
|-------|---------|--------|
| 0 | Land PR #755 + S1 pre-split fixes (findings 1–4, de-typer, sync decoupling prep) | research still in the monorepo, but "movable" |
| 1 | Core R1 (API extraction + shims) + R3 (public materialize + finding 4 fix) + R4 | **gaia-lang 0.6.0**, no behavior change |
| 2 | Core R2 plugin mechanism; bootstrap the new repo — import with `git filter-repo --path gaia/engine/research --path gaia/cli/commands/research... --path tests/...` to preserve history | gaia-research repo ready (unpublished) |
| 3 | Dual-track transition: one more core release still bundling research with a `DeprecationWarning`; publish gaia-research 0.1.0 (S2–S8 complete) | downstream can switch smoothly |
| 4 | Core R5 removal + R6 contract CI | **gaia-lang 0.7.0** (without research) |

## 6. Risks and Decision Points

1. **Shared ownership of `lkm_materialize.py`** is the largest long-term
   friction point: both sides depend on the chain/paper package naming
   convention. Mitigation: the finding-4 content-hash fix, the naming
   convention written into the contract doc, and R6 contract-test coverage.
2. **`inquiry.state` API drift**: research sync reads and writes inquiry state
   deeply; a core schema change breaks research. Mitigation: R6 contract tests
   plus a state schema version.
3. **History preservation vs. clean start**: recommend `git filter-repo` to
   keep history (high forensic value for review/debugging) at the cost of a
   one-time tooling step.
4. **Downstream UIs**: every UI reading paths like
   `.gaia/research/runs/<id>/state.json` sees unchanged paths through phase 3;
   only the `schema_version` field is added — backward compatible.
5. **When the split is not worth it**: if research iteration stays tightly
   synchronized with core (every core change drags a research change), two
   repos turn one PR into two. Current evidence (PR #755 is almost purely
   additive; the reverse dependency is one line) supports the split; if the
   `sync.py` ↔ authoring coupling deepens, re-evaluate.

## 7. Tracked Issues and Coverage

Open issues that the split plan must absorb, mapped to the work items that
cover them:

| Issue | What it tracks | Covered by | Phase | Exit criterion |
|-------|----------------|-----------|-------|----------------|
| [#764](https://github.com/SiliconEinstein/Gaia/issues/764) | Candidate relations silently skipped during research sync; `claim_refs` validation holes; missing compile gate after authored writes | S1 (skip diagnostics, packet validation) + R1 (compile gate in the public authoring API) | 0–1 | Closed before the phase-2 repo bootstrap |
| [#761](https://github.com/SiliconEinstein/Gaia/issues/761) | PR #755 review follow-ups: engine/CLI orchestration extraction, multi-focus checkpoint semantics, CLI override sentinels, report failure/concurrency, citation dedup, typed retry contracts | S1 (engine extraction, checkpoints, overrides) + S2 (report rendering consolidation) + S3 (retry contracts) | 0–3 | Every checkbox either closed or re-homed to gaia-research before phase 4 |
| [#745](https://github.com/SiliconEinstein/Gaia/issues/745) | Fast/batch author mode for agent research workflows | R1 (the public `gaia.engine.authoring` API ships batch writes + single validation pass as a first-class mode, not a research-side workaround) | 1 | Closed by the R1 extraction PR |

Related but on a parallel track:
[#762](https://github.com/SiliconEinstein/Gaia/issues/762) (new-user readiness
for research review workflows) is product work, explicitly separated from the
internal refactors above; it becomes part of the gaia-research 0.1.0 release
criteria in phase 3 and moves to the new repo's tracker at bootstrap.

**Coverage mechanism** — three enforcement points so these do not silently
fall through the split:

1. **PR linkage**: every implementing PR for S1/R1 work references its issue
   with `Closes #N` (or checks off the matching #761 checkbox), so issue state
   is the single source of progress truth — not this spec.
2. **Phase gates**: the phase table in section 5 is only advanceable when the
   issues listed for that phase in the table above are closed or explicitly
   re-homed. Phase 2 (repo bootstrap) is the hard cutoff for #764; phase 4
   (core removal) is the hard cutoff for the rest.
3. **Issue re-homing at bootstrap**: when the gaia-research repo is created in
   phase 2, any still-open research-side issue (or unchecked #761 item whose
   code moved) is transferred to the new repo's tracker (GitHub issue
   transfer), and the old issue is closed with a forwarding link. Core keeps
   only issues whose fix lands in core code (R1–R6 surfaces). The R6
   downstream-compat CI job is the backstop that re-detects anything both
   trackers lose.

## Appendix: Stay / Move Boundary at a Glance

| Stays in gaia-lang | Moves to gaia-research |
|--------------------|------------------------|
| LKM client (made public), `lkm_materialize.py`, authoring write API (made public), package installer, `inquiry.state`, credentials, `DEFAULT_LKM_INDEX_ID` | all 18 modules of `gaia/engine/research/**` (including `source_packages.py` and the atomic-write helpers in `artifacts.py`), the 5 `research*.py` CLI files, the report-writing pipeline, providers, the `gaia-research-loop` skill, research docs, the 12+1 test files, the `llm` extra |
