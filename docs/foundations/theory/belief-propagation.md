# Belief Propagation

> **Status:** Current canonical

## 1. Factor Graphs

A factor graph is a bipartite graph with two kinds of nodes:

- **Variable nodes**: unknown quantities with prior distributions. In Gaia, these are knowledge nodes (propositions) with binary state: true (1) or false (0).
- **Factor nodes**: constraints or relationships between variables. In Gaia, these are reasoning links connecting premises to conclusions.

```
Variable nodes = Knowledge (propositions)
  prior  -> author-assigned plausibility, in (epsilon, 1 - epsilon)
  belief -> posterior plausibility computed by BP

Factor nodes = Reasoning links / constraints
  connects premises[] + conclusion(s)
  potential function encodes edge-type semantics
```

The joint probability over all variables factorizes as:

```
P(x1, ..., xn | I) proportional to  prod_j phi_j(x_j) * prod_a psi_a(x_S_a)
```

where phi_j is the prior (unary factor) for variable j, and psi_a is the potential function for factor a over its connected variable subset S_a. Potentials are not probabilities -- they need not normalize. Only ratios matter.

## 2. Sum-Product Message Passing

Messages are 2-vectors `[p(x=0), p(x=1)]`, always normalized to sum to 1.

### Algorithm

```
Initialize: all messages = [0.5, 0.5] (uniform, MaxEnt)
            priors = {var_id: [1-prior, prior]}

Repeat (up to max_iterations):

  1. Compute all variable -> factor messages (exclude-self rule):
     msg(v -> f) = prior(v) * prod_{f' != f} msg(f' -> v)
     Then normalize.

  2. Compute all factor -> variable messages (marginalize):
     msg(f -> v) = sum_{other vars} potential(assignment) * prod_{v' != v} msg(v' -> f)
     Then normalize.

  3. Damp and normalize:
     msg = alpha * new_msg + (1 - alpha) * old_msg
     Default alpha = 0.5.

  4. Compute beliefs:
     b(v) = normalize(prior(v) * prod_f msg(f -> v))
     Output belief = b(v)[1], i.e., p(x=1).

  5. Check convergence:
     If max |new_belief - old_belief| < threshold: stop.
```

Key design points:

- **Bidirectional messages**: variable-to-factor and factor-to-variable. Backward inhibition (modus tollens) emerges naturally.
- **Exclude-self rule**: when variable v sends a message to factor f, it excludes f's own incoming message. This prevents circular self-reinforcement.
- **Synchronous schedule**: all new messages are computed from old messages, then swapped simultaneously. Factor ordering does not affect results.
- **2-vector normalization**: messages always sum to 1, preventing numerical decay in long chains.

### Correspondence with Jaynes's Rules

| BP operation | Jaynes rule |
|---|---|
| Joint = product of potentials and priors | Product rule |
| Message normalization [p(0) + p(1) = 1] | Sum rule |
| belief = prior * product of factor-to-var messages | Bayes' theorem (posterior proportional to prior * likelihood) |
| Variable-to-factor message (exclude-self) | Background information P(H\|X) excluding current factor |
| Factor-to-variable message (marginalize) | Likelihood P(D\|HX) marginalized over other variables |

On tree-structured graphs, BP is exact. On loopy graphs, it is an approximation.

## 3. Loopy BP and Convergence

Real knowledge graphs have cycles. Loopy BP handles this by iterating message passing until beliefs stabilize.

**Damping** prevents oscillation on cyclic graphs:

```
msg_new = alpha * computed_msg + (1 - alpha) * msg_old
```

With alpha = 0.5 (default), each update moves halfway toward the new value. Damping trades convergence speed for stability.

Loopy BP minimizes the **Bethe free energy**, a variational approximation to the true free energy. On sparse graphs (typical of knowledge hypergraphs), this approximation is generally good. The system always produces a set of beliefs -- there is no "unsatisfiable" state. Incomplete knowledge yields uncertain beliefs, not system failure.

**Cromwell's rule** is enforced at two points:

1. **At construction**: all priors and conditional probabilities are clamped to [epsilon, 1-epsilon], with epsilon = 10^-3.
2. **In potentials**: the leak parameter in noisy-AND factors is itself the Cromwell lower bound, ensuring no state combination has zero potential.

This prevents degenerate updates where a zero probability blocks all future evidence.

## 4. Factor Potentials

Each factor type has a potential function mapping variable assignments to non-negative weights.

### 4.1 Reasoning Support (deduction / induction)

The current implementation uses a **conditional potential gated on all-premises-true**:

| All premises true? | Conclusion value | Potential |
|---|---|---|
| Yes | 1 | p (conditional probability) |
| Yes | 0 | 1 - p |
| No | any | 1.0 (unconstrained) |

where p is the author-assigned conditional probability for the reasoning step.

This covers both deduction (p close to 1.0) and induction (p < 1.0). The `edge_type` values `deduction`, `induction`, `abstraction`, and `paper-extract` all use this same potential shape in the current runtime (`libs/inference/bp.py`).

**Theoretical note**: the target model replaces the "unconstrained when premises false" row with a **noisy-AND + leak** potential (leak = epsilon), which ensures that false premises actively suppress the conclusion rather than leaving it at its prior. This satisfies Jaynes's fourth syllogism (weak denial). The current runtime does not yet implement noisy-AND + leak.

### 4.2 Contradiction

Penalizes the configuration where all premises are simultaneously true:

| All premises true? | Potential |
|---|---|
| Yes | epsilon (near zero) |
| No | 1.0 |

In the current implementation, conclusion variables in contradiction factors are non-participating -- the potential depends only on premises, so factor-to-conclusion messages are uniform and conclusion beliefs stay at their priors.

**BP behavior**: when two contradicted claims both have high belief, the factor sends strong inhibitory backward messages. The claim with weaker evidence is suppressed more -- this is the "weaker evidence yields first" principle, a direct consequence of Jaynes's rules operating in odds space.

For `relation_contradiction` factors (generated from Relation nodes), the relation node itself is included as a premise participant (`premises[0]`). This allows BP to "question the relationship" when both constrained claims have overwhelming evidence -- the relation's belief is lowered rather than indefinitely suppressing strong claims.

### 4.3 Equivalence

Rewards agreement and penalizes disagreement between two claims:

| Claim A value | Claim B value | Potential |
|---|---|---|
| A = B (agree) | | p (constraint strength) |
| A != B (disagree) | | 1 - p |

For `relation_equivalence` factors, the relation node participates as `premises[0]`, and p is derived from the relation node's current belief. When claims agree, the equivalence relation is strengthened; when they disagree, the relation itself is weakened.

N-ary equivalence is decomposed into pairwise factors sharing the same relation node.

### 4.4 Retraction

Inverts the standard conditional -- models evidence **against** a conclusion:

| All premises true? | Conclusion value | Potential |
|---|---|---|
| Yes | 1 | 1 - p |
| Yes | 0 | p |
| No | any | 1.0 (unconstrained) |

When retraction evidence is present (premises true), the conclusion is suppressed. When retraction evidence is absent (premises false), the factor is silent -- "absence of counter-evidence is not evidence of support."

### 4.5 Instantiation

Models the logical implication from a universal/schema claim to a specific instance:

| Schema (premise) | Instance (conclusion) | Potential |
|---|---|---|
| 1 (universal holds) | 1 (instance holds) | 1.0 |
| 1 (universal holds) | 0 (instance fails) | 0.0 (contradiction) |
| 0 (universal fails) | 1 (instance holds) | 1.0 (instance can hold independently) |
| 0 (universal fails) | 0 (instance fails) | 1.0 |

This is deterministic: if the schema is believed, the instance must be believed. If the instance is disbelieved, the schema is disbelieved (counterexample). If the schema is disbelieved, no constraint on the instance -- not-forall-x-P(x) does not imply not-P(a).

Inductive strengthening emerges from BP's message aggregation: multiple high-belief instances send backward messages that raise the schema's belief, while a single low-belief instance (counterexample) lowers the schema and propagates weakness to all other instances.

## 5. Factor Type Summary

| Factor type | Potential shape | Current implementation status |
|---|---|---|
| `infer` (deduction/induction) | Conditional on all-premises-true | Stable; `libs/inference/bp.py` |
| `abstraction` | Same as infer | Transitional; target is deterministic entailment |
| `instantiation` | Deterministic implication | Stable |
| `contradiction` | Jaynes penalty on all-premises-true | Stable |
| `relation_contradiction` | Same penalty with relation as participant | Stable |
| `relation_equivalence` | Agreement/disagreement reward | Stable |
| `retraction` | Inverted conditional | Stable |

## Source

- [../../foundations_archive/theory/inference-theory.md](../../foundations_archive/theory/inference-theory.md)
- [../../foundations_archive/bp-on-graph-ir.md](../../foundations_archive/bp-on-graph-ir.md)
- `libs/inference/bp.py` -- verified potential functions against implementation
