# Jaynes 概率逻辑后端 Foundation Spec

**文档状态**：Foundation Design Spec  
**适用范围**：面向 Gaia / Scientific Formal Language 的概率语义、evidence contract、BeliefContext、BeliefState 与推理后端设计  
**建议文件名**：`docs/foundations/jaynes-probability-logic-backend.md`  
**核心不变量**：概率不是命题的孤立属性，而是在信息状态 `I` 下对命题 `A` 的合理可信度：`P(A | I)`。

---

## 1. 文档目标

本文档定义 Jaynes 风格概率逻辑后端的基础设计。它的目标不是实现一个普通 Bayesian statistics library，而是为科学形式化语言提供一个统一语义层，用来表达：

```text
在什么信息状态下，某个科学命题有多可信？
新证据如何更新这个可信度？
先验从何而来？
模型如何比较？
推理结果如何复现和审查？
```

核心形式：

```text
P(Proposition | InformationContext)
```

也就是：

```text
P(A | I)
```

其中：

```text
A = 命题
I = 背景信息、定义、假设、模型、先验、观测、证据、review 状态、依赖上下文
```

---

## 2. 核心设计原则

### 2.1 所有概率都必须条件化

不推荐：

```text
P(H) = 0.8
```

推荐：

```text
P(H | I0) = 0.8
P(H | I0 + D) = 0.93
```

系统可以提供默认 context，但内部语义必须总是 context-indexed。

### 2.2 概率作用于命题

概率的基本对象不是随机变量表，而是命题：

```text
H := Drug_A reduces blood pressure by at least 5 mmHg
P(H | I)
```

随机变量和分布只是命题族的简写：

```text
P(θ ∈ [a,b] | I)
```

### 2.3 信息状态是一等对象

`InformationContext` 不应只是隐式参数。它必须可序列化、可 hash、可 diff、可复现。

```text
context_id = hash(IR + priors + evidence + review state + dependencies + inference config)
```

### 2.4 Evidence 通过 likelihood 更新 hypothesis

科学证据不应表达为：

```text
support_prior = 0.8
```

而应表达为：

```text
P(E | H, I)
P(E | ¬H, I)
```

当 `E` 被观察到时：

```text
posterior_odds(H | E,I) = prior_odds(H | I) × P(E|H,I) / P(E|¬H,I)
```

### 2.5 Review gating 不是概率

Review 状态决定某个 action/factor 是否进入信息状态 `I`，但不应变成 numeric prior。

```text
accepted   -> factor active
unreviewed -> factor inactive by default
rejected   -> factor inactive
```

不允许：

```text
accepted -> P=0.99
rejected -> P=0.01
```

### 2.6 0 和 1 只留给逻辑必然或不可能

Jaynes 风格下，不应随便设置：

```text
P(H | I) = 0
P(H | I) = 1
```

除非：

```text
I entails H
I entails not H
```

否则应使用 Cromwell epsilon 进行截断，防止未来证据无法更新。

---

## 3. 范围与非目标

### 3.1 范围

本文档覆盖：

```text
Proposition semantics
InformationContext
Bayes update
Likelihood evidence
MaxEnt priors
Model comparison
Prediction
Measurement likelihood
Inference IR
BeliefState
Diagnostics and audit
Gaia mapping
```

### 3.2 非目标

本文档不要求一次性实现：

```text
完整连续概率编程语言
完整因果推理系统
自动先验生成器
全自动模型发现
所有统计检验到 Bayes factor 的自动转换
完整 Markov Logic / PSL / PPL 兼容层
```

MVP 应聚焦：

```text
binary claim graph
likelihood evidence
review-gated information context
context-indexed belief output
```

---

## 4. 核心对象模型

### 4.1 Proposition

命题是可以为真或假的表达式。

```text
Proposition :=
  Atom(predicate, terms)
  Equality(term, term)
  Inequality(term, term)
  Not(Proposition)
  And(Proposition, Proposition)
  Or(Proposition, Proposition)
  Implies(Proposition, Proposition)
  Forall(variable, type, Proposition)
  Exists(variable, type, Proposition)
```

在 Gaia MVP 中，命题主要通过 `Claim` 表示。

### 4.2 Claim

`Claim` 是具有身份、prior、metadata 和 review 依赖的 proposition wrapper。

```text
Claim:
  id
  proposition
  prior optional
  label optional
  grounding optional
  parameters optional
  provenance optional
```

在概率后端中：

```text
Claim -> binary belief variable
```

### 4.3 InformationContext

```text
InformationContext:
  id
  claims
  accepted_actions
  observations
  evidence_factors
  priors
  models
  assumptions
  review_state
  dependency_contexts
  inference_config
```

上下文可以递增更新：

```text
I1 = I0 + Observation_1
I2 = I1 + EvidenceFactor_2
```

### 4.4 ProbabilityExpression

```text
ProbabilityExpression:
  proposition
  context
  result_type: probability | density | distribution | evidence | expectation
```

例子：

```text
P(H | I)
P(θ ∈ [a,b] | I)
E[X | I]
P(D | M, I)
BayesFactor(M1, M2 | D, I)
```

### 4.5 EvidenceFactor

```text
EvidenceFactor:
  hypothesis
  evidence
  P(E | H)
  P(E | not H)
  observed_status
  source_id
  independence_group
  assumptions
  model_id
```

MVP 对应 Gaia `InferAction`。

### 4.6 BeliefState

```text
BeliefState:
  context_id
  beliefs
  diagnostics
  inference_method
  exactness
  generated_at
```

每个 belief 应理解为：

```text
P(claim | context_id)
```

---

## 5. Jaynes / Cox 概率演算内核

### 5.1 加法规则

```text
P(A | I) + P(not A | I) = 1
```

一般情况：

```text
P(A or B | I) = P(A | I) + P(B | I) - P(A and B | I)
```

互斥时：

```text
P(A or B | I) = P(A | I) + P(B | I)
```

### 5.2 乘法规则

```text
P(A and B | I) = P(A | B,I) P(B | I)
```

也可写成：

```text
P(A,B | I) = P(A | B,I) P(B | I)
```

### 5.3 Bayes 更新

```text
P(H | D,I) = P(D | H,I) P(H | I) / P(D | I)
```

其中：

```text
P(D | I) = P(D | H,I)P(H|I) + P(D | not H,I)P(not H|I)
```

### 5.4 Odds 形式

```text
PosteriorOdds(H | D,I)
= PriorOdds(H | I) × LikelihoodRatio(D | H, not H, I)
```

其中：

```text
LikelihoodRatio = P(D | H,I) / P(D | not H,I)
```

这是 evidence contract 的核心。

---

## 6. 信息状态设计

### 6.1 Context contents

`InformationContext` 应包含：

```text
definitions
accepted assumptions
claim priors
accepted observation actions
accepted likelihood evidence factors
accepted logical operators
dependency belief states
prior resolution policy
inference config
```

### 6.2 Context hash

`context_id` 必须由 canonical JSON hash 得出，至少包含：

```text
IR hash
review manifest hash
accepted target IDs
prior source hash
dependency context IDs
active evidence IDs
observed claim IDs
inference config
```

### 6.3 Context diff

系统应支持：

```text
gaia diff-context ctx1 ctx2
```

至少报告：

```text
changed priors
changed review status
added/removed evidence
changed dependencies
changed inference method
```

---

## 7. Priors 与 MaxEnt

### 7.1 Prior 必须有依据

不推荐：

```text
prior θ = uniform
```

推荐：

```text
prior θ:
  distribution: Uniform(0, 10)
  measure: dθ
  justification: symmetry over θ within known support
```

### 7.2 MaxEnt 原则

在只知道约束时，选择不引入额外信息的分布。

离散形式：

```text
p* = argmax_p -Σ p_i log p_i
subject to constraints
```

连续形式应使用相对熵：

```text
p* = argmax_p -∫ p(x) log(p(x)/q(x)) dx
```

其中 `q(x)` 是 reference measure / base distribution。

### 7.3 MaxEnt 输出

若约束为：

```text
E[f_k(X)] = c_k
```

则通常得到：

```text
p(x) ∝ q(x) exp(Σ λ_k f_k(x))
```

### 7.4 先验警告

系统应警告：

```text
[ ] uniform prior 缺少 support
[ ] uniform prior 缺少 measure
[ ] continuous prior 缺少 parameterization
[ ] prior = 0/1 但非逻辑必然
[ ] prior source unknown
```

---

## 8. Evidence / likelihood 语义

### 8.1 Evidence 不等于 claim true

声明 likelihood：

```text
P(E | H) = 0.95
P(E | not H) = 0.10
```

并不表示 `E` 已被观察到。

只有当 `E` 被观察并进入 context：

```text
Observe(E) accepted
```

才会更新 `H`。

### 8.2 Binary evidence factor

MVP factor：

```text
H: binary claim
E: binary evidence claim
φ(E,H) = P(E | H)
```

CPT：

```text
P(E=true | H=false) = p_e_given_not_h
P(E=true | H=true)  = p_e_given_h
```

### 8.3 Likelihood ratio helper

如果用户提供 LR：

```text
LR = P(E|H) / P(E|not H)
```

可以编译为兼容 CPT：

```text
P(E|H)     = LR / (1 + LR)
P(E|notH)  = 1 / (1 + LR)
```

但 metadata 必须保留原始 LR。

### 8.4 Bayes factor helper

对 binary hypothesis，Bayes factor 可视为 likelihood ratio：

```text
BF(H:notH) = P(D|H) / P(D|notH)
```

### 8.5 Independence group

每个 evidence factor 应可声明：

```text
independence_group
source_id
data_id
```

系统应警告重复计数：

```text
multiple active evidence factors share independence_group
```

---

## 9. 测量 likelihood

### 9.1 测量模型

```text
Observed = TrueValue + Error
Error ~ Normal(0, σ)
```

若 hypothesis 是：

```text
H := TrueValue > threshold
```

measurement evidence 可以编译成：

```text
P(observed_value | H)
P(observed_value | not H)
```

短期可通过 adapter 输出 LR / BF。

### 9.2 Continuous value 注意事项

不应写：

```text
P(θ = 1.0 | I)
```

应写：

```text
P(θ ∈ [0.99,1.01] | I)
density(θ=1.0 | I)
```

### 9.3 概率密度单位

若 `X: Length`，则：

```text
p_X(x): 1 / Length
```

后端应区分 probability 与 density。

---

## 10. 模型比较

### 10.1 Posterior model probability

```text
P(M | D,I) = P(D | M,I) P(M | I) / P(D | I)
```

### 10.2 Marginal likelihood

```text
P(D | M,I) = ∫ P(D | θ,M,I) P(θ | M,I) dθ
```

### 10.3 Bayes factor

```text
BF(M1:M2) = P(D | M1,I) / P(D | M2,I)
```

### 10.4 Occam factor

复杂模型只有在提高预测解释能力时才应得到更高 marginal likelihood。Jaynes 后端应避免只用 maximum likelihood 做模型比较。

---

## 11. 预测分布

科学模型的重要用途是预测，而不是只估计参数。

```text
P(new_data | old_data, I)
= ∫ P(new_data | θ,I) P(θ | old_data,I) dθ
```

语言应支持：

```text
predictive(target | context)
posterior_predictive_check(model, data, context)
```

MVP 可先不实现完整 continuous predictive，但应在 IR 中预留对象。

---

## 12. 与硬逻辑的接口

如果逻辑层能推出：

```text
I entails A
```

则：

```text
P(A | I) = 1
```

如果：

```text
I entails not A
```

则：

```text
P(A | I) = 0
```

否则系统不应把经验命题设为 0 或 1。

---

## 13. 条件独立与因子分解

### 13.1 显式声明独立性

不应自动假设：

```text
P(D1,D2 | H) = P(D1|H)P(D2|H)
```

需要声明：

```text
D1 independent_of D2 given H under I
```

### 13.2 Evidence groups

短期实践中，用 `independence_group` 防止最明显重复计数。

```text
evidence_1.independence_group = trial_001.primary_endpoint
evidence_2.independence_group = trial_001.primary_endpoint
```

系统警告这两个 evidence 可能不是独立证据。

---

## 14. Inference IR

推荐 IR：

```text
ProbabilisticIR:
  claims
  priors
  operators
  evidence_factors
  observations
  review_state
  contexts
  queries
```

Evidence factor：

```json
{
  "type": "infer",
  "hypothesis": "claim:H",
  "evidence": "claim:E",
  "conditional_probabilities": [0.10, 0.95],
  "metadata": {
    "evidence": {
      "schema_version": "gaia.evidence.v1",
      "evidence_kind": "raw_likelihood",
      "p_e_given_h": 0.95,
      "p_e_given_not_h": 0.10,
      "source_id": "lab:test_T",
      "independence_group": "patient_001.test_T"
    }
  }
}
```

---

## 15. 编译与 lowering 流程

```text
Gaia Lang DSL
  -> runtime objects
  -> compile actions to IR
  -> normalize EvidenceMetadata
  -> generate ReviewManifest
  -> select accepted actions
  -> build BeliefContext
  -> lower to factor graph
  -> run inference engine
  -> emit BeliefState
```

关键规则：

```text
InferAction -> likelihood factor
ObserveAction accepted -> evidence claim pinned true with Cromwell clamp
Unreviewed action -> excluded from context
Rejected action -> excluded from context
```

---

## 16. 推理后端

后端可以有多种：

```text
exact enumeration
junction tree
loopy belief propagation
generalized belief propagation
factor graph message passing
external PPL adapter
```

语义不应依赖具体算法。算法只影响计算近似和 diagnostics。

输出必须包含：

```text
method_used
is_exact
treewidth optional
elapsed_ms
diagnostics
```

---

## 17. Diagnostics / Explain / Audit

### 17.1 Explain

```text
gaia explain <claim>
```

应显示：

```text
P(claim | context_id)
prior
direct evidence factors
P(E|H), P(E|notH), LR
observed status
review status
source_id
inference method
exactness
```

### 17.2 Sensitivity

未来支持：

```text
prior perturbation
disable evidence group
disable review target
compare exact vs approximate
```

### 17.3 Audit

应检查：

```text
duplicate independence_group
missing source_id
missing context_id
unobserved evidence incorrectly updating posterior
review status used as probability
```

---

## 18. Gaia v0.6 映射

当前 Gaia 可以按以下方式落地：

```text
Claim                  -> binary proposition variable
InferAction             -> likelihood factor P(E|H)
ObserveAction            -> evidence enters context
ReviewManifest           -> qualitative gate
BeliefContext            -> information state I
BeliefState              -> posterior P(Claim | I)
InferenceEngine          -> computational backend
```

核心 v0.6 invariant：

```text
Declaring likelihood does not observe evidence.
Only accepted Observe actions place evidence into the context.
```

---

## 19. API 草案

### 19.1 Raw likelihood

```python
likelihood(
    evidence=test_positive,
    hypothesis=disease,
    p_e_given_h=0.95,
    p_e_given_not_h=0.10,
    observed=True,
    source_id="lab:test_T",
    independence_group="patient_001.test_T",
)
```

### 19.2 Likelihood ratio

```python
likelihood_ratio(
    evidence=experiment_result,
    hypothesis=mechanism_present,
    lr=12.4,
    observed=True,
)
```

### 19.3 Bayes factor

```python
bayes_factor(
    evidence=data_D,
    hypothesis=model_M1_better_than_M0,
    bf=8.7,
    observed=True,
)
```

### 19.4 Query

```text
query P(disease | context_id)
```

---

## 20. Acceptance checklist

基础后端被认为可用时，应满足：

```text
[ ] 所有 belief 输出都有 context_id
[ ] InferAction 表示 P(E|H)，不表示 P(H|E)
[ ] 未观测 evidence 不更新 hypothesis
[ ] accepted Observe 才把 evidence 放入 context
[ ] review status 不被当成概率
[ ] LR/BF metadata 保留原始值
[ ] posterior odds 与 LR/BF 计算一致
[ ] priors 被 Cromwell clamp
[ ] duplicate independence_group 发出警告
[ ] BeliefState 包含 method/exactness/diagnostics
[ ] context_id 对 IR/review/prior/evidence 变化敏感
```

---

## 21. 路线图

```text
Phase 1: binary likelihood evidence
Phase 2: evidence adapters: binomial, two-binomial, Gaussian measurement, Bayes factor
Phase 3: context reproducibility and diff
Phase 4: quantity-aware measurement likelihoods
Phase 5: model comparison and posterior predictive checks
Phase 6: hybrid continuous/discrete factor graph
Phase 7: causal do-operator layer
```

---

## 22. 推荐参考方向

这些是理论背景，不是实现依赖：

```text
E. T. Jaynes, Probability Theory: The Logic of Science
R. T. Cox, The Algebra of Probable Inference
Claude Shannon, A Mathematical Theory of Communication
David MacKay, Information Theory, Inference, and Learning Algorithms
Judea Pearl, Causality
Factor graphs, Bayesian networks, probabilistic programming systems
```

---

## 23. One-line invariant

```text
A Jaynesian backend evaluates the plausibility of propositions under explicit information contexts; evidence updates beliefs through likelihoods, and every posterior is P(Claim | Context), never a context-free confidence score.
```
