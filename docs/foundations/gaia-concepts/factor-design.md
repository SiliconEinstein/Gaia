# Factor Design

> **Status:** Current canonical

A factor is a reasoning link in Gaia's factor graph. Factors are constraint nodes in the bipartite graph that connect knowledge variables and encode the semantics of their relationship through potential functions.

## Factor Structure

Every factor in Graph IR has the same structural schema:

```
FactorNode:
    factor_id:    str              # f_{sha256[:16]} from (kind, module, name)
    type:         str              # reasoning | instantiation | mutex_constraint | equiv_constraint
    premises:     list[str]        # knowledge node IDs with strong dependency
    contexts:     list[str]        # knowledge node IDs with weak dependency (no BP edges)
    conclusion:   str | None       # the single output knowledge node
    source_ref:   SourceRef | None # trace to authoring source
    metadata:     dict | None
```

**Factor identity**: `factor_id` is deterministic -- `f_{sha256[:16]}` computed from the chain ID or source construct. This ensures the same reasoning link always gets the same factor ID across rebuilds.

## Factor Types

### 1. Reasoning (`reasoning` / `infer`)

Generated from: `#claim(from: ...)` or `#action(from: ...)` declarations (via ChainExpr).

- **Premises**: the knowledge nodes listed in `from:`.
- **Contexts**: indirect dependencies (not yet expressible in v4 surface).
- **Conclusion**: the claim or action being supported.
- **Potential**: conditional on all-premises-true. When all premises are true, conclusion follows with conditional probability p. When any premise is false, the factor is unconstrained (potential = 1.0).
- **Granularity**: one factor per ChainExpr, not per step. Intermediate steps are internal to the chain.

Covers deduction (high p), induction (moderate p), and abstraction (same potential shape, transitional).

### 2. Contradiction (`mutex_constraint`)

Generated from: `#relation(type: "contradiction", between: (<A>, <B>))`.

- **Premises**: the relation node R plus the constrained claim nodes [A, B].
- **Conclusion**: the relation node R (acts as read-only gate in current runtime).
- **Potential**: penalizes the configuration where all constrained claims are simultaneously true (potential = epsilon). Otherwise unconstrained.
- **BP behavior**: sends inhibitory backward messages when contradicted claims both have high belief. The weaker claim is suppressed more. If both have overwhelming evidence, the relation node's own belief drops.

### 3. Equivalence (`equiv_constraint`)

Generated from: `#relation(type: "equivalence", between: (<A>, <B>))`.

- **Premises**: the relation node R plus the equated claim nodes [A, B].
- **Conclusion**: the relation node R (acts as read-only gate in current runtime).
- **Potential**: rewards agreement (both true or both false) with weight p derived from the relation node's belief. Penalizes disagreement with weight 1 - p.
- **N-ary**: decomposed into pairwise factors sharing the same relation node.

### 4. Instantiation (`instantiation`)

Generated from: elaboration of schema nodes (parameterized knowledge) into ground instances.

- **Premises**: `[schema_node]` -- the universal/parameterized proposition.
- **Contexts**: `[]`
- **Conclusion**: the ground instance node.
- **Potential**: deterministic implication. Schema true + instance false = zero potential (contradiction). Schema false leaves instance unconstrained. Instance false forces schema false (counterexample).
- **Binary**: each instantiation factor connects exactly one schema to one instance. Partial instantiation chains through intermediate nodes.

### 5. Retraction

Generated from: chains with `type: "retraction"`.

- **Premises**: the evidence nodes that argue against the conclusion.
- **Conclusion**: the claim being retracted.
- **Potential**: inverted conditional. When premises are true, the conclusion is suppressed (potential for conclusion=true is 1-p). Absence of retraction evidence is not evidence of support.

> **Note on storage model**: the `FactorNode` type enum in `libs/storage/models.py` uses `"infer"` rather than `"reasoning"`, and lists five types: `infer | instantiation | abstraction | contradiction | equivalence`. The Graph IR spec uses `reasoning | instantiation | mutex_constraint | equiv_constraint`. These are converging; the storage model is the current implementation.

## Factor Creation Summary

| Source construct | Knowledge node(s) | Factor node(s) |
|---|---|---|
| `#claim` / `#setting` / `#question` / `#action` (no `from:`) | One knowledge node | None |
| `#claim(from: ...)` / `#action(from: ...)` | One knowledge node | One reasoning factor |
| `#relation(type: "contradiction", between: ...)` | One contradiction node | One mutex_constraint factor |
| `#relation(type: "equivalence", between: ...)` | One equivalence node | One equiv_constraint factor |
| Schema elaboration (parameterized node) | Instance node | One instantiation factor per schema-instance pair |

## Source

- `libs/storage/models.py` -- `FactorNode` model
- `libs/inference/bp.py` -- potential function implementations
- `docs/foundations/theory/belief-propagation.md` -- factor potential definitions
- `docs/foundations_archive/graph-ir.md` -- full Graph IR spec
