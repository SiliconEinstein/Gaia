# Gaia IR 概述

> **Status:** Target design — Gaia IR 结构层对齐 [01-plausible-reasoning.md](../theory/01-plausible-reasoning.md) 到 [05-formalization-methodology.md](../theory/05-formalization-methodology.md)；本文后半同时概览其下游相邻层 [06-factor-graphs.md](../theory/06-factor-graphs.md) 与 [07-belief-propagation.md](../theory/07-belief-propagation.md)
>
> **⚠️ Protected Contract Layer** — 本目录定义 CLI↔LKM 结构契约。变更需要独立 PR 并经负责人审查批准。详见 [documentation-policy.md](../../documentation-policy.md#12-变更控制)。

## 目的

Gaia IR 是 Gaia 命题网络与推理结构的核心数据表示。读完本文档，你应当知道：

- Gaia IR 本身编码什么结构
- local 与 global 在 persistent contract 中各自负责什么
- Parameterization 如何作为下游参数层附着在同一批对象上
- BeliefState 如何作为运行结果引用这些对象

Gaia 的数据由三个彼此分离、先后衔接的对象组成：

```
Gaia IR（结构契约）    ×    Parameterization（参数记录）    →    BeliefState（运行结果）
local: Knowledge / Strategy / Operator     prior / conditional probabilities     当前推理器计算出的后验
global: canonical Knowledge + Binding      review / calibration 产出             runtime 产出
```

三者严格分离。

- **Gaia IR** 定义 persistent 结构对象
- **Parameterization** 记录可替换的概率参数
- **BeliefState** 记录某次 runtime 对某个投影视图的计算结果

在当前收缩后的 v2 里，persistent IR 只保留两类全局对象：

- **GlobalCanonicalKnowledgeStore**：跨包统一后的 canonical Knowledge
- **CanonicalBinding**：`lcn -> gcn` 的身份映射

完整的推理结构仍主要保留在 local graph 中：

- `Knowledge`
- `Strategy`
- `Operator`

如果下游运行时需要“全局可计算图”，那是从若干 local graph 通过 `CanonicalBinding` **派生编译**出来的视图，而不是 protected contract 中持久存储的 global strategy/operator 集合。

## 一、Gaia IR — 结构

Gaia IR 编码**什么连接什么**。它不直接存储概率，也不依赖某个特定推理算法。

在 persistent contract 中，Gaia IR 分成两层：

- **LocalCanonicalGraph**：包内完整结构。存储 `Knowledge / Strategy / Operator / steps / content`
- **GlobalCanonicalKnowledgeStore**：跨包命题身份层。只存 canonical Knowledge
- **CanonicalBinding**：把 local claim 接到 global canonical claim 上

### 整体结构

**Local 层示例**（包内，存储完整内容与推理结构）：

```json
{
  "scope": "local",
  "ir_hash": "sha256:...",
  "knowledges": [
    {
      "id": "lcn_a3f2...",
      "type": "claim",
      "content": "该样本在 90 K 以下表现出超导性"
    },
    {
      "id": "lcn_b7e1...",
      "type": "claim",
      "content": "YBa2Cu3O7 的超导转变温度为 92 ± 1 K"
    },
    {
      "id": "lcn_c9a0...",
      "type": "setting",
      "content": "高温超导研究的当前进展"
    },
    {
      "id": "lcn_e4b7...",
      "type": "claim",
      "content": "forall{x}. superconductor({x}) -> zero_resistance({x})",
      "parameters": [{"name": "x", "type": "material"}]
    },
    {
      "id": "lcn_f5c8...",
      "type": "setting",
      "content": "x = YBCO"
    },
    {
      "id": "lcn_g6d9...",
      "type": "claim",
      "content": "superconductor(YBCO) -> zero_resistance(YBCO)"
    }
  ],
  "strategies": [
    {
      "strategy_id": "lcs_d2c8...",
      "type": "infer",
      "premises": ["lcn_a3f2..."],
      "conclusion": "lcn_b7e1...",
      "background": ["lcn_c9a0..."],
      "steps": [{"reasoning": "基于超导样品的电阻率骤降..."}]
    },
    {
      "strategy_id": "lcs_h7ea...",
      "type": "deduction",
      "premises": ["lcn_e4b7..."],
      "conclusion": "lcn_g6d9...",
      "background": ["lcn_f5c8..."]
    }
  ],
  "operators": [
    {
      "operator_id": "lco_q1...",
      "operator": "equivalence",
      "variables": ["lcn_g6d9...", "lcn_b7e1..."],
      "conclusion": "lcn_eq1..."
    }
  ]
}
```

**Global 层示例**（跨包，只负责命题身份统一）：

```json
{
  "scope": "global",
  "knowledges": [
    {
      "id": "gcn_a1...",
      "type": "claim",
      "representative_lcn": {
        "package_id": "pkg_a",
        "version": "1.0.0",
        "knowledge_id": "lcn_a3f2..."
      },
      "local_members": [
        {"package_id": "pkg_a", "version": "1.0.0", "knowledge_id": "lcn_a3f2..."},
        {"package_id": "pkg_b", "version": "2.1.0", "knowledge_id": "lcn_z8f1..."}
      ]
    },
    {
      "id": "gcn_b2...",
      "type": "claim",
      "representative_lcn": {
        "package_id": "pkg_a",
        "version": "1.0.0",
        "knowledge_id": "lcn_b7e1..."
      },
      "local_members": [
        {"package_id": "pkg_a", "version": "1.0.0", "knowledge_id": "lcn_b7e1..."}
      ]
    }
  ],
  "canonical_bindings": [
    {
      "local_canonical_id": "lcn_a3f2...",
      "global_canonical_id": "gcn_a1...",
      "package_id": "pkg_a",
      "version": "1.0.0",
      "decision": "create_new"
    },
    {
      "local_canonical_id": "lcn_z8f1...",
      "global_canonical_id": "gcn_a1...",
      "package_id": "pkg_b",
      "version": "2.1.0",
      "decision": "match_existing"
    }
  ]
}
```

global 层不持久存储 Strategy 或 Operator。服务器 curation 若要补充关系或推理，应提交一个**特殊来源的 local/curation package**，而不是直接写入 global core。

### Knowledge（命题）

Knowledge 表示命题。三种类型：

| type | 说明 | 参与概率推理 | 可作为 |
|------|------|-------------|--------|
| **claim** | 科学断言（封闭或全称） | 是 | premise, background, conclusion, refs |
| **setting** | 背景信息 | 否 | background, refs |
| **question** | 待研究方向 | 否 | background, refs |

其中 helper claim 仍然是普通的 `claim`，不是新的顶层类型。标准 helper claim 目录见 [helper-claims.md](helper-claims.md)。

详细 schema 见 [gaia-ir-v2-draft.md](gaia-ir-v2-draft.md) §1。

### Strategy（推理声明）

Strategy 表示不确定推理声明，连接 premise 与 conclusion。它有三种形态：

| 形态 | 说明 | 独有字段 |
|------|------|---------|
| **Strategy** | 叶子推理，折叠时表现为单条 ↝ | — |
| **CompositeStrategy** | 含子策略，可递归嵌套 | `sub_strategies` |
| **FormalStrategy** | 含确定性 Operator 展开 | `formal_expr` |

关键边界：

- Strategy 只在 **local graph** 中持久存在
- global core 不持久存储 `gcs_` 之类的 global Strategy
- 如果运行时需要跨包使用某条 Strategy，应通过 `CanonicalBinding` 把它的 `lcn_` 端点映射到 `gcn_`，形成**派生的 runtime projection**

`infer` 是对旧 `soft implication` 的更一般推广；`noisy_and` 是其常见受限特例。`deduction / abduction / induction / analogy / extrapolation` 等命名策略则通过 `CompositeStrategy / FormalStrategy` 进一步落地。

详细 schema 见 [gaia-ir-v2-draft.md](gaia-ir-v2-draft.md) §3。

### Operator（结构约束）

Operator 表示确定性逻辑关系，如 `equivalence`、`contradiction`、`complement`、`implication`、`conjunction`、`disjunction`。它们没有自由参数。

当前 v2 约定：**每个 Operator 都有 `conclusion`**。这个 `conclusion` 表示该 Operator 的标准结果 claim。

- `implication` / `conjunction` 的 `conclusion` 延续现有“输出 claim”语义
- `equivalence` / `contradiction` / `complement` / `disjunction` 的 `conclusion` 是 compiler-generated 的标准 helper claim，使这些关系本身也能被引用

关键边界：

- Operator 也只在 **local graph** 中持久存在
- global core 不维护 persistent global operator set
- 服务器 curation 若要声明新的结构关系，也应通过特殊来源的 local/curation package 提交

详细 schema 见 [gaia-ir-v2-draft.md](gaia-ir-v2-draft.md) §2，helper claim 目录见 [helper-claims.md](helper-claims.md)。

### FormalExpr（嵌入字段）

FormalExpr 是 FormalStrategy 的确定性展开结构，由 Operator 列表构成。它不是独立顶层实体。

需要被后续步骤引用、review 或复用的 helper claim，应显式写入顶层 `knowledges`。仅服务于单个 FormalExpr 的局部结构节点，可由 compiler 在 local graph 内生成。

详细 schema 见 [gaia-ir-v2-draft.md](gaia-ir-v2-draft.md) §3.2。

### 两层身份与持久边界

| 对象 | 范围 | ID 前缀 | 作用 |
|------|------|---------|------|
| **LocalCanonicalGraph** | 单个包 | `lcn_`, `lcs_`, `lco_` | 存储完整内容、推理结构和步骤 |
| **GlobalCanonicalKnowledgeStore** | 跨包命题身份层 | `gcn_` | 只存 canonical Knowledge |
| **CanonicalBinding** | local→global 映射 | — | 把 `lcn_` 接到 `gcn_` 上 |

这意味着：

- global core 的职责是**命题身份统一**
- local graph 的职责是**结构表达与内容存储**
- “全局可计算图”不是 persistent core，而是从 selected local graphs 派生出来的 runtime view

规范化流程见 [gaia-ir-v2-draft.md](gaia-ir-v2-draft.md) §4。

### 图哈希

LocalCanonicalGraph 有确定性哈希 `ir_hash = SHA-256(canonical JSON)`，用于编译完整性校验。GlobalCanonicalKnowledgeStore 是增量变化的索引层，不使用整体哈希。

## 二、Parameterization — 参数

Parameterization 是 Gaia IR 的下游参数层。它不改变 persistent IR 的对象边界，而是为**当前将被运行时使用的对象**提供概率值。

在当前收缩后的 v2 里，参数记录挂载在两类对象上：

- **PriorRecord**：挂在 global canonical claim（`gcn_`）上
- **StrategyParamRecord**：挂在 local Strategy 引用上，例如 `LocalStrategyRef(package_id, version, strategy_id)`

也就是说：

- claim 的 prior 是全局共享的
- Strategy 的 conditional probabilities 仍跟随 local graph 中的那条 Strategy

这与 persistent IR 的边界一致：global 只统一命题身份，不统一推理边。

### 存储层

```json
// PriorRecord
{"gcn_id": "gcn_8b1c...", "value": 0.7, "source_id": "src_001", "created_at": "..."}

// StrategyParamRecord
{
  "strategy_ref": {
    "package_id": "pkg_a",
    "version": "1.0.0",
    "strategy_id": "lcs_d2c8..."
  },
  "conditional_probabilities": [0.85],
  "source_id": "src_001",
  "created_at": "..."
}

// ParameterizationSource
{"source_id": "src_001", "model": "gpt-5-mini", "policy": "conservative", "created_at": "..."}
```

### 运行时组装（当前 BP 管线）

当前 BP 管线在运行前做三件事：

1. 选择要参与本次运行的 local package / curation package
2. 用 `CanonicalBinding` 把这些 local graph 的 `lcn_` 映射到 `gcn_`
3. 按 resolution policy 选取 PriorRecord 与 StrategyParamRecord，编译出临时 runtime projection

关键规则：

- `PriorRecord` 只针对 `type=claim` 的 canonical Knowledge
- `StrategyParamRecord` 只针对本次 projection 中会以折叠形式运行的 local Strategy
- Operator 没有独立参数
- runtime projection 是现算的，不是 protected contract 的 persistent 对象

详细设计见 [parameterization.md](parameterization.md)。

## 三、BeliefState — 信念

BeliefState 是下游推理在某个 runtime projection 上的纯输出。它的 belief 值按 `gcn_` 记录，因此不同 local package 的证据会在 canonical claim 上汇聚。

### 整体结构

```json
{
  "bp_run_id": "uuid-...",
  "created_at": "2026-03-24T12:00:00Z",
  "resolution_policy": "latest",
  "projection_policy": {
    "packages": ["pkg_a@1.0.0", "curation/equivalence/ybco@2026-03-27"]
  },
  "beliefs": {
    "gcn_8b1c...": 0.82,
    "gcn_9d2a...": 0.71
  },
  "converged": true,
  "iterations": 23,
  "max_residual": 4.2e-7
}
```

关键规则：

- `beliefs` 只对 canonical claim 记录
- `projection_policy + resolution_policy` 共同定义这次运行使用了哪些 local 图、哪些参数记录
- 同一批 `gcn_` 可以在不同 projection / policy 下多次运行

详细设计见 [belief-state.md](belief-state.md)。

## 完备性

一个完整的 Gaia 知识体系需要以下信息：

| 对象 | 内容 | 变化频率 |
|------|------|---------|
| **LocalCanonicalGraph** | 包内 Knowledge + Strategy + Operator + 完整文本 | 每次 build 更新 |
| **GlobalCanonicalKnowledgeStore** | 跨包 canonical Knowledge | 每次 ingest 更新 |
| **CanonicalBinding** | `lcn -> gcn` 映射记录 | 每次 ingest 更新 |
| **PriorRecord** | canonical claim 的 prior（每条记录携带 source） | 每次 review 追加 |
| **StrategyParamRecord** | local Strategy 的 conditional probabilities（每条记录携带 source） | 每次 review 追加 |
| **ParameterizationSource** | review 来源信息（模型、策略、配置） | 每次 review 创建 |
| **RuntimeProjection** | 从 selected local graphs 派生出的临时可计算视图 | 每次运行现算 |
| **BeliefState** | canonical claim 的后验信念 + 运行策略 | 每次 runtime 创建 |

## 源代码

- `libs/graph_ir/models.py` -- `Knowledge`, `Strategy`, `Operator`, parameter records
- `libs/global_graph/canonicalize.py` -- `CanonicalBinding`, knowledge canonicalization
- `libs/global_graph/similarity.py` -- `find_best_match()`
- `libs/inference/factor_graph.py` -- runtime projection / BP 编译
