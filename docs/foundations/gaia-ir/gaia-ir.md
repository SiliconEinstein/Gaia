# Gaia IR — 结构定义

> **Status:** Target design — 基于 [06-factor-graphs.md](../theory/06-factor-graphs.md) 和 [04-reasoning-strategies.md](../theory/04-reasoning-strategies.md) 设计
>
> **⚠️ Protected Contract Layer** — 本目录定义 CLI↔LKM 结构契约。变更需要独立 PR 并经负责人审查批准。详见 [documentation-policy.md](../../documentation-policy.md#12-变更控制)。
>
> **设计依据：** [Gaia IR 重构设计文档](../../specs/2026-03-26-graph-ir-restructuring-design.md)

Gaia IR 编码推理超图的拓扑结构——**什么连接什么**。它不包含任何概率值。

Gaia IR 由三种实体构成：**Knowledge**（知识）、**Strategy**（推理声明）、**Operator**（结构约束）。Strategy 有三种形态：基础 Strategy（↝ 叶子）、CompositeStrategy（含子策略）和 FormalStrategy（含确定性展开 FormalExpr）。Knowledge 和 Strategy 承载作者的推理意图（Layer 2 — 科学本体），Operator 承载精确的逻辑结构（Layer 3 — 计算方法），FormalExpr 作为 FormalStrategy 的嵌入字段桥接两层。

概率参数见 [parameterization.md](parameterization.md)。BP 输出见 [belief-state.md](belief-state.md)。三者的关系见 [overview.md](overview.md)。

---

## 1. Knowledge（知识）

Knowledge 表示命题。Gaia 中有四种知识对象。**Claim 是唯一默认携带 probability 并参与 BP 的类型。**

### 1.1 Schema

Local 和 global 使用同一个 data class，字段按层级使用：

```
Knowledge:
    id:                     str              # lcn_ 或 gcn_ 前缀
    type:                   str              # claim | setting | question | template
    parameters:             list[Parameter]  # 仅 template：自由变量列表
    metadata:               dict | None      # 含 refs: list[str]（相关 Knowledge IDs、来源引用等）、其他自定义字段

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
| `content` | 有值（唯一存储位置） | 通常为 None（LKM 直接创建的 Knowledge 例外，包括 FormalExpr 中间 Knowledge） |
| `provenance` | 有值（来源包） | 有值（贡献包列表） |
| `representative_lcn` | None | 有值（引用 local Knowledge 获取内容） |
| `local_members` | None | 有值（所有映射到此的 local Knowledge） |

**身份规则**：local 层 `id = lcn_{SHA-256(package_id + type + content + sorted(parameters))[:16]}`。ID 包含 `package_id`，因此不同包中相同内容的节点有**不同的** lcn_id。跨包的语义等价由 global canonicalization 通过 embedding 相似度判定，而非 ID 相等。

**内容存储**：所有知识内容存储在 local 层的 `content` 字段上。Global 层通过 `representative_lcn` 引用获取内容，不重复存储。LKM 服务器直接创建的 global Knowledge（包括 FormalExpr 展开的中间 Knowledge）无 local 来源，content 直接存在 global 层。

### 1.2 四种知识类型

| type | 说明 | 参与 BP | 可作为 |
|------|------|---------|--------|
| **claim** | 封闭的科学断言 | 是（唯一 BP 承载者） | premise, background, conclusion, refs |
| **setting** | 背景信息 | 否 | background, refs |
| **question** | 待研究方向 | 否 | background, refs |
| **template** | 含自由变量的命题模式 | 否 | background, refs |

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

研究的背景信息或动机性叙述。不携带 probability，不参与 BP。可作为 Strategy 的 background（上下文依赖）或 refs（弱引用）。

示例：某个领域的研究现状、实验动机、未解决挑战、近似方法或理论框架。

#### question（问题）

探究制品，表达待研究的方向。不携带 probability，不参与 BP。可作为 Strategy 的 background 或 refs。

示例：未解决的科学问题、后续调查目标。

#### template（模板）

开放的命题模式，含自由变量。不直接参与 BP。核心作用是**桥梁**：将 setting 或 question 包装为 claim，使其获得概率语义。Template 到 claim 的实例化是 deduction 的特例（probability=1.0）。可作为 Strategy 的 background。

示例：`falls_at_rate({x}, {medium})`、`{method} can be applied in this {context}`、`∀{x}. wave({x}) → diffraction({x})`。

---

## 2. Strategy（推理声明）

Strategy 表示推理声明——前提通过某种推理支持结论。是 ↝（软蕴含）的载体，采用 noisy-AND 语义。

Strategy 有三种形态（类层级），支持**多分辨率 BP**——同一图在不同粒度做推理：

| 形态 | 说明 | 独有字段 |
|------|------|---------|
| **Strategy**（基类，可实例化） | 叶子推理，编译为 ↝ | — |
| **CompositeStrategy**(Strategy) | 含子策略，可递归嵌套 | `sub_strategies` |
| **FormalStrategy**(Strategy) | 含确定性 Operator 展开 | `formal_expr` |

所有形态折叠时均编译为 ↝（参数来自 [parameterization](parameterization.md) 层）。展开时进入内部结构。

### 2.1 Schema

**Strategy（基类）**——Local 和 global 使用同一个 data class，字段按层级使用：

```
Strategy:
    strategy_id:    str                # lcs_ 或 gcs_ 前缀（local/global canonical strategy）
    scope:          str                # "local" | "global"
    # ── 统一类型 ──
    type:           str | None         # 见 §2.2（与形态正交）；None = 未分类

    # ── 连接 ──
    premises:       list[str]          # claim Knowledge IDs（全部参与 BP）
    conclusion:     str | None         # 单个输出 Knowledge（必须是 claim）
    background:     list[str] | None   # 上下文 Knowledge IDs（任意类型，不参与 BP）

    # ── local 层 ──
    steps:          list[Step] | None  # 推理过程的分步描述

    # ── 追溯 ──
    metadata:       dict | None        # 含 refs: list[str]（相关 Knowledge IDs、来源引用等）

Step:
    reasoning:        str                # 该步的推理描述文本
    premises:         list[str] | None   # 该步引用的前提（可选）
    conclusion:       str | None         # 该步的结论（可选）
```

**CompositeStrategy(Strategy)**——继承所有基类字段，新增：

```
CompositeStrategy(Strategy):
    sub_strategies:  list[str]          # 子 Strategy IDs（可递归包含 CompositeStrategy）
```

**FormalStrategy(Strategy)**——继承所有基类字段，新增：

```
FormalStrategy(Strategy):
    formal_expr:     FormalExpr         # 确定性 Operator 展开（必填）
```

FormalExpr 是 data class（非顶层实体）：

```
FormalExpr:
    operators:               list[Operator]      # 确定性算子
```

中间 Knowledge 不需要显式列出——可从 operators 的 variables 推导：`{operators 中所有 Knowledge ID} - {premises} - {conclusion}`。中间 Knowledge 作为 global Knowledge 存储在 LKM 中。

**各层字段使用：**

| 字段 | Local | Global |
|------|-------|--------|
| `strategy_id` | `lcs_` 前缀，由源构造确定性计算 | `gcs_` 前缀，由 Strategy 提升后的全局构造计算 |
| `scope` | `"local"` | `"global"` |
| `premises`/`conclusion` | `lcn_` ID | `gcn_` ID |
| `background` | 有值（`lcn_` IDs） | 有值（`gcn_` IDs） |
| `steps` | 有值（推理过程文本） | None |

`steps` 记录推理过程的分步文本。一个 Strategy 可以有一步或多步。每步的 `premises` 和 `conclusion` 是可选的——有些步骤只是描述性的推理过程，不显式关联特定的 Knowledge。Strategy 的顶层 `premises` 和 `conclusion` 是整个推理链的输入和最终输出。

**身份规则：** Strategy ID 由 `scope + type + sorted(premises) + conclusion` 确定性计算：`{prefix}_{sha256[:16]}`。Local 层前缀 `lcs_`，global 层前缀 `gcs_`。Strategy 提升（lcn→gcn 重写）后 premises/conclusion 变化，因此 global Strategy 与其源 local Strategy 有不同的 `strategy_id`。

> **与 Knowledge 的对偶关系：** Knowledge 用 `lcn_`/`gcn_` 前缀 + `content`/`representative_lcn` 字段区分层级；Strategy 用 `lcs_`/`gcs_` 前缀 + `scope` + `steps` 字段区分层级。两者结构对偶。

### 2.2 统一类型字段

`type` 合并了原 FactorNode 的 `category`、`reasoning_type`、`link_type` 三个维度为单一字段：

```
type:
    # ── 推理声明（premises → conclusion，经历 lifecycle） ──
    None                       # 未分类，通用 CPT（2^K 参数，默认 MaxEnt 0.5）
    infer                      # noisy-AND：conjunction + ↝（单参数 q，p₂=1 隐含）
    soft_implication            # 单前提完整二参数模型 [p₁, p₂]

    # 9 种命名策略（经历 lifecycle，对应 FormalStrategy）
    deduction                  # 演绎：∧ + →，确定性
    abduction                  # 溯因：→ + ↔，非确定性
    induction                  # 归纳：n×(→ + ↔)，非确定性
    analogy                    # 类比：∧ + →（含 BridgeClaim），非确定性
    extrapolation              # 外推：∧ + →（含 ContinuityClaim），非确定性
    reductio                   # 归谬：→ + ⊗ + ⊕，确定性
    elimination                # 排除：n×⊗ + n×⊕ + ∧ + →，确定性
    mathematical_induction     # 数学归纳：∧ + →，确定性
    case_analysis              # 分情况讨论：∨ + n×(∧ + →)，确定性

    # ── 关系声明（conclusion=None，断言 premises 之间的关系） ──
    independent_evidence       # 独立证据等价：多个 Knowledge 有独立证据支持等价
    contradiction              # 矛盾：恰好 2 个 Knowledge 被判定为矛盾

    # ── 非推理（不经历 lifecycle） ──
    toolcall                   # 计算 / 工具调用
    proof                      # 形式化证明
```

**从 type 可派生的属性：**

| type | 参数化模型 | 经历 lifecycle | 形态 | conclusion |
|------|-----------|---------------|------|-----------|
| None | 通用 CPT: 2^K（默认 MaxEnt 0.5） | 是 | Strategy 或 CompositeStrategy | 有 |
| infer | noisy-AND: [q] | 是 | Strategy 或 CompositeStrategy | 有 |
| soft_implication | [p₁, p₂] | 是 | Strategy 或 CompositeStrategy | 有 |
| deduction | — | 是 | FormalStrategy | 有 |
| abduction | — | 是 | FormalStrategy | 有 |
| induction | — | 是 | FormalStrategy | 有 |
| analogy | — | 是 | FormalStrategy | 有 |
| extrapolation | — | 是 | FormalStrategy | 有 |
| reductio | — | 是 | FormalStrategy | 有 |
| elimination | — | 是 | FormalStrategy | 有 |
| mathematical_induction | — | 是 | FormalStrategy | 有 |
| case_analysis | — | 是 | FormalStrategy | 有 |
| independent_evidence | [q] | 是 | Strategy | None |
| contradiction | [q] | 是 | Strategy | None |
| toolcall | 另行定义 | 否 | Strategy | 有 |
| proof | 另行定义 | 否 | Strategy | 有 |

### 2.3 参数化语义

Strategy 的参数化模型由 `type` 决定。概率参数本身存储在 [parameterization](parameterization.md) 层，不在 IR 中。

**通用模式（type=None）：** 未分类的 Strategy 使用完整条件概率表（CPT），K 个前提需要 2^K 个参数。按 MaxEnt 原则，默认值全为 0.5（最大熵 = 无信息）。

**Noisy-AND 模式（type=infer）：** 单参数 `[q]`，结构为 conjunction + ↝：

```
conjunction(A₁,...,Aₖ → M)  +  ↝(M → C, p₁=q, p₂=1)
```

- P(C=1 | all Aᵢ=1) = q
- P(C=1 | any Aᵢ=0) = 0 （所有前提充分且必要，p₂=1 隐含）

每个前提的可信度由其自身的 prior 表达（在 parameterization 层），Strategy 的参数 q 表达推理本身的可信度。对应 theory [§5](../theory/03-propositional-operators.md)（∧ + ↝）。

**BP 编译器展开：** `infer` 在 IR 中是叶子 Strategy（不存储 FormalExpr）。conjunction + ↝ 的分解由 BP 编译器隐式完成——模式固定，不需要显式存储。这与 9 种命名策略不同：后者的 FormalExpr 因 case 而异，需要存储在 IR 中。

**Soft-implication 模式（type=soft_implication）：** 单前提，参数为 `[p₁, p₂]`，对应 theory [§4](../theory/04-reasoning-strategies.md) 的完整二参数 ↝(p₁, p₂) 模型：p₁ = P(C=1|A=1)，p₂ = P(C=0|A=0)。

**关系声明（type=independent_evidence / contradiction）：** 断言 premises 之间的关系，conclusion=None。参数为 `[q]`（判定的置信度）。确认后由 BP 编译器编译为对应的确定性 Operator：

- `independent_evidence`：premises=[A, B, ...]（≥2），编译为 pairwise equivalence Operator
- `contradiction`：premises=[A, B]（恰好 2），编译为 contradiction Operator

这两种 Strategy 将 Operator 层的确定性关系提升为可审查的推理声明——identification 本身是不确定的判断（有 conditional probability），确认后才成为确定性结构约束。具体的匹配判定由 review 服务和 agent 研究实现，IR 层只提供结构基础。

### 2.4 Lifecycle

Strategy 的形态（类）本身即反映其状态——不需要 `initial` 阶段：

```
Strategy(type=None)                               ← 未分类（图结构可见）
  ├── reviewer 分类为命名策略 → FormalStrategy + formal_expr
  ├── reviewer 分类为 infer → type=infer（noisy-AND，单参数）
  ├── reviewer 分解 → CompositeStrategy + sub_strategies
  └── 保持 type=None（通用 CPT）
```

IR 中的所有 Strategy 都是已确认的结构——候选项由 review 层管理（见 [issue #230](https://github.com/SiliconEinstein/Gaia/issues/230)）。

**演化规则：**

- 分类为命名策略时，创建 FormalStrategy 替换原 Strategy。
- 分解为子策略时，创建 CompositeStrategy 替换原 Strategy。type 保留原值。
- type=toolcall 和 type=proof 的语义在创建时就是明确的。
- Template 实例化（deduction 特例）可直接创建 FormalStrategy。

### 2.5 合法组合与不变量

| type | 可能的形态 |
|------|-----------|
| **None** | Strategy（叶子 ↝）或 CompositeStrategy（分解） |
| **infer** | Strategy（叶子 ↝）或 CompositeStrategy（分解） |
| **soft_implication** | Strategy（叶子 ↝）或 CompositeStrategy（分解） |
| **9 种命名策略** | FormalStrategy |
| **independent_evidence** | Strategy |
| **contradiction** | Strategy |
| **toolcall** | Strategy |
| **proof** | Strategy |

**不变量：**

1. `premises` 中的 type 必须是 `claim`
2. `conclusion` 的 type 必须是 `claim`（如果 conclusion 非 None）
3. `background` 中的 type 可以是任意类型（claim/setting/question/template）
4. FormalStrategy 的 `formal_expr` 必填；CompositeStrategy 的 `sub_strategies` 必填且非空
5. `sub_strategies` 和 `formal_expr` 不在同一个对象上出现（形态互斥由类层级保证）
6. `independent_evidence`：premises 数量 ≥ 2，conclusion=None；确认后编译为 pairwise equivalence Operator
7. `contradiction`：premises 数量恰好 2，conclusion=None；确认后编译为 contradiction Operator

### 2.6 Premise、Background 与 Refs 的区别

| 字段 | 位置 | 类型约束 | 参与 BP | 说明 |
|------|------|---------|---------|------|
| **premises** | 顶层字段 | 仅 claim | 是（创建 BP 边） | 推理的形式前提，前提为假会削弱结论 |
| **background** | 顶层字段 | 任意类型 | 否 | 上下文依赖，为推理提供背景但不参与概率计算 |
| **refs** | `metadata` 内 | 任意 | 否 | 弱相关的来源引用 |

- **Premise**：推理成立的必要条件，必须是 claim。所有 premise 参与 BP 消息传递（noisy-AND 的输入）。
- **Background**：上下文依赖，任意类型。不创建 BP 边，不影响 belief 计算。适用于不需要参与 BP 的 Knowledge（如绝对确定的公理、背景设定、待研究方向等）。Review 在评估 Strategy probability 时应考虑 background 的内容。
- **Refs**：存储在 `metadata.refs` 中的 ID 列表。不参与图结构（不创建边），不参与 BP。用于记录弱相关的来源引用。

> **Weak points**（推理薄弱环节）不在 IR 中存储——它们属于 review 层的产出。如需在 IR 中记录，可通过 `metadata` 携带。

### 2.7 BP 参与规则

**Premise**：必须是 claim，全部参与 BP 消息传递（noisy-AND 的输入）。Non-claim Knowledge 不能出现在 premises 中——它们属于 background。

**Background**：不参与 BP。上下文依赖在 BP 中不可见——无论其类型是 claim 还是 setting 等。Review 在分配 Strategy probability 时应考虑 background 的内容。

**Refs**：在 metadata 中，不参与图结构，不参与 BP。

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

    metadata:       dict | None      # 含 refs: list[str]（相关 Knowledge IDs、来源引用等）
```

### 3.2 算子类型与势函数

所有算子都是**确定性的**（ψ ∈ {0, 1}，无自由参数）。系统中唯一的连续参数在 [parameterization](parameterization.md) 层（Strategy 的 conditional_probabilities 和 Knowledge 的先验 π）。

| operator | 符号 | variables | conclusion | 势函数 ψ | theory 来源 |
|----------|------|-----------|------------|---------|------------|
| **implication** | → | [A, B] | B | ψ=0 iff A=1,B=0 | [§2.1](../theory/03-propositional-operators.md) |
| **equivalence** | ↔ | [A, B] | None | ψ=1 iff A=B | [§2.3](../theory/03-propositional-operators.md) |
| **contradiction** | ⊗ | [A, B] | None | ψ=0 iff A=1,B=1 | [§2.4](../theory/03-propositional-operators.md) |
| **complement** | ⊕ | [A, B] | None | ψ=1 iff A≠B | [§2.5](../theory/03-propositional-operators.md) |
| **disjunction** | ∨ | [A₁,...,Aₖ] | None | ψ=0 iff all Aᵢ=0 | [§2.2](../theory/03-propositional-operators.md) |
| **conjunction** | ∧ | [A₁,...,Aₖ,M] | M | ψ=1 iff M=(A₁∧...∧Aₖ) | [§1](../theory/03-propositional-operators.md) |

### 3.3 两种存在位置

- **顶层 `operators` 数组**：独立的结构关系（如人工标注的 contradiction、规范化确认的 equivalence）。
- **`FormalStrategy.formal_expr.operators`**：FormalExpr 展开产生的算子，嵌入在 FormalStrategy 内部。

位置即来源，不需要额外的 `source` 字段。

---

## 4. FormalExpr（data class — FormalStrategy 的确定性展开）

FormalExpr 记录一个 FormalStrategy 在 Operator 层的微观结构——由哪些确定性 Operator 构成。FormalExpr 不是顶层实体，而是 FormalStrategy 的嵌入字段。

### 4.1 Schema

```
FormalExpr:
    operators:               list[Operator]        # 确定性算子
```

中间 Knowledge 从 operators 推导：`{operators 中所有 Knowledge ID} - {FormalStrategy.premises} - {FormalStrategy.conclusion}`。中间 Knowledge 作为 global Knowledge 存储在 LKM 中，不在 FormalExpr 中重复声明。

### 4.2 多分辨率 BP 编译规则

BP 编译接受 `expand_set`（需要展开的 Strategy ID 集合），支持同一图在不同粒度做推理：

```
compile(strategy, expand_set):
    if strategy.id not in expand_set:
        → 折叠：编译为 ↝ 因子（参数来自 StrategyParamRecord）
    elif isinstance(strategy, CompositeStrategy):
        for sub_id in strategy.sub_strategies:
            compile(get_strategy(sub_id), expand_set)    # 递归
    elif isinstance(strategy, FormalStrategy):
        for op in strategy.formal_expr.operators:
            → 确定性因子
        # 不确定性转移到中间 Knowledge 的先验 π 上
    else:
        → 叶子：编译为 ↝ 因子（参数来自 StrategyParamRecord）
```

**示例——三种粒度的 BP：**

```
S0 (CompositeStrategy, type=infer): A → D
  sub_strategies: [S1, S2]
  # StrategyParamRecord: [0.6]

  S1 (Strategy, type=infer): A → B
    # StrategyParamRecord: [0.9]

  S2 (FormalStrategy, type=deduction): B → D
    # StrategyParamRecord: [1.0]
    formal_expr: conjunction + implication
```

| expand_set | 因子图中的因子 |
|-----------|--------------|
| `{}` | S0 作为 ↝（最粗） |
| `{S0}` | S1 ↝ + S2 ↝ |
| `{S0, S2}` | S1 ↝ + S2 的确定性 Operator（最细） |

### 4.3 确定性策略的 FormalExpr

确定性策略的全部 Operator 均确定性，无中间 Knowledge 先验参数。

**演绎（deduction）：**
```
Strategy: premises=[A₁,...,Aₖ], conclusion=C

FormalExpr:
  operators:
    - conjunction(variables=[A₁,...,Aₖ,M], conclusion=M)
    - implication(variables=[M,C], conclusion=C)
```

**数学归纳（mathematical_induction）：**
```
Strategy: premises=[Base, Step], conclusion=Law

FormalExpr:
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
  operators:
    - implication(variables=[P,Q], conclusion=Q)
    - contradiction(variables=[Q,R])
    - complement(variables=[P,¬P])
```

**排除（elimination）：**
```
Strategy: premises=[E₁,E₂,Exhaustiveness], conclusion=H₃

FormalExpr:
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
  operators:
    - implication(variables=[H,O], conclusion=O)
    - equivalence(variables=[O,Obs])
```
不确定性来自中间 Knowledge O 的先验 π(O)。

**归纳（induction）：**
```
Strategy: premises=[Obs₁,...,Obsₙ], conclusion=Law

FormalExpr:
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
  operators:
    - conjunction(variables=[SourceLaw,BridgeClaim,M], conclusion=M)
    - implication(variables=[M,Target], conclusion=Target)
```
与演绎结构相同。不确定性来自 BridgeClaim 的先验 π(BridgeClaim)。

**外推（extrapolation）：**
```
Strategy: premises=[KnownLaw, ContinuityClaim], conclusion=Extended

FormalExpr:
  operators:
    - conjunction(variables=[KnownLaw,ContinuityClaim,M], conclusion=M)
    - implication(variables=[M,Extended], conclusion=Extended)
```
与类比结构相同。不确定性来自 ContinuityClaim 的先验。

### 4.5 FormalExpr 层级规则

- FormalStrategy（及其 FormalExpr）**只在 global 层产生**。Local 层的 Strategy 没有 formal_expr。
- FormalExpr 中新创建的中间 Knowledge 由 LKM 直接写在 global 层（content 存在 global Knowledge 上）。
- 确定性策略的 FormalExpr 可以在分类确认时**自动生成**（微观结构由 type 决定）。
- 非确定性策略的 FormalExpr 需要 reviewer/agent **手动创建**中间 Knowledge 并赋先验。
- CompositeStrategy 可以在 local 层或 global 层出现（作者可以在包内构造层次化论证）。

---

## 5. 规范化（Canonicalization）

规范化是将 local canonical 实体映射到 global canonical 实体的过程——从包内身份到跨包身份。

### 5.1 映射决策：身份映射与等价声明

规范化中存在两种本质不同的关系：

- **CanonicalBinding（身份映射）**：local Knowledge 和 global Knowledge 是**同一个命题**的不同表示。纯引用关系，不提供新证据，不创建图结构，不影响 BP。
- **Equivalence Operator（等价声明）**：两个独立的 global Knowledge 被声明为**等价**。两条独立推理链得出相同结论，这本身是新证据——创建确定性因子，BP 在两者之间传播 belief。

Gaia IR 提供这种区分的结构基础。具体的匹配判定和等价确认由 review 服务和后续 agent 研究等方法实现——IR 层不规定判定策略。

当新包中的 local Knowledge 与全局图中已有 Knowledge 语义匹配时，处理方式取决于**该 Knowledge 在 local 图中的角色**：

**作为 premise 的 Knowledge → CanonicalBinding（身份映射，无新证据）**

如果 local Knowledge 在 local 图中仅作为 premise（或 background）使用，且与已有 global Knowledge 匹配，则直接绑定到该 global Knowledge。全局图上的 prior 和 belief 保持不变，不因为新包的加入而更新。

**作为 conclusion 的 Knowledge → Equivalence candidate（等价声明，新证据）**

如果 local Knowledge 在 local 图中作为某个 Strategy 的 conclusion，且与已有 global Knowledge 匹配，**不**直接 merge 为同一个 global Knowledge。而是：

1. 为 local conclusion 创建新的 global Knowledge
2. 在新旧两个 global Knowledge 之间提议一个 equivalence Operator（候选项由 review 层管理，确认后写入 IR）

理由：两个不同包独立得出的结论语义相似，不代表它们是同一个命题。等价关系一旦确认，BP 会在两者之间传播 belief——这是新证据，不是简单的身份合并。

Canonicalization 步骤同时创建 placeholder 参数记录：新 global claim Knowledge 的 PriorRecord（placeholder prior）。具体值由后续 review 步骤确定。

**同时作为 premise 和 conclusion 的 Knowledge → 走 conclusion 路径**

如果一个 local Knowledge 既是某个 Strategy 的 conclusion，又是另一个 Strategy 的 premise，按 conclusion 规则处理（创建新 global Knowledge + equivalence candidate Operator）。理由：该 Knowledge 有独立的推理来源，不应静默合并。

**无匹配 → create_new**

为前所未见的命题创建新的 global Knowledge。

### 5.2 参与规范化的 Knowledge 类型

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
3. 对每个 local Strategy，解析所有 premise、conclusion 和 background ID
4. 含未解析引用的 Strategy 被丢弃（记录在 `unresolved_cross_refs` 中）

**Global Strategy 不携带 steps。** Local Strategy 的 `steps`（推理过程文本）保留在 local canonical 层。Global Strategy 只保留结构信息（type、premises、conclusion、形态及其字段），不复制推理内容。需要查看推理细节时，通过 CanonicalBinding 回溯到 local 层。

### 5.6 Global 层的内容引用

Global 层**通常不存储内容**——Knowledge 的 content 通过 `representative_lcn` 引用 local 层，Strategy 的 steps 保留在 local 层。

- **Global Knowledge** 通过 `representative_lcn` 引用 local canonical Knowledge 获取 content。当多个 local Knowledge 映射到同一 global Knowledge 时，选择一个作为代表，所有映射记录在 `local_members` 中。
- **Global Strategy** 不携带 `steps`（§5.5）。推理过程的文本保留在 local 层的 Strategy 中。

**例外：LKM 直接创建的 global Knowledge。** LKM 服务器直接创建的 Knowledge（包括 FormalExpr 展开的中间 Knowledge，见 §4.5）没有 local 来源，其 content 直接存储在 global Knowledge 上。

需要查看具体内容时，通过 CanonicalBinding 回溯到 local 层。Global 层是**结构索引**，local 层是**内容仓库**——LKM 直接创建的 Knowledge 是例外。

---

## 6. 关于撤回（retraction）

Gaia IR 中没有 retraction 类型。撤回是一个**操作**：为目标 Knowledge 关联的所有 Strategy 添加新的 StrategyParamRecord，将 conditional_probabilities 中的**所有条目**设为 Cromwell 下界 ε。该 Knowledge 实质上变成孤岛，belief 回到 prior。图结构不变——图是不可变的。

---

## 7. 与原 Gaia IR 的映射

### 7.1 概念映射

| 原概念 | 新概念 | 变更说明 |
|--------|--------|---------|
| KnowledgeNode | **Knowledge** | 去掉 Node 后缀，schema 不变 |
| FactorNode | **Strategy** | 改名 + 重构（统一 type，删除 subgraph） |
| FactorNode.category + reasoning_type | Strategy.type | 合并为单一字段 |
| FactorNode.subgraph | **FormalExpr**（FormalStrategy 的嵌入字段） | 从 FactorNode 字段提取为 data class，嵌入 FormalStrategy |
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
| Strategy 三形态类层级 | Strategy（叶子 ↝）、CompositeStrategy（递归嵌套）、FormalStrategy（确定性展开）——形态由结构决定，type 与形态正交 |
| FormalExpr 作为 FormalStrategy 的嵌入字段 | 1:1 关系，不需要独立实体的复杂度；FormalExpr 无独立 ID 和 lifecycle |
| 多分辨率 BP（expand_set） | 任何 Strategy 折叠时均为 ↝；展开时进入内部结构（子策略或确定性 Operator）；支持同一图在不同粒度做推理 |
| type 合并三个字段 | category/reasoning_type/link_type 的合法组合高度受限，实为同一维度 |
| conditional_probabilities 在 parameterization 层 | 概率参数不属于图结构；通过 StrategyParamRecord 存储。type 决定参数模型：None=通用 CPT(2^K), infer=noisy-AND [q], soft_implication=[p₁, p₂] |
| infer 的 conjunction + ↝ 由编译器展开 | 模式固定（conjunction + ↝(q, p₂=1)），不需要存储 FormalExpr；与命名策略不同（后者 FormalExpr 因 case 而异） |
| 9 种命名策略对应 FormalStrategy | 每种策略的 FormalExpr 由 theory 预定义，分类确认即升级为 FormalStrategy |

---

## 源代码

- `libs/graph_ir/models.py` -- `LocalCanonicalGraph`, `Knowledge`（原 `LocalCanonicalNode`）, `Strategy`（原 `FactorNode`）
- `libs/storage/models.py` -- `GlobalCanonicalNode`（= global `Knowledge`）, `CanonicalBinding`
- `libs/global_graph/canonicalize.py` -- `canonicalize_package()`
- `libs/global_graph/similarity.py` -- `find_best_match()`
- *Future:* `libs/graph_ir/operator.py` -- `Operator`
- *Future:* `libs/graph_ir/strategy.py` -- `CompositeStrategy`, `FormalStrategy`, `FormalExpr`
