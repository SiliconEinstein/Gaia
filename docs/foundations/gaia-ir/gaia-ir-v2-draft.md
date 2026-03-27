# Gaia IR — 结构定义（v2 草稿）

> **Status:** Draft — 以 `theory/01`-`theory/05` 为语义边界重写
>
> **⚠️ Protected Contract Layer** — 本目录定义 CLI↔LKM 结构契约。变更需要独立 PR 并经负责人审查批准。

Gaia IR 编码的是 **theory Layer 2 的命题网络结构**：图中有哪些对象、对象之间有哪些严格关系、哪些推理步骤仍停留在粗粒度 weakpoint/strategy 层。

Gaia IR **不**定义以下内容：

- 因子图、势函数、BP 或任何其他推理算法
- 运行时如何折叠/展开同一条推理链
- `Strategy.type` 对应哪一种 CPT / noisy-AND / 编译时执行模型

这些都属于 downstream 的计算层。Gaia IR 的职责只有一个：忠实表达 theory 文档中的**粗命题网络**与**细命题网络**。

Gaia IR 由三类实体构成：

| 实体 | 角色 | 语义边界 |
|------|------|----------|
| **Knowledge** | 节点 | 命题、背景或问题 |
| **Operator** | 严格关系 | claim 之间的确定性逻辑约束 |
| **Strategy** | 粗推理声明 | 尚未完全还原为严格关系的支撑步骤 |

---

## 1. Knowledge（知识）

Knowledge 表示图中的对象。**只有 `claim` 是可判真的命题节点，也是唯一会在 downstream 概率层获得 prior / belief 的类型。**

### 1.1 Schema

Local 和 global 使用同一个 data class，字段按层级使用：

```text
Knowledge:
    id:                     str              # lcn_ 或 gcn_ 前缀
    type:                   str              # claim | setting | question
    parameters:             list[Parameter]  # 全称 claim 的量化变量；封闭命题为空
    metadata:               dict | None

    # ── local 层 ──
    content:                str | None       # local 层唯一正文存储位置

    # ── 追溯 ──
    provenance:             list[PackageRef] | None

    # ── global 层 ──
    representative_lcn:     LocalCanonicalRef | None
    local_members:          list[LocalCanonicalRef] | None
```

**各层字段使用：**

| 字段 | Local | Global |
|------|-------|--------|
| `id` | `lcn_` 前缀，SHA-256 包+内容寻址 | `gcn_` 前缀，注册中心分配 |
| `content` | 有值（唯一正文存储位置） | 通常为 None，通过 `representative_lcn` 间接获取 |
| `provenance` | 有值 | 有值 |
| `representative_lcn` | None | 有值 |
| `local_members` | None | 有值 |

**身份规则**：local 层 `id = lcn_{SHA-256(package_id + type + content + sorted(parameters))[:16]}`。ID 中包含 `package_id`，因此不同包中相同内容的节点会有不同的 `lcn_id`；跨包身份统一由 canonicalization 决定，而不是由 local ID 决定。

### 1.2 三种 Knowledge 类型

| type | 说明 | 是否真值对象 | 可作为 |
|------|------|-------------|--------|
| **claim** | 科学断言（封闭或全称） | 是 | premise, conclusion, refs |
| **setting** | 背景设定 | 否 | background, refs |
| **question** | 待研究问题 | 否 | background, refs |

`template` 不再是 Gaia IR 一等类型。模板概念仅保留在 Gaia Language 编写层；编译到 Gaia IR 时，按语义落到 `claim`、`setting` 或 `question`。

#### claim（断言）

具有真值的命题。唯一会进入命题网络计算语义的类型。

Claim 分为两类，由 `parameters` 区分：

- **封闭 claim**：`parameters=[]`。例如 `"YBCO 在 90 K 以下超导"`
- **全称 claim**：`parameters` 非空。例：`∀{x}. superconductor({x}) → zero_resistance({x})`

全称 claim 仍然是 claim，不是模板占位符。它有真值，可以被支持、反驳、实例化。

#### 显式命题规则

Gaia IR 不允许“隐式中间 claim”：

1. 任何被 `Operator.variables` 或 `Strategy.premises` / `Strategy.conclusion` 引用的 claim，都必须显式存在于顶层 `knowledges`
2. 形式化过程中引入的 prediction、instance、bridge claim、continuity claim 等中间命题，必须作为独立的 self-contained claim 节点写入图中
3. IR 不把中间 claim 视为服务器展开策略时临时生成的副产物

这是 `theory/05-formalization-methodology.md` 的直接要求：细命题网络中的所有承重对象都必须是显式 claim。

#### 全称 claim 的实例化

实例化结果必须表现为**显式封闭 claim**，而不是“靠 background 绑定变量的隐式推导”。

```text
全称 claim:  "∀{x}. superconductor({x}) → zero_resistance({x})"
实例 claim:  "superconductor(YBCO) → zero_resistance(YBCO)"

Strategy(type=deduction):
  premises   = [全称 claim]
  conclusion = 实例 claim
  metadata.binding = {x: "YBCO"}
```

绑定信息属于结构化 provenance，可放在 `metadata`，但 `YBCO` 绑定本身不是新的 claim，也不应被塞进 `background` 伪装成图语义的一部分。

#### setting（背景设定）

研究背景、适用语境、问题动机等非真值对象。不携带 prior，不直接进入命题网络运算。

#### question（问题）

开放研究问题。不携带 prior，不直接进入命题网络运算。

---

## 2. Operator（严格关系）

Operator 表示 claim 之间的**确定性逻辑约束**。它们对应 theory 中的严格命题算子，不携带自由概率参数。

theory 推导见 [03-propositional-operators.md](../theory/03-propositional-operators.md)。

### 2.1 Schema

```text
Operator:
    operator_id:    str              # lco_ 或 gco_ 前缀
    scope:          str              # "local" | "global"

    operator:       str              # 见 §2.2
    variables:      list[str]        # 有序 Knowledge IDs
    conclusion:     str | None       # 有向算子的输出；无向算子为 None

    metadata:       dict | None
```

### 2.2 算子类型

| operator | 符号 | variables | conclusion | 真值约束 | 说明 |
|----------|------|-----------|------------|---------|------|
| **entailment** | → | [A, B] | B | A=1 时 B 必须=1 | theory 中的严格蕴含 |
| **equivalence** | ↔ | [A, B] | None | A=B | 真值一致 |
| **contradiction** | ⊗ | [A, B] | None | ¬(A=1 ∧ B=1) | 不能同真 |
| **negation** | ⊕ | [A, B] | None | A≠B | 真值互补 |
| **conjunction** | ∧ | [A1,...,Ak,M] | M | M=(A1∧...∧Ak) | 生成显式合取 claim |
| **disjunction** | ∨ | [A1,...,Ak] | None | ¬(all Ai=0) | 至少一个为真 |

说明：

- `entailment` 是 IR 对 theory 中严格蕴含 `A→B` 的命名
- `conjunction` 的输出 `M` 必须是一个显式 claim，用来承接多前提推理中的中间命题
- `equivalence` / `contradiction` / `negation` 是真正的命题关系，不是 dedupe 补丁

### 2.3 不变量

1. `variables` 中的所有 ID 必须引用同 graph 中存在的 Knowledge
2. `variables` 中的 Knowledge 类型必须全部是 `claim`
3. `conclusion` 如非 None，必须在 `variables` 中
4. `equivalence`、`contradiction`、`negation`、`disjunction` 的 `conclusion = None`
5. `entailment` 的 `conclusion = variables[-1]`
6. `conjunction` 的 `conclusion = variables[-1]`

---

## 3. Strategy（粗推理声明）

Strategy 记录**尚未完全还原为严格关系的推理步骤**。它处在 theory 的 coarse network 层，不是 BP/factor-graph 的执行单元。

一个 Strategy 表达的是：

```text
premises   --(某种推理模式 / weakpoint)-->   conclusion
```

它说明“这些 claim 以某种推理方式支撑那个 claim”，但尚未把该支撑完整写成显式 claim + strict operator 子网络。

### 3.1 Schema

```text
Strategy:
    strategy_id:    str              # lcs_ 或 gcs_ 前缀
    scope:          str              # "local" | "global"
    type:           str              # 见 §3.2

    premises:       list[str]        # claim Knowledge IDs
    conclusion:     str              # claim Knowledge ID
    background:     list[str] | None # setting/question IDs；不参与命题网络运算

    # ── local 层 ──
    steps:          list[Step] | None

    # ── 追溯 ──
    metadata:       dict | None      # 可含 refs、binding、review 注释等
```

**各层字段使用：**

| 字段 | Local | Global |
|------|-------|--------|
| `strategy_id` | `lcs_` 前缀 | `gcs_` 前缀 |
| `premises` / `conclusion` | `lcn_` ID | `gcn_` ID |
| `steps` | 有值 | None |

### 3.2 Strategy 类型

`type` 表示**语义分类**，不是运行时参数模型：

| type | 含义 | 对应 theory |
|------|------|-------------|
| **soft_implication** | 未进一步分类的粗 weakpoint | `03-propositional-operators.md` 的 ↝ |
| **deduction** | 演绎 | `04` §2.1 |
| **abduction** | 溯因 | `04` §2.2 |
| **induction** | 归纳 | `04` §2.3 |
| **analogy** | 类比 | `04` §2.4 |
| **extrapolation** | 外推 | `04` §2.5 |
| **reductio** | 归谬 | `04` §2.6 |
| **elimination** | 排除 | `04` §2.7 |
| **mathematical_induction** | 数学归纳 | `04` §2.8 |
| **case_analysis** | 分情况讨论 | `04` §2.9 |

`toolcall`、`proof` 等工作流/执行态概念不属于 Gaia IR 核心 contract；如需记录，应放在更上层的 authoring / workflow schema，而不是混入命题网络本体。

### 3.3 参数语义边界

Gaia IR 自身**不存储任何概率值**。它只保留 strategy 的结构和语义分类。

与参数相关的边界如下：

1. claim 的 prior 属于 downstream 参数层
2. `soft_implication` 之类的 coarse weakpoint，如要赋 `(p1, p2)`，也属于 downstream 参数层
3. theory 当前只显式给出了二值接口 `A ↝ B` 的 `(p1, p2)` 语义；多前提策略的推广形式尚未在 theory 中定稿

因此，Gaia IR 允许 `premises: list[str]`，但**不在 IR 层强行绑定某一种 generalized CPT / noisy-AND 参数模型**。IR 只负责记录结构；参数推广如何做，是 theory 与 downstream parameterization 的问题，不是 IR contract 的问题。

### 3.4 粗命题网络与细命题网络

Gaia IR 支持两种合法表达：

#### 粗命题网络

使用 `Strategy` 记录尚未展开的支撑步骤：

```text
Obs1, Obs2  --induction-->  Law
```

#### 细命题网络

把原 strategy 进一步形式化为显式 claim + Operator；若仍有未消去的 weakpoint，再用新的下层 Strategy 表示：

```text
Law  --entailment-->  Instance1  --equivalence-->  Obs1
Law  --entailment-->  Instance2  --equivalence-->  Obs2
```

关键规则：

1. **细化是图重写，不是 IR 内置的运行时折叠/展开协议**
2. 同一条活跃推理步骤在同一张图里应当选择一个分辨率表达
3. 如果同时保留 coarse summary 和其完整 refined subnetwork，并把二者都当作独立证据参与运算，会导致重复计数

如果工作流需要保留“这张细网络来源于哪条 coarse strategy”的追溯关系，应写入 `metadata` / review 层，而不是把双分辨率执行语义塞进 IR contract。

### 3.5 命名策略的标准细化方向

命名策略的意义，是告诉 reviewer / compiler / agent：这条 coarse step 在 theory 中通常应往什么形式化方向细化。

| type | 典型细化骨架 |
|------|--------------|
| `deduction` | `conjunction` + `entailment` |
| `abduction` | `Hypothesis → Prediction`，再 `Prediction ↔ Observation` |
| `induction` | 多组 `Law → Instance_i` 与 `Instance_i ↔ Obs_i` |
| `analogy` | 显式 bridge claim + source law + target entailment |
| `extrapolation` | 显式 continuity claim + known law + target entailment |
| `reductio` | 假设导出结果，再与已知 claim 构成 `contradiction` / `negation` |
| `elimination` | 通过互斥关系逐步排除候选，再 `entailment` 到剩余结论 |
| `mathematical_induction` | base + step 的 `conjunction`，再 `entailment` 到一般命题 |
| `case_analysis` | case 的 `disjunction`，各 case 到结论的 `entailment` |

这些是**形式化方法论的方向约束**，不是嵌入式执行 AST。

### 3.6 Premise / Background / Refs

| 字段 | 类型约束 | 是否进入命题网络 | 说明 |
|------|---------|------------------|------|
| **premises** | 仅 `claim` | 是 | 这条推理真正依赖的真值对象 |
| **background** | 仅 `setting` / `question` | 否 | 背景语境、研究动机、适用范围 |
| **refs**（`metadata.refs`） | 任意 | 否 | 追溯引用 |

规则：

- 任意**承重假设**，只要它有真值、可支持、可反驳，就必须写成 `claim`
- 这种 claim 必须进入 `premises`、`conclusion` 或显式 Operator 网络
- 不能把 claim 藏在 `background` 里逃避结构化

### 3.7 不变量

1. `premises` 中的 Knowledge 类型必须全部为 `claim`
2. `conclusion` 引用的 Knowledge 类型必须为 `claim`
3. `background` 中的 Knowledge 类型只能是 `setting` 或 `question`
4. Strategy 至少有一个 premise
5. `strategy_id` 只标识这条 coarse 推理声明，不暗含任何运行时展开策略

---

## 4. 规范化（Canonicalization）

规范化将 local canonical 实体映射为 global canonical 实体。核心原则是：**按命题身份做映射，而不是按该命题在局部图里的修辞角色做映射。**

### 4.1 CanonicalBinding 与 Equivalence 的区别

规范化中存在两类完全不同的关系：

- **CanonicalBinding（身份映射）**：local Knowledge 与 global Knowledge 是同一个命题的不同出现
- **Equivalence Operator（等价关系）**：两个 global claim 是独立命题，但被判断为等价

前者是身份统一，后者是图中的真实结构关系。`equivalence` 不是为了解决“结论节点不能 merge”的技术补丁，而是命题层面的关系声明。

### 4.2 映射决策

当 local Knowledge 与已有 global Knowledge 语义匹配时：

1. **同一命题** → 直接 CanonicalBinding 到该 global Knowledge
2. **不是同一命题，但 reviewer 认为两者等价** → 创建新的 global Knowledge，并在两者之间提议 `equivalence`
3. **无匹配** → 创建新的 global Knowledge

局部角色（premise / conclusion / background）可以作为 reviewer 判断的辅助信号，但**不能**作为 IR contract 中的规范化规则。

### 4.3 参与规范化的类型

所有 Knowledge 类型都可以规范化：

- `claim`：按命题身份统一
- `setting`：按背景对象身份统一
- `question`：按问题身份统一

其中 `claim` 的 canonicalization 最关键，因为它决定全局命题网络的节点集合。

### 4.4 匹配策略

IR 层不规定具体判定算法，但推荐约束如下：

- 仅同 `type` 候选可比较
- `claim(parameters != [])` 需要额外比较参数结构（count + types 按序匹配，忽略变量名）
- embedding / lexical / symbolic matching 都是实现细节，不属于 IR contract

### 4.5 Strategy 提升

Knowledge 规范化完成后，local Strategy 提升到 global：

1. 基于 CanonicalBinding 构造 `lcn_ → gcn_` 映射
2. 解析 Strategy 的 `premises`、`conclusion`、`background`
3. 若存在未解析引用，则该 Strategy 不能被提升为有效 global Strategy

Global Strategy 不携带 `steps`。推理文本保留在 local 层。

### 4.6 显式内容与中间 claim

Global 层通常通过 `representative_lcn` 间接获得内容；但如果 review / LKM 在 global 层新增了一个 claim，它也必须作为**显式 Knowledge 实体**写入图中，并具备可追溯 content。

系统永远不应把某个 claim 当作“展开 strategy 时隐式出现，但不需要进入 `knowledges`”。

---

## 5. 关于细化（Refinement）

Gaia IR 的细化原则来自 `theory/05-formalization-methodology.md`：

1. 先允许 coarse network 诚实记录 weakpoint
2. 再逐步把 weakpoint 重写为显式 claim + strict operator 子网络
3. 当某条路径已被充分细化后，剩余自由度应尽量收缩到 claim 的 prior，而不是继续塞在边的黑箱参数里

Gaia IR 负责承载这个过程的**结果**，不负责定义运行时如何在同一条路径上来回折叠/展开。

---

## 6. 设计决策记录

| 决策 | 理由 |
|------|------|
| 删除 `template` 作为 IR 一等类型 | 全称命题本身是 claim；模板只属于 authoring 语法层 |
| `Operator` 只保留 theory 层严格关系 | 这些关系是命题网络本体，不是 downstream factor/BP object |
| `Strategy.type` 改为语义分类 | `infer` / `noisy_and` / CPT 是参数模型，不是 ontology 层类型 |
| 不再以 `CompositeStrategy` / `FormalStrategy` 作为核心 contract | 那是执行/展开视角；theory 层要表达的是 coarse graph 与 explicit refined graph |
| 中间 claim 必须显式存在 | theory/05 要求 self-contained claim；不能依赖隐式节点 |
| `background` 禁止 claim | 承重真值对象必须进入 proposition network |
| canonicalization 按命题身份，不按局部角色 | 命题身份与其在一条局部推理中的修辞位置无关 |

### 已知开放点

| 主题 | 当前状态 |
|------|----------|
| `↝` 的多前提参数推广 | theory 尚未定稿；IR 保持结构中立 |
| claim 的 α-equivalence | 仍需单独定义匹配规则 |
| downstream parameterization 与 belief engine | 属于 Layer 3，不在本文定义 |
