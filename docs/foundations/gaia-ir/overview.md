# Gaia IR 概述

> **Status:** Target design — Gaia IR 结构层对齐 [01-plausible-reasoning.md](../theory/01-plausible-reasoning.md) 到 [05-formalization-methodology.md](../theory/05-formalization-methodology.md)；本文后半同时概览其下游相邻层 [06-factor-graphs.md](../theory/06-factor-graphs.md) 与 [07-belief-propagation.md](../theory/07-belief-propagation.md)
>
> **⚠️ Protected Contract Layer** — 本目录定义 CLI↔LKM 结构契约。变更需要独立 PR 并经负责人审查批准。详见 [documentation-policy.md](../../documentation-policy.md#12-变更控制)。

## 目的

Gaia IR 是 Gaia 命题网络与推理结构的核心数据表示。读完本文档，你应当知道：

- Gaia IR 本身编码什么结构
- Parameterization 如何作为下游参数层附着在该结构上
- BeliefState 如何作为运行结果引用同一结构

Gaia 的数据由三个彼此分离、先后衔接的对象组成：

```
Gaia IR（结构契约）    ×    Parameterization（参数记录）    →    BeliefState（运行结果）
命题、Strategy、Operator     每个 Knowledge/Strategy 多可信      当前推理器计算出的后验
编译/规范化确定               review 产出                        runtime 产出
```

三者严格分离。Gaia IR 有 local 和 global 两层。Parameterization 和 BeliefState 只作用在 GlobalCanonicalGraph 上。

在当前 v2 口径里，`GlobalCanonicalGraph` 在逻辑上再拆成两个协同子图：

- `GlobalSemanticGraph`：canonical claim 与被接受的顶层 Operator
- `GlobalContributionGraph`：由 local 图提升上来的 global Strategy contribution

本文的重点是第一部分的 **Gaia IR — 结构**。第二、三部分讨论的是下游相邻层；当前实现以 factor graph / BP 管线为例，但这些运行时选择**不反向定义** Gaia IR 的本体边界。

## 一、Gaia IR — 结构

Gaia IR 编码**什么连接什么**——命题、推理声明与确定性结构约束之间的连接关系。它不包含任何概率值，也不依赖某个特定推理算法。

Gaia IR 由三种实体构成：**Knowledge**（命题）、**Strategy**（推理声明）、**Operator**（结构约束）。Strategy 有三种形态：基础 Strategy（↝ 叶子）、CompositeStrategy（含子策略，可递归嵌套）和 FormalStrategy（含确定性展开 FormalExpr）。

### 整体结构

**Local 层示例**（包内，存储完整内容）：

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
      "content": "YBa₂Cu₃O₇ 的超导转变温度为 92 ± 1 K"
    },
    {
      "id": "lcn_c9a0...",
      "type": "setting",
      "content": "高温超导研究的当前进展"
    },
    {
      "_comment": "全称 claim（原 template）— 通用定律，含量化变量，可进入下游概率推理",
      "id": "lcn_e4b7...",
      "type": "claim",
      "content": "∀{x}. superconductor({x}) → zero_resistance({x})",
      "parameters": [{"name": "x", "type": "material"}]
    },
    {
      "_comment": "绑定 setting — 实例化时提供具体参数值",
      "id": "lcn_f5c8...",
      "type": "setting",
      "content": "x = YBa₂Cu₃O₇（YBCO）"
    },
    {
      "_comment": "实例化后的封闭 claim",
      "id": "lcn_g6d9...",
      "type": "claim",
      "content": "superconductor(YBCO) → zero_resistance(YBCO)"
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
      "_comment": "全称 claim 的实例化 — deduction, p₁=1.0",
      "strategy_id": "lcs_h7ea...",
      "type": "deduction",
      "premises": ["lcn_e4b7..."],
      "conclusion": "lcn_g6d9...",
      "background": ["lcn_f5c8..."]
    }
  ],
  "operators": []
}
```

**Global 层示例**（跨包，semantic subgraph + contribution subgraph）：

```json
{
  "scope": "global",
  "knowledges": [
    {"id": "gcn_a1...", "type": "claim"},
    {"id": "gcn_b2...", "type": "claim"},
    {"id": "gcn_d4...", "type": "claim"},
    {"id": "gcn_m1...", "type": "claim", "content": "gcn_a1 ∧ gcn_b2"},
    {"id": "gcn_eq1...", "type": "claim", "content": "gcn_a1 与 gcn_x9 同真同假"}
  ],
  "strategies": [
    {
      "_comment": "Strategy contribution（由 local strategy 提升）",
      "strategy_id": "gcs_s1...",
      "source_lcs": {"package_id": "pkg_a", "version": "1.0.0", "strategy_id": "lcs_s1..."},
      "type": "infer",
      "premises": ["gcn_a1..."],
      "conclusion": "gcn_b2..."
    },
    {
      "_comment": "CompositeStrategy contribution（含子策略）",
      "strategy_id": "gcs_s2...",
      "source_lcs": {"package_id": "pkg_b", "version": "2.1.0", "strategy_id": "lcs_s2..."},
      "type": "infer",
      "premises": ["gcn_a1...", "gcn_b2..."],
      "conclusion": "gcn_d4...",
      "sub_strategies": ["gcs_s1...", "gcs_s3..."]
    },
    {
      "_comment": "FormalStrategy contribution（确定性展开）",
      "strategy_id": "gcs_s3...",
      "source_lcs": {"package_id": "pkg_b", "version": "2.1.0", "strategy_id": "lcs_s3..."},
      "type": "deduction",
      "premises": ["gcn_a1...", "gcn_b2..."],
      "conclusion": "gcn_d4...",
      "formal_expr": {
        "operators": [
          {"operator_id": "gco_1...", "operator": "conjunction",
           "variables": ["gcn_a1...", "gcn_b2...", "gcn_m1..."], "conclusion": "gcn_m1..."},
          {"operator_id": "gco_2...", "operator": "implication",
           "variables": ["gcn_m1...", "gcn_d4..."], "conclusion": "gcn_d4..."}
        ]
      }
    }
  ],
  "operators": [
    {
      "_comment": "standalone Operator（规范化产生的等价候选，位置即来源——顶层 = 独立结构关系）",
      "operator_id": "gco_e1...",
      "operator": "equivalence",
      "variables": ["gcn_a1...", "gcn_x9..."],
      "conclusion": "gcn_eq1..."
    }
  ]
}
```

Global 层的 claim 通常不存储 content（通过 `representative_lcn` 引用 local 层）。而 `gcs_` 表示的是**保留来源的 Strategy contribution**，不是跨包 dedupe 后的“全局唯一 strategy”。LKM 服务器直接创建的 Knowledge（包括 FormalExpr 中间 Knowledge 如 `gcn_m1`）无 local 来源，content 直接存在 global 层。

### Knowledge（命题）

表示命题。三种类型：

| type | 说明 | 参与 BP | 可作为 |
|------|------|---------|--------|
| **claim** | 科学断言（封闭或全称） | 是（唯一可直接承载 prior/belief 的类型） | premise, background, conclusion, refs |
| **setting** | 背景信息 | 否 | background, refs |
| **question** | 待研究方向 | 否 | background, refs |

其中 **helper claim 仍然是 `claim`**，不是新的 Knowledge 类型。标准 helper claim 目录见 [helper-claims.md](helper-claims.md)。

详细 schema 见 [gaia-ir.md](gaia-ir.md) §1。

### Strategy（推理声明）

表示推理算子，连接 Knowledge。Strategy 有三种形态（类层级）：

| 形态 | 说明 | 独有字段 |
|------|------|---------|
| **Strategy**（基类，可实例化） | 叶子推理，编译为 ↝ | — |
| **CompositeStrategy**(Strategy) | 含子策略，可递归嵌套 | `sub_strategies: list[str]` |
| **FormalStrategy**(Strategy) | 含确定性 Operator 展开 | `formal_expr: FormalExpr` |

所有形态折叠时均编译为 ↝（概率参数来自 [parameterization](parameterization.md) 层）。展开时进入内部结构（子策略或确定性 Operator）。这支持**多分辨率使用**——下游推理器可在不同粒度消费同一图。

在 global 层，Strategy 的语义是：**来自某个 local package/version 的 contribution instance**。也就是说，多个 package 即使产出结构完全相同的推理，也应保留为多条 `gcs_` 记录；是否“结构相似”可以额外分组，但不应自动合并为单一 global Strategy。

统一 `type` 字段（与形态正交）：

| type | 参数化模型 | 经历 lifecycle | 形态 |
|------|-----------|---------------|------|
| **infer** | 完整 CPT: 2^K（默认 MaxEnt 0.5） | 是 | Strategy 或 CompositeStrategy |
| **noisy_and** | ∧ + 单参数 p | 是 | Strategy 或 CompositeStrategy |
| **deduction** | — | 是 | FormalStrategy |
| **abduction** | — | 是 | CompositeStrategy（含 FormalStrategy 子部分） |
| **induction** | — | 是 | CompositeStrategy（含 FormalStrategy 子部分） |
| **analogy** | — | 是 | CompositeStrategy（含 FormalStrategy 子部分） |
| **extrapolation** | — | 是 | CompositeStrategy（含 FormalStrategy 子部分） |
| **reductio** | — | 是 | FormalStrategy |
| **elimination** | — | 是 | FormalStrategy |
| **mathematical_induction** | — | 是 | FormalStrategy |
| **case_analysis** | — | 是 | FormalStrategy |
| **toolcall** | 另行定义 | 否 | Strategy |
| **proof** | 另行定义 | 否 | Strategy |

其中 `infer` 是更一般的条件支撑模型，覆盖旧 `soft_implication` 的更强表达；`independent_evidence` / `contradiction` 则不再作为 Strategy 类型，而是直接落到 Operator。

详细 schema 见 [gaia-ir.md](gaia-ir.md) §2。

### Operator（结构约束）

确定性逻辑关系（equivalence, contradiction, complement, implication, disjunction, conjunction）。它们首先是 theory 中的命题结构约束；在下游 factor-graph 编译中，可进一步映射为硬约束势函数。所有算子本身均确定性（ψ ∈ {0, 1}，无自由参数）。

当前 v2 约定：**每个 Operator 都有 `conclusion`**。对 `equivalence` / `contradiction` / `complement` / `disjunction` 这类关系型算子，`conclusion` 是 compiler-generated 的标准 helper claim，使这些关系本身也能被后续工作引用。Schema 见 [gaia-ir.md](gaia-ir.md) §3，helper claim 目录见 [helper-claims.md](helper-claims.md)。

### FormalExpr（data class，非顶层实体）

FormalStrategy 的确定性展开结构——由 Operator 列表构成。需要被后续步骤引用或参与传播的 helper claim，应以显式 `claim` 的形式出现在 `knowledges` 中；仅服务于单个 FormalExpr 的局部结构节点可由 compiler 自动生成。不是独立实体，而是 FormalStrategy 的嵌入字段。9 种命名策略自带 FormalExpr 模板，确定性策略可自动生成，非确定性策略需 reviewer 手动创建。Schema 见 [gaia-ir.md](gaia-ir.md) §4。

### 两层身份与两个全局子图

两个 ID 命名空间，schema 有差异（global claim 不存储 content，global strategy 不存储 steps）：

| 层 | 范围 | ID 前缀 | 内容 |
|----|------|---------|------|
| **LocalCanonicalGraph** | 单个包 | `lcn_`, `lcs_`, `lco_` | 存储完整 content + Strategy steps（内容仓库） |
| **GlobalSemanticGraph** | 跨包语义层 | `gcn_`, `gco_` | canonical claim + accepted global Operator |
| **GlobalContributionGraph** | 跨包来源层 | `gcs_` | promoted Strategy contribution，保留 package/version/source_lcs |

两者合起来构成 `GlobalCanonicalGraph`。规范化与提升流程见 [gaia-ir.md](gaia-ir.md) §5。

### 图哈希

LocalCanonicalGraph 有确定性哈希 `ir_hash = SHA-256(canonical JSON)`，用于编译完整性校验——审查引擎重新编译并验证匹配。GlobalCanonicalGraph 是增量变化的，不使用整体哈希。

## 二、Parameterization — 参数

Parameterization 是 `GlobalSemanticGraph + GlobalContributionGraph` 上的概率参数层。它由**原子记录**构成，不同 review 来源（不同模型、不同策略）产出不同的记录。

### 存储层

```json
// PriorRecord（每条一个 Knowledge）
{"gcn_id": "gcn_8b1c...", "value": 0.7, "source_id": "src_001", "created_at": "..."}
{"gcn_id": "gcn_8b1c...", "value": 0.8, "source_id": "src_002", "created_at": "..."}

// StrategyParamRecord（每条一个 global Strategy contribution）
{"strategy_id": "gcs_d2c8...", "conditional_probabilities": [0.85], "source_id": "src_001", "created_at": "..."}

// ParameterizationSource（记录产出上下文）
{"source_id": "src_001", "model": "gpt-5-mini", "policy": "conservative", "created_at": "..."}
{"source_id": "src_002", "model": "claude-opus", "policy": null, "created_at": "..."}
```

### 运行时组装（当前 BP 管线）

当前 BP 管线在运行前按 resolution policy 从原子记录中选择每个 Knowledge/Strategy contribution 的值，**现算不持久化**：

| policy | 说明 |
|--------|------|
| `latest` | 每个 Knowledge/Strategy 取最新记录 |
| `source:<source_id>` | 指定使用某个 source 的记录 |

关键规则：

- **claim_priors**：只有 `type=claim` 的 Knowledge 有记录。
- **strategy_params**：所有推理类 Strategy contribution 都有 conditional_probabilities（参数数量由 type 决定：`infer`=2^K，`noisy_and`=[p]，其余命名策略按对应模板/子结构解释）。
- **Cromwell's rule**：所有概率钳制到 `[ε, 1-ε]`，ε = 1e-3。
- 组装时使用 `prior_cutoff` 时间戳过滤记录，确保可重现。
- 组装结果必须覆盖所有 claim Knowledge 和所有可运行的 Strategy contribution，否则 BP 拒绝运行。

详细设计见 [parameterization.md](parameterization.md)。

## 三、BeliefState — 信念

BeliefState 是下游推理运行在 `GlobalSemanticGraph + GlobalContributionGraph` 上的纯输出——后验信念值。当前默认实现是 BP，因此这里展示的是 BP 运行结果格式。它记录 resolution policy 使结果可重现。

### 整体结构

```json
{
  "bp_run_id": "uuid-...",
  "created_at": "2026-03-24T12:00:00Z",
  "resolution_policy": "latest",
  "prior_cutoff": "2026-03-24T12:00:00Z",
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

- **beliefs**：只有 `type=claim` 的 Knowledge 有 belief。
- **可重现**：`resolution_policy` + `prior_cutoff` 完整定义参数组装条件，可重跑 BP。
- **可多次运行**：同一 resolution policy 可以有多次 BP 运行。

详细设计见 [belief-state.md](belief-state.md)。

## 完备性

一个完整的 Gaia 知识体系需要以下信息：

| 对象 | 内容 | 变化频率 |
|------|------|---------|
| **LocalCanonicalGraph** | 包内 Knowledge + Strategy（含 steps）+ 完整文本 | 每次 build 更新 |
| **GlobalSemanticGraph** | 跨包 canonical claim + accepted global Operator | 每次 ingest/curation 更新 |
| **GlobalContributionGraph** | 全局 Strategy contribution（无 steps，保留 `source_lcs/package/version`） | 每次 ingest 更新 |
| **CanonicalBinding** | lcn → gcn 映射记录 | 每次 ingest 更新 |
| **PriorRecord** | 全局 claim 的 prior（每条记录携带 source） | 每次 review 追加 |
| **StrategyParamRecord** | 全局 Strategy contribution 的 conditional_probabilities（每条记录携带 source） | 每次 review 追加 |
| **ParameterizationSource** | review 来源信息（模型、策略、配置） | 每次 review 创建 |
| **BeliefState** | 全局 claim 的后验信念 + resolution policy | 每次 global BP 创建 |

## 源代码

- `libs/graph_ir/models.py` -- `LocalCanonicalGraph`, `Knowledge`, `Strategy`
- `libs/storage/models.py` -- global `Knowledge`, `CanonicalBinding`, `BeliefSnapshot`
- `libs/global_graph/canonicalize.py` -- `canonicalize_package()`
- `libs/global_graph/similarity.py` -- `find_best_match()`
- *Future:* `libs/graph_ir/operator.py` -- `Operator`
- *Future:* `libs/graph_ir/strategy.py` -- `CompositeStrategy`, `FormalStrategy`, `FormalExpr`
