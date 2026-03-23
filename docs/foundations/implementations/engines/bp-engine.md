# Belief Propagation Engine

> **Status:** Current canonical -- target evolution noted

This document describes the BP engine as implemented. For the theoretical foundations and planned evolution, see `docs/foundations_archive/bp-on-graph-ir.md` and `docs/foundations_archive/theory/inference-theory.md`.

## Factor Graph Construction

See `libs/inference/factor_graph.py`.

`FactorGraph` is a bipartite graph between variable nodes and factor nodes:

- **Variables**: `dict[int, float]` mapping node ID to prior belief p(x=1). Each knowledge node becomes a binary variable.
- **Factors**: `list[dict]` where each factor has `edge_id`, `premises: list[int]`, `conclusions: list[int]`, `probability: float`, `edge_type: str`, and optional `gate_var: int`.

**Cromwell's rule** is enforced at construction time. All priors and factor probabilities are clamped to `[epsilon, 1-epsilon]` where `epsilon = 1e-3` (see `factor_graph.py:CROMWELL_EPS`). This prevents degenerate zero-partition states during BP.

The adapter layer (`libs/graph_ir/adapter.py`) builds a `FactorGraph` from Graph IR by mapping `LocalCanonicalNode` IDs to integer variable IDs and `FactorNode` entries to factor dicts.

## BP Algorithm

See `libs/inference/bp.py:BeliefPropagation`.

The engine implements sum-product loopy belief propagation on binary variables.

### Message Representation

Every message is a 2-vector `[p(x=0), p(x=1)]`, always normalized to sum to 1. This is the `Msg` type (NumPy `NDArray[float64]` of shape `(2,)`).

### Synchronous Schedule

Each iteration:

1. **Compute all var-to-factor messages**: For each `(variable, factor)` edge, the message is the variable's prior times the product of all incoming factor-to-var messages except from this factor. See `bp.py:_compute_var_to_factor()`.

2. **Compute all factor-to-var messages**: For each `(factor, variable)` edge, marginalize over all 2^(n-1) assignments of other variables, weighting by factor potential and incoming var-to-factor messages. See `bp.py:_compute_factor_to_var()`.

3. **Damp and normalize**: New messages are blended with old via `damping * new + (1 - damping) * old`, then normalized.

4. **Compute beliefs**: Each variable's belief is its prior times the product of all incoming factor-to-var messages, normalized.

5. **Check convergence**: If the maximum absolute change in any belief is below the threshold, stop.

### Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `damping` | 0.5 | Blending factor; 1.0 = fully replace, 0.0 = keep old |
| `max_iterations` | 50 | Upper bound on sweeps |
| `convergence_threshold` | 1e-6 | Stop when max belief change is below this |

### Diagnostics

`run_with_diagnostics()` returns a `BPDiagnostics` object containing:
- `iterations_run`, `converged`, `max_change_at_stop`
- `belief_history: dict[int, list[float]]` -- per-variable belief trace across iterations
- `direction_changes: dict[int, int]` -- count of sign reversals in belief deltas (oscillation signal for conflict detection)

## Factor Potentials

See `bp.py:_evaluate_potential()`.

Each factor type defines a potential function over the joint assignment of its variables:

### Standard types (gated on "all premises true")

When not all premises are true, the potential is 1.0 (unconstrained).

When all premises are true:

| Edge type | Potential | Meaning |
|-----------|-----------|---------|
| `deduction` / `induction` | `p` if conclusion=1, `1-p` if conclusion=0 | Standard conditional: premises support conclusion with probability p |
| `retraction` | `1-p` if conclusion=1, `p` if conclusion=0 | Inverted: premises argue against conclusion |
| `contradiction` (Jaynes) | `1-p` regardless of conclusion value | The all-premises-true configuration is penalized. Conclusion variables are structurally present but do not participate -- the potential is independent of conclusion values, so factor-to-conclusion messages are uniform and conclusions stay at their priors |

### Relation types

| Edge type | Potential | Meaning |
|-----------|-----------|---------|
| `relation_contradiction` | `1-p` if all premises=1, else 1.0 | Penalizes simultaneous truth of related claims |
| `relation_equivalence` | `p` if A==B, `1-p` if A!=B | Rewards agreement between two claims |

### Read-only gate variables

Relation factors support an optional `gate_var` -- a variable whose current belief is used as the effective constraint strength `p`, but which does not receive messages from the factor. This prevents feedback loops between the relation node and its constraint. See `bp.py:_compute_factor_to_var()`.

## Local BP vs Global BP

The same `BeliefPropagation` class is used for both:

- **Local BP** (`gaia infer`): Runs on the `LocalCanonicalGraph` with `LocalParameterization` as the probability source. Scope is one package.
- **Global BP** (server): Runs on the global canonical graph with `GlobalInferenceState` as the probability source. Scope is all ingested packages.

The only difference is graph scope and parameterization source. The algorithm, message schedule, and factor potentials are identical.

## Current State

The BP engine is functional and tested. Default parameters are `damping=0.5`, `max_iterations=50`, `convergence_threshold=1e-6`. Factor potentials cover deduction, retraction, contradiction (Jaynes), relation_contradiction, and relation_equivalence. Diagnostics support conflict detection via belief oscillation tracking.

## Target State

The planned evolution (from `docs/foundations_archive/theory/inference-theory.md`) includes:

- **Noisy-AND + leak model**: Replace the current all-or-nothing gating with a Noisy-AND potential that allows partial premise support and a leak probability for background causes.
- **Schema/ground BP**: When instantiation factors are implemented in Graph IR, BP will need to handle message passing between schema (universally quantified) and ground (concrete) variables.
- **Asynchronous schedule**: The current synchronous schedule may be replaced with a priority-based asynchronous schedule for better convergence on large graphs.

These changes affect factor potential functions and scheduling but not the core message-passing framework.
