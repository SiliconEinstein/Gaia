# Foundations

Canonical reference docs for Gaia, organized by architectural layer.

## Theory — pure math, Gaia-independent (never changes)

- [Plausible Reasoning](theory/plausible-reasoning.md) — Jaynes, Cox theorem, probability as logic
- [Belief Propagation](theory/belief-propagation.md) — sum-product algorithm, convergence, damping
- [Scientific Ontology](theory/scientific-ontology.md) — scientific knowledge classification

## Rationale — design philosophy (rarely changes)

- [Product Scope](rationale/product-scope.md) — what Gaia is, why it exists
- [Architecture Overview](rationale/architecture-overview.md) — three-layer pipeline, CLI↔LKM contract
- [Domain Vocabulary](rationale/domain-vocabulary.md) — Knowledge, Chain, Module, Package
- [Type System Direction](rationale/type-system-direction.md) — Jaynes + Lean hybrid
- [Documentation Policy](rationale/documentation-policy.md) — doc maintenance rules

## Graph IR — the shared contract between CLI and LKM

- [Overview](graph-ir/overview.md) — purpose, three identity layers
- [Knowledge Nodes](graph-ir/knowledge-nodes.md) — Raw, LocalCanonical, GlobalCanonical schemas
- [Factor Nodes](graph-ir/factor-nodes.md) — FactorNode schema (single definition), types, compilation rules
- [Canonicalization](graph-ir/canonicalization.md) — local and global canonicalization
- [Parameterization](graph-ir/parameterization.md) — overlay schemas, graph hash

## BP — computation on Graph IR

- [Factor Potentials](bp/potentials.md) — potential functions for each factor type
- [Inference](bp/inference.md) — BP algorithm applied to Graph IR
- [Local vs Global](bp/local-vs-global.md) — CLI local inference vs LKM global inference

## CLI — local authoring and inference

- **Gaia Lang** (the CLI's frontend for Graph IR):
  - [Language Spec](cli/gaia-lang/spec.md) — Typst DSL syntax
  - [Knowledge Types](cli/gaia-lang/knowledge-types.md) — declaration types, proof state
  - [Package Model](cli/gaia-lang/package-model.md) — package/module/chain
- [Lifecycle](cli/lifecycle.md) — build → infer → publish
- [Compiler](cli/compiler.md) — Typst → Graph IR compilation
- [Local Inference](cli/local-inference.md) — `gaia infer` internals
- [Local Storage](cli/local-storage.md) — LanceDB + Kuzu embedded

## LKM — computational registry (server)

- [Overview](lkm/overview.md) — Write/Read side architecture
- [Review Pipeline](lkm/review-pipeline.md) — validation → review → gatekeeper
- [Global Canonicalization](lkm/global-canonicalization.md) — cross-package node mapping
- [Curation](lkm/curation.md) — clustering, dedup, conflict detection
- [Global Inference](lkm/global-inference.md) — server-side BP
- [Pipeline](lkm/pipeline.md) — 7-stage batch orchestration
- [Storage](lkm/storage.md) — three-backend architecture
- [API](lkm/api.md) — HTTP API contract
- [Agent Credit](lkm/agent-credit.md) — agent reliability tracking
- [Lifecycle](lkm/lifecycle.md) — review → curate → integrate
