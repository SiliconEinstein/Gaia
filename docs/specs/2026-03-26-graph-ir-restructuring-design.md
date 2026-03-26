# Design: Gaia IR 重构 — 推理层与计算层分离

| 属性 | 值 |
|------|---|
| 日期 | 2026-03-26 |
| 状态 | Draft |
| 影响文档 | `docs/foundations/gaia-ir/` 全部文件, `docs/foundations/bp/`, `docs/foundations/theory/04-reasoning-strategies.md` |
| 前置依赖 | Theory 重构完成（`docs/foundations/theory/` 01-07） |

---

## 1. 动机

Theory 层完成了大重构，定义了 9 种推理策略、完整的命题算子体系（{¬, ∧, π} + 派生算子 + ↝），以及因子图的势函数映射。当前 Gaia IR 存在以下结构性问题：

1. **FactorNode 混淆两层语义**：既是作者的"推理声明"（Layer 2 — 科学本体），又是 BP 的"计算因子"（Layer 3 — 计算方法）。`reasoning_type` 字段混合了算子（equivalent, contradict）和策略（induction, abduction）。

2. **算子集不完整**：缺少 ⊕（互补）、∨（析取），导致归谬、排除、分情况讨论三种策略无法在 Gaia IR 中表示。

3. **策略集不完整**：9 种策略中仅覆盖 3 种（entailment ≈ deduction, induction, abduction），缺少类比、外推、归谬、排除、数学归纳、分情况讨论。

4. **策略到算子的映射未定义**：Theory 为每种策略定义了完整的微观结构（算子组合），但 Gaia IR 没有对应的表示机制。

## 2. 核心设计：推理层与计算层分离

### 2.1 第一性原理

Theory 自身有清晰的分层：

- **Layer 2（科学本体）**：知识类型、推理策略、↝ 的宏观语义 — 面向人（作者、reviewer）
- **Layer 3（计算方法）**：因子图势函数、BP 消息传递 — 面向机器

当前 FactorNode 试图同时服务两层。本设计将其分离为独立实体。

### 2.2 实践观察

> 实践中，最重要的算子是 soft implication（↝）。多数推理很难严格化，也无法继续细化。

知识形态分布：

```
~99%  ↝ 粗链接："前提支持结论，理由是 [steps]"，无法或不需要展开
 ~1%  严格关系：两个 claim 等价 / 矛盾
≪1%   完整 Jaynes 展开：→ + ↔ + ⊗ + 中间节点网络
```

设计应围绕 ↝ 这个最常见的用例优化，同时为完整的 Jaynes 展开提供出口。

## 3. 四实体架构

### 3.1 总览

```
Knowledge          命题（变量节点）
    ├── claim / setting / question / template

Strategy             推理声明（↝ 层，noisy-AND）
    ├── type: infer | 9 strategies | soft_implication | toolcall | proof
    ├── premises + conclusion
    ├── conditional_probabilities

Operator             结构约束（Jaynes 确定性算子）
    ├── operator: equivalence | contradiction | complement
    │            | implication | disjunction | conjunction

FormalExpr           Strategy → Operator 的展开
    ├── source_strategy_id
    ├── operators + intermediate_knowledges
```

**读法：** 一个 Strategy 连接多个 Knowledge。当 Strategy 有 FormalExpr 时，BP 在 Operator 层运行；否则 BP 编译 Strategy 为 ↝ 因子。

### 3.2 Knowledge（原 KnowledgeNode）

命题节点。Schema 与原 KnowledgeNode 基本一致，仅改名。

```
Knowledge:
    id:                     str              # lcn_ 或 gcn_ 前缀
    type:                   str              # claim | setting | question | template
    parameters:             list[Parameter]  # 仅 template：自由变量列表
    source_refs:            list[SourceRef]
    metadata:               dict | None

    # ── local 层 ──
    content:                str | None

    # ── 来源追溯 ──
    provenance:             list[PackageRef] | None

    # ── global 层 ──
    representative_lcn:     LocalCanonicalRef | None
    member_local_nodes:     list[LocalCanonicalRef] | None
```

**四种类型不变：**

| type | 先验 π | 参与 BP | 说明 |
|------|--------|---------|------|
| **claim** | 有 | 是 | 唯一携带真值的类型 |
| **setting** | 无 | 否 | 背景上下文 |
| **question** | 无 | 否 | 开放探究 |
| **template** | 无 | 否 | 含自由变量的命题模式 |

### 3.3 Strategy（原 FactorNode）

推理声明。表示"前提通过某种推理支持结论"。是 ↝ 的载体，采用 noisy-AND 语义。

```
Strategy:
    strategy_id:    str                # lcs_ 或 gcs_ 前缀（local/global canonical strategy）
    scope:          str                # "local" | "global"
    stage:          str                # initial | candidate | permanent

    # ── 统一类型 ──
    type:           str                # 见 §3.3.1

    # ── 连接 ──
    premises:       list[str]          # Knowledge IDs（仅 claim premise 创建 BP 边）
    conclusion:     str | None         # 单个输出 Knowledge

    # ── 条件概率（值在 parameterization 层） ──
    # type ∈ {infer, None}:        [q₁,...,qₖ], qᵢ = P(C=1 | Aᵢ=1, 其余前提=1)
    # type = soft_implication:     [p₁, p₂],    p₁ = P(C=1|A=1), p₂ = P(C=0|A=0)
    # type ∈ {9 strategies}:       不需要（有 FormalExpr，参数在 Operator 层）
    conditional_probabilities: list[float] | None

    # ── local 层 ──
    steps:          list[Step] | None
    weak_points:    list[str] | None

    # ── 追溯 ──
    source_ref:     SourceRef | None
    metadata:       dict | None        # 包含 context: list[str] 等
```

#### 3.3.1 统一类型字段

`type` 合并了原 FactorNode 的 `category`、`reasoning_type`、`link_type` 三个维度：

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

#### 3.3.2 Noisy-AND 语义

Strategy 的隐含结构是 ∧ + ↝：

```
A₁ ──(q₁)──┐
A₂ ──(q₂)──┤  AND → C
 ⋮          │
Aₖ ──(qₖ)──┘

P(C=1 | all Aᵢ=1) = ∏ qᵢ
P(C=1 | any Aᵢ=0) = 0     （所有前提充分且必要）
```

每个前提都是**必要的**（缺一不可），且各自**独立贡献**条件概率 qᵢ。

**对应 theory：** theory §5（多前提推理中的 ∧ + ↝）定义了 ∧ + ↝ 为最基本的多前提组合模式。Noisy-AND 是其实用特化：每个前提有独立的条件概率参数。

**Soft-implication 模式：** 当 type=soft_implication 时，Strategy 恰好有一个 premise，参数为 [p₁, p₂]，对应 theory §4 的完整二参数 ↝(p₁, p₂) 模型。

#### 3.3.3 Lifecycle

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

type=toolcall 和 type=proof 不经历 lifecycle — 创建时语义即明确。

#### 3.3.4 BP 参与规则

与原 FactorNode 一致：

- 仅 type=claim 的 premise 参与 BP 消息传递
- Non-claim premise（setting, question, template）在 BP 中跳过
- weak_points 不参与 BP，影响体现在 conditional_probabilities 的估值上

### 3.4 Operator（新实体）

结构约束。表示两个或多个 Knowledge 之间的确定性逻辑关系。对应 theory Layer 3（因子图层）的势函数。

```
Operator:
    operator_id:    str                # lco_ 或 gco_ 前缀（local/global canonical operator）
    scope:          str                # "local" | "global"

    operator:       str                # 算子类型（见下表）
    variables:      list[str]          # 连接的 Knowledge IDs（有序）
    conclusion:     str | None         # 有向算子的输出（无向算子为 None）

    stage:          str                # candidate | permanent
    source:         str                # "standalone" | "formal_expr:<strategy_id>"
    source_ref:     SourceRef | None
    metadata:       dict | None
```

**算子类型与势函数：**

| operator | 符号 | variables | conclusion | 势函数 ψ | theory 来源 |
|----------|------|-----------|------------|---------|------------|
| implication | → | [A, B] | B | ψ=0 iff A=1,B=0 | §2.1 |
| equivalence | ↔ | [A, B] | None | ψ=1 iff A=B | §2.3 |
| contradiction | ⊗ | [A, B] | None | ψ=0 iff A=1,B=1 | §2.4 |
| complement | ⊕ | [A, B] | None | ψ=1 iff A≠B | §2.5 |
| disjunction | ∨ | [A₁,...,Aₖ] | None | ψ=0 iff all Aᵢ=0 | §2.2 |
| conjunction | ∧ | [A₁,...,Aₖ,M] | M | ψ=1 iff M=(A₁∧...∧Aₖ) | §1 |

所有算子都是**确定性的**（ψ ∈ {0, 1}，无自由参数）。系统中唯一的连续参数在 Strategy 的 conditional_probabilities 和 Knowledge 的先验 π 上。

**来源：**

- `source="standalone"`：独立的结构关系（如规范化产生的 equivalence candidate，或人工标注的 contradiction）。有自己的 lifecycle（candidate → permanent）。
- `source="formal_expr:<strategy_id>"`：从 FormalExpr 展开产生。Lifecycle 由父 Strategy 决定。

### 3.5 FormalExpr（新实体）

Strategy 在 Operator 层的展开。记录一个 Strategy 的微观结构 — 由哪些 Operator 和中间 Knowledge 构成。

```
FormalExpr:
    formal_expr_id:          str
    source_strategy_id:      str                  # 展开的是哪个 Strategy
    operators:               list[Operator]        # 内部的原语算子
    intermediate_knowledges: list[Knowledge]   # 展开时创建的中间命题
```

**BP 编译规则（统一为一条）：**

```
if Strategy 有 FormalExpr:
    BP 在 FormalExpr 的 Operator 层运行
    Strategy 自身不需要 conditional_probabilities
    不确定性转移到中间 Knowledge 的先验 π 上
else:
    BP 将 Strategy 编译为 ↝ 因子
    使用 Strategy 的 conditional_probabilities
```

#### 3.5.1 九种策略的 FormalExpr

每种命名策略都有预定义的微观结构。当 Strategy 的 type 被确定为某种策略时，其 FormalExpr 由策略类型决定。

以下为各策略的标准展开模板（对应 theory `04-reasoning-strategies.md`）：

**确定性策略（全部 Operator 均确定性，无中间先验）：**

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

**非确定性策略（确定性 Operator + 带先验的中间 Knowledge）：**

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

#### 3.5.2 FormalExpr 的层级

- FormalExpr **只在 global 层产生**（与原 subgraph 一致）。Local 层的 Strategy 没有 FormalExpr。
- FormalExpr 中新创建的中间 Knowledge 直接写在 global 层（content 存在 global Knowledge 上，这是 global 层存储 content 的唯一例外）。
- 确定性策略的 FormalExpr 可以在分类确认时**自动生成**（微观结构由 type 决定）。
- 非确定性策略的 FormalExpr 需要 reviewer/agent **手动创建**中间 Knowledge 并赋先验。

## 4. 与原 Gaia IR 的映射

| 原概念 | 新概念 | 变更说明 |
|--------|--------|---------|
| KnowledgeNode | **Knowledge** | 改名，schema 不变 |
| FactorNode | **Strategy** | 改名 + 重构（见下） |
| FactorNode.reasoning_type | Strategy.type | 合并 category + reasoning_type + link_type |
| FactorNode.subgraph | **FormalExpr**（独立实体） | 从 FactorNode 字段提升为独立实体 |
| reasoning_type=equivalent | **Operator**(operator=equivalence) | 从 Strategy 移出 |
| reasoning_type=contradict | **Operator**(operator=contradiction) | 从 Strategy 移出 |
| — | **Operator**(operator=complement) | 新增 |
| — | **Operator**(operator=disjunction) | 新增 |
| — | **Operator**(operator=conjunction) | 新增 |

## 5. 对其他文档的影响

### 5.1 parameterization.md

需要更新：

- `FactorParamRecord` → `StrategyParamRecord`，`factor_id` → `strategy_id`
- probability 结构从单个 float 变为 `conditional_probabilities: list[float]`
- 新增规则：9 种命名策略不需要 StrategyParamRecord（参数在 FormalExpr 的中间 Knowledge 先验上）
- 新增规则：中间 Knowledge 需要 PriorRecord
- Cromwell's rule 不变

### 5.2 belief-state.md

- BeliefState.beliefs 仍只对 type=claim 的 Knowledge
- bp_run 需要记录编译路径（Strategy 直接编译 vs FormalExpr 编译）

### 5.3 overview.md

- LocalCanonicalGraph / GlobalCanonicalGraph 的组成更新为 Knowledge + Strategy + Operator
- 三写原子性规则更新

### 5.4 规范化（canonicalization）

- Knowledge 的规范化逻辑不变
- Strategy 的 factor lifting 逻辑适配新字段名
- 规范化产生的 equivalent candidate 现在是 Operator(source="standalone", stage=candidate)，不再是 FactorNode

## 6. 已知的 Future Work

| 缺口 | 说明 | 影响 |
|------|------|------|
| **量词 / 绑定变量** | `∀n.P(n)` 是 Template `P(n)` 的全称闭包，Gaia IR 无法表达"闭包"关系 | 数学归纳的 Template↔Claim 关系不完整 |
| **soft_implication 作为 Operator** | 当 FormalExpr 部分展开时，某些子链仍为 ↝，需要 soft_implication 作为 Operator 类型 | 当前 Operator 只有确定性类型 |
| **Relation 类型（Issue #62）** | Contradiction/Support 作为一等公民 Relation | 可能影响 Operator 设计 |

## 7. 设计决策记录

| 决策 | 理由 |
|------|------|
| Strategy 保持 noisy-AND 语义 | Theory §5 证明 ∧ + ↝ 是最基本的多前提组合；9 种策略全部可用 noisy-AND 表达 |
| Operator 从 Strategy 分离 | ↔/⊗/⊕ 是确定性命题算子，不是推理声明；分离后 Strategy 纯粹为 ↝ 载体 |
| FormalExpr 作为独立实体 | 推理层和计算层的分离点；避免 Strategy 承担计算语义 |
| 确定性策略视为"有 trivial FormalExpr" | 统一 BP 编译规则为一条：有 FormalExpr → Operator 层运行；无 → ↝ 编译 |
| type 合并三个字段 | category/reasoning_type/link_type 的合法组合高度受限，实为同一维度 |
| conditional_probabilities 为 list[float] | noisy-AND 每前提一个 qᵢ；soft_implication 两个参数 [p₁, p₂]；统一为 list |
| 9 种命名策略自带 FormalExpr | 每种策略的微观结构由 theory 预定义，分类确认即获得 FormalExpr |
