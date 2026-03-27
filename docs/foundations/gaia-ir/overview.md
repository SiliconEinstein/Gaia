# Gaia IR 概述

> **Status:** Target design — 基于 [06-factor-graphs.md](../theory/06-factor-graphs.md) 和 [04-reasoning-strategies.md](../theory/04-reasoning-strategies.md) 设计
>
> **⚠️ Protected Contract Layer** — 本目录定义 CLI↔LKM 结构契约。变更需要独立 PR 并经负责人审查批准。详见 [documentation-policy.md](../../documentation-policy.md#12-变更控制)。

## 目的

Gaia IR 是 Gaia 推理超图的完备数据表示。读完本文档，你应当知道一个完整的 Gaia 知识体系由哪几部分信息构成。

Gaia 的数据由三个独立对象组成：

```
Gaia IR（结构）    ×    Parameterization（参数）    →    BeliefState（信念）
什么连接什么               每个 Knowledge/Strategy 多可信     BP 计算的后验信念
编译时确定                  review 产出                     BP 产出
```

三者严格分离。Gaia IR 有 local 和 global 两层。Parameterization 和 BeliefState 只作用在 GlobalCanonicalGraph 上。

## 一、Gaia IR — 结构

Gaia IR 编码**什么连接什么**——推理超图的拓扑结构。它不包含任何概率值。

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
    }
  ],
  "operators": []
}
```

**Global 层示例**（跨包，展示三种 Strategy 形态）：

```json
{
  "scope": "global",
  "knowledges": [
    {"id": "gcn_a1...", "type": "claim"},
    {"id": "gcn_b2...", "type": "claim"},
    {"id": "gcn_d4...", "type": "claim"},
    {"id": "gcn_m1...", "type": "claim", "content": "gcn_a1 ∧ gcn_b2"}
  ],
  "strategies": [
    {
      "_comment": "Strategy（叶子 ↝）",
      "strategy_id": "gcs_s1...",
      "type": "infer",
      "premises": ["gcn_a1..."],
      "conclusion": "gcn_b2..."
    },
    {
      "_comment": "CompositeStrategy（含子策略）",
      "strategy_id": "gcs_s2...",
      "type": "infer",
      "premises": ["gcn_a1...", "gcn_b2..."],
      "conclusion": "gcn_d4...",
      "sub_strategies": ["gcs_s1...", "gcs_s3..."]
    },
    {
      "_comment": "FormalStrategy（确定性展开）",
      "strategy_id": "gcs_s3...",
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
      "conclusion": null
    }
  ]
}
```

Global 层 Knowledge 通常不存储 content（通过 `representative_lcn` 引用 local 层）。LKM 服务器直接创建的 Knowledge（包括 FormalExpr 中间 Knowledge 如 `gcn_m1`）无 local 来源，content 直接存在 global 层。

### Knowledge（命题）

表示命题。四种类型：

| type | 说明 | 参与 BP | 可作为 |
|------|------|---------|--------|
| **claim** | 封闭的科学断言 | 是（唯一 BP 承载者） | premise, background, conclusion, refs |
| **setting** | 背景信息 | 否 | background, refs |
| **question** | 待研究方向 | 否 | background, refs |
| **template** | 含自由变量的命题模式 | 否 | background, refs |

详细 schema 见 [gaia-ir.md](gaia-ir.md) §1。

### Strategy（推理声明）

表示推理算子，连接 Knowledge。Strategy 有三种形态（类层级）：

| 形态 | 说明 | 独有字段 |
|------|------|---------|
| **Strategy**（基类，可实例化） | 叶子推理，编译为 ↝ | — |
| **CompositeStrategy**(Strategy) | 含子策略，可递归嵌套 | `sub_strategies: list[str]` |
| **FormalStrategy**(Strategy) | 含确定性 Operator 展开 | `formal_expr: FormalExpr` |

所有形态折叠时均编译为 ↝（概率参数来自 [parameterization](parameterization.md) 层）。展开时进入内部结构（子策略或确定性 Operator）。这支持**多分辨率 BP**——同一图在不同粒度做推理。

统一 `type` 字段（与形态正交）：

| type | 参数化模型 | 经历 lifecycle | 形态 |
|------|-----------|---------------|------|
| **None** | 通用 CPT: 2^K（默认 MaxEnt 0.5） | 是 | Strategy 或 CompositeStrategy |
| **infer** | noisy-AND: [q]（单参数） | 是 | Strategy 或 CompositeStrategy |
| **soft_implication** | [p₁, p₂] | 是 | Strategy 或 CompositeStrategy |
| **deduction** | — | 是 | FormalStrategy |
| **abduction** | — | 是 | FormalStrategy |
| **induction** | — | 是 | FormalStrategy |
| **analogy** | — | 是 | FormalStrategy |
| **extrapolation** | — | 是 | FormalStrategy |
| **reductio** | — | 是 | FormalStrategy |
| **elimination** | — | 是 | FormalStrategy |
| **mathematical_induction** | — | 是 | FormalStrategy |
| **case_analysis** | — | 是 | FormalStrategy |
| **independent_evidence** | [q] | 是 | Strategy（conclusion=None） |
| **contradiction** | [q] | 是 | Strategy（conclusion=None） |
| **toolcall** | 另行定义 | 否 | Strategy |
| **proof** | 另行定义 | 否 | Strategy |

详细 schema 见 [gaia-ir.md](gaia-ir.md) §2。

### Operator（结构约束）

确定性逻辑关系（equivalence, contradiction, complement, implication, disjunction, conjunction）。对应 theory Layer 3 的势函数，所有算子均确定性（ψ ∈ {0, 1}，无自由参数）。Schema 见 [gaia-ir.md](gaia-ir.md) §3。

### FormalExpr（data class，非顶层实体）

FormalStrategy 的确定性展开结构——由 Operator 列表构成。中间 Knowledge 从 operators 推导（不显式列出）。不是独立实体，而是 FormalStrategy 的嵌入字段。9 种命名策略自带 FormalExpr 模板，确定性策略可自动生成，非确定性策略需 reviewer 手动创建。Schema 见 [gaia-ir.md](gaia-ir.md) §4。

### 两层身份

两个 ID 命名空间，schema 有差异（global 层不存储 content 和 steps）：

| 层 | 范围 | ID 前缀 | 内容 |
|----|------|---------|------|
| **LocalCanonicalGraph** | 单个包 | `lcn_`, `lcs_`, `lco_` | 存储完整 content + Strategy steps（内容仓库） |
| **GlobalCanonicalGraph** | 跨包 | `gcn_`, `gcs_`, `gco_` | 引用 representative lcn，Strategy 无 steps（结构索引）+ Operator |

规范化（lcn → gcn 映射）见 [gaia-ir.md](gaia-ir.md) §5。

### 图哈希

LocalCanonicalGraph 有确定性哈希 `ir_hash = SHA-256(canonical JSON)`，用于编译完整性校验——审查引擎重新编译并验证匹配。GlobalCanonicalGraph 是增量变化的，不使用整体哈希。

## 二、Parameterization — 参数

Parameterization 是 GlobalCanonicalGraph 上的概率参数层。它由**原子记录**构成，不同 review 来源（不同模型、不同策略）产出不同的记录。

### 存储层

```json
// PriorRecord（每条一个 Knowledge）
{"gcn_id": "gcn_8b1c...", "value": 0.7, "source_id": "src_001", "created_at": "..."}
{"gcn_id": "gcn_8b1c...", "value": 0.8, "source_id": "src_002", "created_at": "..."}

// StrategyParamRecord（每条一个 Strategy）
{"strategy_id": "gcs_d2c8...", "conditional_probabilities": [0.85], "source_id": "src_001", "created_at": "..."}

// ParameterizationSource（记录产出上下文）
{"source_id": "src_001", "model": "gpt-5-mini", "policy": "conservative", "created_at": "..."}
{"source_id": "src_002", "model": "claude-opus", "policy": null, "created_at": "..."}
```

### BP 运行时组装

BP 运行前按 resolution policy 从原子记录中选择每个 Knowledge/Strategy 的值，**现算不持久化**：

| policy | 说明 |
|--------|------|
| `latest` | 每个 Knowledge/Strategy 取最新记录 |
| `source:<source_id>` | 指定使用某个 source 的记录 |

关键规则：

- **claim_priors**：只有 `type=claim` 的 Knowledge 有记录。
- **strategy_params**：所有推理类 Strategy 都有 conditional_probabilities（参数数量由 type 决定：None=2^K, infer=[q], soft_implication=[p₁,p₂]）。
- **Cromwell's rule**：所有概率钳制到 `[ε, 1-ε]`，ε = 1e-3。
- 组装时使用 `prior_cutoff` 时间戳过滤记录，确保可重现。
- 组装结果必须覆盖所有 claim Knowledge 和所有 Strategy，否则 BP 拒绝运行。

详细设计见 [parameterization.md](parameterization.md)。

## 三、BeliefState — 信念

BeliefState 是 BP 在 GlobalCanonicalGraph 上的纯输出——后验信念值。它记录 resolution policy 使结果可重现。

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
| **GlobalCanonicalGraph** | 跨包 Knowledge（引用 lcn）+ 全局 Strategy（无 steps，FormalStrategy 含 FormalExpr）+ Operator | 每次 ingest/curation 更新 |
| **CanonicalBinding** | lcn → gcn 映射记录 | 每次 ingest 更新 |
| **PriorRecord** | 全局 claim 的 prior（每条记录携带 source） | 每次 review 追加 |
| **StrategyParamRecord** | 全局 Strategy 的 conditional_probabilities（每条记录携带 source） | 每次 review 追加 |
| **ParameterizationSource** | review 来源信息（模型、策略、配置） | 每次 review 创建 |
| **BeliefState** | 全局 claim 的后验信念 + resolution policy | 每次 global BP 创建 |

## 源代码

- `libs/graph_ir/models.py` -- `LocalCanonicalGraph`, `Knowledge`, `Strategy`
- `libs/storage/models.py` -- global `Knowledge`, `CanonicalBinding`, `BeliefSnapshot`
- `libs/global_graph/canonicalize.py` -- `canonicalize_package()`
- `libs/global_graph/similarity.py` -- `find_best_match()`
- *Future:* `libs/graph_ir/operator.py` -- `Operator`
- *Future:* `libs/graph_ir/strategy.py` -- `CompositeStrategy`, `FormalStrategy`, `FormalExpr`
