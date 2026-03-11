# V3 Probabilistic Semantics

## Purpose

This document defines the probabilistic layer of Gaia's knowledge system.

It builds on:

- [domain-model.md](../domain-model.md) — shared vocabulary
- [knowledge-package-static.md](knowledge-package-static.md) — V1 deterministic FP core (knowledge objects, inferences, chains, modules, packages)

It covers:

1. Gaia's positioning as a probabilistic functional programming language
2. the probabilistic primitives: prior, belief, dependency strength
3. the inference algorithm: loopy belief propagation on hypergraphs
4. the relationship to existing probabilistic programming languages

It does not cover:

- specific BP implementation details (convergence, damping, scheduling)
- GPU/distributed BP scaling
- server-side inference pipeline

Those belong to implementation-level documents.

## Gaia as a Probabilistic Functional Programming Language

### Core thesis: Curry-Howard for plausible reasoning

Functional programming is grounded in mathematical logic via the **Curry-Howard correspondence**: propositions are types, proofs are programs, and type checking verifies that a proof is valid. This gives FP languages like Haskell and Lean their power — they are programming languages where writing a program is constructing a deductive proof.

Gaia extends this from **deductive reasoning** (certainty) to **plausible reasoning** (degrees of belief):

```text
Mathematical logic  ──(Curry-Howard)──→  FP (Haskell, Lean)
        │
        │  Pólya / Jaynes / Cox
        ↓
Plausible reasoning ──(Gaia)──→  Probabilistic FP for knowledge
```

The intellectual foundation comes from three key results:

- **Pólya** (*Mathematics and Plausible Reasoning*, 1954) — mathematical reasoning extends beyond deductive proof to plausible inference: "this is likely true given the evidence"
- **Jaynes** (*Probability Theory: The Logic of Science*, 2003) — probability theory is not about frequencies or random experiments, but about **the logic of plausible reasoning** — a generalization of deductive logic to degrees of belief
- **Cox's theorem** — any system of plausible reasoning that satisfies basic consistency axioms is isomorphic to probability theory

Gaia's design follows directly from this:

| Deductive logic (FP) | Plausible reasoning (Gaia) |
|-----------------------|---------------------------|
| Proposition (true / false) | Knowledge (belief ∈ [0, 1]) |
| Axiom (assumed true) | Knowledge with prior = 1.0 |
| Theorem (proven) | Exported claim with high belief after BP |
| Deductive proof | Chain (plausible inference) |
| Logical entailment A ⊢ B | Strong dependency (A supports B with probability p) |
| Modus ponens | Forward BP message |
| Type checking (is the proof valid?) | BP convergence (are beliefs self-consistent?) |
| Proof irrelevance | Weak dependency (contextual, does not affect truth) |

This also clarifies how Gaia differs from **statistical** probabilistic programming:

| | Deductive (FP) | Plausible (Gaia) | Statistical (Pyro/Stan) |
|-|---------------|-----------------|----------------------|
| **Objects** | Propositions | Knowledge objects | Random variables |
| **Probability means** | — (only true/false) | Degree of belief (epistemic) | Frequency / measure |
| **Inference** | Type checking | Belief propagation | MCMC / variational inference |
| **Goal** | Is the proof valid? | Are beliefs self-consistent? | What is the posterior distribution? |
| **Theoretical basis** | Constructive logic | Cox's theorem | Kolmogorov measure theory |

Gaia is not a statistical tool. It is **Curry-Howard for plausible reasoning**: a programming language where writing a knowledge package is constructing a plausible argument, and running BP is computing how much you should believe the conclusions given the premises.

### The two-layer architecture

Gaia follows the standard architecture of probabilistic programming languages: a **deterministic host language** with a **probabilistic layer** on top.

| Layer | What it defines | PL analogy |
|-------|----------------|------------|
| **V1 — Deterministic FP core** | knowledge objects (values), inferences (lambdas), chains (composition), modules (with imports/exports), packages | Haskell, OCaml |
| **V3 — Probabilistic layer** | priors, dependency strength (conditioning), belief propagation (inference algorithm) | Church's `observe`/`query`, Hakaru's `measure` monad, Pyro's `sample`/`observe` |

Together they form a complete system where:

- **writing a knowledge package** = writing a probabilistic program (a generative model of reasoning)
- **running belief propagation** = performing posterior inference (computing beliefs given evidence and dependencies)

### Comparison with probabilistic programming languages

| Aspect | Church | Hakaru | Pyro | Gaia |
|--------|--------|--------|------|------|
| **Host language** | Scheme (FP) | Haskell (FP) | Python + PyTorch | Knowledge/Inference FP (V1) |
| **Values** | S-expressions | Haskell values | Tensors | Knowledge objects |
| **Probabilistic primitive** | `flip`, `observe` | `measure` monad | `sample`, `observe` | Prior, dependency strength |
| **Conditioning** | `observe` on data | Disintegration | `obs=` in `sample` | `strong` / `weak` imports |
| **Inference algorithm** | MCMC (MH) | Exact / MCMC | SVI, MCMC, NUTS | Loopy BP on hypergraphs |
| **Program** | Generative model | Probabilistic program | Model + guide | Knowledge package |
| **Prior** | Prior distribution | Prior measure | Prior over parameters | Prior on knowledge truth value |
| **Posterior** | Posterior distribution | Posterior measure | Learned parameters | Belief scores after BP |

### Why not use an existing probabilistic PL?

Gaia's probability is **epistemic** (belief in truth of propositions), not **statistical** (distribution over random variables). This creates fundamental mismatches with existing probabilistic PLs:

| Dimension | Statistical probability (Hakaru, Pyro, Stan) | Epistemic probability (Gaia) |
|-----------|---------------------------------------------|------|
| **What has probability** | Random variables (numerical) | Propositions (knowledge objects) |
| **Probability means** | Frequency / measure over outcomes | Degree of belief in truth |
| **Conditioning on** | Observed data | Dependency strength (strong/weak) |
| **Graph model** | DAG (Bayesian network) or factor graph | Hypergraph (multi-premise → conclusion) |
| **Inference computes** | Posterior distribution | Belief scores on propositions |
| **Inference algorithm** | MCMC, variational inference, exact | Loopy BP with damped message passing |

Additionally:

- **Hakaru** is Haskell-based (Gaia is Python), and essentially unmaintained
- **Pyro/Stan** are designed for statistical modeling with continuous distributions; Gaia needs discrete belief propagation on hypergraphs
- **Church/WebPPL** are closest in spirit (conditioning on logical propositions) but use MCMC sampling, not message passing on factor graphs

Gaia is therefore a **new probabilistic FP language** in the same family, but specialized for epistemic inference over structured knowledge.

### What Gaia learns from probabilistic PLs

**From Church: conditioning as a first-class operation.** Church's `observe` lets you condition a generative model on evidence. Gaia's `strong` dependencies play the same role — they condition the belief in a conclusion on the truth of its premises. The semantic parallel is: `strong import` ≈ `observe` (this premise must be true for the conclusion to hold).

**From Hakaru: clean separation of deterministic and probabilistic layers.** Hakaru builds probabilistic semantics on top of Haskell's pure type system via the `measure` monad. Gaia follows the same architecture: V1 defines a pure deterministic FP core, V3 adds probabilistic semantics on top. This separation keeps the deterministic layer clean and testable independently of the inference algorithm.

**From Pyro: model/guide separation.** Pyro separates the generative model (what you believe) from the guide (how you do inference). Gaia has a similar separation: the knowledge package (model) is independent of the BP algorithm (inference). Different BP strategies (damping, scheduling, GPU vs local) can be applied to the same package.

## Probabilistic Primitives

### Prior

Each knowledge object has an optional `prior` — a scalar in [0, 1] representing the initial degree of belief in the knowledge's truth, before any evidence from the dependency graph is considered.

- For `claim` knowledge, the prior represents initial confidence
- For `question` knowledge, the prior is typically omitted (questions are not truth-apt)
- For `setting` knowledge, the prior represents confidence in the setting's validity
- For `action` knowledge, the prior represents confidence in the action's reliability

When omitted, the prior defaults to a system-level default (typically 1.0 — no initial doubt).

### Belief

After belief propagation, each knowledge object carries a `belief` score in [0, 1] — the posterior degree of belief given all evidence in the dependency graph.

The belief update rule:

```
belief(knowledge) = f(prior(knowledge), messages from connected hyperedges)
```

where `f` is the BP message-passing function.

### Dependency strength as conditioning

Module-level `imports` declare dependency strength:

- **strong** — if the imported knowledge is wrong, this module's conclusions are likely wrong too. Strong dependencies create **hyperedges** in the factor graph. They participate in BP message passing.
- **weak** — the imported knowledge is relevant context, but this module's conclusions can stand on their own. Weak dependencies are folded into the knowledge's **prior** rather than creating BP edges.

This is Gaia's analog of `observe` in probabilistic PLs: strong dependencies condition the conclusion's belief on the premises' beliefs.

### Hyperedge probability

Each hyperedge (derived from a module's strong dependencies) carries a `probability` — the conditional probability that the conclusion is true given all premises are true.

```
P(conclusion | all premises true) = hyperedge.probability
```

This is the "factor" in the factor graph.

## Inference: Belief Propagation

### Factor graph construction

The BP factor graph is derived from the package structure:

1. **Variable nodes**: one per knowledge object that participates in any strong dependency
2. **Factor nodes**: one per module that has strong imports — the factor connects the imported knowledge objects (tail) to the exported knowledge objects (head)
3. **Factor function**: parameterized by the hyperedge probability

### Message passing

Loopy BP proceeds by iterating:

1. **Forward messages** (tail → head): beliefs from premise knowledge objects flow through factors to conclusion knowledge objects
2. **Backward messages** (head → tail): beliefs from conclusion knowledge objects flow back to premise knowledge objects
3. **Damping**: messages are damped to improve convergence on loopy graphs
4. **Convergence**: iterate until belief changes fall below a threshold, or a maximum iteration count is reached

### Relationship to the FP model

In the FP view, BP is a **fixed-point computation** on the belief function:

```
beliefs = fix (λbeliefs. propagate(graph, priors, beliefs))
```

where `propagate` applies one round of message passing. This is analogous to finding the fixed point of a recursive function — the beliefs stabilize when the messages are self-consistent.

## Graded Type Theory Perspective

V1's dependency strength (strong/weak) is a binary distinction. A richer model would assign continuous weights to dependencies — this is a form of **graded type theory** where the "type" of a dependency carries a continuous weight rather than a binary classification.

In graded type theory terms:

- Each import has a **grade** (currently: strong=1, weak=0; future: continuous in [0,1])
- The grade determines how much the import participates in belief propagation
- A grade of 0 means the dependency is purely contextual (no BP edge)
- A grade of 1 means the dependency is fully load-bearing (full BP participation)

This provides a smooth spectrum between "hard logical dependency" and "soft contextual relevance."

## Edge Types and Probabilistic Semantics

### Support (default)

Standard reasoning: premises support the conclusion.

```
strong premises → conclusion (probability p)
```

BP forward message: `belief(conclusion) ↑` as `belief(premises) ↑`

### Contradiction

Two knowledge objects conflict. The factor connects conflicting premises to a contradiction conclusion.

```
[A, B] → C  where A and B conflict
```

BP: confirming the contradiction (C's belief increases) while inhibiting the conflicting premises (A and B's beliefs decrease).

### Retraction

Evidence against a previously held claim.

```
[evidence] → [claim]  with inverted forward message
```

BP: as the evidence strengthens, the claim's belief decreases.

## Deferred Topics

The following are intentionally deferred:

- specific BP convergence guarantees and damping strategies
- GPU/distributed BP implementation
- continuous grading of dependency strength (graded type theory)
- interaction between BP and review (how review scores feed into priors)
- cross-package BP (propagation across package boundaries in the global graph)

Those belong to implementation-level documents or later design phases.

## Relationship to Other Documents

- [knowledge-package-static.md](knowledge-package-static.md) defines the V1 deterministic FP core that this document builds on
- [knowledge-package-file-formats.md](knowledge-package-file-formats.md) defines how priors and beliefs are serialized
- V2 (graph integration) defines how packages map to the global graph on which BP operates
- Implementation details of the BP engine live in `services/inference_engine/`
