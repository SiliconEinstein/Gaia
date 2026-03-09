# Gaia Review System 设计文档

| 属性 | 值 |
|------|---|
| 日期 | 2026-03-06 |
| 状态 | Draft |
| 关联 | `docs/plans/2026-03-05-gaia-cli-design-v3.md` Section 7 |

---

## 1. 目标

为 Gaia 知识图谱中的每条推理链（claim）提供可量化的质量评估。

**核心输出：** 条件概率 **P(conclusion | premises)** — 假设所有强引用（`premise`）都成立，这步推理有多可靠。

**设计原则：**
- **透明** — Review 的 prompt（skill）公开、版本化，任何人可审查
- **可复现** — 同样的 (input, skill, model) 应产生统计上一致的结果
- **发布与评审分离** — GitHub 发布时，Server 独立评审，用户无法篡改

---

## 2. 强引用与弱引用模型

Review 的前提是区分两种引用关系：

### 2.1 强引用（`premise`）

**定义：** 如果这个 premise 是错的，conclusion 一定不成立。

```yaml
premise: [6006, 6007]    # 等效原理依赖 Eötvös 实验 + 电梯思想实验
```

- 数学处理：建模为 hyperedge tail，参与 BP 传播
- P(C | A_premise=false) ≈ 0

### 2.2 弱引用（`context`）

**定义：** 提供背景支持，但即使错了，conclusion 仍可能通过其他路径成立。

```yaml
context: [6003]        # Maxwell 方程作为背景，但 GR 从几何推导光弯曲
```

- 数学处理：贡献折入 claim 的 prior，不建 edge，不参与 BP
- P(C | A_context=false) > 0

### 2.3 判断标准

> 如果这个 premise 是错的，conclusion 还能成立吗？
> - **不能** → `premise`（强引用）
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
  premise:                             # 强引用，展开为完整内容
    - id: 5005
      content: "推导 A: 轻球拖拽重球 → 组合体 HL 比 H 慢"
    - id: 5006
      content: "推导 B: 组合体更重 → 组合体 HL 比 H 快"
  context:                             # 弱引用（本例无）
    []
```

### 3.3 输出格式

```yaml
score: 0.95                            # P(conclusion | premises)
justification: "纯逻辑演绎，前提给出互斥结论，矛盾直接成立，无跳步"
confirmed_premises: [5005, 5006]       # 确认的强引用
downgraded_premises: []                # 应降级为 context
upgraded_context: []                   # 应升级为 premise
irrelevant: []                         # 建议删除
suggested_premise: []                  # 从 why 中提取的隐含强依赖
suggested_context: []                  # 可能相关的引文，建议作为弱引用
```

### 3.4 评估标准

Review skill 按以下维度评估：

**1. 强引用验证**

逐个检查 `premise[]` 中的每个 premise：如果这个 premise 是错的，conclusion 还能成立吗？
- 不能 → 确认为强引用（`confirmed_premises`）
- 能 → 降级为弱引用（`downgraded_premises`）

**2. 逻辑有效性**

剥离强引用后，假设所有 `confirmed_premises` 都为真，评估 `why` 中的推理过程：
- 推理是否有效？
- 有无逻辑跳步？
- 是否依赖未声明的隐含前提？（如有，降低 score）

**3. 充分性**

`confirmed_premises` 是否足够支撑 conclusion？是否需要额外前提？

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
- 不能 → 确认为强引用（confirmed_premises）
- 能 → 降级为弱引用（downgraded_premises）

### Step 2: 评估推理链
假设所有 confirmed_premises 都为真：
1. why 中的推理是否逻辑有效？有无跳步？
2. premises 是否充分？是否缺少隐含前提？（如有，降低 score）
3. 声称的推理类型是否匹配实际推理方式？

### Step 3: 提取隐含假设
从 why 中找出未声明的假设，按强弱分类：
- `suggested_premise`: 推理强依赖的条件（错了结论不成立），显著影响 score
- `suggested_context`: 可能相关的引文，建议作为弱引用补充

### Step 4: 打分
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
confirmed_premises: [<ids>]
downgraded_premises: [<ids>]
upgraded_context: [<ids>]
irrelevant: [<ids>]
suggested_premise: ["<隐含强依赖描述>", ...]
suggested_context: ["<可能相关的引文描述>", ...]
```
```

---

## 4. Review 流程

### 4.1 三种执行场景

| 场景 | 触发方式 | 执行者 | 结果存储 |
|------|---------|--------|---------|
| **本地 Review** | `gaia review [id...]` | 用户自选模型 | 仅本地，用于本地 BP |
| **GitHub 模式** | PR 到 registry repo | Server（webhook 触发） | Server DB + GitHub PR 评论 |
| **Server 直连** | `gaia publish` | Server | Server DB |

三种场景的共同点：都使用同一套 review skill 协议。区别在于谁执行、结果存哪里。

`gaia review` 与 `gaia build` 职责分离：
- `build` — 快速、离线：结构校验 + 本地 BP（秒级）
- `review` — 慢、需 API key：调大模型评审推理质量（分钟级）

### 4.2 本地 Review

```bash
$ gaia review
  Reviewing 20 claims with local model (concurrency: 5)...

  | Claim | Score | Issue |
  |-------|-------|-------|
  | 5005 "推导A" | 0.95 | — |
  | 5006 "推导B" | 0.95 | — |
  | 5007 "矛盾" | 0.92 | — |
  | 5012 "真空等速" | 0.78 | premise 5009 → downgrade to context |

  BP results (with review scores):
    5003 (v∝W): 0.70 → 0.05 ↓
    5012 (真空等速): 0.95 ↑
```

```bash
# 也可以指定 claim ID
$ gaia review 5007
  [1/1] 5007 "矛盾" → 0.92 ✓

$ gaia review 5005 5006 5007
  [1/3] 5005 "推导A" → 0.95 ✓
  [2/3] 5006 "推导B" → 0.95 ✓
  [3/3] 5007 "矛盾"  → 0.92 ✓
```

- 用户自选模型（通过 `~/.gaia/config.toml` 配置）
- 内部并发调 API（默认 concurrency=5），逐条流式输出
- Review score 作为本地 BP 的 hyperedge probability
- 结果仅供本地使用，不上报 Server
- 适合 Agent 写完几条 claim 后立即 review

### 4.3 Server 直连 Review

```bash
$ gaia publish
  Pushing galileo_tied_balls v1.0.0...
  → Server reviewing with claude-opus-4-6::claim-review-v1.0
  → Review complete. Results:
    Overall: ✓ Pass (avg 0.91)
    2 premises downgraded to context
    1 suggested_premise extracted from reasoning
```

- Server 用自己控制的模型和 skill 版本
- Review score 存入 Server DB，作为全局 BP 的 hyperedge probability
- 用户可查看每条 claim 的 review 详情

### 4.4 GitHub Bot Review

**流程：**

```
用户: git push → PR 到 registry repo
                    ↓
Server: webhook 触发
  → clone 包
  → 用 Server 模型跑 review skill
  → 在 PR 下发表评论
  → 通过 → auto-merge；不通过 → request changes
```

**GitHub PR 评论示例：**

```
🤖 Gaia Review Bot

Package: galileo_tied_balls v1.0.0
Reviewer: claude-opus-4-6
Skill: claim-review-v1.0

| Claim | Score | Issue |
|-------|-------|-------|
| 5005 "推导A: HL更慢" | 0.95 | — |
| 5006 "推导B: HL更快" | 0.95 | — |
| 5007 "矛盾" | 0.92 | — |
| 5012 "真空等速" | 0.78 | ⚠ premise 5009 建议降级为 context |

Overall: ✓ Pass (avg 0.90)

Auto-merging into registry...
```

**关键设计：发布与评审分离。**
- GitHub = 发布平台（类似 arXiv，谁都可以发布 claims）
- Server = 独立审稿方（类似期刊，给出质量评价）
- 用户没有动机也没有机会篡改 review 结果
- 所有 review 过程公开在 GitHub PR 评论中（open peer review）

---

## 5. Review 记录数据结构

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
    confirmed_premises: [5005, 5006]
    downgraded_premises: []
    upgraded_context: []
    irrelevant: []
    suggested_premise: []
    suggested_context: []

  # 来源证明
  provenance:
    method: "server"               # "server" | "local"
    model: "claude-opus-4-6"
    skill: "claim-review-v1.0"
    timestamp: "2026-03-06T10:30:00Z"
```

---

## 6. 用户激励

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

---

## 7. Review Skill 演进

Review skill 本身是版本化的 prompt，可以持续迭代改进：

- **v1.0** — 基础版：强引用验证 + 逻辑有效性 + 打分
- **v1.1+** — 根据实际使用反馈调整评估标准和打分区间
- **领域特化** — 未来可能出现物理学、生物学等领域特化的 review skill
- **多模型对比** — Server 可以用多个模型跑同一 skill，取共识结果

Skill 的改进由 Gaia 团队维护，版本化管理，每次更新有明确的 changelog。

---

## 8. 实现路线

### Phase 1: MVP

- 实现 claim-review-v1.0 skill prompt
- `gaia review [id...]` 本地评审（用户配置模型）
- Server 端 review 流程（`gaia publish` 触发）
- Review 结果存储
- GitHub webhook + bot PR 评论

### Phase 2: 改进

- 根据实际使用调优 skill prompt 和打分区间
- Server 支持多模型 review（取共识）
- Review 结果与 BP 集成优化
