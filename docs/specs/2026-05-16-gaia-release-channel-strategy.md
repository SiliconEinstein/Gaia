# Gaia Release Channel Strategy

> **Status:** Proposal
>
> **Date:** 2026-05-16
>
> **Scope:** Release channels, CI validation layers, package-corpus e2e checks, and version naming for gaia-lang.
>
> **Non-goals:** This document does not implement the workflows, publish packages, or define registry submission policy. It defines the smallest release-channel contract those implementations should satisfy.

## 1. Problem

Gaia changes in two coupled dimensions:

- Python package behavior: CLI commands, import paths, tests, packaging metadata.
- Knowledge-package semantics: DSL surface, IR shape, prior contracts, inference, and render artifacts.

A normal unit-test-only release pipeline can say the Python package imports, but it cannot prove that real Gaia knowledge packages still compile, infer, and render. The release system therefore needs two things:

1. Fast feedback for pull requests.
2. Slower channel validation that exercises real package workflows before users treat a build as usable.

## 2. Current Reality

As of this proposal:

- `Makefile` defines `test-fast`, `test-slow`, and `test-all`.
- `make test` runs the fast local slice with `pytest --no-cov -m "not slow"`.
- `make test-slow` runs tests marked `slow`, including baseline snapshots and large BP-scale tests.
- `.github/workflows/ci.yml` still runs `uv run pytest --cov-report=xml tests -v -m "not integration_api"`, so PR CI does not yet exclude `slow`.
- `integration_api` is a vestigial marker filter: it is not registered in `pyproject.toml` and has no current test uses. The PR-CI update should remove it rather than carry it forward.
- `gaia run render --target github` emits a README/wiki/data/assets bundle under `.github-output/`; it no longer needs a React/Vite GitHub Pages app.

Authoritative sources for the implementation PRs are `Makefile`, `.github/workflows/ci.yml`, `pyproject.toml`, `gaia/cli/commands/render.py`, and `gaia/cli/commands/_github.py`. The release-channel work should build from these facts rather than adding a parallel test vocabulary.

## 3. Channel Contract

Release channels are stability contracts. They should answer:

- who should install this build
- how much behavior may still change
- which validation gates passed
- which source commit produced the artifact
- which package corpus was exercised

| Channel | Version form | Trigger | Intended users | Stability contract |
|---|---|---|---|---|
| PR/dev | none | Pull request, or push to `main` / `v0.5` | Contributors | Not published; fast feedback only. |
| Nightly | `0.5.1.dev20260516` | Scheduled or manual workflow | Package authors and maintainers | Rolling snapshot; may break APIs, but must identify the exact commit and validation result. |
| Alpha | `0.5.1a1` | Manual promotion from passing nightly builds | Early adopters trying real packages | Recognized preview; APIs and semantics may still change, but known breakages must be listed. |
| Beta | `0.5.1b1` | Manual promotion after alpha feedback | Users preparing migration | Feature and semantic surface should be mostly frozen; migration docs expected. |
| Release candidate | `0.5.1rc1` | Manual promotion after beta fixes | Final validators | Only release-blocking bug fixes should land after this point. |
| Stable | `0.5.1` | Tag/release workflow | Default users and registry workflows | Default install target; must pass release validation and publish durable artifacts. |

Nightly and alpha are different:

- Nightly is an automatic timestamped snapshot.
- Alpha is a human decision that a snapshot is worth broader early testing.

## 4. CI Layers

### PR CI

PR CI should optimize for short feedback while preserving obvious correctness:

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run python scripts/check_suppression_budget.py
uv run pytest --cov-report=xml tests -v -m "not slow"
```

The important boundary is that PR CI should not silently become the release gate. It is a change detector, not a publication proof. It should still write `coverage.xml` for the existing Codecov patch signal; moving coverage to nightly-only would be a separate policy decision.

### Nightly CI

Nightly CI should run the full repository test surface and real package workflows:

```bash
make test-all
make test-slow
uv run --extra docs mkdocs build --strict
```

Then it should build and install the wheel/sdist in a fresh environment. The current runner target is `ubuntu-latest`, so the smoke example below uses POSIX paths:

```bash
uv build
python -m venv /tmp/gaia-wheel-smoke
/tmp/gaia-wheel-smoke/bin/pip install dist/*.whl
/tmp/gaia-wheel-smoke/bin/gaia --help
```

Exact commands can be adjusted by workflow implementation, but the contract is: test source, test built artifacts, and test the installed CLI.

### Release CI

Release CI should be nightly CI plus publishing checks:

- version is valid PEP 440
- changelog/release notes exist
- docs build
- package corpus e2e passes
- artifacts include source commit and channel metadata
- publishing target matches the channel

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

`gaia --version` should expose enough provenance to reproduce the build:

```text
gaia-lang 0.5.1.dev20260516
channel: nightly
commit: <git sha>
ir_schema: <TBD; see §9>
```

The same metadata should be written into nightly/release manifests so a package-corpus failure can be traced to a commit.

## 7. Promotion Rules

Promotion should be explicit:

1. Merge PRs after PR CI.
2. Nightly runs on the active release branch, currently `v0.5`.
3. Promote to alpha only after nightly passes repository tests, wheel smoke, docs build, and package corpus e2e.
4. Promote to beta only after alpha feedback has no known semantic blockers.
5. Promote to rc only after the behavior and migration docs are frozen.
6. Promote to stable only after rc validation passes without release-blocking changes.

The point is not ceremony. The point is to avoid calling a build stable before real Gaia packages have exercised the language, IR, inference, and render paths together.

## 8. Minimal Implementation Plan

1. Update PR CI to use the fast marker expression while preserving coverage output:

   ```bash
   uv run pytest --cov-report=xml tests -v -m "not slow"
   ```

2. Add a scheduled `nightly.yml` that runs:

   - lint/type/suppression checks
   - `make test-all`
   - `make test-slow`
   - docs build
   - wheel/sdist build
   - fresh-install CLI smoke
   - package corpus e2e

3. Add a package-corpus runner script so workflow YAML stays thin.

4. Add reproducibility metadata to `gaia --version`: `channel`, `commit`, and the final `ir_schema` string once §9 is resolved.

5. Add manual release workflows for alpha, beta, rc, and stable promotion.

## 9. Open Questions

- Should nightly artifacts publish to PyPI pre-release immediately, or begin as GitHub Actions artifacts / GitHub pre-releases only?
- Which large scientific package should join the initial corpus once the two bundled examples are green?
- Which registry packages form the initial compatibility corpus?
- Should package-corpus failures block nightly artifact upload, or publish artifacts with a red compatibility manifest?
- What is the canonical IR schema version string exposed by `gaia --version`?
- Should nightly cover only Python 3.12, or both 3.12 and 3.13?
- Are older pre-release channels retained after a later pre-release is promoted, or superseded and removed?
