# Refactor STATE — v0.5 Quality Baseline Alignment

**Current phase**: Phase 2 in progress — full backfill
**Last updated**: 2026-05-12 10:00 (Phase 2.2-top complete)
**Branch**: `feat/v05-quality-baseline_rsw` (cut from `origin/v0.5` HEAD `8e8e771f`)
**协作单**: Feishu doc_token `AM15dZDhjooNyaxZRhNc1Sawnce` — decisions, ❓ escalation, and Caveats live there
**Kanban entry**: GAIA-LKM kanban (`IUvrwMmwliAUDukbXfUcwwxEnmf`)

---

## User Loop Prompt (paste this verbatim every time you start a new in-repo session)

```
Continue v0.5 quality refactor per .refactor/STATE.md.
```

CLAUDE.md mortal banner auto-loads → agent gets refactor discipline + boundary rules + no-PR policy. STATE.md (this file) holds the full task queue + current progress + contradiction records → the agent derives its next step, when to stop, when to record breakpoints, all from this file alone. No workflow / phase info should be forwarded from chat.

---

## How to use this document (required reading for every in-repo agent / contributor)

**First action on session start**: read this whole file → read `.refactor/doc-fidelity-baseline.md` → find the next `pending` task in the Task Queue → write your `claimed_by` + `claimed_at`, flip status to `in-progress`.

**During work**: any mid-task pause / context switch gets recorded under that task's `breakpoint_notes` (precise to file / symbol / line). At every meaningful commit, update STATE.md so progress is reflected.

**Last action before exit**: task done → status `done` + fill `completed_at`. Task not done (context exhausted / time up / interrupted) → keep status `in-progress`, but the `breakpoint_notes` MUST be precise enough for the next agent to resume losslessly (specific file / specific symbol / what was modified vs not / current mypy or ruff output fragment).

**🚨 If you find a doc-code contradiction**: stop immediately → set the current task's status to `blocked` → write to `breakpoint_notes` (doc paragraph reference + code file:line + description + impact area) → mirror the finding into the `## Doc-Code Contradiction Log` section of this file → notify the user. The user will return to home_agent so Claude can escalate to the 协作单 ❓ section. **Do not decide "which side is right" yourself, and do not "fix it up in passing"**.

---

## ☐ Phase Tracker

- [x] **Phase 0 — Repo prepare** (Claude-led from home_agent side)
  - Done: 0.1 branch cut · 0.2 doc fidelity baseline · 0.3 mortal banner · 0.4 STATE.md framework · 0.5 baseline metrics · 0.6 commit + push · 0.7 iteration playbook
- [x] **Phase 1 — Engineering baseline injection** (user dispatches in-repo agents serially)
  - Progress: 9 / 9 work units
- [ ] **🚦 Checkpoint α**: Phase 1 complete → user returns to home_agent for Claude to verify
- [ ] **Phase 2 — Full backfill** (user dispatches in-repo agents serially through the task queue)
  - Progress: 10 / 25 work units (8 modules × type annotations + 8 × docstrings + tests + coverage guard)
- [ ] **🚦 Checkpoint β**: Phase 2 complete → user returns to home_agent for Claude to verify
- [ ] **Phase 3 — Acceptance + PR**
- [ ] **🚦 Checkpoint γ**: PR body drafting + ship handshake
- [ ] **Cleanup R.x — after PR merge**: delete mortal banner + `.refactor/` + restore canon CD default

---

## Baseline Metrics (measured at Phase 0.5 · 2026-05-11)

| Metric | Current | Target | Gap |
|--------|--------:|-------:|----:|
| pytest passed | 1605 | all green | 0 |
| pytest skipped | 3 | — | — |
| pytest warnings | 58 | (clean up as we go) | 58 |
| pytest total runtime | 75.71s | (preserve) | — |
| **coverage TOTAL** | **90%** | ≥ 90% | **0 (already meets bar)** |
| ruff (current minimal config) | 0 | 0 | 0 |
| **ruff (expanded lbg 15-select)** | **2563** | 0 | **2563** |
| - of which `D` rules (docstrings) | ~1700 | 0 | ~1700 |
| - of which `RUF001/002/003` (ambig chars) | ~347 | 0 | ~347 (may need per-file ignore for CN docstrings) |
| - of which `C901` (complexity) | 91 | 0 | 91 |
| - of which auto-fixable via `--fix` | 305 | — | auto |
| **mypy --strict** | **586** errors in **74** files (146 src files) | 0 | **586** |

**Notes**:
- Coverage already meets 90% — **Phase 2.3 backfill-tests work may be empty**, only need to keep coverage from dropping as annotations / docstrings are added.
- A few modules are under 90%: `gaia/lang/dsl/scaffold.py` (74%) / `gaia/trace/loader.py` (78%) / `gaia/lang/runtime/composition.py` (87%) / `gaia/trace/diagnostics.py` (89%) — candidates for Phase 2.3 if we choose to lift them.
- D-rules account for ~70% of ruff errors — aligns directly with "add Google docstrings" work.
- RUF001/002/003 are mostly Chinese docstrings / comments containing ambiguous unicode chars — Phase 1.1 ruff config will likely need per-file ignore or file-level `noqa`.

---

## Task Queue

### Phase 1 — Engineering baseline injection (each work unit is a single or merged commit on this branch)

- [x] **1.1** `pyproject.toml` — ruff lint full select (lbg 15 categories + mccabe 9 + Google docstrings + per-file ignores)
  - status: `done` | claimed_by: Cursor GPT-5.5 | claimed_at: 2026-05-11 23:22 | completed_at: 2026-05-11 23:25 | breakpoint_notes: Added exact 协作单 category set (`ARG, B, C4, C90, D, DTZ, E, ERA, F, I, RET, RUF, SIM, UP, W`), mccabe `max-complexity = 9`, Google pydocstyle convention, and per-file ignores for test docstrings plus intentional unicode/math text. Verification: `uv run ruff check . --select RUF001,RUF002,RUF003 --exit-zero` => All checks passed; `uv run ruff check . --statistics --exit-zero` => config parsed, 976 remaining full-select backlog items.
  - Ref: 协作单 § Must-migrate #1
- [x] **1.2** `pyproject.toml` — mypy strict block + dev extras adds mypy + types-* stubs + tests overrides
  - status: `done` | claimed_by: Cursor GPT-5.5 | claimed_at: 2026-05-11 23:48 | completed_at: 2026-05-11 23:58 | breakpoint_notes: Added `[tool.mypy]` strict config over `gaia` + `tests`, explicit missing-import overrides for untyped external/fallback modules (`opt_einsum.*`, `sympy.*`, `tomli`), and looser tests override for untyped test defs/decorators. Added dev extra deps via `uv add`: `mypy>=2.0.0` and `scipy-stubs>=1.17.1.4`; attempted `types-sympy` first, but uv confirmed no such registry package and left files unchanged. Verification: `uv sync --extra dev` => green; `uv run ruff check . --statistics --exit-zero` => config parsed, 976 remaining full-select backlog items; `uv run mypy` => config parsed with no missing-import/config errors, 1691 expected Phase 2 type errors in 134 files.
  - Ref: 协作单 § Must-migrate #2
- [x] **1.3** `pyproject.toml` — pytest addopts add `--strict-markers` + `--cov-fail-under=90`; dev extras adds pre-commit
  - status: `done` | claimed_by: Cursor GPT-5.5 | claimed_at: 2026-05-12 00:11 | completed_at: 2026-05-12 00:16 | breakpoint_notes: Added pytest `addopts` for `--strict-markers`, `--cov=gaia`, `--cov-report=term-missing`, and `--cov-fail-under=90`, so the local pytest entry point enforces the 90% coverage gate. Added `pre-commit>=4.6.0` to the dev extra via `uv add --optional dev pre-commit`, updating `uv.lock` with its transitive dependencies. Verification: `uv sync --extra dev && uv run pytest` => 1605 passed, 3 skipped, 58 warnings, TOTAL coverage 90.31%, required 90% reached; `uv run ruff check . --statistics --exit-zero` => config parsed, 976 known Phase 2 full-select backlog items; `uv run ruff format --check .` => 280 files already formatted.
  - Ref: 协作单 § Must-migrate #4
- [x] **1.4** New `.pre-commit-config.yaml` — hygiene hooks + ruff (check --fix / format) + local mypy hook + exclude `^\.refactor/` + exclude `^tmp/`
  - status: `done` | claimed_by: Cursor GPT-5.5 | claimed_at: 2026-05-12 00:20 | completed_at: 2026-05-12 00:26 | breakpoint_notes: Added `.pre-commit-config.yaml` with global excludes for `^\.refactor/` and `^tmp/`, standard hygiene hooks, `ruff-check --fix --select=E4,E7,E9,F`, `ruff-format`, and a local `uv run mypy` hook staged as `manual` until Phase 2 clears the strict type backlog. EOF / trailing-whitespace hooks are scoped away from generated storage fixtures and archival/protected docs after an initial dry run showed they would otherwise rewrite unrelated files, including protected foundations docs. Verification: `uv run pre-commit run --all-files` => all default hooks passed (merge-conflict, YAML, EOF, trailing whitespace, private-key, ruff check, ruff format).
  - Ref: 协作单 § Must-migrate #3
- [x] **1.5** `.github/workflows/ci.yml` — switch to `uv sync --extra dev` + add mypy step
  - status: `done` | claimed_by: Cursor GPT-5.5 | claimed_at: 2026-05-12 00:28 | completed_at: 2026-05-12 00:31 | breakpoint_notes: Added `astral-sh/setup-uv@v5` with cache enabled, changed CI install to `uv sync --extra dev`, routed lint/test commands through `uv run`, and added a dedicated `uv run mypy` type-check step. Verification: `uv sync --extra dev` => green; `uv run pre-commit run check-yaml --files .github/workflows/ci.yml` => passed; `uv run mypy` => command runs and reports the expected Phase 2 strict-type backlog, `1691 errors in 134 files (checked 275 source files)`.
  - Ref: 协作单 § Must-migrate #5
- [x] **1.6** New `codecov.yml` (if codecov bot is enabled; this repo currently has none, so either add one mirroring lbg-cli style or rely on the local strong gate)
  - status: `done` | claimed_by: Cursor GPT-5.5 | claimed_at: 2026-05-12 00:34 | completed_at: 2026-05-12 00:36 | breakpoint_notes: CI already uploads `coverage.xml` via `codecov/codecov-action@v5`, and the repo already had a stale `codecov.yml` with obsolete `gaia/lkm/**` ignore rules. Updated `codecov.yml` to align Codecov's project status with the local strong gate (`target: 90%`, `threshold: 0%`) while preserving the existing 80% patch target and removing nonexistent LKM/script ignores. Verification: `uv run pre-commit run check-yaml --files codecov.yml .github/workflows/ci.yml && uv run pytest --cov-report=xml tests -q -m "not integration_api"` => check-yaml passed; 1605 passed, 3 skipped, 58 warnings, TOTAL coverage 90.31%, required 90% reached; generated `coverage.xml` removed after verification.
  - Ref: 协作单 § Sundry cleanup (codecov.yml part)
- [x] **1.7** New `Makefile` — (optional) `bootstrap / lint / typecheck / test / check` targets
  - status: `done` | claimed_by: Cursor GPT-5.5 | claimed_at: 2026-05-12 00:42 | completed_at: 2026-05-12 00:46 | breakpoint_notes: Added root `Makefile` with `bootstrap`, `lint`, `typecheck`, `test`, and `check` targets. `check` intentionally follows the current Phase 1 green gate (`lint` via `pre-commit run --all-files` plus `test` via `pytest`) while `typecheck` remains available as an explicit target for the known Phase 2 strict-mypy backlog. Verification: `make check` => pre-commit hooks passed; pytest `1605 passed, 3 skipped, 58 warnings`, TOTAL coverage 90.31%; `make -n bootstrap typecheck` => dry-run printed the expected `uv sync --extra dev`, `uv run pre-commit install`, and `uv run mypy` commands.
- [x] **1.8** New `CONTRIBUTING.md` — developer local setup guide (`uv sync --extra dev` + `pre-commit install` + `make check`)
  - status: `done` | claimed_by: Cursor GPT-5.5 | claimed_at: 2026-05-12 00:50 | completed_at: 2026-05-12 00:55 | breakpoint_notes: Added root `CONTRIBUTING.md` covering local setup (`uv sync --extra dev`, `uv run pre-commit install`, `make bootstrap`), daily gate (`make check`), explicit strict-mypy target, style conventions, and v0.5 refactor boundary/doc-fidelity discipline. Verification: `make check` => pre-commit hooks passed; pytest `1605 passed, 3 skipped, 58 warnings`, TOTAL coverage 90.31%, required 90% reached.
- [x] **1.9** `CLAUDE.md` full rewrite (referencing Claude Code `/init` convention) — top mortal banner already written in Phase 0; this work unit lands the remaining sections (engineering rules + local setup + refactor boundary + doc fidelity discipline + test requirements + project overview links to README)
  - status: `done` | claimed_by: Cursor GPT-5.5 | claimed_at: 2026-05-12 00:58 | completed_at: 2026-05-12 01:02 | breakpoint_notes: Rewrote symlink-backed `CLAUDE.md` / `AGENTS.md` after the existing mortal banner using the Claude Code `/init` convention: project map, local setup, quality gates, v0.5 refactor workflow, engineering rules, code style, doc fidelity, foundations layering, protected layers, documentation policy, script logging, and git/worktree rules. Removed the standalone frozen Skills section while preserving a concise instruction to use matching repo skills when the environment exposes them. Verification: `uv sync --extra dev && make check` => sync green; pre-commit all hooks passed; pytest `1605 passed, 3 skipped, 58 warnings`, TOTAL coverage 90.31%, required 90% reached.
  - Ref: 协作单 § CLAUDE.md engineering upgrade

> **Phase 1 done when**: all 9 items `done` + `uv sync --extra dev` + `pre-commit run --all-files` is green (note: at this point mypy strict and full-select ruff will both still fire many errors; the pre-commit config is intentionally permissive on these during Phase 1 — see 1.4 / 1.9 design).

> **🚦 Checkpoint α — after Phase 1**: user brings STATE.md + actual config back to home_agent; Claude verifies config sanity + reviews Phase 2 task queue.

### Phase 2 — Full backfill (serial agent relay through the task queue; each work unit ≈ 1 module / 1 agent run)

#### 2.1 Type annotations until `mypy --strict` is clean (ordering: leaves first, dependents later)

- [x] **2.1-top** gaia top-level files (`__init__.py`, `constants.py`, `stats.py`, `unit.py`) — small, independent, leaf-level
  - status: `done` | claimed_by: Cursor GPT-5.5 | claimed_at: 2026-05-12 01:04 | completed_at: 2026-05-12 01:08 | breakpoint_notes: Added strict-compatible Pint quantity annotations in `gaia/unit.py` while preserving the public `Quantity = ureg.Quantity` runtime alias; narrowed `gaia/stats.py:_spec` to the existing `DistributionKind` literal union so `DistributionLiteral.kind` type-checks. Verification: `uv run mypy --follow-imports=skip gaia/__init__.py gaia/constants.py gaia/stats.py gaia/unit.py` => success for 4 top-level files; `uv run mypy gaia/__init__.py gaia/constants.py gaia/stats.py gaia/unit.py` now reports only the pre-existing imported `gaia/ir/formalize.py` backlog (74 errors), not top-level file errors; `uv run pre-commit run --all-files` => passed; `uv run pytest` => 1605 passed, 3 skipped, 58 warnings, TOTAL coverage 90.32%, required 90% reached.
- [x] **2.1-logic** `gaia/logic/` (2 .py files, small)
  - status: `done` | claimed_by: Cursor GPT-5.5 | claimed_at: 2026-05-12 01:10 | completed_at: 2026-05-12 01:14 | breakpoint_notes: Existing `gaia/logic/` annotations were already strict-clean for the scoped type unit, so no code edits were needed. Verification: `uv run mypy --follow-imports=skip gaia/logic` => success for 2 source files; `uv run mypy gaia/logic` => only pre-existing imported `gaia/ir/formalize.py` backlog (74 errors), not logic-file errors; `uv run pytest tests/gaia/logic/test_propositional.py --no-cov` => 5 passed, 13 warnings; `uv run pre-commit run --all-files` => passed; `uv run pytest` => 1605 passed, 3 skipped, 58 warnings, TOTAL coverage 90.32%, required 90% reached.
- [x] **2.1-ir** `gaia/ir/` (IR primitives — re-read `doc-fidelity-baseline.md` § Protected layers + § Core invariants before touching)
  - status: `done` | claimed_by: Cursor GPT-5.5 | claimed_at: 2026-05-12 01:16 | completed_at: 2026-05-12 01:22 | breakpoint_notes: Added strict-compatible annotations and local type narrowing in `gaia/ir/formalize.py`, `gaia/ir/coarsen.py`, `gaia/ir/linearize.py`, and `gaia/ir/validator.py` without changing IR schemas, public signatures, or validation semantics. `formalize.py` now uses private helpers to express generated-ID invariants and enum coercion to mypy; `coarsen.py`/`linearize.py` now use concrete generic dict/tuple annotations; `validator.py` avoids loop-variable type reuse that confused strict mypy. Verification: `uv run mypy --follow-imports=silent gaia/ir` => success for 13 source files; `uv run pytest tests/ir tests/gaia/ir/test_review.py --no-cov` => 245 passed; `uv run pre-commit run --all-files` => passed; `uv run pytest` => 1605 passed, 3 skipped, 58 warnings, TOTAL coverage 90.32%, required 90% reached.
- [x] **2.1-bp** `gaia/bp/` (BP algorithm — re-read `doc-fidelity-baseline.md` § BP semantics before touching)
  - status: `done` | claimed_by: Cursor GPT-5.5 | claimed_at: 2026-05-12 01:23 | completed_at: 2026-05-12 01:29 | breakpoint_notes: Added strict-compatible annotations and local type narrowing across BP inference, contraction, exact enumeration, lowering, junction-tree, GBP, and engine modules without changing message-passing algorithms or potential-function semantics. Verification: `uv run mypy gaia/bp` => success for 10 source files; `uv run pytest tests/gaia/bp tests/test_lowering.py tests/test_contraction.py tests/test_bp_jaynes_contract.py --no-cov` => 211 passed; `uv run pre-commit run --all-files` => passed; `uv run pytest` => 1605 passed, 3 skipped, 58 warnings, TOTAL coverage 90.30%, required 90% reached.
- [x] **2.1-lang** `gaia/lang/` (DSL — large module with sub-dirs: dsl/, formula/, refs/, review/, runtime/, types/)
  - status: `done` | claimed_by: Cursor GPT-5.5 | claimed_at: 2026-05-12 09:18 | completed_at: 2026-05-12 09:34 | breakpoint_notes: Added strict-compatible annotations and local type narrowing across Gaia Lang runtime, DSL helpers, compiler lowering, formula lowering, and Bayes lowering without changing documented DSL/API signatures or emitted IR semantics. Runtime string fields are now narrowed to IR enum types at construction boundaries; generated strategy/operator IDs are checked before storing in action/strategy maps. Verification: `uv run mypy gaia/lang --show-error-codes --no-pretty` => success for 60 source files; `uv run pytest tests/gaia/lang --no-cov` => 477 passed; `uv run pre-commit run --all-files` => passed after ruff-format reformatted one touched file and the hook was rerun; `uv run pytest` => 1605 passed, 3 skipped, 58 warnings, TOTAL coverage 90.30%, required 90% reached.
- [x] **2.1-trace** `gaia/trace/`
  - status: `done` | claimed_by: Cursor GPT-5.5 | claimed_at: 2026-05-12 09:31 | completed_at: 2026-05-12 09:34 | breakpoint_notes: Added strict-compatible annotations and type narrowing in `gaia/trace/loader.py`, `gaia/trace/ranking.py`, and `gaia/trace/review.py` without changing trace schema, diagnostic ordering, review rendering, or snapshot behavior. Shared inquiry `Diagnostic.kind` remains runtime-compatible with trace-specific diagnostic strings; review aggregation now narrows that value through a local helper for mypy only. Verification: `uv run mypy --follow-imports=silent gaia/trace --show-error-codes --no-pretty` => success for 9 source files; `uv run mypy gaia/trace --show-error-codes --no-pretty` => remaining errors are imported pending `gaia/inquiry`/`gaia/cli` backlog only, no `gaia/trace/*` errors; `uv run pytest tests/trace --no-cov` => 92 passed; `uv run pre-commit run --all-files` => passed; `uv run pytest` => 1605 passed, 3 skipped, 58 warnings, TOTAL coverage 90.30%, required 90% reached.
- [x] **2.1-inquiry** `gaia/inquiry/`
  - status: `done` | claimed_by: Cursor GPT-5.5 | claimed_at: 2026-05-12 09:35 | completed_at: 2026-05-12 09:39 | breakpoint_notes: Added strict-compatible annotations and type narrowing across inquiry diagnostics, semantic diffing, focus resolution, proof context, rendering, review orchestration, and snapshot helpers without changing inquiry review semantics, snapshot schema, diagnostic ordering, or CLI-visible output. Verification: `uv run mypy --follow-imports=silent gaia/inquiry --show-error-codes --no-pretty` => success for 11 source files; `uv run mypy gaia/inquiry --show-error-codes --no-pretty` => remaining errors are imported pending `gaia/cli` backlog only, no `gaia/inquiry/*` errors; `uv run pytest tests/inquiry tests/cli/test_inquiry.py --no-cov` => 144 passed, 42 warnings; `uv run pre-commit run --all-files` => passed after ruff-format reformatted one touched file and the hook was rerun; `uv run pytest` => 1605 passed, 3 skipped, 58 warnings, TOTAL coverage 90.29%, required 90% reached.
- [x] **2.1-cli** `gaia/cli/` (CLI entry — re-read `doc-fidelity-baseline.md` § Behavior contracts before touching)
  - status: `done` | claimed_by: Cursor GPT-5.5 | claimed_at: 2026-05-12 09:40 | completed_at: 2026-05-12 09:48 | breakpoint_notes: Added strict-compatible annotations and local type narrowing across CLI package loading, command helpers, renderers, quality gates, review manifest loading, starmap replay builders, and register/infer/add command internals without changing command names, arguments, output formats, artifact schemas, or CLI behavior. A non-silent CLI mypy run surfaced one imported `gaia/ir/coarsen.py` cache annotation issue; fixed it as a type-only compatibility annotation for `StrategyCptCacheValue`. Verification: `uv run mypy gaia/cli --show-error-codes --no-pretty` => success for 37 source files; `uv run mypy gaia --show-error-codes --no-pretty` => success for 146 source files; `uv run pytest tests/cli --no-cov` => 414 passed, 3 skipped, 3 warnings; `uv run pre-commit run --all-files` => passed; `uv run pytest` => 1605 passed, 3 skipped, 58 warnings, TOTAL coverage 90.29%, required 90% reached.
- [x] **2.1-tests** `tests/` — full
  - status: `done` | claimed_by: Cursor GPT-5.5 | claimed_at: 2026-05-12 09:50 | completed_at: 2026-05-12 09:55 | breakpoint_notes: Corrected the tests mypy override so the non-package `tests/` tree is handled as `tests.*` via `explicit_package_bases = true`, then scoped the remaining test-only relaxations to JSON-shaped fixtures, invalid-input negative tests, deprecated-path ignores, and widened diagnostic string assertions. No production APIs, CLI behavior, IR schemas, DSL names, or BP algorithms changed. Verification: `uv run mypy tests --show-error-codes --no-pretty` => success for 129 source files; `uv run mypy gaia tests --show-error-codes --no-pretty` => success for 275 source files; `uv run mypy` => success for 275 source files; `uv run pre-commit run --all-files` => passed; `uv run pytest` => 1605 passed, 3 skipped, 58 warnings, TOTAL coverage 90.29%, required 90% reached.

> 2.1 done when: `mypy --strict gaia/ tests/` reports 0 errors (tests are allowed some D-class relaxation via overrides).

#### 2.2 Google docstrings until `ruff D` is clean (same ordering as 2.1)

- [x] **2.2-top** gaia top-level files (`__init__.py`, `constants.py`, `stats.py`, `unit.py`)
  - status: `done` | claimed_by: Cursor GPT-5.5 | claimed_at: 2026-05-12 09:58 | completed_at: 2026-05-12 10:00 | breakpoint_notes: Added the package docstring for `gaia/__init__.py` and Google-style docstrings for the public distribution literal factories in `gaia/stats.py`. No behavior, API, IR, DSL, CLI, or algorithm changes made. Verification: `uv run ruff check gaia/__init__.py gaia/constants.py gaia/stats.py gaia/unit.py --select D` => passed; `uv run mypy gaia/__init__.py gaia/constants.py gaia/stats.py gaia/unit.py --show-error-codes --no-pretty` => success for 4 source files; `uv run ruff check . --select D --statistics --exit-zero` => 451 expected remaining Phase 2.2 docstring errors outside this unit; `uv run pre-commit run --all-files` => passed; `uv run pytest` => 1605 passed, 3 skipped, 58 warnings, TOTAL coverage 90.29%, required 90% reached.
- [ ] **2.2-logic** | [ ] **2.2-ir** | [ ] **2.2-bp** | [ ] **2.2-lang** | [ ] **2.2-trace** | [ ] **2.2-inquiry** | [ ] **2.2-cli** | [ ] **2.2-tests**
  - Each work unit uses the same field shape as 2.1 (status / claimed_by / claimed_at / completed_at / breakpoint_notes).
  - Brief shared across all: docstring content must **strictly match** what `docs/foundations/**` describes; empty docstrings must be filled with concrete content; no paraphrasing that adds new meaning; CN-language docstrings will trip RUF001/002/003 — handle per ruff config.

> 2.2 done when: `ruff check . --select D` reports 0 errors (tests may have `D100-D107` allowed via per-file ignore).

#### 2.3 Coverage guard (baseline already at 90% — only act if annotations/docstrings drag coverage below the bar)

- [ ] **2.3-monitor** Run `pytest --cov=gaia --cov-report=term` after each work unit. If TOTAL drops below 90%, add tests under that work unit to bring it back.
  - status: `pending` | breakpoint_notes: This is an ongoing monitor, not a single agent run.

> 2.3 done when: `pytest --cov-fail-under=90` is green.

#### 2.4 Full close-out acceptance gate

- [ ] **2.4** Full run: `pre-commit run --all-files` + `pytest --cov` + `mypy --strict` — all green, coverage ≥ 90%.
  - status: `pending` | breakpoint_notes: —

> **🚦 Checkpoint β — after Phase 2**: user returns to home_agent so Claude can verify (sampled doc fidelity cross-check + acceptance gate all green).

### Phase 3 — Acceptance + PR

- [ ] **3.1** Run the full acceptance gate one more time.
- [ ] **3.2** 🚦 **Checkpoint γ**: user returns to home_agent so Claude can draft the PR body.
- [ ] **3.3** User pushes + opens PR — **requires user explicit "ship / PR" handshake**.

### Cleanup R — Triggered separately after PR merges

- [ ] **R.1** Delete the mortal banner at the top of `gaia/CLAUDE.md`.
- [ ] **R.2** Delete the `gaia/.refactor/` directory.
- [ ] **R.3** Close the 协作单; the `collaboration-mode.md` canon default (CD = Claude) auto-restores.

---

## Checkpoint History

| Checkpoint | When | Outcome | Notes |
|------------|------|---------|-------|
| Phase 0 init | 2026-05-11 | done | branch cut · mortal banner · STATE framework · baseline metrics · doc fidelity baseline · M1 doc fix |
| α (Phase 1 → 2) | (pending) | — | — |
| β (Phase 2 → 3) | (pending) | — | — |
| γ (Phase 3 PR-open) | (pending) | — | — |

---

## Doc-Code Contradiction Log

(Mirror here when an agent finds a doc-code semantic / behavioral contradiction; also notify the user so Claude can escalate to the 协作单 ❓ section.)

### M1 — `docs/foundations/gaia-ir/01-overview.md` + `06-parameterization.md` referenced stale module path `gaia/gaia_ir/...` ✅ FIXED

- **Found at**: Phase 0.2 doc fidelity baseline extraction (subagent)
- **Doc location**: `docs/foundations/gaia-ir/01-overview.md` source-layout section (7 lines) + `06-parameterization.md` source section (2 lines) referenced `gaia/gaia_ir/...`
- **Actual code location**: `gaia/ir/` (`gaia/ir/__init__.py`, etc.; user imports `from gaia.ir import ...`); live code has zero `gaia.gaia_ir` imports (grep-verified)
- **Nature**: doc-side stale wording — the code module was never named `gaia.gaia_ir`; `gaia/gaia_ir/` is leftover from an old plan (`docs/plans/2026-03-30-gaia-ir-code-alignment.md` suggests an earlier migration; `docs/plans/` is frozen by convention)
- **Resolution**: fix doc side (code is canonical) — 9 lines replaced `gaia/gaia_ir/` → `gaia/ir/`. User explicitly authorized this as a one-off exception to `CLAUDE.md § Protected Layers` ("agent forbidden to modify `docs/foundations/gaia-ir/`") because this is a path-wording fix, not an IR-definition change.
- **Status**: ✅ FIXED 2026-05-11 as a Phase 0 follow-up commit pushed to `feat/v05-quality-baseline_rsw` (`48ae1d57`).
- **Mirror source**: `.refactor/doc-fidelity-baseline.md` § 9 (risk surface) items 1 + 17 — baseline file may still list this entry; the FIXED status is canonical here.

### M2 — `StrategyType` enum inconsistency across foundations docs (mild, non-blocking)

- **Found at**: Phase 0.2
- **Inconsistency**: `gaia-ir/02-gaia-ir.md §3.3` lists `support` as a named-canonical strategy, but `gaia-ir/08-validation.md §4`'s allowed set does **not** include `support`; also `noisy_and` is marked deprecated AND allowed by the validator.
- **Resolution**: preserve the live validator's actual behavior (whatever the docs say). During the refactor, treat the IR validation tests as the source of truth.
- **Status**: non-blocking — agents encountering `support` / `noisy_and` should leave them as-is. **NOT escalated to 协作单**; logged here for agent self-check.
- **Mirror source**: `.refactor/doc-fidelity-baseline.md` § 9 risk items 2 + 16

(M3+ reserved for future agent escalations.)

---

## Quick Reference

- **协作单 decision list**: Feishu doc `AM15dZDhjooNyaxZRhNc1Sawnce` § Decision list (一·决策清单)
- **Doc fidelity baseline**: `.refactor/doc-fidelity-baseline.md` (required reading)
- **Mortal banner**: top of `CLAUDE.md`
- **Kanban entry**: `https://dptechnology.feishu.cn/wiki/IUvrwMmwliAUDukbXfUcwwxEnmf`
- **Branch**: `feat/v05-quality-baseline_rsw` (cut from `origin/v0.5` HEAD `8e8e771f`)
