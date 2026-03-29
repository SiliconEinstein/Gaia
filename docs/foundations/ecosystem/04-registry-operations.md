# Official Registry 的运作

> **Status:** Current canonical

本文档描述 Official Registry（官方注册仓库）的业务逻辑：包如何注册、官方 review 如何协调、以及人类发现的问题如何进入后续调查流程。

## 为什么需要 Official Registry

Layer 0（纯包级）的局限：每个包只看到自己的直接依赖。如果两个独立的研究者分别推导出了相同的结论，但彼此不知道对方的存在，他们的证据无法汇聚。

Official Registry 解决的不是"替 LKM 做全局推理"，而是提供一个所有已注册包都能引用的公共索引，并协调官方 review。

**Official repo 采用 Julia General registry 模型：** 就是一个 GitHub 仓库。一切通过 PR。任何人可以 fork 出自己的 registry（不同学科、不同机构可以有不同的 registry）。

## 注册流程

### 为什么需要注册

注册的目的是让 Official Registry 知道这个包的存在，从而能够：

1. 记录该包的身份、版本和显式依赖
2. 让其他包、人类研究者、以及各 LKM 能发现并引用它
3. 指派官方 reviewer，并接收该包版本对应的 review PR

### 注册的具体流程

```
作者在自己的包仓库 release tag v4.0.0
  ↓
作者请求注册（@GaiaRegistrator，GitHub App 或 issue comment）
  ↓
Bot 创建 PR 到 Official Registry：
  + packages/my-package/Package.toml      （UUID, 名称, 仓库 URL）
  + packages/my-package/Versions.toml     （版本 → ir_hash → git tag）
  + packages/my-package/Deps.toml         （依赖列表）
  ↓
Official Registry 记录该包版本，并可指派若干 Review Server
  ↓
CI 自动验证（register.yml）
  ↓
等待期（新包 3 天，版本更新 1 小时）
  ↓
自动合并 package PR（该包进入官方索引）
```

### CI 验证做什么

CI 做的是**纯机械验证**——不需要人类判断，不涉及科学评估：

| 验证项 | 做什么 | 为什么 |
|--------|--------|--------|
| **编译重现** | 克隆包仓库，重新 `gaia build`，比对 ir_hash | 确保编译产物没有被篡改 |
| **依赖可解析** | 检查所有依赖是否已在 Official Registry 中注册 | 注册的前提条件：要注册就必须所有依赖也已注册，确保推理链完整。纯包层（Level 0）用 git URL 引用未注册包不受此限 |
| **Schema 合法** | 检查编译产物的结构是否符合规范 | 确保后续处理不会出错 |
### 等待期的作用

- **新包 3 天**：给社区时间审查是否有明显问题（如恶意内容、垃圾包）
- **版本更新 1 小时**：已知包的更新风险较低，快速通过

等待期内任何人可以评论或阻止。这是社区自治，不是中心审核。

### 注册完成后发生什么

包合并到 Official Registry 后，只是**进入官方索引**。此时 Registry 知道这个包版本存在、它依赖谁、它导出了什么结构。

注册阶段**不会**直接做以下事情：

- 不做 binding / equivalence / duplicate merge 的结构裁决
- 不把 LKM 发现的 `connection` 写回作者的 `gaia-deps.yml`
- 不发布单一的官方 belief 结果

这些事情都属于后续的 review finding、issue 调查、或 LKM curation / belief snapshot 流程。

### 相似性粗筛只是线索，不是裁决

Registry 可以运行 embedding / TF-IDF 等方法做粗筛，把疑似相似命题推荐给 reviewer 或人类研究者。但粗筛只用于发现线索，不会在 package PR 合并时直接创建 binding / equivalence / dedup 结果。

## 官方 Review 的协调与激活

### 官方参数从哪里来

Official Registry 认可的参数只有一个来源：**被 Registry 指派并最终接受的 review PR**。这些 review PR 可以包含：

- 新命题的初始 prior
- 推理链的条件概率参数
- 疑似 duplicate / contradiction / connection 的 findings

### review PR 的流程

```
Package PR 被创建或合并
  ↓
Official Registry 指派若干 Review Server
  ↓
Review Server 提交 review PR：
  - reviewer 身份
  - 目标包版本
  - claim priors
  - chain strategies
  - findings（如有）
  ↓
作者在 review PR 中 rebuttal
  ↓
Official Registry 接受 review PR
  ↓
该包版本获得官方 prior / strategy，成为后续 LKM snapshot 的有效输入
```

### 有 official review 和没有 official review 的区别

**已有被接受的 review PR：**
```
包版本已注册到 Official Registry
  ↓
关联 review PR 通过 review.yml 验证：
  - reviewer 已注册
  - reviewer 是 Registry 指派或认可的实例
  - 参数在合理范围内（Cromwell's rule）
  ↓
review PR 合并
  ↓
该包版本获得官方 prior / strategy，供各 LKM 消费
```

**还没有被接受的 review PR：**
```
包版本已注册到 Official Registry
  ↓
只有结构被索引，没有官方 prior / strategy
  ↓
LKM 在官方 belief 流程中跳过该版本的未审参数
  ↓
后续仍可由 Registry 指派 reviewer 补交 review PR
```

### 为什么这样设计

1. **低门槛注册：** 任何人都可以注册包，不需要先找 Review Server。包版本可以先进入公共索引、先被发现和被引用，即使官方参数还未激活。
2. **质量门控：** 只有被 Registry 接受的 review PR 才能给出官方 prior / strategy，防止 review shopping。
3. **阶段边界清晰：** 注册负责索引和协调；关系发现进入 issue / finding；belief 计算由各 LKM 自己发布。

## Official Registry 的数据结构

```
official-repo/
├── packages/              # 包注册信息
│   ├── package-a/
│   │   ├── Package.toml   # UUID, 名称, 仓库 URL
│   │   ├── Versions.toml  # 版本 → ir_hash → git tag
│   │   └── Deps.toml      # 依赖
│   └── package-b/
│       └── ...
├── reviewers/             # reviewer 注册信息
│   ├── alice/
│   │   └── Reviewer.toml  # 身份, 专长领域, 担保人
│   └── bob/
│       └── Reviewer.toml
├── lkms/                  # LKM 注册信息
│   └── lkm-a/
│       └── LKM.toml       # 仓库 URL, snapshot feed, 元数据
├── reviews/               # 审核记录
│   ├── sources.jsonl      # 审核来源信息
│   ├── priors/            # 命题的先验赋值
│   ├── strategies/        # 推理链的参数赋值
│   └── findings/          # review 中提到的疑似跨包关系
└── .github/workflows/
    ├── register.yml       # 包和 reviewer 注册验证
    └── review.yml         # review 合规检查（含 reviewer 身份验证）
```

一切都是 git commit，一切可审计，一切可 fork。

## Open Questions 与 Relation Reports（Registry Issues）

Official Registry 的 Issues 承载人类/agent 在研究过程中发现的问题、知识空白、以及关系线索：

- **研究问题：** "有没有人在不同氧含量条件下验证过 YBCO 的 Tc？"
- **包需求：** "Y 领域缺少 Z 方面的知识包"
- **知识空白：** "X 和 Y 之间的关系目前没有包覆盖"
- **关系线索：** "Package A 的结论和 Package B 的结论疑似 duplicate / contradiction / connection"

这和 LKM Repo 的 research tasks 互补：LKM Repo 上是自动发现的结构化候选；Official Registry Issues 上则是人类/agent 主动提交的 open questions 和 relation reports。两者都只是后续调查的入口，不会在 issue 创建时直接改写全局结构。

Labels 建议：`open-question` / `relation-report` / `package-request` / `gap-analysis`。

## 可 fork、可联邦

Official Registry 就是一个 git 仓库。任何人可以 fork 出自己的 registry：

- 不同学科可以有不同的 registry（物理学、生物学、经济学各自维护）
- 不同机构可以有不同的审核标准
- 不同 registry 之间可以互相引用（联邦模型）

这意味着没有单一的"真理权威"——不同社区可以对同一命题有不同的可信度评估，这正是科学的本质。

## 相关文档

- [02-decentralized-architecture.md](02-decentralized-architecture.md) — 架构总纲，Registry 在分层中的定位
- [03-authoring-and-publishing.md](03-authoring-and-publishing.md) — 作者从创建包到发布的完整旅程（注册的前置流程）
- [05-review-and-curation.md](05-review-and-curation.md) — Review Server 审核 + LKM / 人类 curation 的发现与确认流程
- [06-belief-flow-and-quality.md](06-belief-flow-and-quality.md) — belief snapshot、全局推理、错误修正场景
