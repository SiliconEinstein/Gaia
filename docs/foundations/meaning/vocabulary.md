# Gaia Vocabulary

| Field | Value |
|---|---|
| Status | Transitional |
| Level | Foundation |
| Scope | Repo-wide |
| Related | [../semantics/terminology.md](../semantics/terminology.md), [../system-overview.md](../system-overview.md), [../product-scope.md](../product-scope.md), [../theory/theoretical-foundation.md](../theory/theoretical-foundation.md) |

## Purpose

This document preserves the earlier vocabulary framing introduced during the foundations reset.

Its terminology content is being migrated to [../semantics/terminology.md](../semantics/terminology.md), which is now the canonical home for active terminology.

## Status Note

Use [../semantics/terminology.md](../semantics/terminology.md) for active terminology updates and references.

This document remains in place temporarily so existing links and stacked PRs do not break during the documentation reset.

## Primary System Terms

### Gaia

`Gaia` is the name of the overall system and product.

Use it when talking about the full ecosystem rather than a specific local or shared-side component.

### Gaia CLI

`Gaia CLI` is the local author-side toolchain.

It owns the local lifecycle:

- `build`
- `infer`
- `publish`

It works on local Typst package source and local `.gaia/` artifacts.

Important boundary:

- `review` is not part of the canonical CLI lifecycle
- older design docs may mention a `gaia review` step, but current `main` does not ship a standalone `gaia review` command in `cli/main.py`

### Gaia LKM

`Gaia LKM` is the shared-side knowledge core and system of record.

It is the primary foundation term for the shared side of Gaia. It owns the shared knowledge state and the workflows around review, rebuttal, integration, and curation.

Use `Gaia LKM` in active foundation docs when the topic is the shared-side concept itself, rather than a specific deployment.

## Secondary System Terms

### Gaia Cloud

`Gaia Cloud` is an acceptable product or deployment alias for the Gaia LKM side.

It is useful when discussing:

- hosted/shared deployment
- product surfaces around the shared side
- user-facing language for the shared system

But it should not replace `Gaia LKM` as the main foundation term.

Important boundary:

- `cloud` does not imply remote-only deployment
- a local or self-hosted deployment of Gaia LKM is still valid

### Server

`Server` is a runtime or deployment term.

Use it only when discussing the current running backend implementation: processes, APIs, storage backends, runtime composition, deployment shape, or similar concerns.

Do not use `server` as the primary conceptual name for the whole shared side.

## Responsibility Terms

### Service

`Service` means a responsibility boundary inside Gaia LKM.

Examples:

- `ReviewService`
- `CurationService`

Use `service` when the emphasis is ownership and contract, not algorithmic internals.

### Engine

`Engine` means an internal algorithmic component.

Examples:

- belief propagation engine
- alignment engine

Use `engine` when the emphasis is algorithmic behavior rather than product or workflow boundary.

## Artifact Terms

### Typst package source

The authored local source form of Gaia knowledge is a **Typst package**.

Use this term when talking about what authors edit directly.

Avoid describing active Gaia authoring as YAML-based.

### Gaia package

`Gaia package` is the formal package artifact unit exchanged in Gaia workflows.

Today it is typically rooted in Typst package source plus derived local artifacts and publishable package state.

Use `Gaia package` when the workflow cares about the package as a submission or exchange artifact, not just the raw authored source files.

### Artifact

`Artifact` means any produced or exchanged object in a workflow.

Examples:

- build outputs
- Graph IR outputs
- local inference outputs
- review outputs
- package submissions

### Pipeline

`Pipeline` means a staged artifact transformation flow.

Examples:

- the Gaia CLI pipeline
- the shared-side integration pipeline

### Runtime

`Runtime` means how the current implementation actually behaves.

Use this term when discussing:

- concrete code paths
- deployed system behavior
- current-vs-target divergence

## Usage Rules

Active foundation docs should follow these defaults:

1. Prefer `Gaia CLI` and `Gaia LKM` over `Gaia Cloud` and `Gaia Server` as the primary conceptual split.
2. Use `service` for responsibility boundaries and `engine` for internal algorithmic components.
3. Use `server` only in runtime/implementation docs.
4. Describe authoring as Typst package authoring, not YAML package authoring.
5. Do not place `review` inside the canonical CLI lifecycle.

## Quick Examples

Good:

- "Gaia CLI builds and infers over local Typst package source."
- "Gaia LKM owns review, rebuttal, integration, and curation."
- "`ReviewService` is an LKM service."
- "The current server runtime exposes the LKM through API and storage services."

Avoid:

- "Gaia Server" as the generic name for the whole shared side
- "YAML package" as the active authored package model
- "CLI review pipeline" as the canonical local lifecycle
