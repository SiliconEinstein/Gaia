# Gaia IR — 结构定义（v2 草稿）

> **Status:** Draft — 基于现有 gaia-ir.md 重构，整合 Issue #231（template → claim with parameters）
>
> **⚠️ Protected Contract Layer** — 本目录定义 CLI↔LKM 结构契约。变更需要独立 PR 并经负责人审查批准。

Gaia IR 编码推理超图的拓扑结构——**什么连接什么**。它不包含任何概率值。

概率参数见 [parameterization.md](parameterization.md)。推理输出见 [belief-state.md](belief-state.md)。三者的关系见 [overview.md](overview.md)。具体的概率推理算法见 [bp/](../bp/) 层。

在当前收缩后的 v2 里，persistent IR 只保留两类全局对象：

- **GlobalCanonicalKnowledgeStore**：跨包统一后的 canonical Knowledge
- **CanonicalBinding**：`lcn -> gcn` 的身份映射

而完整的推理结构仍主要保留在 local graph 中：

- `Knowledge`
- `Strategy`
- `Operator`

如果下游运行时需要“全局可计算图”，那是从若干 local graph 通过 `CanonicalBinding` **派生编译**出来的视图，而不是 protected contract 中持久存储的 global strategy/operator 集合。

从 authoring 视角看，Gaia IR 的 local graph 由三种实体构成：

| 实体 | 角色 | 语义 |
|------|------|------|
| **Knowledge** | 命题 | 表达科学断言、背景或问题 |
| **Operator** | 确定性逻辑约束 | 表达命题间的逻辑关系（真值表完全确定） |
| **Strategy** | 不确定推理声明 | 表达"前提以某种概率支持结论"的推理判断 |

读者先理解图中有什么节点（Knowledge），再理解节点之间的确定性结构关系（Operator），最后理解不确定的推理如何建模（Strategy）。

---

## 1. Knowledge（知识）

Knowledge 表示命题。**Claim 是唯一携带概率（prior + belief）的类型。**

### 1.1 Schema

Local 和 global 使用同一个 data class，字段按层级使用：

```
Knowledge:
    id:                     str              # lcn_ 或 gcn_ 前缀
    type:                   str              # claim | setting | question
    parameters:             list[Parameter]  # 全称命题的量化变量（封闭命题为空列表）
    metadata:               dict | None      # 含 refs: list[str]（相关 Knowledge IDs、来源引用等）

    # ── local 层 ──
    content:                str | None       # 知识内容（local 层存储，global 层通常为 None）

    # ── 来源追溯 ──
    provenance:             list[PackageRef] | None   # 贡献包列表

    # ── global 层 ──
    representative_lcn:     LocalCanonicalRef | None  # 代表性 local Knowledge（内容从此获取）
    local_members:          list[LocalCanonicalRef] | None  # 所有映射到此的 local Knowledge
```

**各层字段使用：**

| 字段 | Local | Global |
|------|-------|--------|
| `id` | `lcn_` 前缀，SHA-256 包+内容寻址 | `gcn_` 前缀，注册中心分配 |
| `content` | 有值（唯一存储位置） | 通常为 None（通过 `representative_lcn` 取回内容） |
| `provenance` | 有值（来源包） | 有值（贡献包列表） |
| `representative_lcn` | None | 有值（引用 local Knowledge 获取内容） |
| `local_members` | None | 有值（所有映射到此的 local Knowledge） |

**身份规则**：local 层 `id = lcn_{SHA-256(package_id + type + content + sorted(parameters))[:16]}`。ID 包含 `package_id`，因此不同包中相同内容的节点有**不同的** lcn_id。跨包的语义等价由 global canonicalization 通过 embedding 相似度判定，而非 ID 相等。

**内容存储**：所有知识内容都应来源于某个 local Knowledge。Global 层通过 `representative_lcn` 引用获取内容，不重复存储。即使是 server curation / review 产出的新 claim，也推荐作为特殊来源的 local/curation package 提交，再经 canonicalization 接入 global 层。

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
- **全称 claim**（`parameters` 非空）：含量化变量的通用定律。如 `∀{x}. superconductor({x}) → zero_resistance({x})`。全称 claim 有真值（可被反例推翻），携带概率，可通过 induction 获得支持，通过 deduction 实例化为封闭 claim。

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

全称 claim 和封闭 claim 之间形成自然的归纳-演绎循环：

- **归纳**：多个封闭实例通过 induction Strategy 支持全称 claim → 全称的 belief 上升
- **演绎**：全称 claim 通过 deduction Strategy 预测新封闭实例 → 实例的 belief 跟随全称
- **反例**：发现与全称矛盾的封闭 claim → contradiction Operator → 全称的 belief 下降

#### setting（背景设定）

研究的背景信息或动机性叙述。不携带概率。可作为 Strategy 的 background（上下文依赖）或 refs（弱引用）。

示例：某个领域的研究现状、实验动机、未解决挑战、近似方法或理论框架、全称 claim 实例化时的变量绑定（如 "x = YBCO"）。

#### question（问题）

探究制品，表达待研究的方向。不携带概率。可作为 Strategy 的 background 或 refs。

示例：未解决的科学问题、后续调查目标。

### 1.3 Helper Claim

Helper claim **不是新的 Knowledge 类型**。它仍然是普通的 `claim`，只是承担了中间推理、关系节点化或模板化复用的角色。

两类 helper claim：

- **语义型 helper claim**：如 `prediction`、`instance`、`bridge`、`continuity`。这些 claim 有独立科学语义，可被 review、引用、复用、反驳。
- **结构型 helper claim**：由 Operator 自动产出的标准结果 claim，如 `not_both_true(A,B)`、`same_truth(A,B)`、`A∧B`。它们主要用于将结构关系节点化，使后续 Strategy/Operator 可以直接引用。

编码规则：

- helper claim 仍使用 `Knowledge(type=claim)`
- 如需参数化模式，直接使用 `parameters`
- 建议在 `metadata.helper_kind` 中标记 helper 种类

标准 helper claim 列表与命名约定见 [helper-claims.md](helper-claims.md)。

---

## 2. Operator（结构约束）

Operator 表示两个或多个 Knowledge 之间的**确定性逻辑关系**——真值表完全确定，无自由参数。

theory 推导见 [命题算子](../theory/03-propositional-operators.md)。

### 2.1 Schema

```
Operator:
    operator_id:    str              # lco_ 前缀（local operator）

    operator:       str              # 算子类型（见 §2.2）
    variables:      list[str]        # 连接的 Knowledge IDs（有序）
    conclusion:     str              # standard result claim / helper claim

    metadata:       dict | None      # 含 refs: list[str] 等
```

`conclusion` 的语义是：**该 Operator 在图中的标准结果 claim**。它总是一个 `claim`。

- 对 `implication` / `conjunction`，`conclusion` 延续现有用法，表示推理链中的输出 claim
- 对 `equivalence` / `contradiction` / `complement` / `disjunction`，`conclusion` 是 compiler-generated 的 helper claim，使这些结构关系也能被后续工作引用

### 2.2 算子类型与真值表

| operator | 符号 | variables | conclusion | 真值约束 | 说明 |
|----------|------|-----------|------------|---------|------|
| **implication** | → | [A, B] | B | A=1 时 B 必须=1 | A 成立则 B 必须成立 |
| **equivalence** | ↔ | [A, B] | helper claim（如 `same_truth(A,B)`） | A=B | 真值必须一致 |
| **contradiction** | ⊗ | [A, B] | helper claim（如 `not_both_true(A,B)`） | ¬(A=1 ∧ B=1) | 不能同时为真 |
| **complement** | ⊕ | [A, B] | helper claim（如 `opposite_truth(A,B)`） | A≠B | 真值必须相反（XOR） |
| **disjunction** | ∨ | [A₁,...,Aₖ] | helper claim（如 `any_true(A₁,...,Aₖ)`） | ¬(all Aᵢ=0) | 至少一个为真 |
| **conjunction** | ∧ | [A₁,...,Aₖ,M] | M | M=(A₁∧...∧Aₖ) | M 等于所有 Aᵢ 的合取 |

**关键性质：** Operator 没有概率参数——它编码的是逻辑结构（"A 和 B 矛盾"），不是推理判断（"作者认为 A 蕴含 B"）。后者由 Strategy 承载。

### 2.3 存在位置

在 protected contract 中，Operator 只存在于 **local graph**：

- **顶层 `operators` 数组**：独立的局部结构关系。例如：
  - 作者或 curator 标注的 contradiction
  - curator package 中声明的 equivalence
  - 某个包内显式写出的 implication

- **FormalStrategy 内部的 `formal_expr.operators`**：FormalExpr 展开产生的算子，嵌入在 FormalStrategy 中，不独立存在。

这里没有 persistent 的 `global operator set`。

如果服务器 curation 或 review 想表达新的结构关系，推荐做法是：**产出一个特殊来源的 local/curation package**，在该 package 中提交相应的 local Operator，而不是直接写入全局硬结构。

### 2.4 不变量

1. `variables` 中的所有 ID 必须引用同 graph 中存在的 Knowledge
2. `variables` 中的 Knowledge 类型必须是 `claim`（Operator 只连接有真值的命题）
3. `conclusion` 必须引用同 graph 中存在的 `claim`
4. `implication`：`conclusion = variables[-1]`
5. `conjunction`：`conclusion = variables[-1]` = M
6. `equivalence` / `contradiction` / `complement` / `disjunction`：`conclusion` 必须是标准 helper claim，且**不**要求出现在 `variables` 中
7. 关系型 Operator 的 `conclusion` 由编译器或 reviewer 按标准命名约定生成，不允许作者借此手写任意主观结论

---

## 3. Strategy（推理声明）

Strategy 表示推理声明——前提通过某种推理支持结论。Strategy 是不确定性的载体：**所有概率参数都在 Strategy 层**（通过 [parameterization](parameterization.md)），Operator 层纯确定性。

### 3.1 基本概念

一个基本 Strategy 表达一条概率性推理：

```
premises  ——↝(p)——→  conclusion
```

其中 ↝ 表示"前提以条件概率 p 支持结论"。

Strategy 有三种形态（类层级），支持多分辨率推理——同一图可在不同粒度上做概率推理：

| 形态 | 说明 | 独有字段 |
|------|------|---------|
| **Strategy**（基类，可实例化） | 叶子推理（单条 ↝） | — |
| **CompositeStrategy**(Strategy) | 含子策略，可递归嵌套 | `sub_strategies` |
| **FormalStrategy**(Strategy) | 含确定性 Operator 展开 | `formal_expr` |

所有形态折叠时均表达为单条 ↝（参数来自 parameterization 层）。展开时进入内部结构。

### 3.2 Schema

**Strategy（基类）**：

```
Strategy:
    strategy_id:    str              # lcs_ 前缀（local strategy）
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
    sub_strategies:  list[Strategy]  # 子策略（可包含 Strategy / CompositeStrategy / FormalStrategy）
```

**FormalStrategy(Strategy)**——新增：

```
FormalStrategy(Strategy):
    formal_expr:     FormalExpr      # 确定性 Operator 展开（必填）

FormalExpr:
    operators:       list[Operator]  # 只包含确定性 Operator
```

FormalExpr 中涉及的中间 Knowledge 分两类：

- **显式 helper claim**：凡是由 `Operator.conclusion` 暴露出来、需要被其他 Strategy/Operator 引用的 helper claim，应写入顶层 `knowledges`
- **纯局部结构节点**：如仅服务于单个 FormalExpr 的内部辅助节点，可由 compiler 自动生成

当前 v2 的推荐做法是：**只要某个中间 claim 需要跨 operator 复用、被后续步骤引用或未来可能参与概率传播，就应显式进入 `knowledges`。**

**各层字段使用：**

| 字段 | Local | Global |
|------|-------|--------|
| `strategy_id` | `lcs_` 前缀 | —（persistent global 层不存 Strategy） |
| `premises`/`conclusion` | `lcn_` ID | — |
| `steps` | 有值 | — |

**身份规则：**

`strategy_id = lcs_{SHA-256(package_id + normalized_local_structure)[:16]}`

Strategy 的持久身份只在 local package 内定义。

如果下游系统需要把 local Strategy 投影到全局 claim 上，可以在运行时生成一个临时的 `LocalStrategyRef(package_id, version, lcs_id)` 或等价结构；这类投影对象不属于 protected IR contract。

### 3.3 类型字段

| type | 参数化模型 | 形态 |
|------|-----------|------|
| **`infer`** | 完整条件概率表（CPT）：2^k 参数（默认 MaxEnt 0.5） | Strategy |
| **`noisy_and`** | ∧ + 单参数 p | Strategy |
| **`deduction`** | 确定性（p=1） | FormalStrategy |
| **`abduction`** | 非确定性 | CompositeStrategy（含 FormalStrategy 子部分） |
| **`induction`** | 非确定性 | CompositeStrategy（含 FormalStrategy 子部分） |
| **`analogy`** | 非确定性 | CompositeStrategy（含 FormalStrategy 子部分） |
| **`extrapolation`** | 非确定性 | CompositeStrategy（含 FormalStrategy 子部分） |
| **`reductio`** | 确定性（p=1） | FormalStrategy |
| **`elimination`** | 确定性（p=1） | FormalStrategy |
| **`mathematical_induction`** | 确定性（p=1） | FormalStrategy |
| **`case_analysis`** | 确定性（p=1） | FormalStrategy |
| **`toolcall`** | 另行定义 | Strategy |
| **`proof`** | 另行定义 | Strategy |

> **设计决策：** `independent_evidence` 和 `contradiction` 不作为 Strategy 类型——它们是结构关系，直接用 Operator（equivalence / contradiction）表达。原 `soft_implication` 归并到 `infer`（单前提/低维特例）。原 `None` 合并到 `infer`。

### 3.4 参数化语义

Strategy 的参数化模型由 `type` 决定。概率参数存储在 [parameterization](parameterization.md) 层，不在 IR 中。

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

**适用范围：前提是联合必要条件的推理。** 包括演绎（所有前提必须成立）、类比（source + bridge 都必须成立）等。

**不适用于归纳和溯因**——它们的前提是独立贡献的，不是全有全无。少一个实例/证据不会让支持归零。这些策略必须用 CompositeStrategy 分解为并行子结构（见 §3.6）。

### 3.5 三种形态

#### 3.5.1 基本 Strategy（叶子 ↝）

最简单的形态——表达单条条件概率关系。参数化模型取决于 type（`infer` → 2^k 参数 CPT，`noisy_and` → 单参数 p）。

#### 3.5.2 CompositeStrategy（嵌套子策略）

将一个推理分解为多个子策略。`sub_strategies` 可以包含任意形态（Strategy / CompositeStrategy / FormalStrategy），支持递归嵌套。

折叠时（不展开）：表达为单条 ↝。展开时：递归进入每个子策略的内部结构。

#### 3.5.3 FormalStrategy + FormalExpr（确定性展开）

用于有已知确定性微观结构的命名策略。`formal_expr` 只包含 Operator（确定性），不包含不确定的 ↝。

**关键约束：FormalExpr 内部没有概率参数——不确定性转移到中间 Knowledge 的先验 π 上。**

### 3.6 命名策略的组装方式

#### 确定性策略 → 纯 FormalStrategy

前提联合必要，推理过程确定性。

**演绎（deduction）**：`premises=[A₁,...,Aₖ], conclusion=C`
```
FormalStrategy(type=deduction):
  formal_expr:
    - conjunction([A₁,...,Aₖ, M], conclusion=M)
    - implication([M, C], conclusion=C)
```

**数学归纳（mathematical_induction）**：`premises=[Base, Step], conclusion=Law`
```
FormalStrategy(type=mathematical_induction):
  formal_expr:
    - conjunction([Base, Step, M], conclusion=M)
    - implication([M, Law], conclusion=Law)
```
结构与演绎相同。语义区分：Base=P(0), Step=∀n(P(n)→P(n+1)), Law=∀n.P(n)。

**归谬（reductio）**：`premises=[R], conclusion=¬P`
```
FormalStrategy(type=reductio):
  formal_expr:
    - implication([P, Q], conclusion=Q)
    - contradiction([Q, R], conclusion=Contra_Q_R)
    - complement([P, ¬P], conclusion=Comp_P_notP)
```

**排除（elimination）**：`premises=[E₁, E₂, Exhaustiveness], conclusion=H₃`
```
FormalStrategy(type=elimination):
  formal_expr:
    - contradiction([H₁, E₁], conclusion=Contra_H₁_E₁)
    - contradiction([H₂, E₂], conclusion=Contra_H₂_E₂)
    - complement([H₁, ¬H₁], conclusion=Comp_H₁_notH₁)
    - complement([H₂, ¬H₂], conclusion=Comp_H₂_notH₂)
    - conjunction([¬H₁, ¬H₂, M], conclusion=M)
    - implication([M, H₃], conclusion=H₃)
```

**分情况讨论（case_analysis）**：`premises=[Exhaustiveness, P₁,...,Pₖ], conclusion=C`
```
FormalStrategy(type=case_analysis):
  formal_expr:
    - disjunction([A₁,...,Aₖ], conclusion=Disj_A₁_..._Aₖ)
    - conjunction([A₁, P₁, M₁], conclusion=M₁), implication([M₁, C], conclusion=C)
    - conjunction([A₂, P₂, M₂], conclusion=M₂), implication([M₂, C], conclusion=C)
    - ...（每个 case 一对 conjunction + implication）
```

#### 非确定性策略 → CompositeStrategy（含 FormalStrategy 子部分）

前提独立贡献或推理过程非确定性。不确定的 ↝ 部分用 Strategy 子节点表达，确定的结构用 FormalStrategy 子节点表达。

以下示例中，`Eq_*` / `Contra_*` / `Comp_*` / `Disj_*` 表示由对应 Operator 自动生成的 helper claim。

**溯因（abduction）**：`premises=[supporting_knowledge], conclusion=H`

溯因的不确定性在于"假说是否是最佳解释"。确定部分是 H→O 和 O↔Obs 的逻辑结构。

```
CompositeStrategy(type=abduction, premises=[supporting_knowledge], conclusion=H):
  sub_strategies:
    - Strategy(type=noisy_and, premises=[H], conclusion=O)        ← 不确定的 ↝
    - FormalStrategy(formal_expr:
        - implication([H, O], conclusion=O)
        - equivalence([O, Obs], conclusion=Eq_O_Obs)
      )                                                            ← 确定的结构
```

**归纳（induction）**：`premises=[Obs₁,...,Obsₙ], conclusion=Law`

归纳的每个实例独立贡献支持——不是联合必要。分解为并行的子推理，每个都是确定性的 implication + equivalence 结构。

```
CompositeStrategy(type=induction, premises=[Obs₁,...,Obsₙ], conclusion=Law):
  sub_strategies:
    - FormalStrategy(formal_expr:
        - implication([Law, Instance₁], conclusion=Instance₁)
        - equivalence([Instance₁, Obs₁], conclusion=Eq_Instance₁_Obs₁)
      )
    - FormalStrategy(formal_expr:
        - implication([Law, Instance₂], conclusion=Instance₂)
        - equivalence([Instance₂, Obs₂], conclusion=Eq_Instance₂_Obs₂)
      )
    - ...（每个观测一组 implication + equivalence）
```

累积效应由多条独立证据的概率在 Law 节点上汇聚实现——更多一致的观测 → Law 的 belief 自然上升。单个反例（Obs 与 Instance 不一致）通过 equivalence Operator 传播，削弱 Law 的 belief。

**类比（analogy）**：`premises=[SourceLaw, BridgeClaim], conclusion=Target`

前提联合必要（source 和 bridge 都要成立），但 bridge 的可信度本身是不确定的。

```
CompositeStrategy(type=analogy, premises=[SourceLaw, BridgeClaim], conclusion=Target):
  sub_strategies:
    - Strategy(type=noisy_and, premises=[SourceLaw, BridgeClaim], conclusion=Target)
    - FormalStrategy(formal_expr:
        - conjunction([SourceLaw, BridgeClaim, M], conclusion=M)
        - implication([M, Target], conclusion=Target)
      )
```

不确定性集中在 BridgeClaim 的先验 π(BridgeClaim)。

**外推（extrapolation）**：`premises=[KnownLaw, ContinuityClaim], conclusion=Extended`

与类比结构相同。不确定性在 ContinuityClaim 的先验。

```
CompositeStrategy(type=extrapolation, premises=[KnownLaw, ContinuityClaim], conclusion=Extended):
  sub_strategies:
    - Strategy(type=noisy_and, premises=[KnownLaw, ContinuityClaim], conclusion=Extended)
    - FormalStrategy(formal_expr:
        - conjunction([KnownLaw, ContinuityClaim, M], conclusion=M)
        - implication([M, Extended], conclusion=Extended)
      )
```

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
  ├── reviewer 分类为命名策略 → CompositeStrategy / FormalStrategy
  ├── reviewer 确认为 noisy_and → type=noisy_and
  ├── reviewer 分解 → CompositeStrategy + sub_strategies
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
- **Background**：上下文依赖，任意类型。不参与概率推理。
- **Refs**：存储在 `metadata.refs` 中的 ID 列表。不参与图结构。

### 3.10 不变量

1. `premises` 中的 Knowledge 类型必须是 `claim`
2. `conclusion` 的 Knowledge 类型必须是 `claim`（如果非 None）
3. `background` 中的 Knowledge 类型可以是任意（claim / setting / question）
4. FormalStrategy 的 `formal_expr` 必填；CompositeStrategy 的 `sub_strategies` 必填且非空
5. `sub_strategies` 和 `formal_expr` 不同时出现（形态互斥由类层级保证）
6. FormalExpr 只包含 Operator（不包含 Strategy）
7. `noisy_and` 仅用于前提联合必要的场景；归纳/溯因必须用 CompositeStrategy 分解

---

## 4. 规范化（Canonicalization）

规范化是将 local canonical 实体接入 global 结构的过程——从包内身份到跨包 canonical 命题层。

### 4.1 Claim 规范化：只处理命题身份

在当前方案里，global 层只负责 **Knowledge 身份统一**。

这意味着：

- canonicalization 只回答“这个 local Knowledge 是否就是某个已有 global Knowledge”
- canonicalization 不回答“这条推理是否应进入全局”
- canonicalization 也不负责生成全局的 Strategy / Operator 对象

Claim 规范化中需要区分的只有：

- **CanonicalBinding（身份映射）**：local Knowledge 和 global Knowledge 是**同一个 canonical knowledge** 的不同表示。它是纯引用关系，不提供新证据，不创建新的图结构。
- **create_new**：当前没有身份匹配的 global Knowledge，需要创建新的 canonical knowledge。

如果将来确实需要表达“两个不同 canonical claim 之间存在等价/矛盾/互补关系”，那应由某个 local graph（例如 curator package）显式写出，再通过后续 runtime projection 使用，而不是由 canonicalization 自动产生。

### 4.1.1 为什么不能按 premise / conclusion 角色分流

如果 canonicalization 取决于 local 角色，就会产生两个问题：

1. **同一命题会被错误拆成多个 global Knowledge**
   仅因为它在某个包里出现在 conclusion 位置，就人为新建 global node。

2. **global 层会被迫承担本不属于它的推理/审核语义**
   例如为了保留某条 local reasoning 的独立性，被迫引入额外的 global structure。

因此，是否复用已有 global Knowledge，应只由命题身份决定。

### 4.2 参与规范化的 Knowledge 类型

**所有知识类型都参与全局规范化：** claim（含全称 claim）、setting、question。

- **claim**：跨包身份统一是概率推理的基础。全称 claim（parameters 非空）跨包共享同一通用定律
- **setting**：不同包可能描述相同背景，统一后可被多个推理引用
- **question**：同一科学问题可被多个包提出

### 4.3 匹配策略

**Embedding 相似度（主要）**：余弦相似度，阈值 0.90。

**TF-IDF 回退**：无 embedding 模型时使用。

**过滤规则：**

- 仅相同 `type` 的候选者才有资格
- 含 `parameters` 的 claim 额外比较参数结构：count + types 按序匹配，忽略 name（α-equivalence，见 Issue #234）

### 4.4 CanonicalBinding

```
CanonicalBinding:
    local_canonical_id:     str
    global_canonical_id:    str
    package_id:             str
    version:                str
    decision:               str    # "match_existing" | "create_new"
    reason:                 str    # 判定原因（如 "cosine similarity 0.95"）
```

### 4.5 没有 persistent 的 Strategy / Operator 提升

Knowledge 规范化完成后，**local Strategy 和 local Operator 不会被持久提升为 global core 对象。**

这意味着：

- 没有 persistent 的 `gcs_` global Strategy
- 也没有 persistent 的 `gco_` global Operator
- global core 不试图回答“有哪些全局被接受的推理边”

这么做的原因是：

- claim identity 统一之后，global 核心语义已经成立
- local graph 仍然完整保留了推理结构、operator 结构和自然语言步骤
- 把 strategy/operator 再升格到 global core，通常只会增加 dedupe、版本、追溯和撤回复杂度

### 4.5.1 Server Curation 的表达方式

如果服务器 curation、review agent 或 curator 想表达新的推理或结构关系，推荐做法是：

- 产出一个**特殊来源的 local/curation package**
- 在该 package 中正常提交 local `Knowledge / Strategy / Operator`
- 再让这些 local claim 通过 `CanonicalBinding` 接入已有 global Knowledge

也就是说，curation 不是“直接改 global graph”，而是“提交一种特殊来源的 local graph”。

这样做的好处是：

- provenance 自然
- 版本自然
- 可挑战性自然
- Graph IR core 不需要知道 review 机制的细节

### 4.6 派生的 Runtime Projection（非 protected contract）

如果下游运行时确实需要“全局可计算图”，推荐做法是：

1. 选择若干 local package / curation package
2. 用 `CanonicalBinding` 将其中的 `lcn_` 映射到 `gcn_`
3. 把 local Strategy / Operator 投影成一个**临时 runtime view**

这个 runtime view 可以包含：

- 映射到 `gcn_` 的 endpoints
- 指回 local 来源的 `LocalStrategyRef(package_id, version, lcs_id)`
- 指回 local 来源的 `LocalOperatorRef(package_id, version, lco_id)`

但它是：

- derived
- rebuildable
- implementation-facing

而不是 protected Graph IR contract 的核心对象。

### 4.6.1 未解析引用

含未解析跨包引用的 local Strategy / Operator，不应在 runtime projection 中被静默忽略。

更合理的做法是：

- 阻止该次 projection / build 进入可运行状态
- 或在运行时层保留 pending / unresolved 记录

但这属于下游实现策略，不应反过来改变 global core schema。

### 4.7 Global 层的内容引用

Global canonical Knowledge **通常不存储内容**：

- **Global Knowledge** 通过 `representative_lcn` 引用 local canonical Knowledge 获取 content。当多个 local Knowledge 映射到同一 global Knowledge 时，选择一个作为代表，所有映射记录在 `local_members` 中。

因此：

- global 层主要是**canonical knowledge index**
- local 层仍然是**内容仓库与结构仓库**

### 4.8 Strategy 形态与层级规则

**三种形态只在 persistent local graph 中出现：**

- **基本 Strategy**：local 层（compiler 产出）
- **CompositeStrategy**：local 层（作者在包内构造层次化论证）
- **FormalStrategy**：local 层（compiler 识别 type 后自动生成 FormalExpr）

如果运行时需要跨包消费它们，应在 runtime projection 中临时映射，而不是持久写回 global core。

**中间 Knowledge 的归属：**

- FormalExpr 展开时可能创建中间 Knowledge（FormalExpr 中引用但不在 premises/conclusion 中的 Knowledge ID）。
- 对关系型 Operator，`conclusion` 对应的 helper claim 应优先作为显式 `Knowledge(type=claim)` 落图，以便后续引用。
- Local 层的中间 Knowledge 获得 `lcn_` ID，归属于当前包。
- 如果某个中间 Knowledge 需要进入 global 层，它应先作为某个 local graph 中的显式 Knowledge 出现，再经 canonicalization 获得 `gcn_`。

**FormalExpr 的生成方式：**

- **确定性策略**（deduction, reductio, elimination, mathematical_induction, case_analysis）：FormalExpr 由 type 唯一确定，可在分类确认时**自动生成**（compiler 或 reviewer 均可触发）。
- **非确定性策略**（abduction, induction, analogy, extrapolation）：表达为 CompositeStrategy，其 sub_strategies 中的 FormalStrategy 子部分可自动生成，但 CompositeStrategy 的整体分解结构（哪些子策略、哪些中间 Knowledge）需要 reviewer/agent 判断。中间 Knowledge 的先验概率通过 parameterization 层的 PriorRecord 赋值，不在 IR 中指定。

---

## 5. 关于撤回（Retraction）

Gaia IR 中没有 retraction 类型。当前方案下，撤回也**不应表现为修改 global core 图结构**。

更合理的理解是：

- 某个来源 package 被运行时排除
- 某条 local Strategy 在 runtime projection 中被禁用
- 某组参数记录在 parameterization / resolution policy 中失效

也就是说，撤回主要是**来源选择与运行时编译策略**的问题，而不是 persistent Graph IR core 的结构操作。

---

## 6. 设计决策记录

| 决策 | 理由 |
|------|------|
| Knowledge 三种类型（删除 template） | Issue #231：全称命题（∀{x}.P({x})）有真值，应携带概率。统一为 claim with parameters。Template 概念保留在 Gaia Language 编写层 |
| Operator 从 Strategy 分离 | ↔/⊗/⊕ 是确定性命题算子，不是推理声明。Operator 无概率参数，Strategy 有 |
| independent_evidence / contradiction 用 Operator 表达 | 它们是结构关系，不是推理判断。直接用 equivalence / contradiction Operator |
| Operator 统一产出 result/helper claim | 关系型 Operator 也需要可引用的标准结果 claim，因此 `conclusion` 不再只服务于有向算子 |
| Strategy type 合并 | 原 None 合并到 infer，原 soft_implication 归并到 infer（单前提/低维特例） |
| infer vs noisy_and 区分 | infer = 完整 CPT（2^k 参数），noisy_and = ∧ + 单参数 p。大多数推理使用 noisy_and |
| noisy_and 仅限联合必要场景 | 归纳/溯因的前提是独立贡献的，不能用 noisy_and。必须用 CompositeStrategy 分解为并行子结构 |
| Strategy 三形态类层级 | Strategy（叶子 ↝）、CompositeStrategy（递归嵌套）、FormalStrategy（确定性展开）——形态由结构决定，type 与形态正交 |
| FormalExpr 只包含 Operator | 不确定部分留在 CompositeStrategy 的 sub_strategies 中，FormalExpr 纯确定性 |
| FormalExpr 作为 FormalStrategy 的嵌入字段 | 1:1 关系，不需要独立实体；FormalExpr 无独立 ID 和 lifecycle |
| helper claim 仍是 claim | 不新增实体类型；helper catalog 单独维护 |
| Claim canonicalization 只处理命题身份 | CanonicalBinding 只回答 `lcn` 是否映射到某个 `gcn`；它不自动生成 global Strategy / Operator |
| global core 收缩为 Knowledge + Binding | persistent global 层只保留 canonical Knowledge 与 `CanonicalBinding`；推理边与结构边留在 local graph，运行时按需投影 |
| conditional_probabilities 在 parameterization 层 | 概率参数不属于图结构；通过 StrategyParamRecord 存储。type 决定参数数量 |
| 多分辨率展开 | 任何 Strategy 折叠时均表达为单条 ↝；展开时进入内部结构。具体推理算法由 bp/ 层定义 |
| 图的不可变性 | 撤回主要体现在来源选择、runtime projection 与参数失效上，不删除 persistent core 图结构 |

### 已知 Future Work

| 缺口 | 说明 | 影响 |
|------|------|------|
| **α-equivalence（Issue #234）** | 含 parameters 的 claim 匹配时需要忽略变量名 | Canonicalization 精度 |
| **Gaia IR Validator（Issue #233）** | 每次 IR 更新时的结构验证 | 数据完整性 |
| **Compiler dispatch（Issue #236）** | Gaia Language template → IR 知识类型的编译规则 | CLI 端实现 |
| **helper claim catalog** | 需要收敛标准 helper claim 的最小列表和命名规则 | 跨文档一致性 |

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
| soft_implication | 合并到 infer | infer 的单前提/低维特例 |
| None (type) | 合并到 infer | 未分类推理统一用 infer |
| independent_evidence (Strategy type) | 直接用 Operator(equivalence) | 结构关系，不是推理声明 |
| contradiction (Strategy type) | 直接用 Operator(contradiction) | 结构关系，不是推理声明 |
