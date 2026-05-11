<!-- BEGIN REFACTOR MORTAL BANNER · started 2026-05-11 -->

> 🚧 **REFACTOR IN PROGRESS — v0.5 engineering quality baseline alignment**
>
> This repo is mid-refactor. Every in-repo agent / contributor MUST follow these rules before touching anything:
>
> 1. **STATE document**: `.refactor/STATE.md` is the live progress doc for this refactor. **First action on session start = read STATE.md**, find the next `pending` work unit in the task queue. **Last action before exit = update STATE.md** (mark `done` or record `breakpoint_notes`).
> 2. **Doc fidelity is the top discipline**: all code / type annotations / docstrings / tests MUST strictly match the logic and semantics described in `docs/foundations/**` and `docs/specs/**`. Read `.refactor/doc-fidelity-baseline.md` on agent startup.
> 3. **Refactor boundary**: **DO NOT change** IR / semantics / DSL surface / API signatures / algorithms / naming. This refactor only does: engineering baseline injection (ruff / mypy / pytest / pre-commit config + CI) + adding type annotations + adding Google docstrings + adding tests.
> 4. **🚨 Doc-code contradiction = record + skip + claim next**: if you find a semantic / behavioral **contradiction** between repo docs and code (not just missing annotations / docstrings — actual logic disagreement), record under the current task's `breakpoint_notes` in `.refactor/STATE.md` (doc paragraph reference + code file:line + contradiction description + impact area), set that task's status to `blocked`, **then claim the next non-blocked pending unit and continue**. Do NOT decide "which side is right" yourself, and do NOT "fix it up in passing" — the refactor branch only does engineering baseline; semantic-layer contradictions accumulate in STATE.md and are batched to the user at the next phase checkpoint (α/β) for resolution.
> 5. **协作单**: this refactor is driven by Feishu 协作单 `AM15dZDhjooNyaxZRhNc1Sawnce`; decisions + ❓ escalation flow through it. Kanban entry: `GAIA-LKM kanban` (`IUvrwMmwliAUDukbXfUcwwxEnmf`).
> 6. **No PR during refactor — commit + push to `feat/v05-quality-baseline_rsw` only**. This repo's `CLAUDE.md § Workflow` rule "open a PR after every commit" is overridden during the refactor with "commit + push feat branch is enough"; PR opens at Phase 3 only, after the user gives an explicit "ship / PR" handshake.
> 7. **Orchestrator mode active**: this refactor is driven by an external orchestrator (the user's home_agent Claude session). The orchestrator triggers an in-repo agent (cursor-agent or equivalent) **one work unit per invocation**, verifies each commit, and pushes to origin in batches. As an in-repo agent you do not need to know the orchestrator exists; your job is exactly: read STATE.md → claim ONE pending unit → execute → commit + update STATE.md → exit. The orchestrator handles cross-unit coordination, push cadence, fresh-eyes audits, and user check-ins at checkpoints α/β/γ. **Do not claim more than one unit per invocation.**
>
> **This banner + `.refactor/` directory are temporary refactor artifacts.** Both will be deleted in a final cleanup PR after the refactor PR merges AND the user explicitly says "clean up refactor artifacts".

<!-- END REFACTOR MORTAL BANNER -->

# CLAUDE.md

This file follows the Claude Code `/init` convention: it gives agents the repo-specific
operating rules that are not obvious from reading the code. `CLAUDE.md` is a symlink to
`AGENTS.md`, so these instructions apply to Claude Code, Cursor, Codex, and other in-repo
agents.

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
uv sync --extra dev
uv run pre-commit install
```

The same setup is available through:

```bash
make bootstrap
```

## Quality Gates

Before committing normal development work, run:

```bash
make check
```

`make check` runs `uv run pre-commit run --all-files` and `uv run pytest`. Pytest is configured
with strict markers, coverage for `gaia`, and `--cov-fail-under=90`.

Additional focused commands:

```bash
make lint        # pre-commit over all files
make test        # pytest with the configured coverage gate
make typecheck   # strict mypy over gaia and tests
```

During the v0.5 refactor, strict mypy and full ruff select may still have known backlog items.
Do not weaken the configuration to make a work unit pass; record the state in `.refactor/STATE.md`
when the refactor queue says a gate is expected to remain red.

## Current Refactor Workflow

The v0.5 quality baseline refactor overrides the normal "open a PR after every commit" habit.
While the mortal banner is present:

1. Read `.refactor/STATE.md` first.
2. Read `.refactor/doc-fidelity-baseline.md`.
3. Claim exactly one pending unit in `STATE.md`.
4. Keep the work inside the stated refactor boundary.
5. Verify the unit with the relevant local gates.
6. Commit the unit on `feat/v05-quality-baseline_rsw`.
7. Update `STATE.md` as the last action before exit.

Do not open a PR during this refactor unless the user explicitly gives the Phase 3 ship/PR
handshake. Outside this temporary refactor, follow the regular branch-to-PR workflow for
feature work.

## Engineering Rules

- Preserve public APIs, CLI command names, arguments, output formats, persisted artifact shapes,
  DSL names, IR schemas, and BP algorithms unless the user explicitly approves a design change.
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
3. Mark the current refactor unit `blocked` in `.refactor/STATE.md`.
4. Record the doc reference, code location, contradiction, and impact in both the task notes and
   the Doc-Code Contradiction Log.
5. Tell the user so the issue can be escalated through the collaboration doc.

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

Work in a branch or an isolated worktree unless the user explicitly asks otherwise. Worktrees live
under `.worktrees/`, which is gitignored:

```bash
git worktree add .worktrees/<name> -b feature/<name>
```

Never use destructive git commands, force-push shared branches, or revert user changes unless the
user explicitly requests it.
