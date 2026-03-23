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

**Theoretical note**: the target model replaces the "unconstrained when premises false" row with a **noisy-AND + leak** potential (leak = epsilon), which ensures that false premises actively suppress the conclusion rather than leaving it at its prior. This satisfies Jaynes's fourth syllogism (weak denial). The current runtime does not yet implement noisy-AND + leak. See the detailed parameterization in section 6 below.

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

## 6. Noisy-AND + Leak: Target Potential Model

### 6.1 Parameters

The noisy-AND + leak model requires only two parameters per reasoning factor:

- **p** — conditional probability P(C=1 | all premises true), the author-assigned strength of the reasoning step.
- **epsilon (leak)** — background probability that the conclusion holds even when premises are not all true. Default: Cromwell lower bound (10^-3).

This compresses the full CPT (2^n entries for n premises) into 2 parameters, matching Gaia's authoring model where the author specifies a single conditional probability.

### 6.2 Potential Function

```
phi(P1, ..., Pn, C):
  all Pi=1, C=1  ->  p          (premises true, support conclusion)
  all Pi=1, C=0  ->  1-p        (premises true, conclusion absent)
  any Pi=0, C=1  ->  epsilon    (premises not all true, conclusion still true -> near-impossible)
  any Pi=0, C=0  ->  1-epsilon  (premises not all true, conclusion false -> compatible)
```

The key difference from the current all-or-nothing model is the third and fourth rows: instead of potential = 1.0 (silence), false premises actively suppress the conclusion via the epsilon/1-epsilon ratio. This satisfies Jaynes's fourth syllogism (weak denial).

### 6.3 Why Noisy-AND Generalizes the Current Model

The current model sets potential = 1.0 when any premise is false, making the factor silent. This is equivalent to setting epsilon = 0.5 in the noisy-AND formulation (equal weight to C=1 and C=0). The noisy-AND model with epsilon << 1 is strictly more expressive:

- epsilon = 0.5 recovers the current silent behavior
- epsilon -> 0 gives hard AND gating (conclusion impossible without premises)
- epsilon = 10^-3 (default) gives strong but not absolute suppression

### 6.4 Jaynes's Four Syllogisms Verified

Given premises P1, P2 with priors pi_1=0.9, pi_2=0.8, conditional probability p=0.9, epsilon=0.001:

**Marginal probability of C:**

```
P(C=1) = p * pi_1 * pi_2 + epsilon * (1 - pi_1 * pi_2)
       = 0.9 * 0.72 + 0.001 * 0.28
       = 0.648
```

**Syllogism 1 — Modus Ponens:** P(C=1 | P1=1, P2=1) = p = 0.9. Premises true implies conclusion supported.

**Syllogism 2 — Weak confirmation:** P(P1=1 | C=1) = P(C=1|P1=1) * pi_1 / P(C=1) where P(C=1|P1=1) = p*pi_2 + epsilon*(1-pi_2) = 0.7202. Result: 0.7202 * 0.9 / 0.648 = 0.9997 > 0.9. Conclusion true raises premise belief.

**Syllogism 3 — Modus Tollens:** P(P1=1 | C=0) = P(C=0|P1=1) * pi_1 / P(C=0) where P(C=0|P1=1) = 0.2798. Result: 0.2798 * 0.9 / 0.352 = 0.716 < 0.9. Conclusion false lowers premise belief.

**Syllogism 4 — Weak denial:** P(C=1 | P1=0) = epsilon = 0.001 << 0.648. Premise false strongly suppresses conclusion. Under the current model (silent), C would only drop to its prior, not to 0.001.

### 6.5 Weak Syllogism: Partial Premise Support

With noisy-AND + leak, partial premise support (some premises believed, others uncertain) produces graded conclusion support. Consider three premises with beliefs b1=0.9, b2=0.6, b3=0.3:

The factor-to-conclusion message is computed by marginalizing over all premise states, weighted by their beliefs. The dominant terms are:

- All true (weight ~ b1*b2*b3 = 0.162): contributes p to conclusion
- Mixed states (remaining weight ~ 0.838): contributes epsilon to conclusion

The resulting conclusion support is approximately:

```
msg(C=1) ~ 0.162 * p + 0.838 * epsilon
         ~ 0.162 * 0.9 + 0.838 * 0.001
         ~ 0.147
```

This is much lower than the all-premises-true case (0.9) but higher than the all-premises-false case (0.001). Partial evidence gives partial support — a smooth interpolation that the current all-or-nothing gating cannot express.

## 7. Factor Potential Derivations by Type

This section collects the explicit potential formulas for all factor types.

### 7.1 Reasoning Support (deduction / induction)

**Current:** conditional potential gated on all-premises-true (section 4.1 above).

**Target (noisy-AND + leak):** phi(P1..Pn, C) as defined in section 6.2.

### 7.2 Contradiction

```
phi(C_contra, A1, ..., An):
  C_contra=1, all Ai=1  ->  epsilon   (contradiction holds and all claims true -> near-impossible)
  all other combinations ->  1.0       (unconstrained)
```

When both contradicted claims have strong evidence, the factor sends inhibitory backward messages. The claim with weaker evidence yields first (the "weaker evidence yields first" principle from odds-space reasoning). When both claims have overwhelming evidence, the relation node C_contra itself is suppressed — the system questions the contradiction.

### 7.3 Equivalence

```
phi(C_equiv, A, B):
  C_equiv=1, A=B    ->  1-epsilon  (equivalence holds + agreement -> high compatibility)
  C_equiv=1, A!=B   ->  epsilon    (equivalence holds + disagreement -> low compatibility)
  C_equiv=0, any    ->  1.0        (no equivalence -> unconstrained)
```

N-ary equivalence decomposes into pairwise factors sharing the same C_equiv node.

### 7.4 Retraction

```
phi(P1..Pn, C):
  all Pi=1, C=1  ->  1-p   (retraction evidence present, conclusion survives -> unlikely)
  all Pi=1, C=0  ->  p     (retraction evidence present, conclusion suppressed -> likely)
  any Pi=0, any  ->  1.0   (retraction evidence absent -> silent)
```

Retraction is correctly silent when evidence is absent: "absence of counter-evidence is not evidence of support."

### 7.5 Instantiation

```
phi(Schema, Instance):
  Schema=1, Instance=1  ->  1.0    (universal holds, instance holds)
  Schema=1, Instance=0  ->  0.0    (universal holds, instance fails -> contradiction)
  Schema=0, Instance=1  ->  1.0    (universal fails, instance can hold independently)
  Schema=0, Instance=0  ->  1.0    (universal fails, no constraint)
```

Deterministic: schema true forces instance true. Instance false forces schema false (counterexample). Schema false places no constraint on instance (not-forall-x-P(x) does not imply not-P(a)).

## 8. Current vs Target

| Aspect | Current implementation | Noisy-AND target |
|---|---|---|
| **Reasoning support potential** | All-or-nothing gating: potential = 1.0 when any premise is false (silent) | Noisy-AND + leak: potential = epsilon when any premise is false (active suppression) |
| **Jaynes syllogism 4** | Not satisfied: false premises leave conclusion at prior | Satisfied: false premises drive conclusion toward epsilon |
| **Weak syllogism** | Not expressible: partial premise support produces no graded signal | Smooth interpolation between full support and full suppression |
| **Contradiction/equivalence** | Relation node belief used as gate strength; relation belief not updated by BP | Target: relation node participates as ordinary BP variable; can be questioned when evidence conflicts |
| **Parameters** | p (conditional probability) per reasoning step | p + epsilon (leak, default 10^-3) per reasoning step |
| **Implementation** | `libs/inference/bp.py` — stable, tested | Not yet implemented in runtime |

The current implementation is correct for its scope: on graphs where premises are well-supported, the all-or-nothing gating produces reasonable beliefs. The noisy-AND target addresses edge cases (partial evidence, syllogism 4 compliance) and is the planned next revision.

## Source

- [../../foundations_archive/theory/inference-theory.md](../../foundations_archive/theory/inference-theory.md)
- [../../foundations_archive/bp-on-graph-ir.md](../../foundations_archive/bp-on-graph-ir.md)
- `libs/inference/bp.py` -- verified potential functions against implementation
