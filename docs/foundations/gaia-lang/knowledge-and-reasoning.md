---
status: current-canonical
layer: gaia-lang
since: v5-phase-1
---

# Knowledge Types and Reasoning Semantics

This document bridges the Gaia Lang v5 Python DSL to the Gaia IR semantics layer. It explains what the three knowledge types mean, how operators constrain the factor graph, how named strategies formalize into deterministic operator expansions, and the compile-time DSL-to-IR mapping.

Source code references: `gaia/ir/knowledge.py`, `gaia/ir/operator.py`, `gaia/ir/strategy.py`, `gaia/ir/formalize.py`, `gaia/bp/potentials.py`, `gaia/lang/compiler/compile.py`, `gaia/ir/parameterization.py`.

---

## 1. Knowledge Types

Three types, defined in [Gaia IR -- Knowledge](../gaia-ir/02-gaia-ir.md#1-knowledge知识).

### 1.1 Claim

The only type carrying probability (prior + posterior belief). Claims participate in BP as variable nodes. They may be **closed** (all variables bound, `parameters=[]`) or **universal** (quantified variables in `parameters`).

DSL entry point: `gaia.lang.Knowledge(content=..., type="claim")`.

Key properties:

- Carries `PriorRecord` in parameterization layer
- Appears in operator `variables` and `conclusion` positions
- Appears in strategy `premises` and `conclusion` positions
- Universal claims can be instantiated into closed claims via deduction

### 1.2 Setting

Background context -- not a probabilistic proposition.

- Does **not** participate in BP (no messages sent or received)
- Can appear in strategy `background` parameter (context dependency, not probabilistic input)
- Can appear in `metadata.refs` for weak association
- Cannot appear in operator `variables` or `conclusion` (operators connect claims only)

DSL entry point: `gaia.lang.Knowledge(content=..., type="setting")`.

### 1.3 Question

Open research inquiry documenting what the package investigates.

- No probability, no BP participation
- Same positional constraints as setting: `background` and `refs` only

DSL entry point: `gaia.lang.Knowledge(content=..., type="question")`.

---

## 2. Operator Semantics

Operators encode **deterministic logical constraints** between claims. Each operator type has a fully determined potential matrix -- no free parameters. They express logical structure ("A and B are contradictory"), not reasoning judgment ("the author believes A implies B"). The latter is expressed by strategies.

Reference: [Gaia IR -- Operators](../gaia-ir/02-gaia-ir.md#2-operator结构约束).

### 2.1 Arity Rules

| Operator | `variables` | `conclusion` |
|----------|-------------|--------------|
| `implication` | exactly 1 (antecedent A) | consequent B |
| `equivalence` | exactly 2 (A, B) | helper claim |
| `contradiction` | exactly 2 (A, B) | helper claim |
| `complement` | exactly 2 (A, B) | helper claim |
| `conjunction` | >= 2 (A1, ..., Ak) | result M |
| `disjunction` | >= 2 (A1, ..., Ak) | result D |

The `conclusion` never appears in `variables` -- inputs and output are strictly separated.

### 2.2 Truth Tables

All potentials use Cromwell softening: logical "true" maps to `1 - eps`, logical "false" maps to `eps`, where `eps = CROMWELL_EPS = 1e-3`. Values below are from `gaia/bp/potentials.py`.

**Implication** -- `implication_potential(A, B)`: forbid A=1, B=0.

| A | B | psi |
|---|---|-----|
| 0 | 0 | 1 - eps |
| 0 | 1 | 1 - eps |
| 1 | 0 | eps |
| 1 | 1 | 1 - eps |

**Conjunction** -- `conjunction_potential(inputs, M)`: M = AND(inputs).

| all inputs = 1? | M | psi |
|-----------------|---|-----|
| yes | 1 | 1 - eps |
| yes | 0 | eps |
| no | 1 | eps |
| no | 0 | 1 - eps |

**Disjunction** -- `disjunction_potential(inputs, D)`: D = OR(inputs).

| any input = 1? | D | psi |
|-----------------|---|-----|
| yes | 1 | 1 - eps |
| yes | 0 | eps |
| no | 1 | eps |
| no | 0 | 1 - eps |

**Equivalence** -- `equivalence_potential(A, B, H)`: H = (A == B).

| A == B? | H | psi |
|---------|---|-----|
| yes | 1 | 1 - eps |
| yes | 0 | eps |
| no | 1 | eps |
| no | 0 | 1 - eps |

**Contradiction** -- `contradiction_potential(A, B, H)`: H = NOT(A AND B).

| A=1 and B=1? | H | psi |
|---------------|---|-----|
| yes | 0 | 1 - eps |
| yes | 1 | eps |
| no | 0 | eps |
| no | 1 | 1 - eps |

**Complement** -- `complement_potential(A, B, H)`: H = (A XOR B).

| A != B? | H | psi |
|---------|---|-----|
| yes | 1 | 1 - eps |
| yes | 0 | eps |
| no | 1 | eps |
| no | 0 | 1 - eps |

### 2.3 Helper Claims

Operators produce a `conclusion` claim. For relation-type operators (`equivalence`, `contradiction`, `complement`, `disjunction`), this conclusion is a **helper claim** -- an ordinary `claim` node with metadata marking it as structural. Helper claims carry no independent prior; their distribution is fully determined by the operator's truth table.

Reference: [Helper Claims](../gaia-ir/04-helper-claims.md).

---

## 3. Strategy Semantics

Strategies express probabilistic reasoning: premises support a conclusion with some conditional probability. All uncertainty in Gaia IR lives at the strategy layer.

Strategies have three forms (`Strategy`, `CompositeStrategy`, `FormalStrategy`) and a `type` field indicating the reasoning family. These two dimensions are orthogonal.

### 3.1 Direct Strategy Types

One strategy type carries explicit external probability parameters via `StrategyParamRecord`:

**`infer`** -- Lowered to a CONDITIONAL factor with full CPT.

- `2^k` conditional probability entries (one per premise truth-value combination)
- Default MaxEnt: all entries = 0.5
- Parameters from `StrategyParamRecord.conditional_probabilities`

**`noisy_and`** (deprecated) -- Use `support` instead. Compiles to `support` internally.

### 3.2 Named Strategy Formalization

Named strategies expand at compile time into `FormalStrategy` with generated helper claims and deterministic operators. The expansion is performed by `formalize_named_strategy()` in `gaia/ir/formalize.py`. The result is a `FormalizationResult` containing:

- `knowledges`: generated intermediate claim nodes (helper claims and interface claims)
- `strategy`: a `FormalStrategy` with `formal_expr` containing the operator skeleton

Named strategies carry **no independent `StrategyParamRecord`**. Their effective conditional behavior is derived from the `FormalExpr` skeleton plus the priors of interface claims.

#### 3.2.1 Support (soft deduction)

**Input:** `premises = [P1, P2, ..., Pk]` (k >= 1), `conclusion = C`.

**Expansion (k >= 2):**

```
helper M = all_true(P1, ..., Pk)
  conjunction([P1, ..., Pk], conclusion=M)
  implication([M], conclusion=C)    # warrant prior from author
```

**Expansion (k = 1):**

```
  implication([P1], conclusion=C)   # warrant prior from author
```

**Semantics:** Based on the **directed** `implication` operator (A=1 → B must =1). Same skeleton as deduction (conjunction + directed implication), but support is a soft (probabilistic) assertion. The author-specified prior on the implication warrant captures the strength of the support. Because implication is directed, information flows from premises to conclusion: true premises drive the conclusion true, but a true conclusion does not force premises true. When prior is high (~0.99), support behaves like deduction. When prior is moderate (~0.5-0.8), it expresses weaker empirical support.

#### 3.2.2 Deduction

**Input:** `premises = [P1, P2, ..., Pk]` (k >= 1), `conclusion = C`.

**Expansion:**

```
helper M = all_true(P1, ..., Pk)
  conjunction([P1, ..., Pk], conclusion=M)
  implication([M], conclusion=C)
```

**Semantics:** If all premises are true, the conclusion must be true. Pure deterministic entailment via directed `implication` operator. Same skeleton as support, but the reasoning is rigid (no epistemic uncertainty beyond the premises themselves).

#### 3.2.3 Mathematical Induction

**Input:** `premises = [Base, Step]` (exactly 2), `conclusion = C`.

**Expansion:**

```
helper M = all_true(Base, Step)
  conjunction([Base, Step], conclusion=M)
  implication([M], conclusion=C)
```

**Semantics:** Structurally identical to deduction with exactly 2 premises. The `type` field distinguishes the reasoning family.

#### 3.2.4 Analogy

**Input:** `premises = [Source, Bridge]` (exactly 2), `conclusion = Target`.

**Expansion:**

```
helper M = all_true(Source, Bridge)
  conjunction([Source, Bridge], conclusion=M)
  implication([M], conclusion=Target)
```

**Semantics:** The bridge claim (e.g., "the structural similarity between source and target domains is sufficient") is an interface claim carrying its own prior. When the bridge prior is low, the implication weakens -- the analogy is less convincing. M is a private helper claim.

#### 3.2.5 Extrapolation

**Input:** `premises = [Source, Continuity]` (exactly 2), `conclusion = Target`.

**Expansion:**

```
helper M = all_true(Source, Continuity)
  conjunction([Source, Continuity], conclusion=M)
  implication([M], conclusion=Target)
```

**Semantics:** The continuity claim (e.g., "the observed trend continues into the extrapolated regime") carries the uncertainty. Structurally identical to analogy; distinguished by `type`.

#### 3.2.6 Compare

**Input:** `premises = [pred_h, pred_alt, observation]` (exactly 3), `conclusion = C`.

**Expansion:**

```
helper H_match1 = matches(pred_h, observation)
helper H_match2 = matches(pred_alt, observation)
  equivalence([pred_h, observation], conclusion=H_match1)
  equivalence([pred_alt, observation], conclusion=H_match2)
  implication([H_match2, H_match1], conclusion=C)
```

**Semantics:** Each prediction is compared to the observation via equivalence (does the prediction match?). The implication asserts that if the alternative also matches, the hypothesis must also match -- expressing inferential ordering. The author-specified prior on the implication warrant captures the strength of the comparison. H_match1 and H_match2 are private helper claims.

#### 3.2.7 Abduction

**Input:** `premises = [Observation]` or `premises = [Observation, AlternativeExplanation]`, `conclusion = Hypothesis`.

**Expansion (1-premise form -- alternative auto-generated):**

```
interface_claim Alt = alternative_explanation_for(Observation)
helper D = explains(Observation)          # disjunction result
helper Eq = same_truth(D, Observation)    # equivalence result
  disjunction([Hypothesis, Alt], conclusion=D)
  equivalence([D, Observation], conclusion=Eq)
```

When only the observation is provided, the compiler generates a **public interface claim** `AlternativeExplanationForObs` and appends it to `premises`. This interface claim carries an independent prior (it is *not* a helper claim) and may be supported by other strategies.

**Expansion (2-premise form):**

Same operator structure, but uses the author-provided alternative explanation instead of generating one.

**Semantics:** The observation is equivalent to "at least one of the hypothesis or the alternative explanation is true." When the alternative explanation's prior is low, BP drives the hypothesis's posterior up. D and Eq are private helper claims.

#### 3.2.8 Elimination

**Input:** `premises = [Exhaustiveness, Cand1, Evid1, Cand2, Evid2, ...]`, `conclusion = Survivor`.

Requires at least 3 premises; the remainder after `Exhaustiveness` must come in (candidate, evidence) pairs.

**Expansion (with n candidate-evidence pairs):**

```
helper D = any_true(Cand1, ..., Candn, Survivor)
helper Eq = same_truth(D, Exhaustiveness)
  disjunction([Cand1, ..., Candn, Survivor], conclusion=D)
  equivalence([D, Exhaustiveness], conclusion=Eq)

for each (Candi, Evidi):
  helper Contrai = not_both_true(Candi, Evidi)
    contradiction([Candi, Evidi], conclusion=Contrai)

gate_inputs = [Exhaustiveness, Evid1, Contra1, ..., Evidn, Contran]
helper Gate = all_true(gate_inputs...)
  conjunction(gate_inputs, conclusion=Gate)
  implication([Gate], conclusion=Survivor)
```

**Semantics:** The candidates plus the survivor form an exhaustive disjunction (tied to the exhaustiveness claim via equivalence). Each candidate is eliminated by its contradicting evidence. The conjunction gate collects all the evidence and contradiction confirmations; when all pass, the survivor is implied.

#### 3.2.9 Case Analysis

**Input:** `premises = [Exhaustiveness, Case1, Support1, Case2, Support2, ...]`, `conclusion = C`.

Requires at least 3 premises; the remainder after `Exhaustiveness` must come in (case, support) pairs.

**Expansion (with n case-support pairs):**

```
helper D = any_true(Case1, ..., Casen)
helper Eq = same_truth(D, Exhaustiveness)
  disjunction([Case1, ..., Casen], conclusion=D)
  equivalence([D, Exhaustiveness], conclusion=Eq)

for each (Casei, Supporti):
  helper Mi = all_true(Casei, Supporti)
    conjunction([Casei, Supporti], conclusion=Mi)
    implication([Mi], conclusion=C)
```

**Semantics:** The cases form an exhaustive disjunction. For each case, the case claim and its supporting evidence are conjoined and imply the conclusion. If any case is true and its support holds, the conclusion follows. Every case independently implies the conclusion.

### 3.3 Composite Strategies

`CompositeStrategy` references sub-strategies by `strategy_id`. It does not introduce new operators directly -- it organizes multiple strategy-level sub-structures into a larger argument tree.

At lowering time, composite strategies are **recursively expanded** by default: each sub-strategy is resolved to its own `FormalStrategy` or leaf `Strategy`, and the full factor graph is assembled from all of them. Intermediate variables remain visible in the factor graph and participate in BP.

A utility function `fold_composite_to_cpt()` is also provided to compute the composite's effective CPT by marginalization. It recursively computes each sub-strategy's effective CPT via tensor contraction, then contracts child CPTs along shared bridge variables to produce the composite's CPT. Exact, no BP iterations. This produces a 2^k CPT (k = number of premises) that captures the composite's aggregate reasoning behavior — useful for analysis or for collapsing a composite into a single `CONDITIONAL` factor.

Composite strategies **do not require** `review_strategy()` parameters in the review sidecar -- only the leaf sub-strategies (if they are `infer` type) need parameterization. FormalStrategy sub-strategies (support, deduction, abduction, etc.) are deterministic and need no parameters at all.

### 3.4 Induction as Composite Strategy

`induction` is a `CompositeStrategy` wrapping multiple `support` sub-strategies that share the same `conclusion` (the law being induced). The inductive effect emerges from factor graph topology: multiple supports sharing a conclusion node cause BP to accumulate evidence.

```
CompositeStrategy(type=induction, conclusion=Law):
  sub_strategies:
    - FormalStrategy(type=support, premises=[Law], conclusion=Obs1)
    - FormalStrategy(type=support, premises=[Law], conclusion=Obs2)
    - ...
```

At the DSL level, `induction(s1, s2, law)` takes two Strategy objects and a law claim, and is chainable: `induction(prev_induction, new_support, law)`.

### 3.5 Deferred Strategy Types

The following are recognized in the type enum but not yet formalized:

- **`reductio`** -- The public-interface contract for hypothetical assumption/consequence nodes is not yet fixed.

---

## 4. DSL to IR Mapping

The compiler (`gaia/lang/compiler/compile.py`) transforms collected DSL objects into a `LocalCanonicalGraph`.

### 4.1 Object Mapping

| DSL Type | IR Type | Key Transformation |
|----------|---------|-------------------|
| `gaia.lang.Knowledge` | `gaia.ir.Knowledge` | QID assigned (`{namespace}:{package_name}::{label}`), `content_hash` computed as SHA-256(type + content + sorted(parameters)) |
| `gaia.lang.Strategy` (leaf) | `gaia.ir.Strategy` | For `infer`: direct mapping. For named types (`support`, `deduction`, `compare`, `abduction`, `analogy`, `extrapolation`, `elimination`, `case_analysis`, `mathematical_induction`): `formalize_named_strategy()` produces `FormalStrategy` + generated `Knowledge` nodes |
| `gaia.lang.Strategy` (with sub_strategies) | `gaia.ir.CompositeStrategy` | Sub-strategies compiled recursively; referenced by `strategy_id`. At lowering, expanded into sub-strategy factors. `fold_composite_to_cpt()` available for deriving aggregate CPT. |
| `gaia.lang.Strategy` (with formal_expr) | `gaia.ir.FormalStrategy` | Operators mapped to IR operators; embedded (no `operator_id` / `scope`) |
| `gaia.lang.Operator` | `gaia.ir.Operator` | Top-level: `operator_id` with `lco_` prefix, `scope="local"`. Within `formal_expr`: no ID/scope |
| `gaia.lang.CollectedPackage` | `gaia.ir.LocalCanonicalGraph` | All knowledge (local + referenced foreign), operators, and strategies assembled |

### 4.2 Compile-Time Formalization

When the compiler encounters a leaf `Strategy` with a named type (`support`, `deduction`, `compare`, `abduction`, `analogy`, `extrapolation`, `elimination`, `case_analysis`, `mathematical_induction`), it calls `formalize_named_strategy()` which:

1. Creates a `_TemplateBuilder` with the strategy's premises and conclusion
2. Invokes the type-specific builder function (e.g., `_build_deduction`)
3. The builder generates intermediate `Knowledge` nodes (helper claims and interface claims) and returns a list of `Operator` objects
4. The result is packaged as a `FormalStrategy` with a `FormalExpr` containing the operators
5. Generated knowledge nodes are appended to the graph's `knowledges` list

### 4.3 Identity Assignment

- **Knowledge IDs:** Local declarations get QIDs from the package's namespace and name. Anonymous nodes (no label) get auto-generated labels (`_anon_001`, `_anon_002`, ...). Foreign references preserve their original QID.
- **Strategy IDs:** Deterministically computed as `lcs_{SHA-256(scope + type + sorted(premises) + conclusion + structure_hash)[:16]}`.
- **Operator IDs:** Top-level operators get `lco_{SHA-256(operator + sorted(var_ids) + conclusion_id)[:16]}`.

---

## 5. Cromwell's Rule

All probabilities in Gaia IR are clamped to `[eps, 1 - eps]` where:

```
CROMWELL_EPS = 1e-3
```

Defined in `gaia/ir/parameterization.py` and `gaia/bp/factor_graph.py`.

This applies to:

- `PriorRecord.value` (claim priors)
- `StrategyParamRecord.conditional_probabilities` (strategy parameters)
- All factor potential values (truth table entries use `1 - eps` instead of 1, `eps` instead of 0)
- CPT entries in conditional factors
- Soft entailment p1/p2 parameters

The rule ensures that no assignment is assigned zero probability, preserving the ability of BP to revise any belief given sufficient evidence.

Reference: [Parameterization](../gaia-ir/06-parameterization.md).
