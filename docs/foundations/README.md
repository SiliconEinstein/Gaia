# Foundations

Canonical reference docs for Gaia, organized by change frequency.

## Theory — why Gaia reasons this way

- [Theoretical Foundation](theory/theoretical-foundation.md) — Jaynes plausible reasoning, why probabilistic
- [Scientific Ontology](theory/scientific-ontology.md) — scientific knowledge ontology, terminology
- [Belief Propagation](theory/belief-propagation.md) — BP algorithm, loopy BP, convergence, factor potentials

## Gaia Concepts — Gaia's technical choices built on theory

- [Knowledge Types](gaia-concepts/knowledge-types.md) — claim / setting / question / action / relation
- [Reasoning Relations](gaia-concepts/reasoning-relations.md) — deduction / induction / abstraction / contradiction
- [Factor Design](gaia-concepts/factor-design.md) — reasoning type → factor potential mapping
- [Package Model](gaia-concepts/package-model.md) — package / module / chain / knowledge structure
- [Type System Direction](gaia-concepts/type-system-direction.md) — Jaynes + Lean hybrid, why not Curry-Howard, probability at value layer

## Interfaces — contracts between layers

- [Language Spec](interfaces/language-spec.md) — Gaia Language v4 Typst DSL full spec
- [Graph IR](interfaces/graph-ir.md) — Graph IR structural contract
- [API](interfaces/api.md) — HTTP API contract
- [Lifecycle](interfaces/lifecycle.md) — CLI lifecycle (build→infer→publish) + LKM lifecycle (review→curate→integrate)
- [Agent Credit](interfaces/agent-credit.md) — agent reliability as BP-computed belief (target design)

## Implementations — how the system is built

- [Overview](implementations/overview.md) — architecture: entry points → engines → storage

### Entry Points (callers of the engine layer)

- [CLI](implementations/entry-points/cli.md) — single-package interactive (build/infer/publish)
- [Server](implementations/entry-points/server.md) — API server: write side (review, curation) + read side (search, recommend)
- [Pipeline](implementations/entry-points/pipeline.md) — batch orchestration (7 stages, multi-paper)

### Engines (shared capability layer)

- [Graph IR Compiler](implementations/engines/graph-ir-compiler.md) — typst → raw graph → local canonical graph
- [BP Engine](implementations/engines/bp-engine.md) — local BP + global BP
- [Review Engine](implementations/engines/review-engine.md) — LLM-based review
- [Curation Engine](implementations/engines/curation-engine.md) — clustering, dedup, abstraction, conflict detection
- [Canonicalization Engine](implementations/engines/canonicalization-engine.md) — local → global node mapping

### Infrastructure

- [Storage](implementations/storage.md) — LanceDB + Neo4j + three-write atomicity
- [Testing](implementations/testing.md) — test structure, fixtures, CI

## Other

- [Product Scope](product-scope.md) — current product boundaries
- [Documentation Policy](documentation-policy.md) — doc maintenance rules
