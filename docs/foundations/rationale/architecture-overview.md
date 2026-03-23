# Architecture Overview

> **Status:** Current canonical

Gaia's architecture is organized around a three-layer compilation pipeline and two product surfaces that share a common intermediate representation.

## Three-Layer Pipeline

```
Gaia Lang (authored surface)
    |
    v  gaia build (deterministic compilation)
Graph IR (structural factor graph)
    |
    v  gaia infer / server BP
Belief Propagation (probabilistic inference)
```

Each layer has a clean boundary:

1. **Gaia Lang** -- the authored surface. A Typst-based DSL for declaring knowledge objects, reasoning chains, and package structure. Compiles deterministically to Graph IR. See `../cli/gaia-lang/spec.md`.

2. **Graph IR** -- the structural intermediate representation. A bipartite factor graph with knowledge nodes (variables) and factor nodes (constraints). Graph IR is the **submission artifact** -- the contract between CLI and LKM. See `../graph-ir/overview.md`.

3. **Belief Propagation** -- probabilistic inference on Graph IR. Computes posterior beliefs for all knowledge nodes given priors and factor potentials. See `../bp/inference.md`.

## Two Product Surfaces

Graph IR is the boundary between Gaia's two product surfaces:

| | CLI | LKM (Server) |
|---|---|---|
| **Scope** | Local, single package | Global, multi-package |
| **Input** | Gaia Lang source (.typ files) | Published Graph IR |
| **Compilation** | Gaia Lang -> Graph IR | N/A -- receives Graph IR |
| **Inference** | Local BP on local canonical graph | Global BP on global canonical graph |
| **Storage** | LanceDB + Kuzu (embedded) | LanceDB + Neo4j + Vector |
| **Additional services** | -- | Review, Curation, Global Canonicalization |

The CLI is a **frontend** for Graph IR -- analogous to how Clang is a frontend for LLVM IR. The LKM never sees Gaia Lang; it operates purely on Graph IR.

## Why This Decomposition

**Graph IR as the shared contract provides:**

- **Auditable lowering** -- the mapping from authored source to factor graph is explicit and deterministic
- **Frontend independence** -- future frontends can produce Graph IR without Typst
- **CLI <-> LKM decoupling** -- the LKM validates and operates on Graph IR, independent of the authoring surface
- **Separation of structure and parameters** -- Graph IR carries structure only; probabilities live in parameterization overlays

**Gaia Lang as a CLI-specific frontend because:**

- The language is an authoring concern, not an inference concern
- The LKM receives compiled artifacts, not source code
- Language evolution does not affect the LKM's contracts

## Analogies

| Gaia | Compiler ecosystem | Role |
|---|---|---|
| Gaia Lang | Rust / C++ / Swift source | Authored surface |
| Graph IR | LLVM IR / MIR / SIL | Shared intermediate representation |
| BP | LLVM codegen / execution | Computation on IR |
| CLI | cargo / clang / swift build | Local tool (compiles + runs locally) |
| LKM | crates.io / PyPI / npm registry | Package registry + compute backend |

## Source

- `docs/foundations/rationale/product-scope.md` -- product positioning
- `docs/foundations/theory/plausible-reasoning.md` -- theoretical foundation
