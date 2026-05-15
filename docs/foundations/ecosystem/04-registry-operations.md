# Official Registry 的运作

> **Status:** Ecosystem architecture with v0.5 implementation notes

> 当前 `gaia pkg register` 实现的是 source registry 写入：验证包 metadata、
> fresh IR、clean git/tag/GitHub repo，然后写 `Package.toml`、
> `Versions.toml`、`Deps.toml` 和
> `releases/<version>/{exports,premises,holes,bridges,beliefs}.json`。
> 本文关于 registry 指派 reviewer、验收 `.gaia/reviews/`、以及 official
> review reports 作为唯一参数来源的段落是生态层设计目标；不是当前 Gaia CLI
> 的注册前置条件。

本文档描述 Official Registry（官方注册仓库）的业务逻辑：包如何注册、reviewer 如何被指派、包内 review reports 如何被验收、以及人类发现的问题如何进入后续调查流程。

## 为什么需要 Official Registry

Layer 0（纯包级）的局限：每个包只看到自己的直接依赖。如果两个独立的研究者分别推导出了相同的结论，但彼此不知道对方的存在，他们的证据无法汇聚。

Official Registry 解决的不是"替 LKM 做全局推理"，而是提供一个所有已注册包都能引用的公共索引，在预注册阶段指派 reviewer，并在入库时校验包内的 review reports 是否满足最低标准。

**Official repo 采用 Julia General registry 模型：** 就是一个 GitHub 仓库。一切通过 PR。任何人可以 fork 出自己的 registry（不同学科、不同机构可以有不同的 registry）。

## 注册流程

### 为什么需要注册

注册的目的是让 Official Registry 知道这个包的存在，从而能够：

1. 记录该包的身份、版本和显式依赖
2. 让其他包、人类研究者、以及各 LKM 能发现并引用它
3. 为该版本指派 reviewer，并验证最终提交的 review reports 是否满足官方最小 policy

### 注册的具体流程

```
作者在自己的包仓库 release tag v4.0.0
  ↓
作者请求注册（@GaiaRegistrator，GitHub App 或 issue comment）
  ↓
Official Registry 为该版本指派若干 Review Server
  ↓
被指派的 Review Server 向作者仓库提交 review report PR
  ↓
作者合并足够的 review reports 到 `.gaia/reviews/`
  ↓
Bot 创建 PR 到 Official Registry：
  + packages/my-package/Package.toml      （UUID, 名称, 仓库 URL）
  + packages/my-package/Versions.toml     （版本 → ir_hash → git tag）
  + packages/my-package/Deps.toml         （依赖列表）
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
| **编译重现** | 克隆包仓库，重新 `gaia build compile` / `gaia build check`，比对 ir_hash | 确保编译产物没有被篡改 |
| **依赖可解析** | 检查所有依赖是否已在 Official Registry 中注册 | 注册的前提条件：要注册就必须所有依赖也已注册，确保推理链完整。纯包层（Level 0）用 git URL 引用未注册包不受此限 |
| **Schema 合法** | 检查编译产物的结构是否符合规范 | 确保后续处理不会出错 |
| **Review reports 验证** | 检查 `.gaia/reviews/` 是否存在、reviewer 是否已注册、reviewer 是否属于 Registry 指派集合、report 数量是否达到 minimal policy、参数范围是否合法 | 确保官方 prior / strategy 的来源可信，且达到最低审核门槛 |

### 等待期的作用

- **新包 3 天**：给社区时间审查是否有明显问题（如恶意内容、垃圾包）
- **版本更新 1 小时**：已知包的更新风险较低，快速通过

等待期内任何人可以评论或阻止。这是社区自治，不是中心审核。

### 注册完成后发生什么

包合并到 Official Registry 后，只是**进入官方索引**。此时 Registry 知道这个包版本存在、它依赖谁、它导出了什么结构。

注册阶段**不会**直接做以下事情：

- 不做 binding / equivalence / duplicate merge 的结构裁决
- 不把 LKM 发现的 `connection` 写回作者的 `pyproject.toml` dependencies
- 不发布单一的官方 belief 结果

这些事情都属于后续的 review finding、issue 调查、或 LKM curation / belief snapshot 流程。

### 相似性粗筛只是线索，不是裁决

Registry 可以运行 embedding / TF-IDF 等方法做粗筛，把疑似相似命题推荐给 reviewer 或人类研究者。但粗筛只用于发现线索，不会在 package PR 合并时直接创建 binding / equivalence / dedup 结果。

## Review Reports 的验收与激活

### 官方参数从哪里来

Official Registry 认可的参数只有一个来源：**由 Registry 指派 reviewer 生成、随包版本一同提交、并通过入库校验的 review reports**。这些 review reports 可以包含：

- 新命题的初始 prior
- 推理链的条件概率参数
- 疑似 duplicate / contradiction / connection 的 findings

### review reports 的流程

```
作者请求注册某个包版本
  ↓
Official Registry 指派 reviewer
  ↓
作者在自己的包仓库中合并 assigned review report PR
  ↓
该版本的 `.gaia/reviews/` 形成一个 review set
  ↓
register.yml 校验：
  - report 文件存在
  - reviewer 已注册
  - reviewer 属于 Registry 指派集合
  - report 数量达到 minimal policy
  - 参数范围合法
  ↓
package PR 合并
  ↓
该包版本获得官方 prior / strategy，成为后续 LKM snapshot 的有效输入
```

### 有 official review 和没有 official review 的区别

**已有满足 policy 的 assigned review reports：**
```
包版本已注册到 Official Registry
  ↓
关联 review reports 通过 register.yml / review.yml 验证：
  - reviewer 已注册
  - reviewer 属于 Registry 指派集合
  - report 数量达到 minimal policy
  - 参数在合理范围内（Cromwell's rule）
  ↓
package PR 合并
  ↓
该包版本获得官方 prior / strategy，供各 LKM 消费
```

**review reports 不足或不合规：**
```
作者仓库中的包版本准备注册
  ↓
`.gaia/reviews/` 缺失、数量不足、或来源不合规
  ↓
Official Registry 拒绝入库
  ↓
作者继续收集 / 合并更多 review reports 后重新提交
```

### 为什么这样设计

1. **低门槛发布，高门槛入库：** 任何人都可以先在自己的仓库发布包，但进入 Official Registry 前必须带上满足最小标准的 assigned review reports。
2. **质量门控：** 官方 prior / strategy 只来自 Registry 指派 reviewer 产生、并在入库时通过校验的 review report 集合。
3. **阶段边界清晰：** Review report 存在包仓库；Registry 负责指派和验收；关系发现进入 issue / finding；belief 计算由各 LKM 自己发布。

## Official Registry 的数据结构

```
official-repo/
├── packages/              # 包注册信息
│   ├── package-a/
│   │   ├── Package.toml   # UUID, 名称, 仓库 URL
│   │   ├── Versions.toml  # 版本 → ir_hash → git tag
│   │   ├── Deps.toml      # 依赖
│   │   └── releases/
│   │       └── 1.0.0/
│   │           ├── exports.json
│   │           ├── premises.json
│   │           ├── holes.json
│   │           ├── bridges.json
│   │           └── beliefs.json
│   └── package-b/
│       └── ...
├── reviewers/             # future ecosystem layer: reviewer 注册信息
│   ├── alice/
│   │   └── Reviewer.toml  # 身份, 专长领域, 担保人
│   └── bob/
│       └── Reviewer.toml
├── lkms/                  # future ecosystem layer: LKM 注册信息
│   └── lkm-a/
│       └── LKM.toml       # 仓库 URL, snapshot feed, 元数据
├── review-assignments/    # future ecosystem layer: 版本 -> 被指派 reviewers
│   └── assignments.jsonl
├── review-policies/       # future ecosystem layer: 入库 review gate
│   └── default.toml       # minimal count、格式要求、校验规则
├── review-index/          # future ecosystem layer: review report 元数据索引
│   └── reports.jsonl      # package version → report paths / reviewer ids
└── .github/workflows/
    ├── register.yml       # 包注册验证（含 review report gate）
    └── review.yml         # reviewer 身份 / report 合规检查
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
- [05-review-and-curation.md](05-review-and-curation.md) — Review Server 审核、review report 落包、LKM / 人类 curation 的发现与确认流程
- [06-belief-flow-and-quality.md](06-belief-flow-and-quality.md) — belief snapshot、全局推理、错误修正场景
