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
- [Gaia Overview](foundation/gaia-overview.md)
- [Terminology](semantics/terminology.md)
- [Foundation Reset Plan](foundation-reset-plan.md)

## Active Structure

The active foundations reset is reorganizing this directory around four top-level families:

- **Foundation** — why Gaia exists and what high-level scientific reasoning foundation it assumes
- **Semantics** — Gaia-specific terminology, knowledge, relations, and reasoning semantics
- **Contracts** — the stable authored and system contracts
- **Runtime** — how the current implementation behaves

The migration is in progress, so some active docs still live in legacy subfolders. The goal is to move the active set toward a clearer `foundation / semantics / contracts / runtime` tree over time.

## Target Tree

The target active tree is being made explicit as a file tree before every legacy document has been retired. Some files in this tree are still placeholders with `Status: Target design`; others are already becoming the new canonical homes for their topics.

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
    artifacts/
      package-profiles.md
      review-artifacts.md
      investigation-artifacts.md
    lifecycles/
      cli-lifecycle.md
      lkm-package-lifecycle.md
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

### Foundation and Semantics

- [Gaia Overview](foundation/gaia-overview.md) — what Gaia is, is not, and why it is split into Gaia CLI and Gaia LKM
- [Scientific Reasoning Foundation](foundation/scientific-reasoning-foundation.md) — why Gaia needs a scientific-reasoning foundation broader than pure mathematical logic
- [Terminology](semantics/terminology.md) — primary foundation terminology
- [Scientific Knowledge](semantics/scientific-knowledge.md) — the main scientific knowledge types in Gaia
- [Knowledge Relations](semantics/knowledge-relations.md) — the semantic relation families between Gaia knowledge items
- [Gaia Reasoning Model](semantics/gaia-reasoning-model.md) — Gaia's chosen reasoning model across deduction, induction, abduction, abstraction, and instantiation
- [Gaia Vocabulary](meaning/vocabulary.md) — transitional terminology bridge during migration
- [Product Scope](product-scope.md) — current baseline and product-surface context during migration
- [Theoretical Foundation](theory/theoretical-foundation.md) — older Jaynes-centered framing and background theory during migration
- [Inference Theory](theory/inference-theory.md) — older operator/factor theory during migration
- [Independent Evidence & Conditional Independence](theory/corroboration-and-conditional-independence.md) — current independent-evidence theory during migration
- [Domain Model](domain-model.md) — legacy meaning doc that will be retired as newer canonical homes stabilize

### Contracts

- [Package Profiles](contracts/artifacts/package-profiles.md) — semantic profiles for knowledge, review, rebuttal, and investigation packages
- [Review Artifacts](contracts/artifacts/review-artifacts.md) — the structured outputs of submission review
- [Investigation Artifacts](contracts/artifacts/investigation-artifacts.md) — open-question and investigation-queue style artifacts
- [LKM Package Lifecycle](contracts/lifecycles/lkm-package-lifecycle.md) — what happens to packages after they arrive in Gaia LKM
- [Service Boundaries](contracts/services/service-boundaries.md) — the primary service split inside Gaia LKM
- [Review Service](contracts/services/review-service.md) — submission-scoped adjudication ownership
- [Curation Service](contracts/services/curation-service.md) — shared-state maintenance and investigation ownership
- [CLI Lifecycle](contracts/lifecycles/cli-lifecycle.md) — the canonical local CLI lifecycle ending at publish
- [Gaia Language Spec](contracts/authoring/gaia-language-spec.md) — the new canonical home for the author-facing language contract
- [Graph IR](contracts/authoring/graph-ir.md) — the structural contract between authored packages and downstream reasoning/runtime
- [Package Linking](contracts/authoring/package-linking.md) — cross-package reference and export-boundary rules
- [Gaia Language Design](language/gaia-language-design.md)
- [Language Design Rationale](language/design-rationale.md)
- [Type System Direction](language/type-system-direction.md)
- [Legacy Gaia Language Spec](language/gaia-language-spec.md) — older detailed v4 spec during migration
- [Legacy Graph IR Draft](graph-ir.md) — older detailed Graph IR draft during migration
- [Legacy CLI Command Lifecycle](cli/command-lifecycle.md) — older combined lifecycle doc during migration
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
