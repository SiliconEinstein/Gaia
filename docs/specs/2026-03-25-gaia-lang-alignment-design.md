# Gaia Language 对齐设计 — 基于 theory + graph-ir 基准

> **Status:** Target design
>
> **目的：** 将 gaia-lang 文档对齐到已收敛的 theory/ 和 graph-ir/ 基准。本文档定义变更内容和设计决策。

## 1. 背景

Theory 目录（reasoning-hypergraph.md, science-formalization.md 等）和 graph-ir 目录已收敛为基准。当前 gaia-lang 文档（spec.md, knowledge-types.md, package-model.md）存在多处与基准不一致。

### 1.1 已识别的差距

| 差距 | 当前 gaia-lang | 基准 (theory + graph-ir) |
|------|---------------|------------------------|
| 知识类型 | claim, setting, question, **action** | claim, setting, question, **template** |
| 矛盾/等价 | Knowledge 节点类型 | FactorNode 的 reasoning_type |
| Setting BP 参与 | 有 prior，可判真 | 不携带 probability，不参与 BP |
| Chain | 作为 gaia-lang 数据模型概念 | graph-ir 中不存在 |
| 编译映射 | 未文档化 | — |
| 合取语义 | 未提及 | noisy-AND（粗因子图） |

## 2. 声明类型变更

### 2.1 删除 `#action`

`#action` 与 `#claim(kind: "computation"/"python")` 语义重叠。Graph-ir 中没有 `action` 类型。

移除后，作者使用 `#claim(kind: ...)` 表达程序性步骤。`kind` 编译为 `KnowledgeNode.metadata: {schema: <kind>}`，纯描述性，不改变拓扑。

### 2.2 保留三种声明类型

| 声明 | graph-ir type | 参与 BP | `from:` | `kind:` |
|------|-------------|---------|---------|---------|
| `#claim` | claim | 是 | 可选 | 可选 |
| `#setting` | setting | 否（无 prior） | 否 | 否 |
| `#question` | question | 否 | 否 | 否 |

### 2.3 Setting 语义修正

Setting 不携带 prior，不参与 BP。可作为 factor 的承载性前提（structural dependency），但不创建 BP 边。对齐 theory（reasoning-hypergraph.md §6.2）和 graph-ir（graph-ir.md §1.2）。

**Setting 作为前提：** Claim 可以通过 `from:` 引用 setting 作为前提。Setting 出现在编译后 FactorNode 的 `premises` 列表中，但按 graph-ir §2.5 的 BP 参与规则，non-claim premise 不参与 BP 消息传递。参见 science-formalization.md 中 S_vac、S_plane 作为 entailment 前提的例子。

### 2.4 证明状态分类

当前 knowledge-types.md 定义的证明状态分类（Theorem, Assumption, Hole, Conjecture）在本次变更后需要重新审视：删除 `#action`、新增论证策略可能影响证明状态的判定逻辑。具体调整作为实现阶段的任务。

### 2.5 Defer `#template`

Graph-ir 中 `template` 类型保留，但 gaia-lang v1 暂不暴露。待通用 template 机制设计后引入（见 §7 Ideas）。

## 3. 关系类型与编译目标

### 3.1 关系类型不变

- `#relation(type: "contradiction", between: (<A>, <B>))`
- `#relation(type: "equivalence", between: (<A>, <B>))`

### 3.2 编译目标修正

`#relation` 编译为 **FactorNode**，不是 KnowledgeNode。

```typst
#relation(type: "contradiction", between: (<claim_a>, <claim_b>))[描述]
```

编译为：

```
FactorNode:
  category: infer
  stage: initial
  reasoning_type: contradict
  premises: [claim_a, claim_b]
  conclusion: None
```

Equivalence 同理（`reasoning_type: equivalent`）。

**注意：** 当前 bp/potentials.md 的 contradiction/equivalence 设计中有一个 Relation node R 作为 `premises[0]` 参与 BP（允许"质疑关系本身"）。这与 graph-ir 的定义不一致——graph-ir 中 contradict/equivalent factor 没有 R 节点。本 spec 对齐 graph-ir。potentials.md 需要在 bp/ 层更新时单独处理 R 节点的去留问题。

### 3.3 知识类型枚举变更

Knowledge.type 枚举移除 `contradiction | equivalence`。知识类型只剩 `claim | setting | question`。

Graph-ir 另有 `template`，gaia-lang 暂不暴露。

## 4. 论证策略

新增四个论证策略（argumentation strategies）。编译器自动从粗因子图展开为细因子图。

**核心原理：**
- 粗因子图：作者的自然推理方向，factor 有 weakpoint（p < 1）
- 细因子图：编译器展开为 entailment (p≈1) + equivalence + contradiction 的组合
- 展开后所有链的 p ≈ 1，不确定性从"推理链强度"转移到"命题是否为真"

**合取语义：** Noisy-AND 仅适用于粗因子图（单个 factor 的多个 premise 是联合必要条件）。细因子图由多个独立 factor 组合，不涉及 noisy-AND——推理效果通过 BP 消息传递协作实现。

### 4.1 `#abduction`（溯因）

**语法：**

```typst
#claim[暗物质存在] <hypo.dark_matter>
#claim(kind: "observation")[星系旋转曲线平坦] <obs.rotation>

#abduction(
  hypothesis: <hypo.dark_matter>,
  observation: <obs.rotation>,
)[暗物质引力效应使外围恒星轨道速度偏高，旋转曲线应保持平坦]
```

**粗因子图：** `[] → H`（无 noisy-AND premise，H 是 conclusion）

> 注：`[] → H` 表示在粗因子视角下，abduction 的 conclusion 是 hypothesis，且没有 noisy-AND 意义上的 premise。观测证据不作为 premise，而是在细因子图中通过 equivalence 连接。这与 graph-ir 中 abduction 的 `premises: [supporting_knowledge]` 不冲突——supporting_knowledge 是承载性依赖，不是 noisy-AND premise。

**细因子图：**
- O claim（predicted observation，编译器自动生成）
- entailment: H → O（steps = 作者的 justification body）
- equivalent: O ≡ O'（O' = 作者传入的 observation 引用）

**BP 路径：** O' belief 高（实验证据）→ equiv 传递给 O → entailment 反向消息提升 H 的 belief。

**参数说明：**
- `hypothesis:` — 指向一个 claim 的标签引用，是 abduction 的 conclusion（要论证的假说）
- `observation:` — 指向一个 claim 的标签引用，有自己独立的证据链
- Body — justification：为什么 H 能预测 O。编译为生成的 entailment factor 的 `steps` 字段。

### 4.2 `#induction`（归纳）

**语法：**

```typst
#claim(kind: "observation")[铜导电] <obs.cu>
#claim(kind: "observation")[铁导电] <obs.fe>
#claim(kind: "observation")[铝导电] <obs.al>
#claim[所有金属都导电] <law.metal_conduct>

#induction(
  law: <law.metal_conduct>,
  instances: (<obs.cu>, <obs.fe>, <obs.al>),
)[金属的共同电子结构（自由电子气）使其具有导电性]
```

**粗因子图：** `[A₁, A₂, A₃] → B`（实例是 premise，定律是 conclusion，noisy-AND）

**细因子图：**
- entailment: B → A₁（p≈1）
- entailment: B → A₂（p≈1）
- entailment: B → A₃（p≈1）

**BP 路径：** 多个 Aᵢ belief 高（观测）→ 各 entailment 反向消息共同提升 B 的 belief。

**参数说明：**
- `law:` — 指向一个 claim 的标签引用，是归纳的 conclusion（一般性定律）
- `instances:` — 标签引用元组，支撑定律的具体观测实例
- Body — justification：为什么 B 能蕴含这些实例

### 4.3 `#analogy`（类比）

**语法：**

```typst
#claim[光具有衍射现象] <source.light_diffraction>
#claim[电子具有衍射现象] <target.electron_diffraction>

#analogy(
  source: <source.light_diffraction>,
  target: <target.electron_diffraction>,
)[光和电子都满足波动方程，共享波动性的核心特征]
```

**粗因子图：** `[source] → target`（source 是 premise，target 是 conclusion）

**细因子图：**
- analogy_claim（编译器生成：两个系统具有结构类比关系）
- entailment: [source, analogy_claim] → target（p≈1）

**BP 路径：** source belief 高 + analogy_claim belief 高 → target 获得支持。如果类比被质疑（analogy_claim belief 下降），target 支持减弱。

**参数说明：**
- `source:` — 源系统的已知性质（高 belief 的 claim）
- `target:` — 目标系统的对应性质（要论证的 claim）
- Body — justification：为什么两个系统结构相似。编译为生成的 entailment factor 的 `steps` 字段。

**与 science-formalization.md 的关系：** science-formalization.md §2.3 的 analogy 模式有三个前提 `[G_src, M, S_target] → V_target`，其中 M 是类比桥梁，S_target 是目标域条件。本设计简化为 `[source, analogy_claim] → target`——`analogy_claim` 对应 M，而 S_target（目标域条件）在 v1 中不作为独立前提，作者可在 justification 中描述。如果目标域条件需要独立参与 BP，作者可用 `from:` 手动构建更精细的结构。

### 4.4 `#extrapolation`（外推）

语法和编译结构与 `#analogy` 完全相同。语义区别：跨范围外推而非跨系统迁移。

**语法：**

```typst
#extrapolation(
  source: <obs.known_range>,
  target: <pred.extended_range>,
)[该温度区间无相变，同一物理机制仍主导电阻行为]
```

**粗因子图：** `[source] → target`

**细因子图：**
- extrapolation_claim（编译器生成：外推条件成立）
- entailment: [source, extrapolation_claim] → target（p≈1）

### 4.5 总结

| 策略 | 粗因子图 | 细因子图 |
|------|---------|---------|
| `#abduction` | `[] → H` | H→O + O≡O' |
| `#induction` | `[A₁..Aₙ] → B` | B→A₁, B→A₂, ... |
| `#analogy` | `[source] → target` | [source, analogy_claim]→target |
| `#extrapolation` | `[source] → target` | [source, extrap_claim]→target |

`from:` 保留作为通用 entailment（粗因子），论证策略是更精确的替代。

### 4.6 语言分类

| 类别 | 构件 | 作用 |
|------|------|------|
| **声明** | `#setting`, `#question`, `#claim` | 声明知识对象 |
| **关系** | `#relation(type: "contradiction" \| "equivalence")` | 结构约束（编译为 FactorNode） |
| **论证策略** | `#abduction`, `#induction`, `#analogy`, `#extrapolation` | 程序化生成细因子图 |

## 5. 结构简化

### 5.1 移除 Chain

Chain 从 gaia-lang 层完全移除。语言中没有 `#chain` 语法，Chain 是数据模型层的概念。如果未来需要，属于 CLI 展示层或存储层。

层级简化为：

```
Package → Module → Knowledge
                   Factor 由 from: / 论证策略 / #relation 生成
```

### 5.2 `from:` → Factor 编译映射

```typst
#claim(from: (<premise_a>, <premise_b>))[conclusion][proof]
```

编译为：

```
FactorNode:
  category: infer
  stage: initial
  reasoning_type: None  （或作者指定）
  premises: [premise_a, premise_b]
  conclusion: this_claim
  steps: [{reasoning: proof_content}]
  weak_points: []
```

- `category: infer`（默认，人类推理）
- `stage: initial`（待 review）
- `reasoning_type: None`（默认，由后续 review 确定具体类型。如果作者通过论证策略生成 factor，reasoning_type 由策略指定。）
- `steps` 来自 `[proof]` 内容块（论证策略生成的 factor 同理，body 编译为 `steps`）

### 5.3 合取语义

`from:` 创建的粗因子，其多个前提遵循 noisy-AND 语义（联合必要条件）。

论证策略（`#abduction` 等）生成细因子图，由 entailment + equivalence + contradiction 组合而成，不涉及 noisy-AND。

参见 theory 层 reasoning-hypergraph.md §4.1 和 science-formalization.md §2.4。

## 6. 需更新的文件

| 文件 | 变更 |
|------|------|
| `docs/foundations/gaia-lang/spec.md` | 删除 `#action`，新增论证策略语法，更新声明表，补充编译映射 |
| `docs/foundations/gaia-lang/knowledge-types.md` | 修正 Setting 语义，移除 contradiction/equivalence 知识类型，修复重复链接 (line 83)，补充合取语义说明 |
| `docs/foundations/gaia-lang/package-model.md` | 移除 Chain，简化层级，更新 Knowledge.type 枚举描述 |

## 7. Ideas（需要 graph-ir 变更，defer）

以下概念写入 `docs/ideas/`：

| 文档 | 内容 | 依赖 |
|------|------|------|
| `negation-relation.md` | negation 作为第六个 reasoning_type，potential 函数（惩罚 (1,1) 和 (0,0)） | graph-ir 变更 |
| `reductio-strategy.md` | `#reductio` 论证策略，粗因子 contradict(P,R)，细因子 P→Q + contradict(Q,R) + negation(P,¬P) | negation |
| `elimination-strategy.md` | `#elimination` 论证策略，粗因子 [E₁,E₂]→H₃，细因子 pairwise contradiction + exhaustive constraint | negation |
| `template-mechanism.md` | 通用 template 机制（可参数化的图结构生成器），含否命题构造、推理模式等用例 | graph-ir 变更 |

## 跨层引用

- **Theory 层**：reasoning-hypergraph.md（知识类型、算子分类）、science-formalization.md（粗/细因子图、子图模式）
- **Graph IR 层**：graph-ir.md（KnowledgeNode/FactorNode schema、BP 参与规则）、overview.md（三对象分离）
- **BP 层**：potentials.md（potential 函数）、belief-propagation.md（noisy-AND、四个三段论）
