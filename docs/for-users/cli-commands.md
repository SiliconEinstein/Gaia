# CLI Commands

> **Status:** Current canonical

Reference for the active Gaia Lang v5 CLI. The installed entrypoint is `gaia`.

## Command Set

```text
gaia compile
gaia check [--brief] [--show <module|label>]
gaia register
```

`gaia build`, `gaia infer`, and `gaia publish` are not part of the current Gaia Lang v5 author workflow.

## `gaia compile`

Compile a Gaia Python package into `.gaia/ir.json` and `.gaia/ir_hash`.

```bash
gaia compile [path]
```

Arguments:

| Argument | Default | Description |
|----------|---------|-------------|
| `path` | `.` | Path to the package repository |

What it does:

- loads `pyproject.toml`
- resolves the Python import package from either `<repo>/<import_name>/` or `<repo>/src/<import_name>/`
- executes the Gaia DSL declarations
- emits a `LocalCanonicalGraph` to `.gaia/ir.json`
- writes the deterministic graph hash to `.gaia/ir_hash`

What it does not do:

- does not push to GitHub
- does not register the package
- does not run belief propagation or local database ingest

Example:

```bash
gaia compile .
```

## `gaia check`

Validate that a package is structurally sound and ready for registration. Optionally display the warrant structure for review.

```bash
gaia check [path]
gaia check --brief [path]
gaia check --show <module|label> [path]
gaia check --brief --show <module|label> [path]
gaia check --hole [path]
```

Arguments:

| Argument | Default | Description |
|----------|---------|-------------|
| `path` | `.` | Path to the package repository |

Options:

| Option | Description |
|--------|-------------|
| `--brief`, `-b` | Show per-module warrant structure overview after validation |
| `--show`, `-s` | Expand a specific module or claim/strategy label with full warrant trees |
| `--hole` | Show detailed prior review report for all independent claims (holes without priors + covered with priors) |

What it checks:

- `pyproject.toml` and `[tool.gaia]` metadata exist
- `.gaia/ir.json` matches the current source
- `.gaia/ir_hash` has the expected `sha256:` format
- the compiled IR is accepted by the current schema and validator
- package identity fields such as `name`, `version`, `namespace`, and `uuid` are present and consistent

### `--brief` output

Displays a per-module overview after validation passes:

- **Settings** with label and truncated content
- **Claims** with role (independent/derived/structural/background/orphaned) and prior if set
- **Strategies** with type, premise labels, conclusion, prior, and reason
- **Operators** with type, variables, and reason

### `--show` output

When given a **module name**, expands all claims with full content and strategies with recursive warrant trees (including composite sub-strategies).

When given a **claim or strategy label**, shows that node's full content and all strategies that conclude to it, with premises listed.

When `--brief` and `--show` are combined, both the overview and the expanded detail are shown.

### `--hole` output

Detailed report for prior review. Splits all independent claims into two groups:

- **Holes**: claims without priors — shows QID, content preview, and `NOT SET (defaults to 0.5)` status
- **Covered**: claims with priors — shows prior value and justification reason

The default `gaia check` output also annotates each independent premise with `prior=X` or `⚠ no prior`, and shows a "Holes (no prior set): N" count in the summary when any holes remain.

Example:

```bash
gaia compile .
gaia check .                          # validate + prior annotations on independent claims
gaia check --hole .                   # validate + detailed hole/covered report
gaia check --brief .                  # validate + overview
gaia check --show motivation .        # validate + expand module
gaia check --show hypothesis .        # validate + expand claim
gaia check --brief --show s3_xxx .    # validate + overview + expand module
```

## `gaia register`

Prepare or submit a metadata PR against the official registry for a pushed GitHub-tagged source release.

```bash
gaia register [path] [--tag TAG] [--repo URL] [--registry-dir PATH] [--create-pr]
```

Arguments:

| Argument | Default | Description |
|----------|---------|-------------|
| `path` | `.` | Path to the package repository |

Common options:

| Option | Description |
|--------|-------------|
| `--tag` | Git tag to register. Defaults to `v<version>` |
| `--repo` | Override the GitHub repository URL instead of inferring it from `origin` |
| `--registry-dir` | Path to a local checkout of the registry repo |
| `--create-pr` | Create and push the registry branch and open a PR via GitHub CLI |

Prerequisites:

- `gaia compile` and `gaia check` already pass
- the package source is pushed to GitHub
- the target tag is already pushed
- the registry repo is available locally if metadata needs to be written

Example:

```bash
gaia compile .
gaia check .
git push origin main
git tag v4.0.3
git push origin v4.0.3
gaia register . --tag v4.0.3 --create-pr
```

## Registration Model

The official registry is currently a Phase 1 source registry:

- it records package metadata, version metadata, dependencies, `git_tag`, `git_sha`, and `ir_hash`
- it re-clones the tagged GitHub source in CI
- it recompiles and revalidates before merge
- consumers currently use validated Git references rather than install-by-name

See [../specs/2026-04-02-gaia-registry-design.md](../specs/2026-04-02-gaia-registry-design.md) for the full registry contract.
