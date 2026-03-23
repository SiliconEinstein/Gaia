# Corroboration And Conditional Independence

| Field | Value |
|---|---|
| Status | Transitional |
| Level | Foundation |
| Scope | Repo-wide |
| Related | [../semantics/knowledge-relations.md](../semantics/knowledge-relations.md), [../contracts/artifacts/investigation-artifacts.md](../contracts/artifacts/investigation-artifacts.md), [../contracts/services/curation-service.md](../contracts/services/curation-service.md) |

## Purpose

This file is a legacy bridge for the older `theory/corroboration-and-conditional-independence.md` path.

It no longer serves as the canonical home for corroboration semantics.

## Current Canonical Judgment

`corroboration` is not a core semantic relation family in Gaia.

Instead:

- base semantic relations are defined in [../semantics/knowledge-relations.md](../semantics/knowledge-relations.md)
- corroboration and independence questions are handled as review/curation-side investigation artifacts
- those artifacts are defined in [../contracts/artifacts/investigation-artifacts.md](../contracts/artifacts/investigation-artifacts.md)

## Why This Matters

If corroboration is treated as just another base relation, the graph risks double-counting support that should instead be analyzed as:

- multiple support paths
- independence or non-independence of evidence
- shared hidden premises
- curation-side investigation work

## Migration Note

Use the canonical docs above for current work.

This file remains only as a bridge for older links and references.
