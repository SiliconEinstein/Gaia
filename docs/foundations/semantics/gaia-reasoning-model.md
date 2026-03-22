# Gaia Reasoning Model

| Field | Value |
|---|---|
| Status | Current canonical |
| Level | Foundation |
| Scope | Repo-wide |
| Related | [../foundation/scientific-reasoning-foundation.md](../foundation/scientific-reasoning-foundation.md), [scientific-knowledge.md](scientific-knowledge.md), [knowledge-relations.md](knowledge-relations.md), [../theory/inference-theory.md](../theory/inference-theory.md), [../bp-on-graph-ir.md](../bp-on-graph-ir.md) |

## Purpose

This document defines Gaia's own reasoning model: how Gaia turns broader ideas about scientific reasoning into a concrete semantic scheme for packages, relations, and belief-oriented inference.

It sits below the broader scientific-reasoning foundation and above runtime inference details.

## The Core Idea

Gaia is not trying to encode only deductive proof. It is trying to represent the reasoning patterns that actually occur in scientific work and then map those patterns into a structured, revisable, belief-oriented system.

In Gaia, the main reasoning families are:

- deduction
- induction
- abduction
- abstraction
- instantiation

## Deduction

In Gaia, deduction means support that runs from premise claims toward a conclusion claim in a way that is intended to be strongly truth-directed.

It is usually represented as a form of `reasoning_support`, not as absolute theorem-prover-style certainty.

This matters because many scientific arguments are deductive in shape while still depending on empirical assumptions, modeling choices, and uncertain premises.

## Induction

In Gaia, induction means movement from a finite set of examples, measurements, or case claims toward a broader claim.

Its defining feature is:

- the resulting claim usually says more than any one supporting instance

So induction is not truth-preserving. In Gaia it belongs on the non-entailment side of the reasoning model.

Typical outputs include:

- a broader hypothesis
- a regularity claim
- a `GeneralizationCandidate`

## Abduction

In Gaia, abduction means movement from an observed or reported phenomenon toward a hypothesis that would explain it.

It is not the same as entailment. The fact that a hypothesis would explain an observation does not make the hypothesis guaranteed. It makes the hypothesis more plausible, subject to competing explanations and background assumptions.

Gaia therefore treats abduction as a reasoning mode, not as a special theorem rule.

## Abstraction

In Gaia, abstraction means extracting a weaker common claim from more specific claims.

Its defining feature is:

- the member claims entail the resulting abstract claim

Because of that, abstraction is best treated as a knowledge-construction operation whose persistent semantic result is usually:

- a new `AbstractClaim`
- entailment links from the members to that abstract claim

## Instantiation

Instantiation is the movement from a general law-like or schema-like claim to a concrete case claim.

It is truth-preserving in a way closer to entailment than to induction or abduction, but it is important enough in scientific reasoning to remain separately named.

## Operator Contracts

Gaia does not treat every reasoning family as a completely separate low-level runtime mechanism.

Instead, the system defines semantic operator contracts such as:

- support should raise or lower beliefs in characteristic directions
- truth-preserving links should behave differently from merely supportive links
- contradiction and equivalence should constrain beliefs without being reduced to plain citations

This is where Jaynes-style update patterns matter: not as surface-language keywords, but as constraints on what a valid reasoning operator must do.

## Belief-Oriented Structure

The reasoning model has several structural consequences.

### Only closed, truth-apt claims directly enter the main belief layer

Templates and open patterns do not directly participate as normal BP variables. They must first become closed claims, law claims, or explicit case claims.

### Not every useful activity becomes a core relation

Some activities are semantic core relations:

- reasoning support
- entailment
- instantiation
- contradiction
- equivalence

Some are better treated as higher-level construction or review activities:

- abstraction
- generalization
- independent-evidence audit
- loop audit and basis analysis

### Loopy reasoning is allowed

Gaia does not require the knowledge graph to be globally rewritten into a DAG before inference.

Loops are allowed. When loop structure needs explanation, diagnosis, or conditioning, Gaia may introduce basis views or loop-analysis artifacts. Those are diagnostic tools, not the primary semantic definition of reasoning.

## Relation To Gaia CLI And Gaia LKM

The same reasoning model underlies both sides of the system:

- Gaia CLI uses it for local build and inference previews
- Gaia LKM uses it for shared-side reasoning, review, integration, and maintenance

The difference is not the semantics of reasoning itself. The difference is the scale, workflow, and artifact lifecycle around that reasoning.

## Relationship To Other Docs

- [scientific-knowledge.md](scientific-knowledge.md) defines the knowledge items being reasoned over.
- [knowledge-relations.md](knowledge-relations.md) defines the relation families between those items.
- [../theory/inference-theory.md](../theory/inference-theory.md) contains more detailed operator and factor-theory material during migration.
- [../runtime/inference-runtime.md](../runtime/inference-runtime.md) will describe how the current runtime actually implements these ideas.

## Out Of Scope

This document does not define:

- low-level message-passing equations
- Graph IR field layout
- storage schema
- package workflow rules

## Migration Note

This document now provides the canonical Gaia-specific reasoning layer that was previously spread across [../theory/inference-theory.md](../theory/inference-theory.md) and runtime-centric BP docs. Those older docs remain important during migration, but the semantic model itself should now be read from here first.
