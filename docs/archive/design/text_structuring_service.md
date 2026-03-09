# 文本自动结构化服务设计

| 文档属性 | 值 |
|---------|---|
| 版本 | 1.0 |
| 日期 | 2026-03-04 |
| 关联文档 | [phase1_billion_scale.md](phase1_billion_scale.md) §5, [agent_verifiable_memory.md](agent_verifiable_memory.md), [version_dependency_environment.md](version_dependency_environment.md) |
| 状态 | Wishlist |

---

## 目录

1. [动机](#1-动机)
2. [分层架构](#2-分层架构)
3. [接口设计](#3-接口设计)
4. [提取流程](#4-提取流程)
5. [质量控制](#5-质量控制)
6. [与现有架构的集成](#6-与现有架构的集成)
7. [领域适配](#7-领域适配)
8. [实施路线图](#8-实施路线图)
9. [与其他设计的关系](#9-与其他设计的关系)

---

## 1. 动机

### 1.1 门槛问题

Gaia 的 commit API 接受结构化的超边操作（`AddEdge` with `tail[]`, `head[]`, `probability`, `reasoning`）。这对开发者友好，但对普通研究员来说门槛极高：

```
用户想表达: "论文里说 A 和 B 共同导致了 C"

当前需要:
  1. 理解什么是超边、tail/head/probability 的语义
  2. 手动构造 JSON:
     {"type": "add_edge",
      "tail": [{"new": {"content": "A", "prior": 0.8}},
               {"new": {"content": "B", "prior": 0.7}}],
      "head": [{"new": {"content": "C", "prior": 1.0}}],
      "edge_type": "paper-extract",
      "probability": 0.85,
      "reasoning": ["A 和 B 共同导致 C"]}
  3. 调用 POST /commits

→ 只有开发者能用，普通研究员用不了
```

如果 Gaia 要服务广泛的学术用户和 AI agent，需要一个"贴段文本就能用"的入口。

### 1.2 批量导入的必要性

Phase 1 目标处理 1000 万篇论文。不可能人工为每段文本构造超边结构，需要自动化的文本 → 超边提取管线。

### 1.3 为什么不做进 Gaia 核心

提取质量高度依赖领域：论文、代码、实验笔记、对话记录——每种文本的提取策略完全不同。如果做进核心：

- 要么做一个很差的通用方案
- 要么核心变成一个臃肿的 NLP 管线

正确做法：**独立的结构化服务，放在 Gaia Core 前面，输出标准 commit 操作**。

> **Knowledge Package 输出**：在 [version_dependency_environment.md](version_dependency_environment.md) 的 Cargo-like 架构中，结构化服务的输出物是 **Knowledge Package**——一篇论文经过结构化服务处理后，成为一个带版本的 Knowledge Package，可以发布到 Gaia Server（registry），被其他 package 声明为依赖。这与 Cargo 中 `cargo publish` 的思路一致。

---

## 2. 分层架构

### 2.1 三层模型

从自然语言文本到 Gaia 图中的超边，有三个不同层次的工作：

```
自然语言文本
    │
    ▼
[层 1] 命题提取 (Proposition Extraction)
    从文本中识别出独立命题
    "这段话里有 3 个 claim"
    │
    ▼
[层 2] 关系识别 (Relation Identification)
    识别命题之间的推理关系
    "命题 A + B 是前提，C 是结论，类型是 induction"
    │
    ▼
[层 3] 结构化写入 (Structured Ingestion)
    组装成 AddEdge 操作，走 commit 流程
    tail=[A, B], head=[C], type="induction", probability=0.7
```

Gaia Core 拥有层 3（commit API）。本文档设计的 Structuring Service 负责层 1 和层 2。

### 2.2 系统边界

```
┌─────────────────────────────────────────────────┐
│  Structuring Service (结构化服务)                  │  ← 本文档设计
│  独立服务，可替换，可按领域定制                      │
│                                                   │
│  文本 → LLM 提取 → 命题 + 关系 → AddEdge 操作     │
├─────────────────────────────────────────────────┤
│  Gaia Core (核心层)                               │  ← 不改
│  commit → review → merge → BP                    │
│  只接受结构化操作，不关心文本怎么来的               │
└─────────────────────────────────────────────────┘
```

类比其他系统：

| 类比系统 | 核心 | 结构化层 |
|---------|------|---------|
| 数据库 | SQL INSERT | ETL pipeline / CSV import |
| Git | git commit | IDE / 代码编辑器 |
| 搜索引擎 | 倒排索引 + 查询 | 爬虫 + 解析器 |
| **Gaia** | **commit API + BP** | **Structuring Service** |

数据库不负责生成数据，但好的数据库生态都有 ETL 工具。Gaia 不负责理解文本，但提供一个标准的结构化服务。

---

## 3. 接口设计

### 3.1 主端点：`POST /ingest/text`

```
POST /ingest/text

Request:
{
    "text": "MgB₂在39K以下表现出超导性。这与BCS理论的预测一致，
             因为MgB₂的电子-声子耦合常数很高。然而最近有研究
             质疑传统BCS理论能否完全解释MgB₂的双能隙现象。",
    "source": {
        "paper_id": "10.1234/...",
        "section": "Discussion",
        "page": 5
    },
    "mode": "suggest",
    "domain_hint": "materials-science"
}
```

**参数说明：**

| 参数 | 必填 | 说明 |
|------|------|------|
| `text` | 是 | 自然语言文本，支持纯文本和 markdown |
| `source` | 否 | 来源信息（论文 DOI、章节、页码等），写入节点的 `paper_id`/`section` |
| `mode` | 否 | `"suggest"` (默认) 或 `"auto"`，见 §3.2 |
| `domain_hint` | 否 | 领域提示，用于选择领域特定的提取策略，见 §7 |

### 3.2 两种模式

**`mode: "suggest"` — 建议模式（默认）**

返回提取结果供用户确认/修改，不自动提交 commit。适用于交互式使用。

```
Response:
{
    "suggested_operations": [
        {
            "type": "add_edge",
            "edge_type": "paper-extract",
            "tail": [
                {"new": {"content": "MgB₂的电子-声子耦合常数很高",
                         "prior": 0.85, "type": "paper-extract"}}
            ],
            "head": [
                {"new": {"content": "MgB₂在39K以下表现出超导性",
                         "prior": 0.9, "type": "paper-extract"}}
            ],
            "probability": 0.85,
            "reasoning": ["BCS理论: 高电子-声子耦合 → 超导"]
        },
        {
            "type": "add_edge",
            "edge_type": "contradiction",
            "tail": [
                {"new": {"content": "MgB₂存在双能隙现象",
                         "prior": 0.8, "type": "paper-extract"}}
            ],
            "head": [
                {"new": {"content": "传统BCS理论完全解释MgB₂超导机制",
                         "prior": 0.6, "type": "paper-extract"}}
            ],
            "probability": 0.6,
            "reasoning": ["双能隙现象挑战单能隙BCS框架"]
        }
    ],
    "extraction_confidence": 0.75,
    "ambiguities": [
        "无法确定'最近有研究'是否特指某篇论文，建议补充来源"
    ],
    "stats": {
        "propositions_extracted": 4,
        "edges_extracted": 2,
        "text_coverage": 0.92
    }
}
```

用户确认后，将 `suggested_operations` 作为 `POST /commits` 的 `operations` 提交——走正常 commit → review → merge 流程。

**`mode: "auto"` — 自动模式**

直接创建 commit 并返回 commit_id。适用于批量导入。

```
Response:
{
    "commit_id": "abc123",
    "status": "pending_review",
    "operations_count": 2,
    "extraction_confidence": 0.75,
    "note": "已自动提交，需经过 review 和 merge 才会入图"
}
```

自动模式仍然走完整的 commit → review → merge 流程。LLM 提取不绕过验证。

### 3.3 批量端点：`POST /ingest/batch`

批量导入多段文本（如一整篇论文的多个段落）。

```
POST /ingest/batch

Request:
{
    "items": [
        {"text": "第一段...", "source": {"section": "Introduction"}},
        {"text": "第二段...", "source": {"section": "Methods"}},
        {"text": "第三段...", "source": {"section": "Results"}}
    ],
    "source": {"paper_id": "10.1234/..."},
    "mode": "auto"
}

Response:
{
    "batch_id": "batch_456",
    "commits_created": 3,
    "total_operations": 12,
    "status": "pending_review"
}
```

---

## 4. 提取流程

### 4.1 管线设计

```
输入文本
    │
    ▼
┌──────────────────────┐
│ 1. 文本预处理         │  分句、去除格式噪音、识别引用标记
└──────────┬───────────┘
           ▼
┌──────────────────────┐
│ 2. 命题提取 (LLM)     │  识别独立的 claim / assertion / hypothesis
│    输入: 文本段落      │  每个命题附带:
│    输出: 命题列表      │    - content (命题文本)
└──────────┬───────────┘    - type (paper-extract / conjecture)
           ▼                - prior 建议值
┌──────────────────────┐
│ 3. 关系识别 (LLM)     │  识别命题间的推理关系
│    输入: 命题列表      │  每条关系附带:
│    输出: 关系列表      │    - tail / head
└──────────┬───────────┘    - edge_type
           ▼                - probability 建议值
┌──────────────────────┐    - reasoning
│ 4. 去重检查           │  与 Gaia 已有命题对比
│    调用 Gaia search   │  已有 → NodeRef, 新增 → NewNode
│    API (只读)         │
└──────────┬───────────┘
           ▼
┌──────────────────────┐
│ 5. 组装 Operations    │  生成 AddEdge 操作列表
│    应用 discount      │  probability × 0.8 (提取折扣)
└──────────┬───────────┘
           ▼
    输出: suggested_operations
```

### 4.2 LLM Prompt 设计要点

命题提取 prompt 需要引导 LLM 输出结构化结果：

```
你是一个科学文本分析器。给定一段文本，识别其中的独立命题和推理关系。

每个命题是一个可以独立判断真假的声明 (claim)。
每条推理关系描述命题之间的逻辑连接。

输出格式 (XML):
<extraction>
  <propositions>
    <prop id="P1" type="paper-extract" prior="0.85">
      命题文本
    </prop>
    ...
  </propositions>
  <edges>
    <edge type="paper-extract" probability="0.85">
      <tail>P1, P2</tail>
      <head>P3</head>
      <reasoning>推理说明</reasoning>
    </edge>
    ...
  </edges>
</extraction>
```

这与 `review_pipeline` 已有的 XML 解析基础设施（`xml_parser.py`）兼容。

---

## 5. 质量控制

### 5.1 提取折扣 (Extraction Discount)

LLM 提取的命题和关系不如人工精确。所有自动提取的概率值应乘以一个折扣系数：

```
自动提取的 probability = LLM 建议值 × extraction_discount

默认 extraction_discount = 0.8
```

这意味着自动提取的边 probability 上限为 0.8，反映了提取过程本身的不确定性。用户手动确认后可以移除折扣。

### 5.2 Confidence 阈值

提取管线对自身输出有一个 confidence 评估。低于阈值时：

| confidence | 行为 |
|-----------|------|
| ≥ 0.7 | 正常返回 suggested_operations |
| 0.4 - 0.7 | 返回结果 + 警告 ambiguities 列表 |
| < 0.4 | 拒绝自动提取，建议用户手动结构化 |

### 5.3 Gaia 的验证承诺不变

无论是 suggest 模式还是 auto 模式，提取结果最终都走正常的 commit → review → merge 流程：

```
Structuring Service 提取  →  commit (pending_review)
                                ↓
                            review (LLM 深度审核)
                                ↓
                            merge (入图 + BP)
```

结构化服务降低了**输入门槛**，但不降低**验证标准**。即使提取有误，review 阶段仍然会检查逻辑蕴含关系和一致性。这是双重保险：提取 LLM 负责"猜"，review LLM 负责"查"。

---

## 6. 与现有架构的集成

### 6.1 架构位置

```
现有:
  Paper Ingest Agent (外部) ──→ POST /commits ──→ Gaia Core

加入 Structuring Service 后:

  用户/Agent                     Structuring Service          Gaia Core
      │                               │                         │
      ├─ POST /ingest/text ──────────→│                         │
      │                               ├─ LLM 提取               │
      │                               ├─ GET /search (去重) ───→│
      │                               │←─ 已有命题 ─────────────┤
      │←─ suggested_operations ───────┤                         │
      │                               │                         │
      │  (用户确认/修改)               │                         │
      │                               │                         │
      ├─ POST /commits ──────────────────────────────────────→│
      │                                                         ├─ review
      │                                                         ├─ merge
      │←─ commit result ──────────────────────────────────────┤
```

### 6.2 复用现有组件

| 新功能 | 复用的现有组件 |
|--------|-------------|
| 命题提取 (LLM) | `review_pipeline/llm_client.py` (litellm 封装) |
| XML 输出解析 | `review_pipeline/xml_parser.py` |
| 去重检查 | `commit_engine/dedup.py` (DedupChecker) |
| 相似命题搜索 | `search_engine` (向量 + BM25) |
| Embedding 计算 | `review_pipeline/operators/embedding.py` |

### 6.3 部署形式

Structuring Service 是一个**独立的 FastAPI 服务**，与 Gaia Core 通过 HTTP API 通信：

```
Structuring Service (:8001)
    ├── /ingest/text
    ├── /ingest/batch
    └── 内部调用 Gaia Core API (:8000) 做去重查询
```

也可以作为 Gaia Gateway 的一组路由挂载（如果不想单独部署），但逻辑上保持独立。

---

## 7. 领域适配

### 7.1 可插拔的提取策略

不同领域的文本结构差异很大：

| 领域 | 文本特点 | 提取重点 |
|------|---------|---------|
| 材料科学 | 实验条件 + 性质测量 + 因果解释 | 材料-性质关系，实验条件作为前提 |
| 生物医学 | 基因-蛋白-表型链 | 分子通路，药物靶点 |
| 数学 | 定义-引理-定理-证明 | 逻辑依赖链，proof sketch |
| CS/代码 | 架构决策、API 约定 | 设计意图 → 实现选择 |

### 7.2 策略注册机制

```python
class ExtractionStrategy(ABC):
    """提取策略抽象基类"""

    @abstractmethod
    async def extract_propositions(self, text: str) -> list[Proposition]:
        """从文本中提取命题"""

    @abstractmethod
    async def identify_relations(self, propositions: list[Proposition]) -> list[Relation]:
        """识别命题间的推理关系"""

    @property
    @abstractmethod
    def domain(self) -> str:
        """策略适用的领域标识"""


# 注册
registry = StrategyRegistry()
registry.register(MaterialsScienceStrategy())
registry.register(BiomedicalStrategy())
registry.register(GeneralStrategy())  # 默认 fallback
```

用户通过 `domain_hint` 参数选择策略。不提供时使用 `GeneralStrategy`。

### 7.3 默认通用策略

Phase 1 先提供一个通用的 LLM 提取策略，不做领域特化。领域特定策略作为后续迭代方向。通用策略的 prompt 需要：

- 能处理大多数学术文本
- 输出格式统一（XML，兼容 `xml_parser.py`）
- 对不确定的提取标记 ambiguity
- extraction_discount 设为保守值 (0.8)

---

## 8. 实施路线图

### Phase 1：基本可用

| 任务 | 说明 |
|------|------|
| 通用提取 prompt | 设计并测试 proposition extraction + relation identification prompt |
| `/ingest/text` suggest 模式 | 返回 suggested_operations，用户手动确认后提交 |
| 复用 `xml_parser.py` | 解析 LLM 的 XML 输出 |
| 复用 `DedupChecker` | 对提取的命题做去重检查 |
| 提取折扣 | probability × 0.8 |

### Phase 2：批量导入

| 任务 | 说明 |
|------|------|
| `/ingest/text` auto 模式 | 自动创建 commit |
| `/ingest/batch` | 批量处理多段文本 |
| 论文 PDF 集成 | Grobid 解析 → 分段 → 批量 ingest |
| confidence 阈值 | 低 confidence 拒绝自动提取 |

### Phase 3：领域适配

| 任务 | 说明 |
|------|------|
| `ExtractionStrategy` 抽象 | 可插拔策略接口 |
| 材料科学策略 | 第一个领域特定策略 |
| 策略评估框架 | 基于标注数据集评估提取质量（precision/recall） |
| Few-shot 适配 | 用户提供几个示例，自动适配新领域 |

---

## 9. 与其他设计的关系

| 设计文档 | 关系 |
|---------|------|
| [version_dependency_environment.md](version_dependency_environment.md) | 结构化服务输出 Knowledge Package（带版本的知识单元），可发布到 Gaia Server registry |
| [agent_verifiable_memory.md](agent_verifiable_memory.md) | 结构化服务降低 agent 构造 commit 的门槛 |
| [verification_providers.md](verification_providers.md) | 提取折扣（probability × 0.8）可以被后续 verification 正确覆盖 |
| [question_as_discovery_context.md](question_as_discovery_context.md) | 自动提取时同时从源文本的问题句中提取 question |
