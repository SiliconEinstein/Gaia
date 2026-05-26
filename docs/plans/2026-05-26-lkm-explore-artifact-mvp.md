# LKM Explore Artifact MVP Implementation Plan

> **For implementers:** Execute this plan task-by-task. Keep the work
> test-driven, make small commits, and preserve backward compatibility for the
> existing `gaia-lkm-explore` commands.

**Goal:** Add typed Explore sidecar artifacts to `gaia-lkm-explore`: `scope`,
`focuses`, `artifact`, and `gate`, without breaking the existing
frontier-driven exploration loop.

**Architecture:** Add a deterministic artifact layer under
`gaia.lkm_explorer.engine`, then expose it through thin Typer verbs in
`gaia.lkm_explorer.client.verbs` and register them in
`gaia.lkm_explorer.client.cli`. The MVP writes additive JSON sidecars under
`.gaia/exploration/`; existing map, landscape, frontier, turn, and round
semantics remain unchanged.

**Tech Stack:** Python 3.12, Typer, JSON sidecar artifacts, pytest.

**Spec reference:** `docs/specs/2026-05-26-lkm-explore-artifact-mvp-design.md`

---

## File Structure

Create:

```text
gaia/lkm_explorer/engine/artifacts.py
tests/lkm_explorer/test_artifacts.py
```

Modify:

```text
gaia/lkm_explorer/client/cli.py
gaia/lkm_explorer/client/verbs.py
tests/lkm_explorer/test_cli_explore.py
```

Responsibilities:

- `engine/artifacts.py`: pure artifact builders, dimension parsing, latest
  landscape discovery, and gate checks.
- `client/verbs.py`: Typer command wrappers, file reading/writing, and
  user-facing text.
- `client/cli.py`: command registration.
- `tests/lkm_explorer/test_artifacts.py`: pure engine tests.
- `tests/lkm_explorer/test_cli_explore.py`: CLI smoke and compatibility tests.

Use `gaia.engine.packaging.write_text_atomic` for artifact writes in the CLI
layer. Store `inputs.pkg` as `str(Path(pkg).resolve())` for path consistency.

## Task 1: Artifact Helpers

**Files:**
- Create: `gaia/lkm_explorer/engine/artifacts.py`
- Test: `tests/lkm_explorer/test_artifacts.py`

Implement small, deterministic helpers:

- `SOP_SCHEMA = "gaia.sop.artifact.v1"`
- `utcnow() -> str`
- `artifact_id(prefix: str) -> str`
- `parse_dimensions(items: list[str] | None) -> dict[str, list[str]]`
- `exploration_dir(pkg: str | Path) -> Path`
- `latest_landscape_path(pkg: str | Path) -> Path | None`
- `rel_artifact_path(pkg: str | Path, path: Path | None) -> str | None`

Required tests:

- repeated `--dimension key=value` entries group under the same key;
- malformed dimensions without `=` raise `ValueError`;
- artifact ids include the requested prefix and end with `Z`;
- latest landscape selection returns the highest sorted `landscape-*.json`;
- package-relative paths are used for artifacts inside the package.

Run:

```bash
uv run python -m pytest -q tests/lkm_explorer/test_artifacts.py
```

Commit:

```bash
git add gaia/lkm_explorer/engine/artifacts.py tests/lkm_explorer/test_artifacts.py
git commit -m "feat(lkm-explorer): add explore artifact helpers"
```

## Task 2: Scope Artifact

**Files:**
- Modify: `gaia/lkm_explorer/engine/artifacts.py`
- Modify: `gaia/lkm_explorer/client/verbs.py`
- Modify: `gaia/lkm_explorer/client/cli.py`
- Test: `tests/lkm_explorer/test_artifacts.py`
- Test: `tests/lkm_explorer/test_cli_explore.py`

Add a pure builder:

```text
build_scope_artifact(pkg, seeds, profile, dimensions, seed_source, map_round) -> dict
```

Contract:

- `kind == "exploration_scope"`
- `schema == "gaia.sop.artifact.v1"`
- `inputs.pkg` is resolved absolute path;
- `inputs.seeds` is the explicit CLI seed list, or map seeds when omitted;
- `inputs.profile` is optional;
- `inputs.dimensions` stores grouped dimension lists;
- `provenance.seed_source` is `cli` or `map`;
- `audit.allowed_next_steps == ["landscape", "focuses", "artifact", "gate"]`.

Add CLI:

```bash
gaia-lkm-explore scope <pkg> \
  [--seed <text>]... \
  [--profile <name>] \
  [--dimension key=value]... \
  [--out <path>] \
  [--json]
```

CLI behavior:

- fail with exit 1 if `.gaia/exploration/map.json` is missing;
- fail with exit 2 on malformed dimensions;
- default output path is `.gaia/exploration/scope.json`;
- print a concise summary and the output path;
- `--json` prints the payload after writing.

Required tests:

- builder records seeds, profile, dimensions, map round, and allowed next steps;
- CLI writes `scope.json`;
- CLI can derive seeds from `map.json` when `--seed` is omitted;
- invalid `--dimension` exits 2;
- `--help` includes `scope` options.

Run:

```bash
uv run python -m pytest -q tests/lkm_explorer/test_artifacts.py tests/lkm_explorer/test_cli_explore.py::test_explore_scope_writes_scope_artifact
```

Commit:

```bash
git add gaia/lkm_explorer/engine/artifacts.py gaia/lkm_explorer/client/verbs.py gaia/lkm_explorer/client/cli.py tests/lkm_explorer/test_artifacts.py tests/lkm_explorer/test_cli_explore.py
git commit -m "feat(lkm-explorer): add scope artifact command"
```

## Task 3: Focuses Artifact

**Files:**
- Modify: `gaia/lkm_explorer/engine/artifacts.py`
- Modify: `gaia/lkm_explorer/client/verbs.py`
- Modify: `gaia/lkm_explorer/client/cli.py`
- Test: `tests/lkm_explorer/test_artifacts.py`
- Test: `tests/lkm_explorer/test_cli_explore.py`

Add a pure builder:

```text
build_focuses_artifact(pkg, scope_path, landscape_path, landscape, map_round) -> dict
```

MVP focus generation rules:

- deterministic only;
- no LLM calls;
- no domain-specific tension invention;
- generate at least one `paper_lead_cluster` focus when landscape paper leads
  exist;
- every generated focus must have `evidence_refs`;
- `recommended_next == "assess"` for assessable focuses.

Minimum focus fields:

```text
id
kind
text
why_it_matters
evidence_refs
recommended_next
confidence
```

Add CLI:

```bash
gaia-lkm-explore focuses <pkg> \
  [--landscape <path>] \
  [--out <path>] \
  [--json]
```

CLI behavior:

- load the explicit landscape path, or default to the latest
  `.gaia/exploration/landscape-*.json`;
- fail with exit 2 if no landscape is available;
- read `.gaia/exploration/scope.json` if present, but do not require it;
- write `.gaia/exploration/focuses.json` by default.

Required tests:

- builder creates `exploration_focuses` from landscape paper leads;
- generated focuses include paper lead provenance;
- CLI writes `focuses.json`;
- CLI fails clearly when no landscape exists;
- existing `landscape` behavior remains unchanged.

Run:

```bash
uv run python -m pytest -q tests/lkm_explorer/test_artifacts.py tests/lkm_explorer/test_cli_explore.py::test_explore_focuses_writes_focuses_from_landscape
```

Commit:

```bash
git add gaia/lkm_explorer/engine/artifacts.py gaia/lkm_explorer/client/verbs.py gaia/lkm_explorer/client/cli.py tests/lkm_explorer/test_artifacts.py tests/lkm_explorer/test_cli_explore.py
git commit -m "feat(lkm-explorer): add focuses artifact command"
```

## Task 4: Exploration Artifact Envelope

**Files:**
- Modify: `gaia/lkm_explorer/engine/artifacts.py`
- Modify: `gaia/lkm_explorer/client/verbs.py`
- Modify: `gaia/lkm_explorer/client/cli.py`
- Test: `tests/lkm_explorer/test_artifacts.py`
- Test: `tests/lkm_explorer/test_cli_explore.py`

Add a pure builder:

```text
build_exploration_artifact(pkg, map_round, map_version) -> dict
```

Contract:

- `kind == "lkm_exploration"`
- `inputs.pkg` is resolved absolute path;
- `artifacts.scope` points to `scope.json` or `null`;
- `artifacts.landscape` points to the latest landscape or `null`;
- `artifacts.focuses` points to `focuses.json` or `null`;
- `artifacts.map` points to `map.json` or `null`;
- `artifacts.rounds`, `artifacts.gaia_ir`, and `artifacts.beliefs` are present
  as optional artifact refs;
- missing core sidecars are recorded in `audit.known_limitations`;
- `audit.allowed_next_steps == ["gate"]`;
- `interface.assess.command` documents the future handoff command.

Add CLI:

```bash
gaia-lkm-explore artifact <pkg> [--out <path>] [--json]
```

CLI behavior:

- load `ExplorationMap` for map round and version;
- write `.gaia/exploration/artifact.json` by default;
- do not fail just because optional files are missing;
- print the output path and limitation count.

Required tests:

- builder records missing optional sidecars as limitations;
- builder records present sidecars as package-relative paths;
- CLI writes `artifact.json`;
- CLI output contains the future `gaia-evidence assess --exploration ...`
  command.

Run:

```bash
uv run python -m pytest -q tests/lkm_explorer/test_artifacts.py tests/lkm_explorer/test_cli_explore.py::test_explore_artifact_writes_handoff_envelope
```

Commit:

```bash
git add gaia/lkm_explorer/engine/artifacts.py gaia/lkm_explorer/client/verbs.py gaia/lkm_explorer/client/cli.py tests/lkm_explorer/test_artifacts.py tests/lkm_explorer/test_cli_explore.py
git commit -m "feat(lkm-explorer): add exploration artifact envelope"
```

## Task 5: Explore Gate

**Files:**
- Modify: `gaia/lkm_explorer/engine/artifacts.py`
- Modify: `gaia/lkm_explorer/client/verbs.py`
- Modify: `gaia/lkm_explorer/client/cli.py`
- Test: `tests/lkm_explorer/test_artifacts.py`
- Test: `tests/lkm_explorer/test_cli_explore.py`

Add a pure builder:

```text
build_gate_report(artifact, focuses) -> dict
```

Required checks:

- `scope_present`
- `map_present`
- `landscape_present`
- `focuses_present`
- `has_assessable_focus`
- `focuses_have_evidence_refs`
- `artifact_present`
- `schema_versions_supported`

Warning checks:

- `compiled_ir_present`
- `beliefs_present`
- `rounds_present`

Verdict rules:

- `block` if any required check fails;
- `revise` if required checks pass but warning checks fail, or if assessable
  focuses exist but some focuses lack refs;
- `pass` only when all required and warning checks pass;
- `allowed_next_steps == ["assess"]` only for `pass`.

Add CLI:

```bash
gaia-lkm-explore gate <pkg> [--out <path>] [--json]
```

CLI behavior:

- read `.gaia/exploration/artifact.json`, or build and write it if missing;
- read `.gaia/exploration/focuses.json` when present;
- write `.gaia/exploration/gate_report.json` by default;
- print `Gate: pass|revise|block`;
- exit 1 on `block`;
- exit 0 on `pass` and `revise`.

Required tests:

- missing focuses yields `block`;
- evidence-backed focus with all artifacts yields `pass`;
- missing optional graph artifacts yields `revise`;
- unsupported schema yields `block`;
- CLI writes `gate_report.json`;
- CLI exits 1 on `block`.

Run:

```bash
uv run python -m pytest -q tests/lkm_explorer/test_artifacts.py tests/lkm_explorer/test_cli_explore.py::test_explore_gate_blocks_without_focuses
```

Commit:

```bash
git add gaia/lkm_explorer/engine/artifacts.py gaia/lkm_explorer/client/verbs.py gaia/lkm_explorer/client/cli.py tests/lkm_explorer/test_artifacts.py tests/lkm_explorer/test_cli_explore.py
git commit -m "feat(lkm-explorer): add explore gate report"
```

## Task 6: CLI Surface And Backward Compatibility

**Files:**
- Modify: `gaia/lkm_explorer/client/cli.py`
- Test: `tests/lkm_explorer/test_cli_explore.py`

Register commands in a readable order:

```text
init
scope
observe
landscape
focuses
artifact
gate
frontier
round
status
render
turn
```

Required tests:

- top-level help lists `scope`, `focuses`, `artifact`, `gate`, and `turn`;
- existing `init`, `observe`, `landscape`, `frontier`, `round`, `status`,
  `render`, and `turn` smoke tests still pass;
- new sidecar commands do not mutate `map.json` except reading from it.

Run:

```bash
uv run python -m pytest -q tests/lkm_explorer/test_landscape.py tests/lkm_explorer/test_cli_explore.py tests/lkm_explorer/test_frontier.py tests/lkm_explorer/test_orchestrator.py
```

Commit:

```bash
git add gaia/lkm_explorer/client/cli.py tests/lkm_explorer/test_cli_explore.py
git commit -m "test(lkm-explorer): cover artifact mvp cli surface"
```

## Task 7: Final Verification

Run targeted Explore tests:

```bash
uv run python -m pytest -q tests/lkm_explorer/test_artifacts.py tests/lkm_explorer/test_landscape.py tests/lkm_explorer/test_cli_explore.py tests/lkm_explorer/test_frontier.py tests/lkm_explorer/test_orchestrator.py tests/lkm_explorer/test_promote.py
```

Run PR gate:

```bash
uv run python -m pytest -q -m "pr_gate and not slow"
```

Use `uv run python -m pytest`, not `uv run pytest`, because the latter may
resolve to an external conda pytest in this workspace.

Run whitespace check:

```bash
git diff --check
```

Before final review:

- update `docs/specs/2026-05-26-lkm-explore-artifact-mvp-design.md` if command
  names, paths, or verdict semantics changed during implementation;
- ensure the old workflow still works:

```bash
gaia-lkm-explore init ./pkg --seed "..."
gaia-lkm-explore observe ./pkg --search-json leads.json
gaia-lkm-explore turn ./pkg
```
