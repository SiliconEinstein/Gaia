# Gaia IR — 结构定义

> **Status:** Target design — 基于 [theory](../theory/) 层设计，整合 Issue #231（template → claim with parameters）
>
> **⚠️ Protected Contract Layer** — 本目录定义 CLI↔LKM 结构契约。变更需要独立 PR 并经负责人审查批准。

Gaia IR 编码推理超图的拓扑结构——**什么连接什么**。它不包含任何概率值。

概率参数见 [06-parameterization.md](06-parameterization.md)。推理输出见 [../bp/belief-state.md](../bp/belief-state.md)。三者的关系见 [01-overview.md](01-overview.md)。backend-facing lowering 语义见 [07-lowering.md](07-lowering.md)。具体的概率推理算法见 [bp/](../bp/) 层。

Gaia IR 由三种实体构成：

| 实体 | 角色 | 语义 |
|------|------|------|
| **Knowledge** | 命题 | 表达科学断言、背景或问题 |
| **Operator** | 确定性逻辑约束 | 表达命题间的逻辑关系（真值表完全确定） |
| **Strategy** | 不确定推理声明 | 表达"前提以某种概率支持结论"的推理判断 |

读者先理解图中有什么节点（Knowledge），再理解节点之间的确定性结构关系（Operator），最后理解不确定的推理如何建模（Strategy）。完整的结构校验边界见 [08-validation.md](08-validation.md)。

---

## 1. Knowledge（知识）

Knowledge 表示命题。**Claim 是唯一携带概率（prior + belief）的类型。**

### 1.1 Schema

```
Knowledge:
    id:                     str | None       # QID 格式 `{namespace}:{package_name}::{label}`；可为 None（由 LocalCanonicalGraph 为本地节点自动分配）
    label:                  str | None       # graph 内唯一；id 和 label 至少提供一个
    type:                   str              # claim | setting | question
    content:                str | None       # 知识内容
    content_hash:           str | None       # SHA-256(type + content + sorted(parameters))，不含 package_id
    parameters:             list[Parameter]  # 全称命题的量化变量（封闭命题为空列表）
    metadata:               dict | None      # 含 refs: list[str]（相关 Knowledge IDs、来源引用等）

    # ── 来源追溯 ──
    provenance:             list[PackageRef] | None   # 贡献包列表
```

**对象身份**：`id` 使用 QID 格式 `{namespace}:{package_name}::{label}`，是 name-addressed identity。对**本地声明**且未显式给出 `id` 的 Knowledge，`namespace` 和 `package_name` 由所属 `LocalCanonicalGraph` 自动补齐。对**外部引用**的 Knowledge，则保留其原始 external QID。`label` 是该 graph 内的唯一句柄。不同包中相同内容的节点有**不同的** QID（不同 `package_name`）。

### 1.1.1 Local Ownership vs External References

`LocalCanonicalGraph` 的 local 属性约束的是：

- 哪个 package 拥有这份 graph
- 哪些未显式给出 `id` 的 Knowledge 需要自动分配本地 QID
- `ir_hash` 计算时覆盖哪一个 graph 闭包

它**不**要求 graph 只包含当前 package 自己声明的节点。

在当前 contract 下：

- imported external reference **不是新 primitive**
- 它仍然编码为普通 `Knowledge`
- 其 `id` 可以是 foreign QID
- 单纯把 foreign QID 写进当前 graph，**不会**铸造一个新的本地身份

也就是说，`LocalCanonicalGraph` 是 **package-local ownership unit**，不是 **package-local reference closure**。

关于 imported node 需要携带哪些附加 provenance / lock metadata，Gaia IR 目前只要求“足以让实现无歧义地识别这是被引用的外部 occurrence”；更细的 authoring / dependency schema 留给 frontend 与 ecosystem 文档。

**内容指纹**：`content_hash = SHA-256(type + content + sorted(parameters))`，不含 `package_id`。同一内容在不同包中产生相同的 `content_hash`。用途：

- **本地去重与匹配**：编译时检测包内是否有内容完全一致的 Knowledge 节点。
- **跨包内容比对**：不同包中同内容的 Knowledge 共享同一 `content_hash`，可用于发现语义等价节点。

完整的身份、内容指纹与图哈希规则见 [03-identity-and-hashing.md](03-identity-and-hashing.md)。

### 1.2 三种知识类型

| type | 说明 | 携带概率 | 可作为 |
|------|------|---------|--------|
| **claim** | 科学断言（封闭或全称） | 是（唯一携带 prior + belief 的类型） | premise, background, conclusion, refs |
| **setting** | 背景信息 | 否 | background, refs |
| **question** | 待研究方向 | 否 | background, refs |

#### claim（断言）

具有真值的科学断言。唯一携带概率（prior + belief）的知识类型。

Claim 分为两类，由 `parameters` 字段区分：

- **封闭 claim**（`parameters=[]`）：所有变量已绑定的具体命题。如 "YBCO 在 90K 以下超导"。
- **全称 claim**（`parameters` 非空）：含量化变量的通用定律。如 `∀{x}. superconductor({x}) → zero_resistance({x})`。全称 claim 有真值（可被反例推翻），携带概率，当前可通过多条共享结论的 abduction 结构获得经验支持，并通过 deduction 实例化为封闭 claim。

> **设计决策（Issue #231）：** 原 `template` 类型统一为 claim with parameters。理由：全称命题天然具有真值，应携带概率。"template" 概念保留在 Gaia Language 编写层作为语法工具，编译到 Gaia IR 时按语义分流为 claim、setting 或 question。

Claim 可以携带描述其产生方式的结构化元数据（`metadata` 字段）。以下是概念性示例，不构成封闭分类。Gaia IR 层不限制 `metadata` 的结构。

```yaml
# 观测
content: "该样本在 90 K 以下表现出超导性"
metadata: {schema: observation, instrument: "四探针电阻率测量"}

# 定量测量
content: "YBa₂Cu₃O₇ 的超导转变温度为 92 ± 1 K"
metadata: {schema: measurement, value: 92, unit: "K", uncertainty: 1}

# 计算结果
content: "DFT 计算预测该材料的带隙为 1.2 eV"
metadata: {schema: computation, software: "VASP 6.4", functional: "PBE"}

# 经验规律
content: "金属的电阻率与温度成线性关系（Bloch-Grüneisen 高温极限）"
metadata: {schema: empirical_law, domain: "固态物理", validity: "T >> Debye 温度"}

# 全称 claim（原 template）
content: "∀{x}. superconductor({x}) → zero_resistance({x})"
parameters: [{name: "x", type: "material"}]
metadata: {schema: universal_law, domain: "凝聚态物理"}
```

#### 全称 claim 的实例化

全称 claim 通过 deduction Strategy（条件概率=1.0）实例化为封闭 claim：

```
全称 claim:  "∀{x}. superconductor({x}) → zero_resistance({x})"  (claim, parameters=[x:material])
绑定:        "x = YBCO"                                            (setting, background)
                ↓ Strategy(type=deduction, p=1.0)
封闭 claim:  "superconductor(YBCO) → zero_resistance(YBCO)"       (claim, parameters=[])
```

全称 claim 和封闭 claim 之间形成自然的“经验支持 - 演绎实例化”循环：

- **经验支持**：多个封闭实例可通过多条共享结论的 abduction 结构共同支持全称 claim；未来也可在 authoring 层以 induction 语法糖表达
- **演绎**：全称 claim 通过 deduction Strategy 预测新封闭实例 → 实例的 belief 跟随全称
- **反例**：发现与全称矛盾的封闭 claim → contradiction Operator → 全称的 belief 下降

#### setting（背景设定）

研究的背景信息或动机性叙述。不携带概率。可作为 Strategy 的 background（上下文依赖）或 refs（弱引用）。

示例：某个领域的研究现状、实验动机、未解决挑战、近似方法或理论框架、全称 claim 实例化时的变量绑定（如 "x = YBCO"）。

#### question（问题）

探究制品，表达待研究的方向。不携带概率。可作为 Strategy 的 background 或 refs。

示例：未解决的科学问题、后续调查目标。

### 1.3 Helper Claim

Helper claim **不是新的 Knowledge 类型**。它仍然是普通的 `claim`，只是承担了结构结果节点的角色。

当前文档里的 `helper claim` 专指**结构型 result claim**，例如 `conjunction` 结果 `M`，以及 `equivalence` / `contradiction` / `complement` / `disjunction` 的标准结果 claim。

在当前 contract 下：

- helper claim 一旦进入 Gaia IR，就仍然编码为 `Knowledge(type=claim)`
- 顶层 Operator 的 conclusion（如 `equivalence` 的结果）是图中的普通可见节点，可以被任何 Strategy 引用
- FormalExpr 内部的中间 claim 是该 FormalStrategy 的**私有节点**，禁止被外部 Strategy 引用（保证 FormalStrategy 可折叠）

像 `AlternativeExplanationForObs`、`BridgeClaim`、`ContinuityClaim` 这类语义接口或中间命题，目前仍按普通 `claim` 处理，不在 helper claim 术语里单独归类。

详细约定见 [04-helper-claims.md](04-helper-claims.md)。

---

## 2. Operator（结构约束）

Operator 表示两个或多个 Knowledge 之间的**确定性逻辑关系**——真值表完全确定，无自由参数。

theory 推导见 [命题算子](../theory/03-propositional-operators.md)。

### 2.1 Schema

```
Operator:
    operator_id:    str | None       # 顶层必填（lco_ 前缀）；FormalExpr 嵌入时可省略
    scope:          str | None       # 顶层必填；FormalExpr 嵌入时可省略

    operator:       str              # 算子类型（见 §2.2）
    variables:      list[str]        # 连接的 Knowledge IDs（有序）
    conclusion:     str              # 该 Operator 的标准结果 claim / helper claim

    metadata:       dict | None      # 含 refs: list[str] 等
```

`conclusion` 的语义是：**该 Operator 在图中的标准结果 claim**。

- 对 `implication` / `conjunction`，它延续原有语义，表示 operator 的输出 claim
- 对 `equivalence` / `contradiction` / `complement` / `disjunction`，它是结构型 helper claim，使这些关系本身也能被后续结构直接引用

### 2.2 算子类型与真值表

| operator | 符号 | variables | conclusion | 真值约束 | 说明 |
|----------|------|-----------|------------|---------|------|
| **implication** | → | [A] | B | A=1 时 B 必须=1 | A 成立则 B 必须成立 |
| **equivalence** | ↔ | [A, B] | helper claim（如 `same_truth(A,B)`） | A=B | 真值必须一致 |
| **contradiction** | ⊗ | [A, B] | helper claim（如 `not_both_true(A,B)`） | ¬(A=1 ∧ B=1) | 不能同时为真 |
| **complement** | ⊕ | [A, B] | helper claim（如 `opposite_truth(A,B)`） | A≠B | 真值必须相反（XOR） |
| **disjunction** | ∨ | [A₁,...,Aₖ] | helper claim（如 `any_true(A₁,...,Aₖ)`） | ¬(all Aᵢ=0) | 至少一个为真 |
| **conjunction** | ∧ | [A₁,...,Aₖ] | M | M=(A₁∧...∧Aₖ) | M 等于所有 Aᵢ 的合取 |

**关键性质：** Operator 没有概率参数——它编码的是逻辑结构（"A 和 B 矛盾"），不是推理判断（"作者认为 A 蕴含 B"）。后者由 Strategy 承载。

### 2.3 存在位置

Operator 可以出现在两个位置：

- **顶层 `operators` 数组**：独立的结构关系。例如：
  - 人工标注的 contradiction（"GR 预测 1.75 角秒"⊗"牛顿预测 0.87 角秒"）
  - 规范化确认的 equivalence（跨包同义命题）
  - Review 发现的 implication

- **FormalStrategy 内部的 `formal_expr.operators`**：FormalExpr 展开产生的算子，嵌入在 FormalStrategy 中，不独立存在。

位置即来源，不需要额外的 `source` 字段。

### 2.4 不变量

`variables` 只包含输入变量，`conclusion` 独立承载输出，两者不重叠。

Operator 分为两类：

| 类别 | Operator 类型 | conclusion 语义 |
|------|-------------|----------------|
| **Directed**（有向） | `implication`, `conjunction` | 输出 claim（如蕴含的结果、合取结果 M） |
| **Relation**（关系） | `equivalence`, `contradiction`, `complement`, `disjunction` | 结构型 helper claim |

具体规则：

1. `variables` 中的所有 ID 必须引用同 graph 中存在的 Knowledge
2. `variables` 中的 Knowledge 类型必须是 `claim`（Operator 只连接有真值的命题）
3. `conclusion` 必须引用同 graph 中存在的 `claim`
4. `conclusion` **不出现在** `variables` 中——`variables` 只放输入，`conclusion` 独立承载输出
5. 关系型 Operator 的 `conclusion` 应语义上对应其结构型 helper claim，不允许借此手写任意主观结论
6. 推荐在 `metadata.canonical_name` 中记录函数式命名（如 `not_both_true(A,B)`、`same_truth(A,B)`）；这是不同实现之间建议统一的命名惯例，不作为 hard validation

**引用位置的 ownership 语义：** 这里只要求“图中存在、类型合法、引用闭合”。  
`variables` 与 `conclusion` 所指向的 claim 可以是本地声明节点，也可以是 imported external occurrence。IR core 不把“这个 claim 属于谁”编码成另一套 Operator 语义。

完整 validator 视角的检查清单见 [08-validation.md](08-validation.md)。

---

## 3. Strategy（推理声明）

Strategy 表示推理声明——前提通过某种推理支持结论。Strategy 是不确定性的载体：**所有概率参数都在 Strategy 层**（通过 [parameterization](06-parameterization.md)），Operator 层纯确定性。

### 3.1 基本概念

一个基本 Strategy 表达一条概率性推理：

```
premises  ——↝(p)——→  conclusion
```

其中 ↝ 表示"前提以条件概率 p 支持结论"。

与 ownership 无关，Strategy 的引用位置只区分 **类型约束**，不区分 **本地 vs imported**。  
也就是说，只要某个 `Knowledge` 作为 claim / setting / question 合法出现在 graph 中，它就可以按字段语义进入 `premises`、`conclusion` 或 `background`。

Strategy 有三种形态（类层级），支持多分辨率推理——同一图可在不同粒度上做概率推理：

| 形态 | 说明 | 独有字段 |
|------|------|---------|
| **Strategy**（基类，可实例化） | 叶子推理（单条 ↝） | — |
| **CompositeStrategy**(Strategy) | 含子策略，可递归嵌套 | `sub_strategies` |
| **FormalStrategy**(Strategy) | 含确定性 Operator 展开 | `formal_expr` |

所有形态折叠时均可视为单条 ↝。对 `infer` / `noisy_and`，其参数直接来自 parameterization 层；对直接 `FormalStrategy`，若需要折叠视图，则由 `FormalExpr` + 相关显式 claim prior 现算导出。

`type` 与 `形态` 是两个不同维度：

- `type` 表示这条推理属于哪一种**语义家族**（如 deduction、abduction、analogy）
- `形态` 表示它当前以哪一种**展开程度/组织方式**存储（叶子、层次化、完全形式化）

二者并非完全绑定。命名策略本体可以直接是 `FormalStrategy`；如果更大的论证需要保留层次边界，则由外层 `CompositeStrategy` 组合这些子结构。

**从第一性原理看，这样分层的原因是：**

- IR 首先要表达的是**推理语义是什么**，其次才是**这些推理单元如何组织**
- `abduction`、`analogy`、`extrapolation` 在 theory 中都有各自的 canonical 微观 skeleton，因此一旦识别出该结构，本体就应直接落为 `FormalStrategy`
- `induction` 是 `CompositeStrategy` 的 canonical use case：它包装多条共享同一结论的 abduction 子策略，归纳效应由因子图拓扑涌现
- `CompositeStrategy` 不是另一种 reasoning family；它只负责组合多个 strategy-level 子结构，保留更大论证树的 hierarchy
- “步骤多”不等于“必须 Composite”。只要一个命名推理仍然对应单一 canonical skeleton，它就仍然是一个 `FormalStrategy`
- 当需要把多个命名或未命名推理单元拼成更大论证时，才引入 `CompositeStrategy`

### 3.2 Schema

**Strategy（基类）**：

```
Strategy:
    strategy_id:    str | None       # 自动计算；构造后总是非 None（lcs_ 前缀）
    scope:          str              # "local"
    type:           str              # 见 §3.3

    # ── 连接 ──
    premises:       list[str]        # claim Knowledge IDs（参与概率推理）
    conclusion:     str | None       # 单个输出 Knowledge（必须是 claim）
    background:     list[str] | None # 上下文 Knowledge IDs（任意类型，不参与概率推理）

    # ── local 层 ──
    steps:          list[Step] | None  # 推理过程的分步描述

    # ── 追溯 ──
    metadata:       dict | None
```

**CompositeStrategy(Strategy)**——新增：

```
CompositeStrategy(Strategy):
    sub_strategies:  list[str]       # 子策略的 strategy_id 列表（可引用 Strategy / CompositeStrategy / FormalStrategy）
```

**FormalStrategy(Strategy)**——新增：

```
FormalStrategy(Strategy):
    formal_expr:     FormalExpr      # 确定性 Operator 展开（必填）

FormalExpr:
    operators:       list[Operator]  # 只包含确定性 Operator
```

FormalExpr 只引用 Knowledge ID，不创建 Knowledge。展开操作需要的中间 Knowledge 或自动补齐的接口 Knowledge（如 deduction 的 conjunction 结果、abduction 的 `AlternativeExplanationForObs`）由执行展开的 compiler/reviewer/agent 显式创建，作为独立的 `claim` 节点存在于图中；这些节点的封装规则见 [04-helper-claims.md](04-helper-claims.md)。

**接口边界规则：**

- `premises` / `conclusion` 定义一个 Strategy 对外暴露的输入输出接口
- `FormalExpr` 中引入但不出现在任何 Strategy 的 `premises` / `conclusion` 中的 Knowledge，属于该 FormalStrategy 的**私有节点**
- 私有节点**禁止**被外部 Strategy 引用。原因：FormalStrategy 的折叠（marginalization）要求对内部变量做变量消去，如果外部依赖这些变量的身份，消去就不安全。私有节点的不可引用性保证了 FormalStrategy 总是可以被折叠的
- 如果某个中间结果需要被多个 Strategy 共享，应重构图结构——把它作为 Strategy 之间的显式接口节点，而不是引用另一个 FormalStrategy 的内部变量

**身份规则**：`strategy_id` 的 hash 输入包含接口信息和内部结构摘要，确保不同结构的同接口策略不会 ID 碰撞：

```
strategy_id = lcs_{SHA-256(scope + type + sorted(premises) + conclusion + structure_hash)[:16]}
```

其中 `structure_hash` 按形态决定：

| 形态 | structure_hash |
|------|---------------|
| 叶子 Strategy | `""` （空字符串） |
| CompositeStrategy | `SHA-256(sorted(sub_strategies))` |
| FormalStrategy | `SHA-256(canonical(formal_expr))` |

`canonical(formal_expr)` 是对 FormalExpr 内 Operator 列表的确定性序列化（按 operator_id 或结构排序）。具体序列化算法待实现时细化。

**注意**：`sorted(premises)` 和 `conclusion` 中的 Knowledge ID 为 QID。

### 3.3 类型字段

| type | 显式外部参数模型 | 典型/默认形态 | 说明 |
|------|----------------|--------------|------|
| **`infer`** | 完整条件概率表（CPT）：2^k 参数（默认 MaxEnt 0.5） | Strategy | 未分类的粗推理；`↝` 摘要的默认承载形态 |
| **`noisy_and`** | ∧ + 单参数 p | Strategy | 前提联合必要的叶子推理 |
| **`deduction`** | 无独立 strategy-level 参数 | FormalStrategy | 严格确定性推导（数学证明、逻辑三段论）。条件行为由 conjunction + implication skeleton 直接确定。推导步骤本身不引入不确定性——不确定性仅来自前提的 prior。如果推理有不确定性（计算误差、经验推断、省略前提），应使用 `noisy_and` |
| **`abduction`** | 无独立 strategy-level 参数 | FormalStrategy | 有效条件概率由 `Obs ≡ (H ∨ AlternativeExplanationForObs)` 与相关 interface prior 现算导出 |
| **`induction`** | 无独立 strategy-level 参数 | CompositeStrategy | 包装 n 条共享同一 conclusion 的 `abduction` 子策略；归纳效应（观测累积→Law 置信度上升）由因子图拓扑涌现 |
| **`analogy`** | 无独立 strategy-level 参数 | FormalStrategy | 有效条件概率由 skeleton + BridgeClaim prior 现算导出 |
| **`extrapolation`** | 无独立 strategy-level 参数 | FormalStrategy | 有效条件概率由 skeleton + ContinuityClaim prior 现算导出 |
| **`reductio`**（deferred） | — | — | theory 中保留；Gaia IR core 当前暂不固化其 hypothetical assumption / consequence 的接口契约 |
| **`elimination`** | 无独立 strategy-level 参数 | FormalStrategy | 条件行为由 disjunction + equivalence + contradiction + conjunction / implication skeleton 直接确定 |
| **`mathematical_induction`** | 无独立 strategy-level 参数 | FormalStrategy | 条件行为由其 formal skeleton 直接确定 |
| **`case_analysis`** | 无独立 strategy-level 参数 | FormalStrategy | 条件行为由 disjunction + equivalence + conjunction / implication skeleton 直接确定 |
| **`toolcall`**（deferred） | — | — | 未引入。待后续设计 |
| **`proof`**（deferred） | — | — | 未引入。待后续设计 |

> **设计决策：** `contradiction` 不作为 Strategy 类型——它是结构关系，直接用 Operator 表达。原 `soft_implication` 合并到 `noisy_and`（k=1 的特例）。原 `None` 合并到 `infer`。跨 package 的 duplicate / double-counting 判断不在 Gaia IR core 中伪装成新的 Strategy type。

### 3.4 参数化语义

只有需要外部概率参数的 Strategy 才在 [parameterization](06-parameterization.md) 层携带 `StrategyParamRecord`。直接 `FormalStrategy` 的命名策略没有独立的 strategy-level 条件概率；其有效条件行为由 `FormalExpr` 和相关**接口 claim** 的 prior 导出。

**三层处理：**

1. **IR 层（source of truth）**
   `FormalStrategy` 的真实定义是 `FormalExpr` + 外部接口节点（`premises` / `conclusion`）+ 私有中间节点；这里不额外存一份手工填写的 `conditional_probabilities`。
2. **持久化 parameterization 输入层**
   只对需要外部概率参数的 Strategy 存 `StrategyParamRecord`，例如 `infer` / `noisy_and`。
3. **运行时 compiled / assembled 层**
   每个 Strategy 都可以关联一份等效的 `conditional_probabilities` 视图：
   - 参数化 Strategy：直接读取持久化参数
   - 直接 FormalStrategy：由 `FormalExpr` + 相关接口 claim prior 现算导出

FormalExpr 内部的中间节点是严格私有的（禁止被外部引用），因此 FormalStrategy **总是可以被折叠**——对私有中间变量做变量消去，导出等效的 P(conclusion | premises)。折叠还是展开由推理引擎的 `expand_set` 决定。

更完整的 backend-facing lowering 边界见 [07-lowering.md](07-lowering.md)。

#### `infer`（通用条件概率表）

未分类的通用推理。k 个前提需要 2^k 个条件概率参数——每种前提真值组合对应一个 P(conclusion | 前提组合)。按最大熵原则，默认值全为 0.5（无信息先验）。

实践中很少使用——大多数推理会被分类为 `noisy_and` 或命名策略。`StrategyParamRecord.conditional_probabilities: list[float]` 已支持变长列表，可存储 2^k 参数。

#### `noisy_and`（∧ + 单参数 p）

**最常用的 Strategy 类型。** 所有前提先 AND（联合必要条件），再以条件概率 p 推出结论：

```
P(conclusion=true | all premises=true) = p
P(conclusion=true | any premise=false) = ε    （Cromwell leak）
```

单参数 p 表达推理本身的可信度，前提的可信度由各自的 prior 表达。

**适用范围：前提是联合必要条件的推理。** 适合表达一条没有继续细化的局部推理。

**不适用于把整条归纳/溯因语义压平成单条 generic noisy_and。** 归纳、溯因、类比、外推在 theory 中都有各自的命名微观结构；如果要保留这些语义，应使用对应的命名 `type` 并直接 formalize 为 FormalStrategy。若更大论证需要保留 hierarchy，则由外层 CompositeStrategy 组合这些结构。

#### 跨 package 的 duplicate 问题不对应新的 core Strategy type

当 GitHub 上出现多个 package 分别讨论“同一个命题”、或新 package 只是旧论证的改写时，真正的问题是 **公共协作生态中的 canonicalization / review / curation**，不是 package-local Strategy 语义的扩展。

因此 Gaia IR core 当前只固定两件事：

- package 内如何表达局部推理结构
- package 内如何保留足够的 occurrence identity、内容指纹与 provenance 信息

至于 “这是不是同题”“这是不是独立新证据”“会不会 double count”，应由 review / registry 层基于公开 package 记录作判断，而不是在 core IR 中新增 `binding` 或 `independent_evidence` 这类 Strategy primitive。

### 3.5 三种形态

#### 3.5.1 基本 Strategy（叶子 ↝）

最简单的形态——内部结构不透明（opaque），没有 `formal_expr`，也没有 `sub_strategies`。叶子策略包括 `infer`、`noisy_and` 等参数化类型，也包括命名策略（如 `deduction`）尚未展开为 FormalStrategy 的形态。当未来发现更明确的内在结构时，叶子策略可以被进一步 refine 为 FormalStrategy。

对参数化叶子（`infer` / `noisy_and`），外部概率参数由 parameterization 层提供；在运行时 compiled 层，它们也对应一份直接读取的 `conditional_probabilities` 视图。

#### 3.5.2 CompositeStrategy（保留层次边界的分解容器）

将一个较大的推理组织为多个子策略。`sub_strategies` 存储子策略的 `strategy_id` 列表；这些 child strategy 本身仍然是同 graph 中的独立 Strategy 对象，且可以是任意形态（Strategy / CompositeStrategy / FormalStrategy）。

CompositeStrategy 的作用是**保留分解边界**。它组合的是多个 strategy-level 子结构，而不是直接组合 Operator。其典型子节点可以是 `Strategy`、`FormalStrategy`，或更深一层的 `CompositeStrategy`。

换句话说，CompositeStrategy 解决的是“这些推理单元如何组成更大的论证树”，不是“单个命名推理的微观 skeleton 是什么”。

典型用途：

- 大型证明或工具调用的多步结构
- 只展开局部而保留其余部分折叠的 partial expansion
- 为更大的论证树保留语义上的组合边界

当一个较大的论证逐步 formalize 时，典型会经历三个阶段：

1. **Strategy**：尚未分解，只有一条粗粒度 ↝
2. **CompositeStrategy（混合态）**：已有部分子结构被 formalize，`sub_strategies` 引用到的 child 里同时存在 `Strategy` 和 `FormalStrategy`
3. **CompositeStrategy（全 formal 叶子）**：层次结构仍保留，但所有叶子都已变成 `FormalStrategy`

折叠时（不展开）：整体仍表达为单条 ↝。展开时：递归进入每个子策略的内部结构。

#### 3.5.3 FormalStrategy + FormalExpr（完全展开）

当某个**原子子结构**已经被展开为确定性 Operator skeleton 时，使用 FormalStrategy。`formal_expr` 只包含 Operator（确定性），不包含不确定的 ↝。

对命名策略本体，`FormalStrategy` 就是 canonical fully-expanded form。若它出现在更大的论证树中，则通常作为 CompositeStrategy 的叶子。

换句话说，FormalStrategy 回答的是“这个命名推理单元内部到底由哪些确定性关系构成”，而不是“它在整篇论证里处于哪一层”。

**关键约束：FormalExpr 只包含确定性 Operator，不包含概率参数。展开后的不确定性通过显式接口 claim 的先验 π 表达（在 parameterization 层赋值）；不再额外引入独立的、持久化的 strategy-level conditional probability。若运行时需要 `conditional_probabilities` 视图，应由内部结构现算导出。**

### 3.6 命名策略的典型表示

#### 典型 fully expanded 形态

所有命名策略在**未展开**时都可以先作为叶子 Strategy 存在。下面给出它们在识别出命名结构后的直接 FormalStrategy 写法；若要保留更大的 hierarchy，再由外层 CompositeStrategy 组合这些 FormalStrategy。

这些 `formal_expr` 示例表示的是 **IR formalization 之后的 canonical stored form**。正常构图时，调用方通常只提供命名 leaf `Strategy` 的接口节点；IR 侧负责自动创建所需的中间 Knowledge，并生成对应的 `FormalExpr`，而不是要求用户手写 `operators`。

对纯确定性家族，FormalExpr 骨架通常几乎是唯一的：

**演绎（deduction）**：`premises=[A₁,...,Aₖ], conclusion=C`
```
FormalStrategy(type=deduction):
  formal_expr:
    - conjunction([A₁,...,Aₖ], conclusion=M)
    - implication([M], conclusion=C)
```

**数学归纳（mathematical_induction）**：`premises=[Base, Step], conclusion=Law`
```
FormalStrategy(type=mathematical_induction):
  formal_expr:
    - conjunction([Base, Step], conclusion=M)
    - implication([M], conclusion=Law)
```
结构与演绎相同。语义区分：Base=P(0), Step=∀n(P(n)→P(n+1)), Law=∀n.P(n)。

**归谬（reductio）**：theory 中保留，但 Gaia IR core 当前 defer。

原因不是 theory 不清楚，而是当前最小 public-interface contract 还没收稳：`P`（假设）与 `Q`（在假设下导出的后果）都带有明显的 hypothetical / internal 角色，而 Gaia IR core 当前只对两类私有节点有稳定 contract：

- structural helper claim
- 可由接口节点严格决定的 deterministic internal node

在没有把这类 hypothetical assumption / consequence 节点的 interface 边界固定下来之前，Gaia IR core 不再保留一个看似简单但会隐藏语义自由度的 reductio canonical template。

**排除（elimination）**：`premises=[Exhaustiveness, H₁, E₁, ..., Hₖ, Eₖ], conclusion=Hₛ`
```
FormalStrategy(type=elimination):
  formal_expr:
    - disjunction([H₁,...,Hₖ,Hₛ], conclusion=Disj_Candidates)
    - equivalence([Disj_Candidates, Exhaustiveness], conclusion=Eq_Disj_Exhaustive)
    - contradiction([H₁, E₁], conclusion=Contra_H₁_E₁)
    - contradiction([H₂, E₂], conclusion=Contra_H₂_E₂)
    - ...（每个被排除候选一条 contradiction）
    - conjunction([Exhaustiveness, E₁, Contra_H₁_E₁, ..., Eₖ, Contra_Hₖ_Eₖ], conclusion=M)
    - implication([M], conclusion=Hₛ)
```

这里 `Exhaustiveness` 仍是正向 coverage claim：它表达“被列出的候选 `H₁...Hₖ` 加上幸存者 `Hₛ` 已足以覆盖这次推理所需的讨论空间”。`Hᵢ` 是显式 interface claim，表示被排除的候选；`Eᵢ` 是对应的排除证据，也同样是普通 interface claim。`Disj_*`、`Eq_*`、`Contra_*`、`M` 则都是 private helper claim。

**最小例子：**
```
Strategy(
  type="elimination",
  premises=[
    "github:diagnosis::diagnosis_exhaustive",
    "github:diagnosis::bacterial_infection",
    "github:diagnosis::antibiotics_negative_excludes_bacterial",
    "github:diagnosis::viral_infection",
    "github:diagnosis::viral_test_negative_excludes_viral",
  ],
  conclusion="github:diagnosis::autoimmune_reaction",
)
```

**分情况讨论（case_analysis）**：`premises=[Exhaustiveness, A₁, P₁, ..., Aₖ, Pₖ], conclusion=C`
```
FormalStrategy(type=case_analysis):
  formal_expr:
    - disjunction([A₁,...,Aₖ], conclusion=Disj_A₁_..._Aₖ)
    - equivalence([Disj_A₁_..._Aₖ, Exhaustiveness], conclusion=Eq_Disj_Exhaustive)
    - conjunction([A₁, P₁], conclusion=M₁), implication([M₁], conclusion=C)
    - conjunction([A₂, P₂], conclusion=M₂), implication([M₂], conclusion=C)
    - ...（每个 case 一对 conjunction + implication）
```

这里 `Exhaustiveness` 是一个正向的 coverage claim：它表达“当前列出的这些 case 已足以覆盖这次推理所需的讨论空间”。`Aᵢ` 是显式 interface claim，`Pᵢ` 是在该 case 下推出 `C` 的 support / justification claim，也都是普通 interface claim。`Disj_*`、`Eq_*`、`Mᵢ` 则是 private helper claim。

当前 Gaia IR core 只保留 strict `case_analysis`。如果调用方不能为 `Exhaustiveness` 建立足够信念，就应降低它的 prior，或改用更弱的结构，而不是在 core 模板里再引入额外的 open-world case。

**最小例子：**
```
Strategy(
  type="case_analysis",
  premises=[
    "github:number_theory::integer_parity_exhaustive",
    "github:number_theory::n_even",
    "github:number_theory::even_case_supports_evenness",
    "github:number_theory::n_odd",
    "github:number_theory::odd_case_supports_evenness",
  ],
  conclusion="github:number_theory::n2_plus_n_even",
)
```

`abduction`、`analogy`、`extrapolation` 虽然宏观上不是纯演绎，但在 theory 中都对应确定性的微观 skeleton。一旦识别出这些命名结构，本体就可以直接表示为 FormalStrategy。`induction` 在 theory 中可理解为 repeated abduction，但 Gaia IR core 当前将其 defer，不单独设为一等 FormalStrategy 类型。

**溯因（abduction）**：概念接口是 `premises=[Obs, AlternativeExplanationForObs], conclusion=H`

`AlternativeExplanationForObs` 是一个**public interface claim**，表示“除 H 之外，还存在某个足以解释 Obs 的替代解释”。它不是 helper claim；它可以带 prior，也可以被其他 Strategy 支撑。若调用方只提供 `Obs`，IR formalization 可以自动生成这个 public interface claim 并补入 `premises`，但不会替它自动发明 prior。

```
FormalStrategy(type=abduction, premises=[Obs, AlternativeExplanationForObs], conclusion=H):
  formal_expr:
    - disjunction([H, AlternativeExplanationForObs], conclusion=Disj_Explains_Obs)
    - equivalence([Disj_Explains_Obs, Obs], conclusion=Eq_Explains_Obs)
```

`Disj_Explains_Obs` 与 `Eq_Explains_Obs` 是结构型 helper claim。`Obs` 和 `AlternativeExplanationForObs` 则是外部接口 claim。

**归纳（induction）**：`CompositeStrategy(type=induction, sub_strategies=[abd₁, abd₂, ..., abdₙ], conclusion=Law)`

归纳 = n 条共享同一 `Law` 结论的 abduction 子策略的组合。每条子策略是独立的 `FormalStrategy(type=abduction)`，各自有自己的 `Obsᵢ` 和 `AltExpᵢ`（可自动生成 interface claim）。

```
CompositeStrategy(type=induction, conclusion=Law):
  sub_strategies:
    - FormalStrategy(type=abduction, premises=[Obs₁, AltExp₁], conclusion=Law)
    - FormalStrategy(type=abduction, premises=[Obs₂, AltExp₂], conclusion=Law)
    - ...
    - FormalStrategy(type=abduction, premises=[Obsₙ, AltExpₙ], conclusion=Law)
```

归纳效应由因子图拓扑的 emergent property 产生：n 条 abduction 共享 Law 节点，BP 自然算出累积后验 `P(Law=1 | all Obsᵢ=1) = π(Law) / [π(Law) + (1−π(Law))·∏ᵢ ρᵢ]`（假设各 AltExpᵢ 条件独立）。CompositeStrategy 不直接 formalize——子 abduction 各自独立走 `_build_abduction` 路径。

全局替代解释（GlobalAltExp）不属于归纳的原子定义——它是独立的建模选择，作者可通过其他已有机制（Operator、Strategy）在论证图中表达。

**类比（analogy）**：`premises=[SourceLaw, BridgeClaim], conclusion=Target`

不确定性集中在 BridgeClaim 的先验 π(BridgeClaim)，不在骨架本身。`BridgeClaim` 是普通 `premise claim`；合取中间项 `M` 是私有结构型 helper claim。

```
FormalStrategy(type=analogy, premises=[SourceLaw, BridgeClaim], conclusion=Target):
  formal_expr:
    - conjunction([SourceLaw, BridgeClaim], conclusion=M)
    - implication([M], conclusion=Target)
```

**外推（extrapolation）**：`premises=[KnownLaw, ContinuityClaim], conclusion=Extended`

与类比结构相同。不确定性在 ContinuityClaim 的先验。`ContinuityClaim` 是普通 `premise claim`；合取中间项 `M` 是私有结构型 helper claim。

```
FormalStrategy(type=extrapolation, premises=[KnownLaw, ContinuityClaim], conclusion=Extended):
  formal_expr:
    - conjunction([KnownLaw, ContinuityClaim], conclusion=M)
    - implication([M], conclusion=Extended)
```

#### 需要保留 hierarchy 时 → CompositeStrategy

当一个更大的论证由多个命名或未命名子结构组成、且你希望保留组合边界时，用 CompositeStrategy 作为外层容器。常见场景：

- 很大的归纳或证明需要按章节/lemma 分组
- `toolcall` / `proof` 未引入，待后续设计
- 只想展开局部 skeleton，其余部分仍保留折叠
- 需要把多个 FormalStrategy / Strategy 组合成更大的 hierarchy

### 3.7 多分辨率展开

Strategy 的三种形态支持同一图在不同粒度上推理。给定一个"展开集合"（需要进入内部结构的 Strategy ID 集合），推理引擎可以选择：

- **不展开**：将 Strategy 视为单条 ↝，使用 parameterization 层的条件概率参数
- **展开 CompositeStrategy**：递归进入子策略
- **展开 FormalStrategy**：进入 FormalExpr 内的确定性 Operator 结构

具体的推理算法实现见 [bp/](../bp/) 层。

### 3.8 Lifecycle

Strategy 的形态即状态——不需要 `initial` / `candidate` / `permanent` 阶段标签：

```
Strategy(type=infer)                          ← 初始：通用推理
  ├── reviewer 分类为命名策略，保持叶子 Strategy
  ├── reviewer 确认为 noisy_and → type=noisy_and
  ├── reviewer 识别命名微观结构 → FormalStrategy + formal_expr
  ├── reviewer 开始分解 → CompositeStrategy（mixed Strategy / FormalStrategy children）
  ├── reviewer 继续 formalize → CompositeStrategy（all leaves FormalStrategy）
  └── 保持 type=infer
```

IR 中所有 Strategy 都是已确认的结构——候选项由 review 层管理。

### 3.9 Premise / Background / Refs

| 字段 | 类型约束 | 参与概率推理 | 说明 |
|------|---------|-------------|------|
| **premises** | 仅 claim | 是 | 推理的形式前提，条件概率的输入变量 |
| **background** | 任意类型 | 否 | 上下文依赖（setting、全称 claim 实例化的绑定等） |
| **refs** (metadata) | 任意 | 否 | 弱相关来源引用 |

- **Premise**：推理成立的必要条件，必须是 claim。Review 在评估 Strategy 条件概率时应同时考虑 premises 和 background 的内容。
- **引用位置对 imported 节点开放**：只要 graph 中显式包含了该 external occurrence，imported claim 也可以作为 `premise` 或 `conclusion`，imported setting/question 也可以作为 `background`。IR core 不额外区分“支持本地结论”和“支持外部已存在结论”这两种写法。
- **Premise 只放外部接口输入**：例如 abduction 的 `Obs` 与 `AlternativeExplanationForObs`、case_analysis 的 `Exhaustiveness` / `Aᵢ` / `Pᵢ`、analogy 的 `SourceLaw` 与 `BridgeClaim`、extrapolation 的 `KnownLaw` 与 `ContinuityClaim`。如果要表达 theory 意义下的 induction，则在当前 Gaia IR 中把每个观测写成一条共享结论的 abduction，其 `AlternativeExplanationForObsᵢ` 同样属于 interface premise。像合取中间项 `M`、析取结果 `Disj_*` 这类仅为 FormalExpr 服务的节点，不应直接放进 `premises`。
- **Background**：上下文依赖，任意类型。不参与概率推理。
- **Refs**：存储在 `metadata.refs` 中的 ID 列表。不参与图结构。

### 3.10 不变量

1. `premises` 中的 Knowledge 类型必须是 `claim`
2. `conclusion` 的 Knowledge 类型必须是 `claim`（如果非 None）
3. `background` 中的 Knowledge 类型可以是任意（claim / setting / question）
4. FormalStrategy 的 `formal_expr` 必填；CompositeStrategy 的 `sub_strategies` 必填且非空
5. `sub_strategies` 和 `formal_expr` 不同时出现（形态互斥由类层级保证）
6. `sub_strategies` 引用关系必须构成 DAG（从任意 Strategy 沿 `sub_strategies` 不能回到自身）
7. FormalExpr 只包含 Operator（不包含 Strategy）；FormalExpr 内 Operator 按 conclusion 依赖关系必须构成 DAG（不允许循环依赖）
8. `noisy_and` 仅用于前提联合必要的场景；对归纳、溯因、类比、外推等命名推理，应优先使用相应 `type` 并直接表示为 FormalStrategy，而不是把整体语义压平成 generic `noisy_and`
9. FormalExpr 内部产生但不出现在任何 Strategy 的 `premises` / `conclusion` 中的中间 claim，属于该 FormalStrategy 的**私有节点**，**禁止**被外部 Strategy 引用。私有节点的不可引用性保证了 FormalStrategy 总是可以被折叠（marginalize 内部变量导出等效条件概率）。如果某个中间结果需要被共享，应重构图结构（见 [04-helper-claims.md §3.3](04-helper-claims.md#33-如果需要共享中间结果)）
10. helper claim 仍然是 `claim`，不引入新的 Knowledge primitive；当前 helper claim 术语只用于结构型 result claim，并额外区分 public/private 角色
11. imported external occurrences 只要被显式放入 graph，就和本地节点一样参与引用闭合、类型检查与 hashing；它们不是“隐式存在”的外部指针

完整 validator 视角的检查清单见 [08-validation.md](08-validation.md)。

---

## 4. 规范化（Canonicalization）

Gaia IR 管理 local package 内部的结构。公共协作生态中的 canonicalization 相关信息，来自 package、validated review reports、Official Registry issues、LKM Repo research tasks，以及后续公开的 public relation packages（见 [05-canonicalization.md](05-canonicalization.md)）。

在 IR schema 层，不存在一种单独的 “relation package graph” 变体。  
如果一个 package 的主要目的，是公开主张跨 package 的 duplicate / refinement / contradiction / connection 等关系，那么它在 IR 里仍然只是一个普通 `LocalCanonicalGraph`：

- 把被讨论的外部 occurrence 显式放进 graph
- 用普通 `Knowledge` / `Operator` / `Strategy` 表达关系主张及其支撑论证
- 用 metadata / provenance / refs 保留 issue、review finding、来源包等上下文

也就是说，relation package 是生态层用途，不是新的 core IR primitive。

IR 层的规范化边界见 [05-canonicalization.md](05-canonicalization.md)，包括：

- occurrence identity（QID）与 `content_hash` 的角色
- Gaia IR 为公共 canonicalization / cross-package review-curation 保留哪些可审计信息
- FormalExpr 中间 Knowledge 的创建规则
- FormalExpr 的生成方式

`Knowledge.id`（QID）与 `Knowledge.content_hash` 是两个不同概念：前者是 name-addressed 对象身份，后者是跨包内容指纹。

---

## 5. Retraction Deferred

`retraction` 不属于 Gaia IR contract。Gaia IR 只描述结构及其参数化接口，不定义“撤回如何表示/执行”的官方机制。

撤回相关设计延后到 review / curation / provenance 层处理；在该设计明确之前，Gaia IR 主规范不再规定任何 retraction 语义。

---

## 6. 设计决策记录

| 决策 | 理由 |
|------|------|
| Knowledge 三种类型（删除 template） | Issue #231：全称命题（∀{x}.P({x})）有真值，应携带概率。统一为 claim with parameters。Template 概念保留在 Gaia Language 编写层 |
| Operator 从 Strategy 分离 | ↔/⊗/⊕ 是确定性命题算子，不是推理声明。Operator 无概率参数，Strategy 有 |
| contradiction 用 Operator 表达 | 结构关系，不是推理判断。直接用 contradiction Operator |
| cross-package duplicate handling 不进入 core Strategy type | double counting 首先是 review / curation 生态问题；core IR 只保留 occurrence、内容和 provenance 信息，不把它硬编码成新的 runtime primitive |
| 所有 Operator 都有标准结果 claim | 关系型 Operator 也需要可引用的结构结论，因此 `conclusion` 不再只服务于 implication / conjunction |
| Strategy type 合并 | 原 None 合并到 infer，原 soft_implication 合并到 noisy_and（k=1 特例） |
| infer vs noisy_and 区分 | infer = 完整 CPT（2^k 参数），noisy_and = ∧ + 单参数 p。大多数推理使用 noisy_and |
| noisy_and 仅限联合必要场景 | 不应把归纳/溯因/类比/外推的整体语义压平成 generic noisy_and；应保留对应命名 type |
| type 与形态解耦 | type 表达推理语义家族，形态表达展开程度/组织方式。命名策略本体可以直接是 FormalStrategy；CompositeStrategy 负责组合这些子结构 |
| FormalExpr 只包含 Operator | fully expanded 后的不确定性转移到显式接口 claim 的 prior，FormalExpr 本身纯确定性 |
| FormalExpr 作为 FormalStrategy 的嵌入字段 | 1:1 关系，不需要独立实体；FormalExpr 无独立 ID 和 lifecycle |
| helper claim 仍是 claim | 不新增 Knowledge primitive；当前 helper claim 术语只用于结构型 result claim，并用 helper catalog 约束其 public/private 边界 |
| 对象身份与内容指纹分离 | `Knowledge.id` 负责对象身份；`content_hash` 负责跨包内容指纹与 canonicalization 快速路径；`ir_hash` 负责 local graph 完整性 |
| relation package 不新增 IR 变体 | cross-package relation 的公开主张仍复用普通 `LocalCanonicalGraph` 与既有 `Knowledge` / `Operator` / `Strategy` primitive；差异在 package 用途与 provenance，不在 graph schema |
| conditional_probabilities 三层处理 | 持久化层只存外部参数；运行时 compiled 层允许每个 Strategy 拥有等效 `conditional_probabilities` 视图；直接 FormalStrategy 的该视图由 FormalExpr 与相关显式 claim prior 导出 |
| 多分辨率展开 | 任意 Strategy 都可在运行时获得折叠视图；参数化 Strategy 直接读外部参数，直接 FormalStrategy 的折叠行为由内部结构现算导出 |
| retraction deferred | 撤回不属于 Gaia IR contract，延后到 review / curation / provenance 层定义 |

### 已知 Future Work

| 缺口 | 说明 | 影响 |
|------|------|------|
| **α-equivalence（Issue #234）** | 含 parameters 的 claim 匹配时需要忽略变量名 | Canonicalization 精度 |
| **Gaia IR Validator（Issue #233）** | 每次 IR 更新时的结构验证 | 数据完整性 |
| **Compiler dispatch（Issue #236）** | Gaia Language template → IR 知识类型的编译规则 | CLI 端实现 |

---

## 与原 Gaia IR 的概念映射

| 原概念 | 新概念 | 变更说明 |
|--------|--------|---------|
| KnowledgeNode | **Knowledge** | 去掉 Node 后缀；删除 template 类型，统一为 claim with parameters |
| FactorNode | **Strategy** | 改名 + 重构（统一 type，三形态类层级） |
| FactorNode.category + reasoning_type | Strategy.type | 合并为单一字段 |
| FactorNode.subgraph | **FormalExpr**（FormalStrategy 嵌入字段） | 从 FactorNode 字段提取为 data class |
| reasoning_type=equivalent | **Operator**(operator=equivalence) | 从推理声明移为结构约束 |
| reasoning_type=contradict | **Operator**(operator=contradiction) | 从推理声明移为结构约束 |
| — | **Operator**(operator=complement, disjunction, conjunction, implication) | 新增 |
| infer（旧，noisy-AND 语义） | **noisy_and** | 重命名；旧 infer 的 noisy-AND 语义现在叫 noisy_and |
| soft_implication | 合并到 noisy_and | k=1 的 noisy_and 特例 |
| None (type) | **infer** | 重命名；未分类推理统一用 infer（通用 CPT） |
| independent_evidence (旧：Operator) | deferred in Gaia IR core | 不在 core IR 中固化为 Strategy primitive；相关 judgment 留给 review / registry layer |
| contradiction (Strategy type) | 直接用 Operator(contradiction) | 结构关系，不是推理声明 |
