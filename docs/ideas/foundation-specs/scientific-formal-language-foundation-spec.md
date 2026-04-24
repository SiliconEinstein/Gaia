# 科学形式化语言 Foundation Spec

**文档状态**：Foundation Design Spec  
**适用范围**：面向 Gaia / Scientific Formal Language 的长期语言内核、IR、编译器与科学知识包设计  
**建议文件名**：`docs/foundations/scientific-formal-language.md`  
**核心不变量**：科学形式化语言不仅要表达公式，还要表达公式在什么条件下成立、由什么证据支持、如何测量、如何近似、如何复现、如何被推翻。

---

## 1. 文档目标

本文档定义一门科学形式化语言的基础设计。它不是某个具体实现版本的 API 文档，而是面向长期演化的 foundation spec，用来约束后续 Gaia Lang、Gaia IR、科学知识包、概率后端、实验后端和审查工作流。

这门语言的目标不是替代数学、LaTeX、Python、Lean、R 或实验记录系统，而是把它们连接起来，让科学知识具备以下性质：

1. **可表达**：能表达对象、属性、关系、过程、模型、实验、数据、假设、适用范围和证据。
2. **可检查**：能检查类型、量纲、单位、作用域、定义、前提和模型适用条件。
3. **可计算**：能把部分模型 lower 到数值仿真、符号推导、概率推理或验证工具。
4. **可审查**：每个 claim、support、measurement、inference 都能追踪来源、状态和依赖。
5. **可更新**：科学结论不是一次性真理，而是在信息状态变化时可被更新的命题。

一句话目标：

```text
A language for representing scientific claims, models, measurements, evidence, and inference under explicit assumptions and contexts.
```

---

## 2. 设计原则

### 2.1 区分真实对象、模型对象与观测对象

科学表达中最常见的错误是把三种东西混在一起：

```text
RealObject       真实世界中的对象
ModelObject      模型中的理想化对象
Observation      某次实验或仪器给出的观测记录
```

例如：

```text
Earth                         # 真实对象
Earth_in_NewtonianModel        # 模型对象
Observation_2026_04_23_mass    # 一次观测或估计记录
```

语言必须允许分别表达：

```text
Mass(Earth)                                # 真实属性，通常未知
Mass(Earth_in_NewtonianModel) = 1 unit      # 模型内归一化参数
ObservedMass(obs_1) = 5.972e24 kg           # 观测结果
```

### 2.2 每个数量都应有量纲和单位

科学语言中不应允许：

```text
3 kg + 5 seconds
Temperature = red
Force = 10 meters
```

最低要求是实现：

```text
Quantity
Dimension
Unit
UnitSystem
UnitConversion
DimensionalCheck
```

### 2.3 每个模型都必须声明假设和适用范围

科学模型不是无条件真理。模型应至少包含：

```text
assumptions
validity_range
scale
boundary_conditions
initial_conditions
failure_conditions
approximation_level
```

例如：

```text
model NewtonianMechanics:
  assumptions:
    velocity << speed_of_light
    gravitational_field is weak
    quantum_effects are negligible
```

### 2.4 测量不是事实，而是带误差模型的证据

测得 `10.4 g` 不等于真实质量就是 `10.4 g`。正确表达应为：

```text
ObservedMass = TrueMass + MeasurementError
MeasurementError ~ ErrorModel
```

语言必须支持：

```text
instrument
calibration
resolution
random_error
systematic_error
uncertainty
confidence_or_credible_interval
measurement_protocol
```

### 2.5 定义、假设、经验命题和定律必须分开

以下对象语义不同：

```text
Definition        约定或定义，如 BMI = mass / height^2
Assumption        当前上下文中暂时接受的前提
EmpiricalClaim    基于数据的经验命题
Law               理论内部或经验归纳的规律
Model             带参数、方程、条件和误差结构的表示
Theorem           在形式系统内可证明的命题
Observation       观测记录
Evidence          用于更新命题可信度的数据或事实
```

混淆这些类别会导致系统无法解释为什么某个结论成立。

### 2.6 概率与不确定性必须条件化到信息状态

语言可以支持概率，但不应鼓励裸概率：

```text
P(H) = 0.8     # 不推荐
```

应写成：

```text
P(H | Context_I) = 0.8
```

概率层属于独立后端，但基础语言必须为其预留：

```text
Proposition
InformationContext
Evidence
Likelihood
Prior
Posterior
BeliefState
```

---

## 3. 范围与非目标

### 3.1 范围

本文档覆盖：

```text
Core objects
Type system
Quantity and unit system
Logical propositions
Scientific models
Measurements
Experiments
Evidence and provenance
Uncertainty hooks
IR and compiler layers
Validation and audit
Gaia mapping
```

### 3.2 非目标

本文档不要求一次性实现：

```text
完整一阶逻辑证明器
完整连续概率编程语言
完整自然语言 parser
全自动科学发现系统
所有科学领域的本体库
与所有数据格式的完整互操作
```

MVP 应优先稳定：

```text
typed claims
actions
contexts
measurements
units
model assumptions
evidence/provenance hooks
```

---

## 4. 分层架构

推荐架构：

```text
Scientific Formal Language
│
├── Surface Language Layer
│   ├── Python internal DSL
│   ├── controlled natural language
│   └── domain-specific syntax sugar
│
├── Core Semantic Layer
│   ├── entity
│   ├── type
│   ├── proposition
│   ├── definition
│   ├── context
│   └── action
│
├── Mathematical Layer
│   ├── expressions
│   ├── equations
│   ├── functions
│   ├── calculus
│   ├── probability hooks
│   └── optimization hooks
│
├── Scientific Quantity Layer
│   ├── dimensions
│   ├── units
│   ├── constants
│   ├── uncertainty
│   └── measurement models
│
├── Model Layer
│   ├── assumptions
│   ├── parameters
│   ├── equations
│   ├── validity ranges
│   ├── residual models
│   └── simulations
│
├── Empirical Layer
│   ├── observations
│   ├── datasets
│   ├── experiments
│   ├── instruments
│   └── protocols
│
├── Evidence and Review Layer
│   ├── provenance
│   ├── evidence factors
│   ├── review status
│   ├── conflict tracking
│   └── audit trails
│
├── IR Layer
│   ├── normalized claims
│   ├── operators
│   ├── actions
│   ├── contexts
│   └── lowering contracts
│
└── Backend Layer
    ├── probabilistic inference
    ├── symbolic math
    ├── numerical simulation
    ├── theorem proving
    └── data validation
```

核心原则：**表层语言可以友好，核心语义必须严格。**

---

## 5. 核心对象模型

### 5.1 Entity

`Entity` 表示可被谈论的对象。

```text
Entity:
  id
  type
  label
  metadata
```

例子：

```text
entity Earth : Planet
entity sample_A : SoilSample
entity Trial_001 : Experiment
```

### 5.2 Type

`Type` 表示分类和约束。

```text
Type:
  name
  parent_types
  constraints
  metadata
```

例子：

```text
Particle
Body
Sample
Dataset
Experiment
Model
Quantity[Mass]
Quantity[Temperature]
```

### 5.3 Quantity

`Quantity` 表示带量纲的物理或科学量。

```text
Quantity:
  value
  unit
  dimension
  uncertainty optional
```

例子：

```text
5.0 kg
298.15 K
9.8 m/s^2
```

### 5.4 Proposition

`Proposition` 表示可以为真或假的命题。

```text
Proposition :=
  Predicate(terms)
  Equality(term, term)
  Inequality(term, term)
  Not(Proposition)
  And(Proposition, Proposition)
  Or(Proposition, Proposition)
  Implies(Proposition, Proposition)
  Forall(variable, type, Proposition)
  Exists(variable, type, Proposition)
```

例子：

```text
Mass(sample_A) > 10 g
Drug_A reduces BloodPressure
ModelAdequate(SIR_Model, Dataset_D)
```

### 5.5 Claim

`Claim` 是带身份、可审查、可进入推理图的命题对象。

```text
Claim:
  id
  proposition
  prior optional
  grounding optional
  parameters optional
  provenance optional
  review_status optional
```

在 Gaia 中，`Claim` 应是 belief variable 的主入口。

### 5.6 Definition

`Definition` 表示约定性等式或构造规则。

```text
definition BMI(person):
  BMI(person) = Mass(person) / Height(person)^2
```

定义不是经验发现，不应被 evidence 更新。

### 5.7 Model

`Model` 表示科学模型。

```text
Model:
  parameters
  equations
  assumptions
  initial_conditions
  boundary_conditions
  validity_conditions
  residual_model optional
```

### 5.8 Observation

`Observation` 表示实际观测或测量记录。

```text
Observation:
  target
  observed_value
  uncertainty
  instrument
  protocol
  timestamp
  provenance
```

### 5.9 Experiment

`Experiment` 表示一组有设计目的的观测。

```text
Experiment:
  hypothesis
  population
  intervention
  control
  randomization
  blinding
  outcome
  protocol
  dataset
```

### 5.10 InformationContext

`InformationContext` 表示一组背景信息。

```text
InformationContext:
  definitions
  assumptions
  claims
  observations
  models
  priors
  evidence
  review_state
  dependency_contexts
```

概率和推理应总是相对于某个 context。

---

## 6. 类型系统与量纲系统

### 6.1 类型系统目标

类型系统应至少实现：

```text
entity type checking
quantity type checking
function signature checking
operator compatibility checking
unit conversion checking
proposition well-formedness checking
```

### 6.2 量纲代数

基础量纲：

```text
Length
Mass
Time
Temperature
Amount
Current
Luminosity
Information optional
```

派生量纲：

```text
Velocity = Length / Time
Acceleration = Length / Time^2
Force = Mass * Length / Time^2
Energy = Mass * Length^2 / Time^2
Pressure = Mass / (Length * Time^2)
```

### 6.3 单位转换

语言应区分：

```text
unit representation
unit conversion
dimension equivalence
```

例如：

```text
1 N = 1 kg*m/s^2
1 J = 1 N*m
```

### 6.4 密度单位

概率无量纲，但概率密度有单位。

```text
X: Length
p_X(x): 1 / Length
```

因此，概率后端必须能识别：

```text
P(X in [1m, 2m])      # probability
p_X(1.5m)             # density, unit 1/m
```

---

## 7. 逻辑层设计

### 7.1 逻辑连接词

支持：

```text
not
and
or
implies
equivalent
contradicts
exclusive
forall
exists
```

### 7.2 Operator 与 Claim 分离

关系操作符不应自动等同于事实本身。

```text
contradicts(A, B)
```

可以表示一个关系声明，也可以表示一个已接受的逻辑约束。推荐方式：

```text
RelationClaim R: A contradicts B under scope S
Operator: if R is active, enforce contradiction(A, B)
```

这样可以处理科学中常见的“表面矛盾”：不同定义、不同尺度、不同实验条件、不同单位或不同模型域。

### 7.3 硬逻辑与软证据

语言应区分：

```text
hard entailment       逻辑或定义上必然
soft support          科学上提供支持，但非必然
evidence likelihood   数据通过似然更新命题
```

---

## 8. 模型语义

### 8.1 精确模型

精确模型把方程当作约束。

```text
model ExactSpring:
  F = -k*x
```

语义：

```text
P(F = -k*x | Model, assumptions) = 1
```

仅适用于定义、理想模型或严格理论内部推导。

### 8.2 近似模型

科学应用中更常见的是近似模型。

```text
model SpringApprox:
  F = -k*x + ε
  ε ~ Normal(0, σ_model)
```

语义：

```text
ObservedForce is likely near -k*x under model assumptions.
```

### 8.3 适用范围

模型应声明：

```text
valid_for
invalid_for
scale
precision
boundary_conditions
initial_conditions
```

例如：

```text
model IdealGas:
  equation: P*V = n*R*T
  validity:
    low_pressure
    high_temperature
  failure_conditions:
    near_phase_transition
    high_density
```

---

## 9. 测量语义

### 9.1 True quantity 与 observed quantity

推荐区分：

```text
TrueMass(sample_A)
ObservedMass(measurement_m1)
```

一次测量：

```text
measurement m1:
  target: TrueMass(sample_A)
  observed_value: 10.4 g
  error_model: Normal(0 g, 0.2 g)
```

编译成：

```text
ObservedMass_m1 = TrueMass(sample_A) + ε
ε ~ Normal(0 g, 0.2 g)
```

### 9.2 仪器与校准

测量应支持：

```text
instrument_id
calibration_id
resolution
operator
protocol
environmental_conditions
```

### 9.3 系统误差

系统误差不应被隐藏在随机误差中：

```text
Observed = True + Bias + RandomError
Bias unknown or calibrated
```

---

## 10. 证据与来源

### 10.1 Provenance

每个 claim、model、observation、evidence factor 应能携带：

```text
source_id
author
created_at
version
method
dataset_id
instrument_id
license
review_status
```

### 10.2 Evidence

证据不是“置信度字段”。证据应说明：

```text
what was observed
which claim it updates
under which model
with what likelihood
under which assumptions
```

示例：

```text
EvidenceFactor:
  target: DiseasePresent(patient)
  data: TestPositive(patient)
  model: DiagnosticTestModel
  P(data | target) = sensitivity
  P(data | not target) = false_positive_rate
```

### 10.3 冲突证据

系统必须允许：

```text
evidence supports H
evidence contradicts H
evidence is inconclusive about H
models disagree
claims conflict under context
```

科学知识库不应假设全局无矛盾。

---

## 11. 实验与数据协议

### 11.1 Experiment object

```text
experiment Trial_001:
  hypothesis: Drug_A reduces SBP
  population: AdultsWithHypertension
  randomization: true
  blind: double
  treatment: Drug_A
  control: placebo
  outcome: SystolicBloodPressure
  duration: 12 weeks
  dataset: Trial_001_Data
```

### 11.2 Dataset object

```text
Dataset:
  schema
  rows
  variables
  units
  missingness
  inclusion_criteria
  exclusion_criteria
  preprocessing
  provenance
```

### 11.3 Analysis object

```text
Analysis:
  dataset
  model
  assumptions
  estimand
  method
  result
  diagnostics
```

---

## 12. Surface language 与 Core IR

### 12.1 表层语言

表层语言可以采用 Python internal DSL：

```python
class TemperatureAbove(Claim):
    """Temperature of {sample} is above {threshold}."""
    sample: Sample
    threshold: Quantity
```

### 12.2 核心 IR

核心 IR 应更严格：

```json
{
  "type": "Claim",
  "predicate": "TemperatureAbove",
  "parameters": {
    "sample": "sample_A",
    "threshold": {"value": 5000, "unit": "K"}
  }
}
```

### 12.3 编译流程

```text
Surface DSL
  -> AST / runtime objects
  -> type check
  -> unit check
  -> normalized propositions
  -> IR graph
  -> review manifest
  -> lowering to backend graph
  -> inference / validation / simulation
  -> BeliefState / Report
```

---

## 13. 与 Gaia 的映射

推荐映射：

```text
Scientific Claim          -> Gaia Claim
Definition                -> Derive / Compute / Operator
Observation               -> Observe action
Evidence likelihood       -> Infer action / EvidenceMetadata
Model assumption          -> Claim or Setting
Experiment                -> structured metadata / future object
InformationContext        -> BeliefContext
Posterior belief          -> BeliefState
Review state              -> ReviewManifest
```

Gaia 的核心方向应是：

```text
Claim-centered, action-backed, review-gated, context-indexed scientific reasoning.
```

---

## 14. 最小可行语言内核

MVP 应实现：

```text
1. Claim as belief variable
2. typed parameters
3. Quantity and Unit metadata
4. Observe action
5. Infer / likelihood evidence action
6. Derive / Compute action
7. Equal / Contradict / Exclusive operator
8. ReviewManifest gating
9. BeliefContext
10. BeliefState
11. Provenance metadata
12. unit and parameter validation
```

MVP 不必实现完整一阶逻辑，也不必实现完整概率编程。

---

## 15. 示例：力学模型

```text
module Mechanics

entity Body
quantity Mass(Body): Mass
quantity Position(Body, Time): Length
quantity Velocity(Body, Time): Length / Time
quantity Acceleration(Body, Time): Length / Time^2
quantity Force(Body, Time): Mass * Length / Time^2

definition Velocity(b, t):
  Velocity(b, t) = d(Position(b, t)) / dt

definition Acceleration(b, t):
  Acceleration(b, t) = d(Velocity(b, t)) / dt

model NewtonSecondLaw:
  equation: Force(b, t) = Mass(b) * Acceleration(b, t)
  assumptions:
    velocity(b,t) << speed_of_light
    quantum_effects_negligible(b)
```

测量：

```text
measurement m1:
  target: Force(cart_1, t0)
  observed_value: 9.81 N
  error_model: Normal(0 N, 0.05 N)
  instrument: force_sensor_01
```

查询：

```text
P(NewtonSecondLawAdequate(cart_1_experiment) | context_with_m1)
```

---

## 16. 验证与错误系统

语言应至少检查：

```text
[ ] 未声明单位的数量
[ ] 量纲不一致的加法/等式
[ ] 连续变量单点概率误用
[ ] 裸概率 P(A) 未指定 context
[ ] 模型无适用范围
[ ] measurement 被当成 true value
[ ] evidence 缺少 source_id
[ ] observed evidence 缺少 review status
[ ] relation operator 未说明 scope
[ ] repeated evidence 可能重复计数
```

---

## 17. 路线图

```text
Phase 1: Propositional scientific claims
Phase 2: Evidence and context contracts
Phase 3: Quantity / Unit / Measurement layer
Phase 4: Model and experiment objects
Phase 5: Cross-package scientific knowledge composition
Phase 6: Hybrid symbolic/probabilistic/numeric backends
Phase 7: Domain ontology libraries
```

---

## 18. Acceptance checklist

本 foundation spec 被实现时，应满足：

```text
[ ] Claim 可以结构化参数化
[ ] Quantity 带 unit / dimension
[ ] Observe 不等于 true fact，而是 observation record
[ ] Infer 表示 likelihood，不表示 posterior
[ ] Model 声明 assumptions / validity
[ ] Definition 与 empirical claim 分离
[ ] 每个 posterior 有 context_id
[ ] 每个 evidence 有 provenance
[ ] review status gate information, not probability
[ ] 输出 BeliefState 可复现
[ ] IR 与 backend 解耦
```

---

## 19. 推荐参考方向

这些不是实现依赖，而是理论背景：

```text
E. T. Jaynes, Probability Theory: The Logic of Science
R. T. Cox, The Algebra of Probable Inference
Claude Shannon, A Mathematical Theory of Communication
Judea Pearl, Causality
David MacKay, Information Theory, Inference, and Learning Algorithms
SBML / OWL / RDF / Lean / Coq / PPL ecosystems
```

---

## 20. One-line invariant

```text
A scientific formal language must represent not only what is claimed, but under what assumptions, measurements, models, evidence, units, contexts, and review states the claim is meaningful.
```
