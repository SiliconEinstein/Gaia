# Domain Vocabulary

> **Status:** Current canonical

Core terms used across Gaia documentation.

## Knowledge

A versioned proposition -- the fundamental unit of the knowledge graph. A knowledge object carries content (the proposition text), a type (claim, question, setting, action, contradiction, equivalence), and an author-assigned prior (degree of initial belief).

For the full type taxonomy, see `../cli/gaia-lang/knowledge-types.md`. For storage schema, see `../graph-ir/knowledge-nodes.md`.

## Chain

A multi-step reasoning structure connecting premises to a conclusion. Each chain has a type (deduction, induction, abstraction, contradiction, retraction, equivalence) that classifies the reasoning pattern. In Graph IR, each chain produces one factor node.

For factor node details, see `../graph-ir/factor-nodes.md`.

## Module

A logical grouping of knowledge objects and chains within a package. In the authoring surface, each `.typ` file (other than `lib.typ` and `gaia.typ`) is implicitly a module. Modules exist for organizational clarity -- they do not create independent BP boundaries.

## Package

A complete, versioned knowledge container. Analogous to a git repository or a published paper. The unit of submission, review, and integration. Identity: `(package_id, version)`.

For package authoring structure, see `../cli/gaia-lang/package-model.md`. For package lifecycle, see `../cli/lifecycle.md`.

## Factor Graph

A bipartite graph with variable nodes (knowledge objects) and factor nodes (reasoning constraints). The core computational structure for belief propagation. See `../graph-ir/overview.md` and `../bp/inference.md`.

## Graph IR

The structural intermediate representation between Gaia Lang and BP. A first-class submission artifact with three identity layers: Raw Graph, Local Canonical Graph, and Global Canonical Graph. See `../graph-ir/overview.md`.

## Belief

The posterior plausibility of a knowledge object, computed by BP. In [0, 1], where 0.5 represents maximum ignorance (MaxEnt). See `../theory/belief-propagation.md`.

## Source

- `libs/storage/models.py` -- Pydantic models for all core types
