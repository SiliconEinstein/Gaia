# Gaia Type System Direction

> Related documents:
> - [Gaia Language Spec](gaia-language-spec.md)
> - [Gaia Language Design](gaia-language-design.md)
> - [Language Design Rationale](design-rationale.md)

## Purpose

This document summarizes the current design direction for Gaia's type system.

It focuses on five questions:

1. which Lean ideas Gaia should borrow
2. which Lean ideas Gaia should avoid in V1
3. what `judgment` means in the Gaia kernel
4. how kernel-level formal checking differs from semantic review
5. how the type system should expand after V1

The short version:

- Gaia should borrow Lean's architecture more than Lean's type theory
- Gaia should have a small deterministic kernel for structural checking
- Gaia should keep LLMs out of the trusted kernel
- Gaia should treat formal proof as one future evidence source, not as the whole language

## Current Position

Gaia is not a direct clone of Lean.

The existing foundation docs already define Gaia as a **proof assistant for probabilistic defeasible reasoning**, not as a general-purpose PL and not as a probabilistic version of the Calculus of Inductive Constructions.

That distinction matters:

- Lean is centered on binary proof validity
- Gaia is centered on support structure, review, and belief revision
- Lean's kernel checks whether a proof term establishes a proposition
- Gaia's kernel should check whether a knowledge artifact is structurally valid and whether it can safely enter review, execution, and BP

## What Gaia Should Learn From Lean

Gaia should borrow the following traits from Lean.

### 1. Small trusted kernel

Lean's most important design property is not dependent types. It is the existence of a small trusted core with a clear trust boundary.

For Gaia, the trusted core should be responsible for deterministic structural checks such as:

- declaration formation
- ref resolution
- action signature checking
- chain well-formedness
- factor-graph compilation validity
- export and module boundary checks

This makes the system reviewable and reproducible.

### 2. Construction and verification separation

In Lean, tactics construct candidate proof terms, but the kernel verifies the result independently.

Gaia should preserve the same separation:

- LLMs, tools, and search procedures construct candidate reasoning structures
- the kernel checks structural validity
- review checks reasoning quality
- BP computes posterior beliefs on the resulting structure

This prevents the language from treating model output as trusted truth.

### 3. Elaboration

Lean distinguishes between surface syntax and core terms.

Gaia should do the same:

- authors and agents write a convenient YAML surface form
- the system elaborates it into a smaller typed core IR
- all kernel checks operate on that core IR

Gaia already has the beginning of this split in `loader`, `resolver`, and `elaborator`, but the current elaboration is still mostly name-resolution and prompt rendering rather than type-directed elaboration.

### 4. Judgments and rules

Lean is defined in terms of judgments and inference rules. Gaia should also define its kernel in that style.

That gives the language a precise answer to questions such as:

- what does it mean for a `Ref` to be valid
- what does it mean for an `Action` signature to be valid
- what does it mean for a `ChainExpr` to be well-formed
- what does it mean for a chain to compile into a valid factor graph

Without judgments, the system remains a collection of ad hoc validators.

### 5. Context-sensitive checking

Lean checks terms relative to an environment or context.

Gaia also needs this.

Examples:

- a `Ref` is only meaningful relative to a module/package environment
- an `apply` step is only meaningful relative to the available action signature
- a `chain_expr` is only meaningful relative to the declarations it mentions

So Gaia should explicitly model a checking environment `Gamma` rather than hiding everything in string lookups.

### 6. Goal-state thinking

Lean's tactic engine operates on proof state with open goals.

Gaia should borrow that mental model for local reasoning:

- open claims are analogous to goals
- grounded claims are analogous to discharged goals
- `InferAction` is analogous to a tactic that attempts to fill a hole
- local progress should be observable as state, not only as final output

This is the right long-term foundation for `BeliefState`.

### 7. Module and namespace discipline

Lean's environment model is strict about names, scope, and imported context.

Gaia should likewise formalize:

- how local names are introduced
- how module-local names are resolved
- how refs preserve type
- which declarations are merely visible versus exported into BP/LKM-facing structure

This is especially important because Gaia separates local authoring names from publish-time identity.

## What Gaia Should Not Learn From Lean

Gaia should avoid importing the following Lean features into V1.

### 1. Full dependent type theory

Gaia does not need universe polymorphism, inductive families, or full dependent typing to solve its current problems.

The current problem is not "how do we prove value-indexed programs correct?" It is "how do we deterministically validate reasoning structures for plausible and defeasible knowledge?"

Adding CIC-level machinery in V1 would impose large complexity with little immediate payoff.

### 2. Global propositions-as-types

Not every Gaia `Claim` should be treated as a formal proposition in the Lean sense.

Reasons:

- many Gaia claims are natural-language scientific statements
- many are defeasible and revisable
- many depend on empirical evidence and review
- many admit graded support rather than deductive completion

If all claims are forced into propositions-as-types, Gaia risks confusing:

- being supported
- being well-formed
- being formally proved

Those are different states and should remain separate.

### 3. Heavy definitional equality machinery

Lean depends on rich normalization and definitional equality.

Gaia mostly does not need that in V1 because its core objects are not primarily lambda terms whose meaning is decided by reduction. Gaia's immediate needs are structural consistency and graph-compilation validity.

### 4. Monotonic proof semantics

Lean lives in a monotonic world:

- once a theorem is proved, it stays proved

Gaia does not:

- new evidence can weaken an old claim
- contradiction and retraction are first-class
- belief is updated rather than fixed forever

That makes Gaia closer to belief revision and probabilistic graphical models than to theorem proving in the narrow sense.

### 5. Aggressive implicit inference and automation

Lean can hide substantial complexity behind inference, coercions, and automation.

Gaia should be cautious here. Its main users are agents and reviewers who need legible artifacts.

Too much hidden inference would:

- reduce auditability
- make generated packages harder to review
- blur the boundary between explicit knowledge and compiler guesses

V1 should prefer explicitness over magical convenience.

## What `Judgment` Means In Gaia

A `judgment` is not an AST node and not a runtime artifact.

It is a statement the kernel tries to establish.

Typical examples in PL and theorem prover design:

- `Gamma |- t : T`
- `Gamma |- expr elaborates_to core`
- `Gamma |- fg well_formed`

For Gaia, useful judgments include the following.

### Formation judgments

These define which objects are valid declarations at all.

Examples:

- `Gamma |- d decl_ok`
- `Gamma |- m module_ok`
- `Gamma |- p package_ok`

### Resolution judgments

These define valid name and ref resolution.

Examples:

- `Gamma |- ref r resolves_to d`
- `Gamma |- ref r : Ref(T)`

### Typing judgments

These define which type each declaration or step has.

Examples:

- `Gamma |- c : Claim`
- `Gamma |- s : Setting`
- `Gamma |- a : Action(T1, ..., Tn => Tout, mode)`
- `Gamma |- step : Tout`

### Chain well-formedness judgments

These define whether a reasoning chain is structurally coherent.

Examples:

- `Gamma |- chain ok`
- `Gamma |- apply(a, args) : Tout`
- `Gamma |- chain supports heads from tails`

### Graph compilation judgments

These define whether a valid chain can be lowered into BP-facing structure.

Examples:

- `Gamma |- chain => fg`
- `Gamma |- fg well_formed`

### Export and integration judgments

These define which objects may participate in downstream inference or publication boundaries.

Examples:

- `Gamma |- x exportable`
- `Gamma |- x belief_bearing`

## Judgments, Rules, and Kernel Passes

These terms should not be collapsed.

| Layer | Meaning | Gaia example |
|---|---|---|
| Judgment | What the kernel is trying to establish | `Gamma |- chain ok` |
| Rule | Why the judgment is allowed to hold | "an `apply` step is valid when each argument matches the action signature" |
| Kernel pass | Implementation phase that checks rules | `resolve_refs()`, `type_check_chain()`, `compile_factor_graph()` |

So a judgment is not "one little implementation step." It is the semantic target of a checker step.

## Formal Checking vs Semantic Review

Gaia should explicitly distinguish two validation layers.

### 1. Kernel formal checking

This is the trusted deterministic layer.

Its job is to answer questions like:

- is this package structurally valid
- do names and refs resolve
- do action signatures line up
- is the chain interface coherent
- can the chain compile into a valid factor graph

This layer should:

- be deterministic
- be reproducible
- be cheap to rerun
- avoid model calls
- produce precise errors

LLMs should not be required here.

### 2. Semantic review

This is the untrusted or semi-trusted content-evaluation layer.

Its job is to answer questions like:

- does this reasoning actually support the conclusion
- is this dependency really direct or indirect
- is the chain skipping essential steps
- is the claim semantically faithful to the evidence
- is the contradiction or retraction justified

This layer may use:

- LLM review
- tool execution
- proof assistants
- dataset checks
- reproduction or simulation
- human review

This layer is where Gaia's "semantic checking" lives.

### 3. BP as a third layer

BP should not be confused with either of the two checks above.

BP:

- does not check free-form text quality
- does not replace semantic review
- computes posterior beliefs on a structurally valid graph

So Gaia's architecture should remain:

1. formal kernel check
2. semantic review
3. probabilistic inference

## No LLM In The Kernel

This deserves an explicit rule.

The kernel should not depend on LLM calls.

Reasons:

- LLM outputs are not reliably reproducible
- trusted checking should not depend on model temperature or prompt drift
- kernel failures need crisp, local, explainable errors
- kernel checks should be cheap enough to run continuously

LLMs are appropriate for:

- proposing candidate chains
- filling open claims
- drafting content
- reviewing semantic quality
- classifying support strength as a proposal

But final kernel judgments should remain mechanically checkable.

## V1 Type System Direction

Gaia V1 should aim for a typed structural kernel, not a full theorem prover.

### V1 goals

V1 should make the following things explicit:

- a small core set of knowledge kinds
- action signatures as first-class structure
- typed chain connectivity
- the distinction between visible declarations and belief-bearing declarations
- the boundary between authoring surface syntax and checked core IR

### Suggested core categories

Gaia's current high-level categories are already close to the right starting point:

- `Claim`
- `Question`
- `Setting`
- `Action`
- `Expr`
- `Ref`
- `Module`

But V1 should strengthen the internal representation of these types.

In particular, Gaia should stop treating action parameter types and return types as mere strings and instead move toward explicit type expressions and signatures.

### Suggested V1 kernel outputs

After formal checking, the kernel should be able to say:

- this package is well-formed
- these refs resolve
- these actions have valid signatures
- these chains are structurally valid
- these declarations are belief-bearing
- these chains compile into this graph structure

That is enough to support execution, review, and BP without prematurely turning Gaia into a proof assistant in the Lean/Coq sense.

## Suggested V1 Judgments

The following is a practical V1 judgment set.

### Package and module formation

- `Gamma |- package_ok`
- `Gamma |- module_ok`
- `Gamma |- decl_ok`

### Reference resolution

- `Gamma |- ref r resolves_to d`
- `Gamma |- ref r preserves_type`

### Action typing

- `Gamma |- action a : ActionSig`
- `Gamma |- arg_i : Ti`
- `Gamma |- apply(a, args) : Tout`

### Chain checking

- `Gamma |- step_i ok`
- `Gamma |- chain ok`
- `Gamma |- chain outputs H from T`

### Graph compilation

- `Gamma |- chain lowers_to fg_fragment`
- `Gamma |- package lowers_to fg`
- `Gamma |- fg well_formed`

### Export and belief participation

- `Gamma |- x exportable`
- `Gamma |- x belief_bearing`

These are intentionally modest. They define the structural kernel without overcommitting to future proof machinery.

## After V1: Recommended Expansion Path

Gaia should expand in layers.

### Phase 1: Typed structural kernel

This is the immediate target.

Add:

- explicit type expressions
- explicit action signatures
- typed chain checking
- explicit graph-lowering rules
- explicit kernel judgments

Do not add:

- full dependent types
- general theorem proving
- LLM-dependent kernel semantics

### Phase 2: BeliefState and hole-driven local reasoning

After V1, Gaia should make local reasoning state explicit.

Add:

- open claims
- grounded claims
- chain application against open claims
- checkpointing and local backtracking
- explicit local progress inspection

This is where the Lean proof-state analogy becomes operational rather than merely conceptual.

### Phase 3: Richer scientific knowledge sorts

The next meaningful semantic growth is not full dependent typing. It is a richer ontology of scientific knowledge.

Possible additions:

- `Observation`
- `Experiment`
- `Dataset`
- `Model`
- `Hypothesis`
- `Method`
- `Protocol`
- `Measurement`

This makes Gaia better at scientific knowledge representation without forcing all knowledge into theorem-prover semantics.

### Phase 4: Effect and capability typing

Gaia should eventually distinguish between kinds of actions more sharply.

Examples:

- purely inferential steps
- tool-backed steps
- retrieval steps
- proof-producing steps
- simulation or verification steps

This suggests adding action modes or capabilities such as:

- required environment
- external tool dependency
- reproducibility constraints
- artifact outputs

This is more valuable in practice than early dependent types.

### Phase 5: Restricted refinement typing

Only after the previous layers are stable should Gaia consider more expressive types.

The right starting point is not full CIC. It is restricted refinement or indexed typing where it is clearly useful.

Examples:

- an action that requires a specific setting kind
- a proof-producing action that returns `Proof(phi)` rather than arbitrary text
- a verification action whose output must be evidence of a specific claim schema

This gives many of the practical benefits associated with "dependent types" without paying the full complexity cost.

### Phase 6: Formal proof as a sublanguage, not the whole language

If Gaia later wants genuine formal proof support, it should add it as a narrower subsystem.

For example:

- `Formula`
- `Proof`
- `LeanProofAction`
- `SMTCheckAction`

In that design:

- some Gaia claims may have formal proof artifacts attached
- formal proof becomes a high-confidence evidence source
- Gaia as a whole still remains a language for defeasible scientific reasoning

This is far better than trying to force the entire language into propositions-as-types.

## Practical Consequences For The Current Codebase

The current codebase already reflects part of this architecture:

- loading surface syntax
- resolving refs
- elaborating prompts
- executing actions
- compiling to a factor graph
- running BP

But the current implementation is still pre-kernel in several important ways:

- parameter and return types are still plain strings
- ref resolution is not yet type-preserving by judgment
- chain checking is mostly shape-based rather than rule-based
- BP participation is still hard-coded rather than derived from typed declarations

So the next language-design step should not be "add more kinds of YAML nodes."

It should be:

1. define the kernel judgments
2. define the rules behind those judgments
3. define the checked core IR
4. make the implementation passes establish those judgments explicitly

## Summary

Gaia should borrow from Lean at the architectural level:

- trusted kernel
- elaboration
- judgments and rules
- explicit environments
- goal-state reasoning

Gaia should avoid borrowing Lean wholesale at the type-theoretic level:

- full dependent types
- global propositions-as-types
- monotonic proof semantics
- heavy implicit automation

The right path is:

1. V1 typed structural kernel
2. BeliefState and hole-driven reasoning
3. richer scientific knowledge sorts
4. effect and capability typing
5. restricted refinement typing where justified
6. formal proof as a future sublanguage and evidence source

That path keeps Gaia rigorous without making it pretend to be Lean before it has earned the right to do so.
