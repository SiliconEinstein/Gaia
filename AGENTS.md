# Contributor and Agent Guide

Canonical operating guide for both human contributors and in-repo agents (Claude Code,
Cursor, Codex, etc.). `CLAUDE.md` is a symlink to this file so Claude Code auto-loads it;
`CONTRIBUTING.md` is a stub pointer. Edit this file directly — never the symlink, never
duplicate guidance into `CONTRIBUTING.md`. For product overview, architecture, CLI, and
DSL reference, start with `README.md` and then `docs/foundations/`.

## Local Setup

Use `uv` for all dependency management. Do not install repo dependencies with `pip`.

```bash
make bootstrap
```

`make bootstrap` runs `uv sync --extra dev`, enables `extensions.worktreeConfig`, installs
all three hook stages (`pre-commit`, `pre-push`, `commit-msg`) into the worktree-local
`.githooks/` directory, and sets `core.hooksPath` per worktree.

Hooks live in `<worktree>/.githooks/` rather than the shared `.git/hooks/`, and the
convention applies whether or not you use additional worktrees. In a
bare-hub-with-worktrees setup `.git/hooks/` is shared across every worktree while
`pre-commit install` stubs hardcode the installing worktree's `.venv/bin/python` —
per-worktree `.githooks/` makes each worktree's hooks point at its own venv. Existing
contributors migrate by re-running `make bootstrap`; the target is idempotent.

## Quality Gates

Local hooks split work across three stages:

- **pre-commit** (per commit, fast): hygiene hooks (trailing whitespace / EOF newline /
  merge-conflict / detect-private-key), `ruff check` narrow select + `--fix`,
  `ruff format`, `mypy --strict`, and the `CLAUDE.md` symlink check.
- **commit-msg** (per commit): `commitizen` validates the message against Conventional
  Commits. Merge and revert commits are exempt by commitizen defaults.
- **pre-push** (per push, CI-byte-aligned): `ruff check .` full 15-cat select,
  `ruff format --check .`, the `ir-schema` bump check, and
  `pytest -n auto -v -m "pr_gate and not slow"`, plus the symlink and suppression-budget
  checks again. `mypy --strict` runs at pre-commit and CI carries it as the push-time
  backstop.

Ad-hoc:

```bash
make check       # pre-commit (all files) + full pytest suite, parallel via pytest-xdist
make lint        # pre-commit over all files
make test        # fast pytest slice (-m "not slow"), parallel, no coverage
make typecheck   # strict mypy over gaia and tests
```

The PR-CI test gate runs the `pr_gate` slice at the two call sites that matter — the CI
workflow's `Run tests` step (`.github/workflows/ci.yml`) and the pre-push `pytest` hook.
The broader test suite runs in nightly via `make test-all`, so regressions outside the
narrowed slice still surface within ~24h. Coverage is no longer a gate anywhere; opt-in
ad-hoc via `pytest --cov=gaia`.

### Test placement and PR-CI marker

PR-CI gate uses the `pr_gate` pytest marker:

```bash
pytest -n auto -m "pr_gate and not slow"
```

Where new tests go:

- **Place by module structure**: tests for `gaia/foo/` go to `tests/foo/` (preferred) or
  `tests/unit/` (for tightly-scoped unit tests of `gaia/foo/`).
- **`tests/baseline/`** is the regression gold standard — a frozen surface; new tests
  there require maintainer review.
- **`tests/cli/`** is for CLI E2E user-facing entry-point tests.

Whether to add `@pytest.mark.pr_gate`:

- **Yes**: test catches user-facing regression (CLI behavior change, baseline contract
  drift, public API break).
- **No**: test is internal contract / unit / fixture — nightly's `make test-all` catches
  drift within 24h.

The marker can apply per-test or per-file (module-level
`pytestmark = pytest.mark.pr_gate`). Judgment call belongs to the PR author and reviewer.

### Push pre-flight

**Do not bypass the pre-push hook** with `--no-verify` or any other hook-skip flag. If the
hook fails, fix the underlying issue and create a new commit. Bypassing produces silent
drift between local and CI state and defeats the entire point of byte-aligning the gates.
Applies equally to in-repo agents.

### CLAUDE.md ↔ AGENTS.md sync

`CLAUDE.md` is a symlink to `AGENTS.md`; pre-commit + pre-push both verify the relationship.
Editing `AGENTS.md` is the canonical action.

## Commits

This repo uses **Conventional Commits**: `<type>(<scope>): <imperative summary>`. Allowed
`<type>` values: `feat`, `fix`, `docs`, `refactor`, `chore`, `test`, `style`, `perf`,
`build`, `ci`. `<scope>` is free-form lower-kebab (e.g. `bp`, `cli`, `gaia-ir`). Subject
≤ 72 characters, no trailing period. Use the body for context, motivation, and
breaking-change notes (`BREAKING CHANGE: …`).

Enforcement is two-sided: the local `commit-msg` hook runs `commitizen` on every commit,
and a CI job runs `cz check` over every commit in a PR. Merge and revert commits are
exempt by commitizen defaults.

## Code Style

Machine-enforced style (Python target, ruff line length, mccabe complexity, mypy
strictness) lives in `pyproject.toml`. The conventions below are not lint-enforced — they
live here so reviewers and agents apply them consistently:

- Use PEP 604 annotations: `X | None`, not `Optional[X]`; `list[X]`, not `List[X]`.
- Use Google-style docstrings for new or touched public modules, classes, and functions.
- Use Pydantic v2 APIs: `.model_dump()`, `.model_validate()`, `.model_validate_json()`.
- Keep Typer command docstrings concise because they can affect `--help` output.

## Git and Worktrees

Work in a branch or isolated worktree unless the user explicitly asks otherwise.
Worktrees live under `.worktrees/<slug>`, which is gitignored:

```bash
git worktree add .worktrees/<slug> -b feature/<slug>
```

After `git worktree add`, run `git config --worktree core.bare false` before `git status`
works — `git worktree add` does not set this automatically when the parent is a bare hub,
and `git status` will fail with "fatal: this operation must be run in a work tree" until
the override is applied.

Never use destructive git commands, force-push shared branches, or revert user changes
unless the user explicitly requests it.

### Branch naming

| Prefix | Use |
|--------|-----|
| `feature/<description>` | Feature development and bug fixes targeting `main` |
| `refactor/<description>` | Refactoring with no behaviour change |
| `hotfix/<description>` | Patch branches that target a `release/0.N.x` branch |
| `docs/<description>` | Documentation-only changes |
| `rfc/<description>` | Design proposals and specs |
| `codex/<description>` | AI agent branches (created automatically by Codex/Claude/Cursor) |

All branches merge into `main` via PR, except `hotfix/*` branches which target
the relevant `release/0.N.x` branch.

### Release branches

A `release/0.N.x` branch is created once per minor series when the RC phase
begins. It is never merged back into `main`. The full policy is in
`docs/releases/branch-strategy.md`; the short rules for contributors are:

- **Alpha and beta** releases are dispatched from `main`. No release branch
  exists yet.
- **RC and stable** releases are dispatched from `release/0.N.x`.
- **Hotfixes** on a released minor go to `release/0.N.x` via a `hotfix/*` PR,
  then cherry-picked back to `main`:

  ```bash
  # Fix goes to the release branch first
  git checkout -b hotfix/fix-foo release/0.5.x
  # ... commit the fix ...
  # Open PR targeting release/0.5.x, merge it, then:
  git checkout main
  git cherry-pick -x <merge-commit-sha>
  ```

- **Only security fixes and P0/P1 critical bugs** qualify for backport.
  New features and non-critical improvements always target `main` only.
- `release/0.N.x` branches have the same CI gates as `main` (lint, typecheck,
  test, commit-lint). Do not skip hooks or bypass CI on release branches.

## Community

- License: MIT, see [`LICENSE`](LICENSE).
- Security: report vulnerabilities via GitHub private vulnerability reporting — see
  [`SECURITY.md`](SECURITY.md).
- Contributing: this file is the canonical guide; [`CONTRIBUTING.md`](CONTRIBUTING.md) is
  a short stub pointer.
