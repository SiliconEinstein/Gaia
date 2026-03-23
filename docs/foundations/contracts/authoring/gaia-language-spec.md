# Gaia Language Spec

| Field | Value |
|---|---|
| Status | Transitional |
| Level | Spec |
| Scope | Subsystem |
| Related | [graph-ir.md](graph-ir.md), [package-linking.md](package-linking.md), [../../semantics/scientific-knowledge.md](../../semantics/scientific-knowledge.md), [../../language/gaia-language-spec.md](../../language/gaia-language-spec.md) |

## Purpose

This document defines the author-facing Gaia Language contract.

It is marked `Transitional` because this file is now the new canonical home in the foundations tree, but the older detailed v4 language spec still contains migration-era surface detail that has not yet been fully folded in here.

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

## Core Surface Commitments

At a high level, the language contract must support:

- typed knowledge declarations
- explicit local reasoning references
- explicit relation declarations where appropriate
- package structure and package-local naming
- explicit cross-package linking

The exact surface syntax may evolve, but those commitments are stable.

## What The Language Must Express

The language must be able to express at least:

- core knowledge items such as claims, observations, laws, hypotheses, predictions, settings, questions, and actions where relevant
- structured reasoning links such as `from:` style dependencies
- relation declarations such as contradiction or equivalence where the author intends to state them explicitly
- package-local labels that allow deterministic extraction and linking
- cross-package references through an explicit package-linking mechanism

## What The Language Must Not Do

Gaia Language is not intended to be:

- a general workflow programming language
- a place to encode opaque global identity assignments
- the final runtime representation for inference
- a hidden container for server-side review judgments

Those belong to other layers.

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

This new document becomes the canonical contract home in the new foundations tree, but it remains intentionally higher-level until that detailed material has been migrated and cleaned up.

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

This file now becomes the canonical home for the language contract in the new tree, but it remains `Transitional` until the remaining detailed v4 surface material is migrated from the older legacy spec.
