# Gaia Domain Model

## Purpose

This document defines the shared core vocabulary used by Gaia foundation docs.

Its job is to lock the minimum set of domain terms before later docs define:

- package schema
- package file formats
- global graph integration
- probabilistic semantics

## Boundary

This document defines vocabulary and modeling boundaries only.

It does not define:

- package file layout
- canonicalization or review algorithms
- server API contracts
- graph propagation, prior, belief, or BP

## Core Layers

Gaia currently uses three conceptual layers:

1. reusable global knowledge objects
2. local reasoning steps with explicit dependencies
3. package-level organization

The corresponding V1 terms are:

- `knowledge_artifact`
- `step`
- `package`

## Shared Knowledge Objects

### `knowledge_artifact`

A `knowledge_artifact` is a globally identifiable, reusable knowledge object.

V1 keeps the shared artifact set intentionally small:

- `claim`
- `question`
- `setting`
- `action`

This is the common substrate used by both local package tooling and later server-side ingestion.

### `claim`

A `claim` is a truth-apt statement or reusable result object.

Examples:

- a scientific statement
- a declarative gap statement
- a reusable code result
- a reusable Lean theorem/proof result

`claim` is the default type for statement-like content.

### `question`

A `question` is an inquiry object.

It is not a truth-apt statement.

Examples:

- "Why does phenomenon X occur?"
- "Can implementation Y be proven correct?"

### `setting`

A `setting` is a context-setting object that determines how later reasoning should be interpreted or executed.

V1 uses `setting` to unify:

- definitions
- logical setup
- execution environment
- experimental environment

### `action`

An `action` is a reusable process object.

Examples:

- an inferential move
- a tool call
- another explicit process step

`action` is used when a reasoning gap is nontrivial enough that it should be made explicit in a reasoning chain.

## Local Reasoning Structure

### `step`

A `step` is one local occurrence of a `knowledge_artifact` inside a `package`.

It exists because the same global artifact can be reused in multiple packages and in different local roles.

Each step declares its logical dependencies explicitly via `input`, with dependency strength:

- **strong** — if the referenced artifact is wrong, this step is likely wrong too
- **weak** — the referenced artifact is relevant context, but this step can stand on its own

These are local step relations, not global artifact properties. The same artifact can be a strong dependency in one step and a weak dependency in another.

### Narrative ordering

A package's `reasoning_steps` list defines a narrative reading order. This ordering carries no implicit logical dependency — all dependencies are declared via `input` on each step.

V1 does not impose a rigid formal grammar on which artifact kinds may follow which others. The governing rule is:

- the narrative should make sense as a reading order
- if there is a nontrivial reasoning gap, it should be made explicit via an `action`

This means direct artifact → artifact transitions are allowed when the reasoning is trivial or locally obvious.

## Package Organization

### `package`

A `package` is a reusable container of knowledge artifacts and reasoning steps.

Typical examples include:

- a paper
- a research bundle
- a structured note
- a project unit

A package contains `reasoning_steps` in narrative order. Starting points (leaves with no `input`) and conclusions (artifacts with no downstream strong dependents) are derived from the dependency graph, not declared separately.

## Important Non-Equivalences

The following should not be treated as equivalent:

- `claim` and `question`
- `claim` and `setting`
- `action` and `claim`
- global `knowledge_artifact` identity and local `step` occurrence
- narrative ordering and logical dependency

Examples:

- a statement-form gap is a `claim`, not a `question`
- a definition is a `setting`, not a generic `claim`
- adjacent steps in `reasoning_steps` do not imply logical dependency — all dependencies are explicit via `input`

## Deferred Distinctions

V1 intentionally does not yet split the artifact system into more detailed epistemic kinds such as:

- `observation`
- `assumption`
- `conjecture`

Those distinctions may become important later for graph integration, probabilistic semantics, or review policy, but they are not required for the minimal shared package substrate.

For now:

- observation-like content is modeled as `claim` plus provenance and supporting resources
- assumption-like content is modeled as `claim` or `setting`, depending on whether it is statement-like or setup-like

## Relationship To Later Docs

- [shared/knowledge-package-static.md](shared/knowledge-package-static.md) instantiates this vocabulary as the V1 static package schema
- [shared/knowledge-package-file-formats.md](shared/knowledge-package-file-formats.md) defines the corresponding package and review-report file formats
- V2 (graph integration) will define how packages map to the global graph
- V3 (probabilistic semantics) will define prior, belief, and BP on top of the dependency graph
- later docs should build on rather than silently replace the terms defined here

## Current Rule

When a new design needs a new noun, prefer to:

1. reuse `claim`, `question`, `setting`, or `action` if one already fits
2. place local dependency semantics on `step`, not on the global artifact kind
3. defer finer epistemic distinctions until they are required by graph or probabilistic semantics
