---
status: current-canonical
layer: cli
since: v5-phase-1
---

# Registry Registration

## Overview

`gaia register` prepares or submits a package registration to the Gaia Official Registry -- a Julia General Registry-style metadata-only GitHub repository. The registry stores package metadata (identity, versions, dependencies) while source code stays in the author's GitHub repo.

Registration produces a pull request against the registry repo. Registry CI validates the submission (recompiles, verifies IR hash, checks deps), then auto-merges after a waiting period.

## Prerequisites

Before running `gaia register`, the following conditions must hold:

1. **`[tool.gaia].uuid`** is set in `pyproject.toml` and is a valid UUID.
2. **`[project].name`** ends with `-gaia` (the naming convention for Gaia packages).
3. **Package compiled and validated** -- `gaia compile` and `gaia check` must have been run. The command verifies `.gaia/ir_hash` exists and matches the current compilation output.
4. **IR validation passes** -- the compiled IR is loaded as a `LocalCanonicalGraph` and validated; any validation errors abort registration.
5. **Git worktree is clean** -- `git status --short` must produce no output.
6. **Git tag exists and points to HEAD** -- by default, the tag is `v<version>` (override with `--tag`). The tag's resolved SHA must equal `HEAD`.
7. **Tag is pushed to origin** -- verified via `git ls-remote --tags origin`.
8. **Repository is hosted on GitHub** -- Phase 1 limitation. The origin URL (or `--repo` override) must resolve to `https://github.com/...`.

If any check fails, the command prints a diagnostic message to stderr and exits with code 1.

## Command Flags

```
gaia register [PATH] [OPTIONS]
```

| Flag | Default | Description |
|------|---------|-------------|
| `PATH` | `.` | Path to the knowledge package directory |
| `--tag` | `v<version>` | Git tag to register |
| `--repo` | origin remote URL | GitHub repository URL (normalized to `https://github.com/...`) |
| `--registry-dir` | `None` | Path to a local checkout of the registry repo |
| `--registry-repo` | `SiliconEinstein/gaia-registry` | Registry GitHub repo slug for PR creation |
| `--create-pr` | `False` | Push the registry branch and open a GitHub PR (requires `--registry-dir`) |

## Dry-Run Mode (Default)

Without `--registry-dir`, `gaia register` outputs a JSON registration plan to stdout and exits. This is the default behavior -- useful for previewing what would be submitted before touching the registry checkout.

The JSON plan contains:

```json
{
  "package": {
    "uuid": "336ed68f-0bac-5ca0-87d4-7b16caf5d00b",
    "name": "galileo-falling-bodies",
    "pypi_name": "galileo-falling-bodies-gaia",
    "repo": "https://github.com/kunyuan/GalileoFallingBodies.gaia",
    "description": "Galileo's falling bodies argument"
  },
  "version": {
    "version": "4.0.0",
    "git_tag": "v4.0.0",
    "git_sha": "abc123def456...",
    "ir_hash": "sha256:a1b2c3d4..."
  },
  "deps": {
    "aristotle-mechanics-gaia": ">= 1.0.0"
  },
  "registry_repo": "SiliconEinstein/gaia-registry",
  "files": {
    "packages/galileo-falling-bodies/Package.toml": "...",
    "packages/galileo-falling-bodies/Versions.toml": "...",
    "packages/galileo-falling-bodies/Deps.toml": "..."
  },
  "pull_request": {
    "title": "register: galileo-falling-bodies-gaia 4.0.0",
    "body": "..."
  }
}
```

The `deps` field is derived from `[project].dependencies` in `pyproject.toml`, filtered to entries whose package name ends with `-gaia`. The version specifier is preserved as-is; if none is given, it defaults to `*`.

## Registry Write Mode

With `--registry-dir <path>`, `gaia register` writes metadata files into a local checkout of the registry repository:

1. **Verifies** the registry checkout is clean (`git status --short` is empty).
2. **Creates branch** `register/<name>-<version>` in the registry checkout. Fails if the branch already exists.
3. **Creates or updates** three TOML files under `packages/<name>/`.
4. **Commits** the changes to the new branch.

### Package.toml

Created once for a new package. On subsequent version registrations, the existing file is read and its `uuid` is verified against `[tool.gaia].uuid` -- a mismatch aborts registration. The file is never overwritten after initial creation.

```toml
uuid = "336ed68f-0bac-5ca0-87d4-7b16caf5d00b"
name = "galileo-falling-bodies"
pypi_name = "galileo-falling-bodies-gaia"
repo = "https://github.com/kunyuan/GalileoFallingBodies.gaia"
description = "Galileo's falling bodies argument"
created_at = "2026-04-02T10:00:00Z"
```

### Versions.toml

Appended with each new version. Existing versions are loaded and the new entry is merged in. If the version already exists, registration aborts with an error.

```toml
[versions."4.0.0"]
ir_hash = "sha256:a1b2c3d4..."
git_tag = "v4.0.0"
git_sha = "abc123def456..."
registered_at = "2026-04-02T10:30:00Z"
gaia_lang_version = "0.2.5"

[versions."4.1.0"]
ir_hash = "sha256:e5f6g7h8..."
git_tag = "v4.1.0"
git_sha = "789abc012def..."
registered_at = "2026-04-10T15:00:00Z"
gaia_lang_version = "0.2.7"
```

Versions are sorted lexicographically by version string in the rendered output.

**Fields:**

| Field | Source | Notes |
|-------|--------|-------|
| `ir_hash` | `.gaia/ir_hash` | Content hash of the compiled IR — structural identity |
| `git_tag` | `--tag` / derived from pyproject version | Must exist and point to HEAD |
| `git_sha` | `git rev-parse <tag>` | Commit the tag points to |
| `registered_at` | `datetime.utcnow()` at register time | UTC, ISO-8601 |
| `gaia_lang_version` | `.gaia/compile_metadata.json` (written at `gaia compile` time) | Which `gaia-lang` compiled the IR being registered. Read from the committed compile metadata file, **not** from the live process environment — this decouples the registered provenance from whatever version happens to be installed when `gaia register` runs. When the metadata file is missing or malformed (e.g. legacy packages compiled before the field was introduced), the value is emitted as `"unknown"` and a warning is printed. Consumers can use this to detect BP engine version drift across patch releases that keep `ir_hash` stable but refine numerical inference. |

Older entries that pre-date the `gaia_lang_version` field are preserved as-is when the registry file is re-rendered — the renderer emits only keys present in the payload. This keeps historical entries stable across registrations.

**Forward-compat note:** The renderer respects native TOML types for canonical and unknown fields alike — a future `gaia-lang` that adds a boolean or integer field to `Versions.toml` can safely coexist with older CLIs reading the same file. Complex types (arrays, nested tables, datetimes) are explicitly rejected rather than silently coerced.

### Deps.toml

Tracks Gaia package dependencies per version. Like `Versions.toml`, existing entries are loaded and the new version is appended. Dependency names within each version section are sorted alphabetically.

```toml
[deps."4.0.0"]
"aristotle-mechanics-gaia" = ">= 1.0.0"

[deps."4.1.0"]
"aristotle-mechanics-gaia" = ">= 1.0.0"
"newton-mechanics-gaia" = ">= 2.0.0"
```

## Creating a PR

With `--create-pr` (requires `--registry-dir`):

1. **Pushes** the registry branch to origin: `git push -u origin register/<name>-<version>`.
2. **Opens a PR** via `gh pr create` against the registry repo's `main` branch with a generated title and body.

The PR title follows the format:

```
register: <pypi_name> <version>
```

The PR body includes repository URL, tag, IR hash, a list of exported claims (if any), and Gaia dependencies.

Without `--create-pr`, the command prints a "next step" message instructing the user to push the branch and open a PR manually.

## Registry CI Overview

After the PR is created, registry CI (`register.yml`) takes over:

- **Untrusted sandbox job**: Clones the package repo by pinned SHA, installs the Gaia runtime, runs `gaia compile` and `gaia check`, and verifies the resulting `ir_hash` matches the declared value. Also verifies all Gaia dependencies are already registered. **Validates that `namespace` matches the registry** — the GitHub Official Registry requires `namespace == "github"`. Author code is executed here, but the job has no registry write permissions.
- **Trusted gate job**: Does not execute author code. Verifies UUID uniqueness for new packages, checks ownership policy, labels the PR, and applies the waiting-period policy.
- **Waiting period**: 72 hours for new packages (community review window), 1 hour for version updates (lower operational risk).
- **Auto-merge**: After the waiting period expires and all checks pass.

Security invariant: author code never runs in a job with write permissions to the registry.

Reference: `docs/specs/2026-04-02-gaia-registry-design.md` for the full CI spec, trust model, and future extension points.

## Consumer Workflow

Phase 1 is a source registry. Consumers install registered packages directly from the pinned GitHub source:

```bash
uv add "galileo-falling-bodies-gaia @ git+https://github.com/kunyuan/GalileoFallingBodies.gaia@<validated-git-sha>"
```

The registry provides the canonical repo URL and immutable git SHA for each version, ensuring reproducible installs even without a wheel index.

A future convenience command (`gaia add`) may resolve packages through registry metadata and write the correct Git direct reference into `pyproject.toml` automatically.

## Example End-to-End

```bash
# 1. Author prepares the release
cd ~/my-package
gaia compile .
gaia check .
git add . && git commit -m "Prepare v1.0.0"
git push origin main
git tag v1.0.0
git push origin v1.0.0

# 2. Preview the registration plan (dry-run)
gaia register .

# 3. Write metadata to a local registry checkout
gaia register . --registry-dir ~/gaia-registry

# 4. Push and open PR in one step
gaia register . --registry-dir ~/gaia-registry --create-pr

# 5. Registry CI validates, waits, and auto-merges
```
