# 基础文档

Gaia 的规范参考文档，按架构层级组织。

## 理论 — 纯数学，与 Gaia 无关（不会变更）

- [合情推理](theory/plausible-reasoning.md) — Jaynes、Cox 定理、概率即逻辑
- [Belief Propagation](theory/belief-propagation.md) — 和积算法、收敛性、阻尼
- [科学本体论](theory/reasoning-hypergraph.md) — 科学知识分类

## 设计理念 — 设计哲学（极少变更）

- [产品范围](rationale/product-scope.md) — Gaia 是什么、为何存在
- [架构概览](rationale/architecture-overview.md) — 三层管线、CLI↔LKM 契约
- [领域词汇表](rationale/domain-vocabulary.md) — Knowledge、Chain、Module、Package
- [类型系统方向](rationale/type-system-direction.md) — Jaynes + Lean 混合方案
- [文档维护策略](rationale/documentation-policy.md) — 文档维护规则

## Graph IR — CLI 与 LKM 之间的共享契约

- [概述](graph-ir/overview.md) — 用途、三层身份体系
- [知识节点](graph-ir/knowledge-nodes.md) — Raw、LocalCanonical、GlobalCanonical 模式
- [因子节点](graph-ir/factor-nodes.md) — FactorNode 模式（单一定义）、类型、编译规则
- [规范化](graph-ir/canonicalization.md) — 局部规范化与全局规范化
- [参数化](graph-ir/parameterization.md) — 叠加模式、图哈希

## BP — 基于 Graph IR 的计算

- [因子势函数](bp/potentials.md) — 各因子类型的势函数
- [推理](bp/inference.md) — BP 算法应用于 Graph IR
- [局部与全局](bp/local-vs-global.md) — CLI 局部推理 vs LKM 全局推理

## CLI — 本地编著与推理

- **Gaia Lang**（CLI 面向 Graph IR 的前端）：
  - [语言规范](cli/gaia-lang/spec.md) — Typst DSL 语法
  - [知识类型](cli/gaia-lang/knowledge-types.md) — 声明类型、证明状态
  - [包模型](cli/gaia-lang/package-model.md) — package/module/chain
- [生命周期](cli/lifecycle.md) — build → infer → publish
- [编译器](cli/compiler.md) — Typst → Graph IR 编译
- [局部推理](cli/local-inference.md) — `gaia infer` 内部机制
- [本地存储](cli/local-storage.md) — LanceDB + Kuzu 嵌入式存储

## LKM — 计算注册中心（服务端）

- [概述](lkm/overview.md) — 写入/读取侧架构
- [审阅管线](lkm/review-pipeline.md) — 验证 → 审阅 → 门控
- [全局规范化](lkm/global-canonicalization.md) — 跨包节点映射
- [整理](lkm/curation.md) — 聚类、去重、冲突检测
- [全局推理](lkm/global-inference.md) — 服务端 BP
- [管线](lkm/pipeline.md) — 7 阶段批处理编排
- [存储](lkm/storage.md) — 三后端架构
- [API](lkm/api.md) — HTTP API 契约
- [Agent 信用](lkm/agent-credit.md) — Agent 可靠性追踪
- [生命周期](lkm/lifecycle.md) — review → curate → integrate
