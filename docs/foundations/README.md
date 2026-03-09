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
- [Gaia Language Spec](language/gaia-language-spec.md)
- [Gaia Language Design](language/gaia-language-design.md)
- [Language Design Rationale](language/design-rationale.md)
- [Type System Direction](language/type-system-direction.md)
- [Theoretical Foundation](theoretical-foundation.md)
- [Inference Theory](inference-theory.md)
- [Gaia CLI Runtime Boundaries](cli/boundaries.md)
- [Gaia CLI Command Lifecycle](cli/command-lifecycle.md)

## Intended outputs

The plan is to establish a small set of durable foundation docs before major code restructuring resumes:

1. `product-scope.md`
2. `domain-model.md`
3. `theoretical-foundation.md` (Jaynes-centered theoretical foundation)
4. `inference-theory.md` (BP algorithm and inference theory)
5. `language/gaia-language-spec.md` (Gaia Language spec)
6. `cli/boundaries.md` (Gaia CLI runtime layering)
7. `graph-spec.md`
8. `storage-schema.md`
9. `module-boundaries.md`
10. `api-contract.md`

Those files do not all exist yet. This directory is the place where they should be created and kept current.

## Folder Layout

- `language/`: Gaia formal language spec, design, and design rationale
- `cli/`: Gaia CLI runtime boundaries and future CLI-specific docs

## Historical docs

Historical design documents and implementation plans from the initial build-out are preserved in [`../archive/`](../archive/).

## Working rule

When a change affects architecture or cross-module behavior, the relevant foundation doc should be updated in the same branch, or the PR should explicitly state why the docs are being deferred.
