# Gaia CLI Runtime Boundaries

## Purpose

This document defines the current architectural boundaries for Gaia CLI.

It does not define Gaia server architecture.

The goal is to separate:

1. the shared reasoning artifact contracts consumed by the CLI
2. the local formalization services used to construct and critique packages
3. the higher-level research orchestrator or agent runtime that chooses when to call those services

## Scope Boundary

This document applies only to the local Gaia CLI side.

It covers:

- local package representation
- local package construction
- local package review
- optional local package revision/materialization

It does not cover:

- Gaia server architecture
- server-side storage
- server-side APIs
- server-side review orchestration
- global graph integration semantics
- BP

## Three Layers

The current Gaia CLI architecture is split into three layers:

1. shared reasoning artifact contracts
2. Gaia CLI formalization services
3. research orchestrator / agent runtime

## 1. Shared Reasoning Artifact Contracts

This layer defines the shared structural contracts used by both Gaia local/CLI and Gaia server.

From the CLI point of view, this layer is imported rather than owned.

### Shared contract responsibilities

- define the V1 static schemas for:
  - `knowledge_artifact`
  - `chain_step`
  - `reasoning_chain`
  - `package`
- define the minimal subtype schemas for:
  - `claim`
  - `question`
  - `setting`
  - `action`
- validate structural correctness
- validate local references and package consistency
- define import/export contracts for shared reasoning artifacts

### Shared contracts should not do

- raw-input canonicalization
- model-based critique
- package rewriting
- graph-level belief propagation

## 2. Gaia CLI Formalization Services

Formalization services sit above the shared contracts.

They are responsible for turning raw local material into kernel-valid structures and critiquing those structures.

### Formalization service responsibilities

- canonicalization of raw material into package candidates
- review of reasoning chains and package candidates
- optional revised package materialization

These services are allowed to be model-driven and strategy-dependent.

They may vary by:

- domain
- input source
- model family
- prompt strategy
- extraction policy

### Formalization services should not do

- redefine shared artifact schema
- act as the authoritative global graph layer
- define BP semantics

## 3. Research Orchestrator / Agent Runtime

The orchestrator sits above formalization services.

It decides when and how the services are used.

### Orchestrator responsibilities

- choose when to canonicalize
- choose which canonicalizer to use
- choose when to run review
- manage multiple review reports
- decide whether to materialize a revised package
- decide when local packages are ready for later graph integration

### Orchestrator should not do

- redefine shared artifact contracts
- silently blur review outputs and package contents

## Layer Interaction

The intended direction is:

```text
research orchestrator
    -> formalization services
        -> shared artifact contracts
```

The shared contracts define what valid reasoning artifacts look like.

Formalization services produce and critique shared-contract-valid structures.

The orchestrator manages when those services are applied and how their outputs are used.

## Relationship To Other Foundation Docs

- [../shared/knowledge-package-static.md](../shared/knowledge-package-static.md) defines the shared V1 static package schema consumed by the CLI
- [../shared/knowledge-package-file-formats.md](../shared/knowledge-package-file-formats.md) defines the shared V1 package file formats and review-report format consumed by CLI formalization services
- [command-lifecycle.md](command-lifecycle.md) defines the intended target lifecycle: core CLI commands `build`, `infer`, `publish`, plus agent skills such as self-review and graph-construction; the shipped `gaia review` command is documented there as a compatibility bridge

Gaia server architecture remains intentionally undefined here and should be designed separately later.
