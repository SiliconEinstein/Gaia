# Curation

> **Status:** Target design

## 概述

Curation 是对 global FactorGraph 的异步维护流程。它在 integrate 之后运行，处理 integrate 阶段无法通过确定性匹配发现的语义级冗余和冲突。

Integrate 已处理：content_hash 完全相同的 variable 去重、premises+conclusion+type 完全相同的 factor 去重。Curation 处理剩余的模糊匹配。

### Discovery vs Resolution

Curation 分为两个阶段，对齐 [上游 ecosystem 治理模型](https://github.com/SiliconEinstein/Gaia/blob/main/docs/foundations/ecosystem/05-review-and-curation.md)：

1. **Discovery（LKM 内部）**：发现语义重复、冲突、结构问题 → 产出结构化的发现报告和提案
2. **Resolution（通过 registry）**：将提案打包为 curation package → 走正常 registry 流程（assignment → review → registration）→ 注册通过后 integrate 到 global FactorGraph

LKM **不直接修改全局图结构**（合并 variable、创建 equivalence/contradiction factor 等）。所有结构变更通过 curation package 走 registry 审查后才生效。这保证了：
- 所有结构变更可审计、可追溯
- 语义判断可被 review 和 rebuttal
- 没有 single point of authority

**例外**：integrate 阶段的 content_hash 精确去重是确定性操作，不需要走 curation package。

## Discovery 阶段

LKM 执行以下发现任务，产出提案报告：

### Canonicalization（语义规范化）

发现 global FactorGraph 中**文本不同但语义等价**的 `visibility: "public"` variable nodes。

匹配策略（content_hash 已在 integrate 阶段处理）：

1. **Embedding 相似度**：余弦相似度超过阈值（默认 0.90）→ 判定为语义等价候选
2. **TF-IDF 回退**：无 embedding 模型时使用 scikit-learn TF-IDF

匹配前置过滤：
- 仅 `visibility: "public"` 的 variable 参与
- 仅相同 `type` 的 variable 才有资格匹配
- 含 `parameters` 的全称 claim 额外比较参数结构（count + types，忽略 name）

发现语义等价后，需要判断背后的 factor nodes 是否提供了独立证据：

- **共享 premises → Binding 提案**：建议合并为一个 variable，合并关联的 factor
- **不同 premises → Equivalence 提案**：建议创建 equivalence factor 连接两者（独立验证增强可信度）

### Conflict Detection（冲突检测）

发现 global FactorGraph 中的矛盾：

- **直接矛盾**：两个 variable 被不同来源分别支持和反对（BP 诊断中表现为振荡或高残差）
- **结构矛盾**：图拓扑异常（不一致的 instantiation 关系等）

产出 **Contradiction 提案**：建议创建 contradiction factor 连接相关 variables。

### Structural Audit（结构审计）

检查 global FactorGraph 的健康状况：

- 孤立 variable nodes（无任何 factor 连接）
- 悬空 factor 引用（premise/conclusion 指向不存在的 variable）
- 未解析的跨包引用（integrate 时 pending 的 `unresolved_cross_refs`）

产出审计报告：errors、warnings、info。

### Discovery 产出

所有发现汇总为结构化报告：

- Binding 提案列表（含匹配证据：相似度分数、premise 重叠分析）
- Equivalence 提案列表
- Contradiction 提案列表
- 审计报告

报告发布到 LKM repo 的 Issues（对齐 [上游 ecosystem 的 relation reports 机制](https://github.com/SiliconEinstein/Gaia/blob/main/docs/foundations/ecosystem/04-registry-operations.md)）。

## Resolution 阶段

基于 discovery 产出，创建 curation package：

1. 将已确认的提案（binding、equivalence、contradiction）编码为 curation package
2. Curation package 提交到 registry，走正常的 assignment → review → registration 流程
3. 注册通过后，LKM 通过正常的 ingest → integrate 路径消费 curation package
4. Curation package 中的结构变更（merge、创建 factor 等）在 integrate 时生效

Curation package 的具体格式待定义（需和上游 ecosystem 对齐）。

## 触发策略

Discovery 阶段可按以下方式触发：
- **批量**：累积 N 个包后或间隔 T 时间后批量运行
- **手动**：通过 API 或 CLI 触发
- **增量**（目标状态）：只处理自上次 discovery 以来新增的 variable/factor nodes

当前实现为全量批处理。增量 discovery 是未来优化方向。
