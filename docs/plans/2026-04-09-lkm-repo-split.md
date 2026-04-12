# LKM Repo Split — Migration Plan

**Status:** In progress — Phase 1-2 done, Phase 3 pending
**Date:** 2026-04-09
**Last updated:** 2026-04-12
**Owner:** TBD

## Motivation

Gaia currently holds two logically distinct surfaces in one repository:

1. **Authoring / IR / BP core** — `gaia.lang`, `gaia.ir`, `gaia.bp`, CLI, theory and Gaia-IR contract docs. Small, stable, contract-driven.
2. **LKM server** — `gaia.lkm.*`, storage backends (LanceDB / Neo4j), ingest pipelines, curation, frontend, ops scripts. Large, fast-moving, infra-heavy.

The two have different audiences, different dependencies (lancedb/neo4j/fastapi vs typer/litellm), different iteration cadence, and different review gates. Splitting them lets the LKM team iterate without touching the protected `gaia-ir/` contract layer, and keeps the authoring repo small and focused.

Target end state:

```
SiliconEinstein/Gaia        (renamed or unchanged)
  ├── gaia/lang/            ← Python DSL
  ├── gaia/ir/              ← Gaia IR models (single source of truth)
  ├── gaia/bp/              ← BP algorithm
  ├── docs/foundations/{theory,ecosystem,gaia-ir,gaia-lang,bp,review,cli}/
  └── Publishes `gaia-lang` package (version-pinned contract)

SiliconEinstein/gaia-lkm    (new)
  ├── gaia/lkm/             ← LKM server
  ├── frontend/             ← React browser
  ├── docs/foundations/lkm/
  ├── docs/specs/           ← M1–M8 specs
  └── Depends on `gaia-lang>=X.Y` via pip
```

## Non-Goals

- **Not** merging any GitHub PRs/issues into the new repo. History references only.
- **Not** changing the Gaia IR contract during the split. Contract freeze.
- **Not** preserving commit history in the new repo. Fresh start, clean `initial commit`. Historical context via PR archive markdown + links to `SiliconEinstein/Gaia` commits.
- **Not** moving `.env` secrets via git. Each repo gets its own `.env.example`.

## Boundary Decisions

### Migrate to `gaia-lkm`

| Path | Rationale |
|------|-----------|
| `gaia/lkm/` | Core LKM code |
| `tests/gaia/lkm/` | Unit + integration tests for LKM |
| `docs/foundations/lkm/` | LKM design docs (7 files restored in #311) |
| `docs/specs/2026-03-31-m8-api.md` | M8 API spec |
| `docs/specs/` (LKM-related) | Audit individually — most belong to LKM |
| `docs/plans/2026-04-03-import-pipeline-hardening.md` | LKM pipeline plan |
| `frontend/` | Only consumer today is LKM API |
| `scripts/dedupe-s3-lance.py` | LKM ops |
| `scripts/migrate_lance_to_bytehouse.py` | LKM backfill (imports `gaia.lkm.storage`) |
| `scripts/dump_lance_to_local.py` | LKM lance snapshot (imports `gaia.lkm.storage`) |
| `scripts/run_full_discovery.py` | LKM embedding + clustering pipeline |
| `scripts/try_discovery.py` | LKM discovery experiment |
| `scripts/build_lance_indexes.py` | LKM storage ops |
| `.github/workflows/ci.yml` (LKM jobs) | Will be split |

### Stay in `Gaia`

| Path | Rationale |
|------|-----------|
| `gaia/lang/`, `gaia/ir/`, `gaia/bp/` | Core language + IR + BP |
| `libs/typst/` | Typst DSL runtime |
| `cli/` | Local CLI |
| `docs/foundations/{theory,ecosystem,gaia-ir,gaia-lang,bp,review,cli}/` | Authoring docs |
| `tests/gaia/{lang,ir,bp}/`, `tests/cli/` | Core tests |
| `docs/archive/` | Historical docs |

### Shared Contract Strategy

**Decision required before migration starts.** Three options:

| Option | Pros | Cons |
|--------|------|------|
| **A. Publish `gaia-lang` as package** | Clean dependency, versioned, semver enforces contract discipline | Needs publish workflow, PyPI or internal registry, release cadence |
| **B. Git submodule** | Easy sync, no publish overhead | Painful DX (checkout, update, worktree interaction), contract drift still possible |
| **C. Vendored copy + sync script** | Dead simple | Contract silently drifts, merge conflicts, anti-pattern |

**Recommendation: A.** Set up `gaia-lang` as installable package (private PyPI or git+ URL in `pyproject.toml`). Initial pin: `gaia-lang==0.3.0` (current version on PyPI). Gaia IR contract changes must bump the version.

**Action before migration:** ~~Verify `gaia.lang`, `gaia.ir`, `gaia.bp` are cleanly installable as a package (no hidden cross-imports into `gaia.lkm`).~~ **✅ Done.** `gaia-lang` v0.3.0 is already published on PyPI and pip-installable. Cross-import audit confirms clean separation (see below).

### Cross-Repo Doc References

**Decision: Option B — pinned-tag GitHub URLs.** No docs site infrastructure in the initial split. Defer mkdocs/Sphinx to a later phase if doc volume justifies it.

Rationale: Sphinx's `intersphinx` is the only tool that gives true build-time verification of cross-repo references, but it requires both sides to be Sphinx projects. mkdocs has no equivalent. Since markdown + external links is the lowest-friction path and doc volume is modest, we accept manual URL maintenance in exchange for zero infrastructure.

**Conventions in `gaia-lkm` docs:**

1. **Pin cross-repo links to the same tag as `gaia-lang` dependency.** If `pyproject.toml` has `gaia-lang==0.2.1`, all upstream doc URLs must use `...Gaia/blob/v0.2.1/...` (not `main`).

2. **Use reference-style links at the top of each doc** to centralize URLs:
   ```markdown
   [gaia-ir]: https://github.com/SiliconEinstein/Gaia/tree/v0.2.1/docs/foundations/gaia-ir
   [factor-nodes]: https://github.com/SiliconEinstein/Gaia/blob/v0.2.1/docs/foundations/gaia-ir/factor-nodes.md
   [bp-potentials]: https://github.com/SiliconEinstein/Gaia/blob/v0.2.1/docs/foundations/bp/potentials.md

   LKM stores [FactorNode instances][factor-nodes] in LanceDB...
   ```

3. **Central upstream index** at `gaia-lkm/docs/upstream-contract.md` listing every referenced upstream doc with its pinned URL and a one-line description. Single source of truth for "what contracts does LKM depend on." Upgrade flow edits this file + `pyproject.toml` in lockstep.

4. **Bump script** `scripts/bump-gaia-lang.sh` does a simple sed replace across all docs when upgrading:
   ```bash
   #!/bin/bash
   OLD=$1
   NEW=$2
   find docs -name '*.md' -exec sed -i '' "s|Gaia/blob/v${OLD}/|Gaia/blob/v${NEW}/|g" {} +
   find docs -name '*.md' -exec sed -i '' "s|Gaia/tree/v${OLD}/|Gaia/tree/v${NEW}/|g" {} +
   sed -i '' "s|gaia-lang==${OLD}|gaia-lang==${NEW}|g" pyproject.toml
   ```

5. **CI link checker** catches drift:
   ```yaml
   # .github/workflows/ci.yml
   - name: Check doc links
     run: npx markdown-link-check docs/**/*.md --config .linkcheck.json
   ```
   Config ignores rate-limited hosts and localhost.

**Reverse direction (Gaia → gaia-lkm)**: Gaia rarely references LKM (LKM is a consumer, not a contract provider). When it does (e.g., ecosystem docs citing LKM as reference implementation), use `main` branch URLs — Gaia does not depend on LKM versions, so drift is acceptable.

**Revisit criteria:** Switch to a docs site (mkdocs-material recommended) if any of these become true:
- Cross-repo reference count exceeds ~30 (manual maintenance burden)
- End users want unified search across both projects
- Team wants versioned docs accessible without navigating raw GitHub
- API reference (autodoc) becomes worth investing in

## Execution Progress (2026-04-12)

| Phase | Status | Notes |
|-------|--------|-------|
| Phase 0 — Prep | ✅ Done | Cross-import audit passed (0 reverse deps, 6 forward type-only). `gaia-lang` v0.3.0 on PyPI. All decisions made. |
| Phase 1 — Dry Run | ✅ Done | Files copied to `~/Projects/gaia-lkm`, `uv sync` + `pytest` 223 passed. |
| Phase 2 — Infrastructure | ✅ Done | Repo: `SiliconEinstein/gaia-lkm`. CI green. CLAUDE.md + 17 skills + `.env.example`. |
| Phase 3 — Cutover | ⏳ Pending | `gaia-lkm` initial commit pushed with 321 files. **Not yet done:** delete LKM code from Gaia, add MIGRATION.md. Waiting for ByteHouse Phase 4 validation first. |
| Phase 4 — History Archive | ⏳ Pending | PR archive not yet exported. |
| Phase 5 — Cleanup | ⏳ Pending | |

### What's in `gaia-lkm` now

- **Repo:** https://github.com/SiliconEinstein/gaia-lkm
- **Files:** 321 (code + tests + fixtures + docs + skills)
- **Tests:** 223 passed, 11 skipped (Neo4j-dependent)
- **CI:** GitHub Actions green (lint + test + coverage)
- **Commits:** 3 (initial commit, claude setup, ci workflow)

### What's blocking Phase 3 cutover (deleting from Gaia)

ByteHouse migration Phase 3B (full backfill) is blocked on Volces team optimizing the table creation strategy. Until the LKM is verified end-to-end on ByteHouse (Phase 4: embedding pipeline), we keep the code in both repos to avoid breaking anything.

**Sequence:** ByteHouse Phase 4 verified → delete LKM from Gaia → Phase 4 history archive → done.

See `gaia-lkm/docs/plans/2026-04-12-bytehouse-migration-status.md` for detailed ByteHouse migration status.

---

## Phased Execution

### Phase 0 — Prep (Week 0)

1. **Alignment meeting**: Confirm boundary with all stakeholders. Capture decisions inline in this doc.
2. **Contract option decision**: A / B / C (recommended A).
3. ~~**Audit cross-imports**~~ **✅ Completed 2026-04-12.** See results below.
4. ~~**Package publish dry-run**~~ **✅ Done.** `gaia-lang` v0.3.0 is on PyPI and pip-installable.
5. **Freeze `gaia/lkm/` new feature merges** for Phase 1 dry run (~2 days).

#### Cross-Import Audit Results (2026-04-12)

**Conclusion: `gaia.lkm` and `gaia.lang/ir/bp` are cleanly separable. No refactoring needed.**

**Reverse dependencies (should be zero — core must not know about LKM):**

| Direction | Result |
|-----------|--------|
| `gaia.lang/ir/bp/cli/review` → `gaia.lkm` | **0 imports** ✅ |
| `libs/` → `gaia.lkm` | **0 imports** ✅ |
| `services/` → `gaia.lkm` | **0 imports** ✅ |
| `tests/gaia/{lang,ir,bp}` → `gaia.lkm` | **0 imports** ✅ |

**Forward dependencies (LKM consuming core — expected and acceptable):**

| File | Imports | Purpose |
|------|---------|---------|
| `gaia/lkm/core/lower.py` | `gaia.ir.graphs.LocalCanonicalGraph`, `gaia.ir.knowledge.Knowledge`, `gaia.ir.operator.Operator`, `gaia.ir.strategy.Strategy` | Lowering: converts Gaia IR graph → LKM internal models |
| `gaia/lkm/pipelines/lower.py` | `gaia.ir.graphs.LocalCanonicalGraph` | Pipeline entry point calls lower |
| `gaia/lkm/scripts/ingest.py` | `gaia.ir.graphs.LocalCanonicalGraph` | CLI ingest script |

All 6 imports are **type definitions only** (Pydantic models), not runtime functions. All concentrated in the lowering boundary layer. After split, these resolve via `gaia-lang>=0.3.0` pip dependency — zero code changes needed.

**Other clean boundaries confirmed:**

| Direction | Result |
|-----------|--------|
| `gaia.lkm` → `libs/` | **0 imports** ✅ |
| `gaia.lkm` → `services/` | **0 imports** ✅ |
| `frontend/` → Python | **0 imports** ✅ (pure React, API only) |

**Scripts audit (all → gaia-lkm):**

| Script | Dependency |
|--------|-----------|
| `scripts/migrate_lance_to_bytehouse.py` | `gaia.lkm.storage` |
| `scripts/dump_lance_to_local.py` | `gaia.lkm.storage` |
| `scripts/run_full_discovery.py` | `gaia.lkm.pipelines` |
| `scripts/try_discovery.py` | `gaia.lkm.models`, `gaia.lkm.core`, `gaia.lkm.storage` |
| `scripts/build_lance_indexes.py` | `gaia.lkm.storage` |
| `scripts/dedupe-s3-lance.py` | `gaia.lkm` (ops) |

### Phase 1 — Dry Run (Week 1)

Goal: verify the new repo structure works standalone, without touching real infrastructure.

> **History decision (2026-04-12):** No commit history preservation. The new repo starts with a clean `initial commit` containing the current state of all migrated files. Historical context is preserved via PR archive markdown (Phase 4) and links back to `SiliconEinstein/Gaia`. This eliminates `git filter-repo` complexity, commit hash breakage, and PR reference rewriting.

1. Create a local dry-run directory with only the migrated files:
   ```bash
   mkdir /tmp/gaia-lkm-dryrun && cd /tmp/gaia-lkm-dryrun
   git init

   # Copy migrated paths from Gaia
   GAIA=~/Projects/Gaia
   cp -r $GAIA/gaia/lkm/ gaia/lkm/
   cp -r $GAIA/tests/gaia/lkm/ tests/gaia/lkm/
   cp -r $GAIA/docs/foundations/lkm/ docs/foundations/lkm/
   cp -r $GAIA/frontend/ frontend/
   # Scripts (audited list)
   mkdir -p scripts
   for f in migrate_lance_to_bytehouse.py dump_lance_to_local.py \
            run_full_discovery.py try_discovery.py build_lance_indexes.py \
            dedupe-s3-lance.py; do
     cp $GAIA/scripts/$f scripts/ 2>/dev/null
   done
   # docs/specs — LKM-related (audit individually)
   ```
2. **Verification checklist:**
   - [ ] `ls -la` — only intended files present, no stray leftovers
   - [ ] No broken cross-references: `grep -r "gaia/lang" gaia/lkm/ docs/` (should be 0 or only in docstrings/type annotations)
   - [ ] No imports of `libs/` or `services/` from `gaia/lkm/`
3. Craft new `pyproject.toml`:
   - Package name: `gaia-lkm`
   - Dependencies: `lancedb`, `neo4j`, `fastapi`, `uvicorn`, `pydantic-settings`, `gaia-lang>=0.3.0`
   - Remove: `typer` (unless LKM needs it; `litellm` and `httpx` likely still needed)
5. Install and test:
   ```bash
   uv sync
   pytest
   ```
6. **Stop signal**: if tests fail because of implicit imports from `gaia.lang/ir/bp`, go back to Phase 0 step 3 — the coupling is not cleanly separable yet.

### Phase 2 — Infrastructure Setup (Week 1-2)

Parallel to Phase 1 dry run verification.

1. **Create new GitHub repo** `SiliconEinstein/gaia-lkm` (empty, private at first).
2. **Configure repo settings:**
   - Branch protection on `main` (require PR, CI green, review)
   - GitHub Actions enabled
   - Codecov integration (new project token)
   - Secrets: `CODECOV_TOKEN`, any deploy credentials
3. **CI workflow**: copy `.github/workflows/ci.yml`, strip Typst/CLI steps, keep Neo4j service container and pytest + coverage.
4. **Claude Code config** (in the new repo root):
   - `CLAUDE.md` — rewrite, LKM-focused. Drop Gaia Lang v4 DSL section. Keep Workflow, Skills, LLM API, Implementation Rules, Protected Layers (gaia-ir/ rules still apply via the `gaia-lang` dep).
   - `.claude/skills/` — copy general-purpose skills (`writing-plans`, `executing-plans`, `verification-before-completion`, `pr-review`, `finishing-a-development-branch`, `test-driven-development`, `systematic-debugging`, `receiving-code-review`, `requesting-code-review`, `using-superpowers`, `subagent-driven-development`). Drop `gaia-ir-authoring`, `paper-formalization` (stay in Gaia).
   - `.claude/settings.json` — copy hooks, adjust paths if any reference `/Users/dp/Projects/Gaia`.
5. **Worktree layout**: mirror `.worktrees/` convention in new repo.
6. **`.env.example`**: populate with LKM-specific vars only (LKM_*, TOS_*, LKM_NEO4J_*, BYTEHOUSE_*).

### Phase 3 — Cutover (Week 2)

Atomic switchover, minimize divergence window. No history preservation — clean initial commit.

1. **Freeze window start**: Announce to team. No merges to `gaia/lkm/` in `Gaia` until switchover complete.
2. **Copy current files to new repo** (same process as Phase 1, but on the real repo):
   ```bash
   cd /path/to/gaia-lkm
   # Copy files from Gaia (latest main) into the new repo structure
   # Same file list as Phase 1 dry run
   git add -A
   git commit -m "feat: initial commit — LKM server split from SiliconEinstein/Gaia

   Migrated from SiliconEinstein/Gaia as of commit $(git -C $GAIA rev-parse HEAD).
   See docs/archive/gaia-pr-history.md for historical PR context."
   git push origin main
   ```
3. **Apply infrastructure config** (`pyproject.toml`, `CLAUDE.md`, `.github/workflows/`, `.env.example`) as a follow-up commit.
4. **Verify CI green** in new repo.
5. **In `Gaia`**: delete `gaia/lkm/`, `tests/gaia/lkm/`, `docs/foundations/lkm/`, `frontend/`, migrated scripts in a single PR titled `chore: remove LKM code — migrated to gaia-lkm`. Leave a `MIGRATION.md` at repo root pointing to the new location.
6. **Update cross-refs:**
   - `Gaia/README.md` — mention the split
   - `Gaia/docs/foundations/README.md` — remove LKM pointer or link to new repo
   - `gaia-lkm/README.md` — pointer back for historical context
7. **Freeze window end**: merge both PRs (`Gaia` deletion + `gaia-lkm` setup). Unfreeze development.

### Phase 4 — History Archive (Week 3)

PR / issue history stays in `Gaia` by default. Two deliverables to avoid lost context:

1. **Export PR archive**: Script that pulls PR list + bodies for all LKM-touching PRs:
   ```bash
   gh pr list --repo SiliconEinstein/Gaia --state all --limit 500 \
     --search "gaia/lkm/ OR frontend/ OR docs/foundations/lkm/" \
     --json number,title,body,author,mergedAt,url > lkm-pr-archive.json
   ```
2. **Commit as markdown** to `gaia-lkm/docs/archive/gaia-pr-history.md` — human-readable table with PR numbers, titles, authors, dates, links to original repo.

Alternative (heavier): use a tool like `github-migration-tool` to re-create issues. Not recommended — adds noise, references break.

### Phase 5 — Cleanup (Week 3-4)

1. Update all internal documentation links.
2. Update `~/.claude/projects/-Users-dp-Projects-gaia-lkm/memory/MEMORY.md` with copies of relevant entries from current Gaia memory (`project_lkm_rebuild.md`, `project_m6_embedding_bytehouse.md`, all `feedback_*.md` except Gaia-specific ones).
3. Remove stale worktrees referencing LKM work in old repo.
4. Notify team in a pinned issue.

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| ~~Hidden `gaia.lkm` → `gaia.lang/ir/bp` coupling breaks install~~ | ~~Dry run fails~~ | **✅ Mitigated.** Cross-import audit (2026-04-12) confirmed 0 reverse deps. Only 6 forward type-only imports in `lower.py`. |
| ~~`git filter-repo` mangles merge commits~~ | ~~Lose merge context~~ | **✅ Eliminated.** Decision: no history preservation, clean initial commit. |
| ~~`gaia-lang` package publish lag blocks new repo~~ | ~~New repo can't install~~ | **✅ Mitigated.** `gaia-lang` v0.3.0 already on PyPI. |
| PR #297/#311/… references break in docs | Broken links | Phase 5 link audit, use fully qualified `SiliconEinstein/Gaia#297` format everywhere |
| Team confusion about where to file new PRs | Fragmented work | Pinned issue + README callout in both repos for 1 month |
| `.worktrees/` in-progress work lost | Developer friction | Announce freeze window 48h in advance, developers land or stash WIP |
| Codecov coverage baseline resets | Lose historical comparison | Accept — fresh project, document cutover date |
| CI token rotation needed | CI fails immediately post-cutover | Pre-provision `CODECOV_TOKEN` etc. in new repo before cutover |

## Open Questions

1. ~~**Package registry**: PyPI public, or internal?~~ **Resolved.** `gaia-lang` v0.3.0 already on public PyPI.
2. ~~**Does `gaia-lkm` ever need to modify `gaia.ir/`?**~~ **Resolved: No.** Cross-import audit (2026-04-12) confirms LKM only imports `gaia.ir` type definitions (Pydantic models). LKM is strictly a consumer. If IR changes are needed, they go through a PR on Gaia → release new `gaia-lang` version → `gaia-lkm` bumps dependency.
3. ~~**Frontend hosting**~~ **Resolved: entirely LKM-owned.** Frontend deploys from `gaia-lkm` repo. Build/deploy pipeline moves with it.
4. ~~**`docs/specs/`**: which specs belong to which repo?~~ **✅ Audited 2026-04-12.** See appendix below.
5. ~~**`docs/plans/`**: which plans belong to which?~~ **✅ Audited 2026-04-12.** See appendix below.
6. ~~**Shared `.claude/skills/`**~~ **Resolved: duplicate and accept drift.** Skills are config files, not code. Maintenance burden is negligible.

## Decision Log

- [x] **Shared contract strategy: Option A — `gaia-lang` pip package** (decided 2026-04-12; `gaia-lang` v0.3.0 already on PyPI; cross-import audit confirms clean separation)
- [x] **Cross-repo doc references: Option B — pinned-tag GitHub URLs** (decided 2026-04-09, defer docs site until volume justifies it)
- [x] **Package registry: public PyPI** (decided 2026-04-12; `gaia-lang` already published there)
- [x] **Commit history: not preserved** (decided 2026-04-12; clean initial commit, PR archive for context)
- [x] **Cross-import audit: passed** (2026-04-12; 0 reverse deps, 6 forward deps all type-only in `lower.py`)
- [x] **`.claude/skills/`: duplicate** (decided 2026-04-12; copy general-purpose skills, accept drift)
- [ ] Freeze window dates: ____ to ____
- [ ] New repo name: `gaia-lkm` / other: ____

## Success Criteria

Migration is complete when:

- [ ] `gaia-lkm` repo exists, CI green, all 447+ tests passing
- [ ] `gaia-lkm` installable via `uv sync` with `gaia-lang` dependency resolved
- [ ] `Gaia` repo `gaia/lkm/` removed, CI green
- [ ] PR archive markdown committed to `gaia-lkm/docs/archive/`
- [ ] Claude Code memory + config ported to new repo path
- [ ] No broken cross-references in docs (verified by link checker)
- [ ] Team notified, onboarding docs updated

---

## Appendix: docs/specs/ and docs/plans/ Ownership Audit (2026-04-12)

101 files classified. Summary: **54 Gaia, 43 gaia-lkm, 3 shared, 1 archive.**

### docs/specs/ → gaia-lkm (16 files)

| File | Topic |
|------|-------|
| `2026-03-14-v2-database-visualization-design.md` | React frontend browser |
| `2026-03-17-curation-service-design.md` | Curation service |
| `2026-03-17-simplified-global-canonicalization-design.md` | Global canonicalization (M5) |
| `2026-03-19-curation-batch-pipeline-design.md` | Curation batch pipeline |
| `2026-03-25-lkm-minimal-pipeline-spec.md` | LKM end-to-end pipeline |
| `2026-03-31-lkm-master-plan.md` | LKM overall plan |
| `2026-03-31-m1-data-models.md` | M1 data models |
| `2026-03-31-m2-storage.md` | M2 storage layer |
| `2026-03-31-m3-pipeline-a.md` | M3 lowering pipeline |
| `2026-03-31-m4-pipeline-b.md` | M4 paper extraction |
| `2026-03-31-m5-integrate.md` | M5 global integration |
| `2026-03-31-m6-curation.md` | M6 curation discovery |
| `2026-03-31-m7-global-bp.md` | M7 global BP inference |
| `2026-03-31-m8-api.md` | M8 API server |
| `2026-04-04-m6-semantic-discovery.md` | M6 embedding + clustering |
| `2026-04-04-m6c-graph-health.md` | M6c conflict detection |
| `2026-04-04-relation-analysis.md` | M6b relation analysis |
| `2026-04-07-m6-scaling-semantic-clustering.md` | M6 scaling to 100M+ |

### docs/specs/ → Gaia (27 files)

| File | Topic |
|------|-------|
| `2026-03-16-noisy-and-leak-unified-factor-design.md` | Unified factor theory |
| `2026-03-19-typst-graph-ir-compiler-design.md` | Typst → Graph IR compiler |
| `2026-03-20-typst-dsl-v4-design.md` | Gaia Lang v4 |
| `2026-03-25-gaia-lang-alignment-design.md` | Lang alignment |
| `2026-03-25-theory-restructuring-design.md` | Theory restructuring |
| `2026-03-26-graph-ir-restructuring-design.md` | IR restructuring |
| `2026-03-26-theory-docs-restructuring-design.md` | Theory docs |
| `2026-03-27-entailment-silence-analysis.md` | Entailment analysis |
| `2026-03-28-package-management-design.md` | Package management |
| `2026-04-02-gaia-lang-v5-python-dsl-design.md` | Gaia Lang v5 Python DSL |
| `2026-04-02-gaia-registry-design.md` | Registry design |
| `2026-04-03-gaia-init-add-registry-ci-design.md` | CLI init/add + registry CI |
| `2026-04-03-gaia-lang-cli-docs-rewrite-design.md` | Lang + CLI docs rewrite |
| `2026-04-03-gaia-lang-future-extensions-design.md` | DSL future extensions |
| `2026-04-04-compile-readme-design.md` | compile --readme |
| `2026-04-04-module-narrative-design.md` | Module narrative |
| `2026-04-05-dsl-v6-support-witness-api-design.md` | v6 support/witness API |
| `2026-04-05-dsl-v6-support-witness-design.md` | v6 support/witness |
| `2026-04-05-gaia-layer-existing-python-packages-design.md` | Python package wrapping |
| `2026-04-05-induction-strategy-design.md` | Induction strategy |
| `2026-04-06-github-presentation-design.md` | GitHub presentation |
| `2026-04-06-operator-strategy-redesign.md` | Operator redesign |
| `2026-04-08-gaia-lang-hole-fills-design.md` | Hole/fills DSL |
| `2026-04-08-gaia-package-hole-bridge-design.md` | Package hole/bridge |
| `2026-04-08-registry-hole-bridge-index-design.md` | Registry hole index |
| `2026-04-09-references-and-at-syntax.md` | @ reference syntax |
| `2026-04-10-obsidian-wiki-backend.md` | Obsidian wiki backend |

### docs/specs/ → shared / archive

| File | Owner | Topic |
|------|-------|-------|
| `2026-03-29-decentralized-architecture-redesign.md` | shared | Ecosystem architecture |
| `2026-04-05-dsl-v6-curry-howard-design.md` | archive | Superseded draft |

### docs/plans/ → gaia-lkm (25 files)

| File | Topic |
|------|-------|
| `2026-03-10-storage-v2-design.md` | V2 storage layer |
| `2026-03-10-storage-v2-chunk1–4.md` (4 files) | Storage v2 implementation chunks |
| `2026-03-10-cli-pipeline-convergence-design.md` | CLI → LKM pipeline |
| `2026-03-11-cli-pipeline-convergence-impl.md` | Pipeline impl |
| `2026-03-11-publish-state-machine.md` | Publish state machine |
| `2026-03-11-storage-v2-chunk5-design.md` + `chunk5.md` | StorageManager facade |
| `2026-03-12-storage-v2-package-knowledge-versioning-design.md` (+zh) | Package versioning |
| `2026-03-12-server-v2-commit-review-merge.md` | Server commit/merge |
| `2026-03-12-v2-e2e-paper-ingest.md` | E2E paper ingest |
| `2026-03-13-storage-v2-graph-ir.md` | Graph IR in storage |
| `2026-03-14-v2-database-visualization.md` | Frontend browser |
| `2026-03-17-curation-service.md` | Curation service |
| `2026-03-17-simplified-global-canonicalization.md` | Canonicalization |
| `2026-03-18-abstraction-agent.md` | Abstraction agent |
| `2026-03-19-factor-type-cleanup-gate-removal.md` | Factor type cleanup |
| `2026-03-20-full-pipeline-100-papers.md` | 100-paper pipeline |
| `2026-03-20-unified-graph-viewer.md` | Unified graph viewer |
| `2026-03-21-multi-step-chains.md` | Multi-step chains |
| `2026-03-25-lkm-minimal-pipeline.md` | LKM minimal pipeline |
| `2026-04-01-lkm-development-roadmap.md` | LKM M1–M8 roadmap |
| `2026-04-01-m1-lkm-data-models.md` | M1 impl |
| `2026-04-01-m2-lkm-storage.md` | M2 impl |
| `2026-04-03-import-pipeline-hardening.md` | Import pipeline |
| `2026-04-04-m6-semantic-discovery.md` | M6 discovery |
| `2026-04-09-bytehouse-as-primary-store.md` | ByteHouse migration |

### docs/plans/ → Gaia (27 files)

All theory restructuring, IR design, DSL v2–v5, QID identity, registry, CLI, package management, presentation plans. (Omitted for brevity — mirror of the specs Gaia list.)

### docs/plans/ → shared

| File | Topic |
|------|-------|
| `2026-03-11-review-pipeline-design.md` | Review pipeline (CLI + LKM) |
| `2026-03-29-decentralized-architecture-rewrite.md` | Ecosystem architecture |
| `2026-04-09-lkm-repo-split.md` | This plan (stays in both or Gaia) |
