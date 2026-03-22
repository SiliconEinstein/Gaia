# Knowledge Relations

| Field | Value |
|---|---|
| Status | Current canonical |
| Level | Foundation |
| Scope | Repo-wide |
| Related | [scientific-knowledge.md](scientific-knowledge.md), [gaia-reasoning-model.md](gaia-reasoning-model.md), [../theory/inference-theory.md](../theory/inference-theory.md), [../theory/corroboration-and-conditional-independence.md](../theory/corroboration-and-conditional-independence.md) |

## Purpose

This document defines the main relation types between Gaia knowledge items.

Its job is to state which relations belong in Gaia's semantic core, which are merely local dependency roles, and which should be treated as review or curation artifacts instead of base relation types.

## A First Principle

Not every useful connection between knowledge items should be modeled as the same kind of relation.

Gaia needs to distinguish at least three things:

- semantic relations between knowledge items
- local authoring roles such as premise and background condition
- workflow artifacts such as review findings and investigation queues

This document defines only the first category.

## Core Relation Families

| Relation family | Typical direction | Truth-preserving | Main role |
|---|---|---:|---|
| `reasoning_support` | claim(s) -> claim | No | Probabilistic support |
| `entailment` | claim -> claim | Yes | Truth-preserving implication |
| `instantiation` | law/schema claim -> concrete claim | Yes | Specialized entailment |
| `contradiction` | claim <-> claim | No | Mutual incompatibility constraint |
| `equivalence` | claim <-> claim | Yes when valid | Same-meaning or same-truth-condition constraint |

## Reasoning Support

`reasoning_support` is the broad relation family for nontrivial scientific support.

It covers cases where one or more claims increase the plausibility of another claim without making it deductively guaranteed.

This family includes different modes, discussed further in [gaia-reasoning-model.md](gaia-reasoning-model.md), such as:

- deductive-style support
- inductive support
- abductive support

The common idea is:

- the source claims matter for the target claim
- the target claim becomes more or less plausible depending on the source claims
- the relation is not just a raw citation or textual adjacency

## Entailment

`entailment` is the truth-preserving relation family.

If `A entails B`, then whenever `A` is true, `B` must also be true in the intended semantics.

This relation is appropriate for cases where a weaker claim follows from a stronger one, including many cases of abstraction output.

## Instantiation

`instantiation` is a specialized truth-preserving relation from a more general law-like or schema-like claim to a concrete case claim.

It is separated out because it is semantically important in science, even if its underlying truth-preserving structure is close to entailment.

Examples:

- a law claim implies a specific case under a specified regime
- a quantified regularity implies a particular instance claim

## Contradiction

`contradiction` expresses that two claims should not both hold together.

Important boundary:

- contradiction is not "bad data cleanup"
- it is a first-class epistemic relation
- in a plausible-reasoning system, contradiction changes beliefs rather than exploding the logic

Gaia therefore treats contradiction as a meaningful relation in its own right, not merely as an exception state.

## Equivalence

`equivalence` expresses that two claims should be treated as semantically or truth-condition-wise the same.

This matters because scientific knowledge often contains:

- alternate phrasings
- equivalent formulations
- claims produced by different packages or traditions that should collapse to one shared meaning

Equivalence is therefore not just editorial deduplication; it is part of knowledge integration.

## Relations That Are Not Core Base Families

### Abstraction

`abstraction` is better treated as a knowledge-construction operation than as a primary persistent relation family.

Its usual result is:

- a new `AbstractClaim`
- entailment links from member claims to that abstract claim

### Generalization

`generalization` is also better treated as a construction process that produces a broader target claim, typically a `GeneralizationCandidate`, rather than as a standalone base relation family.

The resulting support toward that broader claim belongs in the inductive side of `reasoning_support`.

### Corroboration / independent evidence

Independent evidence review should not be treated as a core semantic relation family.

It is better understood as:

- a review or curation artifact
- an audit of whether multiple support paths are genuinely independent

The belief effect should come from correct graph structure, not from inventing an extra "corroboration relation" on top of the same structure.

## Local Dependency Roles Are Not Global Relation Families

Gaia also needs local dependency roles such as:

- load-bearing premise
- background condition or applicability context

Those roles matter for authoring and lowering, but they are not the same thing as the global semantic relation families defined in this document.

In other words:

- "premise" and "context" are relation roles in a local reasoning step
- `reasoning_support`, `entailment`, `contradiction`, and `equivalence` are semantic relation families

## Relationship To Other Docs

- [scientific-knowledge.md](scientific-knowledge.md) defines the knowledge items these relations connect.
- [gaia-reasoning-model.md](gaia-reasoning-model.md) defines how Gaia interprets the major reasoning families.
- [../contracts/authoring/graph-ir.md](../contracts/authoring/graph-ir.md) will define structural lowering and contract details.

## Out Of Scope

This document does not define:

- the broader philosophy of scientific reasoning
- authored syntax details
- Graph IR field layout
- BP runtime equations

## Migration Note

This document supersedes the earlier tendency to discuss relation semantics only indirectly through factor types or runtime BP notes. In the new structure, relation semantics are a first-class semantic topic.
