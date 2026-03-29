# 去中心化架构

> **Status:** Current canonical

本文档记录 Gaia 的去中心化包管理和推理架构的设计决策。

## GitHub 作为通用交互面

Gaia 的所有角色通过 GitHub 交互：

| 角色 | 交互方式 |
|------|---------|
| **Gaia Lang 作者** | git push 到包仓库 |
| **Registry** | GitHub 仓库（Julia General 模型），注册/去重/推理 通过 CI workflow |
| **Reviewer** | 向 registry 仓库提交 PR |

一切都是 git commit，一切通过 PR，一切可审计。

## 三层分离

```
Layer 0: Package = git 仓库（完全自治，不依赖任何服务）
Layer 1: Registry = GitHub 仓库（可选的聚合层，可有多个）
Layer 2: Belief = 多级 BP（包级 local BP + Registry 增量 BP + LKM 全局 BP）
```

- **Layer 0** 是基础——两个人在 GitHub 上各建一个包，互相引用，`gaia build && gaia infer` 就能让 belief 流动。
- **Layer 1 和 Layer 2** 是可选增强。

## Registry = 可选的 GitHub 仓库

Registry 采用 Julia General registry 模型——一个 GitHub 仓库，通过 PR 注册包、提交 review、触发 CI。

**关键性质：**

- Registry 是增值服务，不是基础设施。用户可以完全不用 Registry。
- Registry 就是 git 仓库，任何人可以 fork 出自己的 registry，有自己的 review 标准和 belief。不同学科、不同机构可以运营不同的 registry。

## 多级 BP

Beliefs 在三个层级流动，各层各司其职：

| 层级 | 触发方式 | 范围 | 目的 |
|------|---------|------|------|
| **包级 local BP** | `gaia infer` | 单个包 + 拉取的依赖 beliefs | 作者本地预览 |
| **Registry 增量 BP** | CI workflow（注册/review 后自动触发） | 受影响的局部子图 | 快速反馈，无需等全局 BP |
| **LKM 全局 BP** | 服务端推理服务 | 所有已注册的包 | 十亿节点规模的完整证据汇聚 |

纯去中心化的局限：每个包只看到直接依赖图。如果两条独立推理链指向同一个 claim 但彼此不知道，belief 不能汇聚。Registry 和 LKM 的全局视野解决这个问题。

## 质量 = 涌现而非门槛

| 层 | 机制 |
|----|------|
| 编译门槛 | 包必须通过结构验证（自动） |
| 参数门控 | 未经审核的新推理不影响推理结果（新证据默认待审） |
| Review | 独立性判断 + 参数赋值（人工/agent） |
| BP 自筛 | 弱推理 → 低可信度；独立证据汇聚 → 高可信度 |
| 矛盾检测 | 互相矛盾的命题被自动压低可信度 |

任何人可以发布包（低门槛），但新证据默认不影响推理结果，直到 reviewer 确认。

## 设计原则

| 原则 | 体现 |
|------|------|
| 包即 git 仓库 | 不依赖任何中心服务 |
| GitHub 是通用协议 | 作者 git push、registry CI、reviewer PR |
| Registry 可选 | 增值服务，不是基础设施；可 fork 可联邦 |
| 模糊判断归 review | 独立性、重复性、细化关系等需要语义理解的判断由 reviewer 决定 |
| 新证据默认静默 | 未经审核的推理不影响结果，reviewer 确认后激活 |
| 多级 BP | 包级 + Registry 增量 + LKM 全局，各层各司其职 |
| 错误可修正 | 合并重复命题 + 暂停受影响的推理 + re-review |

## 参考文献

- [architecture-overview.md](architecture-overview.md) — 三层编译管线和两个产品表面
- [product-scope.md](product-scope.md) — 产品定位（CLI 优先，服务器增强）
- `docs/specs/2026-03-28-package-management-design.md` — 具体实现方案
