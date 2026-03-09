# 推理超边的 Question 字段：知识的发现语境

| 文档属性 | 值 |
|---------|---|
| 版本 | 1.0 |
| 日期 | 2026-03-04 |
| 关联文档 | [text_structuring_service.md](text_structuring_service.md), [agent_verifiable_memory.md](agent_verifiable_memory.md) §5, [version_dependency_environment.md](version_dependency_environment.md) |
| 状态 | Wishlist |

---

## 目录

1. [问题的提出](#1-问题的提出)
2. [第一性原理分析：question 的本质](#2-第一性原理分析question-的本质)
3. [两种理解及其不足](#3-两种理解及其不足)
4. [结论：question 是 context of discovery](#4-结论question-是-context-of-discovery)
5. [生成策略：质量取决于时机](#5-生成策略质量取决于时机)
6. [数据模型变更](#6-数据模型变更)
7. [对搜索层的影响](#7-对搜索层的影响)
8. [对 Agent 交互的影响](#8-对-agent-交互的影响)
9. [与其他设计的关系](#9-与其他设计的关系)
10. [实施路线图](#10-实施路线图)

---

## 1. 问题的提出

当前每条 reasoning 超边的形式是 `premises → reasoning → conclusion`：

```
tail: [Node_1("铜氧化物层状钙钛矿结构"), Node_2("Ba 掺杂引入空穴"), Node_3("电阻率 35K 以下急降")]
head: [Node_4("La₂₋ₓBaₓCuO₄ 是高温超导体")]
reasoning: ["步骤1...", "步骤2..."]
probability: 0.85
```

要理解这条边"在说什么"，必须先读所有 tail 节点的 content，再看 reasoning，再看 head。对人和 agent 都不友好。

自然的想法是：为每条超边附加一个 `question` 字段，使其变成 QA 对。但 question 到底是什么？它和已有结构是什么关系？是否冗余？

---

## 2. 第一性原理分析：question 的本质

### 2.1 推理链的信息完备性

`premises → reasoning → conclusion` 完成了一次完整的信息变换：

- **选择（selection）**：从十亿节点中选出 P1, P2, P3 放入 tail — 选择本身就是信息
- **推导（reasoning）**：经过逻辑步骤从前提得到结论 — 压缩、抽象层级跃升、隐含信息显式化
- **结论（conclusion）**：推理链的输出 — 一个新的、更高层的命题

从逻辑上看，这条链是**自足的**。`premises → conclusion` 已经回答了 "what is true and why"。

### 2.2 那 question 在哪？

回想知识的实际产生过程：

```
疑惑/好奇 → 提出问题 → 寻找相关前提 → 推理 → 得出结论
```

question 不是推理链的一个环节，它在推理链**之前**。它是推理链存在的理由。

为什么 P1, P2, P3 会被从十亿个节点中选出来放在一起？因为有一个 question 在引导这个选择。换一个 question，同样的知识图谱里会选出完全不同的前提组合。

### 2.3 两个维度

- `premises → reasoning → conclusion` 回答 **"what is true"** — 辩护语境（context of justification）
- `question` 回答 **"why do we care"** — 发现语境（context of discovery）

这是科学哲学中的经典区分。传统知识表示只存 justification，不存 discovery。数学定理不记录"当初为什么想证这个"。但这是信息的丢失 — 缺少动机的定理是最难理解的。

### 2.4 "提出好的问题是成功的一半"

这句话之所以成立，是因为 question 做了一件 premises 和 conclusion 都不做的事：**定义问题空间**。

- Premises 是事实（描述性的）
- Conclusion 是推导出的事实（描述性的）
- Reasoning 是推理过程（程序性的）
- Question 是方向（意向性的）

question 指向一个方向，说"看那里"。它不包含关于世界的信息，而包含关于**我们想知道什么**的信息。

---

## 3. 两种理解及其不足

### 3.1 理解 A：question 是前提的概括（前向）

```
tail: ["GIL 阻止多线程", "CPU 任务需并行", "multiprocessing 绕过 GIL"]

question(A): "Python 的 GIL、并行需求和 multiprocessing 之间有什么关系？"
```

- 从 tail 端生成，不需要知道 conclusion
- 本质是前提群的主题摘要
- 问题：开放性太强，区分度低；同一组前提推出不同结论时，question 相同

### 3.2 理解 B：question 是结论的问题化改写（后向）

```
conclusion: "CPU 密集型 Python 任务应使用 multiprocessing"

question(B): "Python CPU 密集型任务应该用 threading 还是 multiprocessing？"
```

- 从 conclusion 端生成，必须知道结论
- 本质是 `conclusion.rephrase_as_question()`
- 问题：**退化为结论的机械改写**，信息量为零

### 3.3 为什么都不对

A 和 B 都试图从推理链的**内部**生成 question。但 question 的本质是推理链的**外部动机**。从内部生成必然退化成已有信息的重述。

真正的 question 来自推理之前、来自一个**还不知道答案的人**：

```
真正的 question: "我的 Python 程序好慢，怎么加速？"
```

这和 A（前提摘要）和 B（结论改写）都不同。它用的是**提问者的词汇**（"好慢"、"加速"），而不是答案中的术语（"GIL"、"multiprocessing"）。这个词汇鸿沟才是 question 字段的真正价值所在。

---

## 4. 结论：question 是 context of discovery

### 4.1 定位

question 不是推理链的逻辑组成部分，而是推理链的**元数据** — 但不是普通元数据（如 `created_at`），而是有认知意义的元数据：

- 它记录推理链被创建的**智识动机**
- 它是知识的**认知索引** — 人通过问题来组织和检索知识
- 它在逻辑上冗余，但在认知上不冗余

### 4.2 一条边可以回答多个问题

同一条推理边可以服务于不同的问题：

```
edge: [foo()无null check, API返回可为null, null解引用crash] → [foo()有空指针bug]

问题1: "foo() 为什么会 crash？"          — 调试视角
问题2: "这段代码有没有安全隐患？"          — 审计视角
问题3: "API 错误处理的最佳实践是什么？"    — 学习视角
```

我们存储的 question 应该是**创建这条边的那个动机**（问题1、2、3中的某一个），而不是试图覆盖所有可能的问题。其他问题通过搜索引擎的 query expansion 来处理。

---

## 5. 生成策略：质量取决于时机

### 5.1 核心洞察

question 的质量取决于它在什么时候产生。在结论已知之后生成的 question 几乎必然退化 — 这不是 LLM 能力问题，而是信息论决定的：已知答案的人无法假装不知道。

### 5.2 三种来源，质量递减

| 来源 | 时机 | 质量 | 典型场景 |
|------|------|------|---------|
| **用户/Agent 提供** | 推理之前 | 最高 | Agent 带着子目标来查询和构建推理 |
| **从源文本提取** | 与推理同时 | 中等 | 论文 introduction 中的 research question |
| **事后 LLM 补全** | 推理之后 | 最低 | Edge 已存在，无 question，LLM 反向生成 |

### 5.3 在 Commit 流程中的处理

```
提交 AddEdge 时:
  ├── 提交者提供了 question        → 直接存储 (source = "user")
  ├── 未提供，有 source_text 上下文 → 从源文本提取 (source = "extracted")
  └── 都没有                        → review 阶段 LLM 补全 (source = "generated")
```

来源三（事后生成）的 question 标记为 `source = "generated"`，下游搜索可给予较低权重。类似 text structuring service 的 extraction discount（×0.8）思路。

### 5.4 鼓励前置提供

系统应鼓励在推理之前就提供 question：

- Agent 交互时，agent 的当前子目标自然就是 question
- API 的 AddEdge 操作增加可选 `question` 参数
- Text structuring service 提取时优先从源文本的问题句中提取
- Review 阶段如果发现缺少 question，可以 request changes 要求补充

---

## 6. 数据模型变更

### 6.1 HyperEdge 新增字段

```python
class HyperEdge(BaseModel):
    # ... 现有字段 ...
    question: str | None = None
    question_source: Literal["user", "extracted", "generated"] | None = None
```

- `question`：可选字段，context of discovery
- `question_source`：标记来源，供搜索加权使用

### 6.2 AddEdge 操作扩展

```python
class AddEdgeOp(BaseModel):
    op: Literal["add_edge"] = "add_edge"
    tail: list[NewNode | NodeRef]
    head: list[NewNode | NodeRef]
    question: str | None = None       # 新增
    reasoning: list[str] = []
    probability: float | None = None
```

### 6.3 question 是可选的

不是所有超边都需要 question：

- `reasoning` 类型的边：最适合加 question
- `contradiction` / `retraction` 类型的边：question 不太自然（"什么和什么矛盾？" 不是一个好问题）
- `join` / `meet` 类型的边：可以有，但不强制

---

## 7. 对搜索层的影响

### 7.1 两层召回

当前搜索在 node content 上做 BM25 + vector。增加 question 后，可以实现两层召回：

```
用户查询: "Python 程序太慢怎么办？"

第一层 — question 匹配（推理链级别）:
  匹配到 edge.question = "Python CPU 密集任务怎么加速？"
  → 返回整条推理链（含 premises, reasoning, conclusion, belief）

第二层 — node content 匹配（事实级别）:
  匹配到 node.content 包含 "GIL", "multiprocessing" 等
  → 返回单个节点
```

question 层匹配的是**推理链级别的意图**，node 层匹配的是**事实级别的内容**。两层互补。

### 7.2 question 的搜索权重

按来源加权：

```python
question_weight = {
    "user": 1.0,        # 真实的 discovery context
    "extracted": 0.8,    # 从源文本提取
    "generated": 0.5,    # 事后 LLM 生成，退化风险高
}
```

### 7.3 question 聚合

多条边如果有语义相似的 question，可以自然聚合成"关于这个问题的 N 种论证"：

```
question ≈ "铜氧化物能不能高温超导？"
  ├── edge_1: [实验数据A] → [结论] (probability=0.92)
  ├── edge_2: [理论计算B] → [结论] (probability=0.78)
  └── edge_3: [对比实验C] → [结论] (probability=0.85)
```

这类似同一个定理的多种证明。

---

## 8. 对 Agent 交互的影响

### 8.1 Question-driven 查询

Agent 的自然工作流：

```
Agent 有子目标 Q → 搜索 Gaia（Q 匹配 question）→ 找到相关推理链
  ├── belief 足够高 → 直接使用结论
  └── belief 不够 / 未找到 → 构建新推理链，提交 commit（携带 Q 作为 question）
```

这形成了一个良性循环：agent 的 question 驱动了知识的查询和创建，创建时带入的 question 又为未来的查询提供了索引。

### 8.2 与 Agent Verifiable Memory 的关系

在 [agent_verifiable_memory.md](agent_verifiable_memory.md) 中设计的 dry-run API 可以扩展：

```
POST /verify/dry-run
{
  "question": "Python CPU 密集任务怎么加速？",  // agent 的当前子目标
  "operations": [...]
}
```

返回中可以包含"是否已有类似 question 的推理链"，帮助 agent 避免重复推理。

---

## 9. 与其他设计的关系

| 设计文档 | 关系 |
|---------|------|
| [text_structuring_service.md](text_structuring_service.md) | 自动提取时同时提取 question（来源二），从源文本的问题句中识别 |
| [agent_verifiable_memory.md](agent_verifiable_memory.md) | Agent 的子目标作为 question 的天然来源（来源一） |
| [verification_providers.md](verification_providers.md) | 验证的是 conclusion，不是 question；question 不影响 verification 流程 |
| [scaling_belief_propagation.md](scaling_belief_propagation.md) | BP 不使用 question 字段；question 纯粹影响搜索层 |
| [version_dependency_environment.md](version_dependency_environment.md) | Question 随 Knowledge Package 版本一起管理；在 Gaia.toml 中可以按 question 搜索依赖的 package |

---

## 10. 实施路线图

### Phase 1：数据模型

- HyperEdge 增加 `question` + `question_source` 字段
- AddEdgeOp 增加可选 `question` 参数
- 存储层（LanceDB, Neo4j）适配新字段

### Phase 2：Commit 流程集成

- Review 阶段检测缺失的 question，LLM 自动补全（标记 `source = "generated"`）
- Review 反馈中可以建议 question 改写

### Phase 3：搜索层

- Question 字段加入 BM25 索引和向量索引
- 实现两层召回（question 层 + node 层）
- 按 `question_source` 加权

### Phase 4：Agent API

- 查询 API 支持 question-level 匹配
- Dry-run API 支持 question 去重检查
- Agent SDK 中 question 作为标准参数
