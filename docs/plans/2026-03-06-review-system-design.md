# Gaia Review System 设计文档

| 属性 | 值 |
|------|---|
| 日期 | 2026-03-06 |
| 状态 | Draft |
| 关联 | `docs/plans/2026-03-05-gaia-cli-design-v3.md` Section 7 |

---

## 1. 目标

为 Gaia 知识图谱中的每条推理链（claim）提供可量化的质量评估。

**核心输出：** 条件概率 **P(conclusion | premises)** — 假设所有强引用（`cite`）都成立，这步推理有多可靠。

**设计原则：**
- **透明** — Review 的 prompt（skill）公开、版本化，任何人可审查
- **可复现** — 同样的 (input, skill, model) 应产生统计上一致的结果
- **发布与评审分离** — 发布者不能审自己的稿，解决激励冲突
- **渐进式** — MVP 从 Server 自动评审开始，未来扩展到社区评审

---

## 2. 强引用与弱引用模型

Review 的前提是区分两种引用关系：

### 2.1 强引用（`cite`）

**定义：** 如果这个 premise 是错的，conclusion 一定不成立。

```yaml
cite: [6006, 6007]    # 等效原理依赖 Eötvös 实验 + 电梯思想实验
```

- 数学处理：建模为 hyperedge tail，参与 BP 传播
- P(C | A_cite=false) ≈ 0

### 2.2 弱引用（`context`）

**定义：** 提供背景支持，但即使错了，conclusion 仍可能通过其他路径成立。

```yaml
context: [6003]        # Maxwell 方程作为背景，但 GR 从几何推导光弯曲
```

- 数学处理：贡献折入 claim 的 prior，不建 edge，不参与 BP
- P(C | A_context=false) > 0

### 2.3 判断标准

> 如果这个 premise 是错的，conclusion 还能成立吗？
> - **不能** → `cite`（强引用）
> - **能** → `context`（弱引用）
> - **完全无关** → 删除

用户负责声明强弱，Reviewer 负责验证并可能调整（降级/升级）。

---

## 3. Review Skill 协议

### 3.1 Skill 定义

Review skill 是一个版本化的 prompt 文件，定义了标准化的评审流程。

```
review-skills/
├── claim-review-v1.0.md           # 评估单条推理链
├── claim-review-v1.1.md           # 迭代改进
└── ...
```

### 3.2 输入格式

```yaml
claim:
  id: 5007
  content: "同一物体不可能既比 H 快又比 H 慢 — 矛盾"
  type: deduction
  why: "两个有效推导从同一前提得出互相矛盾的结论"
premises:                              # cite[] 展开为完整内容
  - id: 5005
    content: "推导 A: 轻球拖拽重球 → 组合体 HL 比 H 慢"
  - id: 5006
    content: "推导 B: 组合体更重 → 组合体 HL 比 H 快"
context:                               # context[] 展开
  - id: ...
    content: "..."
```

### 3.3 输出格式

```yaml
score: 0.95                            # P(conclusion | premises)
justification: "纯逻辑演绎，前提给出互斥结论，矛盾直接成立，无跳步"
confirmed_cites: [5005, 5006]          # 确认的强引用
downgraded_cites: []                   # 应降级为 context
upgraded_context: []                   # 应升级为 cite
irrelevant: []                         # 建议删除
missing_premises: []                   # 推理隐含依赖但未声明的前提
```

### 3.4 评估标准

Review skill 按以下维度评估：

**1. 强引用验证**

逐个检查 `cite[]` 中的每个 premise：如果这个 premise 是错的，conclusion 还能成立吗？
- 不能 → 确认为强引用（`confirmed_cites`）
- 能 → 降级为弱引用（`downgraded_cites`）

**2. 逻辑有效性**

剥离强引用后，假设所有 `confirmed_cites` 都为真，评估 `why` 中的推理过程：
- 推理是否有效？
- 有无逻辑跳步？
- 是否依赖未声明的隐含前提？（`missing_premises`）

**3. 充分性**

`confirmed_cites` 是否足够支撑 conclusion？是否需要额外前提？

**4. 推理类型匹配**

声称的 `type`（deduction, induction, analogy...）是否与实际推理方式一致？

### 3.5 打分参考

| 区间 | 含义 | 典型场景 |
|------|------|---------|
| 0.95-1.0 | 纯逻辑演绎，无跳步 | 数学证明、逻辑矛盾推导 |
| 0.80-0.95 | 推理可靠，有微小隐含假设 | 物理定律推导 |
| 0.50-0.80 | 推理合理但有明显跳步 | 跨领域类比 |
| 0.20-0.50 | 推理较弱，结论仅部分被支持 | 弱归纳、不完全类比 |
| 0.00-0.20 | 推理无效或结论与前提无关 | 逻辑谬误 |

### 3.6 Claim Review Skill v1.0 Prompt

```markdown
你是一个科学推理评审员。你的任务是评估一条推理链的可靠性。

## 任务

给定一个 conclusion（结论）、若干 premises（前提）、context（背景）和 why（推理过程），
评估：**假设所有 premises 都成立，从 premises 到 conclusion 的推理有多可靠？**

## 步骤

### Step 1: 验证强引用
逐个检查 premises 中的每一条：
- 问自己："如果这条 premise 是错的，conclusion 还能成立吗？"
- 不能 → 确认为强引用（confirmed_cites）
- 能 → 降级为弱引用（downgraded_cites）

### Step 2: 评估推理链
假设所有 confirmed_cites 都为真：
1. why 中的推理是否逻辑有效？有无跳步？
2. premises 是否充分？是否缺少隐含前提？（列入 missing_premises）
3. 声称的推理类型是否匹配实际推理方式？

### Step 3: 打分
给出 P(conclusion | confirmed premises) 的条件概率：
- 0.95-1.0: 纯逻辑演绎，无跳步
- 0.80-0.95: 推理可靠，有微小隐含假设
- 0.50-0.80: 推理合理但有明显跳步或依赖未声明假设
- 0.20-0.50: 推理较弱，结论仅部分被前提支持
- 0.00-0.20: 推理无效或结论与前提无关

## 输出格式

只输出以下 YAML，不要其他内容：

```yaml
score: <float>
justification: "<一句话说明打分理由>"
confirmed_cites: [<ids>]
downgraded_cites: [<ids>]
upgraded_context: [<ids>]
irrelevant: [<ids>]
missing_premises: ["<description>", ...]
```
```

---

## 4. Review 流程

### 4.1 三种执行场景

```
┌─────────────────────────────────────────────────────────────┐
│                    Review 执行场景                            │
├──────────────┬────────────────────┬─────────────────────────┤
│  本地 Review  │  Server 直连 Review │  GitHub Bot Review      │
│              │                    │                         │
│  用户自选模型  │  Server 控制模型    │  Server 控制模型         │
│  gaia build  │  gaia publish      │  PR → webhook → Server  │
│   --review   │                    │   → PR comment          │
│              │                    │                         │
│  自用，可信   │  权威，可信        │  公开，可信              │
│  不上报      │  存入 Server DB    │  存入 Server DB          │
│              │                    │  + GitHub PR 评论        │
└──────────────┴────────────────────┴─────────────────────────┘
```

### 4.2 本地 Review

```bash
$ gaia build --review
  Reviewing 20 claims with local model...

  | Claim | Score | Issue |
  |-------|-------|-------|
  | 5005 "推导A" | 0.95 | — |
  | 5006 "推导B" | 0.95 | — |
  | 5007 "矛盾" | 0.92 | — |
  | 5012 "真空等速" | 0.78 | cite 5009 → downgrade to context |

  BP results (with review scores):
    5003 (v∝W): 0.70 → 0.05 ↓
    5012 (真空等速): 0.95 ↑
```

- 用户自选模型（通过 `~/.gaia/config.toml` 配置）
- 结果仅供本地 BP 使用，不上报
- 适合 Agent 快速探索

### 4.3 Server 直连 Review

```bash
$ gaia publish
  Pushing galileo_tied_balls v1.0.0...
  → Server reviewing with claude-opus-4-6::claim-review-v1.0
  → Review complete. Results:
    Overall: ✓ Pass (avg 0.91)
    2 cites downgraded to context
    1 missing premise suggested
```

- Server 用自己控制的模型和 skill 版本
- Review 结果存入 Server 数据库，作为 hyperedge probability
- 对用户透明：可查看每条 claim 的 review 详情

### 4.4 GitHub Bot Review

```
用户: git push → PR 到 registry repo
                    ↓
Server: webhook 触发
  → clone 包
  → 用 Server 模型跑 review skill
  → 在 PR 下发表评论:

    ┌────────────────────────────────────────────┐
    │ 🤖 Gaia Review Bot                         │
    │                                            │
    │ Package: galileo_tied_balls v1.0.0         │
    │ Reviewer: claude-opus-4-6                  │
    │ Skill: claim-review-v1.0                   │
    │                                            │
    │ | Claim | Score | Issue |                  │
    │ |-------|-------|-------|                   │
    │ | 5005 "推导A" | 0.95 | — |               │
    │ | 5006 "推导B" | 0.95 | — |               │
    │ | 5007 "矛盾"  | 0.92 | — |               │
    │ | 5012 "真空等速"| 0.78 | ⚠ cite 5009     │
    │ |       | → downgrade to context |         │
    │ |                                          │
    │ | Overall: ✓ Pass (avg 0.90)               │
    │ |                                          │
    │ | Auto-merging into registry...            │
    └────────────────────────────────────────────┘
```

**关键：发布与评审分离。**
- GitHub = 发布平台（类似 arXiv，谁都可以发）
- Server = 独立审稿方（类似期刊，给出质量评价）
- 用户没有动机也没有机会篡改 review 结果

---

## 5. Review 记录数据结构

面向未来的完整 review 记录，预留社区评审扩展字段：

```yaml
review:
  # 评审对象
  target:
    package: "galileo_tied_balls"
    claim_id: 5007
    commit: "a1b2c3d4"

  # 评审结果
  result:
    score: 0.92
    justification: "纯逻辑演绎，无跳步"
    confirmed_cites: [5005, 5006]
    downgraded_cites: []
    upgraded_context: []
    irrelevant: []
    missing_premises: []

  # 来源证明（可审计）
  provenance:
    method: "server"               # "server" | "api" | "self-hosted"
    model: "claude-opus-4-6"
    skill: "claim-review-v1.0"
    api_request_id: "req_abc123"   # API 调用 ID，可审计
    timestamp: "2026-03-06T10:30:00Z"

  # Reviewer 身份（未来扩展）
  identity:
    id: "gaia-server-official"
    type: "server"                 # "server" | "github" | "api-key" | "anonymous"

  # 校准信息（Server 计算，非 reviewer 提交）
  calibration:
    score: 0.85                    # 历史校准分
    reviews_count: 142
    domain_scores:
      physics: 0.90
      biology: 0.72
```

**MVP 阶段：** 只实现 `target` + `result` + `provenance`（method="server"）。`identity` 和 `calibration` 字段预留，未来开放社区评审时启用。

---

## 6. 社区激励机制

### 6.1 用户激励

```
用 gaia 格式上传到 GitHub
  → 自动获得免费 AI peer review
  → Review 结果公开，增加可信度
  → 被 Server 索引，进入全局知识图谱
  → 被更多人 cite，扩大影响力
```

格式本身是入场券 — 不用 gaia 格式就没有 review，没有被索引。

| 用户得到 | Gaia 生态得到 |
|---------|-------------|
| 免费 AI review | 更多结构化知识 |
| 公开可信度背书 | 更大的知识图谱 |
| 被全局引用的机会 | 更多跨包引用和矛盾发现 |

### 6.2 Review 质量生态

Review skill 本身是开源的：

- **任何人可以 fork 改进** — 提交 PR 到 review-skills repo
- **领域特化** — 物理学 review skill、生物学 review skill
- **竞争改进** — 不同 skill 的校准分数公开可比较
- **Open peer review** — 所有 review 结果公开在 GitHub PR 中

---

## 7. Reviewer 校准体系（未来扩展）

> MVP 不实现，但数据结构预留。

### 7.1 Reviewer ID

```
reviewer_id = model + skill_version
例: claude-opus-4-6::claim-review-v1.0
例: gpt-4o::claim-review-v1.0
例: llama-3-70b::claim-review-v1.2
```

### 7.2 校准信号

| 信号 | 说明 |
|------|------|
| **事后验证** | Reviewer 给了 0.9，后来被强证据推翻 → 校准偏高 |
| **Reviewer 间一致性** | 与其他高校准 reviewer 的偏差 |
| **领域表现** | 同一 reviewer 在不同领域的准确度差异 |
| **BP 一致性** | Review score 与全局 BP 结果是否矛盾 |

### 7.3 聚合机制

当同一 claim 有多个 review 时：

```
final_score = Σ(score_i × calibration_i) / Σ(calibration_i)
```

低校准 reviewer 的分数权重自动降低。

### 7.4 冷启动

新 reviewer 处理方式：
1. 给予默认权重（如 0.3）
2. 跑标准 benchmark 测试集（已知答案的 claims）
3. 根据 benchmark 表现给初始校准分
4. 之后随着更多 review 持续更新

### 7.5 可复现验证

```
挑战机制:
  任何人可以用同样的 (model, skill, input) 重跑 review
  如果结果统计上显著不同 → reviewer 信誉扣分
```

LLM 输出有随机性，但同一 (model, skill) 在同一输入上的分数分布应该稳定。

### 7.6 可信执行验证

| 方式 | 可信度 | 说明 |
|------|--------|------|
| **Server 执行** | 最高 | Server 控制全流程 |
| **API 调用证明** | 高 | API provider 签发 request_id，可审计 |
| **自报** | 低 | 靠校准因子淘汰 |

---

## 8. 实现路线

### Phase 1: MVP — Server 自动评审

- 实现 claim-review-v1.0 skill prompt
- Server 端 review 流程（同步/异步）
- Review 结果存储
- `gaia build --review` 本地评审
- GitHub webhook + bot 评论

### Phase 2: 多模型支持

- 支持配置不同模型跑同一 skill
- 多 review 结果存储和展示
- 基础聚合（取平均/中位数）

### Phase 3: 校准体系

- Benchmark 测试集构建
- 校准分数计算
- 加权聚合
- 公开校准排行榜

### Phase 4: 社区评审

- 开放第三方 reviewer 注册
- 可复现验证机制
- 领域特化 review skill
- 去中心化 review 网络
