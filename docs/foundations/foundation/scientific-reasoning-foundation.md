# Scientific Reasoning Foundation

| Field | Value |
|---|---|
| Status | Current canonical |
| Level | Foundation |
| Scope | Repo-wide |
| Related | [gaia-overview.md](gaia-overview.md), [../semantics/gaia-reasoning-model.md](../semantics/gaia-reasoning-model.md), [../theory/theoretical-foundation.md](../theory/theoretical-foundation.md), [../product-scope.md](../product-scope.md) |

## Purpose

This document defines the high-level theoretical foundation behind Gaia's treatment of scientific reasoning.

It answers the question: why does a system for scientific knowledge need a foundation broader than pure mathematical logic?

## The Core Claim

Scientific reasoning is not exhausted by deductive validity.

It also involves:

- uncertain evidence
- incomplete information
- measurement and provenance
- applicability conditions and idealizations
- revision in the face of new evidence
- explanatory and inductive moves that are not pure entailment

Gaia exists because these features must be represented explicitly if scientific knowledge is to become machine-writable, machine-reviewable, and machine-reasonable.

## Why Mathematical Logic Alone Is Not Enough

Mathematical logic is indispensable for precision, consistency, and truth-preserving implication. But science has additional burdens that ordinary proof systems do not solve by themselves.

### Science Is World-Facing

Scientific claims are not only about formal consequences inside an abstract calculus. They are about a world accessed through:

- observation
- measurement
- experiment
- instrumentation
- simulation
- modeling assumptions

This means scientific reasoning must account for how claims are supported by evidence, not only whether they follow from axioms.

### Science Is Uncertain

Most scientific claims are not known with theorem-level certainty.

Even strong claims are typically conditioned on:

- finite evidence
- imperfect instruments
- modeling approximations
- incomplete background knowledge

So a scientific reasoning system needs more than `true` and `false`. It needs a principled way to represent degrees of plausibility.

### Science Is Regime-Bound

Many scientific claims are true only under stated or implicit conditions.

Examples include:

- idealizations
- limiting assumptions
- domain restrictions
- background setup conditions

That is why Gaia treats regime and applicability assumptions as first-class rather than burying them in prose.

### Science Is Revisable

New evidence may weaken, qualify, or overturn earlier conclusions.

So the system must support:

- contradiction without logical explosion
- rebuttal and review
- changes in belief under new information

## Jaynes, Cox, And Pólya

Gaia's foundation is closest to the tradition of plausible reasoning associated with Pólya, Cox, and Jaynes.

### Pólya

Pólya is important because he treats plausible reasoning as a legitimate object of formal study rather than as an embarrassment outside strict proof.

This matters for Gaia because scientific work contains:

- heuristic support
- analogy
- inductive movement
- explanatory preference

These are not reducible to classical proof, but they are still structured reasoning.

### Cox

Cox matters because his theorem motivates the idea that any consistent calculus of plausibility should line up with probability theory.

For Gaia, this justifies the decision that belief and update should not be arbitrary scores. They should live in a probability-shaped discipline.

### Jaynes

Jaynes is the closest direct ancestor of Gaia's reasoning stance.

The crucial ideas are:

- probability is the logic of plausible reasoning
- every probability is conditional on information
- contradictions and revisions should be handled by updating beliefs, not by collapsing the whole system
- reasoning can be delegated to a disciplined "robot" that obeys consistency rules even when humans and LLMs provide the content

Gaia does not claim to be a full theorem derived from Jaynes. But Jaynes provides the clearest foundation for why Gaia should be a structured plausible-reasoning system rather than a binary proof checker.

## What This Means For Gaia

Several design consequences follow from this foundation.

### Closed claims are central

The main reasoning layer should operate over closed, truth-apt scientific claims, not over arbitrary textual fragments.

### Relations must be typed

Science uses different kinds of support and incompatibility. So Gaia must distinguish, at minimum:

- support relations
- truth-preserving implication
- contradiction
- equivalence

### Review and rebuttal are not optional decorations

Because scientific knowledge is revisable, review, rebuttal, and integration are part of the knowledge system itself, not merely project-management workflow.

### Contradiction is informative

In a plausible-reasoning system, contradiction is not an explosion trigger. It is evidence that some beliefs, assumptions, or relations need to be revised.

### Runtime inference is downstream of a broader epistemic stance

Belief propagation is not the foundation by itself. It is one runtime realization of a broader commitment: scientific knowledge should support disciplined belief update under uncertainty.

## Relationship To Other Docs

- [gaia-overview.md](gaia-overview.md) explains what Gaia is at the highest level.
- [../semantics/scientific-knowledge.md](../semantics/scientific-knowledge.md) defines the knowledge objects Gaia reasons about.
- [../semantics/knowledge-relations.md](../semantics/knowledge-relations.md) defines the semantic relation families between those objects.
- [../semantics/gaia-reasoning-model.md](../semantics/gaia-reasoning-model.md) defines Gaia's own reasoning model built on top of this foundation.

## Out Of Scope

This document does not define:

- Gaia-specific object taxonomy details
- authored language syntax
- Graph IR structure
- current BP runtime equations

## Migration Note

This document now supersedes the highest-level epistemic role previously carried by [../theory/theoretical-foundation.md](../theory/theoretical-foundation.md). That older doc remains useful during migration, especially for deeper historical framing, but this file is now the canonical entry point for the question of why Gaia needs a scientific-reasoning foundation.
