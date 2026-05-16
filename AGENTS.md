# Contributor and Agent Guide

This file is the canonical operating guide for both human contributors and in-repo agents
(Claude Code, Cursor, Codex, and any other agent driving the repo). `CLAUDE.md` is a symlink
to this file so Claude Code auto-loads it; `CONTRIBUTING.md` is a short stub that points
back here. Edit this file directly — never the symlink, and never duplicate guidance into
`CONTRIBUTING.md`.

For product overview, architecture, CLI behavior, and DSL reference, start with `README.md`
and then read the relevant canonical documents under `docs/foundations/`. This guide is only
for contributor workflow and guardrails.

## Project Map

Gaia is a Python 3.12 project for compiling a Python authoring DSL into Gaia IR and running
probabilistic inference over the resulting graph.

Key entry points:

- `gaia/lang/` owns the authoring DSL.
- `gaia/ir/` implements the Gaia IR contract shared by CLI and downstream systems.
- `gaia/bp/` implements factor-graph lowering and inference.
- `gaia/cli/` exposes the installed `gaia` Typer command.
- `tests/` contains the behavior and compatibility suite.
- `docs/foundations/` is the canonical design surface; `docs/specs/` holds current and
  historical design specs.

## Local Setup

Use `uv` for all dependency management. Do not install repo dependencies with `pip`.

```bash
make bootstrap
```

`make bootstrap` runs `uv sync --extra dev`, enables `extensions.worktreeConfig`, installs
all three hook stages — `pre-commit`, `pre-push`, and `commit-msg` — into the worktree-local
`.githooks/` directory, and sets `core.hooksPath` per worktree so git picks them up. The
pre-push hook runs the CI-byte-aligned gate locally so red CI is caught before the push
leaves your machine; the commit-msg hook enforces Conventional Commits on every commit.

Hooks live in `<worktree>/.githooks/` rather than the shared `.git/hooks/` directory, and
the convention applies whether or not you use additional worktrees — single clones get their
own `.githooks/` just the same. The rationale is that in a bare-hub-with-worktrees setup
`.git/hooks/` is shared across every worktree, while `pre-commit install` stubs hardcode the
installing worktree's `.venv/bin/python`. Per-worktree `.githooks/` makes each worktree's
hooks point at its own venv, so removing one worktree never leaves stale stubs that break
commits in another. Existing contributors migrate by re-running `make bootstrap` once; the
target is idempotent.

## Quality Gates

Local hooks split work across three stages:

- **pre-commit** (fast, per commit): hygiene hooks (trailing whitespace / EOF newline /
  merge-conflict / detect-private-key), `ruff check` narrow select + `--fix`, `ruff format`,
  `mypy --strict`, and the `CLAUDE.md` symlink check.
- **commit-msg** (per commit): `commitizen` validates the commit message against the
  Conventional Commits format. Merge and revert commits are exempt by commitizen defaults.
- **pre-push** (CI-byte-aligned, per push): `ruff check .` full 15-cat select,
  `ruff format --check .`, the `ir-schema` bump check, and
  `pytest -n auto tests -v -m "not slow" --cov=gaia --cov-fail-under=90`, plus the symlink and
  suppression-budget checks again. `mypy --strict` is not re-run here — it runs at pre-commit
  and CI's test job carries it as the push-time backstop.

For ad-hoc runs:

```bash
make check       # pre-commit (all files) + full pytest suite, parallel via pytest-xdist
make lint        # pre-commit over all files
make test        # fast pytest slice (-m "not slow"), parallel, no coverage
make typecheck   # strict mypy over gaia and tests
```

Pytest is configured with strict markers only; the aggregate 90% coverage gate is enforced via
explicit `--cov=gaia --cov-fail-under=90` flags at the two call sites that matter — the CI
workflow's `Run tests` step (`.github/workflows/ci.yml`) and the pre-push `pytest-cov` hook.
Local invocations like `pytest tests/unit/foo.py` therefore run without coverage by default,
and `make test` (the fast `not slow` slice) passes `--no-cov` explicitly for fast iteration.

Ruff's mccabe complexity limit is set to 12. An earlier limit of 9 proved too tight for
Gaia's mix of CLI workflows with BP message passing, IR coarsening, DSL compile/lower/link
passes, and inquiry orchestration. A limit of 12 is a mainstream Python threshold for mixed
CLI + library + algorithmic codebases while still requiring true decomposition of
high-complexity functions.

## Push Pre-flight

The pre-push hook runs the CI-byte-aligned gate (full ruff + format check + ir-schema bump +
parallel `pytest -n auto -m "not slow" --cov=gaia --cov-fail-under=90`) on every `git push`.
If the hook is green, local state has passed the same commands that CI's test job runs; mypy
was already enforced at pre-commit and is re-run by CI as the push-time backstop. GitHub may
still catch environment, branch-protection, or service-side issues.

**Do not bypass the pre-push hook** with `--no-verify` or any other hook-skip flag. If the hook
fails, fix the underlying issue and create a new commit — do not skip the hook to "ship now,
fix later". Bypassing produces silent drift between local and CI state and defeats the entire
point of byte-aligning the gates.

This applies equally to in-repo agents (Claude Code, Cursor, Codex, etc.). Agents must not
push without a green pre-push gate. Only the human contributor can override the hook in
genuinely exceptional circumstances, and the override should be called out explicitly in the
PR description.

### CLAUDE.md ↔ AGENTS.md sync

`CLAUDE.md` is a symlink to `AGENTS.md`. The pre-commit + pre-push hooks both verify this
relationship. Editing `AGENTS.md` is the canonical action; `CLAUDE.md` is never edited as a
separate file. `CONTRIBUTING.md` is a short stub that points back here — it intentionally
does not duplicate any guidance, so all contributor and agent rules stay in one place. If
you ever find `CLAUDE.md` diverging (the symlink replaced by a real file copy), restore with:

```bash
rm CLAUDE.md && ln -sf AGENTS.md CLAUDE.md
```

## Commits

This repo uses **Conventional Commits**. Every commit subject must follow:

```
<type>(<scope>): <imperative summary>
```

Allowed `<type>` values: `feat`, `fix`, `docs`, `refactor`, `chore`, `test`, `style`,
`perf`, `build`, `ci`. `<scope>` is free-form, lower-kebab (for example `bp`, `cli`,
`gaia-ir`, `docs-foundations`). The subject must be ≤ 72 characters and must not end with a
period. Use the body (separated by a blank line) for context, motivation, and breaking-change
notes (`BREAKING CHANGE: …`).

Enforcement is two-sided: a local `commit-msg` hook runs `commitizen` on every commit, and a
CI job runs `cz check` over every commit in a pull request. Merge commits and revert commits
are exempt by commitizen defaults, so normal `git merge` and `git revert` workflows are not
blocked.

## Engineering Rules

- Follow the design docs exactly. If a requested implementation would downgrade or diverge from
  a documented design, stop and ask before coding.
- Keep plans aligned with specs step by step; omitting a spec requirement is not an acceptable
  simplification.
- Prefer existing repo patterns and helper APIs over new abstractions.
- Keep edits scoped to the work unit. Do not clean up unrelated files, protected docs, generated
  fixtures, or user changes in the same pass.
- If the environment exposes repo skills or agent workflows, use the matching one before going
  manual.

## Code Style

- Python target: 3.12.
- Ruff line length: 100.
- Use PEP 604 annotations: `X | None`, not `Optional[X]`; `list[X]`, not `List[X]`.
- Use Google-style docstrings for new or touched public modules, classes, and functions.
- Use Pydantic v2 APIs: `.model_dump()`, `.model_validate()`, `.model_validate_json()`.
- Keep Typer command docstrings concise because they can affect `--help` output.

## Doc Fidelity

Documentation fidelity is load-bearing in this repo. Code, annotations, docstrings, tests, and
tooling must match the semantics described in `docs/foundations/**` and current-canonical
`docs/specs/**`.

If you find a semantic contradiction between docs and code:

1. Do not decide which side is right.
2. Do not fix it in passing.
3. Stop work on the affected unit and record the doc reference, code location, contradiction,
   and impact area.
4. Tell the user so the issue can be escalated and resolved before the code change lands.

Missing annotations, missing docstrings, and normal test gaps are not contradictions; actual
behavioral or semantic disagreement is.

## Foundations Layers

`docs/foundations/` mirrors the architecture. Information flows downward; lower layers reference
upper layers instead of redefining them.

| Layer | Responsibility |
| --- | --- |
| `theory/` | External theory: Jaynes, propositional operators, BP foundations |
| `ecosystem/` | Product scope, decentralized package flow, registry operations |
| `gaia-ir/` | Gaia IR structure contract and validation rules |
| `gaia-lang/` | Authoring DSL, package model, predicate logic, Bayes surface |
| `bp/` | BP computation over Gaia IR |
| `review/` | Review, inquiry, and gating pipeline |
| `cli/` | Local authoring, compile, inference, storage, registration |
| `contracts/` | Shared report/data contracts |

Hard layering rules:

1. `docs/foundations/gaia-ir/` is the single source for IR structure definitions.
2. `docs/foundations/bp/` defines BP computation semantics.
3. `gaia/cli/` owns Gaia Lang workflows; LKM-side systems operate on Gaia IR, not Gaia Lang.
4. Cross-layer definitions should link instead of copying content.
5. Schema changes start in the IR layer and require downstream validation.

## Protected Layers

Do not edit these documentation layers directly:

- `docs/foundations/gaia-ir/`
- `docs/foundations/theory/`

If implementation work appears to require changing Gaia IR or theory definitions, stop and ask
the user with:

1. the current definition,
2. why it needs to change,
3. the proposed change.

Approved protected-layer changes must be isolated from feature or quality-refactor work.

## Documentation Policy

Before editing architecture or foundation docs, read `docs/documentation-policy.md`.

Foundation documents must clearly distinguish:

- current canonical behavior,
- target designs,
- transitional notes,
- historical background,
- runtime implementation quirks.

Prefer replacing or archiving obsolete conceptual models over repeatedly patching them in place.

## Scripts and Pipelines

CLI scripts and pipeline entry points must log enough detail to be diagnosable when run in the
background. This applies to `scripts/*.py` and any package pipeline entry point with `__main__`.

Required logging pattern:

1. log to both console and `logs/{name}-{timestamp}.log`,
2. use `logging.basicConfig(..., force=True)`,
3. log each phase start and finish,
4. print or log the log-file path first,
5. use `print(..., flush=True)` for ordinary prints.

Template:

```python
import logging
import os
import time

_LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")
os.makedirs(_LOG_DIR, exist_ok=True)
_LOG_FILE = os.path.join(_LOG_DIR, f"{script_name}-{time.strftime('%Y%m%d-%H%M%S')}.log")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler(_LOG_FILE)],
    force=True,
)
logger = logging.getLogger(__name__)
logger.info("Log file: %s", _LOG_FILE)
```

If you run a background script, inspect its log before reporting results.

## Git and Worktrees

Work in a branch or an isolated worktree unless the user explicitly asks otherwise. Worktrees
live under `.worktrees/<slug>`, which is gitignored:

```bash
git worktree add .worktrees/<slug> -b feature/<slug>
```

Never use destructive git commands, force-push shared branches, or revert user changes unless
the user explicitly requests it.

## Community

- License: MIT, see [`LICENSE`](LICENSE).
- Security: report vulnerabilities via GitHub private vulnerability reporting — see
  [`SECURITY.md`](SECURITY.md).
- Contributing: this file is the canonical guide; [`CONTRIBUTING.md`](CONTRIBUTING.md) is a
  short stub pointer.
