# Gaia

[![CI](https://github.com/SiliconEinstein/Gaia/actions/workflows/ci.yml/badge.svg)](https://github.com/SiliconEinstein/Gaia/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/SiliconEinstein/Gaia/graph/badge.svg)](https://codecov.io/gh/SiliconEinstein/Gaia)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Gaia is a knowledge-package authoring toolkit.

As of April 2026, the active author-side workflow is:

```text
author Python package
  -> gaia compile
  -> gaia check
  -> git push + git tag
  -> gaia register
```

The official registry is currently a **GitHub-backed source registry**:

- authors publish tagged source releases in their own GitHub repos
- the registry records metadata such as `repo`, `git_tag`, `git_sha`, `ir_hash`, and dependencies
- registry CI re-clones the tagged source and recompiles it before merge
- Phase 1 does not provide wheel publishing or install-by-name

Older Typst, BP, storage, and server experiments still exist in this repo, but they are not the current Gaia Lang v5 author workflow.

## Install Gaia

To work on Gaia itself:

```bash
uv sync
uv run gaia --help
```

To author a separate Gaia knowledge package, add Gaia as a dependency from a local checkout or Git URL. Until `gaia-lang` is published to a package index, the simplest options are:

```bash
# From a local checkout
uv add --editable /path/to/Gaia

# Or directly from GitHub
uv add git+https://github.com/SiliconEinstein/Gaia.git
```

After that, run the CLI inside the package repo with `uv run gaia ...`.

## Create a Package

### 1. Scaffold a normal Python package

```bash
uv init --lib galileo-falling-bodies-gaia
cd galileo-falling-bodies-gaia
uv add git+https://github.com/SiliconEinstein/Gaia.git
mv src/galileo_falling_bodies_gaia src/galileo_falling_bodies
```

`uv init --lib` creates the recommended `src/` layout. Gaia currently supports both:

- `src/<import_name>/`
- `<import_name>/`

Important: the current Gaia CLI derives `import_name` from `project.name.removesuffix("-gaia")`. For `galileo-falling-bodies-gaia`, the expected import package is therefore `galileo_falling_bodies`, not `galileo_falling_bodies_gaia`.

### 2. Add Gaia package metadata

Edit `pyproject.toml` so it contains:

```toml
[project]
name = "galileo-falling-bodies-gaia"
version = "4.0.3"
description = "Galileo's falling bodies argument"
requires-python = ">=3.12"
# Keep the Gaia dependency entry that `uv add` created in project.dependencies

[tool.gaia]
type = "knowledge-package"
namespace = "reg"
uuid = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
```

Notes:

- `[project].name` must end with `-gaia`
- `[tool.gaia].type` must be `"knowledge-package"`
- `[tool.gaia].uuid` is required for registration
- `namespace` becomes part of each generated QID

### 3. Write package source with the Python DSL

Create `src/galileo_falling_bodies/__init__.py`:

```python
from gaia.lang import claim, deduction, setting

vacuum = setting(
    "The experiment is conducted in a vacuum.",
    provenance=[{"package_id": "paper:galileo-dialogues", "version": "1638"}],
)
observation = claim("Objects of different mass fall at the same rate in a vacuum.")
conclusion = claim("Mass alone does not determine falling speed.")

support = deduction(
    premises=[vacuum, observation],
    conclusion=conclusion,
    steps=[
        {
            "reasoning": "The experiment controls away drag and isolates mass.",
            "premises": [vacuum, observation],
            "conclusion": conclusion,
        }
    ],
    reason="The controlled observation rules out the Aristotelian explanation.",
)


__all__ = ["vacuum", "observation", "conclusion", "support"]
```

The important part is that the module declares `Knowledge` / `Strategy` / `Operator` objects directly. Package identity comes from `pyproject.toml`, not from a `Package(...)` block in the DSL.

Current authoring surface includes:

- `claim()`, `setting()`, `question()`
- `claim(..., given=[...])` as shorthand for a local `noisy_and` support edge
- top-level operators such as `contradiction()` and `equivalence()`
- strategies such as `noisy_and()`, `deduction()`, `abduction()`, `elimination()`, `case_analysis()`, `mathematical_induction()`, and `composite()`
- optional `provenance=[...]` on knowledge declarations
- `steps=[...]` as either simple strings or structured `{reasoning, premises, conclusion}` records

### 4. Compile and validate

```bash
uv run gaia compile .
uv run gaia check .
```

This writes:

```text
.gaia/
  ir.json
  ir_hash
```

What the commands do:

- `gaia compile` executes the Python package, collects `Knowledge` / `Strategy` / `Operator`, and writes a `LocalCanonicalGraph`
- named strategies are formalized through `gaia.ir`'s canonical formalizer at compile time
- `gaia check` recompiles from source and validates schema legality, artifact consistency, and registration preconditions

## Submit to the Official Registry

### 1. Push the package repo to GitHub

Phase 1 registry support is GitHub-only. The package repo must have a GitHub `origin`.

```bash
git add .
git commit -m "Create Gaia package"
git branch -M main
git remote add origin https://github.com/<you>/GalileoFallingBodies.gaia.git
git push -u origin main
```

### 2. Tag the version you want to register

`gaia register` expects:

- a clean git worktree
- `HEAD` to match the version tag being registered
- the tag to already be pushed to `origin`

```bash
git tag v4.0.3
git push origin v4.0.3
```

By default, `gaia register` uses `v<version>` from `pyproject.toml`.

### 3. Create the registry PR

Clone the registry repo locally:

```bash
git clone https://github.com/SiliconEinstein/gaia-registry.git
```

Then from the package repo:

```bash
uv run gaia register . \
  --registry-dir ../gaia-registry \
  --create-pr
```

What `gaia register` does:

- reads package metadata from `pyproject.toml`
- verifies `.gaia/ir_hash` matches the current source
- verifies the worktree is clean
- infers the GitHub repo URL from `origin` unless `--repo` is given
- verifies the target tag exists remotely
- updates registry metadata under `packages/<package-name>/`
- optionally pushes the registry branch and opens a PR when `--create-pr` is set

Useful options:

```bash
# Register a non-default tag
uv run gaia register . --tag v4.0.4 --registry-dir ../gaia-registry

# Override the inferred GitHub repo URL
uv run gaia register . \
  --repo https://github.com/<you>/GalileoFallingBodies.gaia \
  --registry-dir ../gaia-registry
```

`--create-pr` uses GitHub CLI, so you must already be authenticated with `gh auth login`.

### 4. Wait for registry CI

After the PR is opened, registry CI will:

- clone the tagged source release from GitHub
- checkout the registered `git_tag` / `git_sha`
- rerun `gaia compile`
- compare the resulting `ir_hash`
- rerun `gaia check`
- verify Gaia dependencies are already registered

If those checks pass and the PR is merged, that version is officially registered.

## Current CLI

The active CLI surface is:

```text
gaia compile
gaia check
gaia register
```

`gaia build`, `gaia infer`, and `gaia publish` belong to older experiments and are not part of the current Gaia Lang v5 author workflow.

## Code Map

| Path | Purpose |
|------|---------|
| `gaia/lang/` | Python DSL runtime and compiler input model |
| `gaia/ir/` | IR schema, validation, and lowering helpers |
| `gaia/cli/` | `compile`, `check`, `register` commands |
| `tests/gaia/lang/` | DSL and compiler tests |
| `tests/cli/` | CLI tests |

## Documentation

| Path | Content |
|------|---------|
| [docs/specs/2026-04-02-gaia-lang-v5-python-dsl-design.md](docs/specs/2026-04-02-gaia-lang-v5-python-dsl-design.md) | Current Gaia Lang Phase 1 package model and CLI |
| [docs/specs/2026-04-03-gaia-lang-future-extensions-design.md](docs/specs/2026-04-03-gaia-lang-future-extensions-design.md) | Future parameterization, rendering, and inference-adjacent design |
| [docs/specs/2026-04-02-gaia-registry-design.md](docs/specs/2026-04-02-gaia-registry-design.md) | Phase 1 source-registry design |
| [docs/for-users/cli-commands.md](docs/for-users/cli-commands.md) | User-facing CLI command reference |

## Testing

```bash
pytest
ruff check .
ruff format --check .
```
