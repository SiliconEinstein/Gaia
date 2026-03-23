# Reasoning Relations

> **Status:** Current canonical

This document describes how knowledge nodes connect through reasoning links and constraints, and how those connections map to factor graph structures for belief propagation.

## Reasoning via `from:`

A `#claim` or `#action` with a `from:` parameter declares that the listed labels are **load-bearing premises** for the conclusion. Each such declaration generates one **reasoning factor** in the Graph IR:

```
#claim(from: (<A>, <B>))[C is true][because A and B jointly imply C] <C>
```

produces:

```
FactorNode(type="reasoning", premises=[A, B], conclusion=C)
```

`from:` means "this conclusion materially depends on these premises." It is not a generic relevance link. Background conditions and regime assumptions should eventually use a separate `under:` role (not yet implemented in v4).

## Constraints via `between:`

A `#relation` with a `between:` parameter declares a structural constraint between two existing nodes. The relation itself becomes a knowledge node, and a constraint factor connects them:

```
#relation(type: "contradiction", between: (<X>, <Y>))[X and Y conflict]
```

produces:

```
KnowledgeNode(type="contradiction", id=R)
FactorNode(type="mutex_constraint", premises=[R, X, Y], conclusion=R)
```

The relation node R participates as a premise in the factor. This allows BP to lower the relation's own belief when both constrained claims have strong evidence.

## Chain Types

The `Chain` model in storage represents a display-layer multi-step reasoning structure. Each chain has a `type` that classifies the reasoning pattern:

| Chain type | Meaning | Factor potential |
|---|---|---|
| **deduction** | Premises logically entail the conclusion | Conditional potential with high p |
| **induction** | Premises provide non-conclusive support | Conditional potential with moderate p |
| **abstraction** | Premises support a more general conclusion | Same as infer (transitional; target is deterministic entailment) |
| **retraction** | Premises constitute evidence *against* the conclusion | Inverted conditional potential |
| **contradiction** | Declares mutual exclusion between nodes | Penalty on all-premises-true |
| **equivalence** | Declares semantic identity between nodes | Agreement/disagreement reward |

All reasoning chain types (deduction, induction, abstraction) use the same conditional potential shape in the current runtime -- the chain type determines the expected range of the conditional probability parameter, not a different potential function.

## Mapping to Factor Potentials

For detailed potential function definitions, see `docs/foundations/theory/belief-propagation.md`. The key mappings:

**Reasoning factors** (deduction/induction/abstraction):
- All premises true + conclusion true: potential = p (conditional probability)
- All premises true + conclusion false: potential = 1 - p
- Any premise false: potential = 1.0 (unconstrained)

**Retraction factors**:
- Inverted: all premises true suppresses the conclusion instead of supporting it.

**Contradiction factors**:
- All contradicted claims simultaneously true: potential = epsilon (near zero)
- Otherwise: potential = 1.0

**Equivalence factors**:
- Claims agree: potential = p (constraint strength, derived from relation belief)
- Claims disagree: potential = 1 - p

## Context vs. Premise

Graph IR distinguishes two dependency roles:

- **Premise** (`premises` field): load-bearing. False premises undermine the conclusion's validity. Creates BP edges.
- **Context** (`contexts` field): weak/background dependency. Does not create BP edges. Consumed by parameterization overlays when assigning factor probabilities.

> **Not yet in language surface**: v4 only has `from:` (premise). A separate `under:` or context role is planned but not yet implemented.

## Source

- `libs/storage/models.py` -- `Chain.type` enum, `FactorNode` structure
- `libs/inference/bp.py` -- potential function implementations
- `docs/foundations/theory/belief-propagation.md` -- factor potential definitions
- `docs/foundations_archive/graph-ir.md` -- factor type specifications
