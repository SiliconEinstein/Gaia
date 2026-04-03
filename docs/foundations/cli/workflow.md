---
status: current-canonical
layer: cli
since: v5-phase-1
---

# CLI Workflow

## Overview

The Gaia CLI is a knowledge package authoring toolkit. It provides a six-command
pipeline that takes a Python DSL package from scaffolding to registry registration:

```
gaia init --> gaia compile --> gaia check --> gaia add --> gaia infer --> git tag --> gaia register
(scaffold)    (DSL -> IR)     (validate)   (add deps)   (BP preview)              (registry PR)
```

Entry point: installed as the `gaia` CLI command via `pyproject.toml`
`[project.scripts]`, backed by a Typer app at `gaia.cli.main:app`.


## Commands

### `gaia init <NAME>`

Scaffold a new Gaia knowledge package.

```
gaia init <NAME>
```

| Argument | Default | Description |
|----------|---------|-------------|
| `NAME`   | (required) | Package name (must end with `-gaia`) |

**What it does:**

1. Runs `uv init --lib` under the hood to create the package directory.
2. Adds `[tool.gaia]` configuration to `pyproject.toml` (with `type = "knowledge-package"` and a generated `uuid`).
3. Renames the `src/` subdirectory to match the Gaia import name convention (strips the `-gaia` suffix, replaces hyphens with underscores).
4. Writes a DSL template into the package module's `__init__.py`.

The resulting directory is a complete Gaia knowledge package ready for `gaia compile`.

**Key output:** a new directory `<NAME>/` containing `pyproject.toml`, `src/<import_name>/__init__.py` with DSL template code.


### `gaia compile [PATH]`

Compile a Python DSL package to Gaia IR.

```
gaia compile [PATH]
```

| Argument | Default | Description |
|----------|---------|-------------|
| `PATH`   | `.`     | Path to knowledge package directory |

**What it does:**

1. Loads the package from `pyproject.toml` (requires `[tool.gaia].type = "knowledge-package"`).
2. Imports the Python module, collects `Knowledge`, `Strategy`, and `Operator` declarations.
3. Assigns labels from Python variable names to unlabeled objects.
4. Compiles the collected package to Gaia IR via `gaia.lang.compiler.compile_package`.
5. Validates the resulting `LocalCanonicalGraph` (warnings printed, errors abort).
6. Writes `.gaia/ir.json` and `.gaia/ir_hash` to the package directory.

Compilation is deterministic: same source produces the same `ir_hash`. No LLM
calls, no network access.

**Key output:** `.gaia/ir.json` (full IR), `.gaia/ir_hash` (content hash for
staleness detection).

Reference: [Compilation](compilation.md) for internals.


### `gaia check [PATH]`

Validate package structure and artifact consistency.

```
gaia check [PATH]
```

| Argument | Default | Description |
|----------|---------|-------------|
| `PATH`   | `.`     | Path to knowledge package directory |

**What it does:**

1. Loads and compiles the package (same as `gaia compile`).
2. Checks that `[project].name` ends with `-gaia`.
3. Validates the `LocalCanonicalGraph` (schema and structural checks).
4. If `.gaia/ir_hash` exists, verifies it matches the current compilation output.
5. If `.gaia/ir.json` exists, verifies its embedded hash matches.

Exits with code 1 on any error. Warnings (e.g., missing compiled artifacts) are
printed but do not fail the check.

**Key output:** none (validation only, prints pass/fail summary).

Reference: [Compilation](compilation.md) for validation details.


### `gaia add <PACKAGE> [OPTIONS]`

Install a registered Gaia knowledge package from the official registry.

```
gaia add <PACKAGE> [--version VERSION] [--registry REPO]
```

| Argument / Option | Default | Description |
|-------------------|---------|-------------|
| `PACKAGE`         | (required) | Package name (e.g., `galileo-falling-bodies-gaia`) |
| `--version VERSION` | latest | Specific version to install |
| `--registry REPO` | `SiliconEinstein/gaia-registry` | Custom registry repo slug |

**What it does:**

1. Queries registry metadata via the GitHub API to resolve the package and version.
2. Resolves the version to a specific git tag and SHA.
3. Calls `uv add` with a pinned git URL pointing to the resolved tag.

The package is added as a standard Python dependency in `pyproject.toml` and
installed into the project environment.

**Key output:** updated `pyproject.toml` `[project].dependencies` and
`uv.lock` with the pinned Gaia package dependency.


### `gaia infer [PATH] [--review NAME]`

Run belief propagation using compiled IR plus a review sidecar parameterization.

```
gaia infer [PATH] [--review NAME]
```

| Argument / Option | Default | Description |
|-------------------|---------|-------------|
| `PATH`            | `.`     | Path to knowledge package directory |
| `--review NAME`   | `None`  | Review sidecar name: loads `<package>/reviews/<NAME>.py`, or `review` for legacy `<package>/review.py`. Auto-selected when only one sidecar exists. |

**What it does:**

1. Loads and compiles the package to a `LocalCanonicalGraph`.
2. Verifies `.gaia/ir_hash` and `.gaia/ir.json` are present and not stale.
3. Discovers and loads the review sidecar module, which must export
   `REVIEW = ReviewBundle(...)`.
4. Resolves review objects (`ClaimReview`, `GeneratedClaimReview`,
   `StrategyReview`) into `PriorRecord` and `StrategyParamRecord` records.
5. Validates the parameterization against the IR graph.
6. Lowers the graph to a factor graph via `lower_local_graph`.
7. Runs `BeliefPropagation(damping=0.5, max_iterations=100)`.
8. Writes results to `.gaia/reviews/<NAME>/`:
   - `parameterization.json` -- source, resolution policy, resolved priors and
     strategy params.
   - `beliefs.json` -- per-knowledge beliefs, convergence diagnostics.

**Prerequisites:** `gaia compile` must have been run first (artifacts must be
fresh).

**Key output:** `.gaia/reviews/<NAME>/parameterization.json`,
`.gaia/reviews/<NAME>/beliefs.json`.

Reference: [Inference](inference.md) for internals.


### `gaia register [PATH] [OPTIONS]`

Prepare or submit a registration for a tagged, GitHub-backed Gaia package.

```
gaia register [PATH] [--tag TAG] [--repo URL] [--registry-dir PATH]
              [--registry-repo SLUG] [--create-pr]
```

| Argument / Option     | Default                          | Description |
|-----------------------|----------------------------------|-------------|
| `PATH`                | `.`                              | Path to knowledge package directory |
| `--tag TAG`           | `v<version>` from pyproject.toml | Git tag to register |
| `--repo URL`          | git origin remote                | GitHub repository URL |
| `--registry-dir PATH` | `None`                           | Local checkout of the official registry repo |
| `--registry-repo SLUG`| `SiliconEinstein/gaia-registry`  | Registry GitHub repo slug for PR creation |
| `--create-pr`         | `False`                          | Push registry branch and open a GitHub PR |

**What it does:**

1. Loads, compiles, and validates the package.
2. Verifies `.gaia/ir_hash` is present and fresh.
3. Validates prerequisites:
   - `[tool.gaia].uuid` is set and is a valid UUID.
   - `[project].name` ends with `-gaia`.
   - Git worktree is clean.
   - The tag exists, points to HEAD, and is pushed to origin.
   - Remote is a GitHub URL (Phase 1 restriction).
4. Parses `[project].dependencies` for Gaia package deps (names ending in
   `-gaia`).
5. Prepares exported claims from the IR based on the package's `exported` list.
6. Builds a registration plan containing `Package.toml`, `Versions.toml`, and
   `Deps.toml` content.

**Three modes of operation:**

- **Dry-run** (default, no `--registry-dir`): prints the registration plan as
  JSON to stdout.
- **Local write** (`--registry-dir` without `--create-pr`): creates a branch
  `register/<name>-<version>` in the registry checkout, writes/updates TOML
  files, commits. Preserves existing versions when appending.
- **Full registration** (`--registry-dir --create-pr`): local write, then pushes
  the branch and creates a GitHub PR via `gh pr create`.

**Key output (in registry repo):**
- `packages/<name>/Package.toml` -- package identity (uuid, name, repo, description).
- `packages/<name>/Versions.toml` -- version entries (ir_hash, git_tag, git_sha, timestamp).
- `packages/<name>/Deps.toml` -- per-version Gaia package dependencies.

Reference: [Registration](registration.md) for details.


## Artifacts by Stage

| Stage    | Command          | Key Artifacts |
|----------|------------------|---------------|
| Init     | `gaia init`      | `pyproject.toml` with `[tool.gaia]`, `src/<import_name>/__init__.py` with DSL template |
| Compile  | `gaia compile`   | `.gaia/ir.json`, `.gaia/ir_hash` |
| Check    | `gaia check`     | (validation only) |
| Add      | `gaia add`       | Updated `pyproject.toml` dependencies, `uv.lock` |
| Infer    | `gaia infer`     | `.gaia/reviews/<name>/parameterization.json`, `.gaia/reviews/<name>/beliefs.json` |
| Register | `gaia register`  | `packages/<name>/Package.toml`, `Versions.toml`, `Deps.toml` (in registry repo) |


## Package Requirements

A valid Gaia knowledge package has:

- A `pyproject.toml` with `[tool.gaia].type = "knowledge-package"`.
- `[project].name` ending with `-gaia` (enforced by `check` and `register`).
- `[project].version` set.
- `[tool.gaia].uuid` set to a valid UUID (required for `register`).
- A Python module at `src/<import_name>/` or `<import_name>/` that declares
  `Knowledge`, `Strategy`, and/or `Operator` objects.

The import name is derived from the project name: strip the `-gaia` suffix and
replace hyphens with underscores (e.g., `galileo-falling-bodies-gaia` becomes
`galileo_falling_bodies`).


## Quick Start

```bash
# 1. Scaffold a package
gaia init galileo-falling-bodies-gaia
cd galileo-falling-bodies-gaia

# 2. Write DSL declarations in src/galileo_falling_bodies/__init__.py

# 3. Compile DSL to IR
gaia compile .

# 4. Validate package
gaia check .

# 5. Add dependencies from the registry (optional)
gaia add some-prerequisite-gaia

# 6. Preview beliefs (optional)
gaia infer . --review self_review

# 7. Tag and push
git add -A && git commit -m "initial package"
git tag v0.1.0
git push origin main --tags

# 8. Dry-run registration (prints JSON plan)
gaia register .

# 9. Write to registry and open PR
gaia register . --registry-dir ../gaia-registry --create-pr
```
