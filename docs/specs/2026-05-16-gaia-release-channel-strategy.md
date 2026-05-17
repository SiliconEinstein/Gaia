# Gaia Release Channel Strategy

> **Status:** Implemented (PR #620, merged 2026-05-16; follow-up fixes per chenkun review in subsequent PR).
>
> **Date:** 2026-05-16
>
> **Last updated:** 2026-05-16 (post-implementation amend per chenkun review on PR #620).
>
> **Scope:** Release channels, CI validation layers, package-corpus e2e checks, and version naming for gaia-lang.
>
> **Non-goals:** This document does not define registry submission policy. It records the release-channel contract that the workflows under `.github/workflows/` and `.github/actions/` actually enforce.

## 1. Problem

Gaia changes in two coupled dimensions:

- Python package behavior: CLI commands, import paths, tests, packaging metadata.
- Knowledge-package semantics: DSL surface, IR shape, prior contracts, inference, and render artifacts.

A normal unit-test-only release pipeline can say the Python package imports, but it cannot prove that real Gaia knowledge packages still compile, infer, and render. The release system therefore needs two things:

1. Fast feedback for pull requests.
2. Slower channel validation that exercises real package workflows before users treat a build as usable.

## 2. Current Reality

As implemented in PR #620:

- `Makefile` defines `test-fast`, `test-slow`, and `test-all`.
- `make test` runs the fast local slice with `pytest --no-cov -m "not slow"`.
- `make test-slow` runs tests marked `slow`, including baseline snapshots and large BP-scale tests.
- `.github/workflows/ci.yml` (PR CI) runs `uv run pytest -n auto tests/baseline tests/cli -v -m "not slow"` — a deliberate narrowing to the regression-gold (`tests/baseline`) and CLI E2E (`tests/cli`) slices, optimized for short PR feedback. PR CI does not write `coverage.xml` and does not upload to Codecov; the full repository test surface runs under nightly via `make test-all`.
- `integration_api` was a vestigial marker filter and has been dropped from PR CI.
- Codecov was retired entirely (no `--cov-report=xml`, no Codecov action). Codecov GitHub App was removed as a required check. See §4 PR CI for the rationale (PR CI is a change detector, not a coverage gate).
- `gaia run render --target github` emits a README/wiki/data/assets bundle under `.github-output/`; it no longer needs a React/Vite GitHub Pages app.

Authoritative sources are `Makefile`, `.github/workflows/ci.yml`, `.github/workflows/nightly.yml`, `.github/actions/release/action.yml`, `.github/actions/wheel-smoke/action.yml`, `pyproject.toml`, `gaia/cli/commands/render.py`, and `gaia/cli/commands/_github.py`.

## 3. Channel Contract

Release channels are stability contracts. They should answer:

- who should install this build
- how much behavior may still change
- which validation gates passed
- which source commit produced the artifact
- which package corpus was exercised

| Channel | Version form | Trigger | Intended users | Stability contract |
|---|---|---|---|---|
| PR/dev | none | Pull request to `main` / `v0.5`, or push to `main` / `v0.5`; also `workflow_dispatch` | Contributors | Not published; fast feedback only. |
| Nightly | `0.5.1.dev20260516` | Scheduled daily at 20:00 UTC (04:00 Asia/Shanghai next day) via `schedule`, plus on-demand via `workflow_dispatch`; runs against the default branch (`v0.5`) tip (see §9 Q-schedule) | Package authors and maintainers | Rolling snapshot; may break APIs, but must identify the exact commit and validation result. |
| Alpha | `0.5.1a1` | Manual `workflow_dispatch` of `release-alpha.yml` (post-nightly green) | Early adopters trying real packages | Recognized preview; APIs and semantics may still change, but known breakages must be listed. |
| Beta | `0.5.1b1` | Manual `workflow_dispatch` of `release-beta.yml` (post-alpha) | Users preparing migration | Feature and semantic surface should be mostly frozen; migration docs expected. |
| Release candidate | `0.5.1rc1` | Manual `workflow_dispatch` of `release-rc.yml` (post-beta) | Final validators | Only release-blocking bug fixes should land after this point. |
| Stable | `0.5.1` | Manual `workflow_dispatch` of `release-stable.yml` (post-rc) | Default users and registry workflows | Default install target; must pass release validation and publish durable artifacts. |

Nightly and alpha are different:

- Nightly is a timestamped snapshot of the active branch (runs daily at 20:00 UTC via `schedule`, plus operator-initiated `workflow_dispatch`).
- Alpha is a human decision that a snapshot is worth broader early testing.

## 4. CI Layers

### PR CI

PR CI optimizes for short feedback while preserving obvious correctness. The implemented form (`.github/workflows/ci.yml`) is:

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run python scripts/check_suppression_budget.py
uv run pytest -n auto tests/baseline tests/cli -v -m "not slow"
```

It also invokes the wheel-smoke composite (`./.github/actions/wheel-smoke`) on every PR.

The important boundary is that PR CI is not the release gate. It is a change detector, not a publication proof. Policy decision (made during PR #620 review): Codecov was retired entirely — PR CI no longer writes `coverage.xml`, the Codecov GitHub App was removed as a required check, and coverage-as-a-policy-signal is not currently enforced anywhere. The full repository test surface (including `tests/eval`, `tests/integration`, etc., and slow-marked tests) runs under nightly CI.

### Nightly CI

Nightly CI (`.github/workflows/nightly.yml`) runs the full repository test surface and real package workflows. It runs daily at 20:00 UTC (04:00 Asia/Shanghai next day) via `schedule`, plus on-demand via `workflow_dispatch` — see §3 and §9. Steps:

```bash
# Lint, type-check, suppression budget (mirrors PR CI)
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run python scripts/check_suppression_budget.py

# Full test surface
make test-all                            # includes slow tests via pytest's no-marker default
uv run --extra docs mkdocs build --strict

# Build + smoke
# (wheel-smoke composite handles `uv build` + fresh-venv pip-install + `gaia --help` + L2 facade imports)

# Package corpus e2e
uv run python scripts/run_package_corpus.py
```

It also bumps `pyproject.toml` (transiently) to `0.5.1.dev<YYYYMMDD>`, injects `_build_info.py` (CHANNEL=nightly, COMMIT=<sha>), and uploads the wheel/sdist as a GHA artifact gated on corpus success. The corpus runner is the artifact-upload gate per R1 dispatch lock: a red corpus blocks artifact upload.

### Release CI

Release CI is nightly CI plus publishing checks, factored into a composite action (`.github/actions/release/action.yml`) invoked by four manual caller workflows (`release-alpha.yml`, `release-beta.yml`, `release-rc.yml`, `release-stable.yml`). The composite enforces the six release invariants:

| Invariant | Enforcement |
|---|---|
| Version is valid PEP 440 | Caller workflow passes the version string into `inputs.version`; the composite asserts the post-`sed` `pyproject.toml` line matches exactly via `grep -q`, and additionally asserts `gaia --version` reports the same version string (defense-in-depth against a busted `_build_info.py` or version-injection bug). |
| Changelog / release notes exist | For stable, `gh release create --generate-notes` auto-generates release notes from merged PRs. The release does not currently consume a curated `CHANGELOG.md` — the auto-generated notes are the chosen approach (see §9). |
| Docs build | `uv run --extra docs mkdocs build --strict` runs as a release gate before publish. |
| Package corpus e2e passes | `uv run python scripts/run_package_corpus.py` runs as a release gate before publish. |
| Artifacts include source commit and channel metadata | `_build_info.py` injection writes `CHANNEL` + `COMMIT`; `gaia --version` exposes both (asserted). |
| Publishing target matches the channel | Caller workflow drives `inputs.channel`; only `do_git_tag=true` (stable) triggers `git tag` + `gh release create`. All four callers use the same OIDC trusted-publishing target on PyPI. |

The composite also runs `make test-all` as a release gate alongside docs build and corpus runner. Gates run in both dry-run and non-dry-run modes — dry-run skips publish/tag/release, but the validation gates are themselves the pipeline being verified, so they always run.

## 5. Package Corpus E2E

Nightly, alpha, beta, rc, and stable validation should include real packages, not only unit tests.

Minimum corpus:

| Package | Purpose |
|---|---|
| `examples/galileo-v0-5-gaia` | Small tutorial package and baseline authoring path. |
| `examples/mendel-v0-5-gaia` | Multi-claim example with current v0.5 authoring patterns. |
| Selected registry packages | Compatibility signal for published package authors. |

For each package, the e2e command sequence should be:

```bash
gaia build compile <pkg>
gaia build check <pkg>
gaia build check --gate <pkg>
gaia run infer <pkg>
gaia run render <pkg> --target docs
gaia run render <pkg> --target github
gaia run render <pkg> --target obsidian
```

The GitHub render check should assert the current publication-bundle contract:

- `.github-output/README.md` exists and is non-empty
- `.github-output/wiki/Home.md` exists and is non-empty
- `.github-output/docs/public/data/graph.json` exists and is non-empty
- `.github-output/docs/public/data/meta.json` exists and is valid JSON
- `.github-output/docs/public/data/beliefs.json` exists after running `infer` and then `render --target github`
- `.github-output/docs/package.json` does not exist
- `.github-output/docs/src` does not exist

## 6. Version And Metadata

Use one package name, `gaia-lang`, with PEP 440 versions:

```text
0.5.1.dev20260516
0.5.1a1
0.5.1b1
0.5.1rc1
0.5.1
```

`gaia --version` exposes enough provenance to reproduce the build:

```text
gaia-lang 0.5.1.dev20260516
channel: nightly
commit: <git sha>
ir_schema: ir-v1+<12-hex-digest>
```

The `ir_schema` field uses the `ir-vN+<12-hex>` double-write form (a stable major version `vN` plus a snapshot-hash short digest); the digest auto-bumps when the IR schema changes via the `scripts/check_ir_schema_bump.py` pre-push gate against `gaia/_meta.py`. See `gaia/_meta.py` for the live value and the bump mechanism. (§9 Q5 — resolved.)

The same metadata is written into nightly/release manifests so a package-corpus failure can be traced to a commit.

## 7. Promotion Rules

Promotion should be explicit:

1. Merge PRs after PR CI.
2. Nightly runs on the active release branch, currently `v0.5`.
3. Promote to alpha only after nightly passes repository tests, wheel smoke, docs build, and package corpus e2e.
4. Promote to beta only after alpha feedback has no known semantic blockers.
5. Promote to rc only after the behavior and migration docs are frozen.
6. Promote to stable only after rc validation passes without release-blocking changes.

The point is not ceremony. The point is to avoid calling a build stable before real Gaia packages have exercised the language, IR, inference, and render paths together.

## 8. Implementation (landed)

PR #620 (merged 2026-05-16) landed the implementation; this section records what was built rather than what should be built.

1. PR CI (`.github/workflows/ci.yml`) was narrowed to the regression-gold + CLI E2E slices:

   ```bash
   uv run pytest -n auto tests/baseline tests/cli -v -m "not slow"
   ```

   Codecov was retired entirely (no `--cov-report=xml`, no Codecov upload, Codecov GitHub App removed as a required check).

2. `nightly.yml` was added with a daily `schedule` cron (`0 20 * * *` = 20:00 UTC = 04:00 Asia/Shanghai next day) plus `workflow_dispatch`, running:

   - lint / type / suppression checks
   - `make test-all` (the `test-all` target already covers slow tests, so `test-slow` is not a separate step — running both would double-count the slow suite)
   - `uv run --extra docs mkdocs build --strict`
   - wheel-smoke composite (build + fresh-venv install + `gaia --help` + L2 facade imports)
   - `scripts/run_package_corpus.py` (artifact-upload gate)
   - GHA artifact upload (gated on corpus success)

3. `scripts/run_package_corpus.py` keeps the corpus runner thin in workflow YAML.

4. `gaia --version` reports `channel`, `commit`, and `ir_schema` (the `ir-vN+<12-hex>` form, see §6).

5. Four manual caller workflows (`release-alpha.yml`, `release-beta.yml`, `release-rc.yml`, `release-stable.yml`) all invoke `.github/actions/release/action.yml` (composite). The composite enforces version assertion (sed + grep-q), `_build_info.py` injection, `gaia --version` channel + version asserts, `uv build`, wheel-smoke, `make test-all`, docs strict build, package corpus e2e, then conditional PyPI publish / git tag / GH release.

## 9. Open Questions (resolved at implementation time)

- **Q1. Should nightly artifacts publish to PyPI pre-release immediately, or begin as GitHub Actions artifacts / GitHub pre-releases only?**
  Resolved: GHA artifacts only (R2 dispatch lock). PyPI / GitHub pre-release publishing is reserved for the manual release workflows (alpha/beta/rc/stable). Operators can download a nightly artifact from a green run without touching PyPI.

- **Q2. Which large scientific package should join the initial corpus once the two bundled examples are green?**
  Deferred. The initial corpus is `examples/galileo-v0-5-gaia` and `examples/mendel-v0-5-gaia`. Adding a registry/scientific package is Stage 7 territory and out of scope for PR #620.

- **Q3. Which registry packages form the initial compatibility corpus?**
  Deferred — same as Q2.

- **Q4. Should package-corpus failures block nightly artifact upload, or publish artifacts with a red compatibility manifest?**
  Resolved: block. `nightly.yml` gates the artifact-upload step on `steps.corpus.outcome == 'success'` (R1 dispatch lock). No red-compatibility-manifest mode.

- **Q5. What is the canonical IR schema version string exposed by `gaia --version`?**
  Resolved: `ir-vN+<12-hex-digest>` (the "double-write" form — stable major `vN` plus a snapshot-hash short digest). Auto-bumped by `scripts/check_ir_schema_bump.py` as a pre-push gate against `gaia/_meta.py`. See §6.

- **Q6. Should nightly cover only Python 3.12, or both 3.12 and 3.13?**
  Resolved: Python 3.12 only (single-entry matrix, R1 dispatch lock). The matrix entry is preserved so adding 3.13 later is a one-line edit, not a workflow restructure.

- **Q7. Are older pre-release channels retained after a later pre-release is promoted, or superseded and removed?**
  Deferred. No registry-level cleanup policy is enforced yet; pre-releases coexist on PyPI until explicitly yanked.

- **Q-codecov (added 2026-05-16, resolved).** Codecov was discussed during the PR-CI narrowing decision. Resolution: Codecov retired entirely — no `--cov-report=xml`, no Codecov upload step, Codecov GitHub App removed as a required check. PR CI is positioned as a change detector, not a coverage gate; the policy is "if we want coverage, it lives under nightly, not on PR latency".

- **Q-schedule (added 2026-05-16, resolved 2026-05-17).** Whether nightly should run on a schedule cron. Resolution: daily `schedule` cron at `0 20 * * *` (20:00 UTC = 04:00 Asia/Shanghai next day) plus `workflow_dispatch` for on-demand runs. Earlier resolution was `workflow_dispatch`-only — that was reconsidered post-#620: a daily auto-run surfaces fixture / corpus regressions on the README badge without requiring an operator to remember to dispatch. Note: while the galileo fixture `--gate` is red, scheduled runs will fail at the corpus runner step (blocking artifact upload by design); this noise is accepted as a daily reminder that the fixture review is pending.
