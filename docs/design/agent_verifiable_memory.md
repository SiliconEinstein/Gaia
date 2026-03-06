# Gaia 作为 Agent Verifiable Memory 系统

| 文档属性 | 值 |
|---------|---|
| 版本 | 1.0 |
| 日期 | 2026-03-04 |
| 关联文档 | [phase1_billion_scale.md](phase1_billion_scale.md), [scaling_belief_propagation.md](scaling_belief_propagation.md) §2, [theoretical_foundations.md](theoretical_foundations.md), [version_dependency_environment.md](version_dependency_environment.md) |
| 状态 | Wishlist |

---

## 目录

1. [动机：Agentic Science 需要 Verification](#1-动机agentic-science-需要-verification)
2. [现有 Agent Memory 方案的不足](#2-现有-agent-memory-方案的不足)
3. [Gaia 的天然适配性](#3-gaia-的天然适配性)
4. [逐步验证协议](#4-逐步验证协议)
5. [架构边界：裁判而非教练](#5-架构边界裁判而非教练)
6. [新增 API 设计](#6-新增-api-设计)
7. [与现有管线的集成](#7-与现有管线的集成)
8. [定位与产品化方向](#8-定位与产品化方向)
9. [与其他设计的关系](#9-与其他设计的关系)

---

## 1. 动机：Agentic Science 需要 Verification

AI Agent 做科学研究（agentic science）时，会执行一长串推理步骤：阅读论文 → 提取事实 → 跨论文推理 → 归纳泛化 → 提出假设。每一步都可能出错——幻觉、逻辑跳跃、无根据的泛化。

核心问题：**如何验证 agent 推理过程中的每一步，而非仅验证最终结论？**

仅验证最终结论的危害：

```
agent 推理链：
  step 1: "论文A说材料X超导"                    (正确)
  step 2: "论文B说材料Y超导"                    (正确)
  step 3: "所以所有类似材料都超导"               (归纳跳跃，概率应很低)
  step 4: "基于 step 3，材料Z也超导"             (建立在有问题的 step 3 上)
  step 5: "材料Z的超导温度约为 300K"             (幻觉)

最终结论看起来言之凿凿，但推理链中间 3 步有问题。
仅检查最终结论无法发现 step 3 是错误的源头。
```

---

## 2. 现有 Agent Memory 方案的不足

| 方案 | 存储 | 验证 | 溯源 | 矛盾处理 | 一致性 |
|------|------|------|------|---------|--------|
| **LLM Context Window** | token 序列 | 无 | 无法溯源 | 用最新的覆盖 | 无 |
| **向量数据库 (RAG)** | 文本 chunk + embedding | 无 | 能找到来源文档 | 新旧共存，无冲突检测 | 无 |
| **传统知识图谱** | 实体-关系三元组 | 无概率，存即为真 | 可选的元数据 | 视为错误 | 无概率推理 |
| **Gaia** | 命题 + 推理链 + 概率 | **每步 commit 审核 + BP 一致性检查** | **完整推理链溯源** | **contradiction 边 + BP 竞争** | **全局信念传播** |

核心差距：现有方案都缺乏 **过程验证 (process verification)**。RAG 让 agent 有了记忆，但无法验证记忆的推理过程是否正确。

---

## 3. Gaia 的天然适配性

### 3.1 Commit Workflow = Step-by-Step Verification Protocol

Gaia 的 commit → review → merge 工作流天然就是一个逐步验证协议：

```
Agent 的推理步骤                      Gaia 的验证机制
──────────────                        ──────────────
"我读了论文X，它说Y"                   → AddEdge (paper-extract)
                                        submit: 结构校验
                                        review: LLM 检查提取质量
                                        merge: 入图

"从Y和Z，我推出W"                      → AddEdge (join/induction)
                                        submit: 结构校验
                                        review: LLM 验证逻辑蕴含
                                              (tightness, substantiveness 评分)
                                        merge: 入图 + BP 更新所有 belief

"W与已知命题Q矛盾"                     → AddEdge (contradiction)
                                        merge: BP 自动竞争
                                        → 证据弱的一方 belief 下降

"综合所有证据，假设H可信度 0.73"        → BP 自动计算，无需 agent 手动评估
```

每一步经过独立验证后，才成为后续推理的基础。这是 **verified chain of thought**——推理链中的每个环节都被独立审计。

### 3.2 Belief 值作为推理引导信号

Gaia 不只是被动验证——它通过 belief 值**主动引导** agent 的推理方向：

```
有 Gaia 验证的 agent：

  step 1: commit → merge → belief(X超导) = 0.85          ✓ 高可信
  step 2: commit → merge → belief(Y超导) = 0.80          ✓ 高可信
  step 3: commit → review 发现归纳跳跃 → probability 压低
          → merge → belief(所有类似材料超导) = 0.24       ⚠️ 低可信
  step 4: agent 查到 step 3 的 belief 只有 0.24
          → 决定不在此基础上继续，转而寻找更多证据         ← 自我修正
```

低 belief 阻止 agent 在脆弱的中间步骤上继续构建；高 belief 鼓励 agent 深入。这形成了一个**闭环**：agent 推理 → Gaia 验证 → belief 反馈 → agent 调整方向。

### 3.3 可审计的推理链

Gaia 的每个 belief 值都可以追溯到完整的推理路径：

```
belief(H) = 0.73
  ├── 支持: edge 101 (paper-extract, prob=0.9, 贡献 +0.35)
  │         来自 tail: [Node 1 (belief=0.85), Node 2 (belief=0.80)]
  ├── 支持: edge 205 (induction, prob=0.6, 贡献 +0.12)
  │         来自 tail: [Node 15 (belief=0.73)]
  └── 反对: edge 310 (contradiction, prob=0.7, 贡献 -0.14)
            来自 source: Node 22 (belief=0.45)
```

这是 RAG 做不到的——RAG 只能说"我找到了这个文档"，Gaia 能说"基于 3 条支持证据和 1 条反对证据，经过信念传播，可信度从 prior=0.5 更新到 belief=0.73"。

### 3.4 60 亿可解释参数的统计模型视角

从 [scaling_belief_propagation.md](scaling_belief_propagation.md) §2 建立的框架看：Gaia 是一个 60 亿参数的可解释统计模型。每个参数都有语义标签（某个具体推理步骤的可靠性，或某个具体命题的先验可信度）。

对 agent 来说，这意味着：
- **LLM 的记忆**（权重里的隐式知识）不可审计
- **Gaia 的记忆**（图中的显式知识）每一个 bit 都可审计

Agent 把推理过程写入 Gaia，就是把黑盒推理转化为白盒推理。

---

## 4. 逐步验证协议

### 4.1 基本流程

```
Agent                                    Gaia
  │                                        │
  │  1. 查询已有知识                        │
  ├──→ GET /nodes?keywords=...  ──────────→│
  │←── 返回相关命题 + belief 值  ←──────────┤
  │                                        │
  │  2. 草稿推理（agent 本地）              │
  │    "从 A + B 可以推出 C"                │
  │                                        │
  │  3. Dry-run 验证                        │
  ├──→ POST /verify/dry-run  ─────────────→│
  │    {tail: [A,B], head: [C]}            │ 检查一致性、去重、预估 belief
  │←── 返回验证结果  ←────────────────────┤
  │                                        │
  │  4. 判断是否值得正式提交                 │
  │    (belief 预估够高? 无矛盾?)           │
  │                                        │
  │  5. 正式提交                            │
  ├──→ POST /commits  ───────────────────→│
  │←── commit_id  ←──────────────────────┤
  │                                        │
  │  6. 等待审核 + 合并                      │
  ├──→ POST /commits/{id}/review  ────────→│ LLM 深度审核
  ├──→ POST /commits/{id}/merge  ─────────→│ 入图 + BP
  │←── 返回受影响节点的新 belief 值  ←──────┤
  │                                        │
  │  7. 根据 belief 决定下一步               │
  │    belief > threshold → 继续推理        │
  │    belief < threshold → 回溯或找证据    │
```

### 4.2 Confidence-Gated Progression（置信度门控）

Agent 的下一步推理应该依赖于前一步的 belief 值：

```python
# agent 端伪代码
async def verified_reasoning_step(agent, gaia, step):
    # 1. dry-run 检查
    check = await gaia.verify_dry_run(step.operations)
    if check.has_contradiction:
        return agent.handle_contradiction(check)
    if check.estimated_belief < agent.min_threshold:
        return agent.seek_more_evidence(step)

    # 2. 正式提交
    commit = await gaia.submit(step.operations)
    review = await gaia.review(commit.id)
    if not review.approved:
        return agent.revise_step(step, review.issues)

    # 3. merge 并获取 belief
    result = await gaia.merge(commit.id)
    belief = result.affected_beliefs[step.head_node_id]

    # 4. belief 门控
    if belief >= agent.confidence_threshold:
        return agent.proceed(step, belief)  # 继续下一步
    else:
        return agent.backtrack(step, belief)  # 回溯
```

### 4.3 多 Agent 协作验证

多个 agent 同时做研究时，Gaia 自然成为共享的验证基础设施：

```
Agent A (研究超导)              Agent B (研究晶体结构)
    │                              │
    ├── commit: "材料X超导"         │
    │   → merge, belief=0.8        │
    │                              ├── commit: "材料X晶体结构不支持超导"
    │                              │   → merge, 自动创建 contradiction 边
    │                              │   → BP 重算: belief(X超导) 降到 0.45
    │                              │
    ├── 查询: belief(X超导)=0.45   │
    │   → 发现 Agent B 的反对证据   │
    │   → 决定重新审视自己的推理     │
```

Agent 之间不需要直接通信——通过 Gaia 的图和 BP，一个 agent 的发现自动影响所有相关 agent 的推理基础。这是通过**共享参数化模型**实现的隐式协作。

---

## 5. 架构边界：裁判而非教练

### 5.1 核心原则

**Gaia 是裁判，不是教练。** 裁判判定每一步是否合规，但不帮选手规划战术。

```
Gaia 的职责                          不是 Gaia 的职责
──────────                            ──────────────
存储已验证的知识                       管理 agent 的思考过程
验证提交的推理步骤                     帮 agent 决定下一步怎么推理
提供 belief 查询                      提供 workspace 存储
提供 dry-run 一致性检查                管理 agent 的草稿版本
提供信念溯源报告                      跟踪 agent 探索了哪些路径
```

### 5.2 为什么 Workspace 不应该在 Gaia 内

Agent 在正式提交前的探索性思考（workspace）应由 agent 自己管理，不应进入 Gaia。原因：

**语义污染**：Gaia 的核心承诺是"图里的每个命题都经过了 commit → review → merge"。如果草稿也存在图里（即使标记为 draft），这个承诺被稀释。所有查询、BP 计算、API 都需要过滤 draft 状态——增加复杂度，降低信任。

**参数污染**：从统计模型视角（[scaling_belief_propagation.md](scaling_belief_propagation.md) §2），Gaia 的参数（prior, probability）代表已验证的知识。Workspace 草稿不是模型参数，而是对模型的假设性查询。查询不应存入模型。

**规模问题**：1000 个 agent 同时工作，每个每分钟探索 10 条推理路径，90% 最终被丢弃。草稿写入量是正式知识的几十倍，且绝大部分是垃圾。

**类比 Cargo/uv**：[version_dependency_environment.md](version_dependency_environment.md) §4 提出了统一环境模型——agent 的本地 workspace 本身就是一个 Gaia environment（类似 Cargo 本地 project 面向 crates.io registry 工作）。Agent 在本地 Gaia 环境中自由推理和实验，成果通过 `gaia submit` 提交到 Gaia Server。"裁判而非教练"原则仍然成立：**Gaia Server 是裁判**（验证、审核、维护共享知识一致性），**本地 workspace（environment）是 agent 自由工作的场所**。Gaia 不管理 agent 的思考过程，但 agent 的工作空间本身就是一个完整的 Gaia 环境，拥有本地 BP、thought experiment 等能力。

```
Cargo 类比：
  crates.io (registry) = 已发布的包     ←→  Gaia Server  = 已验证的知识
  本地 Cargo project   = 开发者工作区   ←→  Local Gaia workspace = agent 的工作环境
  cargo publish        = 发布到 registry ←→  gaia submit  = 提交到 server review
  cargo test (本地)    = 本地验证        ←→  dry-run API  = 在环境中的预验证

  Cargo 不管理 IDE，但本地 project 本身就是完整的 Cargo 环境。
  Gaia 不管理 agent 的思考过程，但本地 workspace 本身就是完整的 Gaia 环境。
```

---

## 6. 新增 API 设计

### 6.1 `/verify/dry-run` — 假设性验证（只读）

Agent 提交一组假设性操作，Gaia 返回验证结果但不写入。

```
POST /verify/dry-run

Request:
{
    "operations": [
        {
            "type": "add_edge",
            "tail": [{"ref": 101}, {"ref": 102}],
            "head": [{"new": {"content": "合金AB具有Z性质", "prior": 0.8}}],
            "edge_type": "induction",
            "probability": 0.7,
            "reasoning": ["从材料A和材料B的性质归纳"]
        }
    ]
}

Response:
{
    "consistency": {
        "status": "no_contradiction",     // 或 "contradicts_nodes": [42, 67]
        "details": "与已有知识无直接矛盾"
    },
    "dedup": {
        "similar_existing": [
            {"node_id": 55, "similarity": 0.92, "content": "合金AB具有Z特性",
             "belief": 0.71}
        ]
    },
    "tail_status": {
        "101": {"belief": 0.85, "status": "active"},
        "102": {"belief": 0.72, "status": "active"}
    },
    "estimated_belief": 0.67,             // 如果 merge，head 节点的 belief 预估
    "review_hint": "induction 类型边的 probability=0.7 较高，review 可能要求降低"
}
```

**实现方式**：复用现有 `DedupChecker` + `NNSearchOperator` + 局部 BP 模拟，不执行任何写入。

### 6.2 `/explain/belief/{node_id}` — 信念溯源报告

返回某个节点的 belief 值的完整解释：为什么是这个值，哪些证据支持，哪些反对。

```
GET /explain/belief/42

Response:
{
    "node_id": 42,
    "content": "合金AB具有Z性质",
    "belief": 0.73,
    "prior": 0.5,
    "supporting_edges": [
        {
            "edge_id": 101,
            "type": "paper-extract",
            "probability": 0.9,
            "tail_beliefs": [0.85, 0.80],
            "contribution": +0.35,
            "source": "论文 DOI:10.1234/..."
        },
        {
            "edge_id": 205,
            "type": "induction",
            "probability": 0.6,
            "tail_beliefs": [0.73],
            "contribution": +0.12
        }
    ],
    "opposing_edges": [
        {
            "edge_id": 310,
            "type": "contradiction",
            "probability": 0.7,
            "source_node_id": 22,
            "source_belief": 0.45,
            "contribution": -0.14
        }
    ],
    "reasoning_chain_depth": 3,
    "provenance_summary": "基于 2 条支持证据和 1 条反对证据，经 2 轮 BP 传播，belief 从 prior=0.5 更新到 0.73"
}
```

### 6.3 Merge 返回值增强

当前 merge 只返回 commit 状态。增强后应返回受影响节点的 belief 变化，供 agent 做门控决策：

```
POST /commits/{id}/merge

Response (增强):
{
    "commit_id": "...",
    "status": "merged",
    "affected_beliefs": {
        "42": {"old_belief": null, "new_belief": 0.73},   // 新节点
        "101": {"old_belief": 0.85, "new_belief": 0.82},  // 被新边影响的已有节点
        "22": {"old_belief": 0.50, "new_belief": 0.45}    // 通过 contradiction 间接影响
    }
}
```

---

## 7. 与现有管线的集成

### 7.1 现有能力复用

| 新功能 | 复用的现有组件 | 需要新建的部分 |
|--------|-------------|--------------|
| `/verify/dry-run` 一致性检查 | `NNSearchOperator`, `DedupChecker` | 只读模式包装，不写入 |
| `/verify/dry-run` belief 预估 | `BeliefPropagation.run()` | 在临时图副本上执行局部 BP |
| `/explain/belief` | `Neo4jGraphStore.get_subgraph()` | 贡献度分解算法 |
| Merge belief 返回 | `InferenceEngine.compute_local_bp()` | 在 merger.py 中 wire 返回值 |

### 7.2 Review Pipeline 接入

`services/review_pipeline/` 已实现完整的验证链（embedding → NN search → CC/CP join → verify → BP），但尚未接入 commit engine。对 agent verification 场景，这个管线需要：

1. **接入 `CommitEngine.review()`**：替换 `StubLLMClient`，使用 `review_pipeline` 的完整链
2. **暴露 dry-run 模式**：管线前半段（embedding → NN search → dedup）可在不 commit 的情况下运行
3. **返回结构化验证结果**：当前 `ReviewResult` 只有 `approved: bool` + `issues: list[str]`，需要增加 `quality_scores`、`dedup_candidates` 等字段

### 7.3 与分布式 BP 的关系

[scaling_belief_propagation.md](scaling_belief_propagation.md) 规划的分布式 BP 对 agent verification 场景有特殊意义：

- **局部 BP（现有）**：agent 每步 merge 后跑 3-hop 局部 BP，延迟 < 200ms，适合实时门控
- **全局 BP（待实现）**：每 30 分钟一次全局一致性维护，可能改变远处节点的 belief
- **增量 BP（待实现）**：merge 后只传播受影响的子图，平衡实时性和一致性

对 agent 来说，局部 BP 提供即时反馈（"我这一步可信吗"），全局 BP 提供延迟修正（"综合所有 agent 的最新发现，这个结论还可信吗"）。

---

## 8. 定位与产品化方向

### 8.1 在 Agent Memory 栈中的位置

```
┌─────────────────────────────────────────────────┐
│  LLM Context Window                              │
│  短期工作记忆（无验证，无持久化）                   │
├─────────────────────────────────────────────────┤
│  Vector DB / RAG                                 │
│  长期检索记忆（无验证，无推理，可追溯到源文档）      │
├─════════════════════════════════════════════════─┤
│  Gaia — Verifiable Reasoning Memory (新层)       │
│  长期推理记忆（每步验证，可审计，可溯源，BP 一致性） │
└─────────────────────────────────────────────────┘
```

Gaia 不替代 RAG，而是在 RAG 之上增加**推理验证层**。Agent 用 RAG 检索文档，用 Gaia 存储和验证推理过程。

**一句话定位：RAG 让 agent 有了记忆，Gaia 让 agent 的记忆可以被信任。**

### 8.2 目标用户场景

| 场景 | Agent 行为 | Gaia 提供的价值 |
|------|-----------|---------------|
| **药物发现** | 跨论文推理分子性质 | 每步推理经 LLM 审核 + BP 一致性检查 |
| **材料科学** | 从实验数据归纳材料规律 | induction 边 probability 自动控制归纳跳跃 |
| **文献综述** | 综合多篇论文的观点 | contradiction 检测 + belief 竞争 |
| **假设生成** | 提出新假设并评估可信度 | conjecture 节点 + BP 计算全局一致的 belief |

### 8.3 差异化竞争力

```
vs. "Agent 直接问 LLM"：
  LLM 可能幻觉，无法验证推理过程。
  Gaia 的每一步都经过独立审核。

vs. "Agent + RAG"：
  RAG 只存储和检索，不验证推理链。
  Gaia 检查逻辑蕴含关系、矛盾、一致性。

vs. "Agent + 传统知识图谱"：
  传统 KG 没有概率，无法表达不确定性。
  Gaia 的 belief 值量化每个命题的可信度。

vs. "Agent + 人工审核"：
  人工审核不可扩展。
  Gaia 用 LLM 审核 + BP 一致性检查实现自动化验证，
  人工只需要在关键节点介入。
```

---

## 9. 与其他设计的关系

| 设计文档 | 关系 |
|---------|------|
| [version_dependency_environment.md](version_dependency_environment.md) | Agent workspace = Gaia environment（统一环境模型）；dry-run = 在环境中的预验证。见该文档 §3–§4 |
| [verification_providers.md](verification_providers.md) | Verification 使 confidence-gated progression（§4.2）更可靠——agent 门控基于经过验证的 probability |
| [text_structuring_service.md](text_structuring_service.md) | 结构化服务降低 agent 构造 commit 的门槛 |
| [question_as_discovery_context.md](question_as_discovery_context.md) | Agent 的子目标作为 question 的天然来源 |
