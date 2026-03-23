# Gaia Type System Direction

> Related documents:
> - [Gaia Language Spec](gaia-language-spec.md)
> - [Gaia Language Design](gaia-language-design.md)
> - [Language Design Rationale](design-rationale.md)
> - [Theoretical Foundation](../theory/theoretical-foundation.md)
> - [Scientific Ontology](../theory/scientific-ontology.md)

## Purpose

This document defines the design direction for Gaia's type system.

It addresses four questions:

1. What is Gaia's type-theoretic identity — how does it relate to Lean?
2. Which Lean ideas should Gaia borrow, and which should it avoid?
3. What should the V1 type system look like?
4. How should the type system expand after V1?

## Foundational Position: Jaynes' Structure + Lean's Architecture

Gaia is a formal language for plausible reasoning. Its type-theoretic foundation derives from a single observation:

**Jaynes' plausible reasoning extends deductive logic — it preserves the logical structure but generalizes truth values from {0, 1} to [0, 1].**

This means the type system's structure can follow established formal language design (borrowing from Lean), while the evaluation semantics follow Jaynes (BP computes beliefs instead of term reduction producing proofs).

In one sentence: **Lean's structure + Jaynes' semantics.**

## Closed Claims, Templates, and Laws

Gaia's type system should distinguish three layers that are often conflated in informal scientific writing:

- `Template`: open proposition schema or predicate-like pattern
- `ClosedClaim`: closed, truth-apt scientific assertion
- `LawClaim`: closed general assertion with explicit scope, domain, and regime

The Lean analogy is useful here:

- `Template` is analogous to a predicate-like object such as `P : α → Prop`
- a concrete `ClosedClaim` is analogous to `P(a)`
- a `LawClaim` is analogous to a closed quantified proposition such as `∀ x, P(x)`

Only closed, truth-apt assertions directly participate in BP. Open templates do not. This is why Gaia should keep probability at the value layer while also keeping a clear boundary between language surface categories and BP-bearing assertion categories.

## Why Not Curry-Howard

Lean's type system is built on the Curry-Howard correspondence: propositions are types, proofs are terms (inhabitants of those types). This does not apply to Gaia, for three reasons.

### 1. Proof irrelevance vs evidence relevance

In Lean, once a proposition `P` has one proof, all proofs of `P` are equal (proof irrelevance). The proposition is simply "true."

In Gaia, different evidence for the same claim has different weight. Multiple pieces of evidence must be aggregated via BP. Evidence is never irrelevant — it is the entire basis for computing belief.

### 2. Binary inhabitation vs continuous belief

In Lean, a proposition is either inhabited (proved) or not. There is no middle ground.

In Gaia, a claim has a degree of belief in [0, 1]. The question is never "is this true?" but "how much should we believe this?"

### 3. Monotonicity vs defeasibility

In Lean, once a theorem is proved, it stays proved forever. New theorems never invalidate old ones.

In Gaia, new evidence can weaken old claims. Retraction and contradiction are first-class operations. Belief revision is the norm, not the exception.

### Consequence: Claims are terms, not types

In Lean:
```lean
-- "Earth is round" IS a type
def EarthIsRound : Prop := ...
-- A proof is an inhabitant of that type
def proof : EarthIsRound := ...
```

In Gaia:
```typst
#claim(kind: "hypothesis")[
  Earth is round.
] <earth_is_round>
```

All claims are terms of type `Claim`. Evidence connects to claims via graph edges, not via type inhabitation. BP computes belief on the graph, not via type checking.

## Why Probability Stays at the Value Level

If probability were part of the type system (e.g., `Claim(p=0.8)` is a type distinct from `Claim(p=0.7)`), then type checking itself becomes probabilistic — "do these types match?" becomes "to what degree do they match?"

This is avoided because:

- type checking should be decidable and deterministic
- no mature theory exists for probabilistic type checking
- every successful probabilistic language (Church, Pyro, Stan) keeps probability at the value level
- Jaynes' own framework treats logical structure as deterministic, with probability assigned to propositions within that structure

So Gaia's design is:

| Layer | Deterministic? | Responsible for |
|---|---|---|
| Type system | Yes | Structural well-formedness, classification, checking |
| Values (prior, belief) | N/A — they are data | Carrying probability information |
| BP evaluator | Deterministic given a graph | Computing posterior beliefs |

## What Gaia Should Borrow From Lean

### 1. Small trusted kernel

Lean's most important design property is not dependent types. It is the existence of a small trusted core with a clear trust boundary.

Gaia's kernel should handle deterministic structural checks:

- declaration formation
- ref resolution
- action signature checking
- chain well-formedness
- factor-graph compilation validity
- export and module boundary checks

### 2. Construction and verification separation

In Lean, tactics construct candidate proof terms, but the kernel verifies the result independently.

Gaia preserves this:

- LLMs, tools, and search procedures construct candidate reasoning structures
- the kernel checks structural validity
- review checks reasoning quality
- BP computes posterior beliefs on the resulting structure

### 3. Elaboration

Lean distinguishes surface syntax from core terms.

Gaia should do the same:

- authors and agents write Typst-based package source
- the system elaborates into a typed core IR
- all kernel checks operate on that core IR

### 4. Judgments and rules

Lean is defined in terms of judgments and inference rules. Gaia should define its kernel the same way, giving precise answers to:

- what does it mean for a `Ref` to be valid?
- what does it mean for an `Action` signature to be valid?
- what does it mean for a `ChainExpr` to be well-formed?
- what does it mean for a chain to compile into a valid factor graph?

Without judgments, the system remains a collection of ad hoc validators.

### 5. Explicit checking environment

Lean checks terms relative to an environment `Γ`. Gaia also needs this:

- a `Ref` is valid relative to a module/package environment
- an `apply` step is valid relative to the available action signature
- a `chain_expr` is valid relative to the knowledge objects it mentions

### 6. Goal-state thinking

Lean's tactic engine operates on proof state with open goals.

Gaia borrows this for local reasoning:

- open claims are analogous to goals
- grounded claims are analogous to discharged goals
- `InferAction` is analogous to a tactic that fills a hole
- local progress is observable as state (BeliefState)

### 7. Module and namespace discipline

Lean's environment model is strict about names, scope, and imported context.

Gaia should formalize:

- how local names are introduced
- how module-local names are resolved
- how refs preserve type
- which knowledge objects are visible vs exported into BP

## What Gaia Should Not Borrow From Lean

### 1. Propositions-as-types (Curry-Howard)

As established above, claims are terms, not types. Evidence connects via graph edges, not type inhabitation.

### 2. Full dependent type theory

Gaia does not need universe polymorphism, inductive families, or full dependent typing in V1. The current problem is "how do we deterministically validate reasoning structures?" not "how do we prove value-indexed programs correct?"

### 3. Definitional equality and reduction

Lean depends on normalization and definitional equality. Gaia's evaluation is BP on graphs, not term reduction. Definitional equality has no natural counterpart in plausible reasoning.

### 4. Monotonic proof semantics

Once a Lean theorem is proved, it stays proved. Gaia's beliefs are revised as new evidence arrives. Non-monotonicity is fundamental.

### 5. Aggressive implicit inference

Lean hides substantial complexity behind inference, coercions, and automation. Gaia's users are agents and reviewers who need legible artifacts. V1 should prefer explicitness.

## No LLM In The Kernel

The kernel must not depend on LLM calls.

- LLM outputs are not reliably reproducible
- kernel failures need crisp, local, explainable errors
- kernel checks should be cheap enough to run continuously
- trusted checking must not depend on model temperature or prompt drift

LLMs are appropriate for construction (proposing chains), review (assessing quality), and classification (estimating probabilities). But kernel judgments must be mechanically checkable.

## Formal Checking vs Semantic Review vs BP

Gaia has three validation layers, each with a distinct role:

| Layer | Job | Deterministic? | Uses LLM? |
|---|---|---|---|
| **Kernel (formal checking)** | Structural validity: refs resolve, signatures match, chains are well-formed, graph compiles | Yes | No |
| **Semantic review** | Content quality: reasoning supports conclusion, dependencies are correctly classified, no hallucination | No | Yes |
| **BP (inference)** | Compute posterior beliefs on a structurally valid graph | Yes (given graph) | No |

These should never be collapsed. A structurally valid chain may contain bad reasoning (review catches this). A well-reviewed chain needs BP to compute its contribution to overall belief.

## V1 Type System

### V1 goals

V1 should make the following explicit:

- a core set of knowledge kinds with formal rules
- action signatures as first-class checked structure
- typed chain connectivity
- the distinction between BP-bearing closed assertions and non-BP inquiry/workflow objects
- the boundary between surface syntax and checked core IR

### V1 core categories

The current categories are the right starting point:

| Type | Role | Truth-apt? | Participates in BP? |
|---|---|---|---|
| `Claim` | Assertive, revisable | Yes | Yes (variable node) |
| `Setting` | Contextual (definitions, assumptions) | Yes | Yes (variable node) |
| `Question` | Inquiry, follow-up, open issue | No | No |
| `Action` | Procedural (InferAction, ToolCallAction) | No (not by default) | Not directly; via lowering-specific structure |
| `Expr` | Compositional (ChainExpr) | No | Via steps |
| `Ref` | Reference to external knowledge | No | Via resolved target |
| `Module` | Organizational | No | Via exported knowledge objects |

V1 should strengthen the internal representation of these types — stop treating parameter types and return types as bare strings, use explicit type expressions and signatures.

This small root set can still support a richer scientific ontology through metadata and subkinds:

- `Claim(kind: observation | measurement | hypothesis | law | prediction | ...)`
- `Setting(kind: regime | approximation | experimental_setup | ...)`
- future `mode:` for deductive / inductive / abductive support
- future `under:` for background conditions and applicability assumptions

### V1 type-specific belief semantics

- `Claim = true` means the asserted proposition holds.
- `Setting = true` means the contextual assumption/definition holds.
- `Question` does not denote a truth-apt world claim by default; it denotes an inquiry artifact.
- `Action` does not denote a truth-apt scientific assertion by default; it denotes a procedural declaration that may lower into BP-relevant structure elsewhere.

### V1 BP position constraints

| Type | May appear as premise? | May appear as conclusion? |
|---|---|---|
| `Claim` | Yes | Yes |
| `Setting` | Yes | Yes |
| `Question` | No | No |
| `Action` | Lowering-specific, not directly | Lowering-specific, not directly |

### V1 relation constraints

- `Equivalence` is type-preserving.
- `Equivalence` and `Contradiction` are defined over truth-apt declarations and relation-bearing claim structures, not over `Question` or bare `Action` declarations in V1.

### V1 judgments

The kernel should establish these judgments:

**Formation:**
- `Γ ⊢ package ok`
- `Γ ⊢ module ok`
- `Γ ⊢ decl ok`

**Resolution:**
- `Γ ⊢ ref r resolves_to d`
- `Γ ⊢ ref r preserves_type`

**Action typing:**
- `Γ ⊢ action a : ActionSig(T₁, ..., Tₙ → Tₒᵤₜ, mode)`
- `Γ ⊢ apply(a, args) : Tₒᵤₜ`

**Chain well-formedness:**
- `Γ ⊢ step_i ok`
- `Γ ⊢ chain ok`
- `Γ ⊢ chain outputs H from T`

**Graph compilation:**
- `Γ ⊢ chain lowers_to fg_fragment`
- `Γ ⊢ fg well_formed`

**Belief participation (type-level):**
- `Γ ⊢ x belief_bearing`

**Export (module-level):**
- `Γ, M ⊢ x exportable`

Note the distinction: `belief_bearing` is an intrinsic property of a declaration's type. In V1, `Claim` and `Setting` are the root belief-bearing declaration types; richer BP-bearing distinctions such as observation, measurement, hypothesis, or law should be modeled as subkinds of those roots, not as new root types. `Question` and `Action` remain structurally important, but they are not BP-bearing by default. `exportable` is a module boundary property — it depends on whether `x` appears in module `M`'s export list, not on `x`'s type. Any declaration type can be exported or not.

These are intentionally modest — they define the structural kernel without overcommitting to future machinery.

## After V1: Expansion Path

### Phase 2: BeliefState and hole-driven reasoning

Make local reasoning state explicit:

- open claims (analogous to Lean goals)
- grounded claims (analogous to discharged goals)
- chain application against open claims
- checkpointing and local backtracking
- explicit progress inspection (`3/5 claims grounded, confidence 0.68`)

This is where the Lean proof-state analogy becomes operational.

### Phase 3: Type classes

Formalize shared behavior interfaces:

```
class TruthApt (K : Knowledge) where
  prior : K → Float
  belief : K → Float?

class BPNode (K : Knowledge) where
  to_variable : K → VariableNode

class Lowerable (K : Knowledge) where
  lower : K → CoreIRFragment

instance : TruthApt Claim
instance : TruthApt Setting
instance : BPNode Claim
instance : BPNode Setting
instance : Lowerable Action
instance : Lowerable Question
```

Type classes replace the current ad-hoc conventions (scattered if-else checks for "is this type truth-apt?") with explicit, checkable judgments. The `belief_bearing` judgment from V1 becomes derived from `TruthApt` / `BPNode` instances rather than hardcoded rules. `Question` and `Action` still matter structurally, but through `Lowerable`-style interfaces rather than by pretending they are ordinary BP variables. Note that `exportable` remains a module-level judgment — it depends on the module's export list, not on type class membership.

### Phase 4: User-extensible knowledge types

Move type definitions from the Python implementation layer into the language itself, with a clear distinction between closed and open layers.

**Root types are closed.** The base knowledge categories (Claim, Question, Setting, Action, Expr, Ref, Module) define the grammar of the language. They determine what kernel judgments apply, which objects are truth-apt, how knowledge objects participate in BP, and what structural rules hold. These are fixed by the language definition, just as Lean's core type formers (inductive, structure, class) are fixed.

**Subtypes are open.** Users can extend any root type with domain-specific subtypes without modifying the root definition:

```
-- User-defined subtypes of Claim
extend Claim where
  | Observation      -- direct empirical data
  | Measurement      -- quantitative observation
  | Hypothesis       -- explanatory candidate
  | Law              -- scoped general law
  | Prediction       -- model-derived claim

-- User-defined subtypes of Setting
extend Setting where
  | Regime           -- applicability condition
  | Approximation    -- idealization or simplifying assumption
```

New subtypes inherit the kernel rules of their parent (an `Observation` is a `Claim`, so it is `belief_bearing` and participates in BP). Type class instances can be overridden for subtypes where needed (e.g., `Observation` might have a different default prior policy than `Hypothesis`).

The exact syntax (`extend`, `open inductive`, or another mechanism) is deferred. The design commitment is: **closed root types for language integrity, open subtypes for domain extensibility.**

**Important scope limitation:** This extensibility defines the **structural** taxonomy of knowledge (what form it takes, what operations are valid). It does not define **content** classification (what topic it covers) — that remains the job of keywords, embeddings, and graph topology.

### Phase 5: Effect and capability typing

Distinguish action kinds more sharply:

- purely inferential steps
- tool-backed steps (require runtime environment)
- retrieval steps (require access to knowledge base)
- proof-producing steps (output formal artifacts)
- simulation or verification steps

This suggests typing actions by their capabilities and requirements:

```
action verify_claim : Action[requires=LeanRuntime, produces=Proof]
action search_literature : Action[requires=VectorDB, produces=List[Ref]]
```

### Phase 6: Restricted refinement typing

Add expressive types where clearly useful, without full dependent type theory:

```
-- Edge probability constraint depends on edge type
induction_edge : Edge where
  probability : { p : Float | 0 < p ∧ p < 1 }  -- must be < 1

-- Action that returns evidence for a specific claim schema
verify : Action(claim : Claim) → Evidence(claim)
```

This gives practical benefits of dependent types (value-level constraints in types) without the full complexity of CIC.

### Phase 7: Formal proof as sublanguage

If Gaia wants genuine formal proof support, add it as a narrower subsystem:

- `Formula` — formal logical statement
- `Proof` — formal proof artifact
- `LeanProofAction` — action that calls Lean to produce a proof
- `SMTCheckAction` — action that calls an SMT solver

Formal proof becomes one high-confidence evidence source among many. Some claims may have formal proofs attached; most will rely on probabilistic evidence and review. Gaia remains a language for defeasible scientific reasoning, with formal proof as an optional upgrade path.

## Summary

Gaia's type system follows one principle: **Lean's structure + Jaynes' semantics.**

From Lean, Gaia borrows architecture: trusted kernel, elaboration, judgments, environments, goal-state reasoning, module discipline.

From Lean, Gaia explicitly declines: Curry-Howard, full dependent types, definitional equality, monotonic proof semantics, aggressive implicit inference.

The expansion path is:

| Phase | Adds | Solves |
|---|---|---|
| **V1** | Typed structural kernel with judgments | Ad hoc validation → formal checking |
| **2** | BeliefState + hole-driven reasoning | Opaque reasoning → observable progress |
| **3** | Type classes | Implicit conventions → explicit interfaces |
| **4** | User-extensible knowledge types | Hardcoded types → open subtype taxonomy |
| **5** | Effect and capability typing | Undifferentiated actions → typed capabilities |
| **6** | Restricted refinement typing | Stringly-typed constraints → value-level type safety |
| **7** | Formal proof sublanguage | Probabilistic-only → formal proof as evidence source |

Each phase adds the minimum machinery needed for a real problem, without prematurely importing complexity from Lean's full type theory.
