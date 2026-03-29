# 审核与策展

> **Status:** Current canonical

本文档描述 Review Server 和 LKM / 人类 curation 的业务逻辑——官方 prior / strategy 如何产生，跨包关系如何被发现、调查和确认。

## Review Server

### Review Server 是什么

Review Server 就是 reviewer——一个用 LLM 或 agent 实现的自动审核服务。它审核的是**包内部推理过程的逻辑可靠性**，不负责判断前提本身是否正确。

关键区分：

| | Review Server 管 | Review Server 不管 |
|---|---|---|
| **职责** | 新命题的初始 prior、推理过程的逻辑可靠性 | 上游前提是否重新判真、跨包结构是否直接改写 |
| **例子** | "这个新结论初始可信度应是多少？"；"从这些前提出发，这个推理步骤站得住吗？" | "我要现在就把 A 和 B 合并吗？"；"我要替作者改依赖图吗？" |
| **产出** | claim priors、推理链条件概率、疑似跨包关系 findings | binding / equivalence / dedup / package dependency 变更 |

**为什么这样分工：** 已有前提的可靠性来自它们自己版本对应的官方 review / 你所选 LKM snapshot。Review Server 在当前包版本里做的事，是给新命题提供初始 prior，并评估"假设前提成立，这条推理链有多可靠"。

### Review Server 的部署

- **独立部署，可多实例：** 不同机构可以运行自己的 Review Server
- **格式约束：** 只要 review PR 的 payload 符合规定格式，任何 Review Server 都可以
- **在 Official Registry 注册：** Review Server 需要在 Official Registry 注册身份，其 review PR 才被 CI 认可
- **官方资格由 Registry 决定：** 只有 Registry 指派或明确认可的 reviewer，其 review PR 才能成为官方参数来源

### 审核什么

Review Server 审核包内部的推理结构：

1. **新命题的初始 prior** — 这个新结论在进入官方流程时，初始可信度应该是多少？
2. **推理步骤的逻辑有效性** — 从前提到结论的每一步是否逻辑上成立？
3. **推理链的整体可靠性** — 整条推理链的条件概率应该是多少？
4. **逻辑缺陷检测** — 是否存在循环推理、跳跃推理、隐含假设未声明等问题？
5. **可疑关系标注** — 如发现疑似 duplicate / contradiction / connection，写入 finding 供后续调查

Review Server **不**审核：
- 前提命题本身是否正确（那是上游包的事）
- 该推理链和 Official Registry 中其他推理链的结构关系是否立即生效（那是 issue / curation 的事）
- 是否把某个 `connection` 直接写回作者的 package dependency（那必须由作者自己发布新版本）

### 审核的具体流程

```
作者完成 gaia build + gaia infer，push/tag 并请求 Official Registry 注册
  ↓
① Official Registry 受理该包版本，并指派若干 Review Server
  ↓
② Review Server 分析包内部的推理结构：
   - 评估新命题的初始 prior
   - 逐条检查推理链的逻辑有效性
   - 评估每条推理链的条件概率
   - 检查是否有逻辑缺陷和可疑跨包关系
  ↓
③ Review Server 向 Official Registry 提交 review PR：
   - 新命题的 prior（遵守 Cromwell's rule：不允许 0 和 1）
   - 每条推理链的条件概率
   - 发现的问题、建议、以及 findings
  ↓
④ 作者在 review PR 中查看结果并 rebuttal
  ↓
⑤ Official Registry 接受 review PR：
   a. 同意该参数集 → 成为该包版本的官方参数来源
   b. 僵局未解 → Registry 追加 reviewer 或转交仲裁
```

### Rebuttal 流程

作者和 Review Server 可以在 Official Registry 的 review PR 中来回 rebuttal，直到达成一致：

```
作者对 review 中的某条评估提出异议：
  "你给这条推理链 P(conclusion|premises) = 0.6，
   但我认为应该更高，因为..."
  ↓
Review Server 回应：
  a. 接受作者的论证 → 调整参数
  b. 维持原判 → 解释理由
  c. 部分接受 → 折中调整
  ↓
继续 rebuttal 直到双方达成一致
  ↓
最终被接受的 review PR 保留完整 rebuttal 历史
```

**为什么需要 rebuttal：** Review Server 是 LLM/agent，不是绝对权威。作者对自己的推理过程最了解，可能有 Review Server 没考虑到的上下文。Rebuttal 让双方的判断都能被记录和考量。

**Rebuttal 历史的价值：** 完整的 rebuttal 记录随 review PR 保留，其他人可以看到审核过程中讨论了什么、为什么最终选择了这个参数值。这增加了透明度和可审计性。

**Rebuttal 僵局：** 如果作者和 Review Server 始终无法达成一致，由 Official Registry 追加 reviewer 或发起仲裁。核心原则是：不存在单一审核者可以无限否决贡献，也不存在作者自行绕开指派 reviewer 去挑一个更宽松的 reviewer。

### 审核后的产出

review PR 的内容包含：

```
对每条推理链：
  - 新命题的初始 prior（如该推理链导出新结论）
  - 逻辑评估：有效 / 有缺陷（附说明）
  - 条件概率初始值：P(conclusion | premises) = 0.85
  - 置信说明：为什么给这个值
  - rebuttal 历史（如果有的话）
  - findings：疑似 duplicate / contradiction / connection（如果有的话）

整体评估：
  - 包的推理结构概览
  - 主要优点和问题
  - reviewer 身份（哪个 Review Server 实例）
```

这些被 Official Registry 接受的 prior / strategy，会成为各 LKM 发布 belief snapshot 时采用的官方输入。

### 没有 review 的包

**包可以不经过官方 review 就注册到 Official Registry。** 但是：

- 没有被接受的 review PR，就没有官方 claim priors 和条件概率参数
- 没有官方参数 = LKM 的官方 belief 流程跳过这些未审输入
- 效果：包版本被索引了，但没有进入官方 belief 计算

这意味着 review 不是注册的前提条件，而是官方参数激活的前提条件。作者可以先注册再由 Registry 协调 reviewer，review PR 通过后续 PR 补充。

## LKM 的 Curation 角色

### 为什么 curation 是 LKM 的一部分

Review Server 处理的是单个包内部的推理质量。但有些跨包关系需要在全局视角下才能发现——而 LKM 在构建全局图、运行全局推理的过程中，天然具备这个视角。Curation 不是一个独立的服务，而是 LKM 全局推理过程的**副产品**。

### LKM 作为 research agent

LKM 和人类/agent 是两类并列的贡献者。区别在于知识来源：

- **人类/agent：** 从实验、理论、分析中创建知识包
- **LKM：** 从全局图构建过程中发现跨包关系，创建 curation 包

但两者走**完全相同的流程**：创建包 → 请求 Official Registry → official review → 合并。LKM 没有捷径。

### Research Tasks：发现与分拣

LKM 的 curation 流程分两阶段。第一阶段是**发现**——各 LKM Server 在全局推理过程中识别出候选关系，以 **Issues** 的形式发布到各自的 LKM Repo。这是轻量级的发现记录，不直接生效。Issues 支持状态管理（labels：`open` → `investigating` → `confirmed`/`rejected`）、社区讨论（评论区）和批量发现（一个 issue 列一批同类候选）。

### 跨包关系的发现入口

跨包关系有三类发现入口，三者都只是**发现记录**，不会当场改全局结构：

1. **Official Registry issue：** 人类 / agent 在研究过程中发现疑似 duplicate / contradiction / connection，就向 Official Registry 提交 relation report。
2. **LKM Repo issue：** LKM Server 在 curation 过程中发现候选关系，就在自己的 LKM Repo 发布 research task。
3. **Review finding：** Review Server 在审核包内逻辑时发现疑似跨包关系，就写进 review PR 的 finding，供后续调查。

LKM 的价值在于它能系统性地扫描全局图，发现人类不容易注意到的关系。但人类的洞察力同样重要——三类入口互补。

### Research Tasks 的三类候选

三类候选：

**候选一：equivalence（等价候选）**

两个命题语义接近。发现的触发点是相同的，但调查结论可能完全不同：

| 调查结论 | 含义 | 处理方式 |
|---------|------|---------|
| **duplicate** | 两个命题说的是同一件事（注册时 embedding 匹配漏掉了） | 合并：引用重定向，暂停参数，re-review |
| **independent evidence** | 两条独立推理链汇聚到相同结论（真正的独立验证） | 不合并，识别为证据汇聚（增强可信度） |
| **refinement** | 一个命题是另一个的特化或推广 | 建立细化关系 |

```
例：LKM 发现两个命题语义接近
  命题 A（"YBCO 在 92K 以下超导"）≈ 命题 B（"YBa₂Cu₃O₇ 的 Tc 为 92±1K"）
    ↓
在 LKM Repo 创建 equivalence issue
    ↓
调查：A 和 B 来自不同实验室的独立实验？还是同一数据源的不同表述？
    ↓
结论：
  a. 同一数据源 → duplicate → 合并，暂停参数，re-review
  b. 独立实验 → independent evidence → 不合并，证据汇聚增强可信度
  c. B 是 A 在特定氧含量条件下的细化 → refinement → 建立细化关系
```

**为什么 duplicate 需要暂停参数：** 合并后，原本指向 A 和 B 两个独立命题的推理链现在都指向 A。如果之前它们被判定为"独立证据"，现在需要重新评估——因为它们可能实际上是在讨论同一个命题，不应该 double counting。暂停参数确保在 re-review 完成前回退到保守状态（可能少算证据，但不会多算）。

**候选二：contradiction（矛盾候选）**

两个命题互相冲突。

```
例：LKM 发现：
  命题 P（"Tc = 92K"）和命题 Q（"Tc = 89K"）互相矛盾
    ↓
在 LKM Repo 创建 contradiction issue
    ↓
调查确认 → curation 包声明矛盾关系
    ↓
确认矛盾 → 推理引擎自动压低双方的可信度
```

**矛盾是结构性事实，不是判断。** 一旦确认两个命题矛盾，推理引擎保证它们不会同时具有高可信度——这是逻辑一致性的自动维护。

**候选三：connection（隐含连接候选）**

一个包的结论高度相关另一个包的前提，但双方都没有声明依赖。

```
例：LKM 发现：
  Package X 的结论和 Package Y 的前提高度相关
  但 X 和 Y 之间没有依赖关系
    ↓
在 LKM Repo 创建 connection issue
  ↓
调查确认 → curation 包声明跨包 inferred link
  ↓
在 Registry / LKM 侧建立连接，可信度沿新连接流动
  ↓
如果作者认可该连接并希望它成为真正的 package dependency，需要作者自己发新版本更新 `gaia-deps.yml`
```

### 从 Research Task 到 Curation 包

发现记录确认后，进入第二阶段——由接手该任务的贡献者（LKM 或人类 / agent）创建 curation 包，走标准流程：

```
Official Registry issue / LKM Repo issue / review finding
  ↓
调查（LKM 自动分析 + 人类研究者在 issue 评论区讨论）
  ↓
确认 → 创建 curation 包：
  - 声明发现的关系和调查结论
  - 附带检测依据和置信度
  - 在对应 issue / review finding 中贴上 curation 包链接
  ↓
Official Registry 指派 Review Server 审核 curation 包
  ↓
被接受的 review PR + curation 包注册到 Official Registry
  ↓
对应的 LKM 在后续 snapshot / global inference 中吸收该结构变更
```

### Curation 的关键设计

- **两阶段流程：** LKM Repo Issues（轻量级发现记录）→ curation 包（标准的包流程）。发现不直接生效。
- **发现入口不止一种：** 可来自 Official Registry issues、LKM Repo research tasks、或 review findings。
- **Issues 管理 research tasks：** 天然支持状态管理、讨论、labels 过滤，不污染 git 树。批量发现可合并为单个 issue，低置信度候选可自动关闭。
- **以包的形式贡献：** 贡献者不直接修改已有包或 Registry 数据，而是创建新的 curation 包。这保持了数据的不可变性和审计性。
- **经过 Review：** curation 包和人类的知识包一样，需要经过 Review Server 审核才能注册。
- **LKM 无特权：** LKM 在 Official Registry 注册了身份，但不享有任何快速通道。它的 curation 包和普通包走完全相同的流程。
- **Research task 对社区可见：** 候选以 Issues 发布在 LKM Repo 中，人类研究者可以浏览、参与调查、或基于候选创建自己的知识包。

## Review Server 和 LKM 的关系

| | Review Server ×N | LKM Server ×N |
|---|---|---|
| **本质** | LLM/agent 审核员 | 全局推理引擎 + research agent |
| **审核时机** | Registry 协调的 official review 阶段 | 全局推理和 curation 过程中 |
| **视角** | 单个包内部的推理逻辑 | 全局知识网络 |
| **产出** | review PR（claim priors + chain strategies + findings） | belief snapshots + research tasks + curation 包 |
| **与 Registry 的交互** | 提交并维护 review PR | 读取已注册包 / accepted reviews；注册 curation 包 |
| **与 LKM Repo 的交互** | — | 各自维护 LKM Repo，发布 research tasks，调查、确认、close |
| **权限** | 无特权 | 无特权 |

两者互补：Review Server 保证每个包版本进入官方流程时有 prior / strategy 和清晰的 finding；LKM 保证全局知识网络有持续的发现、调查和 belief 发布。

## 相关文档

- [02-decentralized-architecture.md](02-decentralized-architecture.md) — 架构总纲，LKM Repo 的定义和参与者交互
- [04-registry-operations.md](04-registry-operations.md) — 注册流程、官方 review 协调、relation report issue
- [06-belief-flow-and-quality.md](06-belief-flow-and-quality.md) — belief snapshots、全局推理、错误修正场景中 curation 包的具体影响
- [03-authoring-and-publishing.md](03-authoring-and-publishing.md) — 作者视角：本地预览、请求 registry、浏览研究机会
