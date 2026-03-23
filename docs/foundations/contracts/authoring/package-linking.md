# Package Linking

| Field | Value |
|---|---|
| Status | Current canonical |
| Level | Spec |
| Scope | Subsystem |
| Related | [gaia-language-spec.md](gaia-language-spec.md), [graph-ir.md](graph-ir.md), [../lifecycles/cli-lifecycle.md](../lifecycles/cli-lifecycle.md), [../../language/gaia-language-spec.md](../../language/gaia-language-spec.md) |

## Purpose

This document defines the contract for how Gaia packages link to knowledge outside themselves.

It answers one question: when a package refers to something beyond its own authored content, what is allowed and what structural meaning does that reference carry?

## Core Principle

Package linking must preserve two truths at once:

- authoring should remain package-scoped and explicit
- shared identity should not be smuggled into source by opaque global IDs

So Gaia linking is package-oriented first, global-resolution-aware second.

## Package-Local Versus Cross-Package Reference

Gaia distinguishes:

- package-local references
- cross-package references

### Package-local reference

A package-local reference points to knowledge authored inside the same package.

This is the normal reference mode for:

- `from:` premises
- local background conditions
- relation endpoints

### Cross-package reference

A cross-package reference points to knowledge declared outside the current package.

This is allowed, but it must remain explicit and auditable.

## Linking Unit

The linking unit is not an abstract global ID.

The linking unit is a concrete external package reference carrying enough information to identify:

- the source package
- the source package version
- the referenced knowledge item

This preserves provenance and makes author intent explicit.

## Export Boundary

Packages may expose some knowledge as their public interface and keep other knowledge internal.

This export boundary matters because cross-package linking should respect the distinction between:

- what another package intentionally publishes as reusable
- what merely exists as internal local structure

## Premise Versus Context Across Package Boundaries

Cross-package references do not all carry the same force.

Gaia needs to distinguish between at least:

- load-bearing external premises
- external background or contextual references

This matters because using some external result as a hard premise is stronger than citing or depending on it as background context.

The exact authored surface may evolve, but the contract is clear: the linking layer must preserve the semantic role of the external dependency.

## No Silent Global Identity Injection

Authors should not be required to write opaque global canonical IDs in source just to reference external knowledge.

Global matching and LKM-side identity assignment are downstream responsibilities. Package linking should remain understandable at the package boundary.

## Relationship To Graph IR

Graph IR may preserve external references structurally, but package linking is defined first at the authoring contract level.

That means:

- this document defines what counts as a valid external reference
- [graph-ir.md](graph-ir.md) defines how those references appear in structural artifacts after lowering

## Relationship To CLI Lifecycle

Package linking is resolved or elaborated during the local authoring/build boundary, not during shared-side review.

That is why this document belongs near authored contracts and [../lifecycles/cli-lifecycle.md](../lifecycles/cli-lifecycle.md), not under LKM services.

## Relationship To Language Surface

The exact Typst syntax for cross-package references belongs in [gaia-language-spec.md](gaia-language-spec.md).

This document stays one layer more abstract. It defines the linking rules, not the final surface sugar.

## Out Of Scope

This document does not define:

- local CLI lifecycle stages themselves
- shared-side review flow
- storage schema
- registry-side canonical binding logic

## Migration Note

This document replaces the earlier placeholder-only notion of package linking and makes explicit that cross-package references are part of the authoring contract rather than an accidental side effect of later graph integration.
