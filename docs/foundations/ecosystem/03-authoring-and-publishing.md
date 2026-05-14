# 包的创建与发布

> **Status:** Ecosystem architecture with v0.5 implementation notes

本文档描述作者从创建知识包到发布的完整旅程。当前 v0.5 CLI 已实现的是
Python/`pyproject.toml` 包、`gaia compile`、`gaia add`、`gaia infer` 和
`gaia register` 的 source-registry 流程。本文中关于 Review Server 指派、
`.gaia/reviews/` 入库 gate、LKM 官方 belief snapshot 的段落属于生态层设
计目标；它们不是当前 Gaia CLI 的注册前置条件。

## 为什么需要包

科学知识不是孤立的命题，而是有结构的论证——前提支持结论，多条推理链汇聚成证据网络。包是这种结构化知识的最小发布单元，类似于一篇论文或一个实验报告。

包是一个 git 仓库。选择 git 仓库而非中心化数据库的原因：

- 作者拥有完全的控制权，不依赖任何中心服务
- 版本历史天然可追溯
- 可以离线工作
- 可以被其他包引用（通过 git URL）

## 创建包

作者创建一个 git 仓库，用 Gaia Lang Python DSL 编写知识内容：

```
my-package-gaia/
  pyproject.toml      # [project] + [tool.gaia]，包含名称、版本、UUID
  src/
    my_package/
      __init__.py     # Python DSL declarations + __all__ exports
      premises.py
      reasoning.py
      priors.py       # optional register_prior(...) records
```

**包的身份**由 UUID 确定（不是名称），因为不同作者可能独立创建同名包。名称是人类可读的标签，UUID 是机器身份。

## 声明依赖

作者的工作通常建立在已有知识之上。当前 v0.5 contract 使用标准 Python
dependencies，而不是 `gaia-deps.yml`：

```toml
[project]
dependencies = [
  "aristotle-mechanics-gaia>=1.0.0,<2.0.0",
]
```

推荐通过 registry 安装已注册包：

```bash
gaia add aristotle-mechanics-gaia --version 1.0.0
```

`gaia add` 从 registry 解析包版本、git tag 和 immutable git SHA，然后用
SHA-pinned git URL 调用 `uv add`。当命令运行在 Gaia package 内部时，它还
会 best-effort 下载该 release 的 `beliefs.json` 到
`.gaia/dep_beliefs/<import_name>.json`，供默认 `gaia infer --depth 0` 使用。

后续 LKM 在全局视角下发现的 `connection` 不会自动改写
`pyproject.toml`。如果作者认可某个 connection，需要自己发布新版本，把它
提升为真正的显式 dependency。

## 编译

`gaia compile` 将源码确定性地编译为结构化的中间表示：

```
gaia compile 的输入：
  - Python DSL 源码
  - pyproject.toml 中的 [project] / [tool.gaia] metadata
  - 已安装的 Python / Gaia 依赖

gaia compile 做什么：
  1. best-effort 运行 uv sync --quiet（如果 uv 可用）
  2. 导入 Python package，收集 Knowledge / Action / Strategy / Operator
  3. 将 Gaia Lang 声明编译为结构化推理图
  4. 生成完整性校验哈希和 package interface manifests

gaia compile 的输出（.gaia/ 目录）：
  - ir.json      — 结构化推理图（命题 + 推理链 + 模块结构）
  - ir_hash      — 完整性校验（任何人可重新编译验证）
  - compile_metadata.json
  - formalization_manifest.json
  - manifests/{exports,premises,holes,bridges}.json
```

**关键性质：编译图是确定性的。** 相同的源码 + 依赖 = 相同的 `ir_hash`。任何人都可以克隆仓库，重新运行 `gaia compile`，验证 ir_hash 一致。这是后续 CI 验证的基础。

**编译不运行推理。** 编译只产出结构（什么命题、什么推理链、怎么连接），不计算可信度。结构和概率严格分离。

## 本地推理预览

`gaia infer` 在编译产物上运行本地推理，让作者在发布前预览自己的推理结构是否合理：

```
gaia infer 做什么：
  1. 加载编译产物（推理图）
  2. 解析作者显式声明的依赖版本
  3. 默认读取 `.gaia/dep_beliefs/` 中由 `gaia add` 缓存的上游 release belief；`--depth N` 可改为加载依赖包完整 factor graph
  4. 在本地推理图上运行 Belief Propagation
  5. 输出每个命题的可信度预览

gaia infer 的输出：
  - beliefs.json  — 导出命题的可信度预览（仅本地结果）
```

**为什么需要本地推理：** 作者需要在发布前检查自己的推理是否站得住脚。如果结论的可信度很低，可能说明前提不足或推理链薄弱，需要补充论证。

**为什么 build 和 infer 分离：** 编译是确定性的（可验证），推理是概率性的（依赖参数）。分离后，CI 可以验证编译产物的正确性，而不需要重新运行推理。

**本地结果不是官方生态层 belief。** 当前 CLI 的 `gaia infer` 是本地 numerical preview，不因为 `.gaia/review_manifest.json` 未 accepted 而抑制输出。当前 `gaia register` 会在注册计划中生成 release `beliefs.json`，来源是包源码 priors + optional `dep_beliefs` 的本地推理，并且只包含 exported claims。Review Server / LKM snapshot 属于后续生态层设计，不是当前 CLI 的数值来源。

## 可信度沿依赖图流动

当依赖包更新了（新版本、新证据、可信度变化），下游包可以拉取最新的可信度并重新推理：

```
Package A (基础实验)    →  Package B (理论推导)    →  Package C (应用预测)
  claim₁ = 0.90             claim₃ = 0.82             claim₅ = 0.71

A 更新 → claim₁: 0.95
B 重新 build + infer → claim₃: 0.86
C 重新 build + infer → claim₅: 0.74
```

**更新传播的三种模式：**

| 模式 | 触发方式 | 适用场景 |
|------|---------|---------|
| Lazy（默认） | 下游主动更新依赖后运行 `gaia compile && gaia infer` | 最简单，下游决定何时更新 |
| Pull | CI 定期检查依赖的可信度是否变化 | 活跃维护的包 |
| Push | 上游发布时 webhook 通知下游 | 紧密协作的包 |

**为什么默认是 Lazy：** 去中心化系统中，下游包的作者决定何时、是否接受上游的更新。这和 npm/cargo 的依赖更新模型一致。

## 审核（Review）

本地推理预览满意后，作者向 Official Registry 发起注册/审核请求。Registry 会指派一个或多个 Review Server；这些 Review Server 再把 `review report` 作为 PR 提交到作者自己的仓库。作者合并足够的 report 后，该版本才能通过 Registry 入库。

### 为什么需要审核

作者的 `gaia infer` 只能给出可信度预览。进入官方流程后，Review Server（LLM/agent）会给出两类参数：新命题的初始 prior，以及推理链的条件概率。它审核的是包内推理过程和新命题的证据质量，不直接裁决跨包结构关系。最终进入官方流程的，是那些由 Registry 指派 reviewer 产生、已经被合并进包内 `review report` 文件夹、并在 Registry 入库时通过校验的报告。

### 审核流程

```
作者完成本地 self-review，push/tag 到自己的 Knowledge Repo
  ↓
向 Official Registry 发起注册 / 审核请求
  ↓
Official Registry 指派若干 Review Server
  ↓
Review Server 向作者仓库提交 review report PR：
  - 写入 .gaia/reviews/review-<reviewer>-<timestamp>.json
  - 新命题的初始 prior
  - 每条推理链的条件概率：P(conclusion | premises) = ?
  - 疑似 duplicate / contradiction / connection 的 findings（如有）
  ↓
作者在自己的仓库 PR 中查看结果：
  a. 同意 → 合并 report PR
  b. 不同意 → rebuttal（来回讨论直到达成一致）
  ↓
包内 `.gaia/reviews/` 达到 Registry 要求的 minimal review set
  ↓
Registry 入库校验通过
  ↓
该版本进入 Official Registry
```

审核的详细业务逻辑见 [05-review-and-curation.md](05-review-and-curation.md)。

### 没有 review 也能发布

Review 不是发布包到自己仓库的前提条件。作者完全可以先发布、先协作、先讨论。但如果包内没有达到 Official Registry 要求的 review report 集合，该版本就不能进入官方索引，也不会进入 LKM 的官方 belief 流程。

## 发布

当前 CLI 发布到 source registry 的路径是：

```
当前 v0.5 CLI 流程：
  1. 提交所有源码和编译产物到 git
  2. 创建 release tag（如 v4.0.0）
  3. 确保 git worktree clean，tag 指向 HEAD 且已 push
  4. 运行 gaia register . 查看 dry-run JSON plan
  5. 运行 gaia register . --registry-dir ../gaia-registry --create-pr
```

Review Server 指派和 `.gaia/reviews/` 入库验收属于后续生态层流程，不是当前
`gaia register` 的本地 CLI 前置条件。

**版本语义（semver）：** Gaia 包的 breaking change 含义与代码库不同——它基于命题语义：

| semver | 含义 | 例子 |
|--------|------|------|
| MAJOR | 导出命题的语义变化或撤回 | "Tc = 92K" → "Tc = 89K" |
| MINOR | 新增命题或推理链，已有导出不变 | 增加新实验证据 |
| PATCH | 措辞修正、元数据更新，语义不变 | 修正错别字 |

**编译产物纳入 VCS。** `.gaia/` 目录提交到 git，这样其他人可以引用你的编译产物而不需要安装 Gaia 工具链（类似于 vendoring）。ir_hash 保证完整性。

## 发现研究机会

作者有两个渠道发现研究机会：

**各 LKM Repo 的 Issues（结构化候选）：** 各 LKM Server 在全局推理过程中自动发现候选关系（equivalence、contradiction、connection），以 research task 的形式发布到各自的 LKM Repo。作者可以浏览不同 LKM 的 repo：

- **认领 research task：** 基于候选发现创建自己的知识包，走标准的发布流程
- **参与调查：** 在 issue 评论区提供专业意见

**Official Registry Issues（open questions + relation reports）：** 社区成员提出的研究问题、知识空白、以及人类/agent 在研究过程中发现的跨包关系线索。作者可以：

- **浏览 open questions：** 发现哪些领域需要新的知识包
- **提交 relation report：** 如果在研究过程中发现其他包之间可能存在 duplicate / contradiction / connection，提交 issue 给 Official Registry
- **提出 open question：** 在研究过程中发现知识网络的空白或需求，提交 issue 给社区讨论

详见 [05-review-and-curation.md](05-review-and-curation.md) 中的 LKM Curation 流程和 [02-decentralized-architecture.md](02-decentralized-architecture.md) 中的 LKM Repo 和 Open Questions。

## 纯 Level 0 的局限

不注册到 Official Registry 的包完全可以工作，但有以下局限：

- **只看到直接依赖图。** 如果两个包独立推导出了相同的结论，但彼此不知道对方的存在，它们的证据无法汇聚。
- **没有跨包去重。** 相同的命题在不同包中是独立的实体，没有被识别为"同一个命题"。
- **没有官方 review 校准。** 只有作者本地设定的预览参数，或手动选择的 LKM snapshot 参考值，没有通过 Registry 验收的 review report 集合。

这些局限由 Official Registry 的 review 协调，以及各 LKM Repo 发布的 belief snapshots 进一步缓解。见 [04-registry-operations.md](04-registry-operations.md) 和 [06-belief-flow-and-quality.md](06-belief-flow-and-quality.md)。
