# M4 — Pipeline B: XML Extraction Spec

> **Status:** Draft
> **Date:** 2026-03-31
> **实现文件:** `gaia_lkm/pipelines/extract.py`

## 概述

M4 从论文 XML（arXiv / PubMed）中 rule-based 确定性提取命题和推理关系，产出与 M3 相同结构的 local FactorGraph + 参数化记录。不涉及 ML。

M4 与 M3 并行（都依赖 M1，不依赖彼此），产出相同的数据结构供 M5 Integrate 消费。

## 上游参考

- `docs/foundations/lkm/03-lifecycle.md §Pipeline B`：提取规则设计
- Master plan §M4：XML extraction 详细说明

---

## 输入

```python
@dataclass
class PipelineBInput:
    xml_content: str | bytes     # 论文 XML 原始内容
    metadata_id: str             # 数据库中的论文 metadata ID（全局唯一）
    source: str                  # "arxiv" | "pubmed"
    metadata: dict | None = None # 期刊等级、引用数等元数据（用于参数估计）
```

## 输出

```python
@dataclass
class PipelineBOutput:
    local_variables: list[LocalVariableNode]
    local_factors: list[LocalFactorNode]
    prior_records: list[PriorRecord]
    factor_param_records: list[FactorParamRecord]
    param_sources: list[ParameterizationSource]
    package_id: str              # "paper:{metadata_id}"
    version: str                 # 固定 "1.0.0"（论文不更新版本）
```

---

## 提取规则

### 命题提取 → LocalVariableNode

| XML 元素 | 输出 |
|---|---|
| 论文命题（abstract claims, hypotheses, conclusions） | `type="claim"`, `visibility="public"` |
| 背景设定（experimental conditions） | `type="setting"`, `visibility="public"` |
| 研究问题（research questions） | `type="question"`, `visibility="public"` |

QID 格式：

```
paper:{metadata_id}::{content_hash[:8]}
```

- `namespace` = `paper`
- `package_name` = `{metadata_id}`（数据库 metadata ID，全局唯一）
- `label` = `{content_hash[:8]}`（确定性 pseudo-label）

### 推理关系提取 → LocalFactorNode

| 提取的关系 | 输出 |
|---|---|
| 显式推理关系（"A implies B", "from X we conclude Y"） | `factor_type="strategy"`, `subtype="infer"` |
| 论文引用关系（paper A cites paper B's claim） | `factor_type="operator"`, `subtype="implication"` |

### 参数估计

Pipeline B 的参数由提取规则根据元数据估计，`source_class="heuristic"`。

**PriorRecord 估计规则**：

| 信号 | prior 估计 |
|---|---|
| 高影响力期刊 (Nature, Science, ...) | 0.7 - 0.85 |
| 中等期刊 | 0.5 - 0.7 |
| 预印本 / 低引用 | 0.3 - 0.5 |
| 多篇独立论文支持 | 向上调整 |

具体估计函数待实现时细化。所有值 Cromwell clamped。

**FactorParamRecord 估计规则**：

| 关系类型 | 条件概率估计 |
|---|---|
| 论文内显式推理 | 0.6 - 0.8（基于推理步骤的显式程度） |
| 引用关系 | 0.4 - 0.6（引用不等于强支持） |

**ParameterizationSource**：

```
ParameterizationSource:
    source_id    = "extract_{source}_{metadata_id}"
    source_class = "heuristic"  # Pipeline B 的参数是规则估计
    model        = "rule_based_v1"
    config       = { "source": source, "journal_tier": ..., "citation_count": ... }
    created_at   = extraction timestamp
```

---

## XML 解析

### arXiv XML

arXiv 论文通常有以下结构（JATS/NLM 或自定义 schema）：

- `<abstract>` → 提取主要 claims
- `<body><sec>` → 提取各节的推理关系
- `<back><ref-list>` → 提取引用关系

### PubMed XML

PubMed 使用 JATS XML：

- `<abstract>` → structured abstract 的各部分
- `<body>` → 正文推理
- `<ref-list>` → 引用

### 通用提取策略

1. **句子级切分**：将正文按句子切分
2. **命题识别**：rule-based pattern matching 识别 claim/setting/question
3. **关系识别**：pattern matching 识别推理关系（"therefore", "implies", "we conclude"）
4. **引用关系**：从 `<xref>` 标签提取引用链接

**不涉及 ML**：所有提取使用 rule-based patterns + lxml 解析。

---

## 关键约束

1. **确定性**：相同 XML + 相同 metadata → 相同输出
2. **source_class = "heuristic"**：Pipeline B 所有参数记录的 source_class 必须为 heuristic
3. **不依赖 ML**：纯 rule-based，不调用 LLM 或 embedding 模型
4. **QID 稳定性**：同一论文的多次提取产出相同 QIDs（基于 content_hash）
5. **与 Pipeline A 输出结构一致**：产出相同的 `(local_variables, local_factors, prior_records, ...)` 结构

---

## 测试要求

- `test_arxiv_extraction`：从 arXiv XML 提取正确的 variable/factor
- `test_pubmed_extraction`：从 PubMed XML 提取正确的 variable/factor
- `test_qid_format`：QID 为 `paper:{metadata_id}::{hash[:8]}` 格式
- `test_deterministic`：相同输入产出相同输出
- `test_parameter_estimation`：参数在合理范围内且 Cromwell clamped
- `test_source_class_heuristic`：所有 ParameterizationSource.source_class 为 heuristic

纯单元测试，放在 `tests/unit/test_pipeline_b.py`。需要准备 XML fixture 文件。

---

## 实现文件结构

```
gaia_lkm/pipelines/
    extract.py           # extract_paper() 主函数
    _xml_parser.py       # lxml 解析、句子切分
    _claim_extractor.py  # rule-based 命题识别
    _relation_extractor.py # rule-based 关系识别
    _param_estimator.py  # 基于元数据的参数估计
```

---

## 与 M3 的对比

| 方面 | M3 (Pipeline A) | M4 (Pipeline B) |
|------|----------------|----------------|
| 输入 | Gaia IR package + review reports | 论文 XML + metadata |
| source_class | official | heuristic |
| 参数来源 | reviewer 赋值 | 规则估计 |
| 确定性 | 是 | 是 |
| 依赖 ML | 否 | 否 |
| QID namespace | `reg` | `paper` |
