# Scientific Knowledge

| Field | Value |
|---|---|
| Status | Current canonical |
| Level | Foundation |
| Scope | Repo-wide |
| Related | [../foundation/gaia-overview.md](../foundation/gaia-overview.md), [../meaning/vocabulary.md](../meaning/vocabulary.md), [knowledge-relations.md](knowledge-relations.md), [../domain-model.md](../domain-model.md) |

## Purpose

This document defines what counts as scientific knowledge in Gaia's semantic model.

Its job is to define the main knowledge-bearing object kinds before later docs define authored syntax, relation structure, or runtime inference behavior.

## Core Principle

Gaia is centered on claims that can carry belief, support, contradiction, and revision.

That means Gaia must distinguish between:

- objects that are truth-apt and can directly participate in belief-oriented reasoning
- objects that are useful for authoring, packaging, or investigation but are not themselves direct belief-bearing scientific claims

## Two Broad Kinds Of Objects

### 1. Scientific knowledge objects

These are the objects this document is primarily about.

They describe the content of scientific knowledge itself.

### 2. Neighboring package objects

Gaia packages may also contain nearby objects such as:

- `question`
- `action`
- other workflow-oriented artifacts

These are important to package workflows, but they are not the core scientific knowledge types defined here.

## Knowledge Type Table

| Type | Truth-apt | Direct BP participant | Role |
|---|---:|---:|---|
| `Template` | No | No | Open parameterized pattern |
| `Claim` | Yes | Yes | General closed scientific statement |
| `Observation` | Yes | Yes | Observational report |
| `Measurement` | Yes | Yes | Quantified observation |
| `Hypothesis` | Yes | Yes | Explanatory candidate |
| `Prediction` | Yes | Yes | Expected future or implied result |
| `LawClaim` | Yes | Yes | General law-like closed statement |
| `RegimeAssumption` | Yes | Yes | Applicability or idealization condition |
| `AbstractClaim` | Yes | Yes | Weaker claim extracted from members |
| `GeneralizationCandidate` | Yes | Usually yes, but provisional | Broader candidate induced from examples |

## Template

A `Template` is an open, parameterized pattern such as a predicate schema or statement form.

Examples:

- "`material X becomes superconducting below temperature T`"
- "`body x falls with acceleration a under regime r`"

Important boundary:

- a template is not yet a fully closed scientific claim
- it does not directly enter BP as a normal belief-bearing proposition
- it becomes reasoning-ready only after closure, instantiation, or explicit law formation

## Claim

A `Claim` is the central truth-apt object in Gaia.

A claim is a closed scientific statement that can in principle carry:

- prior or initial plausibility
- support from other claims
- contradiction or equivalence relations
- review, rebuttal, and revision

The default semantic picture for Gaia is: if an object can directly participate in the main belief layer, it should usually be modeled as some form of claim.

## Observation

An `Observation` is a claim whose primary force comes from observed or reported phenomena.

Examples:

- a telescope observation
- an experimental observation
- a reported qualitative effect

Observations are still claims. They are not exempt from review or uncertainty. Their special feature is provenance, not magical certainty.

## Measurement

A `Measurement` is an observation with explicit quantitative content.

Measurements typically carry or imply:

- a measured quantity
- a unit or scale
- an experimental or computational procedure
- uncertainty or error context

Measurements remain claims in the truth-apt sense, but they are often more structured than ordinary narrative observations.

## Hypothesis

A `Hypothesis` is a claim proposed as a possible explanation, mechanism, or organizing statement.

Its key feature is epistemic posture: it is a candidate explanation rather than an already-settled law or directly reported observation.

## Prediction

A `Prediction` is a claim about what should be observed or derived if some other claims, models, or laws hold.

Predictions matter because they connect abstract theory to testable consequences.

## LawClaim

A `LawClaim` is a closed law-like statement with broader scope than an individual observation.

It may involve:

- explicit quantification
- an explicit domain of applicability
- an explicit regime or idealization boundary

Important boundary:

- law-like meaning does not imply certainty
- a law claim is still a revisable scientific claim, not a theorem schema outside empirical challenge

## RegimeAssumption

A `RegimeAssumption` is a claim that fixes the conditions under which another claim or inference should be read.

Examples:

- non-relativistic regime
- vacuum approximation
- negligible air resistance

These assumptions are crucial in science because many law-like claims only hold under restricted conditions. Gaia treats them as first-class claims rather than hiding them in prose.

## AbstractClaim

An `AbstractClaim` is a weaker claim extracted from a set of more specific claims.

Its defining property is:

- each member claim entails the abstract claim

This makes abstraction information-losing but truth-preserving.

## GeneralizationCandidate

A `GeneralizationCandidate` is a broader claim proposed from a finite set of examples or results.

Its defining property is the opposite of abstraction:

- it generally says more than any individual supporting example
- therefore it is not automatically truth-preserving

This is why generalization belongs to the inductive side of Gaia rather than the entailment side.

## What Directly Participates In The Main Belief Layer

The main belief layer should operate on closed, truth-apt claims:

- `Claim`
- `Observation`
- `Measurement`
- `Hypothesis`
- `Prediction`
- `LawClaim`
- `RegimeAssumption`
- `AbstractClaim`
- selected `GeneralizationCandidate` objects when they are being tracked as explicit candidates

`Template` does not directly participate in that layer.

## Relationship To Other Docs

- [knowledge-relations.md](knowledge-relations.md) defines how these knowledge types relate to each other.
- [gaia-reasoning-model.md](gaia-reasoning-model.md) defines how Gaia reasons over them.
- [../contracts/authoring/gaia-language-spec.md](../contracts/authoring/gaia-language-spec.md) will define how authors express them.

## Out Of Scope

This document does not define:

- relation semantics between knowledge items
- authored package syntax
- Graph IR lowering
- BP runtime formulas

## Migration Note

This document supersedes the old idea that Gaia's foundational objects could be adequately captured by the smaller `claim / question / setting / action` vocabulary in [../domain-model.md](../domain-model.md). That older vocabulary remains useful for some package and workflow discussions, but it is too coarse to serve as Gaia's scientific knowledge ontology.
