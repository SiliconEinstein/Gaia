---
status: current-canonical
layer: gaia-lang
since: v5-phase-1
---

# Gaia Lang Package Model

A Gaia knowledge package is a standard Python library that declares knowledge (claims, settings, questions), reasoning strategies, and logical operators using the Gaia Lang DSL. This document defines how packages are structured, configured, named, and what artifacts they produce.

## Package Creation

### `gaia init`

```bash
gaia init galileo-falling-bodies-gaia
cd galileo-falling-bodies-gaia
```

This scaffolds the complete package: `pyproject.toml` (with `[tool.gaia]` config and a generated UUID), the `src/` directory layout, a DSL template in `__init__.py`, and `.gitignore` with `.gaia/` entry. Package name must end with `-gaia`.

## pyproject.toml Structure

A complete example:

```toml
[project]
name = "galileo-falling-bodies-gaia"
version = "4.0.0"
description = "Galileo's falling bodies argument"
authors = [{name = "Galileo Galilei"}]
requires-python = ">=3.12"
dependencies = [
    "gaia-lang >= 2.0.0",
    "aristotle-mechanics-gaia >= 1.0.0",
]

[tool.gaia]
type = "knowledge-package"
uuid = "336ed68f-0bac-5ca0-87d4-7b16caf5d00b"
```

### `[project]` section

| Field | Requirement | Notes |
|-------|-------------|-------|
| `name` | Required. Must end with `-gaia`. | Used as the PyPI distribution name. The import name is derived by stripping the `-gaia` suffix and converting hyphens to underscores. |
| `version` | Required. Semantic versioning. | See [Version Semantics](#version-semantics) below. |
| `description` | Optional. | Included in registry metadata if present. |
| `dependencies` | List. | Declare `*-gaia` packages here for cross-package knowledge references. Non-Gaia dependencies are allowed but ignored by the compiler. |

### `[tool.gaia]` section

| Field | Requirement | Notes |
|-------|-------------|-------|
| `type` | Required. Must be `"knowledge-package"`. | The CLI rejects any other value. |
| `namespace` | Optional. Defaults to `"github"`. | Used in QID generation: `{namespace}:{package_name}::{label}`. Identifies the knowledge source (e.g., `github` for the official registry, `paper` for literature extraction). Generally not needed — the default `github` is correct for registry-bound packages. See [../gaia-ir/03-identity-and-hashing.md](../gaia-ir/03-identity-and-hashing.md). |
| `uuid` | Required for registration. | A UUID that uniquely identifies this package in the registry. Generate with `python -c "import uuid; print(uuid.uuid4())"`. Not required during local development. |

## Naming Convention

Gaia uses a Julia-style three-tier naming convention with a `-gaia` / `.gaia` suffix:

| Layer | Format | Example |
|-------|--------|---------|
| GitHub repo | `CamelCase.gaia` | `GalileoFallingBodies.gaia` |
| PyPI package | `kebab-case-gaia` | `galileo-falling-bodies-gaia` |
| Python import | `snake_case` (no suffix) | `galileo_falling_bodies` |
| Source directory | `snake_case/` | `galileo_falling_bodies/` |

The import name is mechanically derived from the PyPI name:

```
galileo-falling-bodies-gaia  -->  strip "-gaia"  -->  replace "-" with "_"  -->  galileo_falling_bodies
```

This derivation is performed by the CLI and runtime; it is not configurable.

## Directory Layout

### `src/` layout (recommended)

```
galileo-falling-bodies-gaia/
├── pyproject.toml
├── src/
│   └── galileo_falling_bodies/
│       ├── __init__.py          # Package entry: exports + DSL declarations
│       ├── premises.py          # Background knowledge and observations
│       ├── reasoning.py         # Reasoning strategies
│       └── reviews/
│           └── self_review.py   # Review sidecar (see below)
└── .gaia/                       # Compiled artifacts (git-tracked)
    ├── ir.json                  # LocalCanonicalGraph JSON
    └── ir_hash                  # SHA-256 integrity hash
```

### Flat layout (also supported)

```
galileo-falling-bodies-gaia/
├── pyproject.toml
├── galileo_falling_bodies/
│   ├── __init__.py
│   └── ...
└── .gaia/
```

The CLI auto-detects which layout is in use by checking whether `<import_name>/` or `src/<import_name>/` exists, in that order.

## Visibility

Three visibility levels control what the compiler exports and how labels are assigned:

| Level | Mechanism | Effect |
|-------|-----------|--------|
| **Exported** | Listed in `__all__` | Cross-package visible. Variable name becomes the label. Compiled into IR. |
| **Public** | No `_` prefix, not necessarily in `__all__` | Package-internal. Variable name becomes the label. Compiled into IR. |
| **Private** | `_` prefix | Not labeled by the CLI. Still compiled into IR as anonymous nodes. Local helpers only. |

Labels are assigned automatically from variable names during package loading. If a `Knowledge` or `Strategy` object is bound to a module-level variable and listed in `__all__` (or is public with no `__all__`), its variable name becomes its `.label` field. The label then forms the final segment of the object's QID.

Example:

```python
# galileo_falling_bodies/__init__.py
from .reasoning import vacuum_prediction, air_resistance_hypothesis

__all__ = ["vacuum_prediction", "air_resistance_hypothesis"]
```

These two claims become:
- `github:galileo_falling_bodies::vacuum_prediction`
- `github:galileo_falling_bodies::air_resistance_hypothesis`

## Version Semantics

Follows semver, defined by knowledge evolution:

| Change | Version level | Example |
|--------|--------------|---------|
| Typo fix, metadata update | PATCH | 1.0.0 -> 1.0.1 |
| New claims/strategies added, existing exports unchanged | MINOR | 1.0.0 -> 1.1.0 |
| Exported claim semantics changed, deletions, restructuring | MAJOR | 1.0.0 -> 2.0.0 |

## Cross-Package Dependencies

Cross-package references use standard Python imports from installed `*-gaia` packages:

```toml
# pyproject.toml
[project]
dependencies = [
    "aristotle-mechanics-gaia >= 1.0.0",
]
```

```python
# galileo_falling_bodies/reasoning.py
from aristotle_mechanics import natural_motion

hypothesis = claim("Heavy objects fall faster.", given=[natural_motion])
```

At compile time, imported Knowledge objects retain their foreign QIDs (e.g., `github:aristotle_mechanics::natural_motion`). The local graph records both owned and foreign QIDs. See [../gaia-ir/03-identity-and-hashing.md](../gaia-ir/03-identity-and-hashing.md) for the ownership vs. reference distinction.

## Review Sidecar

A review sidecar provides prior probabilities and strategy parameters for BP inference. Each sidecar module exports a single `REVIEW = ReviewBundle(...)`.

### Discovery rules

| Convention | Path | Module name |
|------------|------|-------------|
| Single review (legacy) | `<import_name>/review.py` | `<import_name>.review` |
| Multi-review | `<import_name>/reviews/<name>.py` | `<import_name>.reviews.<name>` |

If both conventions are present, all sidecars are collected. If multiple sidecars exist, `gaia infer --review <name>` is required to select one.

### ReviewBundle contents

```python
from gaia.review import ReviewBundle, review_claim, review_strategy

REVIEW = ReviewBundle(
    source_id="self_review",
    objects=[
        review_claim(evidence, prior=0.9, judgment="strong",
                     justification="Direct observation."),
        review_strategy(support, conditional_probability=0.85,
                        judgment="good", justification="Evidence supports hypothesis."),
    ],
)
```

A `ReviewBundle` contains:
- `objects` -- a list of `ClaimReview`, `GeneratedClaimReview`, and `StrategyReview` instances
- `source_id` -- identifies the review source (default: `"self_review"`)
- `model`, `policy`, `config` -- optional metadata for parameterization provenance

## Build Artifacts

All artifacts are written to `.gaia/` within the package root.

| Artifact | Written by | Contents |
|----------|-----------|----------|
| `.gaia/ir.json` | `gaia compile` | `LocalCanonicalGraph` -- the complete compiled IR |
| `.gaia/ir_hash` | `gaia compile` | SHA-256 hash of the canonical IR serialization |
| `.gaia/reviews/<name>/parameterization.json` | `gaia infer` | Resolved review: priors, strategy params, source metadata |
| `.gaia/reviews/<name>/beliefs.json` | `gaia infer` | BP inference output: posterior beliefs per knowledge node |

The `.gaia/` directory should be git-tracked so that compiled artifacts travel with the source. Add `__pycache__/` and `*.pyc` to `.gitignore`, but not `.gaia/`.

## Package Lifecycle

```
init --> authored --> compiled --> checked --> reviewed --> inferred --> tagged --> registered
```

| Stage | Command | What happens |
|-------|---------|-------------|
| **Init** | `gaia init <name>` | Scaffolds package directory, `pyproject.toml`, `src/` layout, and DSL template. |
| **Authored** | (manual) | DSL declarations written in Python modules. |
| **Compiled** | `gaia compile` | Source is imported, declarations collected, IR emitted to `.gaia/ir.json`. The IR is validated against the Gaia IR schema before writing. |
| **Checked** | `gaia check` | Validates naming (`-gaia` suffix), IR structural correctness, and artifact freshness (ir_hash matches current source). |
| **Reviewed** | (manual) | Write a review sidecar (`reviews/<name>.py`) assigning priors to claims and parameters to leaf strategies. CompositeStrategy does not need parameters — its CPT is derived from sub-strategies automatically. |
| **Inferred** | `gaia infer` | Loads review sidecar, lowers IR to factor graph (folding composites to derived CPTs), runs BP, writes beliefs to `.gaia/reviews/<name>/beliefs.json`. |
| **Tagged** | `git tag v<version> && git push origin v<version>` | A git tag marks the release. The tag must point to HEAD and be pushed to origin before registration. |
| **Registered** | `gaia register` | Prepares (or submits) a metadata PR against the official Gaia registry. Requires a valid `[tool.gaia].uuid`, clean git worktree, and pushed tag. |

`gaia register` does not publish artifacts directly. It creates registry metadata (Package.toml, Versions.toml, Deps.toml) that reference the GitHub-tagged source release.

### Validation summary (`gaia check`)

The check command validates three categories:

**Object-level:** Every Knowledge has a valid type and non-empty content.

**Graph-level:** All referenced IDs exist, strategy premises/conclusions are claims (not settings or questions), no cyclic dependencies, ID uniqueness.

**Artifact-level:** `.gaia/ir_hash` matches current source compilation, `.gaia/ir.json` is consistent.
