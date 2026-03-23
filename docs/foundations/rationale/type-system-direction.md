# Type System Direction

> **Status:** Current canonical

## Foundational Position: Jaynes + Lean Hybrid

Gaia's type-theoretic identity derives from one observation: Jaynes's plausible reasoning extends deductive logic by generalizing truth values from {0, 1} to [0, 1]. This means the type system's *structure* can follow established formal language design (borrowing from Lean), while the *evaluation semantics* follow Jaynes (BP computes beliefs instead of term reduction producing proofs).

**In one sentence: Lean's structure + Jaynes's semantics.**

## Why Not Curry-Howard

Lean's type system is built on the Curry-Howard correspondence: propositions are types, proofs are terms. This does not apply to Gaia for three reasons:

### 1. Proof irrelevance vs evidence relevance

In Lean, once a proposition has one proof, all proofs are equal (proof irrelevance). In Gaia, different evidence for the same claim has different weight. Multiple pieces of evidence must be aggregated via BP. Evidence is never irrelevant — it is the entire basis for computing belief.

### 2. Binary inhabitation vs continuous belief

In Lean, a proposition is either inhabited (proved) or not. In Gaia, a claim has a degree of belief in [0, 1]. The question is never "is this true?" but "how much should we believe this?"

### 3. Monotonicity vs defeasibility

In Lean, once a theorem is proved, it stays proved forever. New theorems never invalidate old ones. In Gaia, new evidence can weaken old claims. Retraction and contradiction are first-class operations. Belief revision is the norm, not the exception.

### Consequence

Claims are terms, not types. All claims are terms of type `Claim`. Evidence connects to claims via graph edges, not via type inhabitation. BP computes belief on the graph, not via type checking.

## Probability at the Value Layer, Not the Type Layer

If probability were part of the type system (e.g., `Claim(p=0.8)` as a type distinct from `Claim(p=0.7)`), type checking itself becomes probabilistic. This is avoided because:

- Type checking should be decidable and deterministic
- No mature theory exists for probabilistic type checking
- Every successful probabilistic language (Church, Pyro, Stan) keeps probability at the value level
- Jaynes's own framework treats logical structure as deterministic, with probability assigned to propositions within that structure

| Layer | Deterministic? | Responsible for |
|---|---|---|
| Type system | Yes | Structural well-formedness, classification, checking |
| Values (prior, belief) | N/A — they are data | Carrying probability information |
| BP evaluator | Deterministic given a graph | Computing posterior beliefs |

## Closed Claims vs Templates vs Laws

Gaia's type system distinguishes three layers often conflated in informal scientific writing:

| Concept | Lean analogy | Role |
|---|---|---|
| **Template** | `P : a -> Prop` (predicate) | Open proposition schema; not truth-apt |
| **ClosedClaim** | `P(a)` (applied predicate) | Closed, truth-apt assertion; participates in BP |
| **LawClaim** | `forall x, P(x)` (quantified) | Closed general assertion with explicit scope and regime |

Only closed, truth-apt assertions participate in BP. Open templates do not.

## What Gaia Borrows From Lean

1. **Small trusted kernel** — a core with a clear trust boundary handling deterministic structural checks (declaration formation, ref resolution, chain well-formedness, factor-graph compilation validity).

2. **Construction and verification separation** — LLMs and tools construct candidate reasoning structures; the kernel checks structural validity; review checks reasoning quality; BP computes posteriors.

3. **Elaboration** — authors write Typst-based package source; the system elaborates into typed core IR; all kernel checks operate on that IR.

4. **Judgments and rules** — the kernel is defined in terms of formal judgments (e.g., "ref resolves," "chain is well-formed," "factor graph compiles"), not ad hoc validators.

5. **Goal-state thinking (ProofState)** — open claims are analogous to Lean goals; grounded claims are analogous to discharged goals; `InferAction` is analogous to a tactic that fills a hole; local progress is observable as BeliefState.

6. **Module and namespace discipline** — strict rules for name introduction, scope resolution, and export boundaries.

### ProofState and the Goal-State Metaphor

In Lean, a tactic operates on **proof state** -- a set of "holes" (metavariables), each with a type (the proposition to prove) and a local context (available hypotheses):

```
ProofState = {
  goals: [
    { type: P,   context: [h1: A, h2: B] },
    { type: Q,   context: [h1: A, h2: B] },
  ]
}
```

Each tactic fills a hole, possibly introducing new subgoals. When all holes are filled, the proof is complete.

Gaia's equivalent is **BeliefState**: open claims are analogous to Lean goals (holes to be filled); grounded claims are analogous to discharged goals. The key structural difference is termination: Lean requires all goals to be discharged or the proof fails. Gaia allows incompleteness -- open claims yield wider uncertainty, but BP still computes beliefs on the partial graph. Half a proof is zero proof; half the evidence is half the confidence.

### The Tactic Mental Model vs the Function Call Mental Model

This distinction is architecturally fundamental.

In the **function call mental model** (wrong for Gaia), the LLM is the authority -- its output is the answer, and reasoning quality depends entirely on LLM text quality. Formal structure (chains, priors) is just a calling framework.

In the **tactic mental model** (correct for Gaia), the LLM helps *construct* reasoning content but does not determine its credibility. BP independently computes beliefs based on graph structure, priors, and edge probabilities. BP reads structure, not text. A hallucinating LLM cannot corrupt probabilistic judgment, just as a buggy tactic in Lean cannot corrupt a verified proof -- as long as the formal structure is sound.

`InferAction` in Gaia is a tactic, not a function call. It constructs candidate reasoning chains. BP evaluates them independently.

### Two-Kernel Concept: BP Kernel + Review Kernel

In Lean, a single kernel checks both the structure and the content of a proof term. In Gaia, BP only checks **structure** -- graph topology, priors, edge probabilities. It does not read the text content of claims. BP alone is only half a kernel:

| Component | What it checks | Lean analogy |
|-----------|---------------|--------------|
| **BP** | Graph structure, probability consistency | Structural type-check |
| **Review** | Reasoning text quality, logical validity | Semantic type-check |
| **BP + Review** | **Complete verification** | **Full kernel** |

This means `review` is not an optional product feature. It is the content-checking half of Gaia's kernel. Without review, Gaia can verify that a reasoning graph is structurally consistent but cannot assess whether the reasoning text is sound -- analogous to a type checker that verifies syntax but not semantics.

### How Gaia's "Elaboration" Differs from Lean's

Both systems have an elaboration phase, but they serve different purposes:

- **Lean elaboration** fills in implicit arguments, resolves overloaded notation, inserts coercions, and infers types. It transforms terse surface syntax into a fully explicit core term that the kernel can check. Elaboration is a complex, bidirectional process that interleaves with unification and type inference.

- **Gaia elaboration** transforms Typst-based package source into typed core IR (Graph IR). It resolves references, classifies declarations by root type and kind, compiles chains into factor nodes, and produces the structural graph that BP and review will consume. There is no type inference in Lean's sense -- the elaborator's job is to lower authoring-layer narrative structure into a verifiable factor graph.

The shared principle is that authors write in a convenient surface language and the system elaborates into a core representation where all checks operate. The difference is that Lean's elaboration is primarily about types and terms, while Gaia's elaboration is primarily about graph structure and knowledge identity.

## What Gaia Does Not Borrow From Lean

- **Curry-Howard** — claims are terms, not types (see above)
- **Full dependent type theory** — not needed for V1; the problem is validating reasoning structures, not proving value-indexed programs correct
- **Definitional equality and reduction** — Gaia's evaluation is BP on graphs, not term reduction
- **Monotonic proof semantics** — beliefs are revised as new evidence arrives; non-monotonicity is fundamental
- **Aggressive implicit inference** — Gaia's users are agents and reviewers who need legible artifacts; V1 prefers explicitness

## Source

- [../../archive/foundations-v2/language/type-system-direction.md](../../archive/foundations-v2/language/type-system-direction.md)
