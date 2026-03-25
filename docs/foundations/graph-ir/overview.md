# Graph IR 概述

> **Status:** Target design — 基于 [reasoning-hypergraph.md](../theory/reasoning-hypergraph.md) 重新设计

## 目的

Graph IR 是 Gaia 推理超图的完备数据表示。读完本文档，你应当知道一个完整的 Gaia 知识体系由哪几部分信息构成。

Gaia 的数据由三个独立对象组成：

```
Graph IR（结构）    ×    Parameterization（参数）    →    BeliefState（信念）
什么连接什么               每个节点/算子多可信               BP 计算的后验信念
编译时确定                  review 产出                     BP 产出
```

三者严格分离。Graph IR 有 local 和 global 两层。Parameterization 和 BeliefState 只作用在 GlobalCanonicalGraph 上。

## 一、Graph IR — 结构

Graph IR 编码**什么连接什么**——推理超图的拓扑结构。它不包含任何概率值。

### 整体结构

```json
{
  "scope": "local",
  "graph_hash": "sha256:...",
  "knowledge_nodes": [
    {
      "id": "lcn_a3f2e1...",
      "type": "claim",
      "content": "该样本在 90 K 以下表现出超导性",
      "parameters": [],
      "source_refs": [...],
      "metadata": {"schema": "observation", "instrument": "..."}
    },
    {
      "id": "lcn_b7e1d4...",
      "type": "setting",
      "content": "高温超导研究的当前进展",
      "parameters": [],
      "source_refs": [...]
    },
    {
      "id": "lcn_c9a0f3...",
      "type": "template",
      "content": "∀x. superconductor(x) → zero_resistance(x)",
      "parameters": [{"name": "x", "type": "material"}],
      "source_refs": [...]
    }
  ],
  "factor_nodes": [
    {
      "factor_id": "f_d2c8...",
      "category": "infer",
      "stage": "initial",
      "reasoning_type": null,
      "premises": ["lcn_a3f2e1..."],
      "weak_points": ["稀薄气体假设可能不成立"],
      "conclusion": "lcn_e5f1a2...",
      "steps": [{"reasoning": "基于超导样品的电阻率骤降..."}],
      "source_ref": {...},
      "metadata": {"context": ["lcn_b7e1d4..."]}
    },
    {
      "factor_id": "f_f7a1...",
      "category": "toolcall",
      "stage": "initial",
      "reasoning_type": null,
      "premises": ["lcn_a3f2e1..."],
      "weak_points": [],
      "conclusion": "lcn_g8b2c3...",
      "steps": [{"reasoning": "MCMC fitting using emcee..."}],
      "source_ref": {...}
    }
  ]
}
```

### Knowledge 节点（变量节点）

表示命题。四种类型：

| type | 说明 | 参与 BP | 可作为 |
|------|------|---------|--------|
| **claim** | 封闭的科学断言 | 是（唯一 BP 承载者） | premise, context, conclusion |
| **setting** | 背景信息 | 否 | premise, context |
| **question** | 待研究方向 | 否 | premise, context |
| **template** | 含自由变量的命题模式 | 否 | premise（instantiation） |

详细 schema 见 [graph-ir.md](graph-ir.md) §1。

### Factor 节点（因子节点）

表示推理算子，连接 knowledge 节点。三维类型系统：

| 维度 | 值 | 说明 |
|------|-----|------|
| **category** | infer / toolcall / proof | 怎么得到结论的 |
| **stage** | initial / candidate / permanent | 审查到哪了 |
| **reasoning_type** | entailment / induction / abduction / equivalent / contradict / None | 具体逻辑关系 |

详细 schema 见 [graph-ir.md](graph-ir.md) §2。

### 两层身份

两个 ID 命名空间，schema 有差异（global 层不存储 content 和 steps）：

| 层 | 范围 | ID 前缀 | 内容 |
|----|------|---------|------|
| **LocalCanonicalGraph** | 单个包 | `lcn_` | 存储完整 content + factor steps（内容仓库） |
| **GlobalCanonicalGraph** | 跨包 | `gcn_` | 引用 representative lcn 节点，factor 无 steps（结构索引） |

规范化（lcn → gcn 映射）见 [graph-ir.md](graph-ir.md) §3。

### 图哈希

LocalCanonicalGraph 有确定性哈希 `graph_hash = SHA-256(canonical JSON)`，用于编译完整性校验——审查引擎重新编译并验证匹配。GlobalCanonicalGraph 是增量变化的，不使用整体哈希。

## 二、Parameterization — 参数

Parameterization 是 GlobalCanonicalGraph 上的概率参数层。它由**原子记录**构成，不同 review 来源（不同模型、不同策略）产出不同的记录。

### 存储层

```json
// PriorRecord（每条一个节点）
{"gcn_id": "gcn_8b1c...", "value": 0.7, "source_id": "src_001", "created_at": "..."}
{"gcn_id": "gcn_8b1c...", "value": 0.8, "source_id": "src_002", "created_at": "..."}

// FactorParamRecord（每条一个 factor）
{"factor_id": "f_d2c8...", "probability": 0.85, "source_id": "src_001", "created_at": "..."}

// ParameterizationSource（记录产出上下文）
{"source_id": "src_001", "model": "gpt-5-mini", "policy": "conservative", "created_at": "..."}
{"source_id": "src_002", "model": "claude-opus", "policy": null, "created_at": "..."}
```

### BP 运行时组装

BP 运行前按 resolution policy 从原子记录中选择每个节点/factor 的值，**现算不持久化**：

| policy | 说明 |
|--------|------|
| `latest` | 每个节点/factor 取最新记录 |
| `source:<source_id>` | 指定使用某个 source 的记录 |

关键规则：

- **node_priors**：只有 `type=claim` 的节点有记录。
- **factor_params**：所有 category（infer/toolcall/proof）都有 probability。
- **Cromwell's rule**：所有概率钳制到 `[ε, 1-ε]`，ε = 1e-3。
- 组装时使用 `prior_cutoff` 时间戳过滤记录，确保可重现。
- 组装结果必须覆盖所有 claim 节点和所有 factor，否则 BP 拒绝运行。

详细设计见 [parameterization.md](parameterization.md)。

## 三、BeliefState — 信念

BeliefState 是 BP 在 GlobalCanonicalGraph 上的纯输出——后验信念值。它记录 resolution policy 使结果可重现。

### 整体结构

```json
{
  "bp_run_id": "uuid-...",
  "timestamp": "2026-03-24T12:00:00Z",
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

- **beliefs**：只有 `type=claim` 的节点有 belief。
- **可重现**：`resolution_policy` + `prior_cutoff` 完整定义参数组装条件，可重跑 BP。
- **可多次运行**：同一 resolution policy 可以有多次 BP 运行。

详细设计见 [belief-state.md](belief-state.md)。

## 完备性

一个完整的 Gaia 知识体系需要以下信息：

| 对象 | 内容 | 变化频率 |
|------|------|---------|
| **LocalCanonicalGraph** | 包内 knowledge 节点 + factor 节点（含 steps）+ 完整文本 | 每次 build 更新 |
| **GlobalCanonicalGraph** | 跨包 knowledge 节点（引用 lcn）+ 全局 factor 节点（无 steps） | 每次 ingest/curation 更新 |
| **CanonicalBinding** | lcn → gcn 映射记录 | 每次 ingest 更新 |
| **PriorRecord** | 全局 claim 的 prior（每条记录携带 source） | 每次 review 追加 |
| **FactorParamRecord** | 全局 factor 的 probability（每条记录携带 source） | 每次 review 追加 |
| **ParameterizationSource** | review 来源信息（模型、策略、配置） | 每次 review 创建 |
| **BeliefState** | 全局 claim 的后验信念 + resolution policy | 每次 global BP 创建 |

## 源代码

- `libs/graph_ir/models.py` -- `LocalCanonicalGraph`, `FactorNode`, `LocalParameterization`
- `libs/storage/models.py` -- `GlobalCanonicalNode`, `CanonicalBinding`, `BeliefSnapshot`
