# Gaia Language Design Rationale

> **Related documents:** For the underlying Jaynes/probability foundations, see [../theoretical-foundation.md](../theoretical-foundation.md). For BP algorithm details, see [../inference-theory.md](../inference-theory.md).
>
> This document derives Gaia's CLI architecture from the Lean proof assistant analogy. It covers the tactic model, BeliefState, proof search, and command semantics.

## Purpose

This document captures Gaia's theoretical identity — what kind of formal system Gaia is, how it relates to existing paradigms, and what architectural principles follow from that identity.

The core finding: Gaia is not a programming language, not a database query language, and not a probabilistic programming language in the Stan/Pyro sense. It is a **proof assistant for probabilistic defeasible reasoning** — a system that borrows Lean's architecture, Bayesian networks' semantics, and belief revision's knowledge model.

## The Lean Analogy

### Core Mapping

| Concept | Lean | Gaia |
|---------|------|------|
| Core object | Proposition | Claim |
| Assumed truth | Axiom | Claim with high prior |
| Derived truth | Theorem | Claim whose belief is computed via BP |
| Derivation structure | Proof term | ChainExpr |
| Construction strategy | Tactic | InferAction / Lambda |
| Verification | Kernel type-check | BP + Review |
| Verified artifact | .olean export | Published package |
| Proof state | Goals (metavariables) | BeliefState (open claims) |

The critical difference: Lean is binary (proof valid or invalid), Gaia is probabilistic (belief is a continuous value in [0, 1]).

### InferAction is a Tactic, Not a Function Call

This distinction is architecturally fundamental.

**Function call mental model** (wrong for Gaia):
- The LLM is the authority. Its output is the answer.
- The reasoning quality depends entirely on LLM text quality.
- Formal structure (chains, priors) is just a "calling framework."

**Tactic mental model** (correct for Gaia):
- The LLM helps **construct** reasoning content, but does not determine its credibility.
- The formal system (BP) independently computes beliefs based on structure, priors, and edge probabilities.
- The LLM can generate brilliant reasoning or complete nonsense — BP computes the same belief either way, because BP reads structure, not text.

A buggy tactic in Lean cannot corrupt a verified proof. A hallucinating LLM in Gaia cannot corrupt the probabilistic judgment — as long as the formal structure is sound.

### Two Kernels

In Lean, the kernel checks both the **structure** and the **content** of a proof term.

In Gaia, BP only checks **structure** — graph topology, priors, edge probabilities. It does not read the text content of claims. BP alone is only **half a kernel**:

| Component | What it checks | Lean analogy |
|-----------|---------------|--------------|
| **BP** | Graph structure, probability consistency | Structural type-check |
| **Review** | Reasoning text quality, logical validity | Semantic type-check |
| **BP + Review** | **Complete verification** | **Full kernel** |

Architectural consequence: `review` is not an optional product feature. It is the content-checking half of Gaia's kernel.

## How Tactics Work: The Metavariable Model

Understanding Lean's tactic implementation illuminates Gaia's design space.

### Lean's Mechanism

A tactic operates on **proof state** — a set of "holes" (metavariables), each with a type (the proposition to prove) and a local context (available hypotheses).

```
ProofState = {
  goals: [
    { type: P,   context: [h1: A, h2: B] },
    { type: Q,   context: [h1: A, h2: B] },
  ]
}
```

Each tactic **fills holes**: it replaces a metavariable with an expression that may contain new metavariables (new subgoals).

```
initial:     ?m : P ∧ Q                    -- one hole

constructor: ?m := And.mk ?m₁ ?m₂          -- fill hole, introduce two new holes
             goals: [?m₁ : P, ?m₂ : Q]

exact hp:    ?m₁ := hp                      -- fill hole
             goals: [?m₂ : Q]

exact hq:    ?m₂ := hq                      -- fill hole
             goals: []                      -- done: proof complete
```

The kernel then type-checks the completed proof term (`And.mk hp hq : P ∧ Q`) independently of how the tactics constructed it.

### Key Property: Construction/Verification Separation

Tactics can use any strategy to fill holes — pattern matching, heuristic search, database lookup, even calling an external AI. The kernel doesn't care how the term was built; it only checks the final result.

This is the property Gaia inherits: InferAction (the tactic) can use any LLM with any prompt strategy. BP (the kernel) independently evaluates the resulting structure.

## Proof Search as Tree Search

The process of finding the right tactic sequence is itself a search problem:

```
          ⊢ P ∧ Q → Q ∧ P           -- root: initial goal
         /        |        \
     intro      apply?     simp?     -- candidate tactics
       |          ✗          ✗
   h ⊢ Q ∧ P
    /      \
constructor  cases h                  -- candidate tactics
   |           ...
 ⊢ Q, ⊢ P                           -- two subgoals
  |      |
h.2    h.1
  ✓      ✓                           -- proof found
```

AI proof systems model this as tree search:

| System | Search Algorithm | Evaluation |
|--------|-----------------|------------|
| AlphaProof | MCTS + neural network | Win rate estimation |
| GPT-f | Beam search + LLM | LLM probability |
| Lean's `aesop` | Best-first search | Hand-written priority |

The crucial property: **search quality affects efficiency, never correctness.** A bad search finds proofs slowly (or not at all). But any proof found is independently verified by the kernel.

### Gaia's Search Space

Gaia's reasoning process maps to the same tree search model:

```
Lean proof search:
  State  = remaining goals (metavariables)
  Action = tactic application (fill a hole)
  Eval   = kernel type-check (binary: valid/invalid)

Gaia reasoning search:
  State  = BeliefState (open claims + current beliefs)
  Action = InferAction / ChainExpr (construct reasoning)
  Eval   = BP + Review (continuous: belief ∈ [0,1])
```

Lean searches a discrete space for deterministic proofs. Gaia searches a continuous space for probabilistic beliefs. Search strategy (LLM reasoning quality) affects efficiency and coverage, but not BP's mathematical correctness.

## BeliefState: Gaia's Proof State

### Definition

Gaia's equivalent of Lean's ProofState:

```
BeliefState = {
  -- Claims without reasoning support (analogous to Lean goals)
  open_claims: [
    { claim: C, prior: float, belief: ?, support: [] }
  ],

  -- Claims with reasoning chains (analogous to proved subgoals)
  grounded_claims: [
    { claim: C, prior: float, belief: float, support: [chains] }
  ],

  -- Current factor graph structure
  graph: FactorGraph,

  -- Available knowledge (analogous to Lean's local context)
  context: [settings, refs, external_claims]
}
```

### Tactic Correspondence

| Lean Tactic | Gaia Operation | Effect |
|---|---|---|
| `intro h` | `add_premise(claim)` | Add available evidence to context |
| `apply f` | `begin_chain(action, args)` | Connect premises to conclusion, may create new open claims |
| `exact h` | `ground(claim, chain)` | Fully support a claim with existing evidence |
| `constructor` | `decompose(claim)` | Split a compound claim into sub-claims |
| `simp` | `infer(claim)` | Let LLM automatically construct a reasoning chain |
| `sorry` | Keep prior unchanged | Acknowledge no reasoning support; use prior as-is |

### Termination: The Key Difference

```
Lean:   goals = []       → proof complete (binary: done or not done)
        any open goal    → proof fails

Gaia:   open_claims = [] → graph complete, BP computes final beliefs
        open_claims ≠ [] → graph incomplete, BP STILL computes (with wider uncertainty)
```

Lean requires proof completeness. Gaia allows incompleteness — partial evidence yields partial belief. This is the probabilistic nature: half a proof is zero proof; half the evidence is half the confidence.

### Concrete Example: Galileo Package

```
Initial BeliefState:
  open_claims: [
    aristotle_contradicted (prior=0.5),
    air_resistance_is_confound (prior=0.5),
    vacuum_prediction (prior=0.5),
  ]
  grounded: [
    heavier_falls_faster (prior=0.7),
    everyday_observation (prior=0.95),
  ]
  context: [thought_experiment_env, vacuum_env]

Tactic 1: apply refutation_chain
  → aristotle_contradicted grounded (belief=0.63)
  → 2 open claims remaining

Tactic 2: apply confound_chain
  → air_resistance_is_confound grounded (belief=0.85)
  → 1 open claim remaining

Tactic 3: apply synthesis_chain
  → vacuum_prediction grounded (belief=0.72)
  → 0 open claims → BP converges on complete graph
```

### What BeliefState Enables

1. **Progress observability**: `3/5 claims grounded, overall confidence 0.68`
2. **Search guidance**: `most_impactful_open_claim() → vacuum_prediction`
3. **Interactive reasoning**: `gaia state` / `gaia apply chain_name`
4. **Checkpoint and backtrack**: save state, try a reasoning chain, roll back if belief drops

## Why Gaia is Not "Probabilistic Lean"

The analogy is architecturally productive but semantically misleading. Three reasons:

### 1. Lean's Type Theory is Too Heavy

Lean's kernel implements the Calculus of Inductive Constructions (CIC) — dependent types, universe polymorphism, inductive types. Decades of type theory research.

Gaia's type system: Claim, Setting, Question, Action, ChainExpr. That's it.

Using a probabilistic CIC extension for Gaia would be like using aerospace alloys for a kitchen knife — theoretically possible, practically a disaster.

### 2. Knowledge is Defeasible, Proofs are Not

```
Lean:  Once P is proved, P is true forever.
       Monotonic: new theorems never invalidate old ones.

Gaia:  belief(P) = 0.9 today, may become 0.3 tomorrow.
       Retraction and contradiction are first-class.
       Non-monotonic: new evidence can weaken old conclusions.
```

A "probabilistic Lean" would still be monotonic. Gaia must support belief revision — the ability to reduce confidence in previously established claims.

### 3. Verification Has Different Properties

```
Lean kernel:  Decidable. Type-check always terminates. Returns yes/no.
Gaia BP:      Iterative. May not converge. Returns continuous values in [0,1].
```

This is not simply "replacing bool with float." The entire metatheory is different.

## Gaia's True Identity

Gaia is the intersection of three traditions:

```
         Lean
      (architecture)
          / \
         /   \
        / Gaia \
       /________\
      /          \
  Probabilistic    Non-monotonic
  Graphical Models   Logic
    (semantics)    (knowledge model)
```

| Source | What Gaia Takes |
|---|---|
| **Lean** | Architecture: proof state, tactic framework, construction/verification separation, interactive mode, export format |
| **Probabilistic Graphical Models** (Factor Graphs, BP) | Semantics: continuous beliefs, message passing, approximate inference |
| **Non-monotonic Logic** (AGM, Belief Revision) | Knowledge model: retraction, contradiction, defeasible reasoning |

### The Unnamed Formal System

Gaia's kernel needs a formal system with these properties:

1. Propositions have continuous truth values (belief in [0,1]) — from probability theory
2. Reasoning can be retracted — from non-monotonic logic
3. Contradiction does not cause explosion (paraconsistent) — from paraconsistent logic
4. Structure is verifiable, content requires audit — from Lean's kernel model
5. Beliefs converge via message passing — from probabilistic graphical models

The closest existing system is **Markov Logic Networks** (MLN) — first-order logic unified with probabilistic graphical models. But MLN lacks the tactic architecture and has no notion of belief revision.

Gaia's formal foundation is, as far as we know, a novel combination.

## Implications for Command Semantics

The Lean analogy clarifies why `run` is the wrong top-level verb for Gaia:

- Nobody says "run a proof." They say "**check** a proof" or "**build** a project."
- `lake build` in Lean means: parse, elaborate, type-check, export.
- Similarly, `gaia build` should mean: load, resolve, ground, compile factor graph, run BP.

| Stage | Lean equivalent | What happens |
|-------|----------------|-------------|
| Load + Resolve | Parse + Elaborate | Source to AST, name resolution |
| Execute (LLM) | Tactic execution | Construct reasoning content (untrusted) |
| Compile factor graph | Lower to kernel IR | Translate reasoning structure to verifiable form |
| BP | Kernel type-check (structural) | Compute beliefs from formal structure |
| Review | Kernel type-check (semantic) | Assess content quality and logical validity |
| Publish | Export .olean | Share the verified artifact |

## Implications for Prior and Probability Annotations

The `prior` and `probability` values written by hand in YAML are analogous to **type annotations** in Lean. In Lean, the elaborator can often infer types automatically; the user provides annotations only when needed.

In Gaia, `review` could eventually serve a similar role — estimating or adjusting edge probabilities based on content quality assessment, rather than requiring the author to manually assign all probabilities.

## Summary

Gaia is a **proof assistant for probabilistic defeasible reasoning**. It takes:

- **Lean's architecture**: BeliefState, tactic-based construction, kernel-based verification, interactive mode
- **Bayesian semantics**: continuous beliefs, factor graphs, message passing
- **Belief revision**: retraction, contradiction, non-monotonic knowledge updates

It is not a probabilistic extension of Lean (too heavy, wrong semantics). It is not a traditional probabilistic programming language (not about sampling). It is a new kind of formal system — one designed for the specific problem of computing how much to believe propositions given structured evidence and defeasible reasoning.
