# Theoretical Foundation

> **Status:** Current canonical

## 1. What Gaia Is

Gaia is a **Large Knowledge Model (LKM)** -- a formal system for representing scientific knowledge as propositions with degrees of belief and reasoning relationships between them. It is not a knowledge graph (which stores entities and relations without uncertainty), not a probabilistic programming language (which models statistical distributions over random variables), and not a theorem prover (which produces deductive certainty).

Gaia is the intersection of three traditions:

| Tradition | What Gaia borrows |
|---|---|
| **Probabilistic graphical models** (factor graphs, BP) | Semantics: continuous beliefs, message passing, approximate inference |
| **Non-monotonic logic** (AGM belief revision) | Knowledge model: retraction, contradiction, defeasible reasoning |
| **Proof assistants** (Lean) | Architecture: construction/verification separation, package system, interactive workflow |

The theoretical root of all three layers is E.T. Jaynes's probability-as-logic programme.

## 2. Jaynes's Programme: Probability as Logic

Jaynes (*Probability Theory: The Logic of Science*, 2003) defines probability not as frequency but as **degree of plausibility**: P(A|X) is how believable proposition A is given information X. Every probability is conditional. Change the information, change the probability -- this is logical necessity, not subjective preference.

### Cox's Theorem

Cox (1946) proved that any system of plausible reasoning satisfying three requirements is isomorphic to probability theory:

1. **Real-valued**: plausibility is represented by real numbers
2. **Common-sense consistent**: evidence supporting A continuously increases A's plausibility
3. **Consistent**: equivalent reasoning paths yield the same answer; no information is ignored

From these, three rules are **derived** (not assumed):

- **Product rule**: P(AB|X) = P(A|BX) * P(B|X)
- **Sum rule**: P(A|X) + P(not-A|X) = 1
- **Bayes' theorem**: P(H|DX) = P(D|HX) * P(H|X) / P(D|X)

Probability theory is not one method among many -- it is the only consistent system.

### MaxEnt and Cromwell's Rule

Two principles constrain how Gaia initializes beliefs:

- **Maximum entropy**: when information is incomplete, choose the distribution with maximum entropy subject to known constraints. In Gaia, the default prior is 0.5 (maximum ignorance for a binary variable).
- **Cromwell's rule**: never assign probability 0 or 1 to an empirical proposition. If P(H) = 0, no amount of evidence can update it. All priors and probabilities are clamped to the open interval (epsilon, 1 - epsilon).

## 3. Jaynes's Robot

Jaynes frames his entire programme as designing a **robot** that:

- receives propositions and evidence, outputs plausibilities
- follows the three rules strictly (Cox's theorem)
- has no intuition or bias -- only structure and probabilities
- satisfies consistency -- the same question asked differently yields the same answer

**Gaia is an implementation of this robot.** The factor graph is the robot's reasoning engine. The content of propositions is opaque to the engine -- it only sees graph structure and probability parameters. Semantic understanding is handled by humans and LLMs at the content layer.

This explains Gaia's two-layer architecture:

| Layer | Role | Handled by |
|---|---|---|
| **Content layer** | Proposition semantics -- what claims mean | Humans + LLMs |
| **Graph structure layer** | Reasoning topology -- how claims relate | BP algorithm (automatic) |

## 4. Curry-Howard Analogy

Just as functional programming languages (Haskell, Lean) are grounded in the Curry-Howard correspondence between proofs and programs, Gaia aspires to extend this from deductive certainty to plausible belief. This is an open research direction, not an established theorem -- the full Curry-Howard correspondence for probabilistic computation remains an active area of study.

The key architectural borrowing from Lean is **construction/verification separation**: LLMs construct knowledge packages (and may hallucinate), while BP independently verifies belief consistency. A wrong construction does not corrupt the system -- verification catches it.

## 5. Why Not Existing Tools

| Tool class | What it provides | What it lacks for Gaia's purpose |
|---|---|---|
| **Probabilistic PLs** (Pyro, Stan) | Statistical probability over random variables | Epistemic probability over propositions; hypergraph structure |
| **Knowledge graphs** (Neo4j, OWL) | Entity-relation storage, deterministic queries | Probabilistic inference, contradiction handling |
| **Theorem provers** (Lean, Coq) | Deductive proof, dependent types | Uncertainty, defeasibility, non-monotonic reasoning |
| **Markov Logic Networks** | Probabilistic first-order logic | Statistical (not epistemic) probability; O(N^k) grounding |

Gaia's unique combination: structured package-based knowledge representation + epistemic probabilistic reasoning + hypergraph belief propagation.

## 6. Contradiction as First-Class Citizen

This is Gaia's most distinctive theoretical feature. In classical logic, contradiction triggers the explosion principle (ex falso quodlibet) -- from a contradiction, anything follows. In Jaynes's framework, contradiction is **evidence of conflict**: P(A and B | I) is near 0, meaning A and B cannot both be true. The system does not crash; it adjusts beliefs.

The weaker-evidence-yields-first principle emerges automatically: when a contradiction factor penalizes the all-true configuration, backward messages suppress all premises, but premises with lower prior are suppressed more (their prior odds are smaller, so the same likelihood ratio has a larger effect in odds space).

Traditional knowledge graphs fear contradiction as a data quality problem. Gaia embraces it as the engine of knowledge progress -- science advances through contradictions between experiments, theories, and predictions.

## Source

- [../../foundations_archive/theory/theoretical-foundation.md](../../foundations_archive/theory/theoretical-foundation.md)
- [../../foundations_archive/product-scope.md](../../foundations_archive/product-scope.md)
