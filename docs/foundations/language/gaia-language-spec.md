# Gaia Language Spec (v4)

## Purpose

This document defines the Gaia Language v4 surface: a Typst-based DSL for authoring structured knowledge packages. It covers the package format, declaration types, cross-referencing, extraction mechanism, and conformance rules.

A developer reading this document should be able to write a conforming v4 package from scratch.

## Status and Normative Scope

This document is normative for:

- the v4 package file layout and manifest format
- the declaration type system (`setting`, `question`, `claim`, `action`, `relation`)
- the label and cross-reference conventions
- the cross-package reference mechanism (`gaia-bibliography`)
- the extraction contract (how packages become structured data)
- conformance and well-formedness rules

## Role of Gaia Language

Gaia Language serves five interrelated purposes:

1. **Verifiable agent memory** -- agents externalize reasoning into explicit, reviewable artifacts with structured knowledge objects, explicit reasoning steps, and traceable provenance.

2. **Formalized scientific knowledge** -- typed, modular, composable, uncertainty-aware knowledge representation stable enough for long-term integration.

3. **Publishable research artifact** -- packages act as paper replacements or companions, reviewable in git, readable by humans and agents.

4. **Agent-friendly authoring** -- machine-parsable Typst syntax with deterministic extraction via `typst query`.

5. **Clean path to LKM integration** -- packages map into a global knowledge graph with canonical identity, provenance tracking, contradiction handling, and large-scale belief propagation.

## Non-Goals

- Gaia is not the agent's entire workspace. The published package is the stable artifact, not the full private thought process.
- Gaia is not a general-purpose workflow engine. No `if/else`, loops, or orchestration constructs.
- Package-local names are not global identity. Canonical identity belongs to publish-time integration.
- The published package is not the server's canonical Graph IR. The server derives its own internal representation.

## Package Layout

A conforming v4 package is a directory with the following structure:

```
my_package/
  typst.toml          # package manifest
  lib.typ             # entrypoint: imports runtime, applies style, includes modules
  gaia.typ            # runtime import shim
  motivation.typ      # module file (one or more)
  reasoning.typ       # module file
  gaia-deps.yml       # (optional) cross-package references
```

### `typst.toml` -- Package Manifest

Standard Typst package manifest. Required fields:

```toml
[package]
name = "galileo_falling_bodies"
version = "4.0.0"
entrypoint = "lib.typ"
authors = ["Galileo Galilei"]
description = "Galileo's falling bodies argument"
```

The `name` and `version` fields become the package's identity in the Gaia system.

### `gaia.typ` -- Runtime Import Shim

A single-line file that imports the Gaia runtime library:

```typst
#import "/libs/typst/gaia-lang-v4/lib.typ": *
```

This indirection lets packages resolve the runtime from the repository root via `--root`, without hardcoding absolute paths.

### `lib.typ` -- Entrypoint

The entrypoint imports the runtime, applies document styling, and includes module files in narrative order:

```typst
#import "gaia.typ": *
#show: gaia-style

#include "motivation.typ"
#include "setting.typ"
#include "reasoning.typ"
#include "follow_up.typ"
```

### Module Files (`*.typ`)

Each module file is a Typst document containing knowledge declarations. A module typically begins with `#import "gaia.typ": *` and a heading:

```typst
#import "gaia.typ": *

= Background and Assumptions

#setting[
  A heavy ball $H$ and a light ball $L$ fall from the same height.
] <setting.thought_experiment_env>
```

Module files are the primary authoring surface. They contain narrative prose interspersed with typed knowledge declarations.

## Declaration Types

All declaration types produce `figure(kind: "gaia-node")` elements with hidden metadata. This uniform representation enables extraction via a single `typst query` call.

### `#setting`

A contextual assumption that requires no proof.

```typst
#setting[
  An idealized vacuum environment with no air resistance.
] <setting.vacuum_env>
```

Parameters: none (content body only).

### `#question`

An open question.

```typst
#question[
  Does the rate of falling truly depend on an object's weight?
] <motivation.main_question>
```

Parameters: none (content body only).

### `#claim`

A truth-apt statement. Supports optional `from:` (premises) and `kind:` (subtype).

```typst
// Simple claim with no premises
#claim(kind: "observation")[
  Stones fall faster than feathers in everyday experience.
] <aristotle.everyday_observation>

// Claim with premises and a proof block
#claim(from: (<aristotle.everyday_observation>,))[
  Heavier objects fall faster, in proportion to their weight.
][
  Based on everyday observations @aristotle.everyday_observation,
  heavier objects consistently reach the ground first.
] <aristotle.heavier_falls_faster>
```

Parameters:
- `from: (<label1>, <label2>, ...)` -- tuple of premise labels (optional)
- `kind: "observation"` -- subtype string (optional)
- First content block: the claim statement
- Second content block: the proof/justification (optional)

### `#action`

A procedural step. Same parameter signature as `#claim`.

```typst
#action(from: (<data_source>,), kind: "python")[
  Run statistical analysis on the dataset.
][
  Load the CSV, compute summary statistics, and output results.
] <analysis.run_stats>
```

Parameters: same as `#claim` (`from:`, `kind:`, content body, optional proof block).

### `#relation`

A structural relation between two existing nodes. Currently supports `"contradiction"` and `"equivalence"` types.

```typst
#relation(
  type: "contradiction",
  between: (<galileo.composite_is_slower>, <galileo.composite_is_faster>),
)[
  "HL is slower than H" and "HL is faster than H" contradict each other.
][
  Both predictions derive from the same assumption but yield
  opposite conclusions about the same physical object.
] <galileo.tied_balls_contradiction>
```

Parameters:
- `type: "contradiction"` or `type: "equivalence"` -- required
- `between: (<label_a>, <label_b>)` -- the two nodes being related (required)
- Content body: description of the relation
- Optional proof block

## Labels and Cross-References

### Label Convention

Labels follow the pattern `<filename.label_name>`:

```typst
#setting[...] <setting.vacuum_env>
#claim[...]   <galileo.vacuum_prediction>
```

The `filename.` prefix is a naming convention (not enforced by Typst), chosen so that labels remain unique across module files within a package.

### In-Text References

Use Typst's `@label` syntax to reference other nodes in prose:

```typst
Based on the observation @aristotle.everyday_observation, ...
```

### Premise References

Use angle-bracket labels inside `from:` tuples:

```typst
#claim(from: (<aristotle.everyday_observation>, <setting.vacuum_env>))[...]
```

Note the trailing comma for single-element tuples: `from: (<label>,)`.

## Cross-Package References

To reference knowledge from another package, use `gaia-deps.yml` and `#gaia-bibliography`.

### `gaia-deps.yml`

Declares external knowledge nodes:

```yaml
vacuum_prediction:
  package: "galileo_falling_bodies"
  version: "4.0.0"
  node: "vacuum_prediction"
  type: claim
  content: "In a vacuum, objects of different weights should fall at the same rate."
```

Each entry creates a label (the YAML key) that can be used in `from:` and `@ref` within the package.

### `#gaia-bibliography`

Place this call in the module file that uses external references, before the declarations that reference them:

```typst
#gaia-bibliography(yaml("gaia-deps.yml"))

#claim(from: (<derivation.freefall_acceleration>, <vacuum_prediction>))[
  Newton's mathematical derivation and Galileo's logical argument
  independently reach the same conclusion.
] <derivation.convergence>
```

`#gaia-bibliography` creates hidden `figure(kind: "gaia-ext")` elements for each entry, making the labels resolvable by both Typst's reference system and the extraction pipeline.

## Extraction

Packages are extracted to structured data using Typst's built-in query mechanism. No special export function is needed.

### Local Nodes

```bash
typst query --root <repo-root> lib.typ 'figure.where(kind: "gaia-node")'
```

Each result contains:
- `label` -- the node's identity (e.g., `<galileo.vacuum_prediction>`)
- `supplement` -- the type as display text (`"Setting"`, `"Claim"`, etc.)
- `body` -- content tree with hidden metadata and visible text

The Python loader (`libs/lang/typst_loader.py::load_typst_package_v4`) processes these results into a normalized dict:

```python
{
    "package": "galileo_falling_bodies",
    "version": "4.0.0",
    "dsl_version": "v4",
    "nodes": [
        {"name": "setting.vacuum_env", "type": "setting", "content": "...", "kind": None},
        {"name": "galileo.vacuum_prediction", "type": "claim", "content": "...", "kind": None},
        ...
    ],
    "factors": [
        {"type": "reasoning", "premises": ["aristotle.everyday_observation"], "conclusion": "aristotle.heavier_falls_faster"},
        ...
    ],
    "constraints": [
        {"name": "galileo.tied_balls_contradiction", "type": "contradiction", "between": ["galileo.composite_is_slower", "galileo.composite_is_faster"]},
        ...
    ],
    "refs": [],
    "modules": [],
    "module_titles": {},
}
```

### External Nodes

```bash
typst query --root <repo-root> lib.typ 'figure.where(kind: "gaia-ext")'
```

External nodes are appended to the `nodes` list with `"external": True` and provenance metadata (`ext_package`, `ext_version`, `ext_node`).

## Layer Model

The v4 language separates three semantic layers.

### Knowledge Layer

Defines the type system for knowledge objects:

| Type | Purpose | Has `from:`? | Has `between:`? |
|------|---------|:---:|:---:|
| `setting` | Contextual assumption | No | No |
| `question` | Open question | No | No |
| `claim` | Truth-apt statement | Optional | No |
| `action` | Procedural step | Optional | No |
| `relation` | Structural constraint | No | Yes |

The `kind:` parameter provides further subtyping (e.g., `kind: "observation"` on a claim).

### Structural Layer

Defines how knowledge objects connect:

- **`from:` edges** -- A `claim` or `action` with `from: (<a>, <b>)` declares that `a` and `b` are premises for the conclusion. These become reasoning factors in the Graph IR.
- **`between:` constraints** -- A `relation` with `between: (<a>, <b>)` declares a structural constraint (contradiction or equivalence) between two nodes.

### Probabilistic Layer

Not expressed in the authoring surface. Priors are assigned during the review stage; posteriors are computed by belief propagation over the extracted Graph IR. The language surface provides the graph topology; the probabilistic semantics are layered on top at runtime.

## Lifecycle Model

### Stage A: Local Authoring

The author writes `.typ` files, compiles to PDF for visual review, and iterates. Typst provides instant preview with `typst watch`.

### Stage B: Extraction and Compilation

The pipeline extracts structured data via `typst query`, producing nodes, factors, and constraints. This feeds into Graph IR construction, canonicalization, and storage.

### Stage C: Review and Inference

Review assigns priors and evaluates reasoning quality. Belief propagation runs over the Graph IR to compute posterior beliefs. These are runtime outputs, not part of the authored source.

### Stage D: Integration

Published packages are ingested into the global LKM with canonical identity, provenance tracking, and cross-package BP participation.

## Conformance and Well-Formedness

### Structural Requirements (enforced)

A package is ill-formed if any of the following hold:

- `typst.toml` is missing or lacks a `[package]` section with `name`
- `lib.typ` is missing
- `gaia.typ` does not import the Gaia runtime
- A `from:` label references a label that does not exist in the document
- A `between:` label references a label that does not exist in the document
- A `relation` uses a `type:` other than `"contradiction"` or `"equivalence"` (assertion error at compile time)
- The package fails `typst compile` (syntax errors, unresolved references)

### Semantically Permissive by Design

The following are accepted:

- Packages with no declarations (empty modules)
- Claims without `from:` (standalone assertions)
- Claims without proof blocks
- Unknown `kind:` values on claims and actions (interpreted by the LLM during review)
- Module files that contain only prose with no declarations

### Recommended Lint Rules

- Labels should be unique within a package
- Labels should follow the `filename.label_name` convention
- Every `claim` with `from:` should have a proof block explaining the reasoning
- `gaia-deps.yml` entries should specify `package`, `version`, `node`, `type`, and `content`

## Gaia Runtime Library

The runtime library lives at `libs/typst/gaia-lang-v4/` and exports:

| Symbol | Source file | Purpose |
|--------|------------|---------|
| `setting`, `question`, `claim`, `action`, `relation` | `declarations.typ` | Knowledge declaration functions |
| `gaia-bibliography` | `bibliography.typ` | Cross-package reference registration |
| `gaia-style` | `style.typ` | Document show rules and visual styling |

All declarations produce `figure(kind: "gaia-node")` with hidden `metadata(...)` containing the node's type, `from:` premises, `kind:`, and (for relations) `rel-type` and `between:`.

The `gaia-style` show rule renders each declaration type with a colored left border and type badge, and formats `@ref` links using the label name instead of figure numbering.

## Proof State

After extraction, every node in a package is classified into one of six categories. This classification is the package's **proof state** — a structural completeness report analogous to Lean's goal view.

| Category | Rule | Meaning |
|----------|------|---------|
| **established** | Node is the conclusion of a reasoning factor, or is a relation node | Has proof within this package |
| **assumption** | Node type is `setting` | Contextual choice — no proof needed, but can be challenged or replaced |
| **hole** | Node is used as a premise by some factor, but has no proof in this package | Missing link in the reasoning chain (includes observations without experimental backing) |
| **imported** | Node is marked `external` (from `gaia-bibliography`) | Proof lives in another package |
| **question** | Node type is `question` | Open inquiry — motivates the package but is not a truth claim |
| **standalone** | None of the above | Declared but not referenced and not proven — may indicate an orphaned node |

Key design decisions:

- **Observations are not special-cased.** A `claim(kind: "observation")` follows the same rules as any claim: if it has `from:` it can be established; if it is used as a premise without proof, it is a hole. The `kind` field records the *evidence type* but does not exempt the node from needing proof.
- **Settings are assumptions, not axioms.** A setting can always be challenged by a `relation(type: "contradiction")` in another package. The label "assumption" reflects this: accepted without proof here, but not immune to revision.
- **Axiom systems are future proof views, not node properties.** Gaia does not expose `axiom` as a declaration type or proof-state bucket. If the system later needs alternative starting-point sets for explanation trees, loop cuts, or inference views, those should be represented as explicit `assumption basis` metadata layered on top of the graph.
- **Holes are actionable.** Each hole represents a concrete next step — provide a proof, import from another package, or demote to standalone if the premise link was accidental.

Run `gaia build --proof-state` to generate the proof state report for a package.

## Future Work

The following are not part of the v4 surface but are planned or under consideration:

- `corroboration` relation type (currently modeled as `claim(from:)` instead)
- `dependency: indirect` / context semantics (only `from:` = direct premise exists)
- Action execution runtime (actions are declared but not executed)
- Schema/ground node parameterization in the language surface
- First-class evidence kinds (`observation`, `experiment`, `dataset` as distinct types)
- Explicit schema versioning in source files
- `Gaia.toml` / `gaia.lock` for package dependency management
