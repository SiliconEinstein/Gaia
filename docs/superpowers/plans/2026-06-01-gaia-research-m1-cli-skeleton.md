# Gaia Research M1 CLI Skeleton Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the canonical `gaia research` CLI skeleton with package-local manifest/events artifacts and artifact-only `status`, `explore --mode scan --dry-run`, and `assess --artifact-only` commands.

**Architecture:** Add a small `gaia.engine.research` artifact module for package validation, manifest IO, event logging, and inquiry snapshots. Add `gaia.cli.commands.research` as a thin Typer layer that calls those helpers and emits human-readable next-step suggestions without writing source or parallel semantic ledgers.

**Tech Stack:** Typer, dataclasses, JSON/JSONL files, Gaia package `pyproject.toml`, `gaia.engine.inquiry.state.load_state`, pytest with `CliRunner`.

---

## Success Criteria

- `gaia --help` lists the `research` command group.
- `gaia research status <pkg>` validates an existing Gaia package, creates/updates `.gaia/research/manifest.json`, appends `.gaia/research/events.jsonl`, and reports inquiry status.
- `gaia research explore <pkg> --mode scan --dry-run` records a dry scan planning event and prints `pull_budget: 0`.
- `gaia research assess <pkg> --focus <target> --artifact-only` records an artifact-only assessment planning event.
- Invalid package targets return a scaffold suggestion such as `gaia pkg scaffold --target <path> --name <name>-gaia` and do not create `.gaia/research/`.
- No command creates `.gaia/lkm_packages/`, `.gaia/exploration/`, or source claims in `src/<pkg>/`.
- Suggested gaps appear as `gaia inquiry obligation add ...` command text, not durable `.gaia/research/obligations.json`.
- `gaia build check <pkg>` still runs after research commands.

## File Structure

- Create `gaia/engine/research/__init__.py`: public exports for research artifact helpers.
- Create `gaia/engine/research/artifacts.py`: package metadata validation, manifest read/write, event append, status snapshot.
- Create `gaia/cli/commands/research.py`: Typer app and M1 commands.
- Modify `gaia/cli/main.py`: register `research_app`.
- Create `tests/cli/test_research.py`: CLI-level M1 regression tests.

## Task 1: Research Artifact Helpers

**Files:**
- Create: `gaia/engine/research/__init__.py`
- Create: `gaia/engine/research/artifacts.py`

- [ ] **Step 1: Write package metadata and manifest helpers**

Implement:

```python
@dataclass(frozen=True)
class ResearchPackage:
    path: Path
    project_name: str
    import_name: str
    namespace: str

def load_research_package(path: str | Path) -> ResearchPackage:
    ...

def ensure_research_manifest(pkg: ResearchPackage) -> dict[str, Any]:
    ...

def append_research_event(pkg: ResearchPackage, event: str, payload: dict[str, Any]) -> dict[str, Any]:
    ...
```

- [ ] **Step 2: Validate package target behavior**

Run:

```bash
uv run pytest tests/cli/test_research.py::test_research_rejects_non_package_without_creating_layout -q
```

Expected before implementation: fail because the test/module does not exist.

## Task 2: CLI Skeleton

**Files:**
- Create: `gaia/cli/commands/research.py`
- Modify: `gaia/cli/main.py`

- [ ] **Step 1: Register the Typer app**

Add:

```python
from gaia.cli.commands.research import research_app
...
app.add_typer(research_app, name="research")
```

- [ ] **Step 2: Add M1 commands**

Implement:

```python
research_app = typer.Typer(name="research", help="Package-native research actions.")

@research_app.command("status")
def status_command(pkg: str) -> None: ...

@research_app.command("explore")
def explore_command(pkg: str, mode: str = "scan", dry_run: bool = False) -> None: ...

@research_app.command("assess")
def assess_command(pkg: str, focus: str, artifact_only: bool = True) -> None: ...
```

The commands must call the artifact helpers and print Gaia-native suggestions.

- [ ] **Step 3: Verify help registration**

Run:

```bash
uv run pytest tests/cli/test_research.py::test_research_group_is_help_visible -q
```

Expected: pass.

## Task 3: CLI Regression Tests

**Files:**
- Create: `tests/cli/test_research.py`

- [ ] **Step 1: Add a minimal package fixture**

Fixture writes:

```python
from gaia.engine.lang import claim

seed = claim("Seed claim.")
__all__ = ["seed"]
```

with a valid `[tool.gaia]` package config.

- [ ] **Step 2: Test dry scan manifest/events and source immutability**

Assert:

- `.gaia/research/manifest.json` exists;
- `.gaia/research/events.jsonl` contains an `explore.scan.planned` event;
- `src/<pkg>/__init__.py` is byte-for-byte unchanged;
- `.gaia/lkm_packages/` and `.gaia/exploration/` do not exist;
- output includes `gaia inquiry obligation add`.

- [ ] **Step 3: Test assessment artifact-only event**

Assert:

- `gaia research assess <pkg> --focus seed --artifact-only` exits 0;
- latest event is `assess.planned`;
- event payload contains `artifact_only: true` and `focus: seed`;
- source remains unchanged.

- [ ] **Step 4: Test build check compatibility**

Run `gaia build check <pkg>` after research commands and assert exit code `0`.

## Task 4: Verification And Commit

**Files:**
- Verify all files above.

- [ ] **Step 1: Run targeted checks**

Run:

```bash
uv run pytest tests/cli/test_research.py -q
uv run pytest tests/test_alpha0_docs.py -q
git diff --check
```

Expected: all pass.

- [ ] **Step 2: Review source mutation guarantees**

Run:

```bash
git diff -- gaia/engine/research gaia/cli/commands/research.py gaia/cli/main.py tests/cli/test_research.py docs/superpowers/plans
```

Expected: only the M1 files and plan docs changed.

- [ ] **Step 3: Commit**

```bash
git add docs/superpowers/plans/2026-06-01-gaia-research-implementation-index.md \
  docs/superpowers/plans/2026-06-01-gaia-research-m1-cli-skeleton.md \
  gaia/engine/research \
  gaia/cli/commands/research.py \
  gaia/cli/main.py \
  tests/cli/test_research.py
git commit -m "feat(research): add cli skeleton"
```
