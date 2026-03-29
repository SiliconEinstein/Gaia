# 包的创建与发布

> **Status:** Current canonical

本文档描述作者从创建知识包到发布的完整旅程。

## 为什么需要包

科学知识不是孤立的命题，而是有结构的论证——前提支持结论，多条推理链汇聚成证据网络。包是这种结构化知识的最小发布单元，类似于一篇论文或一个实验报告。

包是一个 git 仓库。选择 git 仓库而非中心化数据库的原因：

- 作者拥有完全的控制权，不依赖任何中心服务
- 版本历史天然可追溯
- 可以离线工作
- 可以被其他包引用（通过 git URL）

## 创建包

作者创建一个 git 仓库，用 Gaia Lang（基于 Typst 的 DSL）编写知识内容：

```
my-package/
  typst.toml          # 包的身份：UUID + 名称 + 版本
  gaia-deps.yml       # 依赖声明（指向其他包的 git 仓库）
  src/
    main.typ          # 知识内容：命题、推理链、模块结构
    experiment.typ
    analysis.typ
```

**包的身份**由 UUID 确定（不是名称），因为不同作者可能独立创建同名包。名称是人类可读的标签，UUID 是机器身份。

## 声明依赖

作者的工作通常建立在已有知识之上。依赖的指向方式取决于对方是否已在 Official Registry 注册（参见 [02-decentralized-architecture.md](02-decentralized-architecture.md) 的架构分层）：

```yaml
# gaia-deps.yml — 已注册包（推荐）
vacuum_prediction:
  registry: "official"                  # 引用 Official Registry
  package: "falling-bodies"             # Registry 中的包标识
  version: "4.0.0"
  node: "vacuum_prediction"             # 引用该包中的哪个命题

# gaia-deps.yml — 未注册包（git URL 回退）
vacuum_prediction:
  repo: "https://github.com/galileo/falling-bodies"
  tag: "v4.0.0"
  node: "vacuum_prediction"
```

**已注册包优先引用 Registry 标识**，因为 Registry 提供全局身份、包索引和官方 review 协调。**未注册包通过 git URL + tag 引用**——两个人互相引用对方的 GitHub 仓库就能建立知识关系，不需要任何中心服务。注册中心是可选的增值层，不是前提条件。

作者可以选择性声明自己的工作和被引用命题的关系（`role` 字段）：这条推理是以它为前提、是对它的独立验证、还是对它的细化？这个声明是帮助 reviewer 快速定位的线索，不是安全机制——系统正确性不依赖作者诚实。

这里的 dependency 是**作者显式声明、可锁版本、影响 build / release 的包依赖**。后续 LKM 在全局视角下发现的 `connection` 不会自动改写 `gaia-deps.yml`。如果作者认可某个 `connection`，需要自己发布新版本，把它提升为真正的显式 dependency。

## 编译

`gaia build` 将源码确定性地编译为结构化的中间表示：

```
gaia build 的输入：
  - 源码（.typ 文件）
  - 依赖声明（gaia-deps.yml）
  - 锁文件（gaia-lock.yml，如果有的话）

gaia build 做什么：
  1. 解析依赖，拉取依赖包的编译产物
  2. 将 Gaia Lang 源码编译为结构化的推理图
  3. 生成完整性校验哈希

gaia build 的输出（.gaia/ 目录）：
  - ir.json      — 结构化推理图（命题 + 推理链 + 模块结构）
  - ir_hash      — 完整性校验（任何人可重新编译验证）
```

**关键性质：编译是确定性的。** 相同的源码 + 依赖 = 相同的编译产物。任何人都可以克隆仓库，重新运行 `gaia build`，验证 ir_hash 一致。这是后续 CI 验证的基础。

**编译不运行推理。** 编译只产出结构（什么命题、什么推理链、怎么连接），不计算可信度。结构和概率严格分离。

## 本地推理预览

`gaia infer` 在编译产物上运行本地推理，让作者在发布前预览自己的推理结构是否合理：

```
gaia infer 做什么：
  1. 加载编译产物（推理图）
  2. 解析作者显式声明的依赖版本
  3. （可选）读取某个 LKM Repo 发布的 belief snapshot，作为上游命题的参考输入
  4. 在本地推理图上运行 Belief Propagation
  5. 输出每个命题的可信度预览

gaia infer 的输出：
  - beliefs.json  — 导出命题的可信度预览（仅本地结果）
```

**为什么需要本地推理：** 作者需要在发布前检查自己的推理是否站得住脚。如果结论的可信度很低，可能说明前提不足或推理链薄弱，需要补充论证。

**为什么 build 和 infer 分离：** 编译是确定性的（可验证），推理是概率性的（依赖参数）。分离后，CI 可以验证编译产物的正确性，而不需要重新运行推理。

**本地结果不是官方 belief。** 官方 prior 来自 Official Registry 接受的 review PR；对外发布的 belief 结果来自你选择参考的 LKM Repo snapshot，而不是包仓库自带的 `.gaia/beliefs.json`。

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
| Lazy（默认） | 下游主动 `gaia update && gaia build && gaia infer` | 最简单，下游决定何时更新 |
| Pull | CI 定期检查依赖的可信度是否变化 | 活跃维护的包 |
| Push | 上游发布时 webhook 通知下游 | 紧密协作的包 |

**为什么默认是 Lazy：** 去中心化系统中，下游包的作者决定何时、是否接受上游的更新。这和 npm/cargo 的依赖更新模型一致。

## 审核（Review）

本地推理预览满意后，作者把包发布到自己的仓库，并向 Official Registry 请求注册。官方 review 由 Registry 协调，Review Server 通过 review PR 提交参数。

### 为什么需要审核

作者的 `gaia infer` 只能给出可信度预览。进入官方流程后，Review Server（LLM/agent）会给出两类参数：新命题的初始 prior，以及推理链的条件概率。它审核的是包内推理过程和新命题的证据质量，不直接裁决跨包结构关系。

### 审核流程

```
作者完成本地 self-review，push/tag 到自己的 Knowledge Repo
  ↓
向 Official Registry 请求注册
  ↓
Official Registry 受理包版本，并指派若干 Review Server
  ↓
Review Server 提交 review PR：
  - 新命题的初始 prior
  - 每条推理链的条件概率：P(conclusion | premises) = ?
  - 疑似 duplicate / contradiction / connection 的 findings（如有）
  ↓
作者在 Registry 的 review PR 中查看结果：
  a. 同意 → Registry 接受该 review PR
  b. 不同意 → rebuttal（来回讨论直到达成一致，或由 Registry 追加 reviewer）
```

审核的详细业务逻辑见 [05-review-and-curation.md](05-review-and-curation.md)。

### 没有 review 也能发布

Review 不是发布包的前提条件。作者可以先发布、先注册，后续再补充官方 review。但没有被 Official Registry 接受的 review PR 时，该包只有结构被索引，没有官方 prior 和条件概率参数，也不会进入 LKM 的官方 belief 流程。

## 发布

审核完成后（或选择跳过审核），作者发布包：

```
发布流程：
  1. 提交所有源码和编译产物到 git
  2. 创建 release tag（如 v4.0.0）
  3.（可选）附上本地 self-review 结果，供后续 reviewer 参考
  4.（可选）向 Official Registry 请求注册，由 Registry 协调官方 review（见 04-registry-operations.md）
```

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
- **没有官方 review 校准。** 只有作者本地设定的预览参数，或手动选择的 LKM snapshot 参考值，没有 Official Registry 接受的 prior / strategy。

这些局限由 Official Registry 的 review 协调，以及各 LKM Repo 发布的 belief snapshots 进一步缓解。见 [04-registry-operations.md](04-registry-operations.md) 和 [06-belief-flow-and-quality.md](06-belief-flow-and-quality.md)。
