# Theory Documents Restructuring — Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restructure `docs/foundations/theory/` into three logical layers: Jaynes theory → Scientific ontology → Computational methods, with factor graphs/BP repositioned as approximation.

**Architecture:** 7 documents in 3 layers. Layer 1 (docs 01-02) presents pure Jaynes theory. Layer 2 (docs 03-05) introduces propositional operators, reasoning strategies, and formalization methodology — all in probability language without factor graphs. Layer 3 (docs 06-07) maps the theory to factor graphs and BP as computational approximation. Downstream files get cross-reference updates.

**Tech Stack:** Markdown documentation, no code changes.

**Spec:** `docs/specs/2026-03-26-theory-docs-restructuring-design.md`

---

## Chunk 1: Layer 1 — Jaynes Theory (docs 01, 02)

### Task 1: Doc 01 — Plausible Reasoning (minor revision)

**Files:**
- Modify: `docs/foundations/theory/01-plausible-reasoning.md`

**What changes:** Add theory stack positioning section. The document is already solid — just needs a header block showing where it sits in the derivation chain, and a brief note that this layer is independent of any computational method.

- [ ] **Step 1: Read current document**

Read `docs/foundations/theory/01-plausible-reasoning.md` fully.

- [ ] **Step 2: Add derivation chain header**

After the title/front matter, add a positioning block:

```markdown
> **Derivation chain position:** This is the foundation layer.
> Jaynes/Cox → **[this document]** → MaxEnt Grounding → Propositional Operators → ...
>
> This document establishes why probability is the unique formalism for plausible reasoning.
> It depends on no other Gaia document. Everything downstream builds on the results here.
```

- [ ] **Step 3: Update internal cross-references to new filenames**

Doc 01 contains a reading order list (lines 12-17) and multiple inline cross-references to old theory filenames. Update ALL of them:
- `01a-jaynes-maxent-grounding.md` → `02-maxent-grounding.md`
- `02-reasoning-factor-graph.md` → `03-propositional-operators.md`
- `03-coarse-reasoning.md` → `03-propositional-operators.md`
- `04-belief-propagation.md` → `07-belief-propagation.md`
- `05-science-ontology.md` → `04-reasoning-strategies.md`
- `06-science-formalization.md` → `05-formalization-methodology.md`

Search the entire document for each old filename and replace. There are ~11 references.

- [ ] **Step 4: Verify no factor graph / BP leakage**

Search the document for: "factor", "因子", "BP", "belief propagation", "message passing", "potential function". These terms should NOT appear. (The current doc is clean, but verify after edits.)

- [ ] **Step 5: Commit**

```bash
git add docs/foundations/theory/01-plausible-reasoning.md
git commit -m "docs: add theory stack positioning and update cross-references in 01-plausible-reasoning"
```

### Task 2: Doc 02 — MaxEnt Grounding (medium revision)

**Files:**
- Modify: `docs/foundations/theory/01a-jaynes-maxent-grounding.md` → rename to `docs/foundations/theory/02-maxent-grounding.md`

**What changes:** Create new file `02-maxent-grounding.md` based on `01a-jaynes-maxent-grounding.md`. Rewrite sections that use factor graph language (especially §5 "局部分解与因子图" and §8) to use pure probability/MaxEnt language. Update all internal cross-references to new filenames. The core MaxEnt/Min-KL content stays; only the framing changes. (The old `01a` file remains in place until Task 8 archives it.)

- [ ] **Step 1: Read current document**

Read `docs/foundations/theory/01a-jaynes-maxent-grounding.md` fully. Identify all lines containing "因子图", "因子", "factor graph", "factor", "势函数", "potential".

- [ ] **Step 2: Create new file with renamed path**

Create `docs/foundations/theory/02-maxent-grounding.md` with the content from `01a-jaynes-maxent-grounding.md`.

- [ ] **Step 3: Rewrite factor graph language**

Replace factor graph framing with pure probability language:
- "局部因子图形式" → "局部乘积分解" or "局部可分解形式"
- "因子" (meaning factor in factor graph) → "局部函数" or "约束函数"
- "势函数" → remove or rephrase as "条件概率"
- Keep the mathematical content (exponential family, Lagrange multipliers) — only change the framing metaphor

Key principle: §5's result (MaxEnt with local features → exponential family → product form) is a MATHEMATICAL result about probability distributions. It does NOT require factor graphs. The product form is a property of the MaxEnt solution, not an artifact of a computational graph.

- [ ] **Step 4: Add derivation chain header**

```markdown
> **Derivation chain position:** Layer 1 — Jaynes Theory
> Plausible Reasoning → **[this document]** → Propositional Operators → ...
>
> This document bridges Jaynes' abstract axioms to computable posteriors via MaxEnt/Min-KL.
> It depends on `01-plausible-reasoning.md` for Cox's theorem and the three probability rules.
```

- [ ] **Step 5: Update internal cross-references**

Update all references to old theory filenames within the document:
- `02-reasoning-factor-graph.md` → `03-propositional-operators.md`
- `04-belief-propagation.md` → `07-belief-propagation.md`
- Any other old filename references → corresponding new filenames (see mapping in Task 10)

- [ ] **Step 6: Verify no factor graph / BP leakage**

Search for: "factor graph", "因子图", "BP", "belief propagation", "消息传递", "message passing". None should remain.
Note: "因子" meaning "mathematical factor in a product" is acceptable; "因子" meaning "factor node in a factor graph" is not.

- [ ] **Step 7: Commit**

```bash
git add docs/foundations/theory/02-maxent-grounding.md
git commit -m "docs: create 02-maxent-grounding from 01a, remove factor graph language"
```

(The old `01a-jaynes-maxent-grounding.md` will be deleted in the archive task later.)

---

## Chunk 2: Layer 2 — Scientific Ontology (docs 03, 04, 05)

### Task 3: Doc 03 — Propositional Operators (FULL REWRITE)

**Files:**
- Create: `docs/foundations/theory/03-propositional-operators.md`
- Reference: `docs/foundations/theory/02-reasoning-factor-graph.md` (current, for content migration)
- Reference: `docs/foundations/theory/03-coarse-reasoning.md` (current, for ↝ content)
- Reference: `docs/specs/2026-03-26-theory-docs-restructuring-design.md` (spec)

**What changes:** Full rewrite. The current `02-reasoning-factor-graph.md` defines operators in factor graph language (potential functions, truth tables as ψ values). The new document defines the same operators in pure Jaynes probability language. Additionally introduces ↝ (plausible implication) as the only parameterized operator, with completeness argument.

- [ ] **Step 1: Read current documents for content reference**

Read `docs/foundations/theory/02-reasoning-factor-graph.md` and `docs/foundations/theory/03-coarse-reasoning.md` to understand the operator definitions and coarse reasoning content to migrate.

- [ ] **Step 2: Write the new document**

Structure:

```markdown
# 命题算子与似然蕴含

> **Derivation chain position:** Layer 2 — Scientific Ontology
> MaxEnt Grounding → **[this document]** → Reasoning Strategies → ...
>
> This document defines the propositional operators for Gaia's knowledge representation.
> It depends on `01-plausible-reasoning.md` (Cox's theorem, three rules)
> and `02-maxent-grounding.md` (MaxEnt/Min-KL, product decomposition).

## 1. 最小原料：{¬, ∧, π}

[From spec §1: Two propositional operations + one numerical assignment, derived from Jaynes' rules]
[Explicit note distinguishing operations from parameter]

## 2. 派生算子

### 2.1 严格蕴含 →
A→B ≡ P(A ∧ ¬B | I) = 0
[Derive from ¬ and ∧; show this is "compound proposition with prior zero"]

### 2.2 析取 ∨
A∨B ≡ ¬(¬A ∧ ¬B)
[Derive from ¬ and ∧]

### 2.3 等价 ↔
P(A ∧ ¬B) = 0 ∧ P(¬A ∧ B) = 0
[= two entailments: A→B and B→A]

### 2.4 矛盾 ⊗
P(A ∧ B) = 0
[= entailment to negation: A→¬B]

### 2.5 互补 ⊕ (negation relation)
A and B are truth-complements: equivalence between A and ¬B
[= A↔¬B]

## 3. 关系类型

[Three structural relations — equivalence, contradiction, negation — as they appear in knowledge networks. Defined purely using derived operators from §2.]

## 4. 似然蕴含 ↝

### 4.1 定义
A ↝ B with parameters (p₁, p₂):
[Conditional probability table from spec §2]
[p₁ = inference reliability, p₂ = condition relevance]

### 4.2 理论地位
- Theoretically reducible to {¬, ∧, π} with auxiliary propositions
- Practically essential for incompletely formalized reasoning
- Unique: the ONLY operator carrying conditional probability parameters

### 4.3 退化情况
[From spec: p₁=1,p₂=1 → equivalence; p₁=1,p₂ free → entailment-like; p₁ free,p₂=0.5 → uninformative reverse]

### 4.4 与现有粗推理算子的关系
[From spec §2: old single-parameter p → new (p₁, p₂) where p₂=0.5]

### 4.5 Jaynes 理论中的起源
[No fundamental soft link; ↝ = macro view of strict operator micro-structure with uncertain intermediate priors]

## 5. 多前提推理中的 ∧ + ↝
[What was called noisy-AND: strict conjunction combines premises, plausible implication connects to conclusion. From spec §3.]

## 6. 完备性

### 6.1 确定性完备性
{¬, ∧} 是布尔函数完备的（经典结果）

### 6.2 概率完备性
{¬, ∧, π, ↝} + 辅助变量可表达任意二值联合分布
[Full proof sketch from spec §4, with mutual exclusivity argument]

### 6.3 科学推理中的实际模式
[Worst case exponential, but practical patterns need few auxiliaries]
```

- [ ] **Step 3: Verify no factor graph / BP leakage**

Search the new document for: "factor", "因子图", "势函数", "potential", "BP", "belief propagation", "消息", "message". None should appear.

- [ ] **Step 4: Commit**

```bash
git add docs/foundations/theory/03-propositional-operators.md
git commit -m "docs: write 03-propositional-operators — Jaynes-grounded operator theory"
```

### Task 4: Doc 04 — Reasoning Strategies (FULL REWRITE)

**Files:**
- Create: `docs/foundations/theory/04-reasoning-strategies.md`
- Reference: `docs/foundations/theory/05-science-ontology.md` (current, for content migration)
- Reference: `docs/foundations/theory/03-coarse-reasoning.md` (current, for micro-structure content)
- Reference: `docs/specs/2026-03-26-theory-docs-restructuring-design.md` (spec, especially §5 worked example)

**What changes:** Full rewrite. Merges knowledge types from current `05-science-ontology.md` with reasoning strategies, reframes all strategies as ↝ micro-structures, adds Bayes-law derivations for effective (p₁, p₂), fixes abduction direction.

- [ ] **Step 1: Read current documents for content reference**

Read `docs/foundations/theory/05-science-ontology.md` and `docs/foundations/theory/03-coarse-reasoning.md`.

- [ ] **Step 2: Write the new document**

Structure:

```markdown
# 推理策略

> **Derivation chain position:** Layer 2 — Scientific Ontology
> Propositional Operators → **[this document]** → Formalization Methodology → ...
>
> This document defines knowledge types and reasoning strategies as micro-structures of ↝.
> It depends on `03-propositional-operators.md` for operator definitions and ↝.

## 1. 知识类型

### 1.1 Claim（主张）
[Has prior π, participates in inference. The only type bearing a truth value.]

### 1.2 Setting（背景设定）
[No prior, does not participate in inference. Structural context.]

### 1.3 Question（问题）
[No prior, does not participate in inference. Motivational framing.]

### 1.4 Template（模板）
[Parameterized pattern. Bridges to Claim via instantiation. v1: hidden/reserved.]

## 2. 推理策略：↝ 的微观结构

[Central thesis: every ↝ link can be decomposed into a network of strict operators
{¬, ∧, →, ↔, ⊗} with intermediate propositions bearing uncertain priors.
Each strategy provides a standard decomposition pattern.
For each strategy, we derive the effective (p₁, p₂) of the macro ↝ under Bayes' law.]

### 2.1 演绎（Deduction）
**Macro:** Premises ↝ Conclusion with p₁=1
**Micro:** M = A₁ ∧ ... ∧ Aₖ, M → C (strict entailment)
**Bayes derivation:**
- P(C=1|M=1) = 1 (strict entailment)
- P(C=0|M=0): C reverts to prior — depends on other support
- Effective: p₁ = 1, p₂ = π(¬C) (prior-dependent)
[Deduction is the only strategy where the macro ↝ is already strict.]

### 2.2 溯因（Abduction）
**Macro:** Observation ↝ Hypothesis (epistemic direction: evidence → conclusion)
**Micro:** H → O (hypothesis entails prediction) + O ↔ Obs (prediction matches observation)
**Bayes derivation:**
[Full worked example from spec §5:
- P(H=1|Obs=1) = π(H) / [π(H) + π(O)·(1-π(H))]
- P(H=0|Obs=0) = 1 (modus tollens via strict entailment)
- Effective: p₁ = π(H)/[π(H) + π(O)(1-π(H))], p₂ = 1]
**Note:** The ↝ direction (O→H) is the epistemic direction. The micro-structure
contains a strict entailment in the OPPOSITE direction (H→O). This is consistent:
the micro-structure IS the mechanism; the macro ↝ IS the effective relationship.

### 2.3 归纳（Induction）
**Macro:** {Obs₁, Obs₂, ..., Obsₙ} ↝ Law
**Micro:** Law → Instance₁ (→) + Instance₁ ↔ Obs₁, ..., Law → Instanceₙ (→) + Instanceₙ ↔ Obsₙ
**Bayes derivation:**
- P(Law=1 | all Obsᵢ=1) = π(Law) / [π(Law) + (1-π(Law))·∏ π(Obsᵢ)]
- As n grows with each π(Obsᵢ) < 1, posterior → 1 (accumulating evidence)
- Single counterexample Obsⱼ=0: forces Instanceⱼ=0 via equivalence, then modus tollens
  on Law→Instanceⱼ forces Law=0
- Effective p₁ increases with n; p₂ = 1 (any counterexample kills the law)

### 2.4 类比（Analogy）
**Macro:** SourceConclusion ↝ TargetConclusion
**Micro:** [SourceLaw, BridgeClaim] → TargetConclusion (strict, with ∧ on premises)
  BridgeClaim: "source and target domains share relevant structure"
**Bayes derivation:**
- Strength depends on π(BridgeClaim) — the bridge's plausibility
- P(Target=1 | Source=1) = π(BridgeClaim) (when SourceLaw is certain)
- Effective: p₁ = π(BridgeClaim), p₂ ≈ π(¬Target)

### 2.5 外推（Extrapolation）
[Structurally same as analogy: known range → extended range, with a "continuity" bridge claim.]
**Bayes derivation:** Same pattern as analogy.

### 2.6 归谬（Reductio ad Absurdum）
**Macro:** Contradiction ↝ ¬Hypothesis
**Micro:** P → Q (→) + Q ⊗ R (contradiction) + P ⊕ ¬P (complement)
  Observing R + deducing Q from P → contradiction → P must be false → ¬P is true
**Bayes derivation:**
- P(¬P=1 | R=1) = 1 if Q ⊗ R is strict and P→Q is strict (deterministic reductio)
- Effective: p₁ = 1, p₂ depends on alternative support for ¬P
[Note: requires negation/complement relation ⊕, not yet in Graph IR — flagged as non-goal]

### 2.7 排除（Elimination）
**Macro:** ExhaustiveContradictions ↝ RemainingCandidate
**Micro:** All alternatives contradicted + exhaustiveness entailment
**Bayes derivation:**
- If exactly one candidate survives all contradictions: p₁ = 1
- Effective: p₁ = 1, p₂ = prior-dependent
[Note: also requires ⊕, same Graph IR non-goal as reductio]
```

- [ ] **Step 3: Verify Bayes derivations are consistent**

For each strategy, check:
- Does the micro-structure correctly use only operators defined in doc 03?
- Does the Bayes derivation correctly follow from the micro-structure?
- Are the effective (p₁, p₂) values consistent with the micro-structure?

- [ ] **Step 4: Verify no factor graph / BP leakage**

Search for: "factor", "因子图", "势函数", "potential", "BP", "belief propagation", "消息", "message passing". None should appear. (Use terms like "命题网络" not "因子图".)

- [ ] **Step 5: Commit**

```bash
git add docs/foundations/theory/04-reasoning-strategies.md
git commit -m "docs: write 04-reasoning-strategies — strategies as ↝ micro-structures with Bayes derivations"
```

### Task 5: Doc 05 — Formalization Methodology (medium revision)

**Files:**
- Modify: `docs/foundations/theory/06-science-formalization.md` → content migrated to `docs/foundations/theory/05-formalization-methodology.md`

**What changes:** Rename from `06` to `05`. Replace "粗因子图" with "粗命题网络". Replace "noisy-AND" / "粗推理算子" with "↝ (似然蕴含)". Remove factor graph terminology. Update cross-references to point to new doc 03 and 04. Keep the three-step methodology and Galileo example.

- [ ] **Step 1: Read current document**

Read `docs/foundations/theory/06-science-formalization.md` fully. Identify all factor graph terminology to replace.

- [ ] **Step 2: Create new file and revise**

Create `docs/foundations/theory/05-formalization-methodology.md`. Systematic replacements:
- "粗因子图" → "粗命题网络" (coarse propositional network)
- "细因子图" → "细命题网络" (fine propositional network)
- "因子图" → "命题网络" (propositional network)
- "粗推理算子" → "↝ (似然蕴含)"
- "noisy-AND" → remove or replace with "∧ + ↝"
- Factor references like `02-reasoning-factor-graph.md` → `03-propositional-operators.md`
- Strategy references like `05-science-ontology.md` → `04-reasoning-strategies.md`

- [ ] **Step 3: Add derivation chain header**

```markdown
> **Derivation chain position:** Layer 2 — Scientific Ontology
> Reasoning Strategies → **[this document]** → [computational boundary] → Factor Graphs → ...
>
> This document provides the methodology for converting scientific arguments to propositional networks.
> It depends on `03-propositional-operators.md` (operators) and `04-reasoning-strategies.md` (strategies).
```

- [ ] **Step 4: Verify no factor graph / BP leakage**

Search for: "因子图", "factor graph", "势函数", "potential", "BP", "belief propagation". None should remain.

- [ ] **Step 5: Commit**

```bash
git add docs/foundations/theory/05-formalization-methodology.md
git commit -m "docs: create 05-formalization-methodology, remove factor graph terminology"
```

---

## Chunk 3: Layer 3 — Computational Methods (docs 06, 07)

### Task 6: Doc 06 — Factor Graphs (NEW document)

**Files:**
- Create: `docs/foundations/theory/06-factor-graphs.md`
- Reference: `docs/foundations/theory/02-reasoning-factor-graph.md` (current, source material)
- Reference: `docs/foundations/theory/04-belief-propagation.md` (current, for factor graph content)

**What changes:** New document that explicitly positions factor graphs as a computational representation of propositional networks. Migrates the factor graph formalism, hypergraph structure, and potential function definitions from current `02-reasoning-factor-graph.md`. Adds the mapping from each operator (¬, ∧, →, ↔, ⊗, ↝) to potential functions. Explicitly states the relationship to exact Jaynes inference.

- [ ] **Step 1: Read source documents**

Read `docs/foundations/theory/02-reasoning-factor-graph.md` (current factor graph content) and the factor graph sections of `docs/foundations/theory/04-belief-propagation.md` (current).

- [ ] **Step 2: Write the new document**

Structure:

```markdown
# 因子图：命题网络的计算表示

> **Derivation chain position:** Layer 3 — Computational Methods
> [computational boundary] → **[this document]** → Belief Propagation
>
> This document defines factor graphs as a computational representation of propositional networks.
> Factor graphs are NOT part of Jaynes' theory — they are an engineering choice for efficient inference.
> It depends on `03-propositional-operators.md` for operator definitions.

## 1. 动机：从精确推理到可计算近似

[Exact Jaynes inference requires summing over all configurations — O(2^n) for n propositions.
Factor graphs exploit the product structure of the joint distribution to enable efficient
approximate inference via message passing.]

## 2. 因子图形式

### 2.1 定义
[Bipartite graph: variable nodes (propositions) + factor nodes (operators/constraints)]
[Hypergraph: factors connect subsets of variables]

### 2.2 联合分布分解
P(x₁,...,xₙ) ∝ ∏_j φⱼ(xⱼ) · ∏_a ψₐ(x_Sₐ)
[φⱼ = prior functions, ψₐ = factor potentials]

## 3. 算子到势函数的映射

### 3.1 否定 ¬
[Unary factor: ψ(A, ¬A) — deterministic complement]

### 3.2 合取 ∧
[Multi-ary factor: ψ = 1 iff all inputs match conjunction truth table]

### 3.3 严格蕴含 →
[Binary factor: ψ(1,0)=0, all others=1 — encodes hard constraint P(A∧¬B)=0]

### 3.4 等价 ↔
[Binary factor: ψ(0,1)=0, ψ(1,0)=0, others=1]

### 3.5 矛盾 ⊗
[Binary factor: ψ(1,1)=0, all others=1]

### 3.6 似然蕴含 ↝
[Binary factor with parameters:
 ψ(1,1) = p₁, ψ(1,0) = 1-p₁, ψ(0,0) = p₂, ψ(0,1) = 1-p₂
 Relationship to current single-parameter model: p₂=0.5 → ψ(0,*)=1 (uniform)]

### 3.7 多前提推理（∧ + ↝）
[Compound factor: conjunction node + plausible implication.
 This is what was previously called "noisy-AND" — now decomposed explicitly.]

## 4. 与精确 Jaynes 推理的关系

[Factor graph encodes the SAME joint distribution as the propositional network.
 No information is lost in the mapping — only the representation changes.
 The advantage is computational: the product structure enables message-passing algorithms.]

## 5. 超图结构

[Why ordinary graphs aren't enough: multi-variable constraints require hyperedges.
 Factor graph is a bipartite representation of a hypergraph.]
```

- [ ] **Step 3: Verify all cross-references use new filenames**

Since this document is written fresh (drawing from old source material), ensure all cross-references use new filenames:
- References to operator definitions → `03-propositional-operators.md`
- References to BP algorithm → `07-belief-propagation.md`
- References to strategies → `04-reasoning-strategies.md`
- NO references to old filenames (`02-reasoning-factor-graph.md`, `03-coarse-reasoning.md`, etc.)

- [ ] **Step 4: Verify positioning language**

The document must explicitly state that factor graphs are a computational tool, not part of the theory. Check the opening paragraph and §1 for clear framing.

- [ ] **Step 5: Commit**

```bash
git add docs/foundations/theory/06-factor-graphs.md
git commit -m "docs: write 06-factor-graphs — computational representation of propositional networks"
```

### Task 7: Doc 07 — Belief Propagation (medium revision)

**Files:**
- Modify: `docs/foundations/theory/04-belief-propagation.md` (current) → content migrated to `docs/foundations/theory/07-belief-propagation.md`

**What changes:** Rename from `04` to `07`. Reposition BP as "approximate inference on factor graphs" (not "the theory"). Add explicit opening statement about BP being an approximation. Update cross-references to point to new document numbers. Keep the algorithm content (sum-product, convergence, damping, Bethe free energy). Update the Jaynes correspondence table to emphasize it's a correspondence, not a derivation.

- [ ] **Step 1: Read current document**

Read `docs/foundations/theory/04-belief-propagation.md` fully.

- [ ] **Step 2: Create new file and revise**

Create `docs/foundations/theory/07-belief-propagation.md`. Key changes:

1. Add derivation chain header:
```markdown
> **Derivation chain position:** Layer 3 — Computational Methods
> Factor Graphs → **[this document]**
>
> This document defines Belief Propagation as an approximate inference algorithm on factor graphs.
> BP is one possible computational method — it is NOT part of Jaynes' theory itself.
> On tree-structured graphs, BP gives exact results. On loopy graphs, it is approximate (Bethe free energy).
> It depends on `06-factor-graphs.md` for factor graph definitions and potential functions.
```

2. Update section references from old doc numbers to new ones:
   - `02-reasoning-factor-graph.md` → `06-factor-graphs.md`
   - `03-coarse-reasoning.md` → `03-propositional-operators.md §4` (↝ definition)
   - `05-science-ontology.md` → `04-reasoning-strategies.md`

3. In the "Correspondence to Jaynes" table, add a note:
   "This table shows how BP operations correspond to Jaynes' rules, establishing BP as a faithful
   approximation. The correspondence is exact on trees; on loopy graphs, BP minimizes the Bethe
   free energy, which is an approximation to the true Gibbs free energy."

4. Replace "noisy-AND" terminology with "∧ + ↝ (合取 + 似然蕴含)".

- [ ] **Step 3: Verify all cross-references use new filenames**

The current `04-belief-propagation.md` contains ~12 references to old filenames. After creating `07-belief-propagation.md`, verify ALL internal cross-references are updated:
- `02-reasoning-factor-graph.md` → `06-factor-graphs.md`
- `03-coarse-reasoning.md` → `03-propositional-operators.md §4`
- `05-science-ontology.md` → `04-reasoning-strategies.md`
- `06-science-formalization.md` → `05-formalization-methodology.md`
- `01-plausible-reasoning.md` → unchanged (same filename)

- [ ] **Step 4: Verify positioning language**

Check that the document clearly states BP is an approximation in the title area and §1.

- [ ] **Step 5: Commit**

```bash
git add docs/foundations/theory/07-belief-propagation.md
git commit -m "docs: create 07-belief-propagation, reposition as approximate inference"
```

---

## Chunk 4: Archive, Index, and Downstream References

### Task 8: Archive old documents

**Files:**
- Delete: `docs/foundations/theory/01a-jaynes-maxent-grounding.md` (replaced by `02-maxent-grounding.md`)
- Delete: `docs/foundations/theory/02-reasoning-factor-graph.md` (replaced by `03-propositional-operators.md` + `06-factor-graphs.md`)
- Delete: `docs/foundations/theory/03-coarse-reasoning.md` (content merged into `03-propositional-operators.md`)
- Delete: `docs/foundations/theory/04-belief-propagation.md` (replaced by `07-belief-propagation.md`)
- Delete: `docs/foundations/theory/05-science-ontology.md` (replaced by `04-reasoning-strategies.md`)
- Delete: `docs/foundations/theory/06-science-formalization.md` (replaced by `05-formalization-methodology.md`)
- Archive: Move deleted files to `docs/archive/foundations-v3/theory/`

- [ ] **Step 1: Create archive directory and move old files**

```bash
mkdir -p docs/archive/foundations-v3/theory
git mv docs/foundations/theory/01a-jaynes-maxent-grounding.md docs/archive/foundations-v3/theory/
git mv docs/foundations/theory/02-reasoning-factor-graph.md docs/archive/foundations-v3/theory/
git mv docs/foundations/theory/03-coarse-reasoning.md docs/archive/foundations-v3/theory/
git mv docs/foundations/theory/04-belief-propagation.md docs/archive/foundations-v3/theory/
git mv docs/foundations/theory/05-science-ontology.md docs/archive/foundations-v3/theory/
git mv docs/foundations/theory/06-science-formalization.md docs/archive/foundations-v3/theory/
```

- [ ] **Step 2: Commit archive**

```bash
git add docs/archive/foundations-v3/theory/
git commit -m "docs: archive old theory/ documents to foundations-v3"
```

### Task 9: Update docs/foundations/README.md

**Files:**
- Modify: `docs/foundations/README.md`

- [ ] **Step 1: Read current README**

Read `docs/foundations/README.md`.

- [ ] **Step 2: Update theory section**

Replace the current theory derivation chain and document list with:

```markdown
### theory/ — 理论基础

**三层结构：**

**Layer 1 — Jaynes 理论（纯理论，不涉及因子图/BP）：**
- `01-plausible-reasoning.md` — Cox 定理、概率唯一性、弱三段论
- `02-maxent-grounding.md` — MaxEnt/Min-KL、从约束到后验

**Layer 2 — 科学本体论（命题与算子，不涉及因子图/BP）：**
- `03-propositional-operators.md` — 最小原料 {¬, ∧, π}、派生算子、↝ 似然蕴含、完备性
- `04-reasoning-strategies.md` — 知识类型、七种推理策略作为 ↝ 微观结构
- `05-formalization-methodology.md` — 从科学文本到命题网络的方法论

**Layer 3 — 计算方法（因子图 + BP 作为大规模近似）：**
- `06-factor-graphs.md` — 命题网络到因子图的映射、势函数
- `07-belief-propagation.md` — BP 近似推理算法
```

- [ ] **Step 3: Commit**

```bash
git add docs/foundations/README.md
git commit -m "docs: update foundations README with new theory/ structure"
```

### Task 10: Update downstream references in docs/foundations/

**Files to modify:**
- `docs/foundations/bp/potentials.md` — lines referencing `03-coarse-reasoning.md`, `04-belief-propagation.md`
- `docs/foundations/bp/inference.md` — line referencing `04-belief-propagation.md`
- `docs/foundations/gaia-lang/spec.md` — lines referencing `05-science-ontology.md`, `03-coarse-reasoning.md`, `06-science-formalization.md`
- `docs/foundations/gaia-lang/knowledge-types.md` — lines referencing `05-science-ontology.md`, `03-coarse-reasoning.md`, `06-science-formalization.md`
- `docs/foundations/gaia-lang/package-model.md` — line referencing `03-coarse-reasoning.md`
- `docs/foundations/rationale/domain-vocabulary.md` — line referencing `04-belief-propagation.md`
- `docs/foundations/rationale/architecture-overview.md` — line referencing `01-plausible-reasoning.md` (unchanged filename, but verify)
- `docs/foundations/rationale/product-scope.md` — line referencing `05-science-ontology.md`
- `docs/foundations/graph-ir/overview.md` — lines referencing `02-reasoning-factor-graph.md`, `05-science-ontology.md`
- `docs/foundations/graph-ir/graph-ir.md` — lines referencing `02-reasoning-factor-graph.md`, `05-science-ontology.md`
- `docs/documentation-policy.md` — line 112 referencing `theory/02-reasoning-factor-graph.md`

**Reference mapping:**
| Old filename | New filename |
|---|---|
| `01a-jaynes-maxent-grounding.md` | `02-maxent-grounding.md` |
| `02-reasoning-factor-graph.md` | `03-propositional-operators.md` (for theory) or `06-factor-graphs.md` (for computation) |
| `03-coarse-reasoning.md` | `03-propositional-operators.md §4` |
| `04-belief-propagation.md` | `07-belief-propagation.md` |
| `05-science-ontology.md` | `04-reasoning-strategies.md` |
| `06-science-formalization.md` | `05-formalization-methodology.md` |

Additionally replace terminology in downstream files:
| Old term | New term |
|---|---|
| "合取语义" (when referring to noisy-AND) | "∧ + ↝ 语义" or "合取 + 似然蕴含" |
| "粗因子图" | "粗命题网络" |
| "细因子图" | "细命题网络" |
| "粗推理算子" | "↝ (似然蕴含)" |

**Important:** `docs/foundations/graph-ir/` files are PROTECTED — only update cross-reference paths, do NOT change content definitions. Verify each edit is reference-only.

- [ ] **Step 1: Read each downstream file**

Read all files listed above to identify exact lines to change.

- [ ] **Step 2: Update references in bp/ files**

Update `docs/foundations/bp/potentials.md` and `docs/foundations/bp/inference.md`.

- [ ] **Step 3: Update references in gaia-lang/ files**

Update `docs/foundations/gaia-lang/spec.md`, `knowledge-types.md`, `package-model.md`.

- [ ] **Step 4: Update references in rationale/ files**

Update `docs/foundations/rationale/domain-vocabulary.md`, `architecture-overview.md`, `product-scope.md`.

- [ ] **Step 5: Update references in graph-ir/ files (REFERENCE ONLY)**

Update `docs/foundations/graph-ir/overview.md` and `graph-ir.md` — ONLY change file path references, not content.

- [ ] **Step 6: Commit**

```bash
git add docs/foundations/bp/ docs/foundations/gaia-lang/ docs/foundations/rationale/ docs/foundations/graph-ir/ docs/documentation-policy.md
git commit -m "docs: update downstream references to new theory/ document structure"
```

### Task 11: Update references in docs/ideas/

**Files to modify:**
- `docs/ideas/case-analysis-strategy.md` — references to `02-reasoning-factor-graph.md`, `05-science-ontology.md`, `03-coarse-reasoning.md`
- `docs/ideas/elimination-strategy.md` — reference to `02-reasoning-factor-graph.md`
- `docs/ideas/template-mechanism.md` — references to `05-science-ontology.md`
- `docs/ideas/mathematical-induction.md` — references to `05-science-ontology.md`, `02-reasoning-factor-graph.md`, `03-coarse-reasoning.md`
- `docs/ideas/negation-relation.md` — references to `04-belief-propagation.md`, `02-reasoning-factor-graph.md`
- `docs/ideas/reductio-strategy.md` — reference to `06-science-formalization.md`

- [ ] **Step 1: Read each file and update references**

Apply same reference mapping as Task 10. These are idea documents so only filenames need updating, not terminology (ideas may reference factor graphs legitimately since they discuss implementation).

- [ ] **Step 2: Commit**

```bash
git add docs/ideas/
git commit -m "docs: update idea docs references to new theory/ filenames"
```

---

## Chunk 5: Validation

### Task 12: Full validation sweep

- [ ] **Step 1: Verify theory/ directory structure**

```bash
ls -la docs/foundations/theory/
```

Expected: exactly 7 files:
```
01-plausible-reasoning.md
02-maxent-grounding.md
03-propositional-operators.md
04-reasoning-strategies.md
05-formalization-methodology.md
06-factor-graphs.md
07-belief-propagation.md
```

- [ ] **Step 2: Verify no factor graph / BP leakage in Layer 1 + 2**

```bash
# Search docs 01-05 for factor graph terminology
grep -n "因子图\|factor graph\|势函数\|potential function\|BP算法\|belief propagation\|消息传递\|message passing" \
  docs/foundations/theory/01-plausible-reasoning.md \
  docs/foundations/theory/02-maxent-grounding.md \
  docs/foundations/theory/03-propositional-operators.md \
  docs/foundations/theory/04-reasoning-strategies.md \
  docs/foundations/theory/05-formalization-methodology.md
```

Expected: NO matches.

- [ ] **Step 3: Verify no stale references to old filenames**

```bash
# Search all foundations/ for old filenames (excluding archive/)
grep -rn "01a-jaynes-maxent\|02-reasoning-factor-graph\|03-coarse-reasoning\|04-belief-propagation\|05-science-ontology\|06-science-formalization" \
  docs/foundations/ --include="*.md" | grep -v "archive/"
```

Expected: NO matches (except possibly in this plan file itself or spec files).

- [ ] **Step 4: Verify derivation chain headers**

Check each of the 7 documents has a consistent derivation chain header block.

- [ ] **Step 5: Verify ↝ is properly introduced in doc 03**

Check doc 03 contains: definition table, (p₁,p₂) semantics, reducibility statement, completeness argument, relationship to old single-parameter model.

- [ ] **Step 6: Verify Bayes derivations in doc 04**

Check doc 04 contains Bayes derivations for all 7 strategies with explicit effective (p₁, p₂).

- [ ] **Step 7: Verify abduction direction**

```bash
grep -n "abduction\|溯因\|Abduction" \
  docs/foundations/theory/04-reasoning-strategies.md \
  docs/foundations/theory/05-formalization-methodology.md
```

Check all instances use "Observation ↝ Hypothesis" direction.

- [ ] **Step 8: Run ruff checks (no code changes, but verify docs don't break anything)**

```bash
ruff check .
ruff format --check .
```

- [ ] **Step 9: Final commit if any fixes needed**

```bash
git add -A
git commit -m "docs: validation fixes for theory restructuring"
```
