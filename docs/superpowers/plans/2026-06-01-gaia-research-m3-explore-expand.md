# Gaia Research M3 Explore Expand Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add targeted `gaia research explore --mode expand` artifacts that link a focused LKM search landscape back to an accepted focus or inquiry obligation.

**Architecture:** Reuse the package-native landscape builder from M2b, but require a target (`--focus` or `--obligation`) for expand mode. The CLI writes `.gaia/research/landscapes/expand-*.json` with target metadata and event provenance; it does not pull papers or mutate inquiry state unless a later accept/write milestone adds that behavior.

**Tech Stack:** Typer mode branching, package-local JSON artifacts, existing `ScanBatch` / `build_research_landscape`, pytest CLI tests.

---

## Success Criteria

- `gaia research explore <pkg> --mode expand` without `--focus` or `--obligation` fails with an actionable error.
- `gaia research explore <pkg> --mode expand --focus <target> --search-json <file>` writes an `explore.expand` landscape artifact.
- `--obligation <id>` works as an equivalent target.
- The artifact links back to the target with `target.kind` and `target.id`.
- Pull budget remains `0`.
- The command appends `explore.expand.completed` with artifact path, target, and stats.
- The command does not create `.gaia/lkm_packages/` or mutate `src/<pkg>/`.

## File Structure

- Modify `gaia/cli/commands/research.py`: branch scan vs expand and add target options.
- Modify `tests/cli/test_research.py`: add expand-mode CLI tests.
- Modify `docs/superpowers/plans/2026-06-01-gaia-research-implementation-index.md`: point M3 to this plan.

## Task 1: Failing CLI Tests

**Files:**
- Modify: `tests/cli/test_research.py`

- [ ] **Step 1: Add missing-target test**

Run:

```bash
uv run pytest tests/cli/test_research.py::test_research_expand_requires_focus_or_obligation -q
```

Expected before implementation: fail because expand mode is rejected as unsupported.

- [ ] **Step 2: Add focused artifact test**

Run:

```bash
uv run pytest tests/cli/test_research.py::test_research_expand_writes_targeted_landscape -q
```

Expected before implementation: fail because expand mode is rejected as unsupported.

## Task 2: CLI Integration

**Files:**
- Modify: `gaia/cli/commands/research.py`

- [ ] **Step 1: Add target options**

Add:

```python
focus: str | None = typer.Option(None, "--focus")
obligation: str | None = typer.Option(None, "--obligation")
```

- [ ] **Step 2: Add expand branch**

If `mode == "expand"`, require exactly one target family, parse search batches, write an `expand` artifact, set `landscape["action"] = "explore.expand"`, and add a `target` payload.

## Task 3: Verification And Commit

**Files:**
- Verify all touched M3 files.

- [ ] **Step 1: Run targeted checks**

Run:

```bash
uv run pytest tests/cli/test_research.py tests/gaia/test_research_landscape.py -q
uv run pytest tests/test_alpha0_docs.py -q
uv run ruff check gaia/engine/research gaia/cli/commands/research.py tests/cli/test_research.py tests/gaia/test_research_landscape.py
uv run ruff format --check gaia/engine/research gaia/cli/commands/research.py tests/cli/test_research.py tests/gaia/test_research_landscape.py
uv run mypy gaia/engine/research gaia/cli/commands/research.py tests/cli/test_research.py tests/gaia/test_research_landscape.py
git diff --check
```

Expected: all pass.

- [ ] **Step 2: Commit**

```bash
git add docs/superpowers/plans/2026-06-01-gaia-research-implementation-index.md \
  docs/superpowers/plans/2026-06-01-gaia-research-m3-explore-expand.md \
  gaia/cli/commands/research.py \
  tests/cli/test_research.py
git commit -m "feat(research): add targeted expand artifacts"
```
