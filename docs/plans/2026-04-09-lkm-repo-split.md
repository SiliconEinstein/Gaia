# LKM Repo Split — Migration Plan

**Status:** Proposal
**Date:** 2026-04-09
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
- **Not** rewriting existing commit messages or squashing history.
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
| `scripts/` (LKM-specific) | Audit individually |
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

**Recommendation: A.** Set up `gaia-lang` as installable package (private PyPI or git+ URL in `pyproject.toml`). Initial pin: `gaia-lang==0.2.1` (current version). Gaia IR contract changes must bump the version.

**Action before migration:** Verify `gaia.lang`, `gaia.ir`, `gaia.bp` are cleanly installable as a package (no hidden cross-imports into `gaia.lkm`). This is a prerequisite gate.

## Phased Execution

### Phase 0 — Prep (Week 0)

1. **Alignment meeting**: Confirm boundary with all stakeholders. Capture decisions inline in this doc.
2. **Contract option decision**: A / B / C (recommended A).
3. **Audit cross-imports**: Grep `gaia.lkm` imports in `gaia.lang/ir/bp` and vice versa. Any unexpected coupling must be resolved first.
   ```bash
   grep -r "from gaia.lkm" gaia/lang/ gaia/ir/ gaia/bp/ cli/
   grep -r "from gaia\.\(lang\|ir\|bp\)" gaia/lkm/
   ```
4. **Package publish dry-run** (if Option A): `uv build` on `gaia-lang` subset, verify it imports standalone.
5. **Freeze `gaia/lkm/` new feature merges** for Phase 1 dry run (~2 days).

### Phase 1 — Dry Run (Week 1)

Goal: verify the extraction mechanics on a throwaway copy without touching real infrastructure.

1. Clone a sacrificial copy:
   ```bash
   git clone --no-local https://github.com/SiliconEinstein/Gaia.git /tmp/gaia-lkm-dryrun
   cd /tmp/gaia-lkm-dryrun
   ```
2. Run `git filter-repo` to keep only LKM-relevant paths:
   ```bash
   git filter-repo \
     --path gaia/lkm/ \
     --path tests/gaia/lkm/ \
     --path docs/foundations/lkm/ \
     --path docs/specs/2026-03-31-m8-api.md \
     --path docs/plans/2026-04-03-import-pipeline-hardening.md \
     --path frontend/ \
     --path scripts/dedupe-s3-lance.py
   ```
3. **Verification checklist:**
   - [ ] `git log --oneline | wc -l` — commit count reasonable (expect hundreds, not thousands)
   - [ ] Random spot-check 5 commits — messages, authors, timestamps preserved
   - [ ] `ls -la` — only intended files present, no stray leftovers
   - [ ] No broken cross-references: `grep -r "gaia/lang" gaia/lkm/ docs/` (should be 0 results or only in docstrings)
4. Craft new `pyproject.toml`:
   - Package name: `gaia-lkm`
   - Dependencies: `lancedb`, `neo4j`, `fastapi`, `uvicorn`, `pydantic-settings`, `gaia-lang>=0.2.1`
   - Remove: `typer`, `litellm`, `httpx` (unless LKM needs them)
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

Atomic switchover, minimize divergence window.

1. **Freeze window start**: Announce to team. No merges to `gaia/lkm/` in `Gaia` until switchover complete.
2. **Re-run `git filter-repo`** on a fresh clone (not the dry-run copy — it's contaminated by manual fixes).
3. **Push to new repo:**
   ```bash
   git remote set-url origin git@github.com:SiliconEinstein/gaia-lkm.git
   git push origin main
   ```
4. **Apply the manual adjustments** from Phase 1 (`pyproject.toml`, `CLAUDE.md`, `.github/workflows/`, etc.) as the first commit on the new repo. Message: `chore: initial repo setup after split from SiliconEinstein/Gaia`.
5. **Verify CI green** in new repo.
6. **In `Gaia`**: delete `gaia/lkm/`, `tests/gaia/lkm/`, `docs/foundations/lkm/`, `frontend/` in a single PR titled `chore: remove LKM code — migrated to gaia-lkm`. Leave a `MIGRATION.md` at repo root pointing to the new location.
7. **Update cross-refs:**
   - `Gaia/README.md` — mention the split
   - `Gaia/docs/foundations/README.md` — remove LKM pointer or link to new repo
   - `gaia-lkm/README.md` — pointer back for historical context
8. **Freeze window end**: merge both PRs (`Gaia` deletion + `gaia-lkm` setup). Unfreeze development.

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
| Hidden `gaia.lkm` → `gaia.lang/ir/bp` coupling breaks install | Dry run fails | Phase 0 step 3 — explicit grep audit before any migration |
| `git filter-repo` mangles merge commits | Lose merge context | Accept — commit messages and authors preserved, merge structure is cosmetic |
| `gaia-lang` package publish lag blocks new repo | New repo can't install | Phase 0 prerequisite — publish succeeds before Phase 1 |
| PR #297/#311/… references break in docs | Broken links | Phase 5 link audit, use fully qualified `SiliconEinstein/Gaia#297` format everywhere |
| Team confusion about where to file new PRs | Fragmented work | Pinned issue + README callout in both repos for 1 month |
| `.worktrees/` in-progress work lost | Developer friction | Announce freeze window 48h in advance, developers land or stash WIP |
| Codecov coverage baseline resets | Lose historical comparison | Accept — fresh project, document cutover date |
| CI token rotation needed | CI fails immediately post-cutover | Pre-provision `CODECOV_TOKEN` etc. in new repo before cutover |

## Open Questions

1. **Package registry**: PyPI public, or internal? (Affects install URL and auth.)
2. **Does `gaia-lkm` ever need to modify `gaia.ir/`?** If yes, contributor flow needs cross-repo PRs. If no, it's strictly a consumer.
3. **Frontend hosting**: does it deploy from new repo, or separately? Confirm build/deploy pipeline ownership.
4. **`docs/specs/`**: which specs belong to which repo? Need a full audit.
5. **`docs/plans/`**: which plans belong to which? Same.
6. **Shared `.claude/skills/`**: should there be a meta-repo that both pull from, or do we duplicate and accept drift?

## Decision Log

- [ ] Shared contract strategy: A / B / C (decided on ____ by ____)
- [ ] Package registry: PyPI / internal / git+ URL (decided on ____ by ____)
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
