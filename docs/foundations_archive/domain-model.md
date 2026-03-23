# Gaia Domain Model

| 文档属性 | 值 |
|---------|---|
| 状态 | **Superseded** |
| 取代者 | [theory/scientific-ontology.md](theory/scientific-ontology.md), [language/gaia-language-spec.md](language/gaia-language-spec.md), [review/package-artifact-profiles.md](review/package-artifact-profiles.md) |

## Status

This document is no longer the canonical source of truth for Gaia vocabulary.

It originally described an older vocabulary centered on `closure`, local chain structure, and early package-schema assumptions. That role is now split more cleanly across newer docs:

- [theory/scientific-ontology.md](theory/scientific-ontology.md)
  - scientific object model
  - BP-bearing vs non-BP objects
  - abstraction / induction / instantiation boundaries
- [language/gaia-language-spec.md](language/gaia-language-spec.md)
  - authored package surface
  - declaration types and metadata
  - package structure
- [review/package-artifact-profiles.md](review/package-artifact-profiles.md)
  - `knowledge` / `investigation` / `review` / `rebuttal` package profiles
- [review/service-boundaries.md](review/service-boundaries.md)
  - `ReviewService` vs `CurationService`

## Current Rule

Do not introduce new normative concepts here.

When updating Gaia foundations, use:

1. [theory/scientific-ontology.md](theory/scientific-ontology.md) for ontology and modeling boundaries
2. [language/gaia-language-spec.md](language/gaia-language-spec.md) for authored surface semantics
3. [graph-ir.md](graph-ir.md) for structural IR semantics
4. [review/package-artifact-profiles.md](review/package-artifact-profiles.md) for formal artifact classes

This file remains only as a compatibility redirect for old links.
