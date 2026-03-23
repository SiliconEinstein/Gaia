# Gaia Language Spec

| Field | Value |
|---|---|
| Status | Current canonical |
| Level | Spec |
| Scope | Subsystem |
| Related | [graph-ir.md](graph-ir.md), [package-linking.md](package-linking.md), [../../semantics/scientific-knowledge.md](../../semantics/scientific-knowledge.md), [../../language/gaia-language-spec.md](../../language/gaia-language-spec.md) |

## Purpose

This document defines the current author-facing Gaia Language contract.

The older detailed v4 file still remains useful as a migration-era reference, but this file is now the canonical contract boundary in the foundations tree.

## Core Role

Gaia Language is the authored package surface of Gaia.

Its job is to let authors and agents express:

- scientific knowledge items
- local reasoning structure
- package-local relations
- cross-package references

in a form that is both human-readable and machine-lowerable.

## The Authoring Boundary

Gaia Language is not the whole private workspace of an author or agent.

It is the stable authored package boundary that is intended to be:

- reviewable
- lowerable into Graph IR
- publishable into Gaia LKM workflows

This means the language is intentionally narrower and more disciplined than general note-taking or free-form scratch work.

## Current Authored Package Shape

The active authored surface is a Typst package.

The current shipped shape is:

- `typst.toml` for package metadata such as package name, version, and entrypoint
- `lib.typ` as the package entrypoint
- one or more included module `.typ` files containing declarations
- optional helper files such as `gaia.typ`
- optional cross-package dependency data such as `gaia-deps.yml`

This is the current contract direction. Active authoring is not based on `package.yaml` plus module YAML files.

## Current Declaration Families

The current v4 authored surface provides five primary declaration families:

- `#setting`
- `#question`
- `#claim`
- `#action`
- `#relation`

Those declarations are the author-facing way to express the semantic object families defined in [../../semantics/scientific-knowledge.md](../../semantics/scientific-knowledge.md).

## Current Surface Capabilities

The current contract supports the following authored capabilities.

### Typed declarations

Authors can declare:

- settings
- questions
- claims
- actions
- relations

The active relation subtypes are currently:

- `contradiction`
- `equivalence`

### Explicit local support structure

`#claim` and `#action` may use `from:` to declare explicit local support dependencies.

This is the active load-bearing author-side dependency surface.

### Optional local subtype labels

`#claim` and `#action` may use `kind:` to indicate a narrower authored subtype such as:

- `observation`
- `python`

These subtype labels are still package-local authored annotations, not shared-side global identity.

### Explicit relation endpoints

`#relation` uses `type:` and `between:` to declare structural relations between already-declared nodes.

### Package-local labels and references

Declarations use explicit labels so that packages can:

- reference local nodes deterministically
- cite them in proof blocks or prose
- lower them deterministically into structured artifacts

### Explicit cross-package references

Packages may refer to external knowledge through the cross-package linking surface described in [package-linking.md](package-linking.md).

In the current v4 authoring pattern this is typically expressed through:

- a `gaia-deps.yml` file
- a `#gaia-bibliography(...)` call in Typst

The important contract is explicit package-oriented linking, not the exact helper filename.

## Core Surface Commitments

At a high level, the language contract must support:

- typed knowledge declarations
- explicit local reasoning references
- explicit relation declarations where appropriate
- package structure and package-local naming
- explicit cross-package linking

The exact surface syntax may evolve, but those commitments are stable.

## Current v4 Surface Conventions

The current shipped Typst-based surface follows these conventions.

### Entrypoint and modules

`lib.typ` is the entrypoint. It typically:

- imports the Gaia Typst library
- applies the Gaia show rules
- includes one or more module files

The included `.typ` files are the main authoring surface.

### Proof blocks

`#claim`, `#action`, and `#relation` may include an additional proof or justification block after the visible statement body.

That block is part of the authored package surface even though the current structural lowering treats it primarily as explanatory source material rather than as Graph IR structure.

### Labels

Declarations end with Typst labels and are intended to be locally referenceable.

The active v4 convention uses package-local labels, often namespaced by module filename, so that extraction remains deterministic.

### Current argument surface

The active stable argument concepts are:

- `from:` for explicit support dependencies
- `kind:` for local authored subtype on `claim` and `action`
- `type:` and `between:` on `relation`

The frequently discussed future ideas such as `under:` or `mode:` are not yet part of the current shipped language contract.

## What The Language Must Express

The language must be able to express at least:

- core knowledge items such as claims, observations, laws, hypotheses, predictions, settings, questions, and actions where relevant
- structured reasoning links such as `from:` style dependencies
- relation declarations such as contradiction or equivalence where the author intends to state them explicitly
- package-local labels that allow deterministic extraction and linking
- cross-package references through an explicit package-linking mechanism

## What The Language Lowers To

The authoring surface lowers to [graph-ir.md](graph-ir.md) through a deterministic extraction path.

At the current local boundary that means:

- declarations lower to structured knowledge items
- `from:` lowers to reasoning support structure
- relation declarations lower to explicit relation/constraint structure
- cross-package references lower to explicit external-node structure rather than hidden global IDs

The language surface does not itself choose shared-side canonical identity or publish-time acceptance outcomes.

## What The Language Must Not Do

Gaia Language is not intended to be:

- a general workflow programming language
- a place to encode opaque global identity assignments
- the final runtime representation for inference
- a hidden container for server-side review judgments

Those belong to other layers.

## Current Conformance Requirements

A conforming Gaia package source must currently satisfy at least the following.

### Deterministic entrypoint

The package must expose a deterministic Typst entrypoint that the loader can compile and query.

### Extractable declarations

Supported declarations must lower to machine-readable metadata in a deterministic way.

### Explicit references

Local and cross-package references must be explicit enough that the package can be rebuilt into the same structural graph from source.

### No shared-side identity leakage

The authored package must not require opaque shared-side canonical IDs as part of ordinary authoring.

### No workflow smuggling

The authored source must not be used as a container for shared-side verdicts, investigation queue ownership, or other downstream runtime-only state.

## Relationship To Graph IR

The language surface is lowered into [graph-ir.md](graph-ir.md).

That means the language contract must be designed with deterministic extraction and structural lowering in mind, even though Graph IR remains a separate layer.

## Relationship To Package Linking

Cross-package references are part of the language contract, but their deeper rules are defined in [package-linking.md](package-linking.md).

This document defines the existence of that surface capability; the linking doc defines its boundary conditions.

## Conformance

A conforming Gaia package source must:

- obey the package-level layout and entry conventions required by the active authoring model
- use supported declaration forms
- use references and labels in ways that can be deterministically extracted
- avoid smuggling shared-side runtime or registry decisions into local authored source

## Relationship To The Existing Detailed v4 Spec

The older [../../language/gaia-language-spec.md](../../language/gaia-language-spec.md) document still contains the detailed v4 Typst surface, including:

- package layout expectations
- declaration forms
- label conventions
- extraction details

That older file is now a detailed migration-era reference, not the canonical contract home.

## Relationship To Other Docs

- [graph-ir.md](graph-ir.md) defines the structural layer this language lowers into.
- [package-linking.md](package-linking.md) defines cross-package linking rules.
- [../../semantics/scientific-knowledge.md](../../semantics/scientific-knowledge.md) and [../../semantics/knowledge-relations.md](../../semantics/knowledge-relations.md) define the semantic objects and relations the language is expected to express.

## Out Of Scope

This document does not define:

- Graph IR internals
- BP runtime behavior
- shared-side workflow semantics
- storage schema

## Migration Note

This file is now the canonical home for the language contract in the new tree.

The older detailed v4 spec remains available as migration-era reference material, but future contract updates should land here first.
