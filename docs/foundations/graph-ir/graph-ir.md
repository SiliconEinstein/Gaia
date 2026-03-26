# Graph IR — 结构定义

> **Status:** Target design — 基于 [06-factor-graphs.md](../theory/06-factor-graphs.md) 和 [04-reasoning-strategies.md](../theory/04-reasoning-strategies.md) 设计
>
> **⚠️ Protected Contract Layer** — 本目录定义 CLI↔LKM 结构契约。变更需要独立 PR 并经负责人审查批准。详见 [documentation-policy.md](../../documentation-policy.md#12-变更控制)。

Graph IR 编码推理超图的拓扑结构——**什么连接什么**。它不包含任何概率值。

概率参数见 [parameterization.md](parameterization.md)。BP 输出见 [belief-state.md](belief-state.md)。三者的关系见 [overview.md](overview.md)。

---

## 1. Knowledge 节点（变量节点）

Knowledge 节点表示命题。Gaia 中有四种知识对象。**Claim 是唯一默认携带 probability 并参与 BP 的类型。**

### 1.1 Schema

Local 和 global 使用同一个 data class，字段按层级使用：

```
KnowledgeNode:
    id:                     str              # lcn_ 或 gcn_ 前缀
    type:                   str              # claim | setting | question | template
    parameters:             list[Parameter]  # 仅 template：自由变量列表
    source_refs:            list[SourceRef]
    metadata:               dict | None      # 特化 schema 数据（见 claim 特化）

    # ── local 层使用 ──
    content:                str | None       # 知识内容（local 层存储，global 层通常为 None）

    # ── 来源追溯 ──
    provenance:             list[PackageRef] | None   # 贡献包列表

    # ── global 层使用 ──
    representative_lcn:     LocalCanonicalRef | None  # 代表性 local 节点（内容从此获取）
    member_local_nodes:     list[LocalCanonicalRef] | None  # 所有映射到此的 local 节点
```

**各层字段使用：**

| 字段 | Local | Global |
|------|-------|--------|
| `id` | `lcn_` 前缀，SHA-256 内容寻址 | `gcn_` 前缀，注册中心分配 |
| `content` | 有值（唯一存储位置） | 通常为 None（subgraph 中间节点例外） |
| `provenance` | 有值（来源包） | 有值（贡献包列表） |
| `representative_lcn` | None | 有值（引用 local 节点获取内容） |
| `member_local_nodes` | None | 有值（所有映射到此的 local 节点） |

**身份规则**：local 层 `id = SHA-256(type + content + sorted(parameters))`，相同类型、内容和参数的声明共享同一 ID。

**内容存储**：所有知识内容存储在 local 层的 `content` 字段上。Global 层通过 `representative_lcn` 引用获取内容，不重复存储。唯一例外是 subgraph 展开时新创建的中间节点（无 local 来源，content 直接存在 global 节点上）。

### 1.2 四种知识类型

| type | 说明 | 参与 BP | 可作为 |
|------|------|---------|--------|
| **claim** | 封闭的科学断言 | 是（唯一 BP 承载者） | premise, context, conclusion |
| **setting** | 背景信息 | 否 | premise, context |
| **question** | 待研究方向 | 否 | premise, context |
| **template** | 含自由变量的命题模式 | 否 | premise（entailment/instantiation 场景） |

#### claim（断言）

封闭的、具有真值的科学断言。默认携带 probability（prior + belief），是 BP 的唯一承载对象。

Claim 可以携带描述其产生方式的结构化元数据（`metadata` 字段）。以下是概念性示例，不构成封闭分类。具体的元数据 schema 由下层文档定义，Graph IR 层不限制 `metadata` 的结构。

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

研究的背景信息或动机性叙述。不携带 probability，不参与 BP。可作为 factor 的 premise（承载性依赖）或 context（弱引用），但无论哪种角色都不创建 BP 边（见 §2.5）。

示例：某个领域的研究现状、实验动机、未解决挑战、近似方法或理论框架。

#### question（问题）

探究制品，表达待研究的方向。不携带 probability，不参与 BP。可作为 factor 的 premise 或 context，但不创建 BP 边（见 §2.5）。

示例：未解决的科学问题、后续调查目标。

#### template（模板）

开放的命题模式，含自由变量。不直接参与 BP。核心作用是**桥梁**：将 setting 或 question 包装为 claim，使其获得概率语义。Template 到 claim 的实例化是 entailment 的特例（probability=1.0）。

示例：`falls_at_rate({x}, {medium})`、`{method} can be applied in this {context}`、`∀{x}. wave({x}) → diffraction({x})`。

---

## 2. Factor 节点（因子节点）

Factor 节点表示推理算子，连接 knowledge 节点。对应 theory 层中的**推理算子（reasoning operator）**。

### 2.1 FactorNode Schema

Local 和 global 使用同一个 data class，字段按层级使用：

```
FactorNode:
    factor_id:        str                # lcf_ 或 gcf_ 前缀 + {sha256[:16]}，确定性
    scope:            str                # "local" | "global"

    # ── 三维类型系统 ──
    category:         str                # infer | toolcall | proof
    stage:            str                # initial | candidate | permanent
    reasoning_type:   str | None         # entailment | induction | abduction
                                         # | equivalent | contradict | None

    # ── 连接 ──
    premises:         list[str]          # knowledge node IDs — 承载性依赖（仅 claim premise 创建 BP 边，见 §2.5）
    conclusion:       str | None         # 单个输出 knowledge 节点（双向算子为 None）

    # ── local 层使用 ──
    steps:            list[Step] | None  # 推理过程的分步描述
    weak_points:      list[str] | None   # 自由文本 — 推理薄弱环节描述

    # ── global 层使用 ──
    subgraph:         list[FactorNode] | None  # 升格为 permanent 时的细粒度分解

    # ── 追溯 ──
    source_ref:       SourceRef | None
    metadata:         dict | None        # 包含 context: list[str]（弱相关 knowledge node IDs）等

Step:
    reasoning:        str                # 该步的推理描述文本
    premises:         list[str] | None   # 该步引用的前提（可选）
    conclusion:       str | None         # 该步的结论（可选）
```

**各层字段使用：**

| 字段 | Local | Global |
|------|-------|--------|
| `factor_id` | `lcf_` 前缀，由源构造确定性计算 | `gcf_` 前缀，由 factor lifting 后的全局构造计算 |
| `scope` | `"local"` | `"global"` |
| `premises`/`conclusion` | `lcn_` ID | `gcn_` ID |
| `steps` | 有值（推理过程文本） | None |
| `weak_points` | 有值（薄弱环节描述） | None |
| `subgraph` | None | 有值（agent 在 global 层创建的细粒度分解，见 §2.6） |

`steps` 记录推理过程的分步文本。一个 factor 可以有一步或多步。每步的 `premises` 和 `conclusion` 是可选的——有些步骤只是描述性的推理过程，不显式关联特定的知识节点。FactorNode 的顶层 `premises` 和 `conclusion` 是整个推理链的输入和最终输出。

**身份规则：** Factor ID 由 `scope + category + sorted(premises) + conclusion` 确定性计算：`{prefix}_{sha256[:16]}`。Local 层前缀 `lcf_`，global 层前缀 `gcf_`。Factor lifting（lcn→gcn 重写）后 premises/conclusion 变化，因此 global factor 与其源 local factor 有不同的 `factor_id`。

> **与 KnowledgeNode 的对偶关系：** KnowledgeNode 用 `lcn_`/`gcn_` 前缀 + `content`/`representative_lcn` 字段区分层级；FactorNode 用 `lcf_`/`gcf_` 前缀 + `scope` + `steps`/`subgraph` 字段区分层级。两者结构完全对偶。

### 2.2 三维类型系统

#### category：怎么得到结论的

| category | 说明 | 概率语义 |
|----------|------|---------|
| **infer** | 人或 agent 的推理判断 | 概率性，由 review 赋值 |
| **toolcall** | 计算过程（工具调用、模拟、数值求解） | 可根据可复现性打分，具体策略后续定义 |
| **proof** | 形式化证明（定理证明、形式验证） | 可设为 1.0（有效证明确定性成立），具体策略后续定义 |

**所有 category 都预留 probability 接口。** 概率值存储在 [parameterization.md](parameterization.md) 的覆盖层中，不内联在 factor 结构里。

#### stage：审查到哪了

| stage | 说明 |
|-------|------|
| **initial** | 作者写入时的默认状态。`reasoning_type` 可为 None（未指定）或作者直接指定。 |
| **candidate** | review/research agent 提议了具体推理类型，但尚未充分验证。 |
| **permanent** | 经过验证确认，正式具有明确的 BP 规则。 |

**生命周期规则：**

- `infer` 类 factor 经历生命周期：initial → candidate → permanent。如果作者在 initial 阶段已指定 `reasoning_type`，review 通过后可直接升格为 permanent。
- `toolcall` 和 `proof` 不经历生命周期——它们的语义在创建时就是明确的
- Template 实例化（entailment 特例）可跳过 review 直接升格为 permanent

#### reasoning_type：具体什么逻辑关系

以下类型在 candidate 和 permanent 阶段必填。initial 阶段可由作者指定，也可为 None（由后续 review 确定）。

**entailment（蕴含）** — 前提 → 结论，保真。

- A 为真 → B 必然为真；A 为假 → 不能推断 B
- `premises: [A], conclusion: B`
- 子场景：**抽象**（多个 claim 蕴含公共结论）、**实例化**（template→claim, probability=1.0）
- 示例："水是 H₂O" entails "水的分子量为 18"

**induction（归纳）** — 前提 → 结论，不保真。

- 具体案例支持结论，但不单独蕴含
- `premises: [A₁, ..., Aₙ], conclusion: B`
- 示例："铜导电"+"铁导电"+"铝导电" → "所有金属都导电"

**abduction（溯因）** — 从证据推断最佳解释，不保真。

- 结论是 hypothesis（被推断的解释）。前提是支持该假说的已有知识。观测证据本身不作为 premise，而是体现在 weak_points 和推理过程（steps）中——"这个假说能解释某些观测现象"是推理的动机，但观测不是假说成立的前提条件。
- `premises: [supporting_knowledge], conclusion: hypothesis`
- `weak_points: ["该假说尚未解释 X 现象", "竞争假说 Y 也能解释部分观测"]`
- 示例：premises: ["星系旋转曲线数据", "引力透镜效应"] → conclusion: "暗物质存在"

**equivalent（等价）** — 双向，真值一致。

- `premises: [A, B], conclusion: None`
- 示例："水的沸点是 100°C (1 atm)" ↔ "水的沸点是 212°F (1 atm)"

**contradict（矛盾）** — 双向，真值取反。

- `premises: [A, B], conclusion: None`
- 示例："暗能量是宇宙学常数" ⊥ "暗能量是动态标量场"

### 2.3 合法组合与不变量

| category | stage=initial | stage=candidate/permanent |
|----------|--------------|--------------------------|
| **infer** | reasoning_type 可为 None 或作者指定 | reasoning_type 必填 |
| **toolcall** | reasoning_type=None | 不经历 lifecycle |
| **proof** | reasoning_type=None | 不经历 lifecycle |

**stage 说明：**

- 作者可以在写入时直接指定 `reasoning_type`（如 `entailment`），此时 `stage=initial` 但 `reasoning_type` 非 None。Review 通过后，包内关系可直接升格为 `permanent`。
- 如果作者不指定具体类型，`reasoning_type=None`，由 review/research agent 在 candidate 阶段提议。

**不变量：**

1. `stage=candidate|permanent` 且 `category=infer` → `reasoning_type` 必填
2. `conclusion` 的 type 必须是 `claim`（如果 conclusion 非 None）
3. `premises` 中的 type 可以是 `claim | setting | question | template`
4. `weak_points` 是自由文本列表（不是 knowledge node 引用），是 factor probability 评估的注解
5. `type=template` 的节点只能作为 entailment factor 的 premise（instantiation 场景）
6. `equivalent` 和 `contradict` 的 `conclusion = None`，`premises` 至少包含 2 个节点

### 2.4 Premise、Weak Point 与 Context 的区别

| 字段 | 位置 | 参与 BP | 说明 |
|------|------|---------|------|
| **premises** | 顶层字段 | claim premise 创建 BP 边（见 §2.5） | 承载性依赖，前提为假会削弱结论 |
| **weak_points** | 顶层字段 | 否 | 推理薄弱环节的注解，影响体现在 factor 的 conditional probability 上 |
| **context** | `metadata` 内 | 否 | 弱相关的 knowledge、question 等引用 |

- **Premise**：推理成立的必要条件。可以是任意知识类型（claim、setting、question、template），但只有 claim premise 创建 BP 边。
- **Weak point**：自由文本，描述推理过程中已识别但尚未分离成独立 premise 的薄弱环节。不是 knowledge node 引用，不创建 BP 边，不承担独立概率——它们的影响体现在该 factor 的 conditional probability 上（review 在评估 factor probability 时会参考 weak_points）。随着研究深入，weak point 可以被具体化为独立的 knowledge node 并提取为 premise。
- **Context**：存储在 `metadata.context` 中的 knowledge node ID 列表。不参与图结构（不创建边），不参与 BP。用于记录弱相关的 knowledge、question 等引用。

### 2.5 BP 参与规则

**Premise**：可以包含任意知识类型，但只有 `type=claim` 的 premise 参与 BP 消息传递。Non-claim premise（setting、question、template）在 BP 中被跳过——不发送消息、不接收消息、不影响 belief 计算。Non-claim premise 在图结构中是承载性依赖，但 review 在分配 factor probability 时应考虑其内容。

**Weak point**：不参与 BP。它们是 factor 内部的注解——review 在评估 factor 的 conditional probability 时参考 weak_points，将薄弱环节的影响编码进 factor probability 中。

**Context**：在 metadata 中，不参与图结构，不参与 BP。

### 2.6 子图分解（Subgraph）

当 candidate factor 经过 agent 验证升格为 permanent 时，agent 可以同时提供一个 `subgraph`——将粗粒度的推理关系分解为更细粒度的 factor 组合，并在分解过程中创建新的中间 knowledge 节点。

**Induction 分解示例：**

```
原始 factor（permanent induction）：
  premises: [A1, A2, A3]  →  conclusion: B
  （三个具体案例归纳出一般性定律 B）

subgraph:
  - FactorNode(entailment, premises: [B], conclusion: A1)  # instantiation
  - FactorNode(entailment, premises: [B], conclusion: A2)  # instantiation
  - FactorNode(entailment, premises: [B], conclusion: A3)  # instantiation
```

归纳的展开：如果 B 成立，它应当能蕴含每个具体观测。subgraph 将这个关系分解为 B 到每个 Aᵢ 的 entailment（instantiation）。

**Abduction 分解示例：**

```
原始 factor（permanent abduction）：
  premises: [supporting_knowledge]  →  conclusion: hypothesis
  weak_points: ["该假说尚未解释 X 现象"]
  （从已有知识推断假说，观测证据在 weak_points 中描述）

subgraph（创建中间节点 prediction 和 observation）：
  - FactorNode(entailment, premises: [hypothesis], conclusion: prediction)
  - FactorNode(equivalent, premises: [prediction, observation])
```

溯因的展开：agent 将 weak_points 中描述的观测具体化为 knowledge 节点，然后构建"假说 → 预测 ↔ 观测"的细粒度结构。prediction 和 observation 是 subgraph 展开时新创建的 knowledge 节点。

**BP 规则：**

- 如果 factor 有 subgraph，**BP 只在最细粒度的 subgraph factor 上运行**，不在外层粗粒度 factor 上运行。外层 factor 的 probability 不再直接参与 BP，由 subgraph 内的 factor 接管。
- 未来可以考虑分层 BP（先在粗粒度 factor 上做快速推理，再在 subgraph 上细化），但当前设计只在最细粒度上运行。

**其他规则：**

- `subgraph` 在 candidate 和 initial 阶段为 None，仅在升格为 permanent 时由 agent 填充
- **subgraph 只在 global 层产生。** 它是 agent 在全局图上做 review/curation 时创建的，不存在于 local 层
- subgraph 展开时新创建的中间 knowledge 节点（如 prediction）直接写在 GlobalCanonicalGraph 上，content 也直接存在 global 节点上（这是 global 节点存储 content 的唯一例外——因为这些节点没有 local 来源）
- subgraph 中的 factor 可以引用外层全局图中已有的 knowledge 节点，也可以引用新创建的中间节点
- subgraph 中的 factor 本身也有完整的 FactorNode schema，可以递归包含 subgraph

### 2.7 关于撤回（retraction）

Graph IR 中没有 retraction factor 类型。撤回是一个**操作**：为目标 knowledge 节点关联的所有 factor 添加新的 FactorParamRecord，probability 设为 Cromwell 下界 ε。该节点实质上变成孤岛，belief 回到 prior。图结构不变——图是不可变的。

---

## 3. 规范化（Canonicalization）

规范化是将 local canonical 节点映射到 global canonical 节点的过程——从包内身份到跨包身份。

### 3.1 映射决策：premise 与 conclusion 的区别

当新包中的 local 节点与全局图中已有节点语义匹配时，处理方式取决于**该节点在 local 图中的角色**：

**作为 premise 的节点 → 直接 merge**

如果 local 节点在 local 图中仅作为 premise 使用，且与已有 global 节点匹配，则直接绑定到该 global 节点。全局图上的 prior 和 belief 保持不变，不因为新包的加入而更新。

**作为 conclusion 的节点 → 创建 equivalent candidate factor**

如果 local 节点在 local 图中作为某个 factor 的 conclusion，且与已有 global 节点匹配，**不**直接 merge 为同一个 global 节点。而是：

1. 为 local conclusion 创建新的 global 节点
2. 在新旧两个 global 节点之间创建一个 `reasoning_type=equivalent, stage=candidate` 的 factor

理由：两个不同包独立得出的结论语义相似，不代表它们是同一个命题。它们之间的等价关系需要经过 review 确认后才能升格为 permanent。直接 merge 会跳过这一审查步骤。

Canonicalization 步骤同时创建 placeholder 参数记录：新 global claim 节点的 PriorRecord（placeholder prior）和 equivalent candidate factor 的 FactorParamRecord（placeholder probability）。具体值由后续 review 步骤确定。

**同时作为 premise 和 conclusion 的节点 → 走 conclusion 路径**

如果一个 local 节点既是某个 factor 的 conclusion，又是另一个 factor 的 premise，按 conclusion 规则处理（创建新 global 节点 + equivalent candidate factor）。理由：该节点有独立的推理来源，不应静默合并。

**无匹配 → create_new**

为前所未见的命题创建新的 GlobalCanonicalNode。

### 3.2 参与规范化的节点类型

**所有知识类型都参与全局规范化：** claim、setting、question、template。

- **claim**：跨包身份统一是 BP 的基础
- **setting**：不同包可能描述相同背景，统一后可被多个推理引用
- **question**：同一科学问题可被多个包提出
- **template**：相同命题模式应跨包共享

### 3.3 匹配策略

**Embedding 相似度（主要）**：余弦相似度，阈值 0.90。

**TF-IDF 回退**：无 embedding 模型时使用。

**过滤规则：**

- 仅相同 `type` 的候选者才有资格
- Template 额外比较自由变量结构（`parameters` 字段）

### 3.4 CanonicalBinding

```
CanonicalBinding:
    local_canonical_id:     str
    global_canonical_id:    str
    package_id:             str
    version:                str
    decision:               str    # "match_existing" | "create_new" | "equivalent_candidate"
    reason:                 str    # 匹配原因（如 "cosine similarity 0.95"）
```

### 3.5 Factor 提升

节点规范化完成后，local factor 提升到全局图：

1. 从 CanonicalBinding 构建 `lcn_ → gcn_` 映射
2. 从全局节点元数据构建 `ext: → gcn_` 映射（跨包引用解析）
3. 对每个 local factor，解析所有 premise 和 conclusion ID（weak_points 是自由文本，无需 ID 解析）
4. 含未解析引用的 factor 被丢弃（记录在 `unresolved_cross_refs` 中）

**Global factor 不携带 steps。** Local factor 的 `steps`（推理过程文本）保留在 local canonical 层。Global factor 只保留结构信息（category、stage、reasoning_type、premises、contexts、conclusion），不复制推理内容。需要查看推理细节时，通过 CanonicalBinding 回溯到 local 层。

### 3.6 Global 层的内容引用

Global 层**通常不存储内容**——knowledge 的 content 通过 `representative_lcn` 引用 local 层，factor 的 steps 保留在 local 层。

- **GlobalCanonicalNode** 通过 `representative_lcn` 引用 local canonical 节点获取 content。当多个 local 节点映射到同一 global 节点时，选择一个作为代表，所有映射记录在 `member_local_nodes` 中。
- **Global factor** 不携带 `steps`（§3.5）。推理过程的文本保留在 local 层的 factor 中。

**例外：subgraph 创建的中间节点。** subgraph 展开时新创建的 knowledge 节点（如 prediction）没有 local 来源，其 content 直接存储在 GlobalCanonicalNode 上（见 §2.6）。

需要查看具体内容时，通过 CanonicalBinding 回溯到 local 层。Global 层是**结构索引**，local 层是**内容仓库**——subgraph 中间节点是唯一的例外。

---

## 源代码

- `libs/graph_ir/models.py` -- `LocalCanonicalGraph`, `LocalCanonicalNode`, `FactorNode`
- `libs/storage/models.py` -- `GlobalCanonicalNode`, `CanonicalBinding`
- `libs/global_graph/canonicalize.py` -- `canonicalize_package()`
- `libs/global_graph/similarity.py` -- `find_best_match()`
