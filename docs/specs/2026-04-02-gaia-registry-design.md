# Gaia Official Registry - Phase 1 Design

> **Status:** Target design
>
> **Depends on:** [Gaia Lang v5](2026-04-02-gaia-lang-v5-python-dsl-design.md), [Gaia IR v2](../foundations/gaia-ir/02-gaia-ir.md), [Ecosystem](../foundations/ecosystem/)
>
> **Phase 1 scope:** Package registration + CI validation for GitHub-backed source releases. Review system deferred. Distribution/install infrastructure deferred.

## 1. Overview

The Gaia Official Registry is a metadata-only GitHub repository. In Phase 1 it behaves like a **source registry**, not an installable package index.

What the registry records:
- package identity: `uuid`, `name`
- source location: GitHub repository URL
- version identity: semantic version, git tag, pinned git SHA
- content identity: `ir_hash`
- dependency metadata: Gaia package dependencies declared in `pyproject.toml`

What the registry does **not** do in Phase 1:
- host wheels
- publish a PEP 503 `simple/` index
- guarantee `uv add <package-name>` by package name alone

### 1.1 Architecture

```
                   +------------------------------------+
                   |     Registry Repo (GitHub)         |
                   |                                    |
                   |  packages/                         |
                   |    galileo-falling-bodies/         |
                   |      Package.toml                  |
                   |      Versions.toml                 |
                   |      Deps.toml                     |
                   |                                    |
                   |  .github/workflows/                |
                   |    register.yml                    |
                   +------------------------------------+
                             ^
                             |
                        PR (register)
                             |
                          Authors


         +-----------------------------------------------+
         |  Package Repo (GitHub, author-controlled)     |
         |    pyproject.toml                             |
         |    package source                             |
         |    .gaia/ir.json                              |
         |    .gaia/ir_hash                              |
         |    git tag vX.Y.Z                             |
         +-----------------------------------------------+
```

### 1.2 Key Properties

| Property | Implementation |
|----------|----------------|
| Source of truth | Author's GitHub repo + pushed git tag |
| Registry role | Index + validation metadata only |
| Trust chain | Registry CI recompiles and validates source by pinned SHA |
| Decentralized authoring | Registry stores metadata, not package source |
| Zero extra infrastructure | GitHub repo + GitHub Actions |
| Auditable | Every registration is a git commit and CI run |
| Future-compatible | New source kinds can be added later without changing the package model |

> **Phase 1 deviation from ecosystem foundation:** The ecosystem doc (`04-registry-operations.md`) states that review is a precondition for registry entry. Phase 1 intentionally relaxes this to bootstrap the package graph. Structural integrity is verified, but no epistemic review gate is enforced yet.

## 2. Registry Repo Structure

```
gaia-registry/
├── packages/
│   ├── galileo-falling-bodies/
│   │   ├── Package.toml
│   │   ├── Versions.toml
│   │   └── Deps.toml
│   └── ...
├── .github/
│   └── workflows/
│       └── register.yml
├── scripts/
│   └── ...
├── registry.toml
└── README.md
```

### 2.1 Package Metadata

**Package.toml** - one per package, created at first registration:

```toml
uuid = "336ed68f-0bac-5ca0-87d4-7b16caf5d00b"
name = "galileo-falling-bodies"
pypi_name = "galileo-falling-bodies-gaia"
repo = "https://github.com/kunyuan/GalileoFallingBodies.gaia"
description = "Galileo's falling bodies argument"
created_at = "2026-04-02T10:00:00Z"
```

`pypi_name` is retained as the canonical package distribution name, even though Phase 1 does not yet expose a wheel index.

**Versions.toml** - appended with each new version:

```toml
[versions."4.0.0"]
ir_hash = "sha256:a1b2c3d4..."
git_tag = "v4.0.0"
git_sha = "abc123def456..."
registered_at = "2026-04-02T10:30:00Z"

[versions."4.1.0"]
ir_hash = "sha256:e5f6g7h8..."
git_tag = "v4.1.0"
git_sha = "789abc012def..."
registered_at = "2026-04-10T15:00:00Z"
```

Notes:
- `ir_hash` uses the same `sha256:...` form emitted by `gaia compile`
- `git_sha` is the immutable source pin used by consumers and future automation
- no wheel metadata appears in Phase 1

**Deps.toml** - Gaia package dependencies per version:

```toml
[deps."4.0.0"]
"aristotle-mechanics-gaia" = ">= 1.0.0"

[deps."4.1.0"]
"aristotle-mechanics-gaia" = ">= 1.0.0"
"newton-mechanics-gaia" = ">= 2.0.0"
```

`Deps.toml` is derived from `pyproject.toml` by filtering to `*-gaia` dependencies only. `gaia register` generates it automatically. Registry CI verifies consistency.

### 2.2 Global Config

```toml
[registry]
name = "Gaia Official Registry"
repo = "https://github.com/SiliconEinstein/gaia-registry"
kind = "source-registry"
default_source_kind = "github"

[policy]
new_package_wait_hours = 72
version_update_wait_hours = 1
require_review = false
min_review_count = 0
```

## 3. Registration Flow

### 3.1 Author Workflow

```bash
cd ~/my-package
# ... edit package source ...
gaia compile .
gaia check .
git add . && git commit -m "Prepare v1.0.0"
git push origin main
git tag v1.0.0
git push origin v1.0.0
gaia register
```

Phase 1 only accepts a release if:
1. source is already pushed to GitHub
2. the registration tag exists
3. the tag is pushed
4. the tag resolves to the exact commit being registered

### 3.2 `gaia register`

`gaia register` automates PR creation:

1. read `pyproject.toml` for package metadata (`[project]` + `[tool.gaia].uuid`)
2. read `.gaia/ir_hash`
3. verify the git worktree is clean
4. verify the registration tag exists, points to `HEAD`, and is pushed
5. infer the GitHub repo URL from `origin` unless explicitly overridden
6. write or update `Package.toml`, `Versions.toml`, and `Deps.toml`
7. prepare a registry PR

Phase 1 source support is intentionally narrow: the release being registered must come from a **GitHub repository + pushed git tag**. Future phases may add other source kinds, such as PyPI sdists.

### 3.3 Registration PR Payload

PR body example:

```markdown
## Register: galileo-falling-bodies-gaia v4.0.0

- Repository: https://github.com/kunyuan/GalileoFallingBodies.gaia
- Tag: v4.0.0
- IR Hash: sha256:a1b2c3d4...

### Exported claims
- `vacuum_prediction` - In a vacuum, objects of different mass fall at the same rate.
- `air_resistance` - Observed speed differences are caused by air resistance.

### Dependencies
- aristotle-mechanics-gaia >= 1.0.0
```

## 4. CI Validation (`register.yml`)

Phase 1 uses two jobs:
- an **untrusted sandbox** that executes author code
- a **trusted gate** that only reads metadata and validation results

This split exists because `gaia compile` imports author Python code.

### 4.1 Sandbox Validation

The sandbox job:
1. parses the proposed registry metadata
2. clones the package repo
3. checks out the declared git tag or pinned git SHA
4. resolves the actual `git_sha`
5. installs the Gaia CLI/runtime needed for compilation
6. runs `gaia compile .`
7. compares the resulting `.gaia/ir_hash` with the declared registry `ir_hash`
8. runs `gaia check .`
9. verifies all Gaia dependencies in `pyproject.toml` are already registered

### 4.2 Trusted Gate

The trusted job does not execute author code. It:
- verifies UUID uniqueness for new packages
- verifies package ownership or authorization policy
- records the validated `git_sha` into `Versions.toml` if needed
- labels the PR and applies waiting-period policy

### 4.3 Waiting Policy

| Scenario | Waiting period | Rationale |
|----------|----------------|-----------|
| New package | 72 hours | Community review window |
| Version update | 1 hour | Lower operational risk |

## 5. Consumer Workflow

Phase 1 consumers use the registry as a **source discovery layer**.

The registry answers:
- what the package is called
- which GitHub repo is canonical
- which tag and git SHA correspond to a version
- which Gaia dependencies that version declares

### 5.1 Installing or Pinning a Registered Package

Consumers can install directly from the pinned source:

```bash
uv add "galileo-falling-bodies-gaia @ git+https://github.com/kunyuan/GalileoFallingBodies.gaia@b8c88fdf7b06a17559941a2741472b5b50af3e20"
```

That is less convenient than `uv add galileo-falling-bodies-gaia`, but it preserves the correct trust model while Phase 1 remains source-only.

### 5.2 Future UX Layer

Phase 1 does not require it, but Gaia may later add a convenience command such as:

```bash
gaia add galileo-falling-bodies
```

Internally, that command would resolve the package through registry metadata and then write the correct GitHub direct reference into `pyproject.toml`.

## 6. Trust Model

### 6.1 Guarantees

Phase 1 guarantees:
- every registered version points to a concrete GitHub repo and immutable git SHA
- registry CI can recompile the source and verify the declared `ir_hash`
- author code never executes in a job with registry write permissions
- registry metadata remains auditable and forkable

### 6.2 What Phase 1 Does Not Guarantee

| Not guaranteed | Why | Future phase |
|---|---|---|
| Scientific quality | No review gate yet | Phase 2 |
| Probability values verified | No parameterization review | Phase 2 |
| Name-only installs via `uv add` | No wheel/index distribution | Later installable registry phase |
| PyPI-backed source support | GitHub is the only source kind | Later multi-source phase |

### 6.3 Limitations

- public GitHub repos only
- no review-based admission yet
- no distribution artifacts or GitHub Pages package index yet
- package consumers may need explicit Git direct references until a Gaia UX wrapper exists

## 7. CLI Surface

```bash
# Author-side
gaia compile
gaia check
gaia register

# Registry-side
register.yml   # validate PRs against source repo + tag + ir_hash
```

No author-side `gaia publish` exists in Phase 1.

## 8. Phase 2+ Extension Points

### 8.1 Review Gate

Later phases can require:
- reviewer assignment
- signed review reports
- parameterization validation

### 8.2 Additional Source Kinds

The registry object model is intentionally source-descriptor based. After GitHub-only Phase 1, new handlers can be added:
- `github`
- `pypi-sdist`
- other audited source providers

### 8.3 Installable Registry

A later phase may add:
- wheel builds
- GitHub Releases
- `simple/` index generation
- package-name installs via `uv add`

Those capabilities are explicitly out of scope for Phase 1.

## 9. Example End-to-End

```bash
# Author side
uv init --lib my-research-gaia
uv add gaia-lang
uv add "galileo-falling-bodies-gaia @ git+https://github.com/kunyuan/GalileoFallingBodies.gaia@v4.0.1"

gaia compile .
gaia check .
git add . && git commit -m "Initial release"
git push origin main
git tag v1.0.0
git push origin v1.0.0
gaia register

# Registry CI
# 1. Clone package repo
# 2. Checkout tag / pin git_sha
# 3. gaia compile . and compare ir_hash
# 4. gaia check .
# 5. Verify Gaia deps are already registered
# 6. Approve / merge after policy wait

# Consumer side
uv add "my-research-gaia @ git+https://github.com/author/MyResearch.gaia@<validated-git-sha>"
```
