# Package Model

> **Status:** Current canonical

This document defines the four structural layers of a Gaia knowledge container: Package, Module, Knowledge, and Chain.

## Package

A Package is a complete, versioned knowledge container. It is analogous to a git repository or a published paper.

- **Identity**: `(package_id, version)` -- semver string (e.g., `"4.0.0"`).
- **Authored form**: a Typst project directory with `typst.toml` manifest, `lib.typ` entrypoint, and module files.
- **Storage form**: a `Package` Pydantic model with `package_id`, `name`, `version`, `modules[]`, `exports[]`, `submitter`, `status`.
- **Status values**: `preparing` | `submitted` | `merged` | `rejected`.

A package is the unit of submission, review, and integration. Packages are ingested atomically -- all modules succeed or none do.

## Module

A Module is a logical grouping within a package. In the authoring surface, each `.typ` file (other than `lib.typ` and `gaia.typ`) is implicitly a module.

- **Identity**: `module_id` scoped to the package.
- **Roles**: `reasoning` | `setting` | `motivation` | `follow_up_question` | `other`.
- **Contains**: references to knowledge objects and chains (`chain_ids[]`, `export_ids[]`).
- **Imports**: cross-module dependencies via `ImportRef(knowledge_id, version, strength)`.

Modules exist for organizational clarity. They do not create independent BP boundaries -- all knowledge within a package participates in the same factor graph.

## Knowledge

A Knowledge object is a versioned proposition -- the fundamental unit of the knowledge graph.

- **Identity**: `(knowledge_id, version)`. The `knowledge_id` is scoped to the package; the version is an integer that increments with edits.
- **Type**: `claim | question | setting | action | contradiction | equivalence` (see `docs/foundations/gaia-concepts/knowledge-types.md`).
- **Content**: the proposition text.
- **Prior**: author-assigned plausibility in (epsilon, 1 - epsilon), required for BP-bearing types.
- **Parameters**: optional list of `Parameter(name, constraint)` for schema/universal nodes. A knowledge object with non-empty parameters is a schema node representing a universally quantified proposition.
- **Keywords**: extracted terms for search.

The graph store uses composite IDs `knowledge_id@version` for node identity.

## Chain

A Chain is a display-layer multi-step reasoning structure. Each chain represents one complete reasoning unit from premises to conclusion.

- **Identity**: `chain_id` scoped to the module.
- **Type**: `deduction | induction | abstraction | contradiction | retraction | equivalence`.
- **Steps**: ordered list of `ChainStep(step_index, premises[], reasoning, conclusion)`. Each step connects premise `KnowledgeRef`s to a conclusion `KnowledgeRef`.
- **Factor mapping**: each Chain produces one factor in the Graph IR. The factor's premises are the union of all step premises; the conclusion is the last step's conclusion. Intermediate steps are internal to the factor.

Chains are the bridge between the authored reasoning narrative and the Graph IR factor graph. The chain preserves the author's multi-step argument; the factor collapses it into a single constraint for BP.

## Package Lifecycle

```
authored   -> author writes Typst source
built      -> gaia build: deterministic lowering to Graph IR (raw + local canonical)
inferred   -> gaia infer: local BP preview with local parameterization
published  -> gaia publish: submitted to registry for peer review
reviewed   -> peer review engine evaluates; rebuttal cycle if needed
curated    -> approved package merged into global graph; CanonicalBindings assigned
```

> **Aspirational**: the full peer review cycle (review -> rebuttal -> editor verdict) and global canonicalization with `CanonicalBinding` records are target architecture. Current implementation supports local `gaia publish --local` with simplified global canonicalization via embedding similarity.

## Relationship Between Layers

```
Package (1)
  contains -> Module (1..n)
    contains -> Knowledge (0..n)
    contains -> Chain (0..n)
      references -> Knowledge via KnowledgeRef (premises, conclusions)
```

At the Graph IR level, Knowledge objects become variable nodes and Chains become factor nodes. The Package/Module hierarchy is metadata -- BP operates on the flat factor graph.

## Source

- `libs/storage/models.py` -- `Package`, `Module`, `Knowledge`, `Chain`, `ChainStep` models
- `docs/foundations_archive/language/gaia-language-spec.md` -- package layout and module conventions
- `docs/foundations_archive/cli/command-lifecycle.md` -- lifecycle stages
