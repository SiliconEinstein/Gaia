# Foundations

This directory contains Gaia's active foundation docs.

Use it when the task affects:

- overall system meaning or terminology
- package, graph, or storage contracts
- CLI and shared-side lifecycle boundaries
- runtime architecture and behavior

## Start Here

- [Documentation Policy](documentation-policy.md)
- [System Overview](system-overview.md)
- [Gaia Vocabulary](meaning/vocabulary.md)
- [Foundation Reset Plan](foundation-reset-plan.md)

## Active Structure

The active foundations reset is reorganizing this directory around four top-level families:

- **Foundation** — why Gaia exists and what high-level scientific reasoning foundation it assumes
- **Semantics** — Gaia-specific terminology, knowledge, relations, and reasoning semantics
- **Contracts** — the stable authored and system contracts
- **Runtime** — how the current implementation behaves

The migration is in progress, so some active docs still live in legacy subfolders. The goal is to move the active set toward a clearer `foundation / semantics / contracts / runtime` tree over time.

## Target Tree

The target active tree is being made explicit as a file tree, even before all content has migrated. Placeholder docs use `Status: Target design` so each major theme has an obvious future canonical home.

```text
docs/foundations/
  foundation/
    gaia-overview.md
    scientific-reasoning-foundation.md

  semantics/
    terminology.md
    scientific-knowledge.md
    knowledge-relations.md
    gaia-reasoning-model.md

  contracts/
    authoring/
      gaia-language-spec.md
      graph-ir.md
      package-linking.md
    workflows/
      package-types.md
      cli-lifecycle.md
      lkm-lifecycle.md
      review-artifacts.md
      investigation-artifacts.md
    services/
      service-boundaries.md
      review-service.md
      curation-service.md
      api-contract.md

  runtime/
    server-architecture.md
    storage-schema.md
    inference-runtime.md
    loop-analysis.md
    review-runtime.md
    curation-runtime.md
```

## Current Reading Order

### Meaning

- [Gaia Vocabulary](meaning/vocabulary.md) — primary foundation terminology
- [Product Scope](product-scope.md) — product positioning and current baseline
- [Theoretical Foundation](theory/theoretical-foundation.md) — Jaynes-centered framing and epistemic motivation
- [Domain Model](domain-model.md) — legacy meaning doc that will be retired as newer canonical homes are created
- [Inference Theory](theory/inference-theory.md) — current semantic operator theory
- [Independent Evidence & Conditional Independence](theory/corroboration-and-conditional-independence.md) — current corroboration semantics

### Contracts

- [Gaia Language Spec](language/gaia-language-spec.md)
- [Gaia Language Design](language/gaia-language-design.md)
- [Language Design Rationale](language/design-rationale.md)
- [Type System Direction](language/type-system-direction.md)
- [Graph IR](graph-ir.md)
- [Gaia CLI Command Lifecycle](cli/command-lifecycle.md)
- [Review Pipeline & Publish Workflow](review/publish-pipeline.md) — current shared-side workflow doc during migration

### Runtime

- [Gaia CLI Runtime Boundaries](cli/boundaries.md)
- [BP on Graph IR](bp-on-graph-ir.md)
- [Server Architecture](server/architecture.md)
- [Server Storage Schema](server/storage-schema.md)

## Migration Notes

- Active docs should prefer `Gaia CLI` and `Gaia LKM` over `Gaia Cloud` and `Gaia Server` as the primary conceptual split.
- Active docs should describe authoring in terms of Typst packages and Gaia packages, not YAML package files.
- The canonical local CLI lifecycle is `build -> infer -> publish`; review belongs on the shared-side lifecycle.

## Historical Docs

Historical design documents and older implementation plans are preserved in [`../archive/`](../archive/).

## Working Rule

When a change affects architecture or cross-module behavior, update the relevant foundation doc in the same branch, or explicitly state why the doc update is being deferred.
