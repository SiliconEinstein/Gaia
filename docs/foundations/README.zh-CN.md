# 基础文档

本目录包含 Gaia 当前激活的基础文档。

当任务影响以下任何内容时，请使用此目录：

- 整体系统语义或术语
- 包、图、存储等契约
- CLI 与共享侧生命周期边界
- 当前运行时实现

## 从这里开始

- [基础文档治理策略](documentation-policy.md)
- [Gaia 概览](foundation/gaia-overview.md)
- [科学推理基础](foundation/scientific-reasoning-foundation.md)
- [Terminology](semantics/terminology.md)
- [系统概览](system-overview.md)

## 当前结构

基础文档当前按四类组织：

- **Foundation**：Gaia 的总体定位与科学推理基础
- **Semantics**：Gaia 自己定义的术语、知识类型、关系和推理模型
- **Contracts**：作者侧与系统侧稳定契约
- **Runtime**：当前实现实际上怎么运行

旧的 `theory/`、`review/`、`server/`、`cli/` 子目录和若干顶层文件仍保留为桥接页或迁移期详细参考，但除非本 README 明确推荐，否则不应被视为第一层 canonical 入口。

## 当前活跃树

```text
docs/foundations/
  foundation/
    gaia-overview.md
    scientific-reasoning-foundation.md

  semantics/
    terminology.md
    scientific-knowledge.md
    knowledge-relations.md
    gaia-reasoning-model.md

  contracts/
    authoring/
      gaia-language-spec.md
      graph-ir.md
      package-linking.md
    artifacts/
      package-profiles.md
      review-artifacts.md
      investigation-artifacts.md
    lifecycles/
      cli-lifecycle.md
      lkm-package-lifecycle.md
    services/
      service-boundaries.md
      review-service.md
      curation-service.md
      api-contract.md

  runtime/
    server-architecture.md
    storage-schema.md
    inference-runtime.md
    loop-analysis.md
    review-runtime.md
    curation-runtime.md
```

## 当前推荐阅读顺序

### Foundation 与 Semantics

- [Gaia 概览](foundation/gaia-overview.md) — Gaia 是什么、为什么分成 CLI 与 LKM
- [科学推理基础](foundation/scientific-reasoning-foundation.md) — 为什么科学推理不只是纯数学逻辑
- [Terminology](semantics/terminology.md) — 基础术语的规范出处
- [Scientific Knowledge](semantics/scientific-knowledge.md) — Gaia 中主要的知识类型
- [Knowledge Relations](semantics/knowledge-relations.md) — Gaia 知识项之间的核心关系
- [Gaia Reasoning Model](semantics/gaia-reasoning-model.md) — Gaia 如何落 deduction / induction / abduction / abstraction / instantiation
- [产品范围](product-scope.md) — 迁移期产品定位文档

### Contracts

- [Gaia Language 规范](contracts/authoring/gaia-language-spec.md)
- [Graph IR 契约](contracts/authoring/graph-ir.md)
- [Package Linking](contracts/authoring/package-linking.md)
- [Package Profiles](contracts/artifacts/package-profiles.md) — `knowledge / review / rebuttal / investigation` 等 package 形态
- [Review Artifacts](contracts/artifacts/review-artifacts.md) — submission review 产物
- [Investigation Artifacts](contracts/artifacts/investigation-artifacts.md) — investigation queue / open question 风格产物
- [CLI Lifecycle](contracts/lifecycles/cli-lifecycle.md) — 规范的本地 `build -> infer -> publish`
- [LKM Package Lifecycle](contracts/lifecycles/lkm-package-lifecycle.md) — package 进入 Gaia LKM 后的共享侧生命周期
- [Service Boundaries](contracts/services/service-boundaries.md) — ReviewService 与 CurationService 的边界
- [Review Service](contracts/services/review-service.md)
- [Curation Service](contracts/services/curation-service.md)
- [API Contract](contracts/services/api-contract.md)

### Runtime

- [Server Architecture](runtime/server-architecture.md) — 当前 backend/runtime 组合方式
- [Storage Schema](runtime/storage-schema.md) — 当前 persistence/runtime data model
- [Inference Runtime](runtime/inference-runtime.md) — 当前 inference 执行路径与 current-vs-target 差异
- [Loop Analysis](runtime/loop-analysis.md) — loops、diagnostics 与 basis-style view 的运行时定位
- [Review Runtime](runtime/review-runtime.md)
- [Curation Runtime](runtime/curation-runtime.md)

## 旧桥接页与详细迁移参考

这些文档在迁移期仍然有参考价值，但不应作为第一层 canonical 入口：

- [Gaia Vocabulary](meaning/vocabulary.md)
- [领域模型](domain-model.md)
- [理论基础](theory/theoretical-foundation.md)
- [推理理论](theory/inference-theory.md)
- [Independent Evidence & Conditional Independence](theory/corroboration-and-conditional-independence.md)
- [Gaia Language Design](language/gaia-language-design.md)
- [Language Design Rationale](language/design-rationale.md)
- [Type System Direction](language/type-system-direction.md)
- [旧 Gaia Language 详细规范](language/gaia-language-spec.md)
- [旧 Graph IR 草稿](graph-ir.md)
- [旧 CLI 生命周期](cli/command-lifecycle.md)
- [Gaia CLI 运行时边界](cli/boundaries.md)
- [Review Architecture](review/architecture.md)
- [审查流水线与发布工作流](review/publish-pipeline.md)
- [图 IR 上的 BP](bp-on-graph-ir.md)
- [旧服务器架构](server/architecture.md)
- [旧服务器存储模式](server/storage-schema.md)
- [基础重置计划](foundation-reset-plan.md)

## 迁移说明

- 激活文档应优先使用 `Gaia CLI` 与 `Gaia LKM` 作为主要概念分界。
- 激活文档应把作者侧描述为 Typst package / Gaia package，而不是 YAML package。
- 规范的本地 CLI 生命周期是 `build -> infer -> publish`；`review` 属于共享侧生命周期。

## 历史文档

初始构建过程中的历史设计文档和实现计划保存在 [`../archive/`](../archive/) 中。

## 工作规则

当变更影响架构或跨模块行为时，应在同一分支中更新相关基础文档，或者在 PR 中明确说明为何推迟更新。
