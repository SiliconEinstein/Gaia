# Terminology

| Field | Value |
|---|---|
| Status | Current canonical |
| Level | Foundation |
| Scope | Repo-wide |
| Related | [../system-overview.md](../system-overview.md), [../foundation/gaia-overview.md](../foundation/gaia-overview.md), [../meaning/vocabulary.md](../meaning/vocabulary.md) |

## Purpose

This document defines the primary terminology used by active Gaia foundation docs.

Its job is to freeze the large terms that otherwise drift across architecture, workflow, and runtime docs.

## Primary System Terms

### Gaia

`Gaia` is the name of the overall system and product.

Use it when discussing the full ecosystem rather than a specific local or shared-side component.

### Gaia CLI

`Gaia CLI` is the local author-side toolchain.

It owns the canonical local lifecycle:

- `build`
- `infer`
- `publish`

Important boundary:

- `review` is not part of the canonical CLI lifecycle
- the currently shipped `gaia review` command on `main` is a compatibility helper, not the primary lifecycle boundary

### Gaia LKM

`Gaia LKM` is the shared-side knowledge core and system of record.

It is the preferred foundation term for the shared side of Gaia.

It owns the shared knowledge state and the workflows around:

- review
- rebuttal
- integration
- curation

## Secondary System Terms

### Gaia Cloud

`Gaia Cloud` is an acceptable product or deployment alias for the Gaia LKM side.

Use it when discussing:

- hosted/shared deployment
- user-facing product surfaces around the shared side

But do not treat it as the primary foundation term.

Important boundary:

- `cloud` does not imply remote-only deployment
- a local or self-hosted Gaia LKM deployment is still valid

### Server

`Server` is a runtime or deployment term.

Use it only when the topic is the current running backend implementation:

- processes
- APIs
- storage backends
- deployment shape
- runtime composition

Do not use `server` as the primary conceptual name for the whole shared side.

## Responsibility Terms

### Service

`Service` means a responsibility boundary inside Gaia LKM.

Examples:

- `ReviewService`
- `CurationService`

Use `service` when the emphasis is ownership and contract rather than algorithmic internals.

### Engine

`Engine` means an internal algorithmic component.

Examples:

- belief propagation engine
- alignment engine

Use `engine` when the emphasis is algorithmic behavior rather than product or workflow boundary.

## Artifact Terms

### Typst package source

The authored local source form of Gaia knowledge is a **Typst package**.

Use this term when discussing what authors edit directly.

Avoid describing active Gaia authoring as YAML-based.

### Gaia package

`Gaia package` is the formal package artifact unit exchanged in Gaia workflows.

Use `Gaia package` when the workflow cares about the package as a submission or exchange artifact rather than just the authored source files.

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

Use it when discussing:

- concrete code paths
- deployed system behavior
- current-vs-target divergence

## Usage Rules

Active foundation docs should follow these defaults:

1. Prefer `Gaia CLI` and `Gaia LKM` over `Gaia Cloud` and `Gaia Server` as the primary conceptual split.
2. Use `service` for responsibility boundaries and `engine` for internal algorithmic components.
3. Use `server` only in runtime or implementation docs.
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

## Out Of Scope

This document does not define:

- detailed knowledge taxonomy
- relation semantics
- workflow-specific contracts

## Migration Note

This document supersedes [../meaning/vocabulary.md](../meaning/vocabulary.md) as the canonical home for active terminology. The older vocabulary doc remains as a transitional bridge while references are migrated.
