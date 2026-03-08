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

- [Foundation Reset Plan](foundation-reset-plan.md)
- [System Overview](system-overview.md)
- [Product Scope](product-scope.md)
- [Domain Model](domain-model.md)
- [Gaia DSL Framework](DSL/gaia-dsl-framework.md)
- [Shared Knowledge Package V1 Static](shared/knowledge-package-static.md)
- [Shared Knowledge Package V1 File Formats](shared/knowledge-package-file-formats.md)
- [V3 Probabilistic Semantics](shared/probabilistic-semantics.md)
- [Gaia CLI Runtime Boundaries](cli/boundaries.md)
- [Gaia CLI Command Lifecycle](cli/command-lifecycle.md)

## Intended outputs

The plan is to establish a small set of durable foundation docs before major code restructuring resumes:

1. `product-scope.md`
2. `domain-model.md`
3. `shared/knowledge-package-static.md` (shared V1 closure/module/package schema)
4. `shared/knowledge-package-file-formats.md` (shared V1 package file formats and review-report format)
5. `shared/probabilistic-semantics.md` (V3 probabilistic FP semantics, priors, BP)
6. `cli/boundaries.md` (Gaia CLI runtime layering on top of shared contracts)
7. `graph-spec.md`
8. `storage-schema.md`
9. `module-boundaries.md`
10. `api-contract.md`

Those files do not all exist yet. This directory is the place where they should be created and kept current.

## Staging

Reasoning design is now intentionally split by layer:

- V1 static: shared `closure / module / package` structure
- V1 file formats: shared package file formats and review-report exchange format
- V2: global Gaia graph integration
- V3: probabilistic semantics, prior/belief, and BP

## Folder Layout

- `DSL/`: Gaia DSL framework and detailed language design docs
- `shared/`: contracts intended to be shared by Gaia local/CLI and Gaia server
- `cli/`: Gaia CLI runtime boundaries and future CLI-specific docs

## Working rule

When a change affects architecture or cross-module behavior, the relevant foundation doc should be updated in the same branch, or the PR should explicitly state why the docs are being deferred.
