# Foundations

This directory is the working area for Gaia's next foundation reset.

Use it when the task affects any of the following:

- overall architecture
- module boundaries
- API contracts
- graph model semantics
- storage schema or backend capability assumptions
- domain vocabulary

## Current status

Gaia now has a documented re-baselining diagnosis in [../architecture-rebaseline.md](../architecture-rebaseline.md).

The execution plan for that reset lives here:

**Global (cross-subsystem):**

- [Foundation Reset Plan](foundation-reset-plan.md)
- [Product Scope](product-scope.md)
- [System Overview](system-overview.md)
- [Domain Model](domain-model.md) — superseded redirect to newer ontology/package-profile docs

**Graph IR:**

- [Graph IR](graph-ir.md) — Canonical factor graph IR between Gaia Language and BP

**Theory:**

- [Theoretical Foundation](theory/theoretical-foundation.md) — Jaynes 纲领
- [Scientific Ontology](theory/scientific-ontology.md) — scientific object model, BP-bearing vs non-BP objects, operator families
- [Inference Theory](theory/inference-theory.md) — BP 算法理论
- [Independent Evidence & Conditional Independence](theory/corroboration-and-conditional-independence.md) — 多路径独立证据的语义、条件独立性判定、交叉审查流程

**BP on Graph IR:**

- [BP on Graph IR](bp-on-graph-ir.md) — Factor functions, gate semantics, schema/ground BP interaction

**Language:**

- [Gaia Language Spec](language/gaia-language-spec.md)
- [Gaia Language Design](language/gaia-language-design.md)
- [Language Design Rationale](language/design-rationale.md)
- [Type System Direction](language/type-system-direction.md)

**CLI:**

- [Gaia CLI Runtime Boundaries](cli/boundaries.md)
- [Gaia CLI Command Lifecycle](cli/command-lifecycle.md)

**Review:**

- [Review Pipeline & Publish Workflow](review/publish-pipeline.md) — current self-review / peer review / publish contract
- [Review and Curation Service Boundaries](review/service-boundaries.md) — submission-scoped review vs registry-scoped curation
- [Gaia Package Artifact Profiles](review/package-artifact-profiles.md) — `knowledge` / `investigation` / `review` / `rebuttal` package semantics
- [Build, Alignment, and Review Architecture](review/architecture.md) — superseded historical reference

**Server:**

- [Server Architecture](server/architecture.md)

## Intended outputs

The plan is to establish a small set of durable foundation docs before major code restructuring resumes:

1. `product-scope.md`
2. `system-overview.md`
3. `theory/scientific-ontology.md` (scientific object model and BP boundary)
4. `theory/theoretical-foundation.md` (Jaynes-centered theoretical foundation)
5. `language/gaia-language-spec.md` (Gaia Language spec)
6. `graph-ir.md` (Graph IR — canonical factor graph layer)
7. `theory/inference-theory.md` (BP algorithm and operator theory)
8. `review/service-boundaries.md` (ReviewService vs CurationService)
9. `review/package-artifact-profiles.md` (knowledge / investigation / review / rebuttal package semantics)
10. `review/publish-pipeline.md` (self-review, peer review, and publish workflow)
11. `server/architecture.md` (Server architecture)
12. `server/storage-schema.md` (Server storage schema)
13. `domain-model.md` (compat redirect only; no longer a normative source)
14. `cli/boundaries.md` (Gaia CLI runtime layering)

Those files do not all exist yet. This directory is the place where they should be created and kept current.

## Folder Layout

- `theory/`: Theoretical foundations and ontology (Jaynes, scientific object model, BP operator theory)
- `language/`: Gaia formal language spec, design, and design rationale
- `cli/`: Gaia CLI runtime boundaries and future CLI-specific docs
- `review/`: Review and publish semantics, plus service-boundary docs for review vs curation
- `server/`: Server architecture, storage schema, API contracts

## Historical docs

Historical design documents and implementation plans from the initial build-out are preserved in [`../archive/`](../archive/).

## Working rule

When a change affects architecture or cross-module behavior, the relevant foundation doc should be updated in the same branch, or the PR should explicitly state why the docs are being deferred.
