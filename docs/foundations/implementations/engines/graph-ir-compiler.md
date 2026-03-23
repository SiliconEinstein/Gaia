# Graph IR Compiler

> **Status:** Current canonical

This document describes the Graph IR compilation pipeline as implemented. For the design rationale and structural specification, see `docs/foundations_archive/graph-ir.md`.

## What Graph IR Is

Graph IR is a structural factor graph intermediate representation between the authored Typst source and belief propagation. It exists at three identity levels:

```
Raw Graph  (1:1 with source declarations)
    ↓  local canonicalization
Local Canonical Graph  (package-scoped deduplication)
    ↓  global canonicalization
Global Canonical Graph  (cross-package identity)
```

Each level adds an identity layer. The raw graph preserves exact source traceability. The local canonical graph allows within-package merging (currently singleton -- no merging). The global canonical graph maps equivalent propositions across packages.

## Compilation Pipeline

### Step 1: Typst Loading

The Typst loader (`libs/lang/typst_loader.py`) runs `typst query` to extract `gaia-node` figures from compiled Typst documents, producing a dict with `nodes`, `factors`, `constraints`, `package`, and `version`.

### Step 2: Raw Graph Compilation

See `libs/graph_ir/typst_compiler.py:compile_v4_to_raw_graph()`.

The compiler processes the loader output into a `RawGraph`:

1. **Knowledge nodes**: Each non-external node becomes a `RawKnowledgeNode`. The v4 type map resolves `setting`, `question`, `claim`, `action`. Relation nodes (`contradiction`, `equivalence`) get their type from the constraint map.

2. **External nodes**: Nodes from `gaia-bibliography` become `RawKnowledgeNode` with `ext:package/node` IDs, preserving cross-package references.

3. **Reasoning factors**: Each `from:` parameter generates a `FactorNode` of type `infer` linking premise nodes to the conclusion.

4. **Constraint factors**: `#relation` declarations with `between:` generate `contradiction` or `equivalence` factors.

### Step 3: Local Canonicalization

See `libs/graph_ir/build_utils.py:build_singleton_local_graph()`.

Currently implements singleton canonicalization: each raw node maps to exactly one `LocalCanonicalNode` with no merging. The raw-to-local mapping is recorded in a `CanonicalizationLogEntry` for auditability.

### Step 4: Local Parameterization

See `libs/graph_ir/build_utils.py:derive_local_parameterization_from_raw()`.

Derives the probability overlay for local BP:

- **Node priors**: From explicit metadata if present, otherwise defaults by type (`setting` = 1.0, everything else = 0.5).
- **Factor parameters**: `infer`, `abstraction`, and `reasoning` factors get `conditional_probability = 1.0` by default.

The parameterization is bound to a specific graph via `graph_hash`.

## Node Identity

Three ID schemes, each deterministic:

| ID type | Format | Generation | Code |
|---------|--------|------------|------|
| `raw_node_id` | `raw_{sha256[:16]}` | SHA-256 of `(package, version, module, name, type, kind, content, parameters)` | `build_utils.py:raw_node_id()` |
| `local_canonical_id` | `lcn_{sha256[:16]}` | SHA-256 of the raw_node_id | `build_utils.py:local_canonical_id()` |
| `global_canonical_id` | `gcn_{sha256[:16]}` | SHA-256 of `(type, content, counter)` | `canonicalize.py:_generate_gcn_id()` |
| `factor_id` | `f_{sha256[:16]}` | SHA-256 of `(kind, module, name[, suffix])` | `build_utils.py:factor_id()` |

External nodes use the format `ext:{package}/{node}` instead of a hash-based ID.

## Factor Types

| Type | Meaning | Created from |
|------|---------|--------------|
| `infer` | Premises support conclusion (deduction/induction) | `from:` parameter on claims |
| `contradiction` | Two claims cannot both be true | `#relation(type: "contradiction")` |
| `equivalence` | Two claims express the same proposition | `#relation(type: "equivalence")` |
| `abstraction` | Schema-to-ground instantiation | Planned, not yet in compiler |
| `instantiation` | Ground instance of a schema | Planned, not yet in compiler |

## Graph IR Models

Defined in `libs/graph_ir/models.py`:

- **`RawGraph`**: `package`, `version`, `knowledge_nodes: list[RawKnowledgeNode]`, `factor_nodes: list[FactorNode]`. Supports `canonical_json()` and `graph_hash()` for integrity.
- **`RawKnowledgeNode`**: `raw_node_id`, `knowledge_type`, `kind`, `content`, `parameters`, `source_refs`, `metadata`.
- **`LocalCanonicalGraph`**: Same structure but with `LocalCanonicalNode` (adds `local_canonical_id`, `member_raw_node_ids`, `representative_content`).
- **`FactorNode`**: `factor_id`, `type`, `premises[]`, `contexts[]`, `conclusion`, `source_ref`, `metadata`.
- **`LocalParameterization`**: `graph_hash`, `node_priors: dict`, `factor_parameters: dict`.

## Current State

The compiler works for v3 and v4 Typst packages. The full pipeline (load, compile, canonicalize, parameterize) is exercised by `gaia build` and `gaia infer` CLI commands and by the server ingestion pipeline. Test coverage exists in `tests/libs/graph_ir/`.

## Target State

The Graph IR compiler is stable. No major changes are planned. The singleton local canonicalization may eventually support semantic merging within a package, but this is not prioritized. Schema/ground distinction (`abstraction` and `instantiation` factors) is designed but not yet implemented in the compiler.
