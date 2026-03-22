# Gaia Overview

| Field | Value |
|---|---|
| Status | Current canonical |
| Level | Foundation |
| Scope | Repo-wide |
| Related | [../system-overview.md](../system-overview.md), [../meaning/vocabulary.md](../meaning/vocabulary.md), [scientific-reasoning-foundation.md](scientific-reasoning-foundation.md), [../product-scope.md](../product-scope.md) |

## Purpose

This document is the canonical high-level explanation of what Gaia is, what it is not, and why the project is split into Gaia CLI and Gaia LKM.

It is intentionally conceptual. It does not try to specify package syntax, Graph IR fields, or runtime code paths.

## Gaia In One Sentence

Gaia is a structured scientific knowledge system in which authors and agents write package-based knowledge artifacts, run local inference and validation with Gaia CLI, and publish those artifacts into Gaia LKM, the shared large knowledge model.

## Why Gaia Exists

Scientific knowledge is not just text. It has at least four properties that ordinary documents and ordinary databases do not handle well together:

- it is made of explicit claims, assumptions, and reasoning steps
- it is uncertain and revisable rather than simply true or false
- it depends on applicability conditions, background assumptions, and provenance
- it should be composable across packages, authors, and review cycles

Gaia exists to make those properties first-class.

## What Gaia Is

Gaia is:

- a package-oriented system for structured scientific knowledge
- a local-to-shared workflow, not just a static file format
- a plausible-reasoning system rather than a pure theorem-proving system
- a way to build and maintain a large knowledge model over time

In practice that means Gaia combines:

- a structured authoring surface
- deterministic build artifacts
- belief-oriented inference over structured claims
- shared-side review, rebuttal, integration, and curation

## What Gaia Is Not

Gaia is not:

- a plain note-taking format or annotation tool
- a generic database product
- a pure theorem prover
- a conventional knowledge graph in which stored edges are simply taken as truth
- a statistical probabilistic programming language aimed at random-variable modeling

Gaia borrows ideas from each of those worlds, but its target object is scientific knowledge with uncertainty and explicit reasoning structure.

## The Primary Split: Gaia CLI And Gaia LKM

Gaia has two primary active sides.

### Gaia CLI

Gaia CLI is the local author-side toolchain.

It owns the local lifecycle:

- `build`
- `infer`
- `publish`

It is responsible for:

- working from local Typst package source
- producing local deterministic artifacts under `.gaia/`
- providing local inference and validation surfaces before publication
- publishing package artifacts outward

### Gaia LKM

Gaia LKM is the shared-side knowledge core and system of record.

It is responsible for:

- accepting published package artifacts
- running shared-side review and rebuttal workflows
- integrating accepted packages into shared knowledge state
- maintaining curation, discovery, and larger-scale inference surfaces

`Gaia Cloud` may still be used as a product or deployment alias, but `Gaia LKM` is the preferred foundation term for the shared-side concept itself.

## Typical Artifact Flow

At the highest level, Gaia works like this:

1. An author or agent writes a Typst package locally.
2. Gaia CLI builds the source into deterministic local artifacts.
3. Gaia CLI may run local inference for preview.
4. Gaia CLI publishes a Gaia package artifact outward.
5. Gaia LKM runs the shared-side lifecycle around that package: review, rebuttal, integration, and curation.

This local-to-shared split is the reason CLI and LKM should be documented separately even when they share code.

## Why Packages Matter

Gaia is package-oriented because scientific knowledge is not created or reviewed one isolated claim at a time. In practice, authors submit:

- a bundle of claims
- supporting reasoning structure
- provenance and scope conditions
- open issues, rebuttals, or follow-up investigation material

The package is therefore the right boundary for authoring, publication, review, and integration.

## Relationship To Other Foundation Docs

This document answers the highest-level question: "What is Gaia?"

The next questions are answered elsewhere:

- [scientific-reasoning-foundation.md](scientific-reasoning-foundation.md) — why scientific reasoning needs a system like Gaia
- [../meaning/vocabulary.md](../meaning/vocabulary.md) — the canonical large terms such as `Gaia CLI`, `Gaia LKM`, `Service`, and `Engine`
- [../semantics/scientific-knowledge.md](../semantics/scientific-knowledge.md) — what counts as scientific knowledge in Gaia
- [../semantics/knowledge-relations.md](../semantics/knowledge-relations.md) — what kinds of relations exist between knowledge items
- [../semantics/gaia-reasoning-model.md](../semantics/gaia-reasoning-model.md) — Gaia's chosen reasoning model

## Out Of Scope

This document does not define:

- detailed knowledge object ontology
- authored package syntax
- Graph IR fields
- storage schema
- current runtime implementation details

## Migration Note

This document now supersedes the highest-level explanatory role previously split across [../product-scope.md](../product-scope.md) and parts of [../system-overview.md](../system-overview.md). Those docs still contain useful migration context but should no longer be the first canonical home for the question "What is Gaia?"
