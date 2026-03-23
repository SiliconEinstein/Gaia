# Parameterization

> **Status:** Current canonical

Graph IR deliberately separates structure from parameters. The factor graph topology (nodes and edges) is deterministic and auditable. Priors, conditional probabilities, and beliefs live in separate overlay objects that reference the graph by hash.

## The Principle

Structure is authored and submitted. Parameters are derived and runtime-specific.

- **Structure** (Graph IR): deterministic from source, submitted during publish, re-verifiable by the review engine.
- **Parameters** (overlays): derived locally for preview, or managed by the registry for global inference. Not submitted during publish.

This separation means the same structural graph can be reasoned over with different probability inputs -- the author's local preview, the reviewer's independent assessment, and the registry's global state.

## LocalParameterization Overlay

```
LocalParameterization:
    graph_hash:         str                          # SHA-256 of the canonical JSON
    node_priors:        dict[str, float]             # keyed by local_canonical_id
    factor_parameters:  dict[str, FactorParams]      # keyed by factor_id

FactorParams:
    conditional_probability: float                   # reasoning factors only
```

The `graph_hash` binds this overlay to a specific version of the local canonical graph. If the graph changes (e.g., after re-running `gaia build`), the overlay becomes invalid and must be regenerated.

### Key resolution

- `node_priors` is keyed by `local_canonical_id`. Full IDs or unambiguous prefixes are allowed.
- `factor_parameters` is keyed by `factor_id`. Full IDs or unambiguous prefixes are allowed.

### Completeness requirement

A valid overlay must provide:
- Priors for every belief-bearing node in the active local graph
- `conditional_probability` for every reasoning/abstraction factor in that graph

Missing entries make the overlay invalid. BP does not fall back to hidden defaults.

### Cromwell's rule

All priors and conditional probabilities are clamped to `[epsilon, 1 - epsilon]` where `epsilon = 1e-3` when the overlay is loaded. This prevents degenerate zero-partition states during BP.

### Not submitted

The local parameterization overlay is NOT submitted during `gaia publish`. It exists only for author-local preview inference via `gaia infer`. The review engine makes independent probability judgments.

## GlobalInferenceState

```
GlobalInferenceState:
    graph_hash:         str                          # hash of the global canonical graph
    node_priors:        dict[str, float]             # keyed by full global_canonical_id
    factor_parameters:  dict[str, FactorParams]      # keyed by factor_id
    node_beliefs:       dict[str, float]             # keyed by full global_canonical_id
    updated_at:         str                          # ISO timestamp
```

The `GlobalInferenceState` is managed by the registry, not authored by package authors. It may be seeded from approved review-report judgments, but the review report is not itself a BP input artifact. Registry/runtime code normalizes those judgments into the current global graph state before BP runs.

### Scope difference

| | LocalParameterization | GlobalInferenceState |
|---|---|---|
| **Scope** | One package | All ingested packages |
| **Graph** | Local canonical graph | Global canonical graph |
| **ID namespace** | `local_canonical_id` | `global_canonical_id` |
| **Managed by** | Author (local tool) | Registry (server) |
| **Submitted** | No | N/A (server-side only) |
| **Includes beliefs** | No (beliefs are output of `gaia infer`) | Yes (persisted between BP runs) |

## Graph Hash Integrity

The graph hash serves as a version lock:

1. `gaia build` produces `local_canonical_graph.json` with a deterministic canonical JSON serialization.
2. `local_graph_hash = SHA-256(canonical JSON)` is computed.
3. The `LocalParameterization.graph_hash` must match the current graph hash.
4. During review, the review engine re-compiles the raw graph from source and verifies the hash matches the submitted graph.

This ensures that the parameterization was generated for the exact graph being reviewed, and that the submitted graph was not tampered with after compilation.

## Source

- `libs/graph_ir/models.py` -- `LocalParameterization`, `FactorParams`
- `libs/inference/factor_graph.py` -- `CROMWELL_EPS`, Cromwell clamping
- `docs/foundations/bp/local-vs-global.md` -- how local and global inference consume these overlays
