# Factor Nodes

> **Status:** Current canonical

This document is the single definition of FactorNode -- the constraint node in Gaia's factor graph. For potential functions (computational semantics), see [../bp/potentials.md](../bp/potentials.md).

## FactorNode Schema

Every factor in Graph IR has this structure:

```
FactorNode:
    factor_id:    str              # f_{sha256[:16]} from (kind, module, name)
    type:         str              # reasoning | instantiation | mutex_constraint | equiv_constraint | retraction
    premises:     list[str]        # knowledge node IDs -- strong dependency, creates BP edges
    contexts:     list[str]        # knowledge node IDs -- weak dependency, no BP edges
    conclusion:   str | None       # single output knowledge node
    source_ref:   SourceRef | None # trace to authoring source
    metadata:     dict | None
```

Factor identity is deterministic: `f_{sha256[:16]}` computed from chain ID or source construct. Same reasoning link always gets the same factor ID across rebuilds.

Factors are shared across all three identity layers (raw, local canonical, global canonical) -- only the node ID namespace changes. When factors are lifted from local to global scope during canonicalization, premise/context/conclusion IDs are rewritten from `lcn_` to `gcn_` namespace.

## Factor Types

### reasoning

Generated from: `#claim(from: ...)` or `#action(from: ...)` declarations (via ChainExpr).

- **Premises**: the knowledge nodes listed in `from:`.
- **Contexts**: indirect dependencies (not yet expressible in v4 surface).
- **Conclusion**: the claim or action being supported.
- **Covers**: deduction (high p), induction (moderate p), abstraction (same potential shape, transitional).
- **Granularity**: one factor per ChainExpr, not per step. Intermediate steps are internal to the chain.

### instantiation

Generated from: elaboration of schema nodes (parameterized knowledge) into ground instances.

- **Premises**: `[schema_node]` -- the universal/parameterized proposition.
- **Contexts**: `[]`
- **Conclusion**: the ground instance node.
- **Binary**: each instantiation factor connects exactly one schema to one instance. Partial instantiation chains through intermediate nodes.

### mutex_constraint

Generated from: `#relation(type: "contradiction", between: (<A>, <B>))`.

- **Premises**: `[R, A, B]` where R is the relation node, A and B are the constrained claim nodes.
- **Conclusion**: R (acts as read-only gate in current runtime; target design makes R a full participant).

### equiv_constraint

Generated from: `#relation(type: "equivalence", between: (<A>, <B>))`.

- **Premises**: `[R, A, B]` where R is the relation node, A and B are the equated claim nodes.
- **Conclusion**: R (acts as read-only gate in current runtime; target design makes R a full participant).
- **N-ary**: decomposed into pairwise factors sharing the same relation node R.

### retraction

Generated from: chains with `type: "retraction"`.

- **Premises**: the evidence nodes that argue against the conclusion.
- **Conclusion**: the claim being retracted.

## Compilation Rules

| Source construct | Knowledge node(s) | Factor node(s) |
|---|---|---|
| `#claim` / `#setting` / `#question` / `#action` (no `from:`) | One knowledge node | None |
| `#claim(from: ...)` / `#action(from: ...)` | One knowledge node | One reasoning factor |
| `#relation(type: "contradiction", between: ...)` | One contradiction node | One mutex_constraint factor |
| `#relation(type: "equivalence", between: ...)` | One equivalence node | One equiv_constraint factor |
| Schema elaboration | Instance node | One instantiation factor per pair |

## Context vs Premise

- **Premise** (`premises` field): load-bearing. False premises undermine conclusion validity. Creates BP edges -- BP sends and receives messages along these connections.
- **Context** (`contexts` field): weak/background dependency. Does not create BP edges. Consumed by parameterization overlays when assigning factor probabilities.

> v4 only has `from:` (premise). A separate `under:` context role is planned but not yet implemented.

## Note on Storage Model

The storage model (`libs/storage/models.py`) uses slightly different enum values for factor types. The `FactorNode` type enum in storage uses `infer` rather than `reasoning`, and lists: `infer | instantiation | abstraction | contradiction | equivalence`. The Graph IR spec uses `reasoning | instantiation | mutex_constraint | equiv_constraint | retraction`. These are converging; the storage model reflects the current implementation while Graph IR reflects the target schema.

## Source

- `libs/graph_ir/models.py` -- Graph IR `FactorNode`
- `libs/storage/models.py` -- Storage `FactorNode`
- [../bp/potentials.md](../bp/potentials.md) -- potential functions for each factor type
