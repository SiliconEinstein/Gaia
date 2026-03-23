# Gaia 系统概览

| Field | Value |
|---|---|
| Status | Current canonical |
| Level | Overview |
| Scope | Repo-wide |
| Related | [semantics/terminology.md](semantics/terminology.md), [product-scope.md](product-scope.md), [contracts/authoring/graph-ir.md](contracts/authoring/graph-ir.md), [contracts/lifecycles/cli-lifecycle.md](contracts/lifecycles/cli-lifecycle.md), [contracts/lifecycles/lkm-package-lifecycle.md](contracts/lifecycles/lkm-package-lifecycle.md), [server/architecture.md](server/architecture.md) |

## Purpose

本文档描述 Gaia 的顶层结构。

它是“Gaia 的主要部分如何组合在一起”的规范入口文档，不试图穷尽所有工作流或运行时细节。

术语规范请参阅 [semantics/terminology.md](semantics/terminology.md)。

## 主要分界：Gaia CLI 与 Gaia LKM

Gaia 当前有两个主要活跃侧：

- **Gaia CLI** —— 本地作者侧工具链
- **Gaia LKM** —— 共享侧知识核心与 system of record

这应当是激活基础文档中的主要概念分界。

```
┌─────────────────────────────────────────────────────────────┐
│ 研究者 / 代理                                               │
│ 编写 Typst package source，并运行本地命令                   │
└─────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│ Gaia CLI                                                    │
│ 本地 authoring、build、infer、publish                      │
│ 本地 Typst package source + 本地 .gaia/ artifacts          │
└─────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│ Gaia LKM                                                    │
│ 共享知识状态、review、rebuttal、integration、               │
│ curation、search，以及共享推理相关能力                     │
└─────────────────────────────────────────────────────────────┘
```

## Gaia CLI

Gaia CLI 是面向作者、研究者和代理的本地工具链。

它的规范本地生命周期是：

- `build`
- `infer`
- `publish`

CLI 负责：

- 处理本地 Typst package source
- 产出 `.gaia/` 下的本地构建和推理 artifacts
- 在进入共享侧之前提供本地预览
- 向外发布 package artifact

重要边界：

- `review` 不属于规范的 CLI 生命周期
- `main` 上当前存在的 `gaia review` 命令应被视为本地兼容辅助路径，而不是主要生命周期边界

CLI 细节见 [contracts/lifecycles/cli-lifecycle.md](contracts/lifecycles/cli-lifecycle.md)。

## Gaia LKM

Gaia LKM 是共享侧知识核心与 system of record。

它负责本地发布进入共享侧之后发生的工作流，包括：

- review
- rebuttal 处理
- 集成进共享知识状态
- curation 与维护
- 共享搜索与发现
- 更大规模的推理与图维护

重要边界：

- Gaia LKM 是共享侧的主要 foundation 级术语
- `Gaia Cloud` 仍可作为产品或部署别名
- `cloud` 不意味着必须远程部署；本地或自托管的 LKM 仍然成立

当前更细的共享侧流程文档仍然暂时保留在 [review/publish-pipeline.md](review/publish-pipeline.md) 这类旧位置中，直到 foundations reset 继续推进。

## Service、Engine 与 Server

在 Gaia LKM 内部，激活文档应当区分三种不同概念：

- **Service** —— 职责边界，例如 `ReviewService`、`CurationService`
- **Engine** —— 内部算法组件，例如 BP engine
- **Server** —— 当前运行中的后端实现

这一区分之所以重要，是因为：

- `service` 是概念架构上的职责边界
- `engine` 是内部执行组件
- `server` 是运行时/部署术语，不是共享侧整体最好的名字

当前后端运行时细节见 [server/architecture.md](server/architecture.md)。

## Artifact Flow

从顶层看，Gaia 的 artifact 流程是：

1. 用户或代理在本地编写 Typst package。
2. Gaia CLI 将其 build 为确定性的本地 artifacts。
3. Gaia CLI 可选地运行本地 infer 以获得预览。
4. Gaia CLI 向外 publish 一个 package artifact。
5. Gaia LKM 在共享侧处理该 package 的后续 lifecycle：review、rebuttal、integration、curation。

这也是为什么即使 CLI 和共享侧共用代码，它们仍然应当被分别文档化。

## `main` 上的当前运行时

当前 `main` 分支已经包含多个已发布的运行时表面：

- Gaia CLI
- 一个后端 server 实现
- 一个 dashboard frontend

激活基础文档应使用 `Gaia CLI / Gaia LKM` 这一概念分界来描述这些表面，而把更具体的实现细节放在 runtime 导向的文档里。

## 相关文档

- [semantics/terminology.md](semantics/terminology.md) — 规范术语
- [product-scope.md](product-scope.md) — 产品定位与当前 baseline
- [language/gaia-language-spec.md](language/gaia-language-spec.md) — 作者侧 package surface
- [contracts/authoring/graph-ir.md](contracts/authoring/graph-ir.md) — 结构化 IR 契约
- [contracts/lifecycles/cli-lifecycle.md](contracts/lifecycles/cli-lifecycle.md) — 本地 CLI 生命周期
- [review/publish-pipeline.md](review/publish-pipeline.md) — 迁移期间的共享侧工作流文档
- [server/architecture.md](server/architecture.md) — 当前后端运行时
