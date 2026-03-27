# Gaia IR — 结构定义（v2 草稿）

> **Status:** Draft — 基于现有 gaia-ir.md 重构，整合 Issue #231（template → claim with parameters）
>
> **⚠️ Protected Contract Layer** — 本目录定义 CLI↔LKM 结构契约。变更需要独立 PR 并经负责人审查批准。

Gaia IR 编码推理超图的拓扑结构——**什么连接什么**。它不包含任何概率值。

概率参数见 [parameterization.md](parameterization.md)。BP 输出见 [belief-state.md](belief-state.md)。三者的关系见 [overview.md](overview.md)。

Gaia IR 由三种实体构成：

| 实体 | 角色 | 语义层 | 确定性 |
|------|------|--------|--------|
| **Knowledge** | 命题（变量节点） | Layer 2 — 科学本体 | — |
| **Operator** | 确定性逻辑约束（ψ∈{0,1}） | Layer 3 — 计算方法 | 确定 |
| **Strategy** | 不确定推理声明（↝ 载体） | Layer 2 — 科学本体 | 不确定 |

读者先理解图中有什么节点（Knowledge），再理解节点之间的确定性结构关系（Operator），最后理解不确定的推理如何建模（Strategy）。

---

## 1. Knowledge（知识）

Knowledge 表示命题——推理超图中的变量节点。**Claim 是唯一携带 probability 并参与 BP 的类型。**

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
| `content` | 有值（唯一存储位置） | 通常为 None（LKM 直接创建的 Knowledge 例外，包括 FormalExpr 中间 Knowledge） |
| `provenance` | 有值（来源包） | 有值（贡献包列表） |
| `representative_lcn` | None | 有值（引用 local Knowledge 获取内容） |
| `local_members` | None | 有值（所有映射到此的 local Knowledge） |

**身份规则**：local 层 `id = lcn_{SHA-256(package_id + type + content + sorted(parameters))[:16]}`。ID 包含 `package_id`，因此不同包中相同内容的节点有**不同的** lcn_id。跨包的语义等价由 global canonicalization 通过 embedding 相似度判定，而非 ID 相等。

**内容存储**：所有知识内容存储在 local 层的 `content` 字段上。Global 层通过 `representative_lcn` 引用获取内容，不重复存储。LKM 服务器直接创建的 global Knowledge（包括 FormalExpr 展开的中间 Knowledge）无 local 来源，content 直接存在 global 层。

### 1.2 三种知识类型

| type | 说明 | 参与 BP | 可作为 |
|------|------|---------|--------|
| **claim** | 科学断言（封闭或全称） | 是（唯一 BP 承载者） | premise, background, conclusion, refs |
| **setting** | 背景信息 | 否 | background, refs |
| **question** | 待研究方向 | 否 | background, refs |

#### claim（断言）

具有真值的科学断言。默认携带 probability（prior + belief），是 BP 的唯一承载对象。

Claim 分为两类，由 `parameters` 字段区分：

- **封闭 claim**（`parameters=[]`）：所有变量已绑定的具体命题。如 "YBCO 在 90K 以下超导"。
- **全称 claim**（`parameters` 非空）：含量化变量的通用定律。如 `∀{x}. superconductor({x}) → zero_resistance({x})`。全称 claim 有真值（可被反例推翻），参与 BP，可通过 induction 获得支持，通过 deduction 实例化为封闭 claim。

> **设计决策（Issue #231）：** 原 `template` 类型统一为 claim with parameters。理由：全称命题天然具有真值，应参与 BP。"template" 概念保留在 Gaia Language 编写层作为语法工具，编译到 Gaia IR 时按语义分流为 claim、setting 或 question。

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

全称 claim 通过 deduction Strategy（p₁=1.0）实例化为封闭 claim：

```
全称 claim:  "∀{x}. superconductor({x}) → zero_resistance({x})"  (claim, parameters=[x:material])
绑定:        "x = YBCO"                                            (setting, background)
                ↓ Strategy(type=deduction, p₁=1.0)
封闭 claim:  "superconductor(YBCO) → zero_resistance(YBCO)"       (claim, parameters=[])
```

全称 claim 和封闭 claim 之间形成自然的归纳-演绎循环：

- **归纳**：多个封闭实例通过 induction Strategy 支持全称 claim → 全称 belief 上升
- **演绎**：全称 claim 通过 deduction Strategy 预测新封闭实例 → 实例 belief 跟随全称
- **反例**：发现与全称矛盾的封闭 claim → contradiction Operator → 全称 belief 下降

#### setting（背景设定）

研究的背景信息或动机性叙述。不携带 probability，不参与 BP。可作为 Strategy 的 background（上下文依赖）或 refs（弱引用）。

示例：某个领域的研究现状、实验动机、未解决挑战、近似方法或理论框架、全称 claim 实例化时的变量绑定（如 "x = YBCO"）。

#### question（问题）

探究制品，表达待研究的方向。不携带 probability，不参与 BP。可作为 Strategy 的 background 或 refs。

示例：未解决的科学问题、后续调查目标。

---

## 2. Operator（结构约束）

Operator 表示两个或多个 Knowledge 之间的**确定性逻辑关系**（ψ∈{0,1}，无自由参数）。

Operator 对应 theory Layer 3（[因子图层](../theory/06-factor-graphs.md)）的势函数，以及 [命题算子](../theory/03-propositional-operators.md) 中定义的六种逻辑关系。

### 2.1 Schema

```
Operator:
    operator_id:    str              # lco_ 或 gco_ 前缀（local/global canonical operator）
    scope:          str              # "local" | "global"

    operator:       str              # 算子类型（见 §2.2）
    variables:      list[str]        # 连接的 Knowledge IDs（有序）
    conclusion:     str | None       # 有向算子的输出（无向算子为 None）

    metadata:       dict | None      # 含 refs: list[str] 等
```

### 2.2 算子类型与势函数

| operator | 符号 | variables | conclusion | 势函数 ψ | 说明 |
|----------|------|-----------|------------|---------|------|
| **implication** | → | [A, B] | B | ψ=0 iff A=1,B=0 | A 成立则 B 必须成立 |
| **equivalence** | ↔ | [A, B] | None | ψ=1 iff A=B | 真值必须一致 |
| **contradiction** | ⊗ | [A, B] | None | ψ=0 iff A=1,B=1 | 不能同时为真 |
| **complement** | ⊕ | [A, B] | None | ψ=1 iff A≠B | 真值必须相反（XOR） |
| **disjunction** | ∨ | [A₁,...,Aₖ] | None | ψ=0 iff all Aᵢ=0 | 至少一个为真 |
| **conjunction** | ∧ | [A₁,...,Aₖ,M] | M | ψ=1 iff M=(A₁∧...∧Aₖ) | M 等于所有 Aᵢ 的合取 |

所有势函数的 theory 推导见 [03-propositional-operators.md](../theory/03-propositional-operators.md)。

**关键性质：** Operator 没有概率参数——它编码的是逻辑结构（"A 和 B 矛盾"），不是推理判断（"作者认为 A 蕴含 B"）。后者由 Strategy 承载。

### 2.3 存在位置

Operator 可以出现在两个位置：

- **顶层 `operators` 数组**：独立的结构关系。例如：
  - 人工标注的 contradiction（"GR 预测 1.75 角秒"⊗"牛顿预测 0.87 角秒"）
  - 规范化确认的 equivalence（跨包同义命题）
  - Review 发现的 implication

- **FormalStrategy 内部的 `formal_expr.operators`**：FormalExpr 展开产生的算子，嵌入在 FormalStrategy 中，不独立存在。例如 abduction 展开为 H→O + O↔Obs，其中 → 和 ↔ 是 FormalExpr 内的 Operator。

位置即来源，不需要额外的 `source` 字段。

### 2.4 不变量

1. `variables` 中的所有 ID 必须引用同 graph 中存在的 Knowledge
2. `variables` 中的 Knowledge 类型必须是 `claim`（Operator 只连接有真值的命题）
3. `conclusion`（如非 None）必须在 `variables` 中
4. `equivalence`、`contradiction`、`complement`：`conclusion = None`（无向）
5. `implication`：`conclusion` 必填（有向，`conclusion = variables[-1]`）
6. `conjunction`：`conclusion` 必填（`conclusion = variables[-1]` = M）
7. `disjunction`：`conclusion = None`（无向约束）

---

<!-- §3 Strategy（推理声明）将在下一轮讨论后编写 -->
