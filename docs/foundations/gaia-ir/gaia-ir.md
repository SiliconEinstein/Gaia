# Gaia IR — 结构定义

> **Status:** Target design — 基于 [06-factor-graphs.md](../theory/06-factor-graphs.md) 和 [04-reasoning-strategies.md](../theory/04-reasoning-strategies.md) 设计
>
> **⚠️ Protected Contract Layer** — 本目录定义 CLI↔LKM 结构契约。变更需要独立 PR 并经负责人审查批准。详见 [documentation-policy.md](../../documentation-policy.md#12-变更控制)。
>
> **设计依据：** [Gaia IR 重构设计文档](../../specs/2026-03-26-graph-ir-restructuring-design.md)

Gaia IR 编码推理超图的拓扑结构——**什么连接什么**。它不包含任何概率值。

Gaia IR 由四种实体构成：**Knowledge**（知识）、**Strategy**（推理声明）、**Operator**（结构约束）、**FormalExpr**（策略展开）。Knowledge 和 Strategy 承载作者的推理意图（Layer 2 — 科学本体），Operator 和 FormalExpr 承载精确的逻辑结构（Layer 3 — 计算方法）。

概率参数见 [parameterization.md](parameterization.md)。BP 输出见 [belief-state.md](belief-state.md)。三者的关系见 [overview.md](overview.md)。

---

## 1. Knowledge（知识节点）

Knowledge 表示命题。Gaia 中有四种知识对象。**Claim 是唯一默认携带 probability 并参与 BP 的类型。**

### 1.1 Schema

Local 和 global 使用同一个 data class，字段按层级使用：

```
Knowledge:
    id:                     str              # lcn_ 或 gcn_ 前缀
    type:                   str              # claim | setting | question | template
    parameters:             list[Parameter]  # 仅 template：自由变量列表
    source_refs:            list[SourceRef]
    metadata:               dict | None

    # ── local 层 ──
    content:                str | None       # 知识内容（local 层存储，global 层通常为 None）

    # ── 来源追溯 ──
    provenance:             list[PackageRef] | None   # 贡献包列表

    # ── global 层 ──
    representative_lcn:     LocalCanonicalRef | None  # 代表性 local 节点（内容从此获取）
    member_local_nodes:     list[LocalCanonicalRef] | None  # 所有映射到此的 local 节点
```

**各层字段使用：**

| 字段 | Local | Global |
|------|-------|--------|
| `id` | `lcn_` 前缀，SHA-256 包+内容寻址 | `gcn_` 前缀，注册中心分配 |
| `content` | 有值（唯一存储位置） | 通常为 None（FormalExpr 中间节点例外） |
| `provenance` | 有值（来源包） | 有值（贡献包列表） |
| `representative_lcn` | None | 有值（引用 local 节点获取内容） |
| `member_local_nodes` | None | 有值（所有映射到此的 local 节点） |

**身份规则**：local 层 `id = lcn_{SHA-256(package_id + type + content + sorted(parameters))[:16]}`。ID 包含 `package_id`，因此不同包中相同内容的节点有**不同的** lcn_id。跨包的语义等价由 global canonicalization 通过 embedding 相似度判定，而非 ID 相等。

**内容存储**：所有知识内容存储在 local 层的 `content` 字段上。Global 层通过 `representative_lcn` 引用获取内容，不重复存储。唯一例外是 FormalExpr 展开时新创建的中间 Knowledge（无 local 来源，content 直接存在 global 节点上）。

### 1.2 四种知识类型

| type | 说明 | 参与 BP | 可作为 |
|------|------|---------|--------|
| **claim** | 封闭的科学断言 | 是（唯一 BP 承载者） | premise, context, conclusion |
| **setting** | 背景信息 | 否 | premise, context |
| **question** | 待研究方向 | 否 | premise, context |
| **template** | 含自由变量的命题模式 | 否 | premise（instantiation 场景） |

#### claim（断言）

封闭的、具有真值的科学断言。默认携带 probability（prior + belief），是 BP 的唯一承载对象。

Claim 可以携带描述其产生方式的结构化元数据（`metadata` 字段）。以下是概念性示例，不构成封闭分类。具体的元数据 schema 由下层文档定义，Gaia IR 层不限制 `metadata` 的结构。

**观测（observation）**
```
content: "该样本在 90 K 以下表现出超导性"
metadata:
  schema: observation
  instrument: "四探针电阻率测量"
  conditions: "液氮温度区间, 10⁻⁶ Torr 真空"
  date: "2024-03-15"
```

**定量测量（measurement）**
```
content: "YBa₂Cu₃O₇ 的超导转变温度为 92 ± 1 K"
metadata:
  schema: measurement
  value: 92
  unit: "K"
  uncertainty: 1
  method: "电阻率-温度曲线拐点"
```

**计算结果（computation）**
```
content: "DFT 计算预测该材料的带隙为 1.2 eV"
metadata:
  schema: computation
  software: "VASP 6.4"
  functional: "PBE"
  basis: "PAW, 500 eV cutoff"
  convergence: "能量差 < 10⁻⁶ eV"
```

**文献断言（literature）**
```
content: "高温超导体的配对机制仍有争议"
metadata:
  schema: literature
  source: "Keimer et al., Nature 2015"
  doi: "10.1038/nature14165"
```

**理论推导（derivation）**
```
content: "在 Hartree-Fock 近似下，交换能正比于电子密度的 4/3 次方"
metadata:
  schema: derivation
  framework: "Hartree-Fock"
  assumptions: ["单行列式波函数", "均匀电子气"]
```

**经验规律（empirical law）**
```
content: "金属的电阻率与温度成线性关系（Bloch-Grüneisen 高温极限）"
metadata:
  schema: empirical_law
  domain: "固态物理"
  validity: "T >> Debye 温度"
```

#### setting（背景设定）

研究的背景信息或动机性叙述。不携带 probability，不参与 BP。可作为 Strategy 的 premise（承载性依赖）或 context（弱引用），但无论哪种角色都不创建 BP 边（见 §2.7）。

示例：某个领域的研究现状、实验动机、未解决挑战、近似方法或理论框架。

#### question（问题）

探究制品，表达待研究的方向。不携带 probability，不参与 BP。可作为 Strategy 的 premise 或 context，但不创建 BP 边（见 §2.7）。

示例：未解决的科学问题、后续调查目标。

#### template（模板）

开放的命题模式，含自由变量。不直接参与 BP。核心作用是**桥梁**：将 setting 或 question 包装为 claim，使其获得概率语义。Template 到 claim 的实例化是 deduction 的特例（probability=1.0）。

示例：`falls_at_rate({x}, {medium})`、`{method} can be applied in this {context}`、`∀{x}. wave({x}) → diffraction({x})`。

---

## 2. Strategy（推理声明）

Strategy 表示推理声明——前提通过某种推理支持结论。是 ↝（软蕴含）的载体，采用 noisy-AND 语义。

### 2.1 Schema

Local 和 global 使用同一个 data class，字段按层级使用：

```
Strategy:
    strategy_id:    str                # lcs_ 或 gcs_ 前缀（local/global canonical strategy）
    scope:          str                # "local" | "global"
    stage:          str                # initial | candidate | permanent

    # ── 统一类型 ──
    type:           str                # 见 §2.2

    # ── 连接 ──
    premises:       list[str]          # Knowledge IDs（仅 claim premise 创建 BP 边，见 §2.7）
    conclusion:     str | None         # 单个输出 Knowledge

    # ── 条件概率（conditional probability，值在 parameterization 层） ──
    # type ∈ {infer}:              [q₁,...,qₖ], qᵢ = P(C=1 | Aᵢ=1, 其余前提=1)
    # type = soft_implication:     [p₁, p₂],    p₁ = P(C=1|A=1), p₂ = P(C=0|A=0)
    # type ∈ {9 strategies}:       不需要（有 FormalExpr，参数在 Operator 层）
    conditional_probabilities: list[float] | None

    # ── local 层 ──
    steps:          list[Step] | None  # 推理过程的分步描述
    weak_points:    list[str] | None   # 自由文本 — 推理薄弱环节描述

    # ── 追溯 ──
    source_ref:     SourceRef | None
    metadata:       dict | None        # 包含 context: list[str]（弱相关 Knowledge IDs）等

Step:
    reasoning:        str                # 该步的推理描述文本
    premises:         list[str] | None   # 该步引用的前提（可选）
    conclusion:       str | None         # 该步的结论（可选）
```

**各层字段使用：**

| 字段 | Local | Global |
|------|-------|--------|
| `strategy_id` | `lcs_` 前缀，由源构造确定性计算 | `gcs_` 前缀，由 Strategy 提升后的全局构造计算 |
| `scope` | `"local"` | `"global"` |
| `premises`/`conclusion` | `lcn_` ID | `gcn_` ID |
| `steps` | 有值（推理过程文本） | None |
| `weak_points` | 有值（薄弱环节描述） | None |

`steps` 记录推理过程的分步文本。一个 Strategy 可以有一步或多步。每步的 `premises` 和 `conclusion` 是可选的——有些步骤只是描述性的推理过程，不显式关联特定的 Knowledge。Strategy 的顶层 `premises` 和 `conclusion` 是整个推理链的输入和最终输出。

**身份规则：** Strategy ID 由 `scope + type + sorted(premises) + conclusion` 确定性计算：`{prefix}_{sha256[:16]}`。Local 层前缀 `lcs_`，global 层前缀 `gcs_`。Strategy 提升（lcn→gcn 重写）后 premises/conclusion 变化，因此 global Strategy 与其源 local Strategy 有不同的 `strategy_id`。

> **与 Knowledge 的对偶关系：** Knowledge 用 `lcn_`/`gcn_` 前缀 + `content`/`representative_lcn` 字段区分层级；Strategy 用 `lcs_`/`gcs_` 前缀 + `scope` + `steps` 字段区分层级。两者结构对偶。

### 2.2 统一类型字段

`type` 合并了原 FactorNode 的 `category`、`reasoning_type`、`link_type` 三个维度为单一字段：

```
type:
    # 推理（经历 lifecycle: initial → candidate → permanent）
    infer                      # 默认，未分类推理（noisy-AND，需要 conditional_probabilities）
    soft_implication            # 单前提完整二参数模型（需要 conditional_probabilities）

    # 9 种命名策略（经历 lifecycle，自带 FormalExpr，不需要 conditional_probabilities）
    deduction                  # 演绎：∧ + →，确定性
    abduction                  # 溯因：→ + ↔，非确定性
    induction                  # 归纳：n×(→ + ↔)，非确定性
    analogy                    # 类比：∧ + →（含 BridgeClaim），非确定性
    extrapolation              # 外推：∧ + →（含 ContinuityClaim），非确定性
    reductio                   # 归谬：→ + ⊗ + ⊕，确定性
    elimination                # 排除：n×⊗ + n×⊕ + ∧ + →，确定性
    mathematical_induction     # 数学归纳：∧ + →，确定性
    case_analysis              # 分情况讨论：∨ + n×(∧ + →)，确定性

    # 非推理（不经历 lifecycle）
    toolcall                   # 计算 / 工具调用
    proof                      # 形式化证明
```

**从 type 可派生的属性：**

| type | 参数化模型 | 经历 lifecycle | 有 FormalExpr | 确定性 |
|------|-----------|---------------|--------------|--------|
| infer | noisy-AND [q₁,...,qₖ] | 是 | 否 | 否 |
| soft_implication | [p₁, p₂] | 是 | 否 | 否 |
| deduction | — | 是 | 是（trivial） | 是 |
| abduction | — | 是 | 是 | 否 |
| induction | — | 是 | 是 | 否 |
| analogy | — | 是 | 是 | 否 |
| extrapolation | — | 是 | 是 | 否 |
| reductio | — | 是 | 是 | 是 |
| elimination | — | 是 | 是 | 是 |
| mathematical_induction | — | 是 | 是（trivial） | 是 |
| case_analysis | — | 是 | 是 | 是 |
| toolcall | 另行定义 | 否 | 否 | — |
| proof | 另行定义 | 否 | 否 | — |

### 2.3 Noisy-AND 语义

Strategy 的隐含结构是 ∧ + ↝（theory [03-propositional-operators.md §5](../theory/03-propositional-operators.md)）：

```
A₁ ──(q₁)──┐
A₂ ──(q₂)──┤  AND → C
 ⋮          │
Aₖ ──(qₖ)──┘

P(C=1 | all Aᵢ=1) = ∏ qᵢ
P(C=1 | any Aᵢ=0) = 0     （所有前提充分且必要）
```

每个前提都是**必要的**（缺一不可），且各自**独立贡献**条件概率 qᵢ = P(C=1 | Aᵢ=1, 其余前提=1)。

**对应 theory：** theory §5（多前提推理中的 ∧ + ↝）定义了 ∧ + ↝ 为最基本的多前提组合模式。Noisy-AND 是其实用特化：每个前提有独立的条件概率参数。

**Soft-implication 模式：** 当 type=soft_implication 时，Strategy 恰好有一个 premise，参数为 [p₁, p₂]，对应 theory [§4](../theory/04-reasoning-strategies.md) 的完整二参数 ↝(p₁, p₂) 模型：p₁ = P(C=1|A=1)，p₂ = P(C=0|A=0)。

### 2.4 Lifecycle

```
type=infer（默认）
    ↓ reviewer 识别策略
type=<named_strategy>（自动获得 FormalExpr）
    ↓ review 验证
stage=permanent
```

- **initial**：作者写入的默认状态。type 可为 infer（未分类）或作者直接指定。
- **candidate**：reviewer 提议了具体 type，待验证。
- **permanent**：验证确认。

**生命周期规则：**

- 推理类 Strategy（type=infer 或 9 种命名策略）经历 lifecycle：initial → candidate → permanent。如果作者在 initial 阶段已指定 type，review 通过后可直接升格为 permanent。
- type=toolcall 和 type=proof 不经历 lifecycle——它们的语义在创建时就是明确的。
- Template 实例化（deduction 特例）可跳过 review 直接升格为 permanent。

### 2.5 合法组合与不变量

| type | stage=initial | stage=candidate/permanent |
|------|--------------|--------------------------|
| **infer** | 默认 type | type 已确认 |
| **soft_implication** | 作者指定 | review 确认 |
| **9 种命名策略** | 作者指定或 reviewer 提议 | review 确认（自动获得 FormalExpr） |
| **toolcall** | 创建时明确 | 不经历 lifecycle |
| **proof** | 创建时明确 | 不经历 lifecycle |

**不变量：**

1. `conclusion` 的 type 必须是 `claim`（如果 conclusion 非 None）
2. `premises` 中的 type 可以是 `claim | setting | question | template`
3. `weak_points` 是自由文本列表（不是 Knowledge 引用），是 Strategy probability 评估的注解
4. `type=template` 的 Knowledge 只能作为 deduction Strategy 的 premise（instantiation 场景）
5. `type=infer` 或 `type=soft_implication` 的 Strategy 需要 `conditional_probabilities`
6. 9 种命名策略的 Strategy 不需要 `conditional_probabilities`（参数在 FormalExpr 的中间 Knowledge 先验上）

### 2.6 Premise、Weak Point 与 Context 的区别

| 字段 | 位置 | 参与 BP | 说明 |
|------|------|---------|------|
| **premises** | 顶层字段 | claim premise 创建 BP 边（见 §2.7） | 承载性依赖，前提为假会削弱结论 |
| **weak_points** | 顶层字段 | 否 | 推理薄弱环节的注解，影响体现在 Strategy 的 conditional probability 上 |
| **context** | `metadata` 内 | 否 | 弱相关的 Knowledge 引用 |

- **Premise**：推理成立的必要条件。可以是任意知识类型（claim、setting、question、template），但只有 claim premise 创建 BP 边。
- **Weak point**：自由文本，描述推理过程中已识别但尚未分离成独立 premise 的薄弱环节。不是 Knowledge 引用，不创建 BP 边，不承担独立概率——它们的影响体现在该 Strategy 的 conditional probability 上（review 在评估 Strategy probability 时会参考 weak_points）。随着研究深入，weak point 可以被具体化为独立的 Knowledge 并提取为 premise。
- **Context**：存储在 `metadata.context` 中的 Knowledge ID 列表。不参与图结构（不创建边），不参与 BP。用于记录弱相关的 Knowledge 引用。

### 2.7 BP 参与规则

**Premise**：可以包含任意知识类型，但只有 `type=claim` 的 premise 参与 BP 消息传递。Non-claim premise（setting、question、template）在 BP 中被跳过——不发送消息、不接收消息、不影响 belief 计算。Non-claim premise 在图结构中是承载性依赖，但 review 在分配 Strategy probability 时应考虑其内容。

**Weak point**：不参与 BP。它们是 Strategy 内部的注解——review 在评估 Strategy 的 conditional probability 时参考 weak_points，将薄弱环节的影响编码进 conditional probability 中。

**Context**：在 metadata 中，不参与图结构，不参与 BP。

---

## 3. Operator（结构约束）

Operator 表示两个或多个 Knowledge 之间的确定性逻辑关系。对应 theory Layer 3（[因子图层](../theory/06-factor-graphs.md)）的势函数。

### 3.1 Schema

```
Operator:
    operator_id:    str                # lco_ 或 gco_ 前缀（local/global canonical operator）
    scope:          str                # "local" | "global"

    operator:       str                # 算子类型（见 §3.2）
    variables:      list[str]          # 连接的 Knowledge IDs（有序）
    conclusion:     str | None         # 有向算子的输出（无向算子为 None）

    stage:          str                # candidate | permanent
    source:         str                # "standalone" | "formal_expr:<strategy_id>"
    source_ref:     SourceRef | None
    metadata:       dict | None
```

### 3.2 算子类型与势函数

所有算子都是**确定性的**（ψ ∈ {0, 1}，无自由参数）。系统中唯一的连续参数在 Strategy 的 conditional_probabilities 和 Knowledge 的先验 π 上。

| operator | 符号 | variables | conclusion | 势函数 ψ | theory 来源 |
|----------|------|-----------|------------|---------|------------|
| **implication** | → | [A, B] | B | ψ=0 iff A=1,B=0 | [§2.1](../theory/03-propositional-operators.md) |
| **equivalence** | ↔ | [A, B] | None | ψ=1 iff A=B | [§2.3](../theory/03-propositional-operators.md) |
| **contradiction** | ⊗ | [A, B] | None | ψ=0 iff A=1,B=1 | [§2.4](../theory/03-propositional-operators.md) |
| **complement** | ⊕ | [A, B] | None | ψ=1 iff A≠B | [§2.5](../theory/03-propositional-operators.md) |
| **disjunction** | ∨ | [A₁,...,Aₖ] | None | ψ=0 iff all Aᵢ=0 | [§2.2](../theory/03-propositional-operators.md) |
| **conjunction** | ∧ | [A₁,...,Aₖ,M] | M | ψ=1 iff M=(A₁∧...∧Aₖ) | [§1](../theory/03-propositional-operators.md) |

### 3.3 来源

- `source="standalone"`：独立的结构关系（如规范化产生的 equivalence candidate，或人工标注的 contradiction）。有自己的 lifecycle（candidate → permanent）。
- `source="formal_expr:<strategy_id>"`：从 FormalExpr 展开产生。Lifecycle 由父 Strategy 决定。

---

## 4. FormalExpr（Strategy → Operator 展开）

FormalExpr 记录一个 Strategy 在 Operator 层的微观结构——由哪些 Operator 和中间 Knowledge 构成。

### 4.1 Schema

```
FormalExpr:
    formal_expr_id:          str
    source_strategy_id:      str                  # 展开的是哪个 Strategy
    operators:               list[Operator]        # 内部的原语算子
    intermediate_propositions: list[Knowledge]   # 展开时创建的中间命题
```

### 4.2 BP 编译规则

统一为一条规则：

```
if Strategy 有 FormalExpr:
    BP 在 FormalExpr 的 Operator 层运行
    Strategy 自身不需要 conditional_probabilities
    不确定性转移到中间 Knowledge 的先验 π 上
else:
    BP 将 Strategy 编译为 ↝ 因子
    使用 Strategy 的 conditional_probabilities
```

### 4.3 确定性策略的 FormalExpr

确定性策略的全部 Operator 均确定性，无中间 Knowledge 先验参数。

**演绎（deduction）：**
```
Strategy: premises=[A₁,...,Aₖ], conclusion=C

FormalExpr:
  intermediate: M
  operators:
    - conjunction(variables=[A₁,...,Aₖ,M], conclusion=M)
    - implication(variables=[M,C], conclusion=C)
```

**数学归纳（mathematical_induction）：**
```
Strategy: premises=[Base, Step], conclusion=Law

FormalExpr:
  intermediate: M
  operators:
    - conjunction(variables=[Base,Step,M], conclusion=M)
    - implication(variables=[M,Law], conclusion=Law)
```
与演绎结构相同。区别在于语义：Base=P(0), Step=∀n(P(n)→P(n+1)), Law=∀n.P(n)。

**归谬（reductio）：**
```
Strategy: premises=[R], conclusion=¬P
（内部推导链 P→Q, Q⊗R 在 steps 中描述）

FormalExpr:
  intermediate: P, Q, ¬P
  operators:
    - implication(variables=[P,Q], conclusion=Q)
    - contradiction(variables=[Q,R])
    - complement(variables=[P,¬P])
```

**排除（elimination）：**
```
Strategy: premises=[E₁,E₂,Exhaustiveness], conclusion=H₃

FormalExpr:
  intermediate: H₁, H₂, ¬H₁, ¬H₂, M
  operators:
    - contradiction(variables=[H₁,E₁])
    - contradiction(variables=[H₂,E₂])
    - complement(variables=[H₁,¬H₁])
    - complement(variables=[H₂,¬H₂])
    - conjunction(variables=[¬H₁,¬H₂,M], conclusion=M)
    - implication(variables=[M,H₃], conclusion=H₃)
```

**分情况讨论（case_analysis）：**
```
Strategy: premises=[Exhaustiveness,P₁,...,Pₖ], conclusion=C

FormalExpr:
  intermediate: A₁,...,Aₖ, M₁,...,Mₖ
  operators:
    - disjunction(variables=[A₁,...,Aₖ])
    - conjunction(variables=[A₁,P₁,M₁], conclusion=M₁)
    - implication(variables=[M₁,C], conclusion=C)
    - conjunction(variables=[A₂,P₂,M₂], conclusion=M₂)
    - implication(variables=[M₂,C], conclusion=C)
    - ...（每个 case 一对 conjunction + implication）
```

### 4.4 非确定性策略的 FormalExpr

非确定性策略使用确定性 Operator + 带先验 π 的中间 Knowledge，不确定性来自中间 Knowledge 的先验。

**溯因（abduction）：**
```
Strategy: premises=[supporting_knowledge], conclusion=H

FormalExpr:
  intermediate: O（预测，先验 π(O)）, Obs（观测）
  operators:
    - implication(variables=[H,O], conclusion=O)
    - equivalence(variables=[O,Obs])
```
不确定性来自中间 Knowledge O 的先验 π(O)。

**归纳（induction）：**
```
Strategy: premises=[Obs₁,...,Obsₙ], conclusion=Law

FormalExpr:
  intermediate: Instance₁,...,Instanceₙ（各自先验 π(Instanceᵢ)）
  operators:
    - implication(variables=[Law,Instance₁], conclusion=Instance₁)
    - equivalence(variables=[Instance₁,Obs₁])
    - implication(variables=[Law,Instance₂], conclusion=Instance₂)
    - equivalence(variables=[Instance₂,Obs₂])
    - ...（每个观测一对 implication + equivalence）
```
归纳是溯因的并行重复。不确定性来自各 Instanceᵢ 的先验。

**类比（analogy）：**
```
Strategy: premises=[SourceLaw, BridgeClaim], conclusion=Target

FormalExpr:
  intermediate: M
  operators:
    - conjunction(variables=[SourceLaw,BridgeClaim,M], conclusion=M)
    - implication(variables=[M,Target], conclusion=Target)
```
与演绎结构相同。不确定性来自 BridgeClaim 的先验 π(BridgeClaim)。

**外推（extrapolation）：**
```
Strategy: premises=[KnownLaw, ContinuityClaim], conclusion=Extended

FormalExpr:
  intermediate: M
  operators:
    - conjunction(variables=[KnownLaw,ContinuityClaim,M], conclusion=M)
    - implication(variables=[M,Extended], conclusion=Extended)
```
与类比结构相同。不确定性来自 ContinuityClaim 的先验。

### 4.5 FormalExpr 层级规则

- FormalExpr **只在 global 层产生**。Local 层的 Strategy 没有 FormalExpr。
- FormalExpr 中新创建的中间 Knowledge 直接写在 global 层（content 存在 global Knowledge 上，这是 global 层存储 content 的唯一例外）。
- 确定性策略的 FormalExpr 可以在分类确认时**自动生成**（微观结构由 type 决定）。
- 非确定性策略的 FormalExpr 需要 reviewer/agent **手动创建**中间 Knowledge 并赋先验。

---

## 5. 规范化（Canonicalization）

规范化是将 local canonical 节点映射到 global canonical 节点的过程——从包内身份到跨包身份。

### 5.1 映射决策：premise 与 conclusion 的区别

当新包中的 local Knowledge 与全局图中已有 Knowledge 语义匹配时，处理方式取决于**该 Knowledge 在 local 图中的角色**：

**作为 premise 的 Knowledge → 直接 merge**

如果 local Knowledge 在 local 图中仅作为 premise 使用，且与已有 global Knowledge 匹配，则直接绑定到该 global Knowledge。全局图上的 prior 和 belief 保持不变，不因为新包的加入而更新。

**作为 conclusion 的 Knowledge → 创建 equivalence candidate Operator**

如果 local Knowledge 在 local 图中作为某个 Strategy 的 conclusion，且与已有 global Knowledge 匹配，**不**直接 merge 为同一个 global Knowledge。而是：

1. 为 local conclusion 创建新的 global Knowledge
2. 在新旧两个 global Knowledge 之间创建一个 `Operator(operator=equivalence, source="standalone", stage=candidate)`

理由：两个不同包独立得出的结论语义相似，不代表它们是同一个命题。它们之间的等价关系需要经过 review 确认后才能升格为 permanent。直接 merge 会跳过这一审查步骤。

Canonicalization 步骤同时创建 placeholder 参数记录：新 global claim Knowledge 的 PriorRecord（placeholder prior）。具体值由后续 review 步骤确定。

**同时作为 premise 和 conclusion 的 Knowledge → 走 conclusion 路径**

如果一个 local Knowledge 既是某个 Strategy 的 conclusion，又是另一个 Strategy 的 premise，按 conclusion 规则处理（创建新 global Knowledge + equivalence candidate Operator）。理由：该 Knowledge 有独立的推理来源，不应静默合并。

**无匹配 → create_new**

为前所未见的命题创建新的 global Knowledge。

### 5.2 参与规范化的节点类型

**所有知识类型都参与全局规范化：** claim、setting、question、template。

- **claim**：跨包身份统一是 BP 的基础
- **setting**：不同包可能描述相同背景，统一后可被多个推理引用
- **question**：同一科学问题可被多个包提出
- **template**：相同命题模式应跨包共享

### 5.3 匹配策略

**Embedding 相似度（主要）**：余弦相似度，阈值 0.90。

**TF-IDF 回退**：无 embedding 模型时使用。

**过滤规则：**

- 仅相同 `type` 的候选者才有资格
- Template 额外比较自由变量结构（`parameters` 字段）

### 5.4 CanonicalBinding

```
CanonicalBinding:
    local_canonical_id:     str
    global_canonical_id:    str
    package_id:             str
    version:                str
    decision:               str    # "match_existing" | "create_new" | "equivalent_candidate"
    reason:                 str    # 匹配原因（如 "cosine similarity 0.95"）
```

### 5.5 Strategy 提升

Knowledge 规范化完成后，local Strategy 提升到全局图：

1. 从 CanonicalBinding 构建 `lcn_ → gcn_` 映射
2. 从全局 Knowledge 元数据构建 `ext: → gcn_` 映射（跨包引用解析）
3. 对每个 local Strategy，解析所有 premise 和 conclusion ID（weak_points 是自由文本，无需 ID 解析）
4. 含未解析引用的 Strategy 被丢弃（记录在 `unresolved_cross_refs` 中）

**Global Strategy 不携带 steps。** Local Strategy 的 `steps`（推理过程文本）保留在 local canonical 层。Global Strategy 只保留结构信息（type、stage、premises、conclusion），不复制推理内容。需要查看推理细节时，通过 CanonicalBinding 回溯到 local 层。

### 5.6 Global 层的内容引用

Global 层**通常不存储内容**——Knowledge 的 content 通过 `representative_lcn` 引用 local 层，Strategy 的 steps 保留在 local 层。

- **Global Knowledge** 通过 `representative_lcn` 引用 local canonical Knowledge 获取 content。当多个 local Knowledge 映射到同一 global Knowledge 时，选择一个作为代表，所有映射记录在 `member_local_nodes` 中。
- **Global Strategy** 不携带 `steps`（§5.5）。推理过程的文本保留在 local 层的 Strategy 中。

**例外：FormalExpr 创建的中间 Knowledge。** FormalExpr 展开时新创建的 Knowledge（如 prediction）没有 local 来源，其 content 直接存储在 global Knowledge 上（见 §4.5）。

需要查看具体内容时，通过 CanonicalBinding 回溯到 local 层。Global 层是**结构索引**，local 层是**内容仓库**——FormalExpr 中间 Knowledge 是唯一的例外。

---

## 6. 关于撤回（retraction）

Gaia IR 中没有 retraction 类型。撤回是一个**操作**：为目标 Knowledge 关联的所有 Strategy 添加新的 StrategyParamRecord，将 conditional_probabilities 中的**所有条目**设为 Cromwell 下界 ε（对 noisy-AND 的 [q₁,...,qₖ] 全部设为 ε，对 soft_implication 的 [p₁, p₂] 全部设为 ε）。该 Knowledge 实质上变成孤岛，belief 回到 prior。图结构不变——图是不可变的。

---

## 7. 与原 Gaia IR 的映射

### 7.1 概念映射

| 原概念 | 新概念 | 变更说明 |
|--------|--------|---------|
| KnowledgeNode | **Knowledge** | 保留原名，schema 不变 |
| FactorNode | **Strategy** | 改名 + 重构（统一 type，删除 subgraph） |
| FactorNode.category + reasoning_type | Strategy.type | 合并为单一字段 |
| FactorNode.subgraph | **FormalExpr**（独立实体） | 从 FactorNode 字段提升为独立实体 |
| reasoning_type=equivalent | **Operator**(operator=equivalence) | 从推理声明移为结构约束 |
| reasoning_type=contradict | **Operator**(operator=contradiction) | 从推理声明移为结构约束 |
| — | **Operator**(operator=complement) | 新增 |
| — | **Operator**(operator=disjunction) | 新增 |
| — | **Operator**(operator=conjunction) | 新增 |
| — | **Operator**(operator=implication) | 新增 |

### 7.2 已知的 Future Work

| 缺口 | 说明 | 影响 |
|------|------|------|
| **量词 / 绑定变量** | `∀n.P(n)` 是 Template `P(n)` 的全称闭包，Gaia IR 无法表达"闭包"关系 | 数学归纳的 Template↔Claim 关系不完整 |
| **soft_implication 作为 Operator** | 当 FormalExpr 部分展开时，某些子链仍为 ↝，需要 soft_implication 作为 Operator 类型 | 当前 Operator 只有确定性类型 |
| **Relation 类型（Issue #62）** | Contradiction/Support 作为一等公民 Relation | 可能影响 Operator 设计 |

---

## 8. 设计决策记录

| 决策 | 理由 |
|------|------|
| Strategy 保持 noisy-AND 语义 | [03-propositional-operators.md §5](../theory/03-propositional-operators.md) 证明 ∧ + ↝ 是最基本的多前提组合；9 种策略全部可用 noisy-AND 表达 |
| Operator 从 Strategy 分离 | ↔/⊗/⊕ 是确定性命题算子，不是推理声明；分离后 Strategy 纯粹为 ↝ 载体 |
| FormalExpr 作为独立实体 | 推理层和计算层的分离点；避免 Strategy 承担计算语义 |
| 确定性策略视为"有 trivial FormalExpr" | 统一 BP 编译规则为一条：有 FormalExpr → Operator 层运行；无 → ↝ 编译 |
| type 合并三个字段 | category/reasoning_type/link_type 的合法组合高度受限，实为同一维度 |
| conditional_probabilities 为 list[float] | noisy-AND 每前提一个 qᵢ；soft_implication 两个参数 [p₁, p₂]；统一为 list |
| 9 种命名策略自带 FormalExpr | 每种策略的微观结构由 theory 预定义，分类确认即获得 FormalExpr |

---

## 源代码

- `libs/graph_ir/models.py` -- `LocalCanonicalGraph`, `LocalCanonicalNode`（= local `Knowledge`）, `FactorNode`（将重命名为 `Strategy`）
- `libs/storage/models.py` -- `GlobalCanonicalNode`（= global `Knowledge`）, `CanonicalBinding`
- `libs/global_graph/canonicalize.py` -- `canonicalize_package()`
- `libs/global_graph/similarity.py` -- `find_best_match()`
- *Future:* `libs/graph_ir/operator.py` -- `Operator`, `FormalExpr`
