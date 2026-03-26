# 基础文档

Gaia 的规范参考文档，按架构层级组织。

## theory/ — 理论基础

推导链：plausible-reasoning → maxent-grounding → propositional-operators → reasoning-strategies → formalization-methodology → factor-graphs → belief-propagation

**三层结构：**

**Layer 1 — Jaynes 理论（纯理论，不涉及因子图/BP）：**
- [`01-plausible-reasoning.md`](theory/01-plausible-reasoning.md) — Cox 定理、概率唯一性、弱三段论
- [`02-maxent-grounding.md`](theory/02-maxent-grounding.md) — MaxEnt/Min-KL、从约束到后验

**Layer 2 — 科学本体论（命题与算子，不涉及因子图/BP）：**
- [`03-propositional-operators.md`](theory/03-propositional-operators.md) — 最小原料 {¬, ∧, π}、派生算子、↝ 软蕴含、完备性
- [`04-reasoning-strategies.md`](theory/04-reasoning-strategies.md) — 知识类型、九种推理策略作为 ↝ 微观结构
- [`05-formalization-methodology.md`](theory/05-formalization-methodology.md) — 从科学文本到命题网络的方法论

**Layer 3 — 计算方法（因子图 + BP 作为大规模近似）：**
- [`06-factor-graphs.md`](theory/06-factor-graphs.md) — 命题网络到因子图的映射、势函数
- [`07-belief-propagation.md`](theory/07-belief-propagation.md) — BP 近似推理算法

## 设计理念 — 设计哲学（极少变更）

- [产品范围](rationale/product-scope.md) — Gaia 是什么、为何存在
- [架构概览](rationale/architecture-overview.md) — 三层管线、CLI↔LKM 契约
- [领域词汇表](rationale/domain-vocabulary.md) — Knowledge、Chain、Module、Package
- [文档维护策略](../documentation-policy.md) — 文档维护规则

## Gaia IR — CLI 与 LKM 之间的共享契约

- [概述](gaia-ir/overview.md) — 三部分总览（Gaia IR + Parameterization + BeliefState）
- [结构定义](gaia-ir/gaia-ir.md) — KnowledgeNode、FactorNode、规范化
- [参数定义](gaia-ir/parameterization.md) — 原子记录、resolution policy
- [信念定义](gaia-ir/belief-state.md) — BP 输出、可重现性

## Gaia Lang — 编著语言

- [语言规范](gaia-lang/spec.md) — Typst DSL 语法
- [知识类型](gaia-lang/knowledge-types.md) — 声明类型、证明状态
- [包模型](gaia-lang/package-model.md) — package/module/chain

## BP — 基于 Gaia IR 的计算

- [因子势函数](bp/potentials.md) — 各因子类型的势函数
- [推理](bp/inference.md) — BP 算法应用于 Gaia IR
- [局部与全局](bp/local-vs-global.md) — CLI 局部推理 vs LKM 全局推理

## Review — 审查管线

- [审阅管线](review/review-pipeline.md) — 验证 → 审阅 → 门控

## CLI — 本地编著与推理

- [生命周期](cli/lifecycle.md) — build → infer → publish
- [编译器](cli/compiler.md) — Typst → Gaia IR 编译
- [局部推理](cli/local-inference.md) — `gaia infer` 内部机制
- [本地存储](cli/local-storage.md) — LanceDB + Kuzu 嵌入式存储

## LKM — 计算注册中心（服务端）

- [概述](lkm/overview.md) — 写入/读取侧架构
- [全局规范化](lkm/global-canonicalization.md) — 跨包节点映射
- [整理](lkm/curation.md) — 聚类、去重、冲突检测
- [全局推理](lkm/global-inference.md) — 服务端 BP
- [管线](lkm/pipeline.md) — 7 阶段批处理编排
- [存储](lkm/storage.md) — 三后端架构
- [API](lkm/api.md) — HTTP API 契约
- [Agent 信用](lkm/agent-credit.md) — Agent 可靠性追踪
- [生命周期](lkm/lifecycle.md) — review → curate → integrate
