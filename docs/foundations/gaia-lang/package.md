---
status: current-canonical
layer: gaia-lang
since: v0.5
---

# Gaia Lang Package Model

A Gaia knowledge package is a standard Python library that declares knowledge (claims, notes, questions), reasoning actions, and logical operators using the Gaia Lang DSL. This document defines how packages are structured, configured, named, and what artifacts they produce. For the conceptual model behind the surface, see [knowledge-and-reasoning.md](knowledge-and-reasoning.md).

## Package Creation

### `gaia build init`

```bash
gaia build init galileo-falling-bodies-gaia
cd galileo-falling-bodies-gaia
```

This wraps `uv init --lib` to scaffold a standard Python library, then patches `pyproject.toml` to add `[tool.hatch.build.targets.wheel]` (so the renamed `src/<import_name>/` is picked up) and `[tool.gaia]` with a generated UUID. It also writes a v0.5 DSL template to `__init__.py`, appends Gaia ignore patterns to `.gitignore`, and runs `uv add gaia-lang`. Package name must end with `-gaia`.

The generated `__init__.py` template uses the v0.5 action surface:

```python
from gaia.engine.lang import claim, derive, note

context = note("Background context for this package.")
hypothesis = claim("A scientific hypothesis.")
prediction = derive(
    "A testable prediction follows from the hypothesis.",
    given=hypothesis,
    background=[context],
    rationale="Explain why the hypothesis entails this prediction.",
)

__all__ = ["hypothesis", "prediction"]
```

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
| `dependencies` | List. | Declare `*-gaia` packages here for cross-package knowledge references. Non-Gaia dependencies are allowed but ignored by the compiler. `gaia-lang` itself is the runtime distribution; in v0.5 it brings the full DSL surface (`gaia.engine.lang`) plus the Bayes peer module (`gaia.engine.bayes`) — see [bayes.md](bayes.md) for the import contract. |

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
│       ├── reasoning.py         # Reasoning actions (derive / observe / infer / relations / ...)
│       └── priors.py            # Prior records via register_prior(...)
└── .gaia/                       # Compiled artifacts (git-tracked)
    ├── ir.json                  # LocalCanonicalGraph JSON
    ├── ir_hash                  # SHA-256 integrity hash
    ├── compile_metadata.json    # gaia-lang version + compile timestamp
    ├── formalization_manifest.json
    └── manifests/
        ├── exports.json
        ├── premises.json
        ├── holes.json
        └── bridges.json
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

Visibility has two separate concepts: what is **compiled** into the local graph
and what is **exported** as the cross-package interface.

| Level | Mechanism | Effect |
|-------|-----------|--------|
| **Exported** | Listed in the package root `__all__` | Cross-package visible. Exported labels appear in `exports.json` and release manifests. |
| **Compiled local declaration** | Any local Gaia object registered during import of the package root or source modules | Compiled into IR and labelable from its Python variable name, even when not exported. |
| **Anonymous helper** | Generated helper or object without an assignable module variable | Compiled with generated or anonymous identity. |

Labels are assigned automatically from loaded module variable names during
package loading. `__all__` does not limit discovery or compilation; it marks the
exported interface. The label then forms the final segment of the object's QID.
Action labels are addressable via `[@label]` references the same way Knowledge
labels are; see [knowledge-and-reasoning.md §4.3](knowledge-and-reasoning.md#43-action-label-references).

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
from gaia.engine.lang import claim, derive
from aristotle_mechanics import natural_motion

hypothesis = claim("Heavy objects fall faster.")
derive(hypothesis, given=natural_motion,
       rationale="Aristotle's natural-motion doctrine entails it.")
```

At compile time, imported Knowledge objects retain their foreign QIDs (e.g., `github:aristotle_mechanics::natural_motion`). The local graph records both owned and foreign QIDs. See [../gaia-ir/03-identity-and-hashing.md](../gaia-ir/03-identity-and-hashing.md) for the ownership vs. reference distinction.

## Priors

Prior probabilities for BP inference are assigned through `priors.py`. The file
imports existing independent probabilistic input claims and calls
`register_prior(...)` on them. Each call records a source-specific prior record;
the compile-time resolution policy chooses the winning value and preserves all
records for audit.

The v0.5 contract is:

- assign external priors only to independent inputs that are load-bearing for exported goals;
- do not assign external priors to zero-premise `observe(...)` claims; they are pinned to `1 - CROMWELL_EPS`;
- do not assign priors to derived claims, structural expression helpers, relation helper claims, or generated formalization helpers;
- use `gaia build check --hole` to decide which independent degrees of freedom are covered and which intentionally rely on MaxEnt.

Legacy strategy/operator APIs may still accept paired `reason+prior` arguments for compatibility. New packages should prefer `register_prior(...)` in `priors.py` for input priors and action/relation verbs for warrants.

### priors.py

```python
# src/<package>/priors.py
from gaia.engine.lang import register_prior

from . import evidence, hypothesis

register_prior(
    evidence,
    0.9,
    justification="Direct observation.",
)

register_prior(
    hypothesis,
    0.65,
    justification="Sourced model prior from a domain review.",
)
```

`apply_package_priors()` discovers `priors.py` automatically at load time. The
import runs `register_prior(...)` calls, then Gaia applies the package
`RESOLUTION_POLICY` or the default policy and injects the winning prior into
claim metadata before compilation. Do not export the removed legacy
`PRIORS = {...}` dict; v0.5+ rejects it with a migration error.

### Removed Review Sidecar

The old review sidecar pattern (`ReviewBundle` / `review_claim()` /
`review_strategy()` in `review.py` or `reviews/<name>.py`) has been removed
from the active authoring surface. Use `priors.py` for independent input
priors, and model warrants with current action/relation verbs.

## Build Artifacts

All artifacts are written to `.gaia/` within the package root.

| Artifact | Written by | Tracked in git? | Contents |
|----------|-----------|-----------------|----------|
| `.gaia/ir.json` | `gaia build compile` | yes | `LocalCanonicalGraph` -- the complete compiled IR |
| `.gaia/ir_hash` | `gaia build compile` | yes | SHA-256 hash of the canonical IR serialization |
| `.gaia/compile_metadata.json` | `gaia build compile` | yes | `gaia_lang_version`, compile timestamp, and IR hash provenance |
| `.gaia/formalization_manifest.json` | `gaia build compile` | yes | Scaffold/formalization records such as `depends_on(...)`, `candidate_relation(...)`, and `materialize(...)` |
| `.gaia/manifests/exports.json` | `gaia build compile` | yes | Exported claims and interface hashes |
| `.gaia/manifests/premises.json` | `gaia build compile` | yes | Public premise interface, including local holes and foreign dependencies |
| `.gaia/manifests/holes.json` | `gaia build compile` | yes | `local_hole` subset of `premises.json` |
| `.gaia/manifests/bridges.json` | `gaia build compile` | yes | `fills(...)` bridge records |
| `.gaia/beliefs.json` | `gaia run infer` | no (gitignored) | BP inference output: posterior beliefs per knowledge node |
| `.gaia/dep_beliefs/` | `gaia pkg add` | no (gitignored) | cached posterior beliefs from upstream `*-gaia` dependencies |

The compile artifacts must travel with the source so that registry clients can
verify the compiled graph and cross-package interface. The inference outputs
are reproducible from source + priors and are intentionally regenerated.
`gaia build init` writes the ignore patterns for local belief caches automatically.

## Package Lifecycle

```
init --> authored --> compiled --> checked --> priors assigned --> inferred --> tagged --> registered
```

| Stage | Command | What happens |
|-------|---------|-------------|
| **Init** | `gaia build init <name>` | Scaffolds package directory, `pyproject.toml`, `src/` layout, and DSL template. |
| **Authored** | (manual) | DSL declarations written in Python modules. |
| **Compiled** | `gaia build compile` | Source is imported, declarations collected, IR emitted to `.gaia/ir.json`. The IR is validated against the Gaia IR schema before writing. |
| **Checked** | `gaia build check` | Validates naming (`-gaia` suffix), IR structural correctness, and artifact freshness (ir_hash matches current source). |
| **Priors assigned** | (manual) | Write `priors.py` assigning priors to independent probabilistic inputs. Use `gaia build check --hole` to identify uncovered independent degrees of freedom. |
| **Inferred** | `gaia run infer` | Loads priors from metadata, lowers IR to factor graph, runs BP, writes beliefs to `.gaia/beliefs.json`. |
| **Tagged** | `git tag v<version> && git push origin v<version>` | A git tag marks the release. The tag must point to HEAD and be pushed to origin before registration. |
| **Registered** | `gaia pkg register` | Prepares (or submits) a metadata PR against the official Gaia registry. Requires a valid `[tool.gaia].uuid`, clean git worktree, and pushed tag. |

`gaia pkg register` creates registry metadata (`Package.toml`, `Versions.toml`,
`Deps.toml`) that reference the GitHub-tagged source release, and writes release
interface files under `packages/<name>/releases/<version>/`. Those release
files are `exports.json`, `premises.json`, `holes.json`, `bridges.json`, and
an exported-only `beliefs.json` generated by local inference at registration
time.

### Validation summary (`gaia build check`)

The check command validates three categories:

**Object-level:** Every Knowledge has a valid type and non-empty content.

**Graph-level:** All referenced IDs exist; strategy and action premises / conclusions are Claims (not Notes or Questions); decomposition graphs have no cycles and every atomic part appears in the formula exactly once; no cyclic strategy / operator dependencies; ID uniqueness; Knowledge labels and Action labels do not collide within the same package.

**Artifact-level:** `.gaia/ir_hash` matches current source compilation, `.gaia/ir.json` is consistent.
