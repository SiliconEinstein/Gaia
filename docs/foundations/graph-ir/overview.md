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

三者严格分离。Graph IR 有 local 和 global 两层。Parameterization 和 BeliefState 只作用在 GlobalCanonicalGraph 上，通过 `graph_hash` 绑定到特定版本的全局图。

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
      "contexts": ["lcn_b7e1d4..."],
      "conclusion": "lcn_e5f1a2...",
      "steps": [{"reasoning": "基于超导样品的电阻率骤降..."}],
      "source_ref": {...}
    },
    {
      "factor_id": "f_f7a1...",
      "category": "toolcall",
      "stage": "initial",
      "reasoning_type": null,
      "premises": ["lcn_a3f2e1..."],
      "contexts": [],
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

同一套 schema，两个 ID 命名空间：

| 层 | 范围 | ID 前缀 | 内容存储 |
|----|------|---------|---------|
| **LocalCanonicalGraph** | 单个包 | `lcn_` | 存储完整 content |
| **GlobalCanonicalGraph** | 跨包 | `gcn_` | 引用 representative lcn 节点，不重复存储 |

规范化（lcn → gcn 映射）见 [graph-ir.md](graph-ir.md) §3。

### 图哈希

`graph_hash = SHA-256(canonical JSON)`。用途：

1. 完整性校验——审查引擎重新编译并验证匹配
2. 版本绑定——Parameterization 和 BeliefState 通过哈希绑定到特定图版本

## 二、Parameterization — 参数

Parameterization 作用在 **GlobalCanonicalGraph** 上，编码每个全局节点和算子的概率值。

### 整体结构

```json
{
  "graph_hash": "sha256:...",
  "node_priors": {
    "gcn_8b1c...": {"value": 0.7, "source": "review"},
    "gcn_9d2a...": {"value": 0.5, "source": "aggregated"}
  },
  "factor_params": {
    "f_d2c8...": {"probability": 0.85, "source": "review"},
    "f_f7a1...": {"probability": 0.95, "source": "toolcall_reproducibility"}
  }
}
```

关键规则：

- **作用于 GlobalCanonicalGraph**：`graph_hash` 绑定到全局图的哈希。所有 ID 使用 `gcn_` 命名空间。
- **node_priors**：只有 `type=claim` 的节点有 prior。Setting/Question/Template 不出现。
- **factor_params**：**所有 category**（infer/toolcall/proof）都有 probability。
- **Cromwell's rule**：所有概率钳制到 `[ε, 1-ε]`，ε = 1e-3。
- **聚合模型**：一个 global 节点可能由多个包贡献，prior 需聚合多个来源。

详细设计见 [parameterization.md](parameterization.md)。

## 三、BeliefState — 信念

BeliefState 作用在 **GlobalCanonicalGraph** 上，是 BP 的纯输出——后验信念值。

### 整体结构

```json
{
  "graph_hash": "sha256:...",
  "parameterization_hash": "sha256:...",
  "bp_run_id": "uuid-...",
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

- **作用于 GlobalCanonicalGraph**：`graph_hash` 与 Parameterization 中的相同，都绑定到同一个全局图。
- **beliefs**：只有 `type=claim` 的节点有 belief（与 node_priors 对应）。
- **双重绑定**：通过 `graph_hash + parameterization_hash` 绑定到产生它的结构和参数。
- **可多次运行**：同一参数化可以有多次 BP 运行（不同调度策略、阻尼系数等）。

详细设计见 [belief-state.md](belief-state.md)。

## 完备性

一个完整的 Gaia 知识体系需要以下信息：

| 对象 | 内容 | 变化频率 |
|------|------|---------|
| **LocalCanonicalGraph** | 包内的 knowledge 节点 + factor 节点 + 完整文本 | 每次 build 更新 |
| **GlobalCanonicalGraph** | 跨包 knowledge 节点（引用 lcn）+ 全局 factor 节点 | 每次 ingest/curation 更新 |
| **CanonicalBinding** | lcn → gcn 映射记录 | 每次 ingest 更新 |
| **Parameterization** | 全局 claim 的 prior + 全局 factor 的 probability | 每次 review/curation 更新 |
| **BeliefState** | 全局 claim 的后验信念 | 每次 global BP 更新 |

## 源代码

- `libs/graph_ir/models.py` -- `LocalCanonicalGraph`, `FactorNode`, `LocalParameterization`
- `libs/storage/models.py` -- `GlobalCanonicalNode`, `CanonicalBinding`, `BeliefSnapshot`
