# Foundations

This directory contains Gaia's active foundation docs.

Use it when the task affects:

- overall system meaning or terminology
- package, graph, or storage contracts
- CLI and shared-side lifecycle boundaries
- runtime architecture and behavior

## Start Here

- [Documentation Policy](documentation-policy.md)
- [Gaia Overview](foundation/gaia-overview.md)
- [Scientific Reasoning Foundation](foundation/scientific-reasoning-foundation.md)
- [Terminology](semantics/terminology.md)
- [System Overview](system-overview.md)

## Active Structure

The active foundations tree is organized around four top-level families:

- **Foundation** — why Gaia exists and what high-level scientific reasoning foundation it assumes
- **Semantics** — Gaia-specific terminology, knowledge, relations, and reasoning semantics
- **Contracts** — the stable authored and system contracts
- **Runtime** — how the current implementation behaves

Legacy subfolders such as `theory/`, `review/`, `server/`, `cli/`, and top-level transition files still exist as bridge pages or detailed migration-era references. They should not be treated as first-stop canonical homes unless this README points to them explicitly.

## Active Tree

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
- [Product Scope](product-scope.md) — current baseline and product-surface context during migration

### Contracts

- [Gaia Language Spec](contracts/authoring/gaia-language-spec.md) — the canonical author-facing language contract
- [Graph IR](contracts/authoring/graph-ir.md) — the structural contract between authored packages and downstream reasoning/runtime
- [Package Linking](contracts/authoring/package-linking.md) — cross-package reference and export-boundary rules
- [Package Profiles](contracts/artifacts/package-profiles.md) — semantic profiles for knowledge, review, rebuttal, and investigation packages
- [Review Artifacts](contracts/artifacts/review-artifacts.md) — the structured outputs of submission review
- [Investigation Artifacts](contracts/artifacts/investigation-artifacts.md) — open-question and investigation-queue style artifacts
- [CLI Lifecycle](contracts/lifecycles/cli-lifecycle.md) — the canonical local CLI lifecycle ending at publish
- [LKM Package Lifecycle](contracts/lifecycles/lkm-package-lifecycle.md) — what happens to packages after they arrive in Gaia LKM
- [Service Boundaries](contracts/services/service-boundaries.md) — the primary service split inside Gaia LKM
- [Review Service](contracts/services/review-service.md) — submission-scoped adjudication ownership
- [Curation Service](contracts/services/curation-service.md) — shared-state maintenance and investigation ownership
- [API Contract](contracts/services/api-contract.md) — what external API commitments are and are not yet stable

### Runtime

- [Server Architecture](runtime/server-architecture.md) — current backend/runtime composition
- [Storage Schema](runtime/storage-schema.md) — current persistence-side data model
- [Inference Runtime](runtime/inference-runtime.md) — current executable inference path and current-vs-target divergence
- [Loop Analysis](runtime/loop-analysis.md) — how Gaia treats loops, diagnostics, and basis-style views
- [Review Runtime](runtime/review-runtime.md) — current execution path for review logic
- [Curation Runtime](runtime/curation-runtime.md) — current execution path for shared-state maintenance

## Legacy Bridges and Detailed References

These docs remain useful during migration, but they are not the preferred first-stop canonical homes:

- [Gaia Vocabulary](meaning/vocabulary.md)
- [Domain Model](domain-model.md)
- [Theoretical Foundation](theory/theoretical-foundation.md)
- [Inference Theory](theory/inference-theory.md)
- [Independent Evidence & Conditional Independence](theory/corroboration-and-conditional-independence.md)
- [Gaia Language Design](language/gaia-language-design.md)
- [Language Design Rationale](language/design-rationale.md)
- [Type System Direction](language/type-system-direction.md)
- [Legacy Gaia Language Spec](language/gaia-language-spec.md)
- [Legacy Graph IR Draft](graph-ir.md)
- [Legacy CLI Command Lifecycle](cli/command-lifecycle.md)
- [Gaia CLI Runtime Boundaries](cli/boundaries.md)
- [Review Architecture](review/architecture.md)
- [Review Pipeline & Publish Workflow](review/publish-pipeline.md)
- [BP on Graph IR](bp-on-graph-ir.md)
- [Legacy Server Architecture](server/architecture.md)
- [Legacy Server Storage Schema](server/storage-schema.md)
- [Foundation Reset Plan](foundation-reset-plan.md)

## Migration Notes

- Active docs should prefer `Gaia CLI` and `Gaia LKM` over `Gaia Cloud` and `Gaia Server` as the primary conceptual split.
- Active docs should describe authoring in terms of Typst packages and Gaia packages, not YAML package files.
- The canonical local CLI lifecycle is `build -> infer -> publish`; review belongs on the shared-side lifecycle.

## Historical Docs

Historical design documents and older implementation plans are preserved in [`../archive/`](../archive/).

## Working Rule

When a change affects architecture or cross-module behavior, update the relevant foundation doc in the same branch, or explicitly state why the doc update is being deferred.
